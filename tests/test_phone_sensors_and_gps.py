"""Phone binding and GPS-drift regression checks without a live HA server."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "tiny_family"


def load_file(name, filename):
    spec = importlib.util.spec_from_file_location(name, COMPONENT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


quality = load_file("_tf_gps_drift_test", "gps_quality.py")


class GpsDriftTests(unittest.TestCase):
    def test_power_save_glitch_then_return_does_not_create_movement(self):
        state = {"last_t": 100, "last_lat": 55.0, "last_lon": 11.0}
        first = quality.screen_gps_drift(
            state, observed_at=160, latitude=55.008, longitude=11.0,
            distance_m=890, accuracy_m=22, speed_mps=0, power_save=True,
        )
        self.assertEqual(first, "discard")
        self.assertIsNotNone(state["gps_suspect"])
        back = quality.screen_gps_drift(
            state, observed_at=220, latitude=55.0002, longitude=11.0,
            distance_m=22, accuracy_m=22, speed_mps=0, power_save=True,
        )
        self.assertEqual(back, "accept")
        self.assertNotIn("gps_suspect", state)

    def test_two_consistent_far_fixes_rebase_without_fabricated_route(self):
        state = {"last_t": 100}
        self.assertEqual(quality.screen_gps_drift(
            state, observed_at=160, latitude=55.01, longitude=11.0,
            distance_m=1112, accuracy_m=20, speed_mps=0, power_save=True), "discard")
        self.assertEqual(quality.screen_gps_drift(
            state, observed_at=220, latitude=55.011, longitude=11.0,
            distance_m=1220, accuracy_m=20, speed_mps=0, power_save=True), "rebase")

    def test_normal_accurate_movement_is_not_filtered(self):
        state = {"last_t": 100}
        self.assertEqual(quality.screen_gps_drift(
            state, observed_at=160, latitude=55.001, longitude=11.0,
            distance_m=111, accuracy_m=10, speed_mps=2, power_save=False), "accept")


class PhoneBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        helpers = sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
        registry_mod = types.ModuleType("homeassistant.helpers.entity_registry")
        helpers.entity_registry = registry_mod
        sys.modules["homeassistant.helpers.entity_registry"] = registry_mod
        cls.registry_mod = registry_mod
        cls.binding = load_file("_tf_phone_binding_test", "device_binding.py")

    def setUp(self):
        def peer(entity_id, disabled_by=None, device_id="phone_a"):
            return types.SimpleNamespace(entity_id=entity_id, disabled_by=disabled_by,
                                         device_id=device_id)
        peers = [
            peer("device_tracker.phone_a"),
            peer("sensor.phone_a_battery_level"),
            peer("sensor.phone_a_detected_activity", disabled_by="user"),
            peer("binary_sensor.phone_a_power_save"),
            peer("sensor.phone_b_battery_level", device_id="phone_b"),
        ]
        self.registry = types.SimpleNamespace(
            async_get=lambda key: next((p for p in peers if p.entity_id == key), None),
            entities={p.entity_id: p for p in peers},
        )
        self.registry_mod.async_get = lambda hass: self.registry
        values = {
            "sensor.phone_a_battery_level": "60",
            "binary_sensor.phone_a_power_save": "on",
            "sensor.phone_b_battery_level": "85",
        }
        states = {k: types.SimpleNamespace(state=v, attributes={}) for k, v in values.items()}
        self.hass = types.SimpleNamespace(states=types.SimpleNamespace(
            get=lambda entity: states.get(entity)))

    def test_only_same_phone_and_enabled_entities(self):
        found = self.binding.companion_device_sensors(self.hass, "device_tracker.phone_a")
        self.assertEqual(found["battery"], "sensor.phone_a_battery_level")
        self.assertEqual(found["power_save"], "binary_sensor.phone_a_power_save")
        self.assertNotIn("activity", found)
        self.assertNotIn("sensor.phone_b_battery_level", found.values())
        details = self.binding.companion_sensor_inventory(self.hass, "device_tracker.phone_a")
        self.assertEqual(details["activity"]["status"], "disabled_in_ha")
        self.assertEqual(details["charging"]["status"], "missing")

    def test_admin_sensor_selection_defaults_on_but_can_disable(self):
        self.assertIn("power_save", self.binding.selected_phone_sensors({}, "person.one"))
        chosen = self.binding.selected_phone_sensors({
            "phone_sensor_selection": {"person.one": ["battery", "power_save"]}}, "person.one")
        self.assertEqual(chosen, ("battery", "power_save"))


if __name__ == "__main__":
    unittest.main()
