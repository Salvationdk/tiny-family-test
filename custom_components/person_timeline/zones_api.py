"""Create geographic Home Assistant zones from the Tiny Family map.

Only HA administrators can create zones. Existing HA zone storage is reused,
not a parallel hidden geofencing database.
"""
from __future__ import annotations

import math

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .privacy import shared_map_zones
from .utils import _hav

try:
    from homeassistant.components.zone.const import DATA_ZONE
except ImportError:
    DATA_ZONE = None
try:
    from homeassistant.components.zone import DATA_ZONE_STORAGE_COLLECTION
except ImportError:
    DATA_ZONE_STORAGE_COLLECTION = None


def validate_new_zone(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Zone data must be an object")
    name = data.get("name")
    lat = data.get("latitude")
    lon = data.get("longitude")
    radius = data.get("radius")
    if not isinstance(name, str) or not (1 <= len(name.strip()) <= 80):
        raise ValueError("Zone name must be 1–80 characters")
    if any(type(value) not in (int, float) for value in (lat, lon, radius)):
        raise ValueError("Numeric coordinates and radius required")
    if not (all(math.isfinite(value) for value in (lat, lon, radius))
            and -90 <= lat <= 90 and -180 <= lon <= 180
            and 25 <= radius <= 5000):
        raise ValueError("Invalid zone center or radius (25–5000 m)")
    return {
        "name": name.strip(),
        "latitude": float(lat),
        "longitude": float(lon),
        "radius": float(radius),
        "passive": False,
        "icon": "mdi:map-marker",
    }


def zone_collection(hass):
    data = hass.data.get(DATA_ZONE) if DATA_ZONE is not None else None
    collection = getattr(data, "storage_collection", None)
    if collection is None and DATA_ZONE_STORAGE_COLLECTION is not None:
        collection = hass.data.get(DATA_ZONE_STORAGE_COLLECTION)
    return collection


def _storage_zone(collection, zone_id):
    """Only editable storage items, never YAML zones or zone.home."""
    if not isinstance(zone_id, str) or len(zone_id) > 128:
        return None
    for item in collection.async_items():
        if isinstance(item, dict) and item.get("id") == zone_id:
            return item
    return None


class TinyFamilyZonesView(HomeAssistantView):
    url = "/api/tiny_family/zones"
    name = "api:tiny_family:zones"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    def _admin_collection(self, request):
        if not request["hass_user"].is_admin:
            return None, web.json_response({"message": "Administrator required"}, status=403)
        if self.hass.data.get("tiny_family_runtime", {}).get("entry") is None:
            return None, web.json_response({"message": "Tiny Family not configured"}, status=503)
        collection = zone_collection(self.hass)
        if collection is None:
            return None, web.json_response({"message": "Home Assistant zone storage unavailable"}, status=503)
        return collection, None

    async def get(self, request):
        collection, error = self._admin_collection(request)
        if error is not None:
            return error
        zones = [
            {k: value for k, value in item.items()
             if k in ("id", "name", "latitude", "longitude", "radius")}
            for item in collection.async_items() if isinstance(item, dict)
        ]
        return web.json_response({"zones": zones}, headers={"Cache-Control": "no-store"})

    async def put(self, request):
        collection, error = self._admin_collection(request)
        if error is not None:
            return error
        try:
            payload = await request.json()
            zone_id = payload.get("zone_id")
            item = _storage_zone(collection, zone_id)
            if item is None:
                return web.json_response({"message": "Only editable stored zones can be changed"}, status=404)
            update = validate_new_zone(payload)
        except (AttributeError, ValueError, TypeError):
            return web.json_response({"message": "Invalid zone update"}, status=400)
        for other in collection.async_items():
            if other.get("id") != zone_id and _hav(
                update["latitude"], update["longitude"],
                float(other["latitude"]), float(other["longitude"])
            ) < 10:
                return web.json_response({"message": "Another stored zone is too close"}, status=409)
        try:
            await collection.async_update_item(zone_id, update)
        except (ValueError, KeyError):
            return web.json_response({"message": "Update rejected by Home Assistant"}, status=400)
        return web.json_response({"updated": True, "zone_id": zone_id},
                                 headers={"Cache-Control": "no-store"})

    async def delete(self, request):
        collection, error = self._admin_collection(request)
        if error is not None:
            return error
        try:
            data = await request.json()
            zone_id = data.get("zone_id")
            if data.get("confirm") is not True:
                return web.json_response({"message": "Confirmation required"}, status=400)
            if _storage_zone(collection, zone_id) is None:
                return web.json_response({"message": "Only editable stored zones can be removed"}, status=404)
        except (AttributeError, ValueError, TypeError):
            return web.json_response({"message": "Invalid zone deletion"}, status=400)
        try:
            await collection.async_delete_item(zone_id)
        except (ValueError, KeyError):
            return web.json_response({"message": "Deletion rejected by Home Assistant"}, status=400)
        return web.json_response({"deleted": True, "zone_id": zone_id},
                                 headers={"Cache-Control": "no-store"})

    async def post(self, request):
        if not request["hass_user"].is_admin:
            return web.json_response({"message": "Administrator required"}, status=403)
        if self.hass.data.get("tiny_family_runtime", {}).get("entry") is None:
            return web.json_response({"message": "Tiny Family not configured"}, status=503)
        try:
            data = validate_new_zone(await request.json())
        except (ValueError, TypeError):
            return web.json_response({"message": "Invalid zone name, center or radius"},
                                     status=400)
        for zone in shared_map_zones(self.hass):
            if _hav(data["latitude"], data["longitude"],
                    zone["latitude"], zone["longitude"]) < 10:
                return web.json_response({"message": "A zone already exists at this location"},
                                         status=409)
        collection = zone_collection(self.hass)
        if collection is None:
            return web.json_response({"message": "Home Assistant zone storage unavailable"},
                                     status=503)
        try:
            await collection.async_create_item(data)
        except (ValueError, KeyError) as err:
            return web.json_response({"message": "Home Assistant rejected the zone"},
                                     status=400)
        return web.json_response({"created": True, "name": data["name"]}, status=201,
                                 headers={"Cache-Control": "no-store"})
