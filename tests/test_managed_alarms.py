"""Regression tests for Tiny Family-owned alerts and legacy HA automation cleanup.

No real family data or Home Assistant configuration is required.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "tiny_family"
PANEL = COMPONENT / "frontend" / "tiny-family-panel.js"

spec = importlib.util.spec_from_file_location(
    "_tiny_family_alerts_under_test", COMPONENT / "automation_engine.py"
)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class NativeAlertTests(unittest.TestCase):
    def test_battery_hysteresis(self):
        state = {}
        self.assertEqual(engine.update_battery(state, 45), [])
        self.assertEqual(engine.update_battery(state, 19), [
            ("battery_low", {"battery": 19})
        ])
        self.assertEqual(engine.update_battery(state, 14), [])
        self.assertEqual(engine.update_battery(state, 26), [])
        self.assertEqual(engine.update_battery(state, 18), [
            ("battery_low", {"battery": 18})
        ])

    def test_speed_requires_two_credible_samples(self):
        state = {}
        self.assertEqual(engine.update_speed(state, 133, 12, 100, 130), [])
        self.assertEqual(engine.update_speed(state, 136, 12, 107, 130), [
            ("speed_warning", {"speed_kmh": 136, "limit_kmh": 130})
        ])
        self.assertEqual(engine.update_speed(state, 142, 12, 115, 130), [])
        self.assertEqual(engine.update_speed(state, 119, 12, 120, 130), [])
        self.assertEqual(engine.update_speed(state, 131, 12, 125, 130), [])

    def test_alerts_are_integration_owned(self):
        source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("update_battery(state, battery)", source)
        self.assertIn("update_speed(", source)
        self.assertIn("emit_alert(", source)
        self.assertIn('hass.bus.async_fire("tiny_family_"', source)
        self.assertIn("notify_family(hass, cfg, person, event_name, details)", source)
        self.assertIn('"_append_history"'.strip('"'), source)


class LegacyAlarmMigrationTests(unittest.TestCase):
    def test_deactivation_is_explicit_and_not_destructive(self):
        panel = PANEL.read_text(encoding="utf-8")
        for entity_id in (
            "automation.person_timeline_lavt_batteri",
            "automation.person_timeline_fartalarm",
        ):
            self.assertIn(entity_id, panel)
        self.assertIn('makeGroup("Alarmer og fartgrænser"', panel)
        self.assertIn("managedAlerts,autoLabel,categoryBox,speedLabel", panel)
        self.assertIn('window.confirm("Deaktivere de gamle', panel)
        self.assertIn('callService("automation","turn_off"', panel)
        self.assertNotIn('callService("automation","turn_on"', panel)
        self.assertNotIn('callService("automation","remove"', panel)

    def test_canonical_domain_and_no_old_integration_directory(self):
        import json
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["domain"], "tiny_family")
        self.assertFalse((ROOT / "custom_components" / "person_timeline").exists())
        source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('migrate_local_json_once', source)

    def test_versions_match(self):
        import json
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        constants = (COMPONENT / "const.py").read_text(encoding="utf-8")
        self.assertEqual(manifest["version"], "0.8.4")
        self.assertIn('CARD_VERSION = "0.8.4"', constants)


if __name__ == "__main__":
    unittest.main()
