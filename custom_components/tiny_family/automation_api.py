"""Stable, read-only geographic calculations for HA YAML scripts and extensions."""
from __future__ import annotations

import math

from .geofences import contains_point
from .gps_quality import MAX_KMH, resolve_speed_mps
from .places import estimate_destination_eta
from .utils import _hav


def _number(data, key, low, high, *, required=False):
    value = data.get(key)
    if value is None and not required:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Invalid {key}")
    return float(value)


def evaluate_location(polygons: list[dict], payload: dict,
                      circles: list[dict] | None = None) -> dict:
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
    zones = [
        {"entity_id": zone["id"], "name": zone["name"], "shape": "circle"}
        for zone in (circles or [])
        if _hav(latitude, longitude, zone["latitude"], zone["longitude"])
        <= zone["radius_m"]
    ]
    result.update({"inside_any_circle": bool(zones),
                   "circle_count": len(zones), "circles": zones,
                   "inside_any_area": bool(inside or zones)})
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


def analyze_motion(payload: dict) -> dict:
    """Analyze two caller-supplied fixes; never access stored family GPS."""
    if not isinstance(payload, dict):
        raise ValueError("Motion input must be an object")
    start_lat = _number(payload, "start_latitude", -90, 90, required=True)
    start_lon = _number(payload, "start_longitude", -180, 180, required=True)
    end_lat = _number(payload, "end_latitude", -90, 90, required=True)
    end_lon = _number(payload, "end_longitude", -180, 180, required=True)
    elapsed = _number(payload, "elapsed_seconds", 0.001, 86400, required=True)
    accuracy = _number(payload, "accuracy_m", 0, 150)
    previous_accuracy = _number(payload, "previous_accuracy_m", 0, 150)
    reported = _number(payload, "reported_speed_mps", 0, MAX_KMH / 3.6)
    distance = _hav(start_lat, start_lon, end_lat, end_lon)
    continuous = elapsed <= 900 and distance <= (
        elapsed * MAX_KMH / 3.6 + max(75.0, 3 * (accuracy or 0)))
    speed, source = resolve_speed_mps(
        reported, distance_m=distance if continuous else None,
        elapsed_seconds=elapsed if continuous else None,
        accuracy_m=accuracy, previous_accuracy_m=previous_accuracy)
    movement = ("unknown" if speed is None else
                "moving" if speed >= 2.2 else
                "stationary" if speed < 0.5 else "uncertain")
    return {
        "displacement_m": round(distance),
        "displacement_km": round(distance / 1000, 3),
        "elapsed_seconds": round(elapsed, 2),
        "continuous": continuous,
        "speed_kmh": round(speed * 3.6, 1) if speed is not None else None,
        "speed_source": source,
        "movement": movement,
        "is_estimate": source == "gps_estimate",
        "distance_is_airline": True,
    }


def analyze_route(payload: dict) -> dict:
    """Summarize <=200 supplied GPS fixes using the shared motion algorithm.

    Only aggregate values are returned; no coordinates, identities or private
    history are read or retained. Gaps and implausible jumps are not bridged.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("fixes"), list):
        raise ValueError("fixes must be a list")
    fixes = payload["fixes"]
    if not 2 <= len(fixes) <= 200:
        raise ValueError("fixes must contain 2 to 200 points")
    validated = []
    for point in fixes:
        if not isinstance(point, dict):
            raise ValueError("Each GPS fix must be an object")
        validated.append({
            "lat": _number(point, "latitude", -90, 90, required=True),
            "lon": _number(point, "longitude", -180, 180, required=True),
            "t": _number(point, "timestamp", 0, 4_102_444_800, required=True),
            "accuracy": _number(point, "accuracy_m", 0, 150),
            "speed": _number(point, "speed_mps", 0, MAX_KMH / 3.6),
        })
    distance_m = 0.0
    moving_seconds = 0.0
    max_speed = None
    intervals = 0
    gaps = 0
    speed_sources = {"phone": 0, "gps_estimate": 0, "unavailable": 0}
    for previous, current in zip(validated, validated[1:]):
        elapsed = current["t"] - previous["t"]
        if elapsed <= 0:
            raise ValueError("GPS timestamps must be increasing")
        leg = analyze_motion({
            "start_latitude": previous["lat"], "start_longitude": previous["lon"],
            "end_latitude": current["lat"], "end_longitude": current["lon"],
            "elapsed_seconds": elapsed, "accuracy_m": current["accuracy"],
            "previous_accuracy_m": previous["accuracy"],
            "reported_speed_mps": current["speed"],
        })
        if not leg["continuous"]:
            gaps += 1
            continue
        intervals += 1
        speed_sources[leg["speed_source"]] += 1
        # Do not sum jitter or claim road distance from only two coordinates.
        floor = max(20.0, 1.5 * ((current["accuracy"] or 0) +
                                  (previous["accuracy"] or 0)))
        if leg["displacement_m"] >= floor:
            distance_m += leg["displacement_m"]
        if leg["movement"] == "moving":
            moving_seconds += elapsed
        speed = leg["speed_kmh"]
        if speed is not None:
            max_speed = speed if max_speed is None else max(max_speed, speed)
    return {
        "fix_count": len(validated), "valid_intervals": intervals,
        "gps_gaps": gaps,
        "distance_km": round(distance_m / 1000, 3),
        "duration_minutes": round((validated[-1]["t"] - validated[0]["t"]) / 60, 1),
        "moving_minutes": round(moving_seconds / 60, 1),
        "max_speed_kmh": round(max_speed, 1) if max_speed is not None else None,
        "speed_sources": speed_sources,
        "distance_is_gps_estimate": True,
    }
