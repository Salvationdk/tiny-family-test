"""A learned destination inside a Home Assistant zone stays independent."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tiny_family"
PACKAGE = "_tf_zone_destination_tests"


def load_places():
    package = types.ModuleType(PACKAGE)
    package.__path__ = []
    sys.modules[PACKAGE] = package
    const = types.ModuleType(PACKAGE + ".const")
    const.DOMAIN = "tiny_family"
    const.ZONE_SUGGEST_MIN_VISITS = 3
    sys.modules[const.__name__] = const
    utils = types.ModuleType(PACKAGE + ".utils")
    utils._hav = lambda a, b, c, d: ((a-c)**2 + (b-d)**2)**.5 * 111000
    sys.modules[utils.__name__] = utils
    historic = types.ModuleType(PACKAGE + ".historical_prediction")
    historic.history_confidence_boost = lambda *args, **kwargs: 0
    sys.modules[historic.__name__] = historic
    spec = importlib.util.spec_from_file_location(PACKAGE + ".places", ROOT / "places.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ZoneDestinationTests(unittest.TestCase):
    def test_stays_inside_zone_are_separate_destinations(self):
        places = load_places()
        centre = {"lat": 55.67, "lon": 12.2, "label": "Hjem",
                  "visits": 2, "min": 25, "n": 2, "source": "zone"}
        state = {"places": [centre]}
        hass = types.SimpleNamespace(data={"tiny_family": {"person.one": state}})
        places._record_place(hass, "person.one", 55.67018, 12.2, 15)
        self.assertEqual(len(state["places"]), 2)
        learned = state["places"][1]
        self.assertEqual(learned["source"], "learned")
        self.assertEqual(learned["label"], "")
        self.assertEqual(centre["visits"], 2)
        places._record_place(hass, "person.one", 55.67019, 12.2, 10)
        self.assertEqual(len(state["places"]), 2)
        self.assertEqual(learned["visits"], 2)


if __name__ == "__main__":
    unittest.main()
