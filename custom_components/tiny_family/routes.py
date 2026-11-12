"""Local 24-hour route history filtered by authenticated family ownership.

A GPS point recorded during Ghost Mode stays private even if Ghost Mode is
subsequently disabled. Routes never appear as HA state attributes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .communications import own_person

RETENTION_SECONDS = 86400
MAX_POINTS = 2500
MIN_INTERVAL = 30


def prune_routes(routes: dict, now: float) -> bool:
    changed = False
    for person, entries in list(routes.items()):
        if not isinstance(entries, list):
            routes.pop(person, None)
            changed = True
            continue
        valid = [p for p in entries if isinstance(p, dict)
                 and type(p.get("ts")) in (int, float)
                 and now - RETENTION_SECONDS <= p["ts"] <= now + 60
                 and type(p.get("lat")) in (int, float)
                 and type(p.get("lon")) in (int, float)
                 and math.isfinite(p["lat"]) and math.isfinite(p["lon"])
                 and -90 <= p["lat"] <= 90 and -180 <= p["lon"] <= 180][-MAX_POINTS:]
        if valid != entries:
            changed = True
        if valid:
            routes[person] = valid
        else:
            routes.pop(person, None)
    return changed


def record_route(routes: dict, person: str, *, ts: float, lat: float,
                 lon: float, private: bool, gap: bool = False) -> None:
    if not all(math.isfinite(x) for x in (ts, lat, lon)):
        return
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return
    track = routes.setdefault(person, [])
    if track and ts <= track[-1]["ts"]:
        return
    if track and ts - track[-1]["ts"] < MIN_INTERVAL and not gap and (
        bool(track[-1].get("private")) == bool(private)
    ):
        return
    track.append({"ts": ts, "lat": round(lat, 6),
                  "lon": round(lon, 6), "private": bool(private),
                  "gap": bool(gap)})
    prune_routes(routes, ts)


def visible_segments(routes: dict, person: str, *, viewer: str,
                     ghost_people: set[str], now: float) -> list[list[list[float]]]:
    if person != viewer and person in ghost_people:
        return []
    segments = []
    segment = []
    for item in routes.get(person, []):
        if not isinstance(item, dict):
            continue
        ts = item.get("ts", 0)
        if type(ts) not in (int, float) or not now - RETENTION_SECONDS <= ts <= now + 60:
            continue
        if item.get("gap") and segment:
            segments.append(segment)
            segment = []
        if item.get("private") and person != viewer:
            if segment:
                segments.append(segment)
                segment = []
            continue
        segment.append([item["lat"], item["lon"], ts])
    if segment:
        segments.append(segment)
    return segments


class TinyFamilyRoutesView(HomeAssistantView):
    url = "/api/tiny_family/routes"
    name = "api:tiny_family:routes"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    async def get(self, request):
        runtime = self.hass.data.get("tiny_family_runtime", {})
        entry = runtime.get("entry")
        if entry is None:
            return web.json_response({"message": "Not configured"}, status=503)
        config = {**entry.data, **entry.options}
        persons = config.get("persons") or []
        viewer = own_person(request["hass_user"].id, persons, config.get("owners") or {})
        if viewer is None:
            return web.json_response({"message": "Account not linked"}, status=403)
        now = datetime.now(tz=timezone.utc).timestamp()
        ghosts = set(config.get("ghost_people") or [])
        saved = runtime.get("routes") or {}
        return web.json_response({
            "hours": 24,
            "paths": [
                {"person": person,
                 "segments": visible_segments(
                    saved, person, viewer=viewer, ghost_people=ghosts, now=now,
                 )}
                for person in persons if person == viewer or person not in ghosts
            ],
        }, headers={"Cache-Control": "no-store, private"})
