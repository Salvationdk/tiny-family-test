"""The stable, read-only YAML-facing polygon and geography calculation API."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tiny_family"
PKG = "_tf_automation_service_tests"
package = types.ModuleType(PKG)
package.__path__ = []
sys.modules[PKG] = package
geo = types.ModuleType(PKG + ".geofences")


def contains_point(vertices, lat, lon):
    return min(p[0] for p in vertices) < lat < max(p[0] for p in vertices) and (
        min(p[1] for p in vertices) < lon < max(p[1] for p in vertices))


geo.contains_point = contains_point
sys.modules[geo.__name__] = geo
places = types.ModuleType(PKG + ".places")
places.estimate_destination_eta = lambda d, speed: (
    round(d * 1.25 / speed / 60) if d >= 150 and 2.2 <= speed <= 40 else None)
sys.modules[places.__name__] = places
utils = types.ModuleType(PKG + ".utils")
utils._hav = lambda lat, lon, to_lat, to_lon: math.hypot(
    (lat - to_lat) * 111_000, (lon - to_lon) * 111_000)
sys.modules[utils.__name__] = utils
quality_spec = importlib.util.spec_from_file_location(
    PKG + ".gps_quality", ROOT / "gps_quality.py")
quality_module = importlib.util.module_from_spec(quality_spec)
sys.modules[quality_spec.name] = quality_module
quality_spec.loader.exec_module(quality_module)
spec = importlib.util.spec_from_file_location(PKG + ".automation_api", ROOT / "automation_api.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class AutomationApiTests(unittest.TestCase):
    def setUp(self):
        self.shape = [[55.0, 12.0], [55.1, 12.0], [55.1, 12.1], [55.0, 12.1]]
        self.polygons = [
            {"id": "a" * 32, "name": "Arbejde", "points": self.shape},
            {"id": "b" * 32, "name": "Kvarter", "points": self.shape},
        ]

    def test_multiple_overlapping_polygon_matches(self):
        result = module.evaluate_location(self.polygons, {
            "latitude": 55.05, "longitude": 12.05})
        self.assertTrue(result["inside_any_polygon"])
        self.assertEqual(result["polygon_count"], 2)
        self.assertEqual(result["polygons"][0]["entity_id"],
                         "sensor.tiny_family_polygon_" + "a" * 32)

    def test_distance_and_eta_are_optional_and_based_on_supplied_points(self):
        result = module.evaluate_location(self.polygons, {
            "latitude": 55.05, "longitude": 12.05,
            "target_latitude": 55.06, "target_longitude": 12.05,
            "speed_kmh": 18})
        self.assertAlmostEqual(result["distance_km"], 1.11, places=2)
        self.assertGreater(result["eta_minutes"], 0)
        self.assertTrue(result["eta_is_estimate"])

    def test_native_circle_and_polygon_results_are_distinct(self):
        result = module.evaluate_location(self.polygons, {
            "latitude": 55.05, "longitude": 12.05}, circles=[
                {"id": "zone.home", "name": "Hjem", "latitude": 55.05,
                 "longitude": 12.05, "radius_m": 90}])
        self.assertTrue(result["inside_any_area"])
        self.assertEqual(result["circle_count"], 1)
        self.assertEqual(result["circles"][0]["entity_id"], "zone.home")

    def test_motion_estimates_stuck_zero_from_confirmed_displacement(self):
        result = module.analyze_motion({
            "start_latitude": 55.0, "start_longitude": 12.0,
            "end_latitude": 55.01, "end_longitude": 12.0,
            "elapsed_seconds": 60, "accuracy_m": 8,
            "previous_accuracy_m": 8, "reported_speed_mps": 0})
        self.assertEqual(result["speed_source"], "gps_estimate")
        self.assertGreater(result["speed_kmh"], 60)
        self.assertEqual(result["movement"], "moving")

    def test_route_summary_ignores_gps_outage_and_does_not_return_fixes(self):
        fixes = [
            {"timestamp": 100, "latitude": 55.0, "longitude": 12.0,
             "accuracy_m": 8},
            {"timestamp": 160, "latitude": 55.001, "longitude": 12.0,
             "accuracy_m": 8, "speed_mps": 0},
            {"timestamp": 2000, "latitude": 56.0, "longitude": 12.0,
             "accuracy_m": 8},
        ]
        result = module.analyze_route({"fixes": fixes})
        self.assertEqual(result["fix_count"], 3)
        self.assertEqual(result["gps_gaps"], 1)
        self.assertEqual(result["speed_sources"]["gps_estimate"], 1)
        self.assertLess(result["distance_km"], 0.2)
        self.assertNotIn("fixes", result)

    def test_route_rejects_invalid_timestamps_and_bounded_payload(self):
        a = {"timestamp": 160, "latitude": 55, "longitude": 12}
        b = {"timestamp": 100, "latitude": 55.01, "longitude": 12}
        for fixes in ([a, b], [a] * 201, [a]):
            with self.subTest(size=len(fixes)), self.assertRaises(ValueError):
                module.analyze_route({"fixes": fixes})

    def test_invalid_partial_or_nonfinite_coordinates_rejected(self):
        for payload in (
            {"latitude": float("nan"), "longitude": 12.05},
            {"latitude": 55.05, "longitude": 12.05,
             "target_latitude": 55.1},
            {"latitude": 55.05, "longitude": 12.05, "speed_kmh": 20},
            {"latitude": True, "longitude": 12.05},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                module.evaluate_location(self.polygons, payload)


if __name__ == "__main__":
    unittest.main()
