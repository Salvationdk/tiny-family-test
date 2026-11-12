"""Registered Tiny Family binary sensors for Companion-friendly automations."""
from __future__ import annotations

import asyncio
from functools import partial

from homeassistant.components.binary_sensor import BinarySensorEntity

from .sensors import generated_payloads


class TinyFamilyBinarySensor(BinarySensorEntity):
    """Non-polling movement, charging and trip sensors."""

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
        self._attr_is_on = None if value == "unknown" else value == "on"
        self._attr_name = attributes.get("friendly_name")
        self._attr_icon = attributes.get("icon")
        self._attr_device_class = attributes.get("device_class")
        self._attr_extra_state_attributes = {
            key: val for key, val in attributes.items()
            if key not in ("friendly_name", "icon", "device_class")
        }
        if write and getattr(self, "hass", None) is not None and getattr(self, "platform", None) is not None:
            self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities):
    config = {**entry.data, **entry.options}
    runtime = hass.data.setdefault("tiny_family_runtime", {})
    registry = runtime.setdefault("registered_entities", {})
    entities = []
    for person in config.get("persons") or []:
        for entity_id, value, attrs in generated_payloads(hass, person)[1]:
            entity = TinyFamilyBinarySensor(entity_id, value, attrs)
            registry[entity_id] = entity
            entities.append(entity)
    async_add_entities(entities)
