"""On-demand road geometry provider for Tiny Family's embedded map matcher.

Only a bounded bounding box is sent to Overpass, never GPS timestamps,
person IDs or a track. Requests require admin + viewer opt-in and are cached.
No OSRM server, API key or separate process is required.
"""
from __future__ import annotations

import asyncio
import json
import math
from time import monotonic

from aiohttp import ClientError, ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .map_matching import _chunks, _meters
from .road_engine_core import (
    eligible_sparse_pair, infer_historical_gap, infer_road_gap, snap_trace,
)

OSM_ROADS_URL = "https://overpass-api.de/api/interpreter"
MAX_WINDOWS = 8
MAX_LAT_SPAN = 0.035
MAX_LON_SPAN = 0.06
MAX_BYTES = 2_500_000
MAX_SECONDS = 30
CACHE_SECONDS = 24 * 3600

ROAD_REGEX = ("motorway|motorway_link|trunk|trunk_link|primary|primary_link|"
              "secondary|secondary_link|tertiary|tertiary_link|residential|"
              "unclassified|living_street|service|road|track")


def road_windows(raw_segments):
    """Partition actual uninterrupted fixes into safely bounded OSM requests."""
    windows = []
    for chunk in _chunks(raw_segments):
        part = []
        for point in chunk:
            trial = part + [point]
            latitudes = [p["lat"] for p in trial]
            longitudes = [p["lon"] for p in trial]
            too_large = (max(latitudes) - min(latitudes) > MAX_LAT_SPAN - .002 or
                         max(longitudes) - min(longitudes) > MAX_LON_SPAN - .004)
            if too_large and len(part) >= 3:
                if _meters([part[0]["lat"], part[0]["lon"]],
                           [part[-1]["lat"], part[-1]["lon"]]) >= 35:
                    windows.append(part)
                part = part[-2:] + [point]  # overlap two real fixes
            elif too_large:
                part = [point]  # widely separated points are not reconstructible
            else:
                part = trial
        if len(part) >= 3 and _meters(
                [part[0]["lat"], part[0]["lon"]],
                [part[-1]["lat"], part[-1]["lon"]]) >= 35:
            windows.append(part)
    return windows


def sparse_road_pairs(raw_segments, *, allow_explicit=False):
    """Bounded guesses. Only an owner may estimate across ambiguous breaks.

    Old archives used one generic `gap` flag both for GPS outages and
    privacy discontinuities. We cannot tell them apart for other viewers.
    """
    pairs = []
    segments = [s for s in (raw_segments or []) if isinstance(s, list) and s]
    for segment in segments:
        if len(segment) == 2 and eligible_sparse_pair(*segment):
            pairs.append(segment)
    for previous, following in zip(segments, segments[1:]):
        reason = following[0].get("gap_origin")
        if reason != "time" and not (allow_explicit and reason == "explicit"):
            continue
        candidate = [previous[-1], following[0]]
        if eligible_sparse_pair(*candidate):
            pairs.append(candidate)
    return pairs[:16]


def bounding_box(points):
    latitudes = [p["lat"] for p in points]
    longitudes = [p["lon"] for p in points]
    lat_mid = sum(latitudes) / len(latitudes)
    padding_lat = 100 / 111320
    padding_lon = 100 / max(1000, 111320 * abs(math.cos(math.radians(lat_mid))))
    south, north = min(latitudes) - padding_lat, max(latitudes) + padding_lat
    west, east = min(longitudes) - padding_lon, max(longitudes) + padding_lon
    if (north - south > MAX_LAT_SPAN or east - west > MAX_LON_SPAN or
            not (-85 <= south < north <= 85) or
            not (-180 <= west < east <= 180)):
        return None
    return tuple(round(v, 5) for v in (south, west, north, east))


def overpass_query(bbox):
    south, west, north, east = bbox
    return (
        "[out:json][timeout:10][maxsize:33554432];"
        f'way["highway"~"^({ROAD_REGEX})$"]'
        f"({south:.5f},{west:.5f},{north:.5f},{east:.5f});"
        "out geom;"
    )


async def match_day_embedded(hass, raw_segments, cache=None, *,
                             include_inferences=False, historical_roads=None,
                             allow_owner_gaps=False):
    """Return matched road segments, or let timeline show untouched GPS fixes."""
    candidates = road_windows(raw_segments)
    sparse = sparse_road_pairs(raw_segments, allow_explicit=allow_owner_gaps) \
        if include_inferences else []
    inferred = []
    road_guesses = []
    for pair in sparse:
        previous = infer_historical_gap(*pair, historical_roads or [])
        if previous:
            inferred.append(previous)
        else:
            road_guesses.append(pair)
    if not candidates and not road_guesses:
        status = "inferred" if inferred else "not_enough_points"
        return ([], inferred, status) if include_inferences else ([], status)
    # Four live/archived road windows and four sparse possibilities bound
    # Overpass usage; historical matches require no external request.
    verified_budget = MAX_WINDOWS // 2 if include_inferences and road_guesses else MAX_WINDOWS
    request_windows = [(p, False) for p in candidates[:verified_budget]]
    available = max(0, MAX_WINDOWS - len(request_windows))
    request_windows.extend((p, True) for p in road_guesses[:available])
    skipped = len(candidates) + len(road_guesses) > MAX_WINDOWS
    cache = cache if isinstance(cache, dict) else {}
    session = async_get_clientsession(hass)
    matched, errors = [], 0
    try:
        async with asyncio.timeout(MAX_SECONDS):
            for points, is_inference in request_windows:
                bbox = bounding_box(points)
                if bbox is None:
                    errors += 1
                    continue
                now = monotonic()
                road_data = cache.get(bbox)
                if road_data is not None and now - road_data[0] < CACHE_SECONDS:
                    response_data = road_data[1]
                else:
                    try:
                        async with session.post(
                            OSM_ROADS_URL,
                            data={"data": overpass_query(bbox)},
                            headers={"User-Agent": "TinyFamily/0.8.9 (Home Assistant integration)"},
                            allow_redirects=False,
                            timeout=ClientTimeout(total=11),
                        ) as response:
                            if (response.status != 200 or
                                    (response.content_length is not None and
                                     response.content_length > MAX_BYTES)):
                                errors += 1
                                continue
                            raw = await response.content.read(MAX_BYTES + 1)
                            if len(raw) > MAX_BYTES:
                                errors += 1
                                continue
                            response_data = json.loads(raw)
                    except (ClientError, OSError, TimeoutError, ValueError, TypeError,
                            UnicodeDecodeError, json.JSONDecodeError):
                        errors += 1
                        continue
                    if (not isinstance(response_data, dict) or
                            response_data.get("remark") or
                            not isinstance(response_data.get("elements"), list)):
                        errors += 1
                        continue
                    cache[bbox] = (monotonic(), response_data)
                    if len(cache) > 36:
                        oldest = min(cache, key=lambda key: cache[key][0])
                        cache.pop(oldest, None)
                if is_inference:
                    guess = await hass.async_add_executor_job(
                        infer_road_gap, points[0], points[1], response_data)
                    if guess:
                        inferred.append(guess)
                    else:
                        errors += 1
                else:
                    roads = await hass.async_add_executor_job(snap_trace, points, response_data)
                    if roads:
                        matched.extend(roads)
                    else:
                        errors += 1
    except TimeoutError:
        errors += 1
    status = (
        "matched" if matched and not errors and not skipped else
        "partial" if matched else "inferred" if inferred else "unavailable"
    )
    return (matched, inferred, status) if include_inferences else (matched, status)
