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


def resolve_speed_mps(reported_mps: float | None, *, distance_m: float | None,
                      elapsed_seconds: float | None, accuracy_m: float | None,
                      previous_accuracy_m: float | None = None) -> tuple[float | None, str]:
    """Prefer the phone's speed, but detect a stuck zero using actual GPS travel.

    The estimate is only made for consecutive, sufficiently accurate fixes.
    Uncertainty is handled by a deliberate minimum distance floor so
    ordinary GPS jitter does not appear as movement. The return value is not
    an authoritative vehicle speed; callers must keep the provenance label.
    """
    if reported_mps is not None and (
            not isinstance(reported_mps, (int, float)) or
            not math.isfinite(reported_mps) or not 0 <= reported_mps <= MAX_KMH / 3.6):
        raise ValueError("Invalid reported speed")
    if (distance_m is not None and elapsed_seconds is not None and
            math.isfinite(distance_m) and distance_m >= 0 and
            math.isfinite(elapsed_seconds) and 2 <= elapsed_seconds <= 300 and
            accuracy_m is not None and 0 <= accuracy_m <= 50 and
            previous_accuracy_m is not None and 0 <= previous_accuracy_m <= 50):
        uncertainty = accuracy_m + previous_accuracy_m
        minimum_displacement = max(25.0, 2 * uncertainty)
        if distance_m >= minimum_displacement:
            estimated = distance_m / elapsed_seconds
            if 0.7 <= estimated <= MAX_KMH / 3.6 and (
                    reported_mps is None or reported_mps < 0.3):
                return round(estimated, 3), "gps_estimate"
    if reported_mps is not None:
        return float(reported_mps), "phone"
    return None, "unavailable"


def _distance_between(lat1, lon1, lat2, lon2):
    a1, a2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = a2 - a1, math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(a1) * math.cos(a2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(max(0, a))))


def screen_gps_drift(state: dict, *, observed_at: float, latitude: float,
                     longitude: float, distance_m: float | None,
                     accuracy_m: float | None, speed_mps: float,
                     power_save: bool = False) -> str:
    """Hold isolated jumps while waiting for a second position to confirm.

    Returns accept, discard, or rebase. Rebase must never bridge the
    suspect distance to the previous trusted fix. This protects trips,
    inferred speed, zones and learned stays during GPS battery-saving drift.
    """
    last_t = state.get("last_t")
    if last_t is None or distance_m is None:
        state.pop("gps_suspect", None)
        return "accept"
    delta = observed_at - last_t
    if delta <= 0 or delta > CONTINUITY_SECONDS:
        state.pop("gps_suspect", None)
        return "accept"
    uncertainty = max(25.0, accuracy_m or 0)
    pending = state.get("gps_suspect")
    if pending:
        # A return near the last confirmed point proves the earlier one
        # was a positioning glitch.
        if distance_m < max(100, 3 * uncertainty):
            state.pop("gps_suspect", None)
            return "accept"
        distance_from_candidate = _distance_between(
            latitude, longitude, pending["lat"], pending["lon"]
        )
        elapsed = max(1, observed_at - pending["ts"])
        if (observed_at > pending["ts"] and
                distance_from_candidate <= max(180, elapsed * 35 + 3 * uncertainty)):
            state.pop("gps_suspect", None)
            # Two consistent GPS positions corroborate genuine movement even
            # when Companion keeps reporting speed=0. Accept the subsequent
            # plausible fixes without repeatedly discarding every other one.
            if (accuracy_m is not None and accuracy_m <= 35 and
                    3.5 <= distance_from_candidate / elapsed <= 40):
                state["gps_motion_confirmed_until"] = observed_at + 120
            return "rebase"
        # Continued wild GPS jumps are not a plausible track.
        state["gps_suspect"] = {"lat": latitude, "lon": longitude, "ts": observed_at}
        return "discard"
    implied_speed = distance_m / delta
    motion_confirmed = (observed_at <= state.get("gps_motion_confirmed_until", 0)
                        and accuracy_m is not None and accuracy_m <= 35
                        and 3.5 <= implied_speed <= 40)
    if motion_confirmed:
        state["gps_motion_confirmed_until"] = observed_at + 120
    suspect = (
        delta <= 600 and distance_m >= max(160, 4 * uncertainty) and
        (power_save or (speed_mps < 2 and implied_speed >= 3.5)
         or implied_speed > 45)
    ) and not motion_confirmed
    if suspect:
        state["gps_suspect"] = {"lat": latitude, "lon": longitude, "ts": observed_at}
        return "discard"
    return "accept"


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
        "trip_start_lat": None, "trip_start_lon": None,
        "trip_dist_m": 0.0, "trip_max_speed": 0.0,
        "stay_start": None, "stay_n": 0, "current_stay_min": 0,
        "stay_lat_sum": 0.0, "stay_lon_sum": 0.0,
        "movement_state": "unknown", "movement_candidate": "",
        "movement_candidate_samples": 0, "speed_kmh": None,
        "speed_source": "unavailable", "last_gps_accuracy": None,
        "destination": "", "dest_eta_min": 0, "dest_dist_m": 0.0,
        "destination_confidence": 0.0, "destination_private": False, "home_eta_min": None,
        "zone_stable": None, "zone_candidate": None, "recent": [],
        "gps_suspect": None,
        "gps_motion_confirmed_until": 0,
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
