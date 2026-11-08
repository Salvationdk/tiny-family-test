"""Self-service erasure of Tiny Family's locally learned personal data.

Does not alter Home Assistant Person/device_tracker or Recorder history.
Other users' chat copies and shared Home Assistant geographic zones remain.
"""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .communications import own_person
from .const import DOMAIN, PLACES_FILE
from .storage import _save_places
from .sensors import _publish


class TinyFamilyPersonalDataView(HomeAssistantView):
    url = "/api/tiny_family/personal_data"
    name = "api:tiny_family:personal_data"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    def _context(self, request):
        runtime = self.hass.data.get("tiny_family_runtime", {})
        entry = runtime.get("entry")
        if entry is None:
            return None, None, None
        cfg = {**entry.data, **entry.options}
        person = own_person(request["hass_user"].id, cfg.get("persons") or [],
                            cfg.get("owners") or {})
        return runtime, entry, person

    async def get(self, request):
        runtime, entry, person = self._context(request)
        if entry is None:
            return web.json_response({"message": "Not configured"}, status=503)
        if person is None:
            return web.json_response({"message": "Account not linked"}, status=403)
        state = self.hass.data.get(DOMAIN, {}).get(person) or {}
        return web.json_response({
            "person": person,
            "routes": len((runtime.get("routes") or {}).get(person, [])),
            "activities": len((runtime.get("activity") or {}).get(person, [])),
            "places": len(state.get("places") or []),
            "routine_observations": len((runtime.get("routines") or {}).get(person, [])),
            "notice": "Home Assistant Recorder history must be handled separately.",
        }, headers={"Cache-Control": "no-store"})

    async def delete(self, request):
        runtime, entry, person = self._context(request)
        if entry is None:
            return web.json_response({"message": "Not configured"}, status=503)
        if person is None:
            return web.json_response({"message": "Account not linked"}, status=403)
        try:
            payload = await request.json()
            categories = payload.get("categories")
            if (payload.get("confirm") is not True
                    or not isinstance(categories, list)
                    or not categories or len(set(categories)) != len(categories)
                    or any(category not in ("routes", "places", "routines", "activities")
                           for category in categories)):
                raise ValueError("Confirm one or more valid categories")
        except (ValueError, TypeError, AttributeError):
            return web.json_response({"message": "Confirmation and categories required"}, status=400)
        deleted = {}
        if "routes" in categories:
            routes = runtime.get("routes") or {}
            deleted["routes"] = len(routes.pop(person, []))
            await self.hass.async_add_executor_job(
                _save_places, self.hass.config.path("tiny_family_routes.json"), routes,
            )
        if "activities" in categories:
            activity = runtime.get("activity") or {}
            deleted["activities"] = len(activity.pop(person, []))
            await self.hass.async_add_executor_job(
                _save_places, self.hass.config.path("tiny_family_activity.json"),
                activity,
            )
        if "places" in categories:
            state = self.hass.data.get(DOMAIN, {}).get(person)
            if state is None:
                return web.json_response({"message": "Person runtime unavailable"}, status=503)
            deleted["places"] = len(state.get("places") or [])
            state["places"] = []
            state["seeded"] = False
            # Preserve other family members' saved places on disk.
            all_places = {
                p: st.get("places") or []
                for p, st in self.hass.data.get(DOMAIN, {}).items()
            }
            await self.hass.async_add_executor_job(
                _save_places, self.hass.config.path(PLACES_FILE), all_places,
            )
            _publish(self.hass, person)
        if "routines" in categories:
            routines = runtime.get("routines") or {}
            deleted["routines"] = len(routines.pop(person, []))
            await self.hass.async_add_executor_job(
                _save_places,
                self.hass.config.path("tiny_family_routines.json"), routines,
            )
            state = self.hass.data.get(DOMAIN, {}).get(person)
            if state is not None:
                state["usual_departure"] = None
                state["routine_confidence"] = 0
                _publish(self.hass, person)
            active = set(entry.options.get("routine_learning_people") or [])
            if person in active:
                active.discard(person)
                self.hass.config_entries.async_update_entry(entry, options={
                    **entry.options, "routine_learning_people": sorted(active),
                })
        return web.json_response({
            "deleted": deleted,
            "notice": "Does not erase data stored by Home Assistant Recorder.",
        }, headers={"Cache-Control": "no-store"})
