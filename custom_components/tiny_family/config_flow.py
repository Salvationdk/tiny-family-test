"""UI-first configuration; no Lovelace dashboard or YAML required."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN


def _person_selector(default=None):
    return vol.Schema({
        vol.Optional("persons", default=default or []):
            selector.EntitySelector(selector.EntitySelectorConfig(
                domain="person", multiple=True,
            )),
    })


class TinyFamilyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TinyFamilyOptionsFlow()

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Tiny Family", data={
                "persons": list(user_input.get("persons") or []),
                "trackers": {},
                "batteries": {},
                "charging_sensors": {},
                "activity_sensors": {},
                "notification_events": sorted((
                    "zone_arrived","zone_departed","battery_low",
                    "speed_warning","trip_ended","weekly_summary",
                )),
                "colors": {},
                "learn_routines_enabled": False,
                "routine_learning_people": [],
                "owners": {},
                "notification_targets": {},
                "speed_limit_kmh": 130,
                "speed_limits_kmh": {},
                "person_notification_events": {},
                "ghost_allowed_people": [],
            })
        return self.async_show_form(step_id="user", data_schema=_person_selector())


class TinyFamilyOptionsFlow(config_entries.OptionsFlow):
    """Manage persons with Home Assistant's own entity picker."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            persons = list(user_input.get("persons") or [])
            options = dict(self.config_entry.options)
            options.update({
                "persons": persons,
                "trackers": {k: v for k, v in options.get("trackers", {}).items() if k in persons},
                "batteries": {k: v for k, v in options.get("batteries", {}).items() if k in persons},
                "charging_sensors": {k: v for k, v in options.get("charging_sensors", {}).items() if k in persons},
                "activity_sensors": {k: v for k, v in options.get("activity_sensors", {}).items() if k in persons},
                "colors": {k: v for k, v in options.get("colors", {}).items() if k in persons},
                "speed_limits_kmh": {k: v for k, v in options.get("speed_limits_kmh", {}).items() if k in persons},
                "person_notification_events": {
                    k: v for k, v in options.get("person_notification_events", {}).items()
                    if k in persons
                },
                "owners": {k: v for k, v in options.get("owners", {}).items() if k in persons},
                "notification_targets": {k: v for k, v in options.get("notification_targets", {}).items() if k in persons},
                "ghost_allowed_people": [
                    p for p in options.get("ghost_allowed_people", options.get("ghost_people", []))
                    if p in persons
                ],
                "ghost_people": [p for p in options.get("ghost_people", []) if p in persons
                                 and p in options.get("ghost_allowed_people", options.get("ghost_people", []))],
            })
            return self.async_create_entry(title="", data=options)
        current = self.config_entry.options.get("persons",
                   self.config_entry.data.get("persons", []))
        return self.async_show_form(step_id="init", data_schema=_person_selector(current))
