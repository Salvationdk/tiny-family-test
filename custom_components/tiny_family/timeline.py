"""Persistent, date-indexed Tiny Family GPS timeline.

Only locally observed, validated Companion fixes are recorded. No road snapping,
fabricated points, live-location replay or third-party routing services.
The SQLite database resides in Home Assistant's configuration directory.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, date
from functools import partial
import hashlib
import json
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
MIN_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 3650
MAX_DAY_POINTS = 25000
MAX_DAY_EVENTS = 500
GAP_SECONDS = 300
MIN_MOVING_INTERVAL = 5
MIN_STATIONARY_INTERVAL = 60


def _connect(path):
    conn = sqlite3.connect(str(path), timeout=20)
    conn.execute("PRAGMA busy_timeout = 20000")
    return conn


def validate_retention_days(value):
    if type(value) is not int or not MIN_RETENTION_DAYS <= value <= MAX_RETENTION_DAYS:
        raise ValueError("Timeline retention must be 30–3650 days")
    return value


def initialize_archive(path, legacy_routes=None, legacy_activity=None, *, now=None,
                       retention_days=RETENTION_DAYS):
    """Create archive and import previously retained 24 h routes/30 d events."""
    retention_days = validate_retention_days(retention_days)
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
            # Older databases contain event times only. Keep their rows and
            # add optional measured anchors without inventing old positions.
            existing={item[1] for item in conn.execute("PRAGMA table_info(events)")}
            for field in ("start_lat","start_lon","end_lat","end_lon"):
                if field not in existing:
                    conn.execute(f"ALTER TABLE events ADD COLUMN {field} REAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS matched_days (
              person TEXT NOT NULL, day TEXT NOT NULL, viewer TEXT NOT NULL,
              source_hash TEXT NOT NULL, matched_json TEXT NOT NULL,
              status TEXT NOT NULL,
              PRIMARY KEY(person, day, viewer)
            )""")
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
                retention_days * 86400
            )
            conn.execute("DELETE FROM fixes WHERE ts < ?", (cutoff,))
            conn.execute("DELETE FROM events WHERE ended_at < ?", (cutoff,))
            conn.execute("DELETE FROM matched_days WHERE day < ?", (
                datetime.fromtimestamp(cutoff, timezone.utc).date().isoformat(),
            ))
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
                def anchor(prefix):
                    lat,lon=event.get(prefix+"_lat"),event.get(prefix+"_lon")
                    if (type(lat) in (int,float) and type(lon) in (int,float)
                            and isfinite(lat) and isfinite(lon)
                            and -90<=lat<=90 and -180<=lon<=180):
                        return float(lat),float(lon)
                    return None,None
                a,b=anchor("start")
                c,d=anchor("end")
                conn.execute("""INSERT OR IGNORE INTO events
                  (id,person,kind,started_at,ended_at,duration_min,distance_km,
                   max_speed_kmh,label,gap,private,start_lat,start_lon,end_lat,end_lon)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (event_id, person, event["kind"], start, end,
                   max(0, int(event.get("duration_min") or 0)),
                   max(0, float(event.get("distance_km") or 0)),
                   max(0, float(event.get("max_speed_kmh") or 0)),
                   str(event.get("label") or "")[:80],
                   int(bool(event.get("gps_gap"))), int(bool(event.get("private"))),
                   a,b,c,d))
            except (KeyError, TypeError, ValueError, OverflowError, sqlite3.Error):
                continue


def persist_archive(path, samples=(), activity=None, *,
                    retention_days=RETENTION_DAYS):
    """Append observed fixes and events in one atomic transaction (executor only)."""
    retention_days = validate_retention_days(retention_days)
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
            # Prune during normal operation too, even if HA never restarts.
            cutoff = datetime.now(timezone.utc).timestamp() - retention_days * 86400
            conn.execute("DELETE FROM fixes WHERE ts < ?", (cutoff,))
            conn.execute("DELETE FROM events WHERE ended_at < ?", (cutoff,))
            conn.execute("DELETE FROM matched_days WHERE day < ?", (
                datetime.fromtimestamp(cutoff, timezone.utc).date().isoformat(),
            ))
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
                conn.execute("DELETE FROM matched_days WHERE person=?", (person,))
            if activities:
                deleted["events"]=conn.execute(
                    "DELETE FROM events WHERE person=?",(person,)
                ).rowcount
        return deleted
    finally:
        conn.close()


def match_fingerprint(segments, backend, server=""):
    """Hash only the GPS samples visible to this viewer, never a global track."""
    hasher = hashlib.sha256()
    hasher.update(f"v2-sparse|{backend}|{server}|".encode("utf-8"))
    for segment in segments:
        hasher.update(b"|")
        for fix in segment:
            hasher.update(json.dumps((fix["t"], fix["lat"], fix["lon"]),
                                     separators=(",", ":")).encode("utf-8"))
    return hasher.hexdigest()


def read_matched_day(path, person, day, viewer, source_hash):
    """Return a previously derived road overlay for exactly this viewer."""
    conn = _connect(path)
    try:
        row = conn.execute("""SELECT matched_json,status FROM matched_days
          WHERE person=? AND day=? AND viewer=? AND source_hash=?""",
          (person, day, viewer, source_hash)).fetchone()
        if row is None:
            return None
        return json.loads(row[0]), row[1]
    finally:
        conn.close()


def earlier_matched_roads(path, person, day, viewer, *, limit=20):
    """Use only road overlays previously visible to this same viewer.

    Private observations from another family member cannot become inferred
    travel by reading the owner's separate archive or cache.
    """
    conn = _connect(path)
    try:
        rows = conn.execute("""SELECT matched_json FROM matched_days
          WHERE person=? AND viewer=? AND day<>? ORDER BY day DESC LIMIT ?""",
          (person, viewer, day, min(20, max(0, limit)))).fetchall()
    finally:
        conn.close()
    result = []
    for (encoded,) in rows:
        try:
            segments = json.loads(encoded)
        except (TypeError, ValueError):
            continue
        if isinstance(segments, list):
            result.extend(item for item in segments[:40]
                          if isinstance(item, dict) and
                          isinstance(item.get("coordinates"), list))
        if len(result) >= 60:
            break
    return result[:60]


def save_matched_day(path, person, day, viewer, source_hash, segments, status):
    """Persist the derived line only; original GPS fixes remain immutable."""
    conn = _connect(path)
    try:
        with conn:
            conn.execute("""INSERT INTO matched_days
              (person,day,viewer,source_hash,matched_json,status)
              VALUES (?,?,?,?,?,?) ON CONFLICT(person,day,viewer) DO UPDATE SET
              source_hash=excluded.source_hash,
              matched_json=excluded.matched_json,status=excluded.status""",
              (person, day, viewer, source_hash,
               json.dumps(segments, separators=(",", ":")), status))
    finally:
        conn.close()


def archived_dates(path, person, *, limit=None,
                   retention_days=RETENTION_DAYS):
    """Available dates for a person's archive, without returning GPS points."""
    retention_days = validate_retention_days(retention_days)
    conn=_connect(path)
    try:
        rows=conn.execute("""SELECT DISTINCT date(ts, 'unixepoch') AS day
          FROM fixes WHERE person=? ORDER BY day DESC LIMIT ?""",
          (person, min(limit if limit is not None else retention_days,
                       retention_days))).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def _distance_m(a, b):
    lat1, lon1, lat2, lon2 = map(radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    dlat, dlon = lat2-lat1, lon2-lon1
    c = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 6371000 * 2 * asin(min(1.0, sqrt(max(0.0,c))))


def day_window(value, zone_name, *, now=None,
               retention_days=RETENTION_DAYS):
    """Resolve a calendar day in Home Assistant's timezone, including DST."""
    retention_days = validate_retention_days(retention_days)
    try:
        chosen = date.fromisoformat(value)
        if chosen.isoformat() != value:
            raise ValueError
        zone = ZoneInfo(zone_name)
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        raise ValueError("Invalid date or timezone") from None
    current = (now or datetime.now(timezone.utc)).astimezone(zone).date()
    if chosen > current or (current - chosen).days >= retention_days:
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
                max_speed_kmh,label,gap,start_lat,start_lon,end_lat,end_lon FROM events
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
    gap_causes = {"time": 0, "explicit": 0, "implausible": 0}
    for point in points:
        reason = ""
        if last is not None and (
            point.get("gap") or point["ts"] - last["ts"] > GAP_SECONDS
        ):
            reason = "explicit" if point.get("gap") else "time"
            gap_causes[reason] += 1
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
                reason = "implausible"
                gap_causes[reason] += 1
                if current:segments.append(current)
                current=[]
        fix = {
            "t":point["ts"],"lat":point["lat"],"lon":point["lon"],
            "speed":point.get("speed"),"battery":point.get("battery"),
            "movement":point.get("movement") or "unknown",
            "stay_min":point.get("stay_min"),"accuracy":point.get("accuracy"),
        }
        if not current and reason:
            fix["gap_origin"] = reason
        current.append(fix)
        last=point
    if current:
        segments.append(current)
    valid_speeds=[p["speed"] for p in points if type(p.get("speed")) in (int,float)
                  and isfinite(p["speed"])]
    measured_moving = sum(1 for speed in valid_speeds if speed >= 2)
    speed_health = (
        "missing" if not valid_speeds else
        "zero_despite_movement" if len(valid_speeds) >= 10 and
            measured_moving == 0 and distance_m >= 100 else
        "recorded"
    )
    return {
        "segments":segments,"events":events,
        "points_count":len(points),"gaps":max(0,len(segments)-1),
        "gps_diagnostics":{
            "gap_causes":gap_causes,"speed_health":speed_health,
            "speed_samples":len(valid_speeds),
            "moving_speed_samples":measured_moving,
        },
        "summary":{
            "distance_km":round(distance_m/1000,2),
            "max_speed_kmh":round(max(valid_speeds),1) if valid_speeds else None,
            "stays":sum(1 for event in events if event["kind"]=="stay"),
            "trips":sum(1 for event in events if event["kind"]=="trip"),
        },
    }


def build_daily_report(data, start, end, *, shared_places=()):
    """Compact, evidence-labelled daily diary from already authorized data.

    Measured GPS distances do not bridge gaps. Walking/driving labels are
    only estimates based on plausible speeds, not proven transport modes.
    """
    segments = data.get("segments") or []
    events = data.get("events") or []
    diagnostic = data.get("gps_diagnostics") or {}
    speed_healthy = diagnostic.get("speed_health") == "recorded"
    seconds = {"walking": 0.0, "driving": 0.0, "other": 0.0, "stopped": 0.0}
    weighted_speed = {"walking": 0.0, "driving": 0.0}
    top_speed = {"walking": 0.0, "driving": 0.0}
    raw_speeds = []
    inferred_rows = []
    intervals = []

    def place_label(lat, lon, fallback=""):
        named=str(fallback or "").strip()
        if named and named.casefold() not in ("ukendt sted","ukendt","unknown"):
            return named[:80]
        if type(lat) not in (int,float) or type(lon) not in (int,float):
            return "Ukendt sted"
        best = None
        for place in shared_places:
            if not isinstance(place, dict) or place.get("private") is True:
                continue
            plat, plon = place.get("latitude"), place.get("longitude")
            if not (type(plat) in (int,float) and type(plon) in (int,float)
                    and all(isfinite(v) for v in (plat,plon))):
                continue
            distance = _distance_m({"lat":lat,"lon":lon},
                                   {"lat":plat,"lon":plon})
            if distance <= 80 and (best is None or distance < best[0]):
                best = (distance, str(place.get("name") or "Ukendt sted")[:80])
        return best[1] if best else "Ukendt sted"

    for segment in segments:
        active = None
        for previous, fix in zip(segment, segment[1:]):
            dt = fix["t"] - previous["t"]
            if not 0 < dt <= GAP_SECONDS:
                continue
            distance = _distance_m(previous, fix)
            if distance / dt > 55.56:
                continue
            measured = [p["speed"] for p in (previous,fix)
                        if type(p.get("speed")) in (int,float) and
                        isfinite(p["speed"]) and 0 <= p["speed"] <= 200]
            if speed_healthy:
                raw_speeds.extend(v for v in measured if v >= 2)
            gps_speed = distance / dt * 3.6
            avg = sum(measured) / len(measured) if measured else None
            # A GPS displacement cannot be called stationary merely because
            # Companion reported an implausible constant zero speed.
            speed = (avg if speed_healthy and avg is not None and
                     (avg > 0 or distance < 15) else gps_speed)
            kind = ("stopped" if (speed < 2 and distance < 15) or
                    (distance < 15 and previous.get("movement")=="stationary"
                     and fix.get("movement")=="stationary") else
                    "walking" if 2 <= speed <= 8.5 else
                    "driving" if speed >= 20 else "other")
            seconds[kind] += dt
            if kind in weighted_speed:
                weighted_speed[kind] += speed*dt
                top_speed[kind] = max(top_speed[kind],speed)
            if active and active["kind"] == kind and active["ended_at"] == previous["t"]:
                active["ended_at"] = fix["t"]
                active["distance_m"] += distance
                active["max_speed_kmh"] = max(active["max_speed_kmh"],speed)
            else:
                if active:
                    intervals.append(active)
                active = {"kind":kind,"started_at":previous["t"],
                          "ended_at":fix["t"],"distance_m":distance,
                          "max_speed_kmh":speed,"lat":previous["lat"],
                          "lon":previous["lon"]}
        if active:
            intervals.append(active)

    rows = []
    for event in events:
        begun = max(start, event["started_at"])
        ended = min(end, event["ended_at"])
        if ended <= begun:
            continue
        kind = event.get("kind")
        if kind not in ("trip","stay"):
            continue
        lat, lon = event.get("start_lat"), event.get("start_lon")
        trip_label = event.get("label") or ""
        if kind == "trip" and not trip_label:
            origin = place_label(lat,lon)
            destination = place_label(event.get("end_lat"),event.get("end_lon"))
            if origin != "Ukendt sted" or destination != "Ukendt sted":
                trip_label = origin+" → "+destination
            else:
                trip_label = "Tur"
        recorded_speed = event.get("max_speed_kmh")
        if type(recorded_speed) not in (int,float) or recorded_speed <= 0:
            recorded_speed = None
        trip_distance = event.get("distance_km") if kind == "trip" else None
        avg_trip_speed = None
        # Derive an event-specific average only for an uncut, contiguous trip.
        # A whole-trip distance divided by a clipped day or GPS gap is false.
        if (kind == "trip" and begun == event["started_at"] and
                ended == event["ended_at"] and not event.get("gap") and
                type(trip_distance) in (int,float) and
                isfinite(trip_distance) and trip_distance > 0):
            speed = trip_distance * 3600 / (ended-begun)
            if 0 < speed <= 200:
                avg_trip_speed = round(speed,1)
        rows.append({"kind":kind,"started_at":begun,"ended_at":ended,
                     "duration_min":round((ended-begun)/60),
                     "label":place_label(lat,lon,event.get("label") or "") if
                       kind == "stay" else trip_label,
                     "distance_km":trip_distance,
                     "avg_speed_kmh":avg_trip_speed,
                     "max_speed_kmh":recorded_speed if kind == "trip" else None,
                     "mode":("driving" if recorded_speed and recorded_speed >= 20 else
                             "walking" if recorded_speed and recorded_speed <= 8.5 else
                             "other") if kind == "trip" else "stopped",
                     "source":"archive","gps_gap":bool(event.get("gap"))})

    for interval in intervals:
        span = interval["ended_at"]-interval["started_at"]
        if span < (180 if interval["kind"] == "stopped" else 120):
            continue
        # Completed activity records take precedence over any approximate
        # intervals derived from the same GPS points.
        overlap = sum(max(0,min(interval["ended_at"],r["ended_at"])-
                          max(interval["started_at"],r["started_at"]))
                      for r in rows if r["kind"] in ("stay","trip"))
        if overlap >= span*.5:
            continue
        stayed = interval["kind"] == "stopped"
        inferred_rows.append({
            "kind":"stay" if stayed else "trip",
            "started_at":interval["started_at"],"ended_at":interval["ended_at"],
            "duration_min":round(span/60),
            "label":place_label(interval["lat"],interval["lon"]) if stayed
              else "Bevægelse registreret via GPS",
            "distance_km":None if stayed else round(interval["distance_m"]/1000,2),
            "avg_speed_kmh":None if stayed else round(
                interval["distance_m"] / span * 3.6,1),
            "max_speed_kmh":None if stayed else round(interval["max_speed_kmh"],1),
            "mode":interval["kind"],"source":"gps","gps_gap":False,
        })
    rows.extend(inferred_rows)
    # Only substantial missing periods merit an explicit diary line; short
    # gaps are already represented by the GPS diagnostics below the diary.
    for previous, following in zip(segments,segments[1:]):
        if not previous or not following:
            continue
        gap_start, gap_end = previous[-1]["t"], following[0]["t"]
        if gap_end-gap_start >= 900:
            rows.append({"kind":"gap","started_at":gap_start,
                         "ended_at":gap_end,"duration_min":round((gap_end-gap_start)/60),
                         "label":"Ingen sammenhængende GPS-målinger",
                         "source":"gps","mode":"unknown"})
    rows.sort(key=lambda item:(item["started_at"],0 if item["source"]=="archive" else 1))
    if not rows and data.get("points_count"):
        first = next((part[0] for part in segments if part),None)
        if first:
            rows.append({"kind":"position","started_at":first["t"],
                         "ended_at":first["t"],"duration_min":0,
                         "label":place_label(first["lat"],first["lon"]),
                         "source":"gps","mode":"unknown"})
    archived_km = sum(float(item.get("distance_km") or 0)
                      for item in rows if item["kind"]=="trip" and
                      item["source"]=="archive")
    measured_speed = [p["speed"] for part in segments for p in part
                      if type(p.get("speed")) in (int,float) and
                      isfinite(p["speed"]) and p["speed"]>=2] if speed_healthy else []
    return {"summary":{
        "gps_distance_km":data.get("summary",{}).get("distance_km",0),
        "archived_trip_distance_km":round(archived_km,2),
        "walking_minutes":round(seconds["walking"]/60),
        "driving_minutes":round(seconds["driving"]/60),
        "walking_avg_kmh":round(weighted_speed["walking"]/seconds["walking"],1)
          if seconds["walking"] else None,
        "walking_max_kmh":round(top_speed["walking"],1)
          if seconds["walking"] else None,
        "driving_avg_kmh":round(weighted_speed["driving"]/seconds["driving"],1)
          if seconds["driving"] else None,
        "driving_max_kmh":round(top_speed["driving"],1)
          if seconds["driving"] else None,
        "other_moving_minutes":round(seconds["other"]/60),
        "stopped_minutes":round(seconds["stopped"]/60),
        "observed_minutes":round(sum(seconds.values())/60),
        "max_recorded_speed_kmh":round(max(measured_speed),1) if measured_speed else None,
        "avg_recorded_moving_speed_kmh":round(sum(measured_speed)/len(measured_speed),1)
          if measured_speed else None,
        "stays":sum(row["kind"]=="stay" for row in rows),
        "trips":sum(row["kind"]=="trip" for row in rows),
        "gps_points":data.get("points_count",0),
        "gps_gaps":data.get("gaps",0),
        "speed_health":diagnostic.get("speed_health","missing"),
    },"items":rows}


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
        retention_days = validate_retention_days(cfg.get("timeline_retention_days", RETENTION_DAYS))
        persons=cfg.get("persons") or []
        admin=bool(getattr(request["hass_user"],"is_admin",False))
        viewer=own_person(request["hass_user"].id, persons, cfg.get("owners") or {})
        if viewer is None and not admin:
            return web.json_response({"message":"Account not linked"},status=403)
        person=request.query.get("person",viewer)
        if person not in persons:
            return web.json_response({"message":"Person not configured"},status=404)
        if not admin and person != viewer and person in set(cfg.get("ghost_people") or []):
            return web.json_response({"message":"Historical privacy restriction"},status=403)
        # A HA administrator can inspect each configured person's full data.
        # Other family members retain the existing private/Ghost filtering.
        effective_viewer=person if admin else viewer
        today=datetime.now(ZoneInfo(self.hass.config.time_zone)).date().isoformat()
        day=request.query.get("date",today)
        try:
            start,end=day_window(day,self.hass.config.time_zone,
                                 retention_days=retention_days)
        except ValueError:
            return web.json_response({"message":"Date outside retained archive"},status=400)
        try:
            data=await self.hass.async_add_executor_job(partial(
                query_day,runtime["timeline_path"],person,start,end,viewer=effective_viewer
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
            if person!=effective_viewer and p["private"]:
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
        if request.query.get("view") == "report":
            # Text-first diary: no road matching, OSM requests, large point
            # arrays or map rendering. Reuse the same per-fix privacy filter.
            public_places=tuple(dict(place) for place in
                (runtime.get("shared_places") or ()) if isinstance(place,dict))
            report=await self.hass.async_add_executor_job(partial(
                build_daily_report,data,start,end,shared_places=public_places))
            return web.json_response({
                "person":person,"date":day,"timezone":self.hass.config.time_zone,
                "retention_days":retention_days,**report,
            },headers={"Cache-Control":"no-store, private"})
        # Admin-enabled matching also applies to old archived days. Derive
        # lines when a date is viewed, and cache per viewer on disk; an
        # unbounded eager backfill could overload OSM and leak private fixes.
        matching_only = request.query.get("phase") == "matching"
        data["matched_segments"]=[]
        data["inferred_segments"]=[]
        data["matching_status"]="off"
        if matching_only or request.query.get("map_match") == "1" or (
            cfg.get("map_matching_enabled") and request.query.get("map_match") != "0"
        ):
            server = cfg.get("map_matching_url", "")
            backend = cfg.get("map_matching_backend") or (
                "osrm" if server else "builtin"
            )
            if (not cfg.get("map_matching_enabled") or
                    backend not in ("builtin", "osrm") or
                    (backend == "osrm" and not server)):
                data["matching_status"] = "disabled"
            elif data["points_count"] >= (2 if backend == "builtin" else 3):
                cache = runtime.setdefault("map_matching_cache", {})
                source_hash = match_fingerprint(data["segments"], backend, server)
                cache_key = (
                    request["hass_user"].id, person, day, source_hash,
                )
                cached = cache.get(cache_key)
                now_ts = datetime.now(timezone.utc).timestamp()
                if cached is not None and now_ts - cached["at"] < 600:
                    data["matched_segments"] = cached["segments"]
                    data["inferred_segments"] = cached.get("inferred", [])
                    data["matching_status"] = cached["status"]
                else:
                    # Cached historical overlays survive HA restarts.
                    try:
                        stored = await self.hass.async_add_executor_job(
                            read_matched_day, runtime["timeline_path"], person,
                            day, effective_viewer, source_hash
                        )
                    except (OSError, sqlite3.Error, ValueError, KeyError):
                        stored = None
                    import asyncio
                    lock = runtime.setdefault("map_matching_lock", asyncio.Lock())
                    inferred = []
                    if stored is not None:
                        matched, status = stored
                        # Cache from an earlier viewing is already verified.
                        # Local history may still identify additional gaps.
                        if backend == "builtin":
                            from .road_engine import sparse_road_pairs
                            from .road_engine_core import infer_historical_gap
                            past = await self.hass.async_add_executor_job(
                                earlier_matched_roads, runtime["timeline_path"],
                                person, day, effective_viewer)
                            inferred = [item for item in (
                                infer_historical_gap(*pair, past)
                                for pair in sparse_road_pairs(data["segments"],
                                    allow_explicit=(effective_viewer == person)))
                                if item is not None]
                    else:
                        # One matching request at a time avoids flooding OSM.
                        async with lock:
                            if backend == "builtin":
                                road_cache = runtime.setdefault("osm_road_cache", {})
                                past = await self.hass.async_add_executor_job(
                                    earlier_matched_roads, runtime["timeline_path"],
                                    person, day, effective_viewer)
                                matched, inferred, status = await match_day_embedded(
                                    self.hass, data["segments"], road_cache,
                                    include_inferences=True, historical_roads=past,
                                    allow_owner_gaps=(effective_viewer == person)
                                )
                            else:
                                matched, status = await match_day(
                                    self.hass, server, data["segments"]
                                )
                        if matched:
                            try:
                                await self.hass.async_add_executor_job(
                                    save_matched_day, runtime["timeline_path"],
                                    person, day, effective_viewer, source_hash, matched, status
                                )
                            except (OSError, sqlite3.Error, ValueError):
                                pass  # Overlay is optional; keep original GPS.
                    data["matched_segments"] = matched
                    data["inferred_segments"] = inferred
                    data["matching_status"] = status
                    cache[cache_key] = {
                        "at": now_ts, "segments": matched,
                        "inferred": inferred, "status": status,
                    }
                    if len(cache) > 20:
                        oldest = min(cache, key=lambda key: cache[key]["at"])
                        cache.pop(oldest, None)
            else:
                data["matching_status"] = "not_enough_points"
        if matching_only:
            # In the browser this request happens *after* the raw day has
            # already rendered. Never resend the private fixes unnecessarily.
            return web.json_response({
                "person": person, "date": day,
                "matched_segments": data["matched_segments"],
                "inferred_segments": data["inferred_segments"],
                "matching_status": data["matching_status"],
            }, headers={"Cache-Control":"no-store, private"})
        return web.json_response({
            "person":person,"date":day,"timezone":self.hass.config.time_zone,
            "retention_days":retention_days,"start":start,"end":end,
            **data,
        }, headers={"Cache-Control":"no-store, private"})
