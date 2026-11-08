"""Account-scoped learned place listing, naming, deletion and zone promotion."""
from __future__ import annotations

import math
from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .communications import own_person
from datetime import datetime, timezone
from .const import DOMAIN, PLACES_FILE, ZONE_SUGGEST_MIN_VISITS
from .utils import _hav
from .storage import _save_places
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
        in_zone = any(_hav(lat, lon, z["latitude"], z["longitude"]) <=
                      z["radius_m"] + 10 for z in zones)
        name = str(pl.get("label") or "").strip()[:80]
        try:
            visits = max(0, int(pl.get("visits") or 0))
            mins = max(0, int(pl.get("min") or 0))
        except (ValueError, TypeError):
            continue
        if in_zone or pl.get("source") == "zone":
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


class TinyFamilyPlacesView(HomeAssistantView):
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
        return entry, person, (self.hass.data.get(DOMAIN, {}).get(person)
                               if person else None)

    async def get(self, request):
        entry, person, state = self.context(request)
        if entry is None:
            return web.json_response({"message": "Not configured"}, status=503)
        if state is None:
            return web.json_response({"message": "Account not linked"}, status=403)
        seen = state.get("gps_seen_at")
        age = (round(max(0, datetime.now(timezone.utc).timestamp() - seen) / 60)
               if isinstance(seen, (float, int)) else None)
        return web.json_response({
            "person": person, "places": describe_places(self.hass, state.get("places")),
            "can_create_zone": bool(request["hass_user"].is_admin),
            "ghost_active": person in ({**entry.data, **entry.options}.get("ghost_people") or []),
            "gps_health": state.get("gps_health", "unknown"),
            "gps_age_minutes": age,
        }, headers={"Cache-Control": "no-store, private"})

    async def put(self, request):
        return await self.write(request, "rename")

    async def delete(self, request):
        return await self.write(request, "delete")

    async def post(self, request):
        return await self.write(request, "zone")

    async def write(self, request, action):
        entry, person, state = self.context(request)
        if entry is None:
            return web.json_response({"message": "Not configured"}, status=503)
        if state is None:
            return web.json_response({"message": "Account not linked"}, status=403)
        if action == "zone" and not request["hass_user"].is_admin:
            return web.json_response({"message": "Administrator required"}, status=403)
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("Expected object")
            lat, lon = payload.get("latitude"), payload.get("longitude")
            pl = match_place(state.get("places"), lat, lon)
            if pl is None:
                return web.json_response({"message": "Place not found"}, status=404)
            if describe_places(self.hass, [pl])[0]["status"] == "zone":
                return web.json_response({"message": "Edit this HA zone on the family map"}, status=409)
            name = payload.get("name")
            if action != "delete" and (not isinstance(name, str)
                                       or not 1 <= len(name.strip()) <= 80):
                raise ValueError("Invalid name")
            if action == "zone":
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
                pl["label"], pl["source"] = name.strip(), "zone"
            elif action == "rename":
                pl["label"], pl["source"] = name.strip(), "named"
            else:
                state["places"].remove(pl)
            await self.hass.async_add_executor_job(
                _save_places, self.hass.config.path(PLACES_FILE),
                {p: s.get("places") or [] for p, s in self.hass.data.get(DOMAIN, {}).items()},
            )
            _publish(self.hass, person)
            return web.json_response({"saved": True, "action": action},
                                     headers={"Cache-Control": "no-store"})
        except (ValueError, TypeError, KeyError, AttributeError):
            return web.json_response({"message": "Invalid place action"}, status=400)
