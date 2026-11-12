"""Consent-based Companion notifications and private message history.

This module deliberately does not provide a generic notification service.
User identity is always resolved from HA's authenticated request context and
the administrator's explicit person-to-user assignment.
"""
from __future__ import annotations

import math
from secrets import token_urlsafe
from datetime import datetime, timezone

from .utils import _hav

ACTIONS = frozenset(("checkin", "heading_home", "sos", "message"))
MAX_MESSAGE_LENGTH = 500
MAX_POSITION_AGE_SECONDS = 15 * 60
REPLY_PREFIX = "TF_REPLY_"
REPLY_TTL_SECONDS = 24 * 3600
MAX_PENDING_REPLIES = 200


def pending_reply_tokens(hass, now: datetime) -> dict:
    """Bound short-lived, unpersisted capability tokens used by Companion replies."""
    tokens = hass.data.setdefault("tiny_family_reply_tokens", {})
    now_ts = now.timestamp()
    for key, item in list(tokens.items()):
        if not isinstance(item, dict) or item.get("expires", 0) <= now_ts:
            tokens.pop(key, None)
    if len(tokens) >= MAX_PENDING_REPLIES:
        for key, _ in sorted(tokens.items(), key=lambda pair: pair[1]["expires"])[
            :len(tokens) - MAX_PENDING_REPLIES + 1
        ]:
            tokens.pop(key, None)
    return tokens


def consume_reply_token(hass, action: str, now: datetime) -> dict | None:
    """Treat a unique notification action as a one-use, expiring capability."""
    if not isinstance(action, str) or not action.startswith(REPLY_PREFIX):
        return None
    tokens = hass.data.get("tiny_family_reply_tokens", {})
    record = tokens.pop(action[len(REPLY_PREFIX):], None)
    if not isinstance(record, dict) or record.get("expires", 0) <= now.timestamp():
        return None
    return record


class CommunicationError(ValueError):
    """Communication failure with a stable code for translated UI messages."""

    def __init__(self, message: str, *, code: str = "invalid_action"):
        super().__init__(message)
        self.code = code


def own_person(user_id: str, persons: list[str], owners: dict) -> str | None:
    """Find the exact Person entity associated with a logged-in HA user."""
    return next((person for person in persons if owners.get(person) == user_id), None)


def check_target(target: str, services: dict, notify_entities: set[str]) -> bool:
    """Allow only active mobile-app notification services or notify entities."""
    if not isinstance(target, str) or not target.startswith("notify."):
        return False
    name = target.removeprefix("notify.")
    return (name.startswith("mobile_app_") and name in services) or (
        target in notify_entities and "send_message" in services
    )


def current_location(person_state, now: datetime) -> tuple[float, float] | None:
    """Return a non-stale, finite position; never silently reuse an old fix."""
    if person_state is None:
        return None
    age = (now - person_state.last_updated).total_seconds()
    if not (0 <= age <= MAX_POSITION_AGE_SECONDS):
        return None
    attributes = person_state.attributes
    try:
        lat, lon = float(attributes["latitude"]), float(attributes["longitude"])
    except (KeyError, ValueError, TypeError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90
            and -180 <= lon <= 180):
        return None
    return lat, lon


def compose_message(action: str, name: str, text: str, location,
                    home_location, speed_kmh: float) -> tuple[str, str]:
    """Create text and subject for explicit user-initiated actions."""
    if action not in ACTIONS:
        raise CommunicationError("Unknown action")
    if action == "message":
        if not text or len(text) > MAX_MESSAGE_LENGTH:
            raise CommunicationError("Message must contain 1 to 500 characters")
        return "Tiny Family – besked", f"{name}: {text}"
    if action == "sos":
        title, body = "Tiny Family – SOS", f"SOS fra {name}. Personen beder om hjælp."
    elif action == "checkin":
        title, body = "Tiny Family – check-in", f"{name} har meldt: Jeg er okay."
    else:
        title, body = "Tiny Family – på vej hjem", f"{name} har meldt: Jeg er på vej hjem."
        if location and home_location and 3 <= speed_kmh <= 130:
            distance_km = _hav(*location, *home_location) / 1000
            if 0 < distance_km <= 500:
                minutes = round(distance_km / speed_kmh * 60)
                if 1 <= minutes <= 600:
                    body += f" Anslået ETA: ca. {minutes} min."
    if location:
        lat, lon = location
        body += (f" Position: https://www.google.com/maps/search/"
                 f"?api=1&query={lat:.6f}%2C{lon:.6f}")
    else:
        body += " Aktuel position er ikke tilgængelig."
    return title, body


def private_history(history: dict, user_id: str, limit: int = 50) -> list[dict]:
    """Return account-scoped messages and non-identifying panel read receipts."""
    allowed = []
    for item in history.get("chat", []):
        if user_id in (item.get("hidden_for") or []):
            continue
        recipients = item.get("recipient_user_ids") or []
        if item.get("sender_user_id") != user_id and user_id not in recipients:
            continue
        clean = {k: v for k, v in item.items()
                 if k in ("id", "tid", "fra", "til", "tekst", "kategori", "status",
                          "accepted_recipients", "failed_recipients",
                          "delivery_state", "location_status")}
        reads = item.get("read_at") or {}
        if not isinstance(reads, dict):
            reads = {}
        clean["read_by_me"] = user_id in reads
        if item.get("sender_user_id") == user_id:
            clean["read_count"] = sum(uid in reads for uid in recipients)
            clean["recipient_count"] = len(recipients)
        allowed.append(clean)
    return list(reversed(allowed))[:limit]


def acknowledge_message(history: dict, user_id: str, message_id: str,
                        now: datetime) -> bool:
    """Mark *one addressed message* as read in Tiny Family, never a push receipt.

    Returns False for an already acknowledged message, for idempotent retries.
    """
    if not isinstance(message_id, str) or not (1 <= len(message_id) <= 64):
        raise CommunicationError("Invalid message ID")
    for item in history.get("chat", []):
        if item.get("id") != message_id:
            continue
        if (user_id not in (item.get("recipient_user_ids") or []) or
                user_id in (item.get("hidden_for") or [])):
            raise CommunicationError("Not a permitted recipient")
        reads = item.setdefault("read_at", {})
        if not isinstance(reads, dict):
            raise CommunicationError("Invalid receipt record")
        if user_id in reads:
            return False
        reads[user_id] = now.astimezone(timezone.utc).isoformat()
        return True
    raise CommunicationError("Unknown message")


def danish_tts_language(tts_state) -> str:
    """Choose a Danish language code supported by the configured TTS engine."""
    attrs = getattr(tts_state, "attributes", {}) or {}
    languages = attrs.get("supported_languages")
    if isinstance(languages, (list, tuple, set)) and languages:
        for language in languages:
            if isinstance(language, str) and language.lower().replace("_", "-").startswith("da"):
                return language
        raise CommunicationError("Den valgte TTS-stemme understøtter ikke dansk",
                                 code="danish_not_supported")
    # Some HA TTS engines do not publish supported_languages in entity state.
    # Try Danish; a rejecting engine returns an error instead of using English.
    return "da"


async def deliver_spoken(hass, *, sender_user_id: str, sender_person: str,
                         config: dict, recipient_person: str | None,
                         message: str) -> dict:
    """Play an explicitly selected direct message on the recipient's speaker.

    TTS is never used for SOS or automatic alerts; no GPS location is spoken.
    Speaker/engine mappings are administrator-owned, not supplied by the caller.
    """
    persons = config.get("persons") or []
    owners = config.get("owners") or {}
    if (sender_person not in persons or
            owners.get(sender_person) != sender_user_id):
        raise CommunicationError("Du er ikke knyttet til afsenderen", code="not_linked")
    if (not isinstance(recipient_person, str) or
            recipient_person not in persons or recipient_person == sender_person or
            not owners.get(recipient_person)):
        raise CommunicationError("Vælg én anden familiemodtager", code="invalid_recipient")
    if not isinstance(message, str) or not (1 <= len(message.strip()) <= 250):
        raise CommunicationError("Oplæsning skal indeholde 1–250 tegn", code="invalid_action")
    speaker = (config.get("smart_speakers") or {}).get(recipient_person)
    engine = (config.get("tts_engines") or {}).get(recipient_person)
    if (not isinstance(speaker, str) or not speaker.startswith("media_player.") or
            not isinstance(engine, str) or not engine.startswith("tts.")):
        raise CommunicationError("Modtageren mangler højttaler eller dansk TTS",
                                 code="speaker_not_configured")
    speaker_state = hass.states.get(speaker)
    engine_state = hass.states.get(engine)
    if (speaker_state is None or speaker_state.state in ("unknown", "unavailable") or
            engine_state is None or engine_state.state == "unavailable" or
            "speak" not in hass.services.async_services().get("tts", {})):
        raise CommunicationError("Højttaler eller TTS er ikke tilgængelig",
                                 code="speaker_unavailable")
    language = danish_tts_language(engine_state)
    now = datetime.now(timezone.utc)
    ledger = hass.data.setdefault("tiny_family_action_limits", {})
    key = (sender_user_id, "speaker", recipient_person)
    previous = ledger.get(key)
    if previous is not None and now.timestamp() - previous < 10:
        raise CommunicationError("Vent lidt før næste oplæsning", code="rate_limited")
    ledger[key] = now.timestamp()
    sender_state = hass.states.get(sender_person)
    name = sender_state.name if sender_state is not None else sender_person
    clean_message = message.strip()
    try:
        await hass.services.async_call(
            "tts", "speak",
            {
                "media_player_entity_id": speaker,
                "message": f"Tiny Family. Besked fra {name}. {clean_message}",
                "language": language,
            },
            target={"entity_id": engine}, blocking=True,
        )
    except Exception as err:
        ledger.pop(key, None)
        raise CommunicationError("Home Assistant kunne ikke starte oplæsning",
                                 code="tts_failed") from err
    return {
        "action": "message", "title": "Tiny Family – oplæst besked",
        "message": clean_message,
        "sender_user_id": sender_user_id,
        "sender_person": sender_person,
        "recipient_people": [recipient_person],
        "recipient_user_ids": [owners[recipient_person]],
        "recipients_sent": 1, "recipients_failed": 0,
        "attempted_recipients": 1,
        "delivery_state": "accepted_by_tts",
        "delivery_channel": "speaker",
        "push_delivery_verified": False,
        "location_status": "not_applicable",
        "tid": now.isoformat(),
    }


async def deliver(hass, *, sender_user_id: str, sender_person: str,
                  config: dict, action: str, message: str = "",
                  recipient_person: str | None = None,
                  include_location: bool = True) -> dict:
    """Deliver only to recipients explicitly configured by the administrator.

    A notification that failed to send must never be recorded as delivered.
    """
    persons = config.get("persons", [])
    owners = config.get("owners") or {}
    if sender_person not in persons or owners.get(sender_person) != sender_user_id:
        raise CommunicationError("You are not assigned to this person", code="not_linked")
    if action not in ACTIONS:
        raise CommunicationError("Unknown action")
    if type(include_location) is not bool:
        raise CommunicationError("Invalid location option")
    if action == "message" and (not message.strip() or len(message.strip()) > 500):
        raise CommunicationError("Invalid message")
    if recipient_person is not None:
        if (action != "message" or not isinstance(recipient_person, str)
                or recipient_person == sender_person
                or recipient_person not in persons
                or not owners.get(recipient_person)):
            raise CommunicationError("Invalid message recipient", code="invalid_recipient")
    targets = config.get("notification_targets") or {}
    # SOS also reaches the sender's own configured phone as a receipt.
    # Check-in, heading-home and ordinary messages go to other members only.
    recipients = [(person, owners[person], targets.get(person))
                  for person in persons if (person != sender_person or action == "sos")
                  and owners.get(person) and targets.get(person)
                  and (recipient_person is None or person == recipient_person)]
    if not recipients:
        raise CommunicationError("No notification recipients are configured", code="no_recipient")

    now = datetime.now(timezone.utc)
    # Rate-limit repeated taps and concurrent mobile service calls per user/action.
    ledger = hass.data.setdefault("tiny_family_action_limits", {})
    interval = 2 if action == "message" else 10
    key = (sender_user_id, action)
    previous = ledger.get(key)
    if previous is not None and now.timestamp() - previous < interval:
        raise CommunicationError("Please wait before sending the same action again", code="rate_limited")
    ledger[key] = now.timestamp()
    state = hass.states.get(sender_person)
    # Location opt-out is a hard veto, even if a panel or mobile caller asks
    # to include a location. Ghost Mode additionally suppresses sharing.
    may_share = (include_location and
                 sender_person not in (config.get("ghost_people") or []) and
                 sender_person not in (config.get("message_location_opt_out") or []))
    # Home Assistant may update a Person entity without a new GPS fix.
    # Respect Tiny Family's independent GPS quality and age indicators.
    runtime_person = hass.data.get("tiny_family", {}).get(sender_person, {})
    gps_seen = runtime_person.get("gps_seen_at")
    gps_health = runtime_person.get("gps_health")
    reliable_fix = (gps_health == "fresh"
                    and isinstance(gps_seen, (int, float))
                    and math.isfinite(gps_seen)
                    and 0 <= now.timestamp() - gps_seen <= MAX_POSITION_AGE_SECONDS)
    location = current_location(state, now) if may_share and reliable_fix else None
    location_status = ("not_applicable" if action == "message"
                       else "included" if location is not None
                       else "withheld" if not may_share
                       else "unavailable")
    home = (hass.config.latitude, hass.config.longitude)
    speed_kmh = 0.0
    if (sensor := hass.states.get(
            "sensor.tiny_family_" + sender_person.removeprefix("person.") + "_current_speed"
    )) is not None:
        try:
            speed_kmh = float(sensor.state)
        except (ValueError, TypeError):
            pass
    name = state.name if state is not None else sender_person
    title, body = compose_message(action, name, message.strip(), location, home, speed_kmh)
    available = hass.services.async_services().get("notify", {})
    # If both modern notify entities and legacy notify.mobile_app_* exist,
    # the configured target selects the exact allowed route.
    registered_notify = {s.entity_id for s in hass.states.async_all("notify")}
    successful = []
    failures = []
    for person, user_id, destination in recipients:
        if not check_target(destination, available, registered_notify):
            failures.append(person)
            continue
        token = None
        try:
            service = destination.removeprefix("notify.")
            if destination in registered_notify:
                await hass.services.async_call(
                    "notify", "send_message", {"message": body, "title": title},
                    blocking=True, target={"entity_id": destination},
                )
            else:
                # Mobile-app service notifications support in-place textInput.
                # A random one-time token is bound to the *selected* recipient
                # and original sender; we never trust an event's claimed user.
                actions = [{"action": "URI", "title": "Åbn Tiny Family",
                            "uri": "/tiny-family"}]
                if person != sender_person:
                    token = token_urlsafe(24)
                    pending_reply_tokens(hass, now)[token] = {
                        "recipient_user_id": user_id,
                        "recipient_person": person,
                        "sender_person": sender_person,
                        "notification_target": destination,
                        "expires": now.timestamp() + REPLY_TTL_SECONDS,
                    }
                    actions.insert(0, {
                        "action": REPLY_PREFIX + token,
                        "title": "Svar", "behavior": "textInput",
                        "authenticationRequired": True,
                    })
                await hass.services.async_call("notify", service, {
                    "message": body, "title": title,
                    "data": {
                        "url": "/tiny-family", "clickAction": "/tiny-family",
                        "actions": actions,
                    },
                }, blocking=True)
            successful.append((person, user_id))
        except Exception:  # Notify integrations can fail or be offline.
            if token is not None:
                hass.data.get("tiny_family_reply_tokens", {}).pop(token, None)
            failures.append(person)
    if not successful:
        ledger.pop(key, None)
        raise CommunicationError("No notification provider accepted the request", code="notify_failed")
    return {
        "action": action,
        "title": title,
        "message": message.strip() if action == "message" else body.split(" Position:")[0],
        "sender_user_id": sender_user_id,
        "sender_person": sender_person,
        "recipient_people": [person for person, _ in successful],
        "recipient_user_ids": [user_id for _, user_id in successful],
        "recipients_sent": len(successful),
        "recipients_failed": len(failures),
        "attempted_recipients": len(successful) + len(failures),
        "delivery_state": ("accepted_by_notify" if not failures
                           else "partially_accepted"),
        "push_delivery_verified": False,
        "location_status": location_status,
        "tid": now.isoformat(),
    }
