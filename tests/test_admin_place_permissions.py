"""HTTP-level protection of personal/shared places and suggestion visibility."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

try:
    from aiohttp import web
except ModuleNotFoundError:
    # Isolated CI tests intentionally do not install all of Home Assistant's
    # dependencies. These views only need json_response's status and body.
    fake_aiohttp = types.ModuleType("aiohttp")
    web = types.ModuleType("aiohttp.web")

    def json_response(body, *, status=200, headers=None):
        return types.SimpleNamespace(status=status, text=json.dumps(body))

    web.json_response = json_response
    fake_aiohttp.web = web
    sys.modules["aiohttp"] = fake_aiohttp
    sys.modules["aiohttp.web"] = web

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "tiny_family"
PKG = "_tiny_family_places_permission_tests"


def load_places():
    package = types.ModuleType(PKG)
    package.__path__ = []
    sys.modules[PKG] = package
    modules = {
        "communications": {"own_person": lambda user, persons, owners: next(
            (p for p in persons if owners.get(p) == user), None)},
        "const": {"DOMAIN": "tiny_family", "PLACES_FILE": "places.json",
                  "SHARED_PLACES_FILE": "shared.json", "ZONE_SUGGEST_MIN_VISITS": 3},
        "utils": {"_hav": lambda a, b, c, d: ((a-c)**2 + (b-d)**2)**.5 * 111000},
        "storage": {"_save_places": lambda *args: None,
                    "_load_places": lambda *args: []},
        "sensors": {"_publish": lambda *args: None},
        "zones_api": {"zone_collection": lambda *args: None,
                      "validate_new_zone": lambda value: value},
        "privacy": {"shared_map_zones": lambda *args: []},
    }
    for name, attributes in modules.items():
        mod = types.ModuleType(PKG + "." + name)
        mod.__dict__.update(attributes)
        sys.modules[mod.__name__] = mod
    http = types.ModuleType("homeassistant.components.http")
    http.HomeAssistantView = object
    sys.modules[http.__name__] = http
    spec = importlib.util.spec_from_file_location(PKG + ".places_api", COMPONENT / "places_api.py")
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


def load_personal_data():
    load_places()
    timeline = types.ModuleType(PKG + ".timeline")
    timeline.archive_stats = lambda *args: {"fixes": 10, "events": 5}
    timeline.delete_archive = lambda *args, **kwargs: {"fixes": 10, "events": 5}
    timeline.RETENTION_DAYS = 365
    sys.modules[timeline.__name__] = timeline
    spec = importlib.util.spec_from_file_location(PKG + ".personal_data",
                                                  COMPONENT / "personal_data.py")
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


class Request(dict):
    def __init__(self, user, payload=None):
        super().__init__(hass_user=user)
        self.payload = payload or {}

    async def json(self):
        return self.payload


class PlacesPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mod = load_places()
        self.alice = types.SimpleNamespace(id="alice", is_admin=False)
        self.admin = types.SimpleNamespace(id="admin", is_admin=True)
        entry = types.SimpleNamespace(data={
            "persons": ["person.alice", "person.bob"],
            "owners": {"person.alice": "alice", "person.bob": "bob"},
        }, options={})
        place = lambda latitude, private: {
            "lat": latitude, "lon": 11.0, "visits": 4, "min": 60,
            "label": "", "source": "learned", "private": private,
        }
        runtime = {"entry": entry, "shared_places": [{
            "id": "a"*32, "name": "Skole", "latitude": 55.0,
            "longitude": 11.0, "created_by": "alice",
        }], "shared_places_lock": asyncio.Lock()}
        people = {
            "person.alice": {"places": [place(55.0, False)]},
            "person.bob": {"places": [place(56.0, True), place(57.0, False)]},
        }
        async def run_sync(func, *args):
            return func(*args)
        self.hass = types.SimpleNamespace(
            data={"tiny_family_runtime": runtime, "tiny_family": people},
            states=types.SimpleNamespace(get=lambda name: types.SimpleNamespace(
                name=name, attributes={}) if name.startswith("person.") else None),
            config=types.SimpleNamespace(path=lambda value: value),
            async_add_executor_job=run_sync,
        )
        self.view = self.mod.TinyFamilyPlacesView(self.hass)

    async def test_family_get_exposes_public_suggestions_not_other_private(self):
        response = await self.view.get(Request(self.alice))
        self.assertEqual(response.status, 200)
        data = json.loads(response.text)
        locations = {item["latitude"] for item in data["family_suggestions"]}
        self.assertEqual(locations, {55.0, 57.0})
        self.assertEqual(data["admin_suggestions"], [])
        admin = json.loads((await self.view.get(Request(self.admin))).text)
        self.assertEqual(len(admin["family_suggestions"]), 3)

    async def test_non_admin_cannot_delete_or_set_privacy_even_as_owner(self):
        deny = await self.view.delete(Request(self.alice, {"shared_id": "a"*32}))
        self.assertEqual(deny.status, 403)
        deny = await self.view.put(Request(self.alice, {
            "kind": "privacy", "latitude": 55.0, "longitude": 11.0,
            "private": True,
        }))
        self.assertEqual(deny.status, 403)
        self.assertEqual(len(self.hass.data["tiny_family_runtime"]["shared_places"]), 1)

    async def test_admin_can_make_place_private_and_delete_shared_place(self):
        privacy = await self.view.put(Request(self.admin, {
            "kind": "privacy", "person": "person.alice",
            "latitude": 55.0, "longitude": 11.0, "private": True,
        }))
        self.assertEqual(privacy.status, 200)
        self.assertTrue(self.hass.data["tiny_family"]["person.alice"]["places"][0]["private"])
        response = await self.view.delete(Request(self.admin, {"shared_id": "a"*32}))
        self.assertEqual(response.status, 200)
        self.assertEqual(self.hass.data["tiny_family_runtime"]["shared_places"], [])


class PersonalDataPermissionsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mod = load_personal_data()
        entry = types.SimpleNamespace(data={
            "persons": ["person.alice", "person.bob"],
            "owners": {"person.alice": "alice", "person.bob": "bob"},
        }, options={})
        async def run_sync(func, *args):
            return func(*args)
        self.hass = types.SimpleNamespace(
            data={
                "tiny_family_runtime": {"entry": entry, "timeline_path": "test.sqlite3",
                    "timeline_lock": asyncio.Lock(), "timeline_pending": [],
                    "timeline_last_samples": {}, "routes": {}, "activity": {}, "routines": {}},
                "tiny_family": {"person.alice": {"places": []},
                                "person.bob": {"places": []}},
            },
            config=types.SimpleNamespace(path=lambda value: value),
            async_add_executor_job=run_sync,
        )
        self.view = self.mod.TinyFamilyPersonalDataView(self.hass)

    async def test_member_cannot_erase_routes_places_or_activities(self):
        member = types.SimpleNamespace(id="alice", is_admin=False)
        for category in ("routes", "places", "activities"):
            response = await self.view.delete(Request(member, {
                "categories": [category], "confirm": True,
            }))
            self.assertEqual(response.status, 403, category)

    async def test_admin_can_delete_another_members_archived_routes(self):
        admin = types.SimpleNamespace(id="admin", is_admin=True)
        response = await self.view.delete(Request(admin, {
            "person": "person.bob", "categories": ["routes"], "confirm": True,
        }))
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.text)["deleted"]["archived_fixes"], 10)


if __name__ == "__main__":
    unittest.main()
