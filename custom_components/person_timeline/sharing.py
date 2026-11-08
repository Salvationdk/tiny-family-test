"""Account-aware explanation of Tiny Family's sharing rules.

This reports only permissions enforced by Tiny Family. Home Assistant
administrators and direct HA entity/Recorder access are separate.
"""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .communications import own_person
from .privacy import may_use_ghost


def sharing_report(hass, cfg, person, *, admin=False):
    selected = cfg.get("persons") or []
    owners = cfg.get("owners") or {}
    targets = cfg.get("notification_targets") or {}
    ghosts = set(cfg.get("ghost_people") or [])
    active = person in ghosts
    visible_to = []
    notifications_to = []
    for other in selected:
        if other == person or not owners.get(other):
            continue
        state = hass.states.get(other)
        display_name = state.name if state is not None else other
        if not active:
            visible_to.append(display_name)
        if targets.get(other):
            notifications_to.append(display_name)
    return {
        "person": person,
        "name": (hass.states.get(person).name
                 if hass.states.get(person) is not None else person),
        "ghost_active": active,
        "ghost_allowed": may_use_ghost(cfg, person),
        "tiny_family_location_viewers": visible_to,
        "tiny_family_route_viewers": visible_to,
        "tiny_family_system_event_viewers": visible_to,
        "own_learned_places_private": True,
        "own_activity_archive_private": True,
        "messages_visible_only_to_participants": True,
        "position_in_messages_allowed": (
            not active and person not in (cfg.get("message_location_opt_out") or [])
        ),
        "configured_phone_recipients": notifications_to,
        "speed_alert_kmh": ((cfg.get("speed_limits_kmh") or {}).get(
            person, cfg.get("speed_limit_kmh", 130)) if admin else None),
        "alert_types": (
            (cfg.get("person_notification_events") or {}).get(
                person, cfg.get("notification_events") or []
            ) if admin else None),
    }


class TinyFamilySharingView(HomeAssistantView):
    url = "/api/tiny_family/sharing"
    name = "api:tiny_family:sharing"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    async def get(self, request):
        entry = self.hass.data.get("tiny_family_runtime", {}).get("entry")
        if entry is None:
            return web.json_response({"message": "Not configured"}, status=503)
        cfg = {**entry.data, **entry.options}
        user = request["hass_user"]
        selected = cfg.get("persons") or []
        my_person = own_person(user.id, selected, cfg.get("owners") or {})
        if not my_person and not user.is_admin:
            return web.json_response({"message": "Account not linked"}, status=403)
        report = (sharing_report(self.hass, cfg, my_person, admin=False)
                  if my_person else None)
        return web.json_response({
            "mine": report,
            "admin": bool(user.is_admin),
            "family": ([sharing_report(self.hass, cfg, p, admin=True)
                        for p in selected] if user.is_admin else []),
            "limitations": [
                "Ghost Mode limits sharing inside Tiny Family; it does not alter Home Assistant Person/device_tracker entities.",
                "Home Assistant Recorder and other integrations have their own access rules.",
                "Private places and activity archives use authenticated Tiny Family endpoints.",
                "Push-service acceptance is not a guarantee that a telephone received a message.",
            ],
        }, headers={"Cache-Control": "no-store, private"})
