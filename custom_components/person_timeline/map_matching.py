"""Optional OSRM road matching for explicitly requested Tiny Family timelines.

No automatic uploads: an administrator enables a selected OSRM backend and a
family viewer explicitly toggles road matching for the chosen date. Source
GPS fixes remain authoritative; a poor/unavailable match never replaces them.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import math
from urllib.parse import urlsplit
from aiohttp import ClientError, ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession

MAX_CHUNKS = 18
MAX_FIXES_PER_CHUNK = 65
MAX_GEOMETRY_POINTS = 1800
MIN_CONFIDENCE = 0.65
MAX_RESPONSE_BYTES = 1_500_000
MAX_MATCH_SECONDS = 18


def validate_match_server(value: str) -> str:
    """Allow explicitly configured endpoints, never credentials or URL queries.

    HTTP is limited to local IPs/.local or single-label LAN hostnames.
    Remote routing must use TLS. Redirects are always disabled on requests.
    """
    if not isinstance(value, str) or len(value) > 240:
        raise ValueError("Invalid map matching server")
    value = value.strip().rstrip("/")
    if not value:
        return ""
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or
            any(x in value for x in ("\n", "\r", "\t", " " ))
            or parsed.path not in ("", "/")
            or parsed.hostname in ("0.0.0.0",)):
        raise ValueError("Invalid OSRM server URL")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid OSRM port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Invalid OSRM port")
    host = parsed.hostname
    if parsed.scheme == "http":
        try:
            addr = ipaddress.ip_address(host)
            local = addr.is_private or addr.is_loopback
        except ValueError:
            local = "." not in host or host.endswith(".local")
        if not local:
            raise ValueError("External OSRM servers must use HTTPS")
    return value


def _meters(a, b):
    latitude = math.radians(a[0] - b[0])
    longitude = math.radians(a[1] - b[1])
    x = (math.sin(latitude / 2) ** 2 +
         math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) *
         math.sin(longitude / 2) ** 2)
    return 12742000 * math.asin(min(1.0, math.sqrt(max(0.0, x))))


def _chunks(raw_segments):
    """Never bridge >90 s missing data or a private/GPS gap."""
    chunks = []
    for segment in raw_segments or ():
        current = []
        for item in segment:
            if not isinstance(item, dict) or not all(
                type(item.get(k)) in (int, float) and math.isfinite(item[k])
                for k in ("lat", "lon", "t")
            ):
                if len(current) >= 3:
                    chunks.append(current)
                current = []
                continue
            if current and (item["t"] - current[-1]["t"] > 90
                            or item["t"] <= current[-1]["t"]):
                if len(current) >= 3:
                    chunks.append(current)
                current = []
            current.append(item)
            if len(current) == MAX_FIXES_PER_CHUNK:
                chunks.append(current)
                current = [item]  # overlap one real fix across API batches
        if len(current) >= 3:
            chunks.append(current)
    return chunks[:MAX_CHUNKS]


def build_match_request(base, points):
    """Bounded OSRM Match request: coordinates and timestamps in order."""
    base = validate_match_server(base)
    if not base or not 3 <= len(points) <= MAX_FIXES_PER_CHUNK:
        raise ValueError("Invalid GPS trace")
    coords = ";".join(f'{p["lon"]:.6f},{p["lat"]:.6f}' for p in points)
    times = ";".join(str(int(p["t"])) for p in points)
    radiuses = ";".join(str(min(50, max(5, round(p.get("accuracy") or 15))))
                       for p in points)
    return (base + "/match/v1/driving/" + coords,
            {"geometries":"geojson","overview":"full","gaps":"split",
             "tidy":"true","timestamps":times,"radiuses":radiuses,
             "steps":"false"})


def parse_osrm_match(reply, points):
    """Accept only plausible, confidently matched subtraces of real fixes."""
    if not isinstance(reply, dict) or reply.get("code") != "Ok":
        return []
    tracepoints = reply.get("tracepoints")
    if not isinstance(tracepoints, list) or len(tracepoints) != len(points):
        return []
    matchings = reply.get("matchings")
    if not isinstance(matchings, list):
        return []
    result = []
    for matching_index, matching in enumerate(matchings):
        if not isinstance(matching, dict):
            continue
        confidence = matching.get("confidence")
        if (type(confidence) not in (int,float) or not math.isfinite(confidence)
                or confidence < MIN_CONFIDENCE):
            continue
        geometry = matching.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
            continue
        coords = geometry.get("coordinates")
        if not isinstance(coords,list) or not 2 <= len(coords) <= MAX_GEOMETRY_POINTS:
            continue
        path=[]
        for point in coords:
            if (not isinstance(point,list) or len(point)<2
                or type(point[0]) not in (int,float) or type(point[1]) not in (int,float)
                or not all(math.isfinite(v) for v in point[:2])
                or not (-180<=point[0]<=180 and -90<=point[1]<=90)):
                path=[]
                break
            path.append([round(point[1],6),round(point[0],6)])
        if not path:
            continue
        indices=[i for i,p in enumerate(tracepoints)
                 if isinstance(p,dict) and p.get("matchings_index")==matching_index]
        if len(indices)<3 or len(indices)<max(3,round(len(points)*0.60)):
            continue
        first,last=points[indices[0]],points[indices[-1]]
        if (_meters(path[0],[first["lat"],first["lon"]])>175 or
            _meters(path[-1],[last["lat"],last["lon"]])>175):
            continue
        result.append({
            "start_t":first["t"],"end_t":last["t"],
            "confidence":round(confidence,2),
            "coordinates":path,
        })
    return result


async def match_day(hass, server, raw_segments):
    """Return verified road geometry; never write to permanent GPS history."""
    server = validate_match_server(server)
    if not server:
        return [], "disabled"
    chunks = _chunks(raw_segments)
    if not chunks:
        return [], "not_enough_points"
    session=async_get_clientsession(hass)
    result = []
    failed = 0
    try:
        async with asyncio.timeout(MAX_MATCH_SECONDS):
            for points in chunks:
                if _meters([points[0]["lat"],points[0]["lon"]],
                           [points[-1]["lat"],points[-1]["lon"]]) < 35:
                    continue
                url,params=build_match_request(server,points)
                try:
                    async with session.get(url,params=params,allow_redirects=False,
                                           timeout=ClientTimeout(total=6)) as response:
                        if response.status!=200 or (
                            response.content_length is not None and
                            response.content_length>MAX_RESPONSE_BYTES
                        ):
                            failed+=1
                            continue
                        body=await response.content.read(MAX_RESPONSE_BYTES+1)
                        if len(body)>MAX_RESPONSE_BYTES:
                            failed+=1
                            continue
                        parsed=json.loads(body)
                        matched=parse_osrm_match(parsed,points)
                        result.extend(matched)
                        if not matched:failed+=1
                except (ClientError,ValueError,TypeError,UnicodeDecodeError,
                        json.JSONDecodeError,asyncio.TimeoutError):
                    failed+=1
    except TimeoutError:
        failed+=1
    return result, ("matched" if result and not failed else
                    "partial" if result else "unavailable")
