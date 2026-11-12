"""Time-based GPS validity and continuity without storing coordinates.

A stale location is never treated as stationary. Recover from missing updates
using a fresh baseline instead of inventing travel across an offline interval.
"""
from __future__ import annotations

import math

MAX_ACCURACY_M = 150.0
FRESH_SECONDS = 15 * 60
CONTINUITY_SECONDS = 15 * 60
MAX_KMH = 200.0
FUTURE_TOLERANCE_SECONDS = 60


def assess_sample(state: dict, *, observed_at: float, now_ts: float,
                  latitude: float, longitude: float, speed_mps: float,
                  accuracy_m: float | None, distance_m: float | None) -> str:
    """Return invalid, duplicate, jump, baseline, gap or continuous."""
    values = (observed_at, now_ts, latitude, longitude, speed_mps)
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in values):
        return "invalid"
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return "invalid"
    if not (0 <= speed_mps <= MAX_KMH / 3.6):
        return "invalid"
    if accuracy_m is not None and (
            not math.isfinite(accuracy_m) or not 0 <= accuracy_m <= MAX_ACCURACY_M):
        return "invalid"
    if not 0 <= now_ts - observed_at <= FRESH_SECONDS and not (
            0 < observed_at - now_ts <= FUTURE_TOLERANCE_SECONDS):
        return "invalid"
    if state.get("gps_seen_at") is not None and observed_at <= state["gps_seen_at"]:
        return "duplicate"
    last_t = state.get("last_t")
    if last_t is None:
        return "baseline"
    delta = observed_at - last_t
    if delta <= 0:
        return "duplicate"
    if delta > CONTINUITY_SECONDS:
        return "gap"
    if distance_m is not None:
        if not math.isfinite(distance_m) or distance_m < 0:
            return "invalid"
        # Up to 200 km/h plus a generous positioning error allowance.
        if distance_m > delta * MAX_KMH / 3.6 + max(75.0, 3 * (accuracy_m or 0)):
            return "jump"
    return "continuous"


def reset_continuity(state: dict) -> None:
    """Discard unfinished trips/stays and last fix, preserving accumulated totals."""
    state.update({
        "last_t": None, "last_lat": None, "last_lon": None,
        "trip_active": False, "trip_start": None, "trip_last_move": None,
        "trip_dist_m": 0.0, "trip_max_speed": 0.0,
        "stay_start": None, "stay_n": 0, "current_stay_min": 0,
        "stay_lat_sum": 0.0, "stay_lon_sum": 0.0,
        "movement_state": "unknown", "movement_candidate": "",
        "movement_candidate_samples": 0, "speed_kmh": 0.0,
        "destination": "", "dest_eta_min": 0, "dest_dist_m": 0.0,
        "destination_confidence": 0.0, "home_eta_min": None,
        "zone_stable": None, "zone_candidate": None, "recent": [],
    })


def mark_stale(state: dict, now_ts: float) -> bool:
    """Transition fresh -> stale exactly once after prolonged GPS silence."""
    seen = state.get("gps_seen_at")
    if (not isinstance(seen, (float, int)) or
            state.get("gps_health") != "fresh" or
            now_ts - seen <= FRESH_SECONDS):
        return False
    reset_continuity(state)
    state["gps_health"] = "stale"
    return True
