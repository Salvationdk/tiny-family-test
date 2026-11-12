"""Tiny Family's embedded OSM road graph matcher (pure Python, no router).

OpenStreetMap way topology is kept separate from personal GPS history.
No straight-line bridges are manufactured across disconnected streets.
"""
from __future__ import annotations

import heapq
import math

ROAD_CLASSES = frozenset((
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "residential", "unclassified",
    "living_street", "service", "road", "track",
))
MAX_WAYS = 5000
MAX_VERTICES = 25000
MAX_EDGES = 28000
MAX_PATH_POINTS = 1800


def meters(a, b):
    """Small-area spherical distance in metres."""
    x = math.radians(a[0] - b[0])
    y = math.radians(a[1] - b[1])
    h = (math.sin(x / 2) ** 2
         + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0]))
         * math.sin(y / 2) ** 2)
    return 12742000 * math.asin(min(1.0, math.sqrt(max(0.0, h))))


def valid_point(value):
    return (isinstance(value, dict) and
            all(type(value.get(k)) in (int, float) and math.isfinite(value[k])
                for k in ("lat", "lon")) and
            -90 <= value["lat"] <= 90 and -180 <= value["lon"] <= 180)


def road_graph(payload):
    """Read bounded Overpass way geometry preserving actual shared OSM nodes."""
    if (not isinstance(payload, dict) or payload.get("remark") or
            not isinstance(payload.get("elements"), list) or
            len(payload["elements"]) > MAX_WAYS):
        return None
    nodes = {}
    links = {}
    edges = []
    for way in payload["elements"]:
        if not isinstance(way, dict) or way.get("type") != "way":
            continue
        tags = way.get("tags") or {}
        if (not isinstance(tags, dict) or
                tags.get("highway") not in ROAD_CLASSES or
                tags.get("access") in ("private", "no") or
                tags.get("motor_vehicle") in ("private", "no") or
                tags.get("motorcar") in ("private", "no")):
            continue
        ids, geometry = way.get("nodes"), way.get("geometry")
        if (not isinstance(ids, list) or not isinstance(geometry, list) or
                len(ids) != len(geometry) or len(ids) < 2 or len(ids) > 2500):
            continue
        direction = tags.get("oneway", "").lower()
        forward = direction not in ("-1", "reverse")
        backward = direction not in ("yes", "true", "1") and not (
            tags.get("junction") == "roundabout"
        )
        for i in range(len(ids) - 1):
            u, v = ids[i:i + 2]
            a, b = geometry[i:i + 2]
            if (type(u) is not int or type(v) is not int or u == v or
                    not valid_point(a) or not valid_point(b)):
                continue
            axy = (a["lat"], a["lon"])
            bxy = (b["lat"], b["lon"])
            length = meters(axy, bxy)
            if not 0.3 <= length <= 10000:
                continue
            nodes[u] = axy
            nodes[v] = bxy
            edges.append((u, v, axy, bxy, length, forward, backward))
            if forward:
                links.setdefault(u, []).append((v, length))
            if backward:
                links.setdefault(v, []).append((u, length))
            if len(edges) > MAX_EDGES or len(nodes) > MAX_VERTICES:
                return None
    return (nodes, links, edges) if len(edges) >= 2 else None


def project(pt, edge):
    """Project one fix onto a road edge using a local metre coordinate frame."""
    _, _, a, b, _, _, _ = edge
    lat = math.radians(pt["lat"])
    dx = (b[1] - a[1]) * 111320 * math.cos(lat)
    dy = (b[0] - a[0]) * 111320
    px = (pt["lon"] - a[1]) * 111320 * math.cos(lat)
    py = (pt["lat"] - a[0]) * 111320
    t = max(0.0, min(1.0, (px * dx + py * dy) / (dx * dx + dy * dy + 1e-8)))
    projected = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    return t, projected, meters((pt["lat"], pt["lon"]), projected)


def nearest(pt, edges, limit=3):
    accuracy = pt.get("accuracy")
    radius = max(35.0, min(75.0, 2.5 * accuracy if type(accuracy) in (int, float)
                             and math.isfinite(accuracy) and accuracy > 0 else 45.0))
    nearby = []
    for i, edge in enumerate(edges):
        a, b = edge[2:4]
        if (abs(pt["lat"] - a[0]) > .002 and abs(pt["lat"] - b[0]) > .002) or (
            abs(pt["lon"] - a[1]) > .003 and abs(pt["lon"] - b[1]) > .003
        ):
            continue
        t, position, distance = project(pt, edge)
        if distance <= radius:
            nearby.append((distance, i, t, position))
    nearby.sort(key=lambda item: item[0])
    return nearby[:limit]


def shortest_path(start, end, graph, maximum):
    """Directed Dijkstra with exact projected start and end on road segments."""
    nodes, links, edges = graph
    ea, eb = edges[start[1]], edges[end[1]]
    src = []
    if ea[6]:
        src.append((start[2] * ea[4], ea[0]))
    if ea[5]:
        src.append(((1.0 - start[2]) * ea[4], ea[1]))
    targets = {}
    if eb[5]:
        targets[eb[0]] = end[2] * eb[4]
    if eb[6]:
        targets[eb[1]] = (1.0 - end[2]) * eb[4]
    best = (math.inf, [])
    if start[1] == end[1]:
        dt = end[2] - start[2]
        if (dt >= 0 and ea[5]) or (dt <= 0 and ea[6]):
            best = (abs(dt) * ea[4], [start[3], end[3]])
    if not src or not targets:
        return best if best[0] <= maximum else None
    dist, parent, queue = {}, {}, []
    for cost, node in src:
        if cost < dist.get(node, math.inf):
            dist[node] = cost
            parent[node] = None
            heapq.heappush(queue, (cost, node))
    seen = set()
    while queue:
        cost, node = heapq.heappop(queue)
        if node in seen or cost > maximum or cost > best[0]:
            continue
        seen.add(node)
        if node in targets and cost + targets[node] < best[0]:
            route = []
            current = node
            while current is not None:
                route.append(nodes[current])
                current = parent[current]
            route.reverse()
            best = (cost + targets[node], [start[3], *route, end[3]])
        for neighbor, weight in links.get(node, ()):
            new_cost = cost + weight
            if new_cost < dist.get(neighbor, math.inf) and new_cost <= maximum:
                dist[neighbor] = new_cost
                parent[neighbor] = node
                heapq.heappush(queue, (new_cost, neighbor))
    return best if best[0] <= maximum else None


def snap_trace(points, roads):
    """Map-match a short GPS trace; return only contiguous plausible road paths."""
    graph = road_graph(roads)
    if graph is None or not isinstance(points, list) or len(points) < 3:
        return []
    _, _, edges = graph
    if any(not valid_point(p) or type(p.get("t")) not in (int, float)
           or not math.isfinite(p["t"]) for p in points):
        return []
    candidates = [nearest(p, edges) for p in points]
    matched = []
    chain = []
    start_t = None
    last_t = None
    n_fixes = 0
    residual = 0.0

    def flush():
        nonlocal chain, start_t, last_t, n_fixes, residual
        if n_fixes >= 3 and len(chain) >= 2 and len(chain) <= MAX_PATH_POINTS:
            quality = max(.65, min(.98, .93 - (residual / n_fixes) / 200))
            matched.append({
                "start_t": start_t, "end_t": last_t,
                "confidence": round(quality, 2),
                "coordinates": [[round(lat, 6), round(lon, 6)]
                                for lat, lon in chain],
            })
        chain, start_t, last_t, n_fixes, residual = [], None, None, 0, 0.0

    prev = candidates[0][0] if candidates[0] else None
    for i in range(1, len(points)):
        pt_a, pt_b = points[i-1:i+1]
        dt = pt_b["t"] - pt_a["t"]
        air = meters((pt_a["lat"], pt_a["lon"]), (pt_b["lat"], pt_b["lon"]))
        if prev is None or not candidates[i] or not (0 < dt <= 90) or air < 5:
            flush()
            prev = candidates[i][0] if candidates[i] else None
            continue
        maximum = min(air * 3.1 + 150, dt * 55 + 120)
        best = None
        for candidate in candidates[i]:
            route = shortest_path(prev, candidate, graph, maximum)
            if route is None:
                continue
            distance, geometry = route
            score = distance + (prev[0] + candidate[0]) * 3
            if best is None or score < best[0]:
                best = (score, candidate, geometry)
        if best is None:
            flush()
            prev = candidates[i][0]
            continue
        _, chosen, geometry = best
        if not chain:
            start_t = pt_a["t"]
            n_fixes = 1
            residual = prev[0]
        for location in geometry:
            if not chain or meters(chain[-1], location) > .25:
                chain.append(location)
        residual += chosen[0]
        last_t = pt_b["t"]
        n_fixes += 1
        prev = chosen
        if len(chain) > MAX_PATH_POINTS:
            flush()
    flush()
    return matched
