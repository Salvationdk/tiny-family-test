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
    """Select members, then associate each with one phone and optional speaker."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TinyFamilyOptionsFlow()

    def _create_family_entry(self):
        return self.async_create_entry(title="Tiny Family", data={
            "persons": list(self._setup_persons),
            "trackers": dict(self._setup_trackers),
            "smart_speakers": dict(self._setup_speakers),
            "batteries": {},
            "charging_sensors": {},
            "activity_sensors": {},
            "notification_events": sorted((
                "zone_arrived", "zone_departed", "battery_low",
                "speed_warning", "trip_ended", "weekly_summary",
            )),
            "colors": {},
            "learn_routines_enabled": False,
            "routine_learning_people": [],
            "owners": dict(self._setup_owners),
            "notification_targets": {},
            "speed_limit_kmh": 130,
            "speed_limits_kmh": {},
            "person_notification_events": {},
            "ghost_allowed_people": [],
        })

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            self._setup_persons = list(dict.fromkeys(user_input.get("persons") or []))
            self._setup_trackers = {}
            self._setup_speakers = {}
            self._setup_owners = {}
            self._setup_index = 0
            if not self._setup_persons:
                return self._create_family_entry()
            return await self.async_step_member()
        return self.async_show_form(step_id="user", data_schema=_person_selector())

    async def async_step_member(self, user_input=None):
        """One step per person keeps the phone/speaker pairing unambiguous."""
        if not getattr(self, "_setup_persons", None):
            return await self.async_step_user()

        person = self._setup_persons[self._setup_index]
        errors = {}
        if user_input is not None:
            tracker = user_input.get("tracker")
            speaker = user_input.get("speaker")
            owner = user_input.get("owner")
            if tracker and tracker in self._setup_trackers.values():
                errors["tracker"] = "already_assigned"
            if owner and owner in self._setup_owners.values():
                errors["owner"] = "already_assigned"
            if not errors:
                if tracker:
                    self._setup_trackers[person] = tracker
                if speaker:
                    self._setup_speakers[person] = speaker
                if owner:
                    self._setup_owners[person] = owner
                self._setup_index += 1
                if self._setup_index == len(self._setup_persons):
                    return self._create_family_entry()
                return await self.async_step_member()

        schema = {
            vol.Optional("tracker"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="device_tracker"),
            ),
            vol.Optional("speaker"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="media_player"),
            ),
        }
        users = [user for user in await self.hass.auth.async_get_users()
                 if user.is_active]
        if users:
            schema[vol.Optional("owner")] = vol.In({
                user.id: user.name or user.id for user in users
            })
        state = self.hass.states.get(person)
        person_name = state.name if state is not None else person
        return self.async_show_form(
            step_id="member",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "person": person_name,
                "number": str(self._setup_index + 1),
                "total": str(len(self._setup_persons)),
            },
            errors=errors,
            last_step=self._setup_index == len(self._setup_persons) - 1,
        )


class TinyFamilyOptionsFlow(config_entries.OptionsFlow):
    """Manage persons with Home Assistant's own entity picker."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            persons = list(user_input.get("persons") or [])
            options = dict(self.config_entry.options)
            options.update({
                "persons": persons,
                "trackers": {k: v for k, v in options.get("trackers", {}).items() if k in persons},
                "smart_speakers": {k: v for k, v in options.get("smart_speakers", {}).items() if k in persons},
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
