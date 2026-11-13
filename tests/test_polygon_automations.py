"""Polygons must be valid, overlap safely, and be reusable by HA entities."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tiny_family"
PACKAGE = "_tiny_polygon_automation_tests"
saved = []


def load_geofences():
    # GitHub's standalone regression runner has no HA/aiohttp dependencies.
    try:
        from aiohttp import web  # noqa: F401
    except ImportError:
        aiohttp = types.ModuleType("aiohttp")
        aiohttp.web = types.SimpleNamespace(json_response=lambda _data, status=200,
                                             headers=None: types.SimpleNamespace(status=status))
        sys.modules["aiohttp"] = aiohttp
    for name in ("homeassistant", "homeassistant.components", PACKAGE):
        mod = types.ModuleType(name)
        mod.__path__ = []
        sys.modules.setdefault(name, mod)
    http = types.ModuleType("homeassistant.components.http")
    http.HomeAssistantView = object
    sys.modules[http.__name__] = http
    communications = types.ModuleType(PACKAGE + ".communications")
    communications.own_person = lambda *_args: True
    sys.modules[communications.__name__] = communications
    storage = types.ModuleType(PACKAGE + ".storage")
    storage._save_places = lambda path, items: saved.append(json.loads(json.dumps(items)))
    sys.modules[storage.__name__] = storage
    spec = importlib.util.spec_from_file_location(PACKAGE + ".geofences", ROOT / "geofences.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


GEO = load_geofences()


class PolygonGeometryTests(unittest.TestCase):
    def test_circular_zone_becomes_an_editable_valid_polygon(self):
        outline = GEO.circle_to_polygon(55.679, 12.08, 100)
        valid = GEO.validate_polygon({"name": "Park", "points": outline})
        self.assertEqual(len(valid["points"]), 16)
        self.assertTrue(GEO.contains_point(outline, 55.679, 12.08))
        self.assertFalse(GEO.contains_point(outline, 55.685, 12.08))

    def test_overlapping_polygons_keep_separate_memberships(self):
        shape = GEO.circle_to_polygon(55.679, 12.08, 100)
        polygons = [{"id": "a", "name": "Park", "points": shape},
                    {"id": "b", "name": "Skole", "points": shape}]
        first, changes = GEO.polygon_membership_changes(None, polygons, 55.679, 12.08)
        self.assertEqual(first, {"a": True, "b": True})
        self.assertFalse(changes)  # first GPS fix is only an initial baseline
        second, changes = GEO.polygon_membership_changes(first, polygons, 55.685, 12.08)
        self.assertEqual(second, {"a": False, "b": False})
        self.assertEqual([(p["id"], state) for p, state in changes],
                         [("a", False), ("b", False)])


class PolygonApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        saved.clear()
        self.runtime = {"entry": types.SimpleNamespace(data={}, options={}),
                        "geofences": []}
        self.sync_calls = 0

        async def sync():
            self.sync_calls += 1

        self.runtime["sync_polygon_entities"] = sync

        async def executor(func, *args):
            return func(*args)

        self.hass = types.SimpleNamespace(
            data={"tiny_family_runtime": self.runtime},
            config=types.SimpleNamespace(path=lambda value: "/tmp/" + value),
            async_add_executor_job=executor,
        )
        self.view = GEO.TinyFamilyGeofencesView(self.hass)

    def request(self, payload, *, admin=True):
        class Request(dict):
            async def json(self):
                return payload
        return Request(hass_user=types.SimpleNamespace(is_admin=admin, id="one"))

    async def test_create_polygon_without_removing_any_circle_zone(self):
        request = self.request({"name": "Hjem", "points": GEO.circle_to_polygon(
            55.679, 12.08, 100)})
        response = await self.view.post(request)
        self.assertEqual(response.status, 201)
        self.assertEqual(len(self.runtime["geofences"]), 1)
        self.assertEqual(self.sync_calls, 1)
        self.assertEqual(saved[-1]["items"][0]["name"], "Hjem")
        self.assertEqual(len(self.runtime["geofences"][0]["id"]), 32)

    async def test_polygon_save_is_forbidden_to_non_admins(self):
        request = self.request({"name": "Hjem", "points": GEO.circle_to_polygon(
            55.679, 12.08, 100)}, admin=False)
        response = await self.view.post(request)
        self.assertEqual(response.status, 403)
        self.assertFalse(self.runtime["geofences"])


if __name__ == "__main__":
    unittest.main()
