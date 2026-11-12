"""Normalize selected Home Assistant Companion charging and activity sensors.

Only configured entities are read; no device IDs or GPS coordinates are stored.
"""
from __future__ import annotations

CHARGING_ON = frozenset(("on", "charging", "full", "plugged", "plugged_in", "true", "1"))
CHARGING_OFF = frozenset(("off", "discharging", "not_charging", "unplugged", "false", "0"))

def charging_state(value) -> str:
    """Return 'on', 'off' or 'unknown'; never infer from battery percentage."""
    if value is None:
        return "unknown"
    normalized = str(value).strip().lower().replace(" ", "_")
    if normalized in CHARGING_ON:
        return "on"
    if normalized in CHARGING_OFF:
        return "off"
    return "unknown"

def activity_state(value) -> str:
    if value is None:
        return "unknown"
    normalized = str(value).strip().lower()
    if not normalized or normalized in ("unknown", "unavailable", "none"):
        return "unknown"
    return normalized[:64]

def companion_readings(hass, *, charging_entity: str | None,
                       activity_entity: str | None) -> dict[str, str]:
    charging = hass.states.get(charging_entity) if charging_entity else None
    activity = hass.states.get(activity_entity) if activity_entity else None
    return {
        "charging": charging_state(charging.state if charging is not None else None),
        "activity": activity_state(activity.state if activity is not None else None),
    }
