"""Stable movement-state classification for HA automation entities and events.

A deliberately conservative, in-memory state machine. No coordinates are emitted
as events or written to this module. Learned routine detection is separate work.
"""
from __future__ import annotations

from math import isfinite

MAX_ACCURACY_M = 150.0
MIN_SPEED_MPS = 1.2
MIN_DISPLACEMENT_M = 45.0
CONFIRMATION_SAMPLES = 2


def update_motion(state: dict, *, observed_at: float, speed_mps: float,
                  displacement_m: float | None, accuracy_m: float | None = None) -> str | None:
    """Update movement state. Return 'started'/'stopped' only on confirmed change.

    First reliable observation establishes baseline silently (e.g. after restart).
    Missing/poor GPS, duplicate timestamps and improbable jumps never fire events.
    """
    if not isfinite(observed_at) or not isfinite(speed_mps) or speed_mps < 0:
        return None
    if accuracy_m is not None and (
        not isfinite(accuracy_m) or accuracy_m < 0 or accuracy_m > MAX_ACCURACY_M
    ):
        return None
    previous_t = state.get("last_t")
    delta_s = (observed_at - previous_t) if previous_t is not None else None
    if delta_s is not None and delta_s <= 0:
        return None

    motion_by_speed = speed_mps >= MIN_SPEED_MPS
    reliable_distance = (
        displacement_m is not None
        and isfinite(displacement_m) and displacement_m >= 0
        and delta_s is not None and 10 <= delta_s <= 900
        and displacement_m <= 200 * 1000 * delta_s / 3600
        and displacement_m >= max(MIN_DISPLACEMENT_M, (accuracy_m or 0) * 1.5)
        and displacement_m / delta_s >= 0.8
    )
    observed = "moving" if motion_by_speed or reliable_distance else "stationary"
    current = state.get("movement_state", "unknown")

    if current == "unknown":
        state["movement_state"] = observed
        state["movement_candidate"] = ""
        state["movement_candidate_samples"] = 0
        return None
    if observed == current:
        state["movement_candidate"] = ""
        state["movement_candidate_samples"] = 0
        return None

    if state.get("movement_candidate") == observed:
        samples = state.get("movement_candidate_samples", 0) + 1
    else:
        samples = 1
    state["movement_candidate"] = observed
    state["movement_candidate_samples"] = samples
    if samples < CONFIRMATION_SAMPLES:
        return None

    state["movement_state"] = observed
    state["movement_candidate"] = ""
    state["movement_candidate_samples"] = 0
    return "started" if observed == "moving" else "stopped"
