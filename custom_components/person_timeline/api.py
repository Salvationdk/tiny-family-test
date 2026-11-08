"""Authenticated per-user family communications; no sender impersonation."""
from __future__ import annotations

from aiohttp import web
from datetime import datetime, timezone
from secrets import token_urlsafe
from homeassistant.components.http import HomeAssistantView

from .communications import (CommunicationError, acknowledge_message, deliver,
                             own_person, private_history)
from .const import HISTORY_FILE, HISTORY_KEY
from .storage import _append_history, _save_history

RUNTIME_KEY = "tiny_family_runtime"


class TinyFamilyCommunicationsView(HomeAssistantView):
    """Actions and history are scoped to the logged-in Home Assistant user."""

    url = "/api/tiny_family/communications"
    name = "api:tiny_family:communications"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    def _context(self, request):
        entry = self.hass.data.get(RUNTIME_KEY, {}).get("entry")
        if entry is None:
            raise CommunicationError("Tiny Family is not configured")
        config = {**entry.data, **entry.options}
        user_id = request["hass_user"].id
        person = own_person(user_id, config.get("persons") or [],
                            config.get("owners") or {})
        if person is None:
            raise CommunicationError("No person is linked to this Home Assistant user", code="not_linked")
        return config, user_id, person

    async def get(self, request):
        try:
            config, user_id, person = self._context(request)
        except CommunicationError as err:
            return web.json_response({"message": str(err), "error_code": err.code}, status=403)
        targets = config.get("notification_targets") or {}
        owners = config.get("owners") or {}
        recipients = sum(1 for other in config.get("persons") or []
                         if other != person and owners.get(other) and targets.get(other))
        return web.json_response({
            "person": person, "recipients_configured": recipients,
            "recipients": [
                {"person": other, "name": (
                    self.hass.states.get(other).name
                    if self.hass.states.get(other) else other)}
                for other in config.get("persons") or []
                if other != person and owners.get(other) and targets.get(other)
            ],
            "history": private_history(self.hass.data.get(HISTORY_KEY) or {}, user_id),
        }, headers={"Cache-Control": "no-store"})

    async def delete(self, request):
        """Hide this user's messages only; do not delete other users' copies."""
        try:
            _, user_id, _ = self._context(request)
        except CommunicationError as err:
            return web.json_response({"message":str(err),"error_code":err.code},status=403)
        hist=self.hass.data.get(HISTORY_KEY) or {}
        count=0
        for item in hist.get("chat",[]):
            if (item.get("sender_user_id")==user_id or
                    user_id in (item.get("recipient_user_ids") or [])):
                already=set(item.get("hidden_for") or [])
                if user_id not in already:
                    already.add(user_id)
                    item["hidden_for"]=sorted(already)
                    count+=1
        await self.hass.async_add_executor_job(
            _save_history,self.hass.config.path(HISTORY_FILE),hist)
        return web.json_response({"hidden":count},headers={"Cache-Control":"no-store"})

    async def post(self, request):
        try:
            config, user_id, person = self._context(request)
            payload = await request.json()
            if not isinstance(payload, dict):
                raise CommunicationError("Invalid action payload")
            action = payload.get("action")
            if action == "acknowledge":
                history = self.hass.data.get(HISTORY_KEY) or {}
                changed = acknowledge_message(
                    history, user_id, payload.get("message_id"),
                    datetime.now(timezone.utc),
                )
                if changed:
                    await self.hass.async_add_executor_job(
                        _save_history, self.hass.config.path(HISTORY_FILE), history
                    )
                return web.json_response({"status": "read", "updated": changed},
                                         headers={"Cache-Control": "no-store"})
            message = payload.get("message", "")
            recipient_person = payload.get("recipient_person")
            include_location = payload.get("include_location", True)
            if type(include_location) is not bool:
                raise CommunicationError("Invalid location option")
            if (not isinstance(action, str) or not isinstance(message, str)
                    or (recipient_person is not None
                        and not isinstance(recipient_person, str))):
                raise CommunicationError("Invalid action or message")
            result = await deliver(
                self.hass, sender_user_id=user_id, sender_person=person,
                config=config, action=action, message=message,
                recipient_person=recipient_person, include_location=include_location,
            )
        except CommunicationError as err:
            return web.json_response({"message": str(err), "error_code": err.code}, status=400)
        except (ValueError, TypeError):
            return web.json_response({"message": "Invalid request"}, status=400)
        _append_history(self.hass, self.hass.config.path(HISTORY_FILE), "chat", {
            "id": token_urlsafe(12), "read_at": {},
            "tid": result["tid"], "kategori": result["action"],
            "fra": result["sender_person"], "til": ", ".join(result["recipient_people"]),
            "tekst": result["message"],
            "sender_user_id": result["sender_user_id"],
            "recipient_user_ids": result["recipient_user_ids"],
            "status": "sent" if not result["recipients_failed"] else "partial",
            "accepted_recipients": result["recipients_sent"],
            "failed_recipients": result["recipients_failed"],
            "delivery_state": result["delivery_state"],
            "location_status": result["location_status"],
        })
        self.hass.bus.async_fire("tiny_family_communication_sent", {
            "action": result["action"], "person": person,
            "recipients_sent": result["recipients_sent"],
            "recipients_failed": result["recipients_failed"],
        })
        return web.json_response({
            "status": "sent" if not result["recipients_failed"] else "partial",
            "recipients_sent": result["recipients_sent"],
            "recipients_failed": result["recipients_failed"],
            "attempted_recipients": result["attempted_recipients"],
            "delivery_state": result["delivery_state"],
            "push_delivery_verified": result["push_delivery_verified"],
            "location_status": result["location_status"],
        }, headers={"Cache-Control": "no-store"})
