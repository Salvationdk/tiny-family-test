"""Verify new installs and legacy upgrades default to embedded matching."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONST = ROOT / "custom_components" / "tiny_family" / "const.py"
spec = importlib.util.spec_from_file_location("_tf_road_defaults", CONST)
defaults = importlib.util.module_from_spec(spec)
spec.loader.exec_module(defaults)


class DefaultRoadMatchingTests(unittest.TestCase):
    def test_existing_untouched_false_default_is_upgraded_once(self):
        previous_data = {"map_matching_enabled": False,
                         "map_matching_backend": "builtin"}
        options = {"timeline_retention_days": 365}
        updated = defaults.default_road_matching_options(previous_data, options)
        self.assertEqual(updated["map_matching_enabled"], True)
        self.assertEqual(updated["map_matching_backend"], "builtin")
        self.assertEqual(updated["timeline_retention_days"], 365)
        self.assertNotIn("map_matching_enabled", options)

    def test_explicit_admin_disabled_choice_is_untouched(self):
        self.assertIsNone(defaults.default_road_matching_options(
            {"map_matching_enabled": False},
            {"map_matching_enabled": False, "map_matching_backend": "builtin"}))

    def test_enabled_or_external_backend_choice_is_untouched(self):
        self.assertIsNone(defaults.default_road_matching_options(
            {}, {"map_matching_enabled": True, "map_matching_backend": "osrm"}))

    def test_configuration_and_startup_use_default_migration(self):
        flow = (ROOT / "custom_components/tiny_family/config_flow.py").read_text()
        setup = (ROOT / "custom_components/tiny_family/__init__.py").read_text()
        self.assertIn('"map_matching_enabled": True', flow)
        self.assertIn('default_road_matching_options(entry.data, entry.options)', setup)
        self.assertIn('async_update_entry(entry, options=upgraded_options)', setup)


if __name__ == "__main__":
    unittest.main()
