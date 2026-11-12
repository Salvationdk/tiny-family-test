"""Authenticated system-event history, filtered by owner and Ghost sharing."""
from __future__ import annotations
from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .communications import own_person
from .const import HISTORY_FILE, HISTORY_KEY
from .storage import _save_history


def visible_system_events(events, person: str, config: dict, user_id: str, limit=200):
    selected=set(config.get("persons") or [])
    ghosts=set(config.get("ghost_people") or [])
    allowed=selected - ghosts
    allowed.add(person)  # A person can always review their own system events.
    return [
        {key: value for key,value in event.items()
         if key in ("tid","kategori","tekst","person","event_key")}
        for event in reversed(events)
        if event.get("person") in allowed
        and user_id not in (event.get("hidden_for") or [])
    ][:limit]


class TinyFamilyHistoryView(HomeAssistantView):
    url="/api/tiny_family/history"
    name="api:tiny_family:history"
    requires_auth=True

    def __init__(self,hass):
        self.hass=hass

    def _context(self,request):
        entry=self.hass.data.get("tiny_family_runtime",{}).get("entry")
        if entry is None:return None,None
        cfg={**entry.data,**entry.options}
        own=own_person(request["hass_user"].id,
                       cfg.get("persons") or [],cfg.get("owners") or {})
        return cfg,own

    async def get(self,request):
        cfg,person=self._context(request)
        if person is None:
            return web.json_response({"message":"Account not linked"},status=403)
        user=request["hass_user"].id
        history=(self.hass.data.get(HISTORY_KEY) or {}).get("system") or []
        return web.json_response({
            "entries":visible_system_events(history,person,cfg,user)
        },headers={"Cache-Control":"no-store"})

    async def delete(self,request):
        cfg,person=self._context(request)
        if person is None:
            return web.json_response({"message":"Account not linked"},status=403)
        user=request["hass_user"].id
        history=self.hass.data.get(HISTORY_KEY) or {}
        changed=0
        for item in history.get("system",[]):
            if item.get("person") not in set(cfg.get("persons") or []):
                continue
            if item.get("person") in (cfg.get("ghost_people") or []) and item.get("person")!=person:
                continue
            hidden=set(item.get("hidden_for") or [])
            if user not in hidden:
                hidden.add(user)
                item["hidden_for"]=sorted(hidden)
                changed+=1
        await self.hass.async_add_executor_job(
            _save_history,self.hass.config.path(HISTORY_FILE),history)
        return web.json_response({"hidden":changed},headers={"Cache-Control":"no-store"})
