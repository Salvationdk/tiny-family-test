"""Offline regression tests for Tiny Family's embedded road matcher."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tiny_family"
PKG = "_tiny_family_road_tests"


def load_files():
    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    client.async_get_clientsession = lambda hass: hass.session
    sys.modules.update({
        "homeassistant": ha, "homeassistant.helpers": helpers,
        "homeassistant.helpers.aiohttp_client": client,
    })
    aio = types.ModuleType("aiohttp")
    aio.ClientError = OSError
    aio.ClientTimeout = lambda **kwargs: kwargs
    sys.modules["aiohttp"] = aio
    pkg = types.ModuleType(PKG)
    pkg.__path__ = []
    sys.modules[PKG] = pkg
    result = []
    for file in ("map_matching", "road_engine_core", "road_engine"):
        spec = importlib.util.spec_from_file_location(
            f"{PKG}.{file}", ROOT / f"{file}.py"
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        result.append(mod)
    return result


OSRM, CORE, ENGINE = load_files()


def osm_roads(oneway=""):
    return {"elements": [
        {"type": "way", "nodes": [1, 2, 3],
         "tags": {"highway": "residential", "oneway": oneway},
         "geometry": [
             {"lat": 55.670, "lon": 12.200},
             {"lat": 55.670, "lon": 12.202},
             {"lat": 55.670, "lon": 12.204},
         ]},
    ]}


def fixes(reverse=False, begin=1000):
    coords = [12.2004, 12.2020, 12.2036]
    if reverse:
        coords.reverse()
    return [
        {"lat": 55.67003, "lon": lon, "t": begin + i * 25, "accuracy": 12}
        for i, lon in enumerate(coords)
    ]


class RoadCoreTests(unittest.TestCase):
    def test_embedded_match_uses_actual_osm_roads(self):
        result = CORE.snap_trace(fixes(), osm_roads())
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(result[0]["confidence"], .65)
        self.assertEqual(result[0]["start_t"], 1000)
        self.assertEqual(result[0]["end_t"], 1050)
        self.assertTrue(all(abs(lat-55.670) < 1e-6 for lat, lon in result[0]["coordinates"]))

    def test_sparse_companion_fixes_up_to_five_minutes_still_snap(self):
        sparse = fixes()
        for index, fix in enumerate(sparse):
            fix["t"] = 1000 + index * 120
        self.assertEqual(len(ENGINE.road_windows([sparse])), 1)
        matched = CORE.snap_trace(sparse, osm_roads())
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["end_t"], 1240)

    def test_missing_gps_over_five_minutes_is_not_connected(self):
        interrupted = fixes()
        for index, fix in enumerate(interrupted):
            fix["t"] = 1000 + index * 360
        self.assertEqual(ENGINE.road_windows([interrupted]), [])
        self.assertEqual(CORE.snap_trace(interrupted, osm_roads()), [])

    def test_one_way_is_not_reversed(self):
        result = CORE.snap_trace(fixes(reverse=True), osm_roads("yes"))
        self.assertEqual(result, [])

    def test_disconnected_ways_are_not_joined_with_fabricated_line(self):
        geometry = {"elements": [
            {"type": "way", "nodes": [1, 2],
             "tags": {"highway": "residential"},
             "geometry": [{"lat":55.670,"lon":12.200},{"lat":55.670,"lon":12.202}]},
            {"type": "way", "nodes": [3, 4],
             "tags": {"highway": "residential"},
             "geometry": [{"lat":55.670,"lon":12.202},{"lat":55.670,"lon":12.204}]},
        ]}
        self.assertEqual(CORE.snap_trace(fixes(), geometry), [])

    def test_turn_uses_shared_junction_node(self):
        roads = {"elements": [
            {"type": "way", "nodes": [1, 2],
             "tags": {"highway": "residential"},
             "geometry": [{"lat":55.670,"lon":12.200},{"lat":55.670,"lon":12.202}]},
            {"type": "way", "nodes": [2, 3],
             "tags": {"highway": "residential"},
             "geometry": [{"lat":55.670,"lon":12.202},{"lat":55.672,"lon":12.202}]},
        ]}
        track = [
            {"lat":55.67002,"lon":12.2004,"t":1000},
            {"lat":55.67001,"lon":12.2017,"t":1025},
            {"lat":55.6718,"lon":12.20202,"t":1050},
        ]
        result = CORE.snap_trace(track, roads)
        self.assertEqual(len(result), 1)
        self.assertTrue(any(abs(lat-55.670)<1e-6 and abs(lon-12.202)<1e-6
                            for lat, lon in result[0]["coordinates"]))

    def test_invalid_and_private_ways_are_excluded(self):
        self.assertIsNone(CORE.road_graph({"remark": "timeout", "elements": []}))
        roads = osm_roads()
        roads["elements"][0]["tags"]["access"] = "private"
        self.assertEqual(CORE.snap_trace(fixes(), roads), [])

    def test_sparse_two_point_route_is_inference_not_verified_measurement(self):
        first, last = fixes()[0], fixes()[-1]
        last["t"] = 1300
        estimated = CORE.infer_road_gap(first, last, osm_roads())
        self.assertIsNotNone(estimated)
        self.assertEqual(estimated["basis"], "road_network")
        self.assertLessEqual(estimated["confidence"], .62)
        self.assertLess(estimated["confidence"], .65)
        self.assertEqual((estimated["start_t"], estimated["end_t"]), (1000, 1300))
        self.assertGreaterEqual(len(estimated["coordinates"]), 2)
        self.assertTrue(all(lat == 55.67 for lat, _ in estimated["coordinates"]))

    def test_road_estimate_respects_direction_and_plausible_speed(self):
        first, last = fixes()[0], fixes()[-1]
        last["t"] = 1300
        self.assertIsNone(CORE.infer_road_gap(last, first, osm_roads("yes")))
        self.assertIsNone(CORE.infer_road_gap(first, {**last,"t":1001},osm_roads()))
        self.assertIsNone(CORE.infer_road_gap(first, {**last,"t":3001},osm_roads()))
        self.assertIsNone(CORE.infer_road_gap(first, last,
            {"elements": [{**osm_roads()["elements"][0],
                "tags":{"highway":"service","access":"private"}}]}))

    def test_historical_estimate_requires_correct_direction_and_corridor(self):
        first, last = fixes()[0], fixes()[-1]
        last["t"] = 1300
        previous = CORE.snap_trace(fixes(), osm_roads())
        estimated = CORE.infer_historical_gap(first, last, previous)
        self.assertIsNotNone(estimated)
        self.assertEqual(estimated["basis"], "previous_road_history")
        self.assertGreater(estimated["confidence"], .5)
        self.assertIsNone(CORE.infer_historical_gap(last,
            {**first,"t":1600}, previous))
        self.assertIsNone(CORE.infer_historical_gap(first, last, []))

    def test_sparse_pairs_never_bridge_explicit_privacy_discontinuity(self):
        first, last = fixes()[0], fixes()[-1]
        last["t"] = 1300
        self.assertEqual(len(ENGINE.sparse_road_pairs([[first],
            [{**last,"gap_origin":"time"}]])), 1)
        self.assertEqual(ENGINE.sparse_road_pairs([[first],
            [{**last,"gap_origin":"explicit"}]]), [])
        self.assertEqual(len(ENGINE.sparse_road_pairs([[first],
            [{**last,"gap_origin":"explicit"}]],allow_explicit=True)),1)
        self.assertEqual(ENGINE.sparse_road_pairs([[first],
            [{**last,"gap_origin":"implausible"}]]), [])


class FakeResponse:
    def __init__(self, code=200, body=None):
        self.status = code
        self.content_length = None
        self.body = json.dumps(body or osm_roads()).encode()
        self.content = types.SimpleNamespace(read=self.read)

    async def read(self, maximum):
        return self.body[:maximum]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeSession:
    def __init__(self, response=None):
        self.response = response or FakeResponse()
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class FakeHass:
    def __init__(self, response=None):
        self.session = FakeSession(response)

    async def async_add_executor_job(self, function, *args):
        return function(*args)


class RoadNetworkTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_point_sparse_trace_returns_separate_dashed_estimate(self):
        first, last = fixes()[0], fixes()[-1]
        last["t"] = 1300
        hass=FakeHass()
        matched, inferred, status=await ENGINE.match_day_embedded(
            hass,[[first,last]],{},include_inferences=True)
        self.assertEqual(matched, [])
        self.assertEqual(status, "inferred")
        self.assertEqual(len(inferred), 1)
        self.assertEqual(len(hass.session.calls), 1)

    async def test_existing_road_history_avoids_external_network_call(self):
        first, last = fixes()[0], fixes()[-1]
        last["t"] = 1300
        hass=FakeHass()
        past=CORE.snap_trace(fixes(), osm_roads())
        matched, inferred, status=await ENGINE.match_day_embedded(
            hass,[[first,last]],{},include_inferences=True,
            historical_roads=past)
        self.assertEqual(matched, [])
        self.assertEqual(status, "inferred")
        self.assertEqual(inferred[0]["basis"], "previous_road_history")
        self.assertFalse(hass.session.calls)

    async def test_public_road_geometry_fetch_contains_no_raw_gps_or_times(self):
        hass = FakeHass()
        data, status = await ENGINE.match_day_embedded(hass, [fixes()], {})
        self.assertEqual(status, "matched")
        self.assertTrue(data)
        self.assertEqual(len(hass.session.calls), 1)
        url, settings = hass.session.calls[0]
        self.assertTrue(url.startswith("https://"))
        self.assertFalse(settings["allow_redirects"])
        query = settings["data"]["data"]
        self.assertIn('way["highway"', query)
        self.assertNotIn("1000", query)
        self.assertNotIn("1050", query)
        self.assertNotIn("person.", query)
        self.assertNotIn("12.200400", query)

    async def test_cached_road_data_avoids_second_external_query(self):
        hass = FakeHass()
        cache = {}
        await ENGINE.match_day_embedded(hass, [fixes()], cache)
        await ENGINE.match_day_embedded(hass, [fixes()], cache)
        self.assertEqual(len(hass.session.calls), 1)

    async def test_no_points_or_server_error_falls_back(self):
        hass = FakeHass()
        self.assertEqual(await ENGINE.match_day_embedded(hass, [[]], {}),
                         ([], "not_enough_points"))
        self.assertEqual(len(hass.session.calls), 0)
        failing = FakeHass(FakeResponse(429))
        matched, status = await ENGINE.match_day_embedded(failing, [fixes()], {})
        self.assertEqual((matched, status), ([], "unavailable"))
        self.assertEqual(len(failing.session.calls), 1)

    async def test_never_bridges_gaps_or_exceeds_window_budget(self):
        segments = [fixes(begin=1000 + i * 3000) for i in range(11)]
        hass = FakeHass()
        matched, status = await ENGINE.match_day_embedded(hass, segments, {})
        self.assertEqual(status, "partial")
        self.assertLessEqual(len(hass.session.calls), ENGINE.MAX_WINDOWS)
        self.assertTrue(matched)


if __name__ == "__main__":
    unittest.main()
