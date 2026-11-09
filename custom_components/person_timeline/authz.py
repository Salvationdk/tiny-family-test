"""Authorization helpers for service calls that modify family-owned data."""
from homeassistant.exceptions import HomeAssistantError


async def require_permission(hass, config, call, person=None, *, admin_only=False):
    user_id = getattr(getattr(call, "context", None), "user_id", None)
    if not user_id:
        raise HomeAssistantError("Tiny Family needs an authenticated account")
    user = await hass.auth.async_get_user(user_id)
    if user is None or not getattr(user, "is_active", True):
        raise HomeAssistantError("Unknown or inactive account")
    if person is not None and person not in (config.get("persons") or []):
        raise HomeAssistantError("Unknown family member")
    if person is None or admin_only:
        if not user.is_admin:
            raise HomeAssistantError("Administrator permission required")
    elif not user.is_admin and (config.get("owners") or {}).get(person) != user_id:
        raise HomeAssistantError("Cannot modify another person's data")


async def require_history_log_permission(hass, config, call):
    """Authorize writing a bounded system log entry.

    Home Assistant's own automation/script calls have a service context but
    no user_id. Allow that *only* for the log_notification service; any call
    attributable to a user remains admin-only. Never reuse this helper for
    member data, history deletion, messaging or zone changes.
    """
    context = getattr(call, "context", None)
    if context is None:
        raise HomeAssistantError("Missing Home Assistant service context")
    if getattr(context, "user_id", None) is None:
        return
    await require_permission(hass, config, call)
