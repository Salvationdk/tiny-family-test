"""Single account-bound implementation for panel, iOS and Android Companion actions."""
from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_urlsafe

from .communications import CommunicationError, deliver, own_person
from .const import HISTORY_FILE, HISTORY_KEY
from .storage import _append_history


async def send_from_user(hass, config: dict, user_id: str, action: str,
                         message: str = "",
                         recipient_person: str | None = None) -> dict:
    """Send as the authenticated HA user; no caller-controlled person or target."""
    person=own_person(user_id,config.get("persons") or [],config.get("owners") or {})
    if person is None:
        raise CommunicationError("This HA user is not assigned to a Tiny Family person")
    result=await deliver(hass,sender_user_id=user_id,sender_person=person,
                         config=config,action=action,message=message,
                         recipient_person=recipient_person)
    _append_history(hass,hass.config.path(HISTORY_FILE),"chat",{
        "id":token_urlsafe(12),"read_at":{},
        "tid":result["tid"],"kategori":result["action"],
        "fra":result["sender_person"],"til":", ".join(result["recipient_people"]),
        "tekst":result["message"],"sender_user_id":result["sender_user_id"],
        "recipient_user_ids":result["recipient_user_ids"],
        "status":"sent" if not result["recipients_failed"] else "partial",
    })
    hass.bus.async_fire("tiny_family_communication_sent",{
        "person":person,"action":result["action"],
        "recipients_sent":result["recipients_sent"],
        "recipients_failed":result["recipients_failed"],
    })
    return {"status":"sent" if not result["recipients_failed"] else "partial",
            "recipients_sent":result["recipients_sent"],
            "recipients_failed":result["recipients_failed"]}
