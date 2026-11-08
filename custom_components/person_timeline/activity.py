"""Own-account activity archive with bounded local retention.

Only completed trips and stays are recorded. Coordinates are intentionally
kept in the separate 24-hour routes store, never in activity summaries.
"""
from __future__ import annotations
from datetime import datetime, timezone
from math import isfinite
from uuid import uuid4

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from .communications import own_person

RETENTION_DAYS = 30
MAX_PER_PERSON = 200
KINDS = frozenset(("trip", "stay"))


def prune_activity(records: dict, now_ts: float) -> bool:
    changed = False
    cutoff = now_ts - RETENTION_DAYS * 86400
    for person, rows in list(records.items()):
        if not isinstance(rows, list):
            records.pop(person, None)
            changed = True
            continue
        valid = [row for row in rows
                 if isinstance(row, dict)
                 and row.get("kind") in KINDS
                 and type(row.get("ended_at")) in (float, int)
                 and isfinite(row["ended_at"])
                 and cutoff <= row["ended_at"] <= now_ts + 60]
        valid = sorted(valid, key=lambda row: row["ended_at"])[-MAX_PER_PERSON:]
        if rows != valid:
            changed = True
        if valid:
            records[person] = valid
        else:
            records.pop(person, None)
    return changed


def add_activity(records: dict, person: str, *, kind: str,
                 started_at: float, ended_at: float, private: bool,
                 distance_km: float = 0, max_speed_kmh: float = 0,
                 label: str = "", gps_gap: bool = False) -> dict:
    if kind not in KINDS or not person.startswith("person."):
        raise ValueError("Invalid activity")
    if not all(type(n) in (int, float) and isfinite(n)
               for n in (started_at, ended_at, distance_km, max_speed_kmh)):
        raise ValueError("Invalid activity measurements")
    if not (0 <= ended_at - started_at <= RETENTION_DAYS * 86400):
        raise ValueError("Invalid activity duration")
    row = {
        "id": uuid4().hex, "kind": kind,
        "started_at": started_at, "ended_at": ended_at,
        "duration_min": round((ended_at - started_at) / 60),
        "distance_km": round(max(0, distance_km), 2),
        "max_speed_kmh": round(max(0, max_speed_kmh), 1),
        "label": str(label)[:80], "private": bool(private),
        "gps_gap": bool(gps_gap),
    }
    records.setdefault(person, []).append(row)
    prune_activity(records, datetime.now(timezone.utc).timestamp())
    return row


def archive_interrupted_trip(records: dict, person: str, state: dict,
                             *, private: bool) -> bool:
    """Retain incomplete journey metrics without inventing an arrival or GPS path."""
    if not state.get("trip_active"):
        return False
    start, end = state.get("trip_start"), state.get("last_t")
    if type(start) not in (int, float) or type(end) not in (int, float) or end < start:
        return False
    add_activity(
        records, person, kind="trip", started_at=start, ended_at=end,
        private=private, distance_km=max(0, state.get("trip_dist_m") or 0) / 1000,
        max_speed_kmh=max(0, state.get("trip_max_speed") or 0) * 3.6,
        label="GPS-afbrudt – ingen registreret afslutning", gps_gap=True,
    )
    return True


class TinyFamilyActivityView(HomeAssistantView):
    url = "/api/tiny_family/activity"
    name = "api:tiny_family:activity"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    async def get(self, request):
        runtime = self.hass.data.get("tiny_family_runtime", {})
        entry = runtime.get("entry")
        if entry is None:
            return web.json_response({"message": "Not configured"}, status=503)
        cfg = {**entry.data, **entry.options}
        person = own_person(request["hass_user"].id, cfg.get("persons") or [],
                            cfg.get("owners") or {})
        if person is None:
            return web.json_response({"message": "Account not linked"}, status=403)
        now_ts = datetime.now(timezone.utc).timestamp()
        archive = runtime.get("activity") or {}
        rows = [dict(row) for row in archive.get(person, [])
                if now_ts - RETENTION_DAYS * 86400 <= row.get("ended_at", 0) <= now_ts + 60]
        rows.sort(key=lambda row: row["ended_at"], reverse=True)
        active = (self.hass.data.get("person_timeline", {})
                  .get(person, {}).get("trip_active", False))
        return web.json_response({
            "person": person, "retention_days": RETENTION_DAYS,
            "trip_active": bool(active), "entries": rows[:MAX_PER_PERSON],
            "route_hours": 24,
            "notice": "Kun dit eget arkiv. Kortspor gemmes særskilt i højst 24 timer.",
        }, headers={"Cache-Control": "no-store, private"})
