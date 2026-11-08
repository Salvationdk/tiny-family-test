"""Conservative Companion activity alerts; deterministic and privacy-aware.

Nothing in this module directly sends a notification, persists user data, or
publishes coordinates. All outgoing messages require explicit admin opt-in.
"""
from __future__ import annotations

import math

ALERT_EVENTS = frozenset((
    "zone_arrived", "zone_departed", "battery_low",
    "speed_warning", "trip_ended", "weekly_summary",
    "tracking_stale", "tracking_restored",
))
# Monitoring warnings are opt-in, never silently enabled for existing users.
DEFAULT_ALERT_EVENTS = tuple(sorted(ALERT_EVENTS - {
    "tracking_stale", "tracking_restored",
}))
ZONE_DWELL_SECONDS = 5 * 60
SPEED_WARNING_KMH = 130
SPEED_REARM_KMH = 120
BATTERY_LOW = 20
BATTERY_REARM = 25


def update_zone(state: dict, zone: str, observed_at: float) -> list[tuple[str, dict]]:
    """Require five minutes of stable readings for arrival or departure.

    Initialize silently; never send an arrival immediately after HA restart.
    """
    zone = str(zone or "").strip()
    previous = state.get("zone_stable")
    if previous is None:
        state["zone_stable"] = zone
        state["zone_candidate"] = None
        return []
    if zone == previous:
        state["zone_candidate"] = None
        return []
    candidate = state.get("zone_candidate")
    if not candidate or candidate[0] != zone:
        state["zone_candidate"] = (zone, observed_at)
        return []
    if observed_at - candidate[1] < ZONE_DWELL_SECONDS:
        return []
    state["zone_candidate"] = None
    state["zone_stable"] = zone
    changes = []
    if previous:
        changes.append(("zone_departed", {"zone": previous}))
    if zone:
        changes.append(("zone_arrived", {"zone": zone}))
    return changes


def update_battery(state: dict, percent: float | None) -> list[tuple[str, dict]]:
    """Send once when the battery crosses below 20%, rearm above 25%."""
    if percent is None or not isinstance(percent, (int, float)) or not math.isfinite(percent):
        return []
    if percent < 0 or percent > 100:
        return []
    active = state.get("battery_alert_active")
    state["battery_percent"] = percent
    if active is None:
        state["battery_alert_active"] = percent < BATTERY_LOW
        return []
    if active and percent >= BATTERY_REARM:
        state["battery_alert_active"] = False
        return []
    if not active and percent < BATTERY_LOW:
        state["battery_alert_active"] = True
        return [("battery_low", {"battery": round(percent)})]
    return []


def update_speed(state: dict, kmh: float, accuracy_m: float | None,
                 observed_at: float, threshold_kmh: int = SPEED_WARNING_KMH
                 ) -> list[tuple[str, dict]]:
    """Require two credible GPS readings above the administrator's limit."""
    if type(threshold_kmh) is not int or not 30 <= threshold_kmh <= 200:
        raise ValueError("Speed warning threshold must be 30–200 km/h")
    # Reset warning hysteresis after an administrator changes the limit.
    if state.get("speed_threshold_kmh") != threshold_kmh:
        state["speed_threshold_kmh"] = threshold_kmh
        state.pop("speed_warning_active", None)
        state.pop("speed_first_high", None)
    rearm_kmh = max(0, threshold_kmh - 10)
    if not isinstance(kmh, (int, float)) or not math.isfinite(kmh):
        return []
    if kmh < 0 or kmh > 220 or (accuracy_m is not None and accuracy_m > 75):
        return []
    if kmh <= rearm_kmh:
        state["speed_warning_active"] = False
        state["speed_first_high"] = None
        return []
    if kmh <= threshold_kmh or state.get("speed_warning_active"):
        state["speed_first_high"] = None
        return []
    first = state.get("speed_first_high")
    if first is None or not (5 <= observed_at - first <= 120):
        state["speed_first_high"] = observed_at
        return []
    state["speed_first_high"] = None
    state["speed_warning_active"] = True
    return [("speed_warning", {
        "speed_kmh": round(kmh), "limit_kmh": threshold_kmh,
    })]


def message_for_event(event: str, name: str, details: dict) -> tuple[str, str]:
    """Human-readable text with no raw GPS coordinates."""
    if event == "zone_arrived":
        return "Tiny Family – ankomst", f"{name} er ankommet til {details['zone']}."
    if event == "zone_departed":
        return "Tiny Family – afgang", f"{name} har forladt {details['zone']}."
    if event == "battery_low":
        return "Tiny Family – batteri", f"{name}s telefon er nede på {details['battery']} %."
    if event == "speed_warning":
        return "Tiny Family – fart", f"{name} er registreret med {details['speed_kmh']} km/t. GPS-data kan være upræcise."
    if event == "trip_ended":
        return "Tiny Family – tur", (
            f"{name}s tur er afsluttet: {details['distance_km']:.1f} km, "
            f"{details['duration_min']:.0f} min., "
            f"maks. {details.get('max_speed_kmh', 0):.0f} km/t.")
    if event == "weekly_summary":
        return "Tiny Family – ugeoversigt", (
            f"{name} tilbagelagde {details['distance_km']:.1f} km i sidste uge.")
    if event == "tracking_stale":
        return "Tiny Family – GPS forældet", (
            f"Der er ikke modtaget en frisk GPS-position fra {name} i "
            f"ca. {details['age_minutes']} minutter. Det kan skyldes "
            "batterisparefunktion eller manglende forbindelse.")
    if event == "tracking_restored":
        return "Tiny Family – GPS genoprettet", (
            f"Der modtages igen friske GPS-positioner fra {name}.")
    raise ValueError("Unsupported event")


async def notify_family(hass, config: dict, person: str, event: str, details: dict):
    """Explicit opt-in, no ghost sharing, only administrator-selected targets.

    Returns successful/failed destination counts; failures do not imply delivery.
    """
    if not config.get("auto_notifications_enabled", False):
        return {"sent": 0, "failed": 0, "reason": "disabled"}
    per_person = (config.get("person_notification_events") or {}).get(person)
    enabled = (per_person if per_person is not None
               else config.get("notification_events"))
    if enabled is not None and event not in enabled:
        return {"sent": 0, "failed": 0, "reason": "event_disabled"}
    if person in (config.get("ghost_people") or []):
        return {"sent": 0, "failed": 0, "reason": "ghost"}
    from .communications import check_target
    selected = config.get("persons") or []
    owners = config.get("owners") or {}
    targets = config.get("notification_targets") or {}
    if person not in selected:
        return {"sent": 0, "failed": 0, "reason": "unknown_person"}
    state = hass.states.get(person)
    name = state.name if state is not None else person
    title, body = message_for_event(event, name, details)
    services = hass.services.async_services().get("notify", {})
    entities = {s.entity_id for s in hass.states.async_all("notify")}
    sent, failed = 0, 0
    eligible = 0
    for other in selected:
        if other == person or not owners.get(other) or other in (config.get("ghost_people") or []):
            continue
        target = targets.get(other)
        if not target:
            continue
        eligible += 1
        # A removed Companion target is a failed notification, not an
        # invisible success. Report it so callers can surface the problem.
        if not check_target(target, services, entities):
            failed += 1
            continue
        service = target.removeprefix("notify.")
        try:
            if target in entities:
                await hass.services.async_call("notify", "send_message",
                    {"title": title, "message": body},
                    blocking=True, target={"entity_id": target})
            else:
                await hass.services.async_call("notify", service,
                    {"title": title, "message": body}, blocking=True)
            sent += 1
        except Exception:
            failed += 1
    return {"sent": sent, "failed": failed,
            "reason": "no_targets" if eligible == 0 else
                      "failed" if sent == 0 else
                      "partial" if failed else "accepted_by_notify",
            "push_delivery_verified": False}
