"""Resolve Companion sensors from the *same Home Assistant device* as a tracker.

Never infer a sensor from a similar device name or a different phone.
A missing/unregistered device produces no guesses: the admin editor then
offers a manual fallback for unusual Home Assistant configurations.
"""
from __future__ import annotations

from homeassistant.helpers import entity_registry as er

PHONE_SENSOR_KEYS = ("battery", "charging", "activity", "power_save")


def selected_phone_sensors(config: dict, person: str) -> tuple[str, ...]:
    """Admin-selected categories; upgrades default to all useful sensors on."""
    selection = (config.get("phone_sensor_selection") or {}).get(person)
    if selection is None:
        return PHONE_SENSOR_KEYS
    return tuple(key for key in PHONE_SENSOR_KEYS if key in selection)


def companion_sensor_inventory(hass, tracker: str) -> dict[str, dict]:
    """Report registered sensors, including disabled/missing ones, for one phone.

    A Home Assistant entity existing does *not* mean the Companion app has
    enabled that sensor. The integration cannot remotely change app switches.
    """
    missing = {key: {"entity_id": None, "status": "missing"}
               for key in PHONE_SENSOR_KEYS}
    if not isinstance(tracker, str) or not tracker.startswith("device_tracker."):
        return missing
    registry = er.async_get(hass)
    entry = registry.async_get(tracker)
    if entry is None or not entry.device_id:
        return missing
    device_id = entry.device_id
    candidates: dict[str, tuple[tuple[int, int], object]] = {}

    for peer in registry.entities.values():
        if peer.device_id != device_id:
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
        if ("power_save" in slug or "battery_saver" in slug) and domain in (
            "sensor", "binary_sensor"
        ):
            scores["power_save"] = 130 if domain == "binary_sensor" else 100

        for key, score in scores.items():
            # Prefer an enabled entity to a better-named but disabled one.
            rank = (int(peer.disabled_by is None), score)
            current = candidates.get(key)
            if current is None or rank > current[0]:
                candidates[key] = (rank, peer)

    for key, (_, peer) in candidates.items():
        state = hass.states.get(peer.entity_id)
        if peer.disabled_by is not None:
            status = "disabled_in_ha"
        elif state is None or state.state in ("unknown", "unavailable"):
            status = "unavailable"
        else:
            status = "ready"
        missing[key] = {"entity_id": peer.entity_id, "status": status}
    return missing


def companion_device_sensors(hass, tracker: str) -> dict[str, str]:
    """Pick battery, charging and detected activity for one device_tracker."""
    return {key: info["entity_id"]
            for key, info in companion_sensor_inventory(hass, tracker).items()
            if info["entity_id"] and info["status"] != "disabled_in_ha"}
