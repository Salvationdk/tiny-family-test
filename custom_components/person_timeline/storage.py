"""Persistence and publication of history data. Files remain on Home Assistant only."""

import json
import logging

from .const import DOMAIN, HISTORY_EXPOSE, HISTORY_KEY, HISTORY_MAX

_LOGGER = logging.getLogger(__name__)


def _load_places(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_places(path, data):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Kunne ikke gemme steder: %s", err)


def _persist(hass, path):
    data = {p: st.get("places", []) for p, st in hass.data.get(DOMAIN, {}).items()}
    hass.async_add_executor_job(_save_places, path, data)


def _load_history(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        data = {}
    return {"chat": list(data.get("chat") or []),
            "system": list(data.get("system") or [])}


def _save_history(path, data):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Kunne ikke gemme historik: %s", err)


def _publish_history(hass):
    data = hass.data.get(HISTORY_KEY) or {"chat": [], "system": []}
    # HA state attributes may be readable to unrelated HA accounts.
    # Never expose message text or recipient metadata via public sensors.
    system = []
    hass.states.async_set("sensor.person_timeline_beskeder", str(len(data["chat"])),
                          {"friendly_name": "Person Timeline beskeder",
                           "icon": "mdi:message-text-multiple",
                           "unit_of_measurement": "beskeder",
                           "gemt": len(data["chat"])})
    hass.states.async_set("sensor.person_timeline_systembeskeder", str(len(data["system"])),
                          {"friendly_name": "Person Timeline systembeskeder",
                           "icon": "mdi:bell-ring-outline",
                           "unit_of_measurement": "beskeder",
                           "gemt": len(data["system"])})


def _append_history(hass, path, kind, entry):
    data = hass.data[HISTORY_KEY]
    bucket = data.setdefault(kind, [])
    bucket.append(entry)
    if len(bucket) > HISTORY_MAX:
        del bucket[:-HISTORY_MAX]
    hass.async_add_executor_job(_save_history, path, data)
    _publish_history(hass)
