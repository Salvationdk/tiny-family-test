"""Resolve Companion sensors from the *same Home Assistant device* as a tracker.

Never infer a sensor from a similar device name or a different phone.
A missing/unregistered device produces no guesses: the admin editor then
offers a manual fallback for unusual Home Assistant configurations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite

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


def phone_tracker_diagnostic(hass, tracker: str, now: datetime | None = None) -> dict:
    """Inspect an actual HA tracker, not the friendly name in the selector.

    Only metadata and health are returned to the admin UI, never coordinates.
    A GPS fix older than 15 minutes is stale, matching Tiny Family's runtime.
    Reading the current state cannot force an iOS/Android location update.
    """
    now = now or datetime.now(timezone.utc)
    state = hass.states.get(tracker) if isinstance(tracker, str) else None
    details = {
        "tracker": tracker, "name": state.name if state else tracker,
        "device_name": None, "manufacturer": None, "model": None,
        "platform": None, "is_companion": False,
        "tracking_type": "unknown", "gps_status": "not_found",
        "position_available": False, "age_seconds": None,
        "accuracy_m": None, "phone_speed_kmh": None,
    }
    if not tracker or not tracker.startswith("device_tracker.") or state is None:
        return details

    registry = er.async_get(hass)
    registration = registry.async_get(tracker)
    if registration is not None:
        details["platform"] = getattr(registration, "platform", None)
        details["is_companion"] = details["platform"] == "mobile_app"
        if registration.device_id:
            from homeassistant.helpers import device_registry as dr
            device = dr.async_get(hass).async_get(registration.device_id)
            if device is not None:
                details["device_name"] = (getattr(device, "name_by_user", None)
                                          or getattr(device, "name", None))
                details["manufacturer"] = getattr(device, "manufacturer", None)
                details["model"] = getattr(device, "model", None)

    attrs = state.attributes
    tracking_type = attrs.get("tracking_type")
    source_type = attrs.get("source_type")
    if tracking_type == "connection" or source_type in ("router", "bluetooth", "bluetooth_le"):
        details["tracking_type"] = "connection"
    elif tracking_type == "position" or source_type == "gps":
        details["tracking_type"] = "position"

    try:
        latitude, longitude = float(attrs["latitude"]), float(attrs["longitude"])
        details["position_available"] = (isfinite(latitude) and isfinite(longitude)
                                         and -90 <= latitude <= 90 and -180 <= longitude <= 180)
    except (KeyError, TypeError, ValueError, OverflowError):
        pass
    # Legacy GPS trackers may not expose tracking_type/source_type.
    if details["tracking_type"] == "unknown" and details["position_available"]:
        details["tracking_type"] = "position"

    try:
        stamp = state.last_updated
        if stamp is not None:
            details["age_seconds"] = max(0, round((now - stamp).total_seconds()))
    except (AttributeError, TypeError, ValueError):
        pass
    try:
        accuracy = float(attrs["gps_accuracy"])
        if isfinite(accuracy) and accuracy >= 0:
            details["accuracy_m"] = round(accuracy)
    except (KeyError, TypeError, ValueError, OverflowError):
        pass
    try:
        # Device tracker speed is read by Tiny Family in metres per second.
        speed_mps = float(attrs["speed"])
        if isfinite(speed_mps) and 0 <= speed_mps <= 200 / 3.6:
            details["phone_speed_kmh"] = round(speed_mps * 3.6, 1)
    except (KeyError, TypeError, ValueError, OverflowError):
        pass

    if details["tracking_type"] == "connection":
        details["gps_status"] = "not_gps"
    elif state.state in ("unknown", "unavailable"):
        details["gps_status"] = "unavailable"
    elif details["tracking_type"] != "position":
        details["gps_status"] = "unverified"
    elif not details["position_available"]:
        details["gps_status"] = "no_fix"
    elif details["age_seconds"] is None:
        details["gps_status"] = "unverified"
    elif details["age_seconds"] > 15 * 60:
        details["gps_status"] = "stale"
    elif details["age_seconds"] > 5 * 60:
        details["gps_status"] = "delayed"
    else:
        details["gps_status"] = "fresh"
    return details


def validate_phone_trackers(hass, mappings: dict[str, str]) -> None:
    """Prevent multiple people following one device or selecting router presence."""
    selected = [tracker for tracker in mappings.values() if tracker]
    if len(selected) != len(set(selected)):
        raise ValueError("A GPS phone may only be assigned to one person")
    for tracker in selected:
        diagnosis = phone_tracker_diagnostic(hass, tracker)
        if diagnosis["gps_status"] == "not_found":
            raise ValueError("The selected phone tracker does not exist")
        if diagnosis["tracking_type"] == "connection":
            raise ValueError("A connection-only tracker cannot provide GPS")
        # Companion GPS may not have provided its first fix yet. Permit its
        # selection so the administrator can diagnose missing permissions.
        if diagnosis["tracking_type"] == "unknown" and not diagnosis["is_companion"]:
            raise ValueError("The selected tracker cannot be verified as GPS")
