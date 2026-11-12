"""Safe Companion textInput routing; notification tokens are short-lived capabilities.

Never resolve sender or recipient from an untrusted mobile_app event payload.
The configured user/account binding remains the authorization source.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from .communications import (
    CommunicationError, consume_reply_token, own_person,
)
from .family_actions import send_from_user

_LOGGER = logging.getLogger(__name__)


async def process_companion_reply(hass, event) -> bool:
    """Route one notification reply to its original author, when still allowed."""
    values = getattr(event, "data", {}) or {}
    now = datetime.now(timezone.utc)
    record = consume_reply_token(hass, values.get("action"), now)
    if record is None:
        return False
    reply = values.get("reply_text")
    if not isinstance(reply, str) or not (1 <= len(reply.strip()) <= 500):
        return False
    entry = hass.data.get("tiny_family_runtime", {}).get("entry")
    if entry is None:
        return False
    config = {**entry.data, **entry.options}
    persons = config.get("persons") or []
    owners = config.get("owners") or {}
    person = record["recipient_person"]
    user_id = record["recipient_user_id"]
    if (person not in persons or own_person(user_id, persons, owners) != person
            or record["sender_person"] not in persons
            or not owners.get(record["sender_person"])
            or (config.get("notification_targets") or {}).get(person) !=
               record["notification_target"]):
        return False
    try:
        await send_from_user(
            hass, config, user_id, "message", reply.strip(),
            recipient_person=record["sender_person"],
        )
    except CommunicationError:
        # Failed delivery is not a successful reply; do not include message
        # text, phone identifiers or the token in logs.
        _LOGGER.warning("Tiny Family mobile reply was rejected or not delivered")
        return False
    return True
