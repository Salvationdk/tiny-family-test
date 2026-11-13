"""Administrator-controlled erasure of routes, activities and places.

Does not alter Home Assistant Person/device_tracker or Recorder history.
Other users' chat copies and shared Home Assistant geographic zones remain.
Members may still remove their own consensual routine observations.
"""
from __future__ import annotations

from functools import partial
from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .communications import own_person
from .const import DOMAIN, PLACES_FILE
from .storage import _save_places
from .sensors import _publish
from .timeline import archive_stats, delete_archive, RETENTION_DAYS


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
        admin = bool(request["hass_user"].is_admin)
        cfg = {**entry.data, **entry.options}
        target = request.query.get("person", person)
        if not admin and (person is None or target != person):
            return web.json_response({"message": "Account not linked"}, status=403)
        if target not in (cfg.get("persons") or []):
            return web.json_response({"message": "Person not configured"}, status=404)
        state = self.hass.data.get(DOMAIN, {}).get(target) or {}
        timeline = (await self.hass.async_add_executor_job(
            archive_stats, runtime["timeline_path"], target
        )) if runtime.get("timeline_path") else {"fixes":0,"events":0}
        return web.json_response({
            "person": target,
            "routes": timeline["fixes"],
            "activities": timeline["events"],
            "timeline_retention_days": cfg.get("timeline_retention_days", RETENTION_DAYS),
            "places": len(state.get("places") or []),
            "routine_observations": len((runtime.get("routines") or {}).get(target, [])),
            "can_delete_history": admin,
            "notice": "Home Assistant Recorder history must be handled separately.",
        }, headers={"Cache-Control": "no-store"})

    async def delete(self, request):
        runtime, entry, person = self._context(request)
        if entry is None:
            return web.json_response({"message": "Not configured"}, status=503)
        admin = bool(request["hass_user"].is_admin)
        if person is None and not admin:
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
        cfg = {**entry.data, **entry.options}
        target = payload.get("person", person)
        if not admin and target != person:
            return web.json_response({"message": "Administrator required"}, status=403)
        if target not in (cfg.get("persons") or []):
            return web.json_response({"message": "Person not configured"}, status=404)
        if not admin and any(key in categories for key in ("routes", "places", "activities")):
            return web.json_response({"message": "Administrator required"}, status=403)
        person = target
        deleted = {}
        # Respect the same erasure categories as before, including the new
        # persistent SQLite history. The lock prevents a concurrent flush
        # from restoring samples the user has just deleted.
        if "routes" in categories or "activities" in categories:
            lock = runtime.get("timeline_lock")
            if lock is not None:
                async with lock:
                    if "routes" in categories:
                        runtime["timeline_pending"][:] = [
                            item for item in runtime.get("timeline_pending", ())
                            if item["person"] != person
                        ]
                        runtime.get("timeline_last_samples", {}).pop(person,None)
                    if runtime.get("timeline_path"):
                        archived=await self.hass.async_add_executor_job(partial(
                            delete_archive,runtime["timeline_path"],person,
                            routes="routes" in categories,
                            activities="activities" in categories
                        ))
                        deleted["archived_fixes"]=archived["fixes"]
                        deleted["archived_events"]=archived["events"]
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
            # Self-service deletion does not override the admin-only setting.
            # The same person may accumulate fresh observations on later trips.
        return web.json_response({
            "deleted": deleted,
            "notice": "Does not erase data stored by Home Assistant Recorder.",
        }, headers={"Cache-Control": "no-store"})
