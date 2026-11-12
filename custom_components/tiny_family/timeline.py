"""Persistent, date-indexed Tiny Family GPS timeline.

Only locally observed, validated Companion fixes are recorded. No road snapping,
fabricated points, live-location replay or third-party routing services.
The SQLite database resides in Home Assistant's configuration directory.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, date
from functools import partial
from math import asin, cos, isfinite, radians, sin, sqrt
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .communications import own_person
from .map_matching import match_day
from .road_engine import match_day_embedded

RETENTION_DAYS = 365
MAX_DAY_POINTS = 25000
MAX_DAY_EVENTS = 500
GAP_SECONDS = 300
MIN_MOVING_INTERVAL = 5
MIN_STATIONARY_INTERVAL = 60


def _connect(path):
    conn = sqlite3.connect(str(path), timeout=20)
    conn.execute("PRAGMA busy_timeout = 20000")
    return conn


def initialize_archive(path, legacy_routes=None, legacy_activity=None, *, now=None):
    """Create archive and import previously retained 24 h routes/30 d events."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(path)
    try:
        with conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS fixes (
              person TEXT NOT NULL,
              ts REAL NOT NULL,
              lat REAL NOT NULL, lon REAL NOT NULL,
              speed REAL, battery INTEGER, movement TEXT,
              accuracy REAL, stay_min INTEGER,
              gap INTEGER NOT NULL DEFAULT 0,
              private INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(person, ts)
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS fixes_by_time ON fixes(ts)")
            conn.execute("""CREATE TABLE IF NOT EXISTS events (
              id TEXT PRIMARY KEY, person TEXT NOT NULL, kind TEXT NOT NULL,
              started_at REAL NOT NULL, ended_at REAL NOT NULL,
              duration_min INTEGER NOT NULL, distance_km REAL NOT NULL,
              max_speed_kmh REAL NOT NULL, label TEXT NOT NULL,
              gap INTEGER NOT NULL, private INTEGER NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS events_by_date ON events(person, started_at)")
            # Migration never expands visibility: old legacy privacy flags remain.
            for person, points in (legacy_routes or {}).items():
                if not isinstance(person, str) or not isinstance(points, list):
                    continue
                for point in points:
                    try:
                        ts, lat, lon = (float(point[k]) for k in ("ts", "lat", "lon"))
                        if not all(isfinite(v) for v in (ts, lat, lon)) or not (
                            -90 <= lat <= 90 and -180 <= lon <= 180
                        ):
                            continue
                        conn.execute("""INSERT OR IGNORE INTO fixes
                          (person,ts,lat,lon,gap,private) VALUES (?,?,?,?,?,?)""",
                          (person, ts, lat, lon, int(bool(point.get("gap"))),
                           int(bool(point.get("private")))))
                    except (TypeError, ValueError, KeyError, sqlite3.Error):
                        continue
            _insert_events(conn, legacy_activity or {})
            cutoff = (now if now is not None else datetime.now(timezone.utc).timestamp()) - (
                RETENTION_DAYS * 86400
            )
            conn.execute("DELETE FROM fixes WHERE ts < ?", (cutoff,))
            conn.execute("DELETE FROM events WHERE ended_at < ?", (cutoff,))
    finally:
        conn.close()


def _insert_events(conn, events_by_person):
    for person, events in events_by_person.items():
        if not isinstance(person, str) or not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict) or event.get("kind") not in ("trip", "stay"):
                continue
            try:
                event_id = event.get("id")
                start, end = float(event["started_at"]), float(event["ended_at"])
                if not isinstance(event_id, str) or len(event_id) != 32:
                    continue
                if not all(isfinite(v) for v in (start, end)) or not 0 <= end - start <= 86400:
                    continue
                conn.execute("""INSERT OR IGNORE INTO events
                  (id,person,kind,started_at,ended_at,duration_min,distance_km,
                   max_speed_kmh,label,gap,private) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (event_id, person, event["kind"], start, end,
                   max(0, int(event.get("duration_min") or 0)),
                   max(0, float(event.get("distance_km") or 0)),
                   max(0, float(event.get("max_speed_kmh") or 0)),
                   str(event.get("label") or "")[:80],
                   int(bool(event.get("gps_gap"))), int(bool(event.get("private")))))
            except (KeyError, TypeError, ValueError, OverflowError, sqlite3.Error):
                continue


def persist_archive(path, samples=(), activity=None):
    """Append observed fixes and events in one atomic transaction (executor only)."""
    conn = _connect(path)
    try:
        with conn:
            for item in samples:
                conn.execute("""INSERT OR IGNORE INTO fixes
                  (person,ts,lat,lon,speed,battery,movement,accuracy,stay_min,gap,private)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (item["person"], item["ts"], item["lat"], item["lon"],
                   item.get("speed"), item.get("battery"), item.get("movement"),
                   item.get("accuracy"), item.get("stay_min"),
                   int(item.get("gap", False)), int(item.get("private", False))))
            if activity:
                _insert_events(conn, activity)
    finally:
        conn.close()


def enqueue_fix(pending, *, person, ts, lat, lon, speed_kmh, battery,
                movement, accuracy, stay_min, gap, private, last_samples=None):
    """Keep real fixes without dropping every point inside a fixed 30 s window."""
    if not isinstance(person, str) or not all(
        type(v) in (float, int) and isfinite(v) for v in (ts, lat, lon)
    ) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return False
    last = (last_samples or {}).get(person)
    if last is None:
        last = next((p for p in reversed(pending) if p["person"] == person), None)
    if last and ts <= last["ts"]:
        return False
    if last and not gap and last["private"] == bool(private):
        interval = ts - last["ts"]
        # Preserve bends/changes of movement, but coalesce stationary jitter.
        min_interval = MIN_STATIONARY_INTERVAL if movement == "stationary" else MIN_MOVING_INTERVAL
        if interval < min_interval and movement == last.get("movement"):
            return False
    def finite_optional(value, low, high):
        return (float(value) if type(value) in (float, int)
                and isfinite(value) and low <= value <= high else None)
    sample={
        "person":person,"ts":float(ts),"lat":round(lat,6),"lon":round(lon,6),
        "speed":finite_optional(speed_kmh,0,200),
        "battery":(int(battery) if type(battery) in (int,float) and
                    isfinite(battery) and 0 <= battery <= 100 else None),
        "movement":movement if movement in ("stationary","moving") else "unknown",
        "accuracy":finite_optional(accuracy,0,150),
        "stay_min":(int(stay_min) if type(stay_min) in (int,float)
                   and isfinite(stay_min) and 0 <= stay_min <= 86400 else None),
        "gap":bool(gap),"private":bool(private),
    }
    pending.append(sample)
    if last_samples is not None:
        last_samples[person]=sample
    return True


def archive_stats(path, person):
    """Summary of retained history for the signed-in account only."""
    conn=_connect(path)
    try:
        fixes=conn.execute("SELECT COUNT(*) FROM fixes WHERE person=?",(person,)).fetchone()[0]
        events=conn.execute("SELECT COUNT(*) FROM events WHERE person=?",(person,)).fetchone()[0]
        return {"fixes":fixes,"events":events}
    finally:
        conn.close()


def delete_archive(path, person, *, routes=False, activities=False):
    """Erase selected local data by person, leaving all other family data."""
    conn=_connect(path)
    deleted={"fixes":0,"events":0}
    try:
        with conn:
            if routes:
                deleted["fixes"]=conn.execute(
                    "DELETE FROM fixes WHERE person=?",(person,)
                ).rowcount
            if activities:
                deleted["events"]=conn.execute(
                    "DELETE FROM events WHERE person=?",(person,)
                ).rowcount
        return deleted
    finally:
        conn.close()


def archived_dates(path, person, *, limit=RETENTION_DAYS):
    """Available dates for a person's archive, without returning GPS points."""
    conn=_connect(path)
    try:
        rows=conn.execute("""SELECT DISTINCT date(ts, 'unixepoch') AS day
          FROM fixes WHERE person=? ORDER BY day DESC LIMIT ?""",
          (person, min(limit,RETENTION_DAYS))).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def _distance_m(a, b):
    lat1, lon1, lat2, lon2 = map(radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    dlat, dlon = lat2-lat1, lon2-lon1
    c = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 6371000 * 2 * asin(min(1.0, sqrt(max(0.0,c))))


def day_window(value, zone_name, *, now=None):
    """Resolve a calendar day in Home Assistant's timezone, including DST."""
    try:
        chosen = date.fromisoformat(value)
        if chosen.isoformat() != value:
            raise ValueError
        zone = ZoneInfo(zone_name)
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        raise ValueError("Invalid date or timezone") from None
    current = (now or datetime.now(timezone.utc)).astimezone(zone).date()
    if chosen > current or (current - chosen).days >= RETENTION_DAYS:
        raise ValueError("Date outside retained archive")
    start = datetime(chosen.year, chosen.month, chosen.day, tzinfo=zone)
    following = chosen + timedelta(days=1)
    end = datetime(following.year, following.month, following.day, tzinfo=zone)
    return start.timestamp(), end.timestamp()


def query_day(path, person, start, end, *, viewer, ghost=False):
    """Return only authorized fixes and events for one selected calendar day."""
    if ghost and person != viewer:
        return {"segments":[], "events":[], "summary":{}, "points_count":0}
    visibility = "" if person == viewer else " AND private=0"
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    try:
        raw_points = [dict(row) for row in conn.execute(
            """SELECT ts,lat,lon,speed,battery,movement,accuracy,stay_min,gap,private
               FROM fixes WHERE person=? AND ts>=? AND ts<?
               ORDER BY ts ASC LIMIT ?""",
            (person,start,end,MAX_DAY_POINTS*2))]
        points=[]
        private_gap=False
        for fix in raw_points:
            if person != viewer and fix.pop("private"):
                private_gap=True
                continue
            if private_gap:
                fix["gap"]=1
            private_gap=False
            points.append(fix)
            if len(points)>=MAX_DAY_POINTS:
                break
        events = [dict(row) for row in conn.execute(
            """SELECT id,kind,started_at,ended_at,duration_min,distance_km,
                max_speed_kmh,label,gap FROM events
                WHERE person=? AND started_at<? AND ended_at>=?""" +
            visibility + " ORDER BY started_at ASC LIMIT ?",
            (person,end,start,MAX_DAY_EVENTS))]
    finally:
        conn.close()
    return build_day(points, events)


def build_day(points, events):
    """Bound gaps and summarize observed distances without inventing roads."""
    segments, current = [], []
    distance_m = 0.0
    last = None
    for point in points:
        if last is not None and (
            point.get("gap") or point["ts"] - last["ts"] > GAP_SECONDS
        ):
            if current:
                segments.append(current)
            current=[]
            last=None
        if last is not None:
            displacement=_distance_m(last,point)
            elapsed = point["ts"] - last["ts"]
            if elapsed>0 and displacement/elapsed<=55.56:
                distance_m+=displacement
            else:
                if current:segments.append(current)
                current=[]
        current.append({
            "t":point["ts"],"lat":point["lat"],"lon":point["lon"],
            "speed":point.get("speed"),"battery":point.get("battery"),
            "movement":point.get("movement") or "unknown",
            "stay_min":point.get("stay_min"),"accuracy":point.get("accuracy"),
        })
        last=point
    if current:
        segments.append(current)
    valid_speeds=[p["speed"] for p in points if type(p.get("speed")) in (int,float)
                  and isfinite(p["speed"])]
    return {
        "segments":segments,"events":events,
        "points_count":len(points),"gaps":max(0,len(segments)-1),
        "summary":{
            "distance_km":round(distance_m/1000,2),
            "max_speed_kmh":round(max(valid_speeds),1) if valid_speeds else None,
            "stays":sum(1 for event in events if event["kind"]=="stay"),
            "trips":sum(1 for event in events if event["kind"]=="trip"),
        },
    }


class TinyFamilyTimelineView(HomeAssistantView):
    """One family member and one local calendar date per authorized request."""
    url = "/api/tiny_family/timeline"
    name = "api:tiny_family:timeline"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    async def get(self, request):
        runtime = self.hass.data.get("tiny_family_runtime", {})
        entry=runtime.get("entry")
        if entry is None:
            return web.json_response({"message":"Not configured"},status=503)
        cfg={**entry.data,**entry.options}
        persons=cfg.get("persons") or []
        viewer=own_person(request["hass_user"].id, persons, cfg.get("owners") or {})
        if viewer is None:
            return web.json_response({"message":"Account not linked"},status=403)
        person=request.query.get("person",viewer)
        if person not in persons:
            return web.json_response({"message":"Person not configured"},status=404)
        if person != viewer and person in set(cfg.get("ghost_people") or []):
            return web.json_response({"message":"Historical privacy restriction"},status=403)
        today=datetime.now(ZoneInfo(self.hass.config.time_zone)).date().isoformat()
        day=request.query.get("date",today)
        try:
            start,end=day_window(day,self.hass.config.time_zone)
        except ValueError:
            return web.json_response({"message":"Date outside retained archive"},status=400)
        try:
            data=await self.hass.async_add_executor_job(partial(
                query_day,runtime["timeline_path"],person,start,end,viewer=viewer
            ))
        except (OSError,sqlite3.Error,KeyError):
            return web.json_response({"message":"Timeline storage unavailable"},status=503)
        # Recent pending samples have not reached the next scheduled flush.
        # They use the same privacy filter as persisted rows.
        pending=[]
        hidden_gap=False
        for p in runtime.get("timeline_pending",()):
            if p["person"]!=person or not start<=p["ts"]<end:
                continue
            if person!=viewer and p["private"]:
                hidden_gap=True
                continue
            pending.append({
                "ts":p["ts"],"lat":p["lat"],"lon":p["lon"],
                "speed":p["speed"],"battery":p["battery"],
                "movement":p["movement"],"accuracy":p["accuracy"],
                "stay_min":p["stay_min"],"gap":p["gap"] or hidden_gap,
            })
            hidden_gap=False
        if pending:
            # Recalculate with persisted points to avoid hiding the pending tail.
            all_points=[{**point,"ts":point["t"],"gap":idx==0 and bool(i) }
                        for i,segment in enumerate(data["segments"])
                        for idx,point in enumerate(segment)]
            all_points.extend(pending)
            combined={p["ts"]:p for p in all_points}
            data=build_day([combined[k] for k in sorted(combined)],data["events"])
        # Map matching never runs for a normal timeline request. The user
        # must deliberately activate matching and the admin must configure
        # a matching backend first. Avoid sharing routes across viewers in
        # memory: their visible GPS samples may differ due to legacy privacy.
        data["matched_segments"]=[]
        data["matching_status"]="off"
        if request.query.get("map_match") == "1":
            server = cfg.get("map_matching_url", "")
            backend = cfg.get("map_matching_backend") or (
                "osrm" if server else "builtin"
            )
            if (not cfg.get("map_matching_enabled") or
                    backend not in ("builtin", "osrm") or
                    (backend == "osrm" and not server)):
                data["matching_status"] = "disabled"
            elif data["points_count"] >= 3:
                cache = runtime.setdefault("map_matching_cache", {})
                last_fix = max(
                    (seg[-1]["t"] for seg in data["segments"] if seg), default=0
                )
                cache_key = (
                    request["hass_user"].id, person, day, last_fix,
                    data["points_count"], backend, server if backend == "osrm" else "",
                )
                cached = cache.get(cache_key)
                now_ts = datetime.now(timezone.utc).timestamp()
                if cached is not None and now_ts - cached["at"] < 600:
                    data["matched_segments"] = cached["segments"]
                    data["matching_status"] = cached["status"]
                else:
                    # A single matching request at a time protects external
                    # road-data services and the Home Assistant event loop.
                    import asyncio
                    lock = runtime.setdefault("map_matching_lock", asyncio.Lock())
                    async with lock:
                        if backend == "builtin":
                            road_cache = runtime.setdefault("osm_road_cache", {})
                            matched, status = await match_day_embedded(
                                self.hass, data["segments"], road_cache
                            )
                        else:
                            matched, status = await match_day(
                                self.hass, server, data["segments"]
                            )
                    data["matched_segments"] = matched
                    data["matching_status"] = status
                    cache[cache_key] = {
                        "at": now_ts, "segments": matched, "status": status,
                    }
                    if len(cache) > 20:
                        oldest = min(cache, key=lambda key: cache[key]["at"])
                        cache.pop(oldest, None)
            else:
                data["matching_status"] = "not_enough_points"
        return web.json_response({
            "person":person,"date":day,"timezone":self.hass.config.time_zone,
            "retention_days":RETENTION_DAYS,"start":start,"end":end,
            **data,
        }, headers={"Cache-Control":"no-store, private"})
