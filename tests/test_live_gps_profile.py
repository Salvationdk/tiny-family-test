"""Live map must use the selected phone's accepted GPS, not the HA Person cache."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tiny_family"
PKG = "_tf_live_gps_profile_tests"
package = types.ModuleType(PKG)
package.__path__ = []
sys.modules[PKG] = package

aiohttp = sys.modules.setdefault("aiohttp", types.ModuleType("aiohttp"))
aiohttp.web = sys.modules.setdefault("aiohttp.web", types.ModuleType("aiohttp.web"))
sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
sys.modules.setdefault("homeassistant.components", types.ModuleType("homeassistant.components"))
http = types.ModuleType("homeassistant.components.http")
http.HomeAssistantView = object
sys.modules[http.__name__] = http

comm = types.ModuleType(PKG + ".communications")
comm.MAX_POSITION_AGE_SECONDS = 900
comm.own_person = lambda *args: None
comm.current_location = lambda state, now: (
    (state.attributes["latitude"], state.attributes["longitude"])
    if state and 0 <= (now - state.last_updated).total_seconds() <= 900 else None
)
sys.modules[comm.__name__] = comm
companion = types.ModuleType(PKG + ".companion")
companion.companion_readings = lambda *args, **kwargs: {"activity": "unknown"}
sys.modules[companion.__name__] = companion
const = types.ModuleType(PKG + ".const")
const.DOMAIN = "tiny_family"
sys.modules[const.__name__] = const

spec = importlib.util.spec_from_file_location(PKG + ".privacy", ROOT / "privacy.py")
privacy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = privacy
spec.loader.exec_module(privacy)


class LivePhoneProfileTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)
        person = types.SimpleNamespace(
            name="Nicolaj", state="home", last_updated=self.now-timedelta(hours=2),
            attributes={"latitude": 54.0, "longitude": 10.0})
        phone = types.SimpleNamespace(
            name="Phone", state="not_home", last_updated=self.now,
            attributes={"latitude": 55.0, "longitude": 11.0})
        states = {"person.nicolaj": person, "device_tracker.nicolaj_phone": phone}
        runtime = {
            "tracker": "device_tracker.nicolaj_phone",
            "gps_seen_at": self.now.timestamp() - 8,
            "gps_health": "fresh", "last_lat": 55.695,
            "last_lon": 11.088, "speed_kmh": 63.5,
            "speed_source": "gps_estimate", "last_gps_accuracy": 8,
        }
        self.runtime = runtime
        self.hass = types.SimpleNamespace(
            states=types.SimpleNamespace(get=lambda entity: states.get(entity)),
            data={"tiny_family": {"person.nicolaj": runtime}},
        )
        self.config = {"persons": ["person.nicolaj"], "ghost_people": []}

    def profile(self, viewer="person.nicolaj"):
        return privacy.public_profile(self.hass, "person.nicolaj",
                                      self.config, self.now, viewer)

    def test_selected_phone_fix_outweighs_stale_ha_person_entity(self):
        p = self.profile()
        self.assertFalse(p["stale"])
        self.assertEqual((p["latitude"], p["longitude"]), (55.695, 11.088))
        self.assertEqual(p["speed_kmh"], 63.5)
        self.assertEqual(p["speed_source"], "gps_estimate")
        self.assertEqual(p["gps_age_minutes"], 0)

    def test_no_fresh_phone_fix_does_not_fall_back_to_person_as_live(self):
        self.runtime["gps_seen_at"] = self.now.timestamp() - 1000
        p = self.profile()
        self.assertTrue(p["stale"])
        self.assertNotIn("speed_kmh", p)
        self.assertNotEqual((p.get("latitude"), p.get("longitude")), (54.0, 10.0))

    def test_ghost_hides_location_from_other_member(self):
        self.config["ghost_people"] = ["person.nicolaj"]
        p = self.profile(viewer="person.other")
        self.assertTrue(p["ghost"])
        self.assertNotIn("latitude", p)
        self.assertNotIn("speed_kmh", p)

    def test_phone_fix_works_even_if_ha_person_entity_absent(self):
        self.hass.states = types.SimpleNamespace(
            get=lambda entity: None if entity == "person.nicolaj" else None)
        p = self.profile()
        self.assertFalse(p["stale"])
        self.assertEqual(p["latitude"], 55.695)


if __name__ == "__main__":
    unittest.main()
