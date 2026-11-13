"""Bounded, local historical GPS patterns used only to improve destination guesses.

All history stays in Home Assistant's local SQLite database. This module
never contacts a routing or AI service and never changes stored raw fixes.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from math import isfinite
import sqlite3
from zoneinfo import ZoneInfo

from .utils import _hav

MAX_HISTORIC_FIXES = 30000
MAX_CANDIDATES = 45
MAX_ARRIVALS = 20
ARRIVAL_RADIUS_M = 140
APPROACH_RADIUS_M = 250


def load_historical_patterns(path, person, places, timezone_name,
                             *, now_ts=None, retention_days=365):
    """Learn arrival times and route approaches from historic, observed fixes.

    Only named/learned destinations already known to this person are scored.
    Old fixes must show a plausible approach into a destination. The sample
    limit keeps a large long-lived installation responsive.
    """
    if not isinstance(person, str) or not person.startswith("person."):
        return []
    candidates = []
    def visit_count(place):
        try:
            return max(0, int(place.get("visits") or 0))
        except (ValueError, TypeError):
            return 0

    for place in sorted((p for p in places if isinstance(p, dict)),
                        key=visit_count, reverse=True):
        if len(candidates) >= MAX_CANDIDATES:
            break
        try:
            lat, lon = float(place["lat"]), float(place["lon"])
        except (ValueError, TypeError, KeyError):
            continue
        if not all(isfinite(x) for x in (lat, lon)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        candidates.append({"lat": lat, "lon": lon, "arrivals": []})
    if not candidates:
        return []
    tz = ZoneInfo(timezone_name)
    cutoff = (now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()) - retention_days * 86400
    try:
        conn = sqlite3.connect(str(path), timeout=15)
        try:
            rows = conn.execute("""SELECT ts,lat,lon,gap FROM fixes
              WHERE person=? AND ts>=? ORDER BY ts DESC LIMIT ?""",
              (person, cutoff, MAX_HISTORIC_FIXES)).fetchall()
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        return []
    path_points = deque(maxlen=240)
    previous = None
    for ts, lat, lon, gap in reversed(rows):
        if not all(type(x) in (int, float) and isfinite(x) for x in (ts, lat, lon)):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        if previous is not None:
            last_ts, last_lat, last_lon = previous
            delta = ts - last_ts
            if gap or not 0 < delta <= 900 or _hav(last_lat, last_lon, lat, lon) > delta * 55.56 + 150:
                path_points.clear()
                previous = None
        path_points.append((ts, lat, lon))
        while path_points and ts - path_points[0][0] > 3600:
            path_points.popleft()
        if previous is not None:
            last_ts, last_lat, last_lon = previous
            for candidate in candidates:
                arrivals = candidate["arrivals"]
                old_dist = _hav(last_lat, last_lon, candidate["lat"], candidate["lon"])
                new_dist = _hav(lat, lon, candidate["lat"], candidate["lon"])
                if old_dist <= ARRIVAL_RADIUS_M or new_dist > ARRIVAL_RADIUS_M:
                    continue
                earlier = [p for p in path_points if 120 <= ts - p[0] <= 3600
                           and _hav(p[1], p[2], candidate["lat"], candidate["lon"]) > 350]
                if not earlier:
                    continue
                local = datetime.fromtimestamp(ts, timezone.utc).astimezone(tz)
                if any(item.get("date") == local.date().isoformat() for item in arrivals):
                    continue
                # Keep a bounded, sparse but directional route signature.
                path = [(round(p[1], 5), round(p[2], 5))
                        for p in list(path_points)[::max(1, len(path_points)//25)]]
                arrivals.append({"date":local.date().isoformat(),
                                 "weekday": local.weekday(),
                                 "minute": local.hour * 60 + local.minute,
                                 "path": path})
                if len(arrivals) > MAX_ARRIVALS:
                    arrivals.pop(0)
        previous = (ts, lat, lon)
    return [p for p in candidates if p["arrivals"]]


def history_confidence_boost(patterns, place, *, base, current,
                             weekday, arrival_minute):
    """Prioritize repeated observed routes/times; weak history stays weak."""
    if not patterns:
        return 0.0
    matched = next((row for row in patterns if
                    _hav(row["lat"], row["lon"], place["lat"], place["lon"]) <= 100), None)
    if not matched:
        return 0.0
    arrivals = matched["arrivals"]
    if not arrivals:
        return 0.0
    repetitions = len(arrivals)
    score = min(0.12, repetitions * 0.04)
    if any(row["weekday"] == weekday for row in arrivals):
        score += 0.07 if repetitions >= 2 else 0.02
    if any(min(abs(row["minute"] - arrival_minute),
               1440 - abs(row["minute"] - arrival_minute)) <= 90
           for row in arrivals):
        score += 0.14 if repetitions >= 2 else 0.05
    # Only a prior ordered approach near both the current start and the
    # current position counts as directional route support.
    for row in arrivals:
        path = row.get("path") or []
        if any(_hav(base[0], base[1], start[0], start[1]) <= 450 and
               _hav(current[0], current[1], end[0], end[1]) <= 450
               for i, start in enumerate(path)
               for end in path[i + 1:]):
            score += 0.25 if repetitions >= 2 else 0.12
            break
    return min(0.58, round(score, 3))
