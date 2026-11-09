"""Publish Home Assistant sensor states without changing entity IDs."""

import asyncio

from datetime import datetime, timezone
from .const import DOMAIN
from .places import _zone_candidates
from .companion import companion_readings
from .utils import _pretty, _sensor, _slug


def generated_payloads(hass, person):
    st = hass.data[DOMAIN][person]
    slug = _slug(person)
    name = _pretty(person)
    dist = round(st["distance_m"] / 1000, 1)
    # Avoid publishing GPS place coordinates to HA-wide state attributes
    # while this person has enabled Ghost Mode inside Tiny Family.
    ghost = person in hass.data.get("tiny_family_runtime", {}).get("ghost_people", set())
    companion = companion_readings(
        hass, charging_entity=st.get("charging_entity"),
        activity_entity=st.get("activity_entity"),
    )
    sensors = [
        _sensor(f"sensor.person_timeline_{slug}_distance_today", dist,
                {"unit_of_measurement": "km", "device_class": "distance",
                 "state_class": "total", "friendly_name": f"{name} distance i dag"}),
        _sensor(f"sensor.person_timeline_{slug}_stays_today", st["stays"],
                {"unit_of_measurement": "ophold", "state_class": "total",
                 "friendly_name": f"{name} ophold i dag"}),
        _sensor(f"sensor.person_timeline_{slug}_current_stay", st["current_stay_min"],
                {"unit_of_measurement": "min", "friendly_name": f"{name} aktuelt ophold"}),
        _sensor(f"sensor.person_timeline_{slug}_max_speed", round(st["max_speed"] * 3.6, 0),
                {"unit_of_measurement": "km/h", "device_class": "speed",
                 "friendly_name": f"{name} max fart i dag"}),
        _sensor(f"sensor.person_timeline_{slug}_distance_week", round(st["distance_week_m"] / 1000, 1),
                {"unit_of_measurement": "km", "device_class": "distance",
                 "state_class": "total", "friendly_name": f"{name} distance i ugen"}),
        _sensor(f"sensor.person_timeline_{slug}_last_trip", st.get("last_trip", "Ingen ture endnu"),
                {"friendly_name": f"{name} sidste tur"}),
        _sensor(f"sensor.person_timeline_{slug}_destination",
                "Privat" if ghost else (st.get("destination") or "Ingen"),
                {"icon": "mdi:map-marker-question",
                 "friendly_name": f"{name} mulig destination",
                 "confidence": 0.0 if ghost else st.get("destination_confidence", 0.0)}),
        _sensor(f"sensor.person_timeline_{slug}_destination_confidence",
                0 if ghost else round(st.get("destination_confidence", 0.0) * 100),
                {"unit_of_measurement": "%",
                 "friendly_name": f"{name} destinationssikkerhed",
                 "icon": "mdi:chart-bell-curve-cumulative"}),
        _sensor(f"sensor.person_timeline_{slug}_destination_eta",
                0 if ghost else int(st.get("dest_eta_min") or 0),
                {"unit_of_measurement": "min", "icon": "mdi:timer-sand",
                 "friendly_name": f"{name} ETA til destination"}),
        _sensor(f"sensor.person_timeline_{slug}_destination_afstand",
                0 if ghost else round((st.get("dest_dist_m") or 0) / 1000, 1),
                {"unit_of_measurement": "km", "device_class": "distance",
                 "friendly_name": f"{name} afstand til destination"}),
        _sensor(f"sensor.person_timeline_{slug}_home_eta",
                None if ghost else st.get("home_eta_min"),
                {"unit_of_measurement": "min", "icon": "mdi:home-clock",
                 "friendly_name": f"{name} anslået tid til hjemmet"}),
        _sensor(f"sensor.person_timeline_{slug}_activity",
                companion["activity"],
                {"friendly_name": f"{name} telefonaktivitet",
                 "icon": "mdi:motion-sensor", "person": person}),
        _sensor(f"sensor.person_timeline_{slug}_movement",
                st.get("movement_state", "unknown"),
                {"friendly_name": f"{name} bevægelse",
                 "icon": "mdi:walk", "person": person}),
        _sensor(f"sensor.person_timeline_{slug}_current_speed",
                st.get("speed_kmh", 0.0),
                {"friendly_name": f"{name} aktuel hastighed",
                 "unit_of_measurement": "km/h", "device_class": "speed",
                 "person": person}),
        _sensor(f"sensor.person_timeline_{slug}_gps_health",
                st.get("gps_health", "unknown"),
                {"friendly_name": f"{name} GPS-datakvalitet",
                 "icon": "mdi:crosshairs-question", "person": person}),
        _sensor(f"sensor.person_timeline_{slug}_gps_age_minutes",
                (round(max(0, datetime.now(tz=timezone.utc).timestamp() -
                           st["gps_seen_at"]) / 60)
                 if st.get("gps_seen_at") is not None else None),
                {"friendly_name": f"{name} minutter siden GPS-fix",
                 "unit_of_measurement": "min", "icon": "mdi:clock-alert-outline",
                 "person": person}),
        _sensor(f"sensor.person_timeline_{slug}_usual_departure",
                st.get("usual_departure") or "unknown",
                {"friendly_name": f"{name} typisk afgang",
                 "icon": "mdi:clock-outline",
                 "confidence": st.get("routine_confidence",0)}),
        _sensor(f"sensor.person_timeline_{slug}_kendte_steder", len(st.get("places") or []),
                {"friendly_name": f"{name} kendte steder",
                 "zone_forslag": [],
                 "zone_forslag_antal": (0 if ghost else len(
                     _zone_candidates(hass, st.get("places"))))}),
    ]
    moving = st.get("movement_state", "unknown")
    binary_sensors = [
        (f"binary_sensor.person_timeline_{slug}_charging", companion["charging"],
         {"friendly_name": f"{name} oplader", "person": person,
          "device_class": "battery_charging"}),
        (f"binary_sensor.person_timeline_{slug}_moving",
         "unknown" if moving == "unknown" else ("on" if moving == "moving" else "off"),
         {"friendly_name": f"{name} i bevægelse", "person": person,
          "icon": "mdi:walk"}),
        (f"binary_sensor.person_timeline_{slug}_on_trip",
         ("unknown" if st.get("gps_health", "fresh") not in ("fresh",)
          else ("on" if st.get("trip_active") else "off")),
         {"friendly_name": f"{name} på tur", "person": person,
          "icon": "mdi:car"}),
    ]
    return sensors, binary_sensors


def _publish(hass, person):
    """Publish on HA's event loop even if a caller runs in a worker thread."""
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    if current_loop is not hass.loop:
        # Schedule the complete state read/update on HA's loop. Scheduling
        # only the final write would still mutate entities off-thread.
        hass.loop.call_soon_threadsafe(_publish, hass, person)
        return
    readings = generated_payloads(hass, person)
    entities = hass.data.get("tiny_family_runtime", {}).get("registered_entities", {})
    for entity_id, value, attributes in (*readings[0], *readings[1]):
        entity = entities.get(entity_id)
        if entity is None:
            hass.states.async_set(entity_id, value, attributes)
        else:
            entity.update_from_payload(value, attributes)


GENERATED_SENSORS = (
    "distance_today", "stays_today", "current_stay", "max_speed",
    "distance_week", "last_trip", "destination", "destination_confidence",
    "destination_eta", "home_eta",
    "destination_afstand", "activity", "movement", "current_speed",
    "usual_departure", "kendte_steder", "gps_health", "gps_age_minutes",
)
GENERATED_BINARY_SENSORS = ("charging", "moving", "on_trip")


def remove_generated_states(hass, people):
    """Clean manually published states when the integration is unloaded."""
    for person in people:
        slug = _slug(person)
        for suffix in GENERATED_SENSORS:
            hass.states.async_remove(f"sensor.person_timeline_{slug}_{suffix}")
        for suffix in GENERATED_BINARY_SENSORS:
            hass.states.async_remove(f"binary_sensor.person_timeline_{slug}_{suffix}")
    for name in ("sensor.person_timeline_beskeder",
                 "sensor.person_timeline_systembeskeder"):
        hass.states.async_remove(name)
