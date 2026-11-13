"""Phone binding and GPS-drift regression checks without a live HA server."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
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
    def test_zero_phone_speed_uses_plausible_movement_when_accurate(self):
        value, source = quality.resolve_speed_mps(
            0.0, distance_m=150, elapsed_seconds=10,
            accuracy_m=8, previous_accuracy_m=10)
        self.assertEqual(source, "gps_estimate")
        self.assertAlmostEqual(value, 15)

    def test_jitter_is_not_mistaken_for_movement(self):
        self.assertEqual(quality.resolve_speed_mps(
            0, distance_m=18, elapsed_seconds=10,
            accuracy_m=12, previous_accuracy_m=12), (0, "phone"))
        self.assertEqual(quality.resolve_speed_mps(
            None, distance_m=70, elapsed_seconds=400,
            accuracy_m=8, previous_accuracy_m=8), (None, "unavailable"))
        self.assertEqual(quality.resolve_speed_mps(
            None, distance_m=100, elapsed_seconds=10,
            accuracy_m=None, previous_accuracy_m=8), (None, "unavailable"))

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

    def test_zero_reported_speed_does_not_discard_every_car_fix(self):
        state = {"last_t": 100}
        self.assertEqual(quality.screen_gps_drift(
            state, observed_at=130, latitude=55.003, longitude=11,
            distance_m=334, accuracy_m=8, speed_mps=0), "discard")
        self.assertEqual(quality.screen_gps_drift(
            state, observed_at=160, latitude=55.006, longitude=11,
            distance_m=668, accuracy_m=8, speed_mps=0), "rebase")
        state["last_t"] = 160
        self.assertEqual(quality.screen_gps_drift(
            state, observed_at=190, latitude=55.009, longitude=11,
            distance_m=334, accuracy_m=8, speed_mps=0), "accept")

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
        device_mod = types.ModuleType("homeassistant.helpers.device_registry")
        helpers.entity_registry = registry_mod
        helpers.device_registry = device_mod
        sys.modules["homeassistant.helpers.entity_registry"] = registry_mod
        sys.modules["homeassistant.helpers.device_registry"] = device_mod
        cls.registry_mod = registry_mod
        cls.device_mod = device_mod
        cls.binding = load_file("_tf_phone_binding_test", "device_binding.py")

    def setUp(self):
        def peer(entity_id, disabled_by=None, device_id="phone_a"):
            return types.SimpleNamespace(entity_id=entity_id, disabled_by=disabled_by,
                                         device_id=device_id,
                                         platform="mobile_app" if entity_id.startswith("device_tracker") else "sensor")
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
        self.device_mod.async_get = lambda hass: types.SimpleNamespace(
            async_get=lambda device_id: types.SimpleNamespace(
                name="Nicolajs telefon",name_by_user=None,
                manufacturer="Motorola",model="Moto G15")
            if device_id == "phone_a" else None)
        values = {
            "sensor.phone_a_battery_level": "60",
            "binary_sensor.phone_a_power_save": "on",
            "sensor.phone_b_battery_level": "85",
        }
        self.now = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
        states = {k: types.SimpleNamespace(state=v, attributes={}) for k, v in values.items()}
        states["device_tracker.phone_a"] = types.SimpleNamespace(
            name="Din Moto",state="not_home",
            last_updated=self.now-timedelta(seconds=34),
            attributes={"tracking_type":"position", "latitude":55.67,
                        "longitude":11.08,"gps_accuracy":8,"speed":10.0})
        self.states = states
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

    def test_diagnostics_identify_one_phone_and_fresh_gps_without_leaking_coordinates(self):
        result = self.binding.phone_tracker_diagnostic(
            self.hass, "device_tracker.phone_a", self.now)
        self.assertEqual(result["gps_status"], "fresh")
        self.assertEqual(result["tracking_type"], "position")
        self.assertEqual(result["device_name"], "Nicolajs telefon")
        self.assertEqual(result["manufacturer"], "Motorola")
        self.assertTrue(result["is_companion"])
        self.assertEqual(result["age_seconds"], 34)
        self.assertEqual(result["accuracy_m"], 8)
        self.assertEqual(result["phone_speed_kmh"], 36)
        self.assertNotIn("latitude", result)
        self.assertNotIn("longitude", result)

    def test_diagnostics_detect_stale_gps_and_missing_fix(self):
        phone = self.states["device_tracker.phone_a"]
        phone.last_updated = self.now-timedelta(minutes=22)
        self.assertEqual(self.binding.phone_tracker_diagnostic(
            self.hass, "device_tracker.phone_a", self.now)["gps_status"], "stale")
        phone.attributes = {"tracking_type":"position"}
        self.assertEqual(self.binding.phone_tracker_diagnostic(
            self.hass, "device_tracker.phone_a", self.now)["gps_status"], "no_fix")

    def test_duplicate_phone_and_router_are_rejected_but_gps_without_fix_can_be_saved(self):
        self.binding.validate_phone_trackers(
            self.hass, {"person.nicolaj":"device_tracker.phone_a"})
        with self.assertRaisesRegex(ValueError, "only be assigned"):
            self.binding.validate_phone_trackers(self.hass, {
                "person.nicolaj":"device_tracker.phone_a",
                "person.bertram":"device_tracker.phone_a"})
        phone = self.states["device_tracker.phone_a"]
        phone.attributes = {"tracking_type":"connection"}
        with self.assertRaisesRegex(ValueError, "connection-only"):
            self.binding.validate_phone_trackers(
                self.hass, {"person.nicolaj":"device_tracker.phone_a"})
        phone.attributes = {"source_type":"gps"}
        self.binding.validate_phone_trackers(
            self.hass, {"person.nicolaj":"device_tracker.phone_a"})
        # A real Companion phone may be set up before its first GPS fix.
        phone.attributes = {}
        self.binding.validate_phone_trackers(
            self.hass, {"person.nicolaj":"device_tracker.phone_a"})
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.binding.validate_phone_trackers(
                self.hass, {"person.nicolaj":"device_tracker.unknown"})

    def test_setup_and_admin_both_validate_phone_selection(self):
        setup_source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        admin_source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('errors["tracker"] = "not_gps"', setup_source)
        self.assertIn('validate_phone_trackers(self.hass, trackers)', admin_source)
        self.assertIn('"tracker_diagnostics": phone_diagnostics', admin_source)


if __name__ == "__main__":
    unittest.main()
