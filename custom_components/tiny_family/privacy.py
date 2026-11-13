"""Per-account sharing preferences and a strictly filtered Tiny Family status API.

IMPORTANT: This protects Tiny Family endpoints and UI only. Home Assistant
Person/device_tracker entities and history have their own HA-wide permissions.
This does not promise to hide data from HA administrators or other integrations.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .communications import current_location, own_person
from .companion import companion_readings
from .const import DOMAIN

RUNTIME_KEY = "tiny_family_runtime"


def shared_map_zones(hass) -> list[dict]:
    """Geographic HA zones available to already authorized Tiny Family users."""
    result = []
    for zone in hass.states.async_all("zone"):
        attrs = zone.attributes
        try:
            lat = float(attrs["latitude"])
            lon = float(attrs["longitude"])
            radius = float(attrs.get("radius", 100))
        except (ValueError, TypeError, KeyError):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon) and math.isfinite(radius)
                and -90 <= lat <= 90 and -180 <= lon <= 180
                and 1 <= radius <= 100000):
            continue
        result.append({
            "id": zone.entity_id,
            "name": str(zone.name)[:120],
            "latitude": lat,
            "longitude": lon,
            "radius_m": radius,
        })
    return result[:100]


def may_use_ghost(config: dict, person: str) -> bool:
    """Fail closed for new installs; preserve previously active legacy Ghost."""
    allowed = config.get("ghost_allowed_people")
    if allowed is None:
        allowed = config.get("ghost_people") or []
    return person in (allowed or [])



def visible_person(person, *, viewer_person, configured, ghost):
    """Show only explicitly configured family members; ghost hides from others."""
    return (person in configured and
            (person == viewer_person or person not in ghost))


def public_profile(hass, person: str, config: dict, now: datetime,
                   viewer_person: str) -> dict:
    """Expose only the data authorized for this viewer."""
    ghost=set(config.get("ghost_people") or [])
    state=hass.states.get(person)
    result={"person":person, "name": state.name if state is not None else person,
            "ghost": person in ghost and person != viewer_person}
    if not visible_person(person, viewer_person=viewer_person,
                          configured=config.get("persons") or [], ghost=ghost):
        return result
    if state is None:
        return {**result,"status":"unknown","stale":True}
    runtime_state = getattr(hass, "data", {}).get(DOMAIN, {}).get(person, {})
    gps_health = runtime_state.get("gps_health")
    gps_timestamp = runtime_state.get("gps_seen_at")
    if (not isinstance(gps_timestamp, (int, float))
            or not __import__("math").isfinite(gps_timestamp)
            or gps_timestamp < 0 or gps_timestamp > now.timestamp() + 60):
        gps_timestamp = None
    last_fix = (datetime.fromtimestamp(gps_timestamp, tz=timezone.utc)
                if gps_timestamp is not None else state.last_updated)
    location = (current_location(state, now)
                if gps_health in (None, "fresh") else None)
    result.update({"status":state.state, "stale":location is None,
                   "gps_health": gps_health or ("fresh" if location else "unknown"),
                   "updated_at":last_fix.isoformat(),
                   "gps_age_minutes": max(0, round((now - last_fix).total_seconds() / 60))})
    result["power_save"] = runtime_state.get("power_save")
    result["gps_glitches"] = max(0, int(runtime_state.get("gps_glitches") or 0))
    glitch_at = runtime_state.get("gps_glitch_at")
    result["gps_glitch_recent"] = (type(glitch_at) in (int, float)
                                   and 0 <= now.timestamp() - glitch_at <= 1800)
    if location is not None:
        result.update({"latitude":location[0],"longitude":location[1]})
    elif 0 <= (now - last_fix).total_seconds() <= 24 * 3600:
        # Last known fix may be shown grey for up to 24 h, never as live.
        try:
            lat=float(state.attributes["latitude"])
            lon=float(state.attributes["longitude"])
            if __import__("math").isfinite(lat) and __import__("math").isfinite(lon) and (
                -90 <= lat <= 90 and -180 <= lon <= 180
            ):
                result.update({"latitude":lat,"longitude":lon})
        except (KeyError, TypeError, ValueError):
            pass
    battery=(config.get("batteries") or {}).get(person)
    battery_state=hass.states.get(battery) if battery else None
    if battery_state and battery_state.state not in ("unknown","unavailable"):
        try:
            value=float(battery_state.state)
            if 0 <= value <= 100:
                result["battery_percent"]=round(value)
        except (TypeError,ValueError):
            pass
    result.update(companion_readings(
        hass,
        charging_entity=(config.get("charging_sensors") or {}).get(person),
        activity_entity=(config.get("activity_sensors") or {}).get(person),
    ))
    # Live map badges are derived from the assigned phone's tracked motion.
    # Never present an old GPS speed or stay duration as a live reading.
    if not result["stale"] and result["gps_health"] == "fresh":
        speed = runtime_state.get("speed_kmh")
        if type(speed) in (int, float) and math.isfinite(speed) and 0 <= speed <= 200:
            result["speed_kmh"] = round(speed)
        movement = runtime_state.get("movement_state", "unknown")
        result["movement"] = movement
        stay_start = runtime_state.get("stay_start")
        if (movement == "stationary" and type(stay_start) in (int, float)
                and math.isfinite(stay_start) and 0 < stay_start <= now.timestamp()):
            result["stay_minutes"] = int((now.timestamp() - stay_start) // 60)
    private_destination = bool(runtime_state.get("destination_private"))
    result["destination_confidence"] = (
        0 if private_destination and person != viewer_person else
        round(runtime_state.get("destination_confidence", 0.0) * 100)
    )
    if runtime_state.get("home_eta_min") is not None:
        result["home_eta_minutes"] = runtime_state["home_eta_min"]
    slug=person.removeprefix("person.")
    for field,suffix in (("movement","movement"),("destination","destination"),
                         ("eta_minutes","destination_eta"),
                         ("distance_today_km","distance_today")):
        metric=hass.states.get(f"sensor.tiny_family_{slug}_{suffix}")
        if metric is not None and metric.state not in ("unknown","unavailable"):
            if field in ("destination", "eta_minutes") and person != viewer_person and runtime_state.get("destination_private"):
                continue
            result[field]=metric.state
    if private_destination and person == viewer_person:
        result["destination"] = runtime_state.get("destination") or "Ingen"
        result["eta_minutes"] = int(runtime_state.get("dest_eta_min") or 0)
    if (person == viewer_person and config.get("learn_routines_enabled") and
            person in (config.get("routine_learning_people") or [])):
        result["usual_departure"] = runtime_state.get("usual_departure")
        result["routine_confidence"] = runtime_state.get("routine_confidence", 0)
    return result


class TinyFamilyStatusView(HomeAssistantView):
    """Filtered family profiles; never return hidden coordinates or history."""
    url="/api/tiny_family/status"
    name="api:tiny_family:status"
    requires_auth=True

    def __init__(self,hass):
        self.hass=hass

    async def get(self,request):
        entry=self.hass.data.get(RUNTIME_KEY,{}).get("entry")
        if entry is None:
            return web.json_response({"message":"Not configured"},status=503)
        cfg={**entry.data,**entry.options}
        user_id=request["hass_user"].id
        person=own_person(user_id,cfg.get("persons") or [],cfg.get("owners") or {})
        if not person:
            return web.json_response({"message":"Account is not linked to a person"},status=403)
        now=datetime.now(timezone.utc)
        people=[public_profile(self.hass,p,cfg,now,person)
                for p in cfg.get("persons") or []]
        return web.json_response({
            "viewer_person":person, "people":people,
            "zones":shared_map_zones(self.hass),
            "can_manage_zones": bool(request["hass_user"].is_admin),
        }, headers={"Cache-Control":"no-store"})


class TinyFamilyPrivacyView(HomeAssistantView):
    """Users may switch only their *own* Tiny Family sharing preference."""
    url="/api/tiny_family/privacy"
    name="api:tiny_family:privacy"
    requires_auth=True

    def __init__(self,hass):
        self.hass=hass

    def _entry_person(self,request):
        entry=self.hass.data.get(RUNTIME_KEY,{}).get("entry")
        if entry is None:
            return None,None
        config={**entry.data,**entry.options}
        person=own_person(request["hass_user"].id,
                          config.get("persons") or [],config.get("owners") or {})
        return entry,person

    async def get(self,request):
        entry,person=self._entry_person(request)
        if not person:
            return web.json_response({"message":"Account not linked"},status=403)
        config = {**entry.data, **entry.options}
        return web.json_response({
            "person": person,
            "ghost": person in (config.get("ghost_people") or []),
            "ghost_allowed": may_use_ghost(config, person),
            "share_position_in_messages":
                person not in (config.get("message_location_opt_out") or []),
            "routine_learning_available": bool(config.get("learn_routines_enabled")),
            "learn_my_routines": bool(config.get("learn_routines_enabled") and
                person in (config.get("routine_learning_people") or [])),
        }, headers={"Cache-Control": "no-store"})

    async def post(self, request):
        entry, person = self._entry_person(request)
        if not person:
            return web.json_response({"message": "Account not linked"}, status=403)
        try:
            data = await request.json()
            if isinstance(data, dict) and "learn_my_routines" in data:
                return web.json_response({"message": "Only administrator controls routine learning"}, status=403)
            allowed = {"ghost", "share_position_in_messages"}
            if (not isinstance(data, dict) or not (set(data) & allowed) or
                    set(data) - allowed or
                    any(type(value) is not bool for value in data.values())):
                raise ValueError("Invalid privacy preference")
        except (ValueError, TypeError):
            return web.json_response({"message": "Use boolean privacy preferences"}, status=400)
        # This version has no user-facing tracking pause or Ghost activation.
        # Reject these actions at the API as well; allow only one-way cleanup
        # for legacy opt-outs to avoid silently revealing old private routes.
        if data.get("ghost") is True or data.get("share_position_in_messages") is False:
            return web.json_response({
                "message": "Tracking and sharing pauses are not available in Tiny Family"
            }, status=403)
        config = {**entry.data, **entry.options}
        ghost = set(config.get("ghost_people") or [])
        no_location = set(config.get("message_location_opt_out") or [])
        if data.get("ghost") and not may_use_ghost(config, person):
            return web.json_response({
                "message": "Ghost Mode requires administrator permission"
            }, status=403)
        if "ghost" in data:
            (ghost.add if data["ghost"] else ghost.discard)(person)
        if "share_position_in_messages" in data:
            (no_location.discard if data["share_position_in_messages"]
             else no_location.add)(person)

        new_options = {**entry.options,
                       "ghost_people": sorted(ghost),
                       "message_location_opt_out": sorted(no_location)}
        runtime = self.hass.data.get(RUNTIME_KEY, {})
        for key, values in (("ghost_people", ghost),
                            ("message_location_opt_out", no_location)):
            live = runtime.get(key)
            if live is not None:
                live.clear()
                live.update(values)
            live_cfg = runtime.get("live_config")
            if live_cfg is not None:
                live_cfg[key] = sorted(values)
        from .sensors import _publish
        if person in self.hass.data.get(DOMAIN, {}):
            _publish(self.hass, person)
        runtime["privacy_options_in_flight"] = {**entry.data, **new_options}
        self.hass.config_entries.async_update_entry(entry, options=new_options)
        return web.json_response({
            "person": person,
            "ghost": person in ghost,
            "ghost_allowed": may_use_ghost(config, person),
            "share_position_in_messages": person not in no_location,
            "routine_learning_available": bool(config.get("learn_routines_enabled")),
            "learn_my_routines": bool(config.get("learn_routines_enabled") and
                                      person in (config.get("routine_learning_people") or [])),
        }, headers={"Cache-Control": "no-store"})
