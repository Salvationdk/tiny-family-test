"""Opt-in geographic polygon overlays native to Tiny Family.

Home Assistant core zones are circular. Polygons here are separate local
geofences and publish Tiny Family arrival/departure events, not zone.* states.
"""
from __future__ import annotations

import math
from uuid import uuid4

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .communications import own_person
from .storage import _save_places


def _orientation(a, b, c):
    return (b[1] - a[1]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[1] - a[1])


def _intersects(a, b, c, d):
    p, q = _orientation(a, b, c), _orientation(a, b, d)
    r, s = _orientation(c, d, a), _orientation(c, d, b)
    return (p * q < 0 and r * s < 0)


def validate_polygon(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Expected a polygon")
    name = data.get("name")
    points = data.get("points")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError("Invalid polygon name")
    if not isinstance(points, list) or not 3 <= len(points) <= 32:
        raise ValueError("A polygon requires 3–32 vertices")
    vertices = []
    for point in points:
        if (not isinstance(point, (list, tuple)) or len(point) != 2
                or any(type(coord) not in (int, float) for coord in point)
                or not all(math.isfinite(coord) for coord in point)):
            raise ValueError("Invalid vertex")
        lat, lon = point
        if not (-85 <= lat <= 85 and -180 <= lon <= 180):
            raise ValueError("Vertex out of bounds")
        vertices.append([round(float(lat), 7), round(float(lon), 7)])
    if any(vertices[i] == vertices[(i + 1) % len(vertices)]
           for i in range(len(vertices))):
        raise ValueError("Duplicate adjacent vertices")
    lats = [p[0] for p in vertices]
    lons = [p[1] for p in vertices]
    if max(lats) - min(lats) > 1 or max(lons) - min(lons) > 1.5:
        raise ValueError("Polygon too large or crosses the date line")
    area2 = sum(vertices[i][1] * vertices[(i+1) % len(vertices)][0]
                - vertices[(i+1) % len(vertices)][1] * vertices[i][0]
                for i in range(len(vertices)))
    if abs(area2) * 111_000 * 111_000 * math.cos(
            math.radians(sum(lats) / len(lats))) / 2 < 100:
        raise ValueError("Polygon area is too small")
    for i in range(len(vertices)):
        a, b = vertices[i], vertices[(i+1) % len(vertices)]
        for j in range(i+1, len(vertices)):
            if (abs(i-j) == 1 or {i, j} == {0, len(vertices)-1}):
                continue
            c, d = vertices[j], vertices[(j+1) % len(vertices)]
            if _intersects(a, b, c, d):
                raise ValueError("Polygon edges may not cross")
    return {"name": name.strip(), "points": vertices}


def contains_point(vertices: list, latitude: float, longitude: float) -> bool:
    """Even/odd geographic point-in-polygon for small local geofences."""
    inside = False
    for i in range(len(vertices)):
        a = vertices[i]
        b = vertices[(i+1) % len(vertices)]
        if (a[0] > latitude) != (b[0] > latitude):
            lon_crossing = ((b[1] - a[1]) * (latitude - a[0])
                            / (b[0] - a[0]) + a[1])
            if longitude < lon_crossing:
                inside = not inside
    return inside


def polygon_zone(polygons: list[dict], latitude: float, longitude: float) -> str:
    for polygon in polygons:
        if contains_point(polygon.get("points") or [], latitude, longitude):
            return polygon.get("name") or ""
    return ""


class TinyFamilyGeofencesView(HomeAssistantView):
    url = "/api/tiny_family/geofences"
    name = "api:tiny_family:geofences"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    def _get(self, request, *, admin=False):
        runtime = self.hass.data.get("tiny_family_runtime", {})
        entry = runtime.get("entry")
        if entry is None:
            return None, web.json_response({"message": "Not configured"}, status=503)
        if admin and not request["hass_user"].is_admin:
            return None, web.json_response({"message": "Administrator required"}, status=403)
        config = {**entry.data, **entry.options}
        if not request["hass_user"].is_admin and not own_person(
            request["hass_user"].id, config.get("persons") or [],
            config.get("owners") or {},
        ):
            return None, web.json_response({"message": "Account not linked"}, status=403)
        return runtime, None

    async def get(self, request):
        runtime, error = self._get(request)
        if error is not None:
            return error
        return web.json_response({
            "geofences": list(runtime.get("geofences") or []),
            "editable": bool(request["hass_user"].is_admin),
        }, headers={"Cache-Control": "no-store"})

    async def post(self, request):
        return await self._write(request, create=True)

    async def put(self, request):
        return await self._write(request, create=False)

    async def _write(self, request, *, create):
        runtime, error = self._get(request, admin=True)
        if error is not None:
            return error
        try:
            payload = await request.json()
            valid = validate_polygon(payload)
            geofences = runtime.get("geofences")
            if not isinstance(geofences, list):
                return web.json_response({"message": "Geofences not initialized"}, status=503)
            if create:
                if len(geofences) >= 50:
                    raise ValueError("Too many geofences")
                item = {"id": uuid4().hex, **valid}
                if any(g["name"].casefold() == item["name"].casefold()
                       for g in geofences):
                    raise ValueError("Duplicate geofence name")
                geofences.append(item)
            else:
                item_id = payload.get("id")
                item = next((g for g in geofences if g["id"] == item_id), None)
                if item is None:
                    return web.json_response({"message": "Geofence not found"}, status=404)
                if any(g["id"] != item_id and
                       g["name"].casefold() == valid["name"].casefold()
                       for g in geofences):
                    raise ValueError("Duplicate geofence name")
                item.update(valid)
            await self.hass.async_add_executor_job(
                _save_places, self.hass.config.path("tiny_family_geofences.json"),
                {"items": geofences},
            )
        except (ValueError, TypeError, AttributeError, KeyError):
            return web.json_response({"message": "Invalid geofence"}, status=400)
        return web.json_response({"saved": True, "id": item["id"]},
                                 status=201 if create else 200,
                                 headers={"Cache-Control": "no-store"})

    async def delete(self, request):
        runtime, error = self._get(request, admin=True)
        if error is not None:
            return error
        try:
            data = await request.json()
            if data.get("confirm") is not True:
                raise ValueError("Confirmation required")
            geofences = runtime.get("geofences") or []
            item_id = data.get("id")
            if not any(item.get("id") == item_id for item in geofences):
                return web.json_response({"message": "Geofence not found"}, status=404)
            geofences[:] = [item for item in geofences if item.get("id") != item_id]
            await self.hass.async_add_executor_job(
                _save_places, self.hass.config.path("tiny_family_geofences.json"),
                {"items": geofences},
            )
        except (ValueError, TypeError, AttributeError):
            return web.json_response({"message": "Invalid deletion request"}, status=400)
        return web.json_response({"deleted": True}, headers={"Cache-Control": "no-store"})
