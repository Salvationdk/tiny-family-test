"""Registered Tiny Family sensor entities preserving legacy entity IDs."""
from __future__ import annotations

import asyncio
from functools import partial

from homeassistant.components.sensor import SensorEntity

from .sensors import generated_payloads, polygon_definition_payloads


class TinyFamilySensor(SensorEntity):
    """Non-polling entity updated by Tiny Family's existing coordinator."""

    _attr_should_poll = False

    def __init__(self, entity_id, value, attributes):
        self.entity_id = entity_id
        self._attr_unique_id = entity_id
        self.update_from_payload(value, attributes, write=False)

    def update_from_payload(self, value, attributes, *, write=True):
        if getattr(self, "hass", None) is not None:
            try:
                on_loop = asyncio.get_running_loop() is self.hass.loop
            except RuntimeError:
                on_loop = False
            if not on_loop:
                self.hass.loop.call_soon_threadsafe(
                    partial(self.update_from_payload, value, attributes, write=write)
                )
                return
        unit = attributes.get("unit_of_measurement")
        # Registered numeric HA sensors cannot expose the string "None".
        # Legacy payloads were all stringified by _sensor(); use an actual
        # missing value instead of inventing an ETA or zero-speed fix.
        if unit is not None:
            if value is None or str(value).strip().lower() in (
                    "", "none", "unknown", "unavailable"):
                value = None
            else:
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    value = None
        self._attr_native_value = value
        self._attr_name = attributes.get("friendly_name")
        self._attr_icon = attributes.get("icon")
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = attributes.get("device_class")
        self._attr_state_class = attributes.get("state_class")
        self._attr_extra_state_attributes = {
            key: val for key, val in attributes.items()
            if key not in ("friendly_name", "icon", "unit_of_measurement",
                           "device_class", "state_class")
        }
        if write and getattr(self, "hass", None) is not None and getattr(self, "platform", None) is not None:
            self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities):
    config = {**entry.data, **entry.options}
    runtime = hass.data.setdefault("tiny_family_runtime", {})
    registry = runtime.setdefault("registered_entities", {})
    entities = []
    for person in config.get("persons") or []:
        for entity_id, value, attrs in generated_payloads(hass, person)[0]:
            entity = TinyFamilySensor(entity_id, value, attrs)
            registry[entity_id] = entity
            entities.append(entity)
    for entity_id, value, attrs in polygon_definition_payloads(hass):
        entity = TinyFamilySensor(entity_id, value, attrs)
        registry[entity_id] = entity
        entities.append(entity)
    async_add_entities(entities)

    async def sync_polygon_definitions():
        """Expose polygons to dashboards and third-party HA integrations live."""
        desired = {entity_id: (value, attrs)
                   for entity_id, value, attrs in polygon_definition_payloads(hass)}
        added = []
        for entity_id, (value, attrs) in desired.items():
            if entity_id not in registry:
                entity = TinyFamilySensor(entity_id, value, attrs)
                registry[entity_id] = entity
                added.append(entity)
            else:
                registry[entity_id].update_from_payload(value, attrs)
        for entity_id in list(registry):
            if entity_id.startswith("sensor.tiny_family_polygon_") and entity_id not in desired:
                entity = registry.pop(entity_id)
                await entity.async_remove()
        if added:
            async_add_entities(added)

    runtime["sync_polygon_definitions"] = sync_polygon_definitions
