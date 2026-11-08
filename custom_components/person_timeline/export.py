"""Export only the signed-in person's Tiny Family data.

This endpoint is never available to an unlinked HA user and never reads
another person's learned locations. It does not access HA Recorder history.
"""
from __future__ import annotations

from datetime import datetime, timezone
from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .communications import own_person, private_history
from .const import DOMAIN, HISTORY_KEY, HISTORY_MAX


class TinyFamilyPersonalExportView(HomeAssistantView):
    url = "/api/tiny_family/export"
    name = "api:tiny_family:export"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    async def get(self, request):
        runtime = self.hass.data.get("tiny_family_runtime", {})
        entry = runtime.get("entry")
        if entry is None:
            return web.json_response({"message": "Not configured"}, status=503)
        config = {**entry.data, **entry.options}
        person = own_person(request["hass_user"].id, config.get("persons") or [],
                            config.get("owners") or {})
        if person is None:
            return web.json_response({"message": "Account not linked"}, status=403)
        history = self.hass.data.get(HISTORY_KEY) or {}
        state = self.hass.data.get(DOMAIN, {}).get(person) or {}
        trails = (runtime.get("routes") or {}).get(person, [])
        routines = (runtime.get("routines") or {}).get(person, [])
        result = {
            "format": "tiny-family-personal-export-v1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "person": person,
            "places": state.get("places") or [],
            "route_history_24h": trails[-2500:],
            "activity_archive": (runtime.get("activity") or {}).get(person, [])[-200:],
            "routine_observations": routines[-80:],
            "messages": private_history(history, request["hass_user"].id, HISTORY_MAX),
            "system_events": [
                {key: val for key, val in item.items()
                 if key in ("tid", "kategori", "tekst", "person")}
                for item in (history.get("system") or [])
                if item.get("person") == person
                and request["hass_user"].id not in (item.get("hidden_for") or [])
            ][-HISTORY_MAX:],
            "notice": "Personal backup only; Home Assistant Recorder is separate.",
        }
        return web.json_response(result, headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": 'attachment; filename="tiny-family-personal-export.json"',
        })
