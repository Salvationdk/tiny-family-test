"""Account-scoped learned place listing, naming, deletion and zone promotion."""
from __future__ import annotations

import math
import asyncio
from uuid import uuid4
from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .communications import own_person
from datetime import datetime, timezone
from .const import DOMAIN, PLACES_FILE, ZONE_SUGGEST_MIN_VISITS, SHARED_PLACES_FILE
from .utils import _hav
from .storage import _save_places, _load_places
from .sensors import _publish
from .zones_api import zone_collection, validate_new_zone
from .privacy import shared_map_zones


def describe_places(hass, places):
    zones = shared_map_zones(hass)
    out = []
    for pl in places or []:
        if not isinstance(pl, dict):
            continue
        try:
            lat, lon = float(pl["lat"]), float(pl["lon"])
            if not (math.isfinite(lat) and math.isfinite(lon) and
                    -90 <= lat <= 90 and -180 <= lon <= 180):
                continue
        except (KeyError, ValueError, TypeError):
            continue
        containing_zones = [z["name"] for z in zones if
                            _hav(lat, lon, z["latitude"], z["longitude"]) <=
                            z["radius_m"] + 10]
        name = str(pl.get("label") or "").strip()[:80]
        try:
            visits = max(0, int(pl.get("visits") or 0))
            mins = max(0, int(pl.get("min") or 0))
        except (ValueError, TypeError):
            continue
        # A destination may be located *inside* a zone. Only actual
        # zone-seeded entries are zones, never an unrelated learned stay.
        if pl.get("source") == "zone":
            status = "zone"
        elif name and name.casefold() not in ("ukendt sted", "ukendt", "unknown"):
            status = "named"
        elif visits >= ZONE_SUGGEST_MIN_VISITS:
            status = "suggested"
        else:
            status = "learned"
        out.append({
            "latitude": round(lat, 6), "longitude": round(lon, 6),
            "name": name or "Ukendt sted", "visits": visits, "minutes": mins,
            "last": str(pl.get("last") or "")[:40], "status": status,
            "private": pl.get("private") is True,
            "zones": containing_zones[:5],
        })
    return sorted(out, key=lambda row: (row["status"] != "suggested", -row["visits"]))


def match_place(places, lat, lon):
    if type(lat) not in (float, int) or type(lon) not in (float, int):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    for place in places or []:
        if isinstance(place, dict):
            try:
                if _hav(float(place["lat"]), float(place["lon"]), lat, lon) <= 10:
                    return place
            except (KeyError, TypeError, ValueError):
                pass
    return None


def collapse_suggestions(places, *, radius_m=35):
    """Group nearby unpromoted stays without deleting original observations.

    Only the presentation layer is grouped; personal place edits remain
    addressable under each person's own history.
    """
    groups = []
    for place in places:
        duplicate = next((group for group in groups if
            _hav(place["latitude"], place["longitude"],
                 group["latitude"], group["longitude"]) <= radius_m), None)
        if duplicate is None:
            groups.append({**place, "sources_count": 1,
                           "people": [place["person_name"]],
                           "sources": [place]})
            continue
        duplicate["sources_count"] += 1
        duplicate["visits"] += place["visits"]
        duplicate["minutes"] += place["minutes"]
        if place["person_name"] not in duplicate["people"]:
            duplicate["people"].append(place["person_name"])
        duplicate["sources"].append(place)
        # Do not expose a private learned place as another member's
        # shared suggestion, nor merge its counts into a public item.
        duplicate["private"] = duplicate["private"] or place["private"]
    return groups



class TinyFamilyPlacesView(HomeAssistantView):
    """Personal learned places and explicitly published family places.

    Private raw GPS points are not published automatically. Anyone linked to
    the family may create a shared place; only admins may edit or delete it.
    Learned suggestions with enough visits
    are visible to the family unless an administrator marks them private.
    """
    url = "/api/tiny_family/places"
    name = "api:tiny_family:places"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    def context(self, request):
        entry = self.hass.data.get("tiny_family_runtime", {}).get("entry")
        if entry is None:
            return None, None, None
        cfg = {**entry.data, **entry.options}
        person = own_person(request["hass_user"].id, cfg.get("persons") or [],
                            cfg.get("owners") or {})
        state = self.hass.data.get(DOMAIN, {}).get(person) if person else None
        return entry, person, state

    def allowed(self, request, entry, person):
        return entry is not None and (person is not None or request["hass_user"].is_admin)

    async def _shared(self):
        runtime = self.hass.data.setdefault("tiny_family_runtime", {})
        # Serialise lazy initialization to prevent two first requests from
        # loading separate copies of the shared place collection.
        lock = runtime.setdefault("shared_places_lock", asyncio.Lock())
        async with lock:
            if "shared_places" not in runtime:
                raw = await self.hass.async_add_executor_job(
                    _load_places, self.hass.config.path(SHARED_PLACES_FILE)
                )
                runtime["shared_places"] = raw if isinstance(raw, list) else []
            return runtime["shared_places"]

    async def _save_shared(self):
        await self.hass.async_add_executor_job(
            _save_places, self.hass.config.path(SHARED_PLACES_FILE),
            self.hass.data["tiny_family_runtime"]["shared_places"],
        )

    @staticmethod
    def _coordinates(payload):
        try:
            # Do not accept booleans as latitude/longitude.
            if type(payload.get("latitude")) not in (int, float) or type(payload.get("longitude")) not in (int, float):
                raise ValueError("Coordinates must be numeric")
            lat, lon = float(payload["latitude"]), float(payload["longitude"])
            if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Invalid coordinates")
            return round(lat, 6), round(lon, 6)
        except (ValueError, TypeError, KeyError, OverflowError):
            raise ValueError("Invalid coordinates") from None

    @staticmethod
    def _name(payload):
        name = payload.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError("Name must be 1-80 characters")
        return name.strip()

    async def get(self, request):
        entry, person, state = self.context(request)
        if entry is None:
            return web.json_response({"message": "Not configured"}, status=503)
        if not self.allowed(request, entry, person):
            return web.json_response({"message": "Account not linked"}, status=403)
        admin = bool(request["hass_user"].is_admin)
        seen = state.get("gps_seen_at") if state else None
        age = (round(max(0, datetime.now(timezone.utc).timestamp() - seen) / 60)
               if isinstance(seen, (float, int)) else None)
        shared = await self._shared()
        common = [{
            "id": place["id"], "name": place["name"],
            "latitude": place["latitude"], "longitude": place["longitude"],
            "created_by_name": place.get("created_by_name", "Familiemedlem"),
            "can_edit": admin,
            "can_delete": admin,
        } for place in shared if isinstance(place, dict) and
            all(k in place for k in ("id", "name", "latitude", "longitude"))]
        def published_at(place):
            return next((saved for saved in common
                if all(type(saved.get(key)) in (float, int) and
                       math.isfinite(saved[key])
                       for key in ("latitude", "longitude"))
                and _hav(place["latitude"], place["longitude"],
                         saved["latitude"], saved["longitude"]) <= 45), None)

        own_places = describe_places(self.hass, state.get("places")) if state else []
        for place in own_places:
            if place["status"] == "suggested":
                published = published_at(place)
                if published:
                    place["status"] = "published"
                    place["name"] = str(published["name"])
        proposals = []
        managed = []
        known_names = []
        cfg = {**entry.data, **entry.options}
        for member in cfg.get("persons") or []:
            if not admin and member != person and member in (cfg.get("ghost_people") or []):
                continue
            member_state = self.hass.data.get(DOMAIN, {}).get(member)
            if not member_state:
                continue
            label = self.hass.states.get(member)
            display = label.name if label is not None else member
            for place in describe_places(self.hass, member_state.get("places")):
                if place["status"] == "zone":
                    continue
                if place["private"] and not admin and member != person:
                    continue
                record = {**place, "person": member, "person_name": display}
                if place["status"] == "named":
                    known_names.append(record)
                    if admin:
                        managed.append(record)
                    continue
                if place["status"] != "suggested":
                    continue
                # A published suggestion remains in personal history, but
                # it is no longer a suggestion once a shared place exists.
                if published_at(place):
                    continue
                proposals.append(record)
        # A named learned destination also supersedes nearby suggestions
        # from other people. Preserve their personal history for themselves.
        proposals = [p for p in proposals if not any(
            _hav(p["latitude"], p["longitude"],
                 target["latitude"], target["longitude"]) <= 35
            for target in known_names)]
        # Do not group private and public records together.
        proposals.sort(key=lambda item: (-item["visits"], -item["minutes"]))
        public = collapse_suggestions([p for p in proposals if not p["private"]])
        private = collapse_suggestions([p for p in proposals if p["private"]])
        proposals = sorted(public + private,
                           key=lambda item: (-item["visits"], -item["minutes"]))
        managed.sort(key=lambda item: (item["person_name"], item["name"]))
        return web.json_response({
            "person": person, "places": own_places,
            "shared_places": common,
            "family_suggestions": proposals,
            "admin_suggestions": proposals if admin else [],
            "managed_places": managed if admin else [],
            "can_create_zone": admin,
            "can_manage_all_places": admin,
            "gps_health": state.get("gps_health", "unknown") if state else "unknown",
            "gps_age_minutes": age,
        }, headers={"Cache-Control": "no-store, private"})

    async def post(self, request):
        return await self.write(request, "create")

    async def put(self, request):
        return await self.write(request, "rename")

    async def delete(self, request):
        if not request["hass_user"].is_admin:
            return web.json_response({"message": "Administrator required"}, status=403)
        return await self.write(request, "delete")

    async def write(self, request, action):
        entry, person, state = self.context(request)
        if entry is None:
            return web.json_response({"message": "Not configured"}, status=503)
        if not self.allowed(request, entry, person):
            return web.json_response({"message": "Account not linked"}, status=403)
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("Expected object")
            if payload.get("kind") == "shared" or "shared_id" in payload:
                return await self._write_shared(request, payload, action, person)
            if payload.get("kind") == "privacy":
                action = "privacy"
            # The old POST operation publishes one existing personal suggestion
            # as a Home Assistant zone. It remains administrator-only.
            return await self._write_personal(request, payload,
                "zone" if action == "create" else action, person, state)
        except (ValueError, TypeError, KeyError, AttributeError):
            return web.json_response({"message": "Invalid place action"}, status=400)

    async def _write_shared(self, request, payload, action, person):
        admin = bool(request["hass_user"].is_admin)
        if action == "delete" and not admin:
            return web.json_response({"message": "Administrator required"}, status=403)
        shared = await self._shared()
        user_id = request["hass_user"].id
        lock = self.hass.data["tiny_family_runtime"]["shared_places_lock"]
        async with lock:
            if action == "create":
                name = self._name(payload)
                lat, lon = self._coordinates(payload)
                if not admin:
                    # An admin-private learned place must not become public
                    # via the shared-place creation endpoint.
                    for member_state in self.hass.data.get(DOMAIN, {}).values():
                        if match_place([p for p in member_state.get("places", [])
                                        if p.get("private") is True], lat, lon):
                            return web.json_response({"message": "Private place"}, status=403)
                if len(shared) >= 1000:
                    return web.json_response({"message": "Too many shared places"}, status=409)
                existing = next((p for p in shared if
                    _hav(lat, lon, float(p["latitude"]), float(p["longitude"])) < 10 or
                    (str(p.get("name", "")).casefold() == name.casefold() and
                     _hav(lat, lon, float(p["latitude"]), float(p["longitude"])) < 75)), None)
                if existing:
                    # Idempotent creation: do not surface a duplicate error
                    # or insert a second copy of the same destination.
                    return web.json_response({
                        "saved": True, "existing": True,
                        "shared_id": existing["id"], "name": existing["name"],
                    }, headers={"Cache-Control": "no-store"})
                person_state = self.hass.states.get(person) if person else None
                place = {
                    "id": uuid4().hex, "name": name, "latitude": lat, "longitude": lon,
                    "created_by": user_id,
                    "created_by_name": (person_state.name if person_state else "Administrator"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                shared.append(place)
            else:
                identifier = payload.get("shared_id")
                if not isinstance(identifier, str) or len(identifier) != 32:
                    raise ValueError("Invalid shared place ID")
                place = next((p for p in shared if p.get("id") == identifier), None)
                if place is None:
                    return web.json_response({"message": "Place not found"}, status=404)
                if not admin:
                    return web.json_response({"message": "Administrator required"}, status=403)
                if action == "delete":
                    shared.remove(place)
                else:
                    place["name"] = self._name(payload)
                    # Coordinate edits require both latitude and longitude.
                    if "latitude" in payload or "longitude" in payload:
                        place["latitude"], place["longitude"] = self._coordinates(payload)
            await self._save_shared()
        return web.json_response({"saved": True, "action": action},
                                 headers={"Cache-Control": "no-store"})

    async def _write_personal(self, request, payload, action, person, state):
        admin = bool(request["hass_user"].is_admin)
        if action in ("delete", "privacy", "rename") and not admin:
            return web.json_response({"message": "Administrator required"}, status=403)
        if action == "zone" and not admin:
            return web.json_response({"message": "Administrator required"}, status=403)
        target = payload.get("person", person)
        if not isinstance(target, str) or (target != person and not admin):
            return web.json_response({"message": "Administrator required"}, status=403)
        if admin and target != person:
            entry = self.hass.data["tiny_family_runtime"]["entry"]
            cfg = {**entry.data, **entry.options}
            if target not in (cfg.get("persons") or []):
                return web.json_response({"message": "Person not configured"}, status=404)
            state = self.hass.data.get(DOMAIN, {}).get(target)
        if state is None:
            return web.json_response({"message": "Person not configured"}, status=404)
        lat, lon = self._coordinates(payload)
        pl = match_place(state.get("places"), lat, lon)
        if pl is None:
            return web.json_response({"message": "Place not found"}, status=404)
        if describe_places(self.hass, [pl])[0]["status"] == "zone":
            return web.json_response({"message": "Edit this HA zone on the family map"}, status=409)
        if action == "zone":
            name = self._name(payload)
            candidate = validate_new_zone({
                "name": name, "latitude": lat, "longitude": lon,
                "radius": payload.get("radius", 100),
            })
            if any(_hav(lat, lon, z["latitude"], z["longitude"]) < 10
                   for z in shared_map_zones(self.hass)):
                return web.json_response({"message": "Zone already exists"}, status=409)
            collection = zone_collection(self.hass)
            if collection is None:
                return web.json_response({"message": "Zone storage unavailable"}, status=503)
            await collection.async_create_item(candidate)
            # The newly created HA zone is separate from the observed stay.
            # Naming the stay completes its proposal while keeping it a
            # distinct destination, including when inside its new zone.
            pl["label"], pl["source"] = name, "named"
        elif action == "rename":
            pl["label"], pl["source"] = self._name(payload), "named"
        elif action == "privacy":
            if type(payload.get("private")) is not bool:
                raise ValueError("Privacy flag required")
            pl["private"] = payload["private"]
        else:
            state["places"].remove(pl)
        await self.hass.async_add_executor_job(
            _save_places, self.hass.config.path(PLACES_FILE),
            {p: s.get("places") or [] for p, s in self.hass.data.get(DOMAIN, {}).items()},
        )
        _publish(self.hass, target)
        return web.json_response({"saved": True, "action": action},
                                 headers={"Cache-Control": "no-store"})
