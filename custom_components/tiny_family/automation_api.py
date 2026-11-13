"""Stable, read-only geographic calculations for HA YAML scripts and extensions."""
from __future__ import annotations

import math

from .geofences import contains_point
from .places import estimate_destination_eta
from .utils import _hav


def _number(data, key, low, high, *, required=False):
    value = data.get(key)
    if value is None and not required:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Invalid {key}")
    return float(value)


def evaluate_location(polygons: list[dict], payload: dict) -> dict:
    """Check every polygon, optionally calculate distance and conservative ETA.

    No private person state is read, only supplied coordinates and shared
    polygon definitions. This is safe for system automations without user_id.
    """
    if not isinstance(payload, dict):
        raise ValueError("Location must be an object")
    latitude = _number(payload, "latitude", -90, 90, required=True)
    longitude = _number(payload, "longitude", -180, 180, required=True)
    inside = [
        {"id": polygon["id"], "name": polygon["name"],
         "entity_id": "sensor.tiny_family_polygon_" + polygon["id"]}
        for polygon in polygons
        if contains_point(polygon["points"], latitude, longitude)
    ]
    result = {"inside_any_polygon": bool(inside),
              "polygon_count": len(inside), "polygons": inside}
    target_lat = _number(payload, "target_latitude", -90, 90)
    target_lon = _number(payload, "target_longitude", -180, 180)
    speed_kmh = _number(payload, "speed_kmh", 0, 200)
    if (target_lat is None) != (target_lon is None):
        raise ValueError("Both destination coordinates are required")
    if speed_kmh is not None and target_lat is None:
        raise ValueError("Speed requires destination coordinates")
    if target_lat is not None:
        distance = _hav(latitude, longitude, target_lat, target_lon)
        result["distance_m"] = round(distance)
        result["distance_km"] = round(distance / 1000, 3)
        result["eta_minutes"] = (estimate_destination_eta(distance, speed_kmh / 3.6)
                                 if speed_kmh is not None else None)
        result["eta_is_estimate"] = True
    return result
