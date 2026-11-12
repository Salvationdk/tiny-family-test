"""Resolve Companion sensors from the *same Home Assistant device* as a tracker.

Never infer a sensor from a similar device name or a different phone.
A missing/unregistered device produces no guesses: the admin editor then
offers a manual fallback for unusual Home Assistant configurations.
"""
from __future__ import annotations

from homeassistant.helpers import entity_registry as er


def companion_device_sensors(hass, tracker: str) -> dict[str, str]:
    """Pick battery, charging and detected activity for one device_tracker."""
    if not isinstance(tracker, str) or not tracker.startswith("device_tracker."):
        return {}
    registry = er.async_get(hass)
    entry = registry.async_get(tracker)
    if entry is None or not entry.device_id:
        return {}
    device_id = entry.device_id
    candidates: dict[str, tuple[int, str]] = {}

    for peer in registry.entities.values():
        if peer.device_id != device_id or peer.disabled_by is not None:
            continue
        entity_id = peer.entity_id
        domain, _, slug = entity_id.partition(".")
        if domain not in ("sensor", "binary_sensor"):
            continue
        state = hass.states.get(entity_id)
        attributes = state.attributes if state is not None else {}
        device_class = str(attributes.get("device_class") or "").lower()
        slug = slug.lower()
        scores: dict[str, int] = {}
        if domain == "sensor":
            if "battery_level" in slug or "battery_percentage" in slug:
                scores["battery"] = 130
            elif device_class == "battery" and not any(
                token in slug for token in ("health", "state", "temperature")
            ):
                scores["battery"] = 100
            if "detected_activity" in slug:
                scores["activity"] = 140
            elif slug.endswith("_activity") or "activity_type" in slug:
                scores["activity"] = 120
            elif "motion_activity" in slug:
                scores["activity"] = 100
            if "battery_state" in slug or slug.endswith("_charging"):
                scores["charging"] = 80
        if domain == "binary_sensor" and (
            device_class == "battery_charging" or "is_charging" in slug
            or slug.endswith("_charging")
        ):
            scores["charging"] = 140

        for key, score in scores.items():
            current = candidates.get(key)
            if current is None or (score, entity_id) > current:
                candidates[key] = (score, entity_id)
    return {key: value[1] for key, value in candidates.items()}
