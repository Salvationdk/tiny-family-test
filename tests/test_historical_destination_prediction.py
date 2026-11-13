"""Historic, repeated real paths outweigh fallback direction-only guesses."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "tiny_family"
PKG = "_tf_history_destination_test"


def load_modules():
    package = types.ModuleType(PKG)
    package.__path__ = []
    sys.modules[PKG] = package
    const = types.ModuleType(PKG + ".const")
    const.DOMAIN = "tiny_family"
    const.ZONE_SUGGEST_MIN_VISITS = 3
    sys.modules[const.__name__] = const
    result = []
    for name in ("utils", "historical_prediction", "places"):
        spec = importlib.util.spec_from_file_location(PKG + "." + name,
                                                      COMPONENT / (name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        result.append(mod)
    return result


UTILS, HIST, PLACES = load_modules()


class HistoricalPredictionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "timeline.sqlite3"
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE fixes(person TEXT, ts REAL, lat REAL, lon REAL, gap INTEGER)")
            base = datetime(2026, 11, 9, 7, tzinfo=timezone.utc)
            for day in range(3):
                start = base + timedelta(days=day)
                for minute, lat in ((0,54.989),(5,54.992),(10,54.996),
                                    (15,54.9986),(20,54.9998)):
                    conn.execute("INSERT INTO fixes VALUES (?,?,?,?,?)", (
                        "person.one", (start+timedelta(minutes=minute)).timestamp(),
                        lat, 11.0, 0))
        self.place = {"lat":55.0,"lon":11.0,"label":"Arbejde","visits":3}

    def tearDown(self):
        self.tmp.cleanup()

    def test_repeated_arrivals_produce_local_time_and_route_signatures(self):
        patterns = HIST.load_historical_patterns(
            self.path, "person.one", [self.place], "Europe/Copenhagen",
            now_ts=datetime(2026,11,13,tzinfo=timezone.utc).timestamp(),
        )
        self.assertEqual(len(patterns), 1)
        self.assertEqual(len(patterns[0]["arrivals"]), 3)
        self.assertTrue(all(row["path"] for row in patterns[0]["arrivals"]))

    def test_history_takes_priority_but_fallback_still_works(self):
        base = datetime(2026, 11, 12, 7, tzinfo=timezone.utc).timestamp()
        current = [(base,54.990,11.0),(base+200,54.994,11.0),
                   (base+400,54.997,11.0)]
        state = {"recent":current,"places":[self.place],
                 "prediction_timezone":"Europe/Copenhagen",
                 "prediction_speed_mps":10}
        fallback = PLACES._predict(state)
        self.assertIsNotNone(fallback)
        base_confidence = state["destination_confidence"]
        state["history_patterns"] = HIST.load_historical_patterns(
            self.path, "person.one", [self.place], "Europe/Copenhagen",
            now_ts=datetime(2026,11,13,tzinfo=timezone.utc).timestamp(),
        )
        prediction = PLACES._predict(state)
        self.assertEqual(prediction[0]["label"], "Arbejde")
        self.assertGreater(state["destination_confidence"], base_confidence)
        self.assertGreaterEqual(state["destination_confidence"], 0.95)


if __name__ == "__main__":
    unittest.main()
