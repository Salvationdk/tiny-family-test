"""Tiny Family Home Assistant integration, retaining the person_timeline domain."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from aiohttp import web
import voluptuous as vol
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http import StaticPathConfig
# Home Assistant 2026.11 stores zone collections inside ZoneData.
# Retain the older lookup so existing deployments remain compatible.
try:
    from homeassistant.components.zone.const import DATA_ZONE
except ImportError:
    DATA_ZONE = None

try:
    from homeassistant.components.zone import DATA_ZONE_STORAGE_COLLECTION
except ImportError:
    DATA_ZONE_STORAGE_COLLECTION = None
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change, async_track_time_interval

from .const import CARD_VERSION, DOMAIN, HISTORY_FILE, HISTORY_KEY, PLACES_FILE, SHARED_PLACES_FILE, STATIC_URL
from .places import _predict, _record_place, _seed_zones, estimate_home_eta, estimate_destination_eta
from .places_api import TinyFamilyPlacesView
from .motion import update_motion
from .gps_quality import assess_sample, mark_stale, reset_continuity
from .automation_engine import update_zone, update_battery, update_speed, notify_family, message_for_event
from .privacy import TinyFamilyStatusView, TinyFamilyPrivacyView
from .sharing import TinyFamilySharingView
from .zones_api import TinyFamilyZonesView
from .routes import TinyFamilyRoutesView, record_route, prune_routes
from .activity import TinyFamilyActivityView, add_activity, prune_activity, archive_interrupted_trip
from .geofences import TinyFamilyGeofencesView, polygon_zone, validate_polygon
from .personal_data import TinyFamilyPersonalDataView
from .export import TinyFamilyPersonalExportView
from .places import _nearest_zone_label
from .weekly import rollover, increment, due_reports
from .routines import record_departure, typical_departure
from .api import TinyFamilyCommunicationsView
from .history_api import TinyFamilyHistoryView
from .family_actions import send_from_user
from .mobile_actions import process_companion_reply
from .communications import CommunicationError
from .authz import require_permission, require_history_log_permission
from .communications import check_target
from .device_binding import companion_device_sensors
from .sensors import _publish, remove_generated_states
from .automation_engine import ALERT_EVENTS, DEFAULT_ALERT_EVENTS
from .storage import (
    _append_history, _load_history, _load_places, _persist,
    _publish_history, _save_history, _save_places,
)
from .utils import _hav


# Legacy YAML is accepted only for migration. Normal installation uses the
# config flow and stores configuration in a Home Assistant config entry.
CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.Schema({
        vol.Optional("persons", default=[]): [str],
        vol.Optional("trackers", default={}): dict,
        vol.Optional("batteries", default={}): dict,
        vol.Optional("colors", default={}): dict,
    }, extra=vol.ALLOW_EXTRA),
}, extra=vol.ALLOW_EXTRA)

RUNTIME_KEY = "tiny_family_runtime"
PANEL_URL = "tiny-family"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Initialize the integration; legacy YAML remains available temporarily."""
    if DOMAIN in config:
        hass.data.setdefault(RUNTIME_KEY, {})["legacy_yaml_active"] = True
        return await _async_setup_runtime(hass, config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up a UI-configured instance and its independent sidebar panel."""
    if hass.data.get(RUNTIME_KEY, {}).get("legacy_yaml_active"):
        # Never overwrite legacy location/history data by setting up twice.
        raise HomeAssistantError(
            "Tiny Family YAML and a UI config entry cannot be active together. "
            "Back up your files and remove the old person_timeline YAML first."
        )
    cfg = {**entry.data, **entry.options}
    if not await _async_setup_runtime(hass, {DOMAIN: cfg}):
        return False
    hass.data.setdefault(RUNTIME_KEY, {})["entry"] = entry
    # Real entity platforms own state and registry lifecycle after initial setup.
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
    )
    await panel_custom.async_register_panel(
        hass, webcomponent_name="tiny-family-panel",
        frontend_url_path=PANEL_URL, sidebar_title="Tiny Family",
        sidebar_icon="mdi:account-group", module_url=f"{STATIC_URL}/tiny-family-panel.js?v={CARD_VERSION}",
        require_admin=False, config_panel_domain=DOMAIN,
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_changed))
    return True


async def _async_options_changed(hass: HomeAssistant, entry) -> None:
    """Apply a Ghost Mode change without tearing down the authenticated API.

    Changes to tracking, recipients or other structural options still reload
    the integration. Per-person privacy toggles update in memory safely.
    """
    runtime = hass.data.get(RUNTIME_KEY, {})
    updated = {**entry.data, **entry.options}
    # Settings API awaits its own reload; do not start a concurrent reload
    # from this update listener while the new configuration is being applied.
    skip_settings = runtime.get("settings_reload_in_flight")
    if skip_settings is not None and updated == skip_settings:
        return
    privacy_keys = ("ghost_people", "message_location_opt_out", "routine_learning_people")
    non_privacy = {key: value for key, value in updated.items()
                   if key not in privacy_keys}
    # The privacy API already updates the in-memory state under the logged-in
    # user's identity, then persists ONLY privacy option keys. The update
    # listener must not tear down the API in the gap before the next request.
    # The marker only matches the precise options snapshot being saved.
    skip_options = runtime.pop("privacy_options_in_flight", None)
    if (skip_options is not None and
            runtime.get("entry") is entry and updated == skip_options):
        return
    if runtime.get("reload_config") == non_privacy:
        live_config = runtime.get("live_config")
        if live_config is not None:
            for key in privacy_keys:
                values = set(updated.get(key) or [])
                live_config[key] = sorted(values)
                privacy_set = runtime.get(key)
                if privacy_set is not None:
                    privacy_set.clear()
                    privacy_set.update(values)
            return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Remove UI and running listeners without deleting saved local history."""
    runtime = hass.data.setdefault(RUNTIME_KEY, {})
    for unsubscribe in runtime.pop("unsubscribers", []):
        unsubscribe()
    previous_config = runtime.get("live_config") or {}
    if isinstance(runtime.get("routes"), dict):
        await hass.async_add_executor_job(
            _save_places, hass.config.path("tiny_family_routes.json"),
            runtime["routes"],
        )
    runtime.pop("routes", None)
    if isinstance(runtime.get("activity"), dict):
        await hass.async_add_executor_job(
            _save_places, hass.config.path("tiny_family_activity.json"),
            runtime["activity"],
        )
    runtime.pop("activity", None)
    active = runtime.pop("entry", None)
    if active is not None:
        # Use previous runtime selection: options may already contain a new
        # set of people when Home Assistant invokes this unload for a reload.
        await hass.config_entries.async_unload_platforms(
            entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
        )
        runtime.pop("registered_entities", None)
        remove_generated_states(hass, previous_config.get("persons") or [])
        hass.data.pop(DOMAIN, None)
        for name in (
            "get_day_summary", "mobile_checkin", "mobile_heading_home",
            "mobile_sos", "mobile_message", "log_message", "log_notification",
            "clear_history", "create_zone_from_suggestion", "label_place",
            "save_place_as_zone", "delete_place_suggestion",
        ):
            if hass.services.has_service(DOMAIN, name):
                hass.services.async_remove(DOMAIN, name)
    runtime.pop("live_config", None)
    runtime.pop("ghost_people", None)
    runtime.pop("message_location_opt_out", None)
    runtime.pop("routine_learning_people", None)
    hass.data.pop("tiny_family_reply_tokens", None)
    runtime.pop("reload_config", None)
    frontend.async_remove_panel(hass, PANEL_URL, warn_if_unknown=False)
    return True


class TinyFamilySettingsView(HomeAssistantView):
    """Authenticated configuration for the dedicated Tiny Family editor."""

    url = "/api/tiny_family/settings"
    name = "api:tiny_family:settings"
    requires_auth = True

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    def _entry(self):
        return self.hass.data.get(RUNTIME_KEY, {}).get("entry")

    async def get(self, request):
        entry = self._entry()
        if entry is None:
            return web.json_response({"message": "Tiny Family is not configured"}, status=503)
        cfg = {**entry.data, **entry.options}
        admin = bool(request["hass_user"].is_admin)
        owner = next((p for p in cfg.get("persons", [])
                      if (cfg.get("owners") or {}).get(p) == request["hass_user"].id), None)
        visible = cfg.get("persons", []) if admin else ([owner] if owner else [])
        return web.json_response({
            "persons": visible,
            "trackers": {p: v for p,v in (cfg.get("trackers") or {}).items() if p in visible},
            "batteries": {p: v for p,v in (cfg.get("batteries") or {}).items() if p in visible},
            "charging_sensors": {p: v for p,v in (cfg.get("charging_sensors") or {}).items() if p in visible},
            "activity_sensors": {p: v for p,v in (cfg.get("activity_sensors") or {}).items() if p in visible},
            "colors": {p: v for p,v in (cfg.get("colors") or {}).items() if p in visible},
            "available_persons": (sorted([
                {"id": s.entity_id, "name": s.attributes.get("friendly_name", s.entity_id)}
                for s in self.hass.states.async_all("person")
            ], key=lambda x: x["name"]) if admin else []),
            "device_sensors": ({s.entity_id: companion_device_sensors(self.hass, s.entity_id)
                                for s in self.hass.states.async_all("device_tracker")}
                               if admin else {}),
            "available_trackers": (sorted([
                {"id": s.entity_id, "name": s.attributes.get("friendly_name", s.entity_id)}
                for s in self.hass.states.async_all("device_tracker")
            ], key=lambda x: x["name"]) if admin else []),
            "available_charging": (sorted([
                {"id": s.entity_id, "name": s.name}
                for domain in ("sensor", "binary_sensor")
                for s in self.hass.states.async_all(domain)
                if "charg" in s.entity_id or "plug" in s.entity_id or "battery_state" in s.entity_id
            ], key=lambda x: x["name"]) if admin else []),
            "available_activities": (sorted([
                {"id": s.entity_id, "name": s.name}
                for domain in ("sensor", "binary_sensor")
                for s in self.hass.states.async_all(domain)
                if any(word in s.entity_id for word in ("activity", "motion", "transport"))
            ], key=lambda x: x["name"]) if admin else []),
            "available_batteries": (sorted([
                {"id": s.entity_id, "name": s.attributes.get("friendly_name", s.entity_id)}
                for s in self.hass.states.async_all("sensor")
                if s.attributes.get("device_class") == "battery" or "battery" in s.entity_id
            ], key=lambda x: x["name"]) if admin else []),
            "editable": bool(request["hass_user"].is_admin),
            "auto_notifications_enabled": bool(cfg.get("auto_notifications_enabled",False)),
            "learn_routines_enabled": bool(cfg.get("learn_routines_enabled",False)),
            "notification_events": cfg.get("notification_events", list(DEFAULT_ALERT_EVENTS)),
            "speed_limit_kmh": cfg.get("speed_limit_kmh", 130) if admin else None,
            "speed_limits_kmh": cfg.get("speed_limits_kmh", {}) if admin else {},
            "person_notification_events": (
                cfg.get("person_notification_events", {}) if admin else {}
            ),
            "ghost_allowed_people": (
                cfg.get("ghost_allowed_people", cfg.get("ghost_people", []))
                if admin else []
            ),
            "owners": cfg.get("owners", {}) if request["hass_user"].is_admin else {},
            "notification_targets": cfg.get("notification_targets", {}) if request["hass_user"].is_admin else {},
            "available_users": ([{"id": u.id, "name": u.name or u.id}
                               for u in await self.hass.auth.async_get_users()
                               if u.is_active] if request["hass_user"].is_admin else []),
            "available_notify_targets": ([
                {"id": "notify." + service, "name": "Companion: " + service}
                for service in self.hass.services.async_services().get("notify", {})
                if service.startswith("mobile_app_")
            ] + [
                {"id": state.entity_id, "name": state.name}
                for state in self.hass.states.async_all("notify")
            ] if request["hass_user"].is_admin else []),
        }, headers={"Cache-Control": "no-store"})

    async def post(self, request):
        if not request["hass_user"].is_admin:
            return web.json_response({"message": "Administrator required"}, status=403)
        entry = self._entry()
        if entry is None:
            return web.json_response({"message": "Tiny Family is not configured"}, status=503)
        try:
            data = await request.json()
            persons = data["persons"]
            trackers = data.get("trackers", {})
            batteries = data.get("batteries", {})
            charging_sensors = data.get("charging_sensors", {})
            activity_sensors = data.get("activity_sensors", {})
            notification_events = data.get("notification_events", list(DEFAULT_ALERT_EVENTS))
            speed_limit_kmh = data.get("speed_limit_kmh", {**entry.data, **entry.options}.get("speed_limit_kmh", 130))
            speed_limits_kmh = data.get("speed_limits_kmh", {})
            person_notification_events = data.get("person_notification_events", {})
            ghost_allowed_people = data.get(
                "ghost_allowed_people",
                {**entry.data, **entry.options}.get("ghost_allowed_people",
                    {**entry.data, **entry.options}.get("ghost_people", [])),
            )
            colors = data.get("colors", {})
            owners = data.get("owners", {})
            notification_targets = data.get("notification_targets", {})
            auto_notifications_enabled = data.get("auto_notifications_enabled", False)
            learn_routines_enabled = data.get("learn_routines_enabled", False)
            if type(auto_notifications_enabled) is not bool or type(learn_routines_enabled) is not bool:
                raise ValueError("Invalid settings toggle")
            if type(speed_limit_kmh) is not int or not 30 <= speed_limit_kmh <= 200:
                raise ValueError("Invalid speed threshold")
            if (not isinstance(speed_limits_kmh, dict) or
                    any(person not in persons or type(limit) is not int or
                        not 30 <= limit <= 200
                        for person, limit in speed_limits_kmh.items())):
                raise ValueError("Invalid person-specific speed thresholds")
            if (not isinstance(person_notification_events, dict) or
                    any(person not in persons or not isinstance(events, list) or
                        any(not isinstance(event, str) or event not in ALERT_EVENTS
                            for event in events) or len(events) != len(set(events))
                        for person, events in person_notification_events.items())):
                raise ValueError("Invalid individual notification preferences")
            if (not isinstance(ghost_allowed_people, list) or
                    any(not isinstance(p, str) or p not in persons
                        for p in ghost_allowed_people) or
                    len(ghost_allowed_people) != len(set(ghost_allowed_people))):
                raise ValueError("Invalid Ghost Mode permissions")
            if not isinstance(persons, list) or len(persons) > 30 or len(set(persons)) != len(persons):
                raise ValueError("invalid persons")
            if not all(isinstance(p, str) and p.startswith("person.") and len(p) <= 128 for p in persons):
                raise ValueError("invalid person entities")
            if (not isinstance(notification_events, list) or
                    any(event not in ALERT_EVENTS for event in notification_events) or
                    len(set(notification_events)) != len(notification_events)):
                raise ValueError("Invalid alert categories")
            if not all(isinstance(obj, dict) for obj in (
                    trackers, batteries, charging_sensors, activity_sensors,
                    colors, owners, notification_targets)):
                raise ValueError("invalid mappings")
            if any(k not in persons for obj in (
                    trackers, batteries, charging_sensors, activity_sensors,
                    colors, owners, notification_targets) for k in obj):
                raise ValueError("mapping contains a person not selected")
            if any(not isinstance(v, str) or len(v) > 128 or
                   (v and not v.startswith("device_tracker."))
                   for v in trackers.values()):
                raise ValueError("invalid tracker")
            if any(not isinstance(v, str) or len(v) > 128 or
                   (v and not v.startswith("sensor."))
                   for v in batteries.values()):
                raise ValueError("invalid battery")
            if any(not isinstance(v, str) or len(v) > 128 or
                   (v and not v.startswith(("sensor.", "binary_sensor.")))
                   for mapping in (charging_sensors, activity_sensors)
                   for v in mapping.values()):
                raise ValueError("invalid companion sensor")
            if any(not isinstance(v, str) or
                   (v and not __import__("re").fullmatch(r"#[0-9a-fA-F]{6}", v))
                   for v in colors.values()):
                raise ValueError("invalid color")
            available_users = {u.id for u in await self.hass.auth.async_get_users() if u.is_active}
            if any(not isinstance(uid, str) or uid not in available_users
                   for uid in owners.values() if uid):
                raise ValueError("Unknown Home Assistant account")
            assigned = [uid for uid in owners.values() if uid]
            if len(assigned) != len(set(assigned)):
                raise ValueError("A user account may only be assigned to one person")
            services = self.hass.services.async_services().get("notify", {})
            notify_entities = {state.entity_id for state in self.hass.states.async_all("notify")}
            if any(not isinstance(target, str) or
                   (target and not check_target(target, services, notify_entities))
                   for target in notification_targets.values()):
                raise ValueError("Notification target is not registered")
            # The selected Companion tracker is the source of its sensor bindings.
            # Never guess using a different phone's similarly named entity.
            # Each configured member has one authoritative Companion phone.
            # Ignore caller-supplied sensor entity IDs, even if they point to
            # another family member's battery/activity sensor.
            batteries.clear()
            charging_sensors.clear()
            activity_sensors.clear()
            for person in persons:
                tracker = trackers.get(person)
                if not tracker:
                    continue
                found = companion_device_sensors(self.hass, tracker)
                for key, mapping in (
                    ("battery", batteries), ("charging", charging_sensors),
                    ("activity", activity_sensors),
                ):
                    if found.get(key):
                        mapping[person] = found[key]
        except (KeyError, ValueError, TypeError, AttributeError):
            return web.json_response({"message": "Invalid settings"}, status=400)
        options = dict(entry.options)
        options.update({
            "persons": persons, "trackers": trackers,
            "batteries": batteries, "colors": colors,
            "charging_sensors": charging_sensors,
            "activity_sensors": activity_sensors,
            "notification_events": notification_events,
            "speed_limit_kmh": speed_limit_kmh,
            "speed_limits_kmh": speed_limits_kmh,
            "person_notification_events": person_notification_events,
            "ghost_allowed_people": ghost_allowed_people,
            # Revoking permission immediately revokes the active Ghost state.
            "ghost_people": [
                person for person in options.get("ghost_people", [])
                if person in ghost_allowed_people
            ],
            "owners": {p: uid for p, uid in owners.items() if uid},
            "notification_targets": {p: target for p, target in notification_targets.items() if target},
            "auto_notifications_enabled": auto_notifications_enabled,
            "learn_routines_enabled": learn_routines_enabled,
            "routine_learning_people": (options.get("routine_learning_people", [])
                                         if learn_routines_enabled else []),
        })
        if not learn_routines_enabled and {**entry.data, **entry.options}.get("learn_routines_enabled",False):
            # Disable globally: erase both disk and in-memory learned data.
            routines_cache = self.hass.data.get(RUNTIME_KEY, {}).get("routines")
            if isinstance(routines_cache, dict):
                routines_cache.clear()
            await self.hass.async_add_executor_job(
                _save_places, self.hass.config.path("tiny_family_routines.json"), {})
        runtime = self.hass.data.setdefault(RUNTIME_KEY, {})
        runtime["settings_reload_in_flight"] = {**entry.data, **options}
        try:
            self.hass.config_entries.async_update_entry(entry, options=options)
            # Do not acknowledge success before entity platforms and the
            # authenticated API are fully available after a structural edit.
            ready = await self.hass.config_entries.async_reload(entry.entry_id)
        except Exception:
            return web.json_response(
                {"message": "Home Assistant could not reload Tiny Family"},
                status=503, headers={"Cache-Control": "no-store"})
        finally:
            runtime.pop("settings_reload_in_flight", None)
        if not ready:
            return web.json_response(
                {"message": "Tiny Family reload did not complete"},
                status=503, headers={"Cache-Control": "no-store"})
        return web.json_response({"status": "saved"}, headers={"Cache-Control": "no-store"})


async def _async_setup_runtime(hass: HomeAssistant, config: dict) -> bool:
    """Load current activity algorithms with UI-selected person mappings."""
    runtime = hass.data.setdefault(RUNTIME_KEY, {})
    for unsubscribe in runtime.pop("unsubscribers", []):
        unsubscribe()
    runtime["unsubscribers"] = []
    if not runtime.get("assets_registered"):
        frontend_dir = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(frontend_dir), False)]
        )
        hass.http.register_view(TinyFamilySettingsView(hass))
        hass.http.register_view(TinyFamilyCommunicationsView(hass))
        hass.http.register_view(TinyFamilyStatusView(hass))
        hass.http.register_view(TinyFamilyPrivacyView(hass))
        hass.http.register_view(TinyFamilySharingView(hass))
        hass.http.register_view(TinyFamilyZonesView(hass))
        hass.http.register_view(TinyFamilyRoutesView(hass))
        hass.http.register_view(TinyFamilyActivityView(hass))
        hass.http.register_view(TinyFamilyPlacesView(hass))
        hass.http.register_view(TinyFamilyGeofencesView(hass))
        hass.http.register_view(TinyFamilyPersonalDataView(hass))
        hass.http.register_view(TinyFamilyPersonalExportView(hass))
        hass.http.register_view(TinyFamilyHistoryView(hass))
        runtime["assets_registered"] = True
    if not runtime.get("switch_registered"):
        hass.async_create_task(async_load_platform(hass, Platform.SWITCH, DOMAIN, {}, config))
        runtime["switch_registered"] = True

    # The action identifier contains a short-lived, random bearer capability.
    # A mobile_app_notification_action event must never supply sender identity.
    async def _handle_companion_reply(event):
        await process_companion_reply(hass, event)

    @callback
    def _on_companion_reply(event):
        hass.async_create_task(_handle_companion_reply(event))

    runtime["unsubscribers"].append(
        hass.bus.async_listen("mobile_app_notification_action", _on_companion_reply)
    )

    # Work with a runtime copy; keep legacy persisted options unchanged.
    cfg = dict(config.get(DOMAIN, {}) or {})
    persons = cfg.get("persons") or []
    ghost_people = set(cfg.get("ghost_people") or [])
    location_opt_out = set(cfg.get("message_location_opt_out") or [])
    routine_people = set(cfg.get("routine_learning_people") or [])
    if not cfg.get("learn_routines_enabled", False):
        routine_people.clear()
    routine_people.intersection_update(persons)
    runtime["live_config"] = cfg
    runtime["ghost_people"] = ghost_people
    runtime["message_location_opt_out"] = location_opt_out
    runtime["routine_learning_people"] = routine_people
    runtime["reload_config"] = {
        key: value for key, value in cfg.items()
        if key not in ("ghost_people", "message_location_opt_out", "routine_learning_people")
    }
    trackers = dict(cfg.get("trackers") or {})
    # If no tracker was explicitly chosen, listen to the Person entity.
    # The HA Companion app supplies that Person's GPS via its device_tracker.
    for person in persons:
        trackers[person] = trackers.get(person) or person
    # Refresh phone-owned sensor mapping during startup as well as on save.
    # This avoids stale sensor references after an upgrade or a phone switch.
    for mapping_key in ("batteries", "charging_sensors", "activity_sensors"):
        cfg[mapping_key] = {}
    for person in persons:
        tracker = trackers.get(person)
        found = companion_device_sensors(hass, tracker)
        for key, mapping_key in (
            ("battery", "batteries"), ("charging", "charging_sensors"),
            ("activity", "activity_sensors"),
        ):
            if found.get(key):
                cfg[mapping_key][person] = found[key]
    # Shared places load once, and each person's prediction engine sees
    # the same in-memory list. Personal learned stays remain separate.
    shared = await hass.async_add_executor_job(
        _load_places, hass.config.path(SHARED_PLACES_FILE)
    )
    runtime["shared_places"] = shared if isinstance(shared, list) else []
    places_path = hass.config.path(PLACES_FILE)
    try:
        saved = await hass.async_add_executor_job(_load_places, places_path)
    except Exception:
        saved = {}
    history_path = hass.config.path(HISTORY_FILE)
    try:
        history = await hass.async_add_executor_job(_load_history, history_path)
    except Exception:
        history = {"chat": [], "system": []}
    hass.data[HISTORY_KEY] = history
    weekly_path=hass.config.path("tiny_family_weekly.json")
    weekly=await hass.async_add_executor_job(_load_places,weekly_path)
    if not isinstance(weekly,dict): weekly={}
    local_now=datetime.now(tz=ZoneInfo(hass.config.time_zone))
    if rollover(weekly,local_now):
        await hass.async_add_executor_job(_save_places, weekly_path, weekly)
    routines_path=hass.config.path("tiny_family_routines.json")
    routines_data={}
    if cfg.get("learn_routines_enabled",False):
        routines_data=await hass.async_add_executor_job(_load_places,routines_path)
        if not isinstance(routines_data,dict): routines_data={}
        from .routines import prune_records
        changed = prune_records(routines_data, datetime.now(tz=timezone.utc),
                                selected_people=routine_people)
        if changed:
            await hass.async_add_executor_job(_save_places, routines_path, routines_data)
    runtime["weekly"]=weekly
    runtime["routines"]=routines_data
    routes_path = hass.config.path("tiny_family_routes.json")
    routes_data = await hass.async_add_executor_job(_load_places, routes_path)
    if not isinstance(routes_data, dict):
        routes_data = {}
    prune_routes(routes_data, datetime.now(tz=timezone.utc).timestamp())
    runtime["routes"] = routes_data
    activity_path = hass.config.path("tiny_family_activity.json")
    activity_data = await hass.async_add_executor_job(_load_places, activity_path)
    if not isinstance(activity_data, dict):
        activity_data = {}
    prune_activity(activity_data, datetime.now(tz=timezone.utc).timestamp())
    runtime["activity"] = activity_data
    geofences_file = hass.config.path("tiny_family_geofences.json")
    saved_polygons = await hass.async_add_executor_job(_load_places, geofences_file)
    polygons = []
    for item in (saved_polygons.get("items") or []) if isinstance(saved_polygons, dict) else []:
        try:
            valid = validate_polygon(item)
            if isinstance(item.get("id"), str) and len(item["id"]) == 32:
                polygons.append({"id": item["id"], **valid})
        except (ValueError, TypeError, AttributeError):
            continue
    runtime["geofences"] = polygons
    hass.data[DOMAIN] = {}
    for person in persons:
        hass.data[DOMAIN][person] = {"distance_m": 0.0, "stays": 0, "current_stay_min": 0,
                                     "stay_start": None, "last_lat": None, "last_lon": None,
                                     "last_t": None, "max_speed": 0.0,
                                     "distance_week_m": float((weekly.get("totals") or {}).get(person,0)),
                                     "trip_active": False, "trip_start": None, "trip_last_move": None,
                                     "trip_dist_m": 0.0, "trip_max_speed": 0.0, "last_trip": "Ingen ture endnu",
                                     "places": list(saved.get(person, [])),
                                     "family_places": runtime["shared_places"],
                                     "recent": [], "seeded": False,
                                     "destination": "", "dest_eta_min": 0, "dest_dist_m": 0.0,
                                     "destination_confidence": 0.0,
                                     "home_eta_min": None,
                                     "stay_lat_sum": 0.0, "stay_lon_sum": 0.0, "stay_n": 0,
                                     "tracker": trackers.get(person),
                                     "charging_entity": (cfg.get("charging_sensors") or {}).get(person),
                                     "activity_entity": (cfg.get("activity_sensors") or {}).get(person),
                                     "movement_state": "unknown",
                                     "movement_candidate": "",
                                     "movement_candidate_samples": 0,
                                     "speed_kmh": 0.0,
                                     "gps_health": "unknown",
                                     "gps_seen_at": None}
        if cfg.get("learn_routines_enabled",False) and person in routine_people:
            learned=typical_departure(routines_data,person,local_now.weekday())
            if learned:
                hass.data[DOMAIN][person]["usual_departure"]=learned["time"]
                hass.data[DOMAIN][person]["routine_confidence"]=learned["confidence"]
        _publish(hass, person)
    _publish_history(hass)

    # Updates from phone charging/activity sensors must refresh derived HA
    # states without waiting for a GPS fix.
    for person in persons:
        st = hass.data[DOMAIN][person]
        for entity in filter(None, (st.get("charging_entity"), st.get("activity_entity"))):
            @callback
            def _refresh(event, person=person):
                # Run on HA's event loop, not in the default executor.
                if person in hass.data.get(DOMAIN, {}):
                    _publish(hass, person)
            runtime["unsubscribers"].append(
                async_track_state_change_event(hass, [entity], _refresh)
            )

    def emit_alert(person, event_name, details, *, has_event=True):
        # Exclude Ghost Mode from Tiny Family's own event bus and push output.
        if person in ghost_people:
            return
        state = hass.states.get(person)
        name = state.name if state is not None else person
        title, body = message_for_event(event_name, name, details)
        if has_event:
            hass.bus.async_fire("tiny_family_" + event_name, {
                "person":person, **details,
                "timestamp":datetime.now(tz=timezone.utc).isoformat(),
            })
        if cfg.get("auto_notifications_enabled", False):
            hass.async_create_task(notify_family(hass, cfg, person, event_name, details))
        _append_history(hass, history_path, "system", {
            "tid":datetime.now(tz=timezone.utc).isoformat(),
            "kategori":title, "tekst":body[:500], "person":person,
            "event_key":event_name,
        })

    # Establish a baseline for battery readings and watch Companion sensors.
    for person in persons:
        sensor=(cfg.get("batteries") or {}).get(person)
        if not sensor:
            continue
        def _on_battery(target_person):
            async def _handler(event):
                new=event.data.get("new_state")
                if new is None or target_person not in hass.data.get(DOMAIN, {}):
                    return
                try:
                    battery=float(new.state)
                except (ValueError, TypeError):
                    return
                state=hass.data[DOMAIN][target_person]
                for event_name, details in update_battery(state, battery):
                    emit_alert(target_person, event_name, details)
            return _handler
        initial=hass.states.get(sensor)
        if initial is not None:
            try:
                update_battery(hass.data[DOMAIN][person], float(initial.state))
            except (ValueError, TypeError):
                pass
        runtime["unsubscribers"].append(
            async_track_state_change_event(hass,[sensor],_on_battery(person))
        )

    def _handle(person):
        async def _cb(event):
            new = event.data.get("new_state")
            if new is None:
                return
            a = new.attributes
            if a.get("latitude") is None:
                return
            try:
                # last_changed can remain unchanged while Companion GPS
                # attributes update inside the same Home Assistant zone.
                t = new.last_updated.timestamp()
            except Exception:
                return
            st = hass.data.get(DOMAIN, {}).get(person)
            if st is None:
                return
            try:
                lat, lon = float(a["latitude"]), float(a["longitude"])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    return
                accuracy = float(a["gps_accuracy"]) if a.get("gps_accuracy") is not None else None
                raw_speed = a.get("speed")
                if raw_speed is None and isinstance(a.get("source"), str):
                    # Person entities can inherit their position from Companion.
                    source = hass.states.get(a["source"])
                    if source is not None:
                        raw_speed = source.attributes.get("speed")
                        if accuracy is None and source.attributes.get("gps_accuracy") is not None:
                            accuracy = float(source.attributes["gps_accuracy"])
                speed = max(0.0, float(raw_speed or 0))
                if not all(__import__("math").isfinite(v) for v in (lat, lon, speed)):
                    return
                if accuracy is not None and (
                    not __import__("math").isfinite(accuracy)
                    or accuracy < 0 or accuracy > 150
                ):
                    return
            except (ValueError, TypeError, OverflowError):
                return
            d = None
            if st["last_lat"] is not None:
                d = _hav(st["last_lat"], st["last_lon"], lat, lon)
            old_timestamp = st.get("gps_seen_at")
            health_before = st.get("gps_health", "unknown")
            quality = assess_sample(
                st, observed_at=t, now_ts=datetime.now(tz=timezone.utc).timestamp(),
                latitude=lat, longitude=lon, speed_mps=speed,
                accuracy_m=accuracy, distance_m=d,
            )
            if quality in ("invalid", "duplicate", "jump"):
                return
            if quality == "gap":
                archive_interrupted_trip(
                    activity_data, person, st, private=person in ghost_people
                )
                reset_continuity(st)
                d = None  # Never add a jump across the GPS outage to a trip.
            st["gps_health"] = "fresh"
            st["gps_seen_at"] = t
            record_route(
                routes_data, person, ts=t, lat=lat, lon=lon,
                private=person in ghost_people,
                gap=(quality == "gap" or bool(st.pop("route_gap_pending", False))),
            )
            dt_h = ((t - st["last_t"]) / 3600
                    if st.get("last_t") is not None else 0)
            distance_step = 0.0
            if st["last_lat"] is not None and d is not None:
                if raw_speed is None and dt_h > 0 and dt_h <= (10 / 60):
                    # Estimate only when Companion did not provide speed.
                    # A GPS accuracy floor reduces jitter-induced motion.
                    if (accuracy is None or accuracy <= 100) and d >= max(45, (accuracy or 0) * 1.5):
                        estimated = d / (dt_h * 3600)
                        if estimated < 200 / 3.6:
                            speed = estimated
                if (dt_h > 0 and (d / 1000 / dt_h) <= 200 and
                        d >= max(20.0, 1.5 * (accuracy or 0))):
                    distance_step = d
                    st["distance_m"] += distance_step
                    st["distance_week_m"] += distance_step
                    increment(weekly, person, distance_step)
                if d < 100 and (speed * 3.6) < 5:
                    if st["stay_start"] is None:
                        st["stay_start"] = t
                        st["stay_lat_sum"] = 0.0
                        st["stay_lon_sum"] = 0.0
                        st["stay_n"] = 0
                    st["stay_lat_sum"] += lat
                    st["stay_lon_sum"] += lon
                    st["stay_n"] += 1
                    mins = (t - st["stay_start"]) / 60
                    st["current_stay_min"] = int(mins)
                else:
                    if st["stay_start"] is not None:
                        stay_min = (t - st["stay_start"]) / 60
                        if stay_min >= 10:
                            st["stays"] += 1
                            if person not in ghost_people:
                                hass.bus.async_fire("tiny_family_stay_completed", {
                                    "person": person,
                                    "timestamp": datetime.fromtimestamp(t, tz=timezone.utc).isoformat(),
                                    "duration_min": round(stay_min),
                                })
                            if st.get("stay_n"):
                                add_activity(
                                    activity_data, person, kind="stay",
                                    started_at=st["stay_start"], ended_at=t,
                                    private=person in ghost_people,
                                    label=polygon_zone(polygons, lat, lon) or
                                          _nearest_zone_label(hass, lat, lon),
                                )
                                _record_place(hass, person,
                                              st["stay_lat_sum"] / st["stay_n"],
                                              st["stay_lon_sum"] / st["stay_n"],
                                              int(stay_min))
                                _persist(hass, places_path)
                    st["stay_start"] = None
                    st["stay_n"] = 0
                    st["current_stay_min"] = 0
            change = update_motion(
                st, observed_at=t, speed_mps=speed,
                displacement_m=d, accuracy_m=accuracy,
            )
            st["speed_kmh"] = round(speed * 3.6, 1)
            st["max_speed"] = max(st["max_speed"], speed)
            if person not in ghost_people:
                zone = (polygon_zone(polygons, lat, lon)
                        or _nearest_zone_label(hass, lat, lon))
                for name, details in update_zone(st, zone, t):
                    emit_alert(person, name, details)
                for name, details in update_speed(
                        st, speed * 3.6, accuracy, t,
                        threshold_kmh=(cfg.get("speed_limits_kmh") or {}).get(
                            person, cfg.get("speed_limit_kmh", 130))):
                    emit_alert(person, name, details)
            def fire(event_name, **details):
                # No raw GPS coordinates, phone identifiers or tokens in events.
                if person in ghost_people:
                    return
                hass.bus.async_fire("tiny_family_" + event_name, {
                    "person": person,
                    "timestamp": datetime.fromtimestamp(t, tz=timezone.utc).isoformat(),
                    **details,
                })
            if health_before == "stale":
                emit_alert(person, "tracking_restored", {
                    "gap_minutes": max(0, round((t - (old_timestamp or t)) / 60)),
                })
            if quality == "gap":
                fire("tracking_gap", duration_min=max(
                    0, round((t - (old_timestamp or t)) / 60)))
            if change:
                fire("movement_" + change, state=st["movement_state"])
            if speed >= 2.8 and quality == "continuous":
                if not st["trip_active"]:
                    st.update({"trip_active": True, "trip_start": t,
                               "trip_dist_m": 0.0, "trip_max_speed": speed})
                    fire("trip_started")
                st["trip_last_move"] = t
                if distance_step:
                    st["trip_dist_m"] += distance_step
                st["trip_max_speed"] = max(st["trip_max_speed"], speed)
            elif st["trip_active"] and st.get("trip_last_move") and (t - st["trip_last_move"]) >= 300:
                mins = (t - st["trip_start"]) / 60 if st["trip_start"] else 0
                if mins >= 3 and st["trip_dist_m"] >= 500:
                    st["last_trip"] = (f"{round(st['trip_dist_m'] / 1000, 1)} km på "
                                       f"{int(mins)} min, max {round(st['trip_max_speed'] * 3.6, 0)} km/t")
                st["trip_active"] = False
                details = {
                    "distance_km":round(st["trip_dist_m"] / 1000, 2),
                    "duration_min":round(mins),
                    "max_speed_kmh":round(st["trip_max_speed"] * 3.6, 1),
                }
                add_activity(
                    activity_data, person, kind="trip",
                    started_at=st["trip_start"] or t,
                    ended_at=t, private=person in ghost_people,
                    distance_km=details["distance_km"],
                    max_speed_kmh=details["max_speed_kmh"],
                )
                fire("trip_ended", **details)
                emit_alert(person, "trip_ended", details, has_event=False)
                if (cfg.get("learn_routines_enabled",False)
                        and person in routine_people and st.get("trip_start")
                        and mins >= 3 and st["trip_dist_m"] >= 500):
                    departure=datetime.fromtimestamp(st["trip_start"],
                                tz=timezone.utc).astimezone(ZoneInfo(hass.config.time_zone))
                    suggestion=record_departure(routines_data,person,departure,
                                now=datetime.now(tz=timezone.utc))
                    if suggestion is not None:
                        st["usual_departure"]=suggestion["time"]
                        st["routine_confidence"]=suggestion["confidence"]
                        if person not in ghost_people:
                            fire("routine_learned", weekday=suggestion["weekday"],
                                 usual_departure=suggestion["time"],
                                 confidence=suggestion["confidence"])
                    await hass.async_add_executor_job(_save_places,routines_path,routines_data)
            if not st.get("seeded"):
                _seed_zones(hass, person)
            recent = st.setdefault("recent", [])
            recent.append((t, lat, lon))
            st["recent"] = [p for p in recent if t - p[0] <= 900][-60:]
            previous_destination = st.get("destination") or ""
            pred = _predict(st) if speed >= 2.2 else None
            if pred:
                pl, d_now = pred
                st["destination"] = pl.get("label") or "ukendt sted"
                st["dest_eta_min"] = estimate_destination_eta(d_now,speed) or 0
                st["dest_dist_m"] = d_now
            else:
                st["destination"] = ""
                st["dest_eta_min"] = 0
                st["dest_dist_m"] = 0.0
                st["destination_confidence"] = 0.0
            st["home_eta_min"] = estimate_home_eta(
                st, lat, lon, hass.config.latitude, hass.config.longitude, speed
            )
            destination = st.get("destination") or ""
            if destination != previous_destination:
                fire("destination_changed",
                     destination=destination,
                     previous_destination=previous_destination,
                     eta_minutes=st.get("dest_eta_min", 0))
            st["last_lat"], st["last_lon"], st["last_t"] = lat, lon, t
            _publish(hass, person)
        return _cb

    for person in persons:
        tracker = trackers.get(person)
        if tracker:
            runtime["unsubscribers"].append(
                async_track_state_change_event(hass, [tracker], _handle(person))
            )
            # Existing HA Person/tracker state must also establish a baseline
            # when the integration starts after the Companion phone.
            initial_state = hass.states.get(tracker)
            if initial_state is not None:
                from types import SimpleNamespace
                await _handle(person)(SimpleNamespace(
                    data={"new_state": initial_state}
                ))

    async def _check_gps_health(now: datetime):
        now_ts = now.timestamp()
        for person in persons:
            st = hass.data.get(DOMAIN, {}).get(person)
            if st is None:
                continue
            if (st.get("gps_health") == "fresh"
                    and type(st.get("gps_seen_at")) in (float, int)
                    and now_ts - st["gps_seen_at"] > 15 * 60):
                archive_interrupted_trip(
                    activity_data, person, st, private=person in ghost_people
                )
            if mark_stale(st, now_ts):
                st["route_gap_pending"] = True
                age = max(0, round((now_ts - st["gps_seen_at"]) / 60))
                _publish(hass, person)
                emit_alert(person, "tracking_stale", {"age_minutes": age})

    runtime["unsubscribers"].append(
        async_track_time_interval(hass, _check_gps_health, timedelta(minutes=2))
    )

    async def _midnight(now: datetime):
        monday = now.isoweekday() == 1
        rolled=rollover(weekly,now)
        for person in persons:
            st = hass.data[DOMAIN][person]
            st.update({"distance_m": 0.0, "stays": 0, "current_stay_min": 0,
                       "stay_start": None, "max_speed": 0.0})
            if monday and rolled:
                st["distance_week_m"] = 0.0
            _publish(hass, person)
        if rolled:
            await hass.async_add_executor_job(_save_places,weekly_path,weekly)

    runtime["unsubscribers"].append(
        async_track_time_change(hass, _midnight, hour=0, minute=0, second=0)
    )

    async def _save_weekly_periodically(_):
        await hass.async_add_executor_job(_save_places,weekly_path,weekly)
        prune_routes(routes_data, datetime.now(tz=timezone.utc).timestamp())
        await hass.async_add_executor_job(_save_places,routes_path,routes_data)
        prune_activity(activity_data, datetime.now(tz=timezone.utc).timestamp())
        await hass.async_add_executor_job(_save_places,activity_path,activity_data)

    runtime["unsubscribers"].append(
        async_track_time_interval(hass,_save_weekly_periodically,timedelta(minutes=10))
    )

    async def _weekly_report(now: datetime):
        reports=due_reports(weekly,now)
        if not reports: return
        await hass.async_add_executor_job(_save_places,weekly_path,weekly)
        for person, distance_km in reports:
            if person in persons:
                emit_alert(person,"weekly_summary",{"distance_km":distance_km})
        for person in persons:
            st=hass.data[DOMAIN][person]
            st["distance_week_m"]=float((weekly.get("totals") or {}).get(person,0))
            _publish(hass,person)

    runtime["unsubscribers"].append(
        async_track_time_change(hass,_weekly_report,hour=8,minute=0,second=0)
    )

    async def get_day_summary(call):
        person = call.data.get("person", persons[0] if persons else "")
        user_id = call.context.user_id if call.context else None
        if not user_id:
            raise HomeAssistantError("Day summary requires an authenticated user")
        viewer=next((p for p in persons if (cfg.get("owners") or {}).get(p)==user_id),None)
        ha_user=await hass.auth.async_get_user(user_id)
        if person not in persons or (
                person != viewer and (person in ghost_people or
                                      not (ha_user and ha_user.is_admin))):
            raise HomeAssistantError("No access to requested summary")
        st = hass.data.get(DOMAIN, {}).get(person, {})
        return {"person": person, "gps_health": st.get("gps_health", "unknown"),
                "distance_km": round(st.get("distance_m", 0) / 1000, 1),
                "stays": st.get("stays", 0), "current_stay_min": st.get("current_stay_min", 0),
                "max_speed_kmh": round(st.get("max_speed", 0) * 3.6, 0),
                "distance_week_km": round(st.get("distance_week_m", 0) / 1000, 1),
                "trip_active": st.get("trip_active", False),
                "last_trip": st.get("last_trip", "Ingen ture endnu"),
                "destination": st.get("destination", ""),
                "dest_eta_min": st.get("dest_eta_min", 0)}

    hass.services.async_register(DOMAIN, "get_day_summary", get_day_summary,
                                 supports_response=SupportsResponse.ONLY)

    # Companion widgets and iOS shortcuts can call these services as their
    # signed-in HA user, without YAML scripts or Lovelace dashboard cards.
    def _mobile_action(action):
        async def _handler(call):
            if not call.context or not call.context.user_id:
                raise HomeAssistantError(
                    "Tiny Family mobile actions require a signed-in Home Assistant user"
                )
            active_entry=hass.data.get(RUNTIME_KEY,{}).get("entry")
            if active_entry is None:
                raise HomeAssistantError("Tiny Family must be configured in UI first")
            config={**active_entry.data,**active_entry.options}
            try:
                message = call.data.get("message", "")
                recipient = call.data.get("recipient_person")
                if (not isinstance(message, str) or
                        (recipient is not None and not isinstance(recipient, str))):
                    raise CommunicationError("Invalid mobile action data")
                await send_from_user(hass, config, call.context.user_id,
                                     action, message,
                                     recipient_person=recipient)
            except CommunicationError as err:
                raise HomeAssistantError(str(err)) from err
        return _handler
    for service_name, action in (
        ("mobile_checkin","checkin"),
        ("mobile_heading_home","heading_home"),
        ("mobile_sos","sos"),
        ("mobile_message","message"),
    ):
        hass.services.async_register(DOMAIN,service_name,_mobile_action(action))

    async def log_message(call):
        await require_permission(hass, cfg, call)
        tekst = (call.data.get("tekst") or "").strip()
        if not tekst:
            return
        _append_history(hass, history_path, "chat",
                        {"tid": datetime.now().isoformat(timespec="seconds"),
                         "fra": (call.data.get("fra") or "").strip(),
                         "til": (call.data.get("til") or "").strip(),
                         "tekst": tekst[:500]})

    async def log_notification(call):
        # HA automations normally run with context.user_id=None. This
        # service only appends a bounded system-history entry; it does not
        # impersonate a family member, send push messages or edit zones.
        # Interactive calls still require an authenticated administrator.
        await require_history_log_permission(hass, cfg, call)
        category = call.data.get("kategori") or "Besked"
        message = call.data.get("tekst") or ""
        if not isinstance(category, str) or not isinstance(message, str):
            raise HomeAssistantError("Invalid notification text or category")
        category = category.strip()[:80] or "Besked"
        message = message.strip()[:500]
        if not message:
            return
        _append_history(hass, history_path, "system",
                        {"tid": datetime.now().isoformat(timespec="seconds"),
                         "kategori": category, "tekst": message})

    async def clear_history(call):
        # Legacy global reset is restricted to an authenticated HA admin.
        # Ordinary users clear only their own view via /api/tiny_family/communications.
        user_id = call.context.user_id if call.context else None
        user = await hass.auth.async_get_user(user_id) if user_id else None
        if not user or not user.is_admin:
            raise HomeAssistantError("Only a Home Assistant administrator can clear global history")
        kind = (call.data.get("kind") or "all").strip()
        hist = hass.data[HISTORY_KEY]
        if kind in ("chat", "all"):
            hist["chat"] = []
        if kind in ("system", "all"):
            hist["system"] = []
        await hass.async_add_executor_job(_save_history, history_path, hist)
        _publish_history(hass)

    hass.services.async_register(DOMAIN, "log_message", log_message)
    hass.services.async_register(DOMAIN, "log_notification", log_notification)
    hass.services.async_register(DOMAIN, "clear_history", clear_history)

    async def _save_place(call, create_zone):
        person = call.data.get("person")
        await require_permission(hass, cfg, call, person, admin_only=create_zone)
        lat = call.data.get("lat")
        lon = call.data.get("lon")
        label = (call.data.get("label") or call.data.get("navn") or "").strip()
        radius = int(call.data.get("radius") or 25)
        if not person or lat is None or lon is None or not label:
            raise ValueError("Person, koordinater og navn skal udfyldes")
        st = hass.data.get(DOMAIN, {}).get(person)
        if not st:
            raise ValueError(f"Ukendt person: {person}")
        places = st.setdefault("places", [])
        best = None
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError) as err:
            raise ValueError("Ugyldige koordinater") from err
        for pl in places:
            try:
                d = _hav(pl["lat"], pl["lon"], lat_f, lon_f)
            except Exception:
                continue
            if d <= 10 and (best is None or d < best[0]):
                best = (d, pl)
        if best is not None:
            best[1]["label"] = label
            data_to_save = {p: stp.get("places", []) for p, stp in hass.data.get(DOMAIN, {}).items()}
            await hass.async_add_executor_job(_save_places, places_path, data_to_save)
        else:
            raise ValueError("Det valgte forslag blev ikke fundet")

        if create_zone:
            existing = any(
                zone.attributes.get("latitude") is not None
                and zone.attributes.get("longitude") is not None
                and _hav(
                    lat_f,
                    lon_f,
                    float(zone.attributes["latitude"]),
                    float(zone.attributes["longitude"]),
                ) <= max(radius, float(zone.attributes.get("radius") or 0)) + 25
                for zone in hass.states.async_all("zone")
            )
            if not existing:
                zone_data = hass.data.get(DATA_ZONE) if DATA_ZONE is not None else None
                collection = getattr(zone_data, "storage_collection", None)
                if collection is None and DATA_ZONE_STORAGE_COLLECTION is not None:
                    collection = hass.data.get(DATA_ZONE_STORAGE_COLLECTION)
                if collection is None:
                    raise ValueError("Home Assistants zone-lager er ikke tilgængeligt")
                await collection.async_create_item({
                    "name": label,
                    "latitude": lat_f,
                    "longitude": lon_f,
                    "radius": float(radius),
                    "passive": False,
                    "icon": "mdi:map-marker",
                })

        _publish(hass, person)

    async def _create_zone_async(call):
        await _save_place(call, True)

    async def _label_place(call):
        await _save_place(call, False)

    async def _save_place_as_zone(call):
        await _save_place(call, True)

    async def _delete_place_suggestion(call):
        person = call.data.get("person")
        await require_permission(hass, cfg, call, person)
        lat = call.data.get("lat")
        lon = call.data.get("lon")
        if not person or lat is None or lon is None:
            raise ValueError("Person og koordinater skal udfyldes")
        st = hass.data.get(DOMAIN, {}).get(person)
        if not st:
            raise ValueError(f"Ukendt person: {person}")
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError) as err:
            raise ValueError("Ugyldige koordinater") from err

        places = st.setdefault("places", [])
        best = None
        for pl in places:
            try:
                distance = _hav(pl["lat"], pl["lon"], lat_f, lon_f)
            except Exception:
                continue
            if distance <= 10 and (best is None or distance < best[0]):
                best = (distance, pl)
        if best is None:
            raise ValueError("Det valgte forslag blev ikke fundet")
        label = (best[1].get("label") or "").strip().lower()
        if label and label not in ("ukendt sted", "unknown", "ukendt"):
            raise ValueError("Kun unavngivne forslag kan slettes")

        places.remove(best[1])
        data_to_save = {
            saved_person: saved_state.get("places", [])
            for saved_person, saved_state in hass.data.get(DOMAIN, {}).items()
        }
        await hass.async_add_executor_job(_save_places, places_path, data_to_save)
        _publish(hass, person)

    hass.services.async_register(DOMAIN, "create_zone_from_suggestion", _create_zone_async)
    hass.services.async_register(DOMAIN, "label_place", _label_place)
    hass.services.async_register(DOMAIN, "save_place_as_zone", _save_place_as_zone)
    hass.services.async_register(DOMAIN, "delete_place_suggestion", _delete_place_suggestion)
    return True
