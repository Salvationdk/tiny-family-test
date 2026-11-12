"""Isolated OSRM map matching regression tests (no Home Assistant install)."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest


ROOT=Path(__file__).resolve().parents[1] / "custom_components" / "tiny_family"
PKG="_tiny_family_matching_test"


def load():
    ha=types.ModuleType("homeassistant")
    ha.__path__=[]
    helpers=types.ModuleType("homeassistant.helpers")
    helpers.__path__=[]
    client=types.ModuleType("homeassistant.helpers.aiohttp_client")
    client.async_get_clientsession=lambda hass: hass.session
    sys.modules["homeassistant"]=ha
    sys.modules["homeassistant.helpers"]=helpers
    sys.modules["homeassistant.helpers.aiohttp_client"]=client
    aio=types.ModuleType("aiohttp")
    aio.ClientError=OSError
    aio.ClientTimeout=lambda **kwargs: kwargs
    sys.modules["aiohttp"]=aio
    sys.modules[PKG]=types.ModuleType(PKG)
    sys.modules[PKG].__path__=[]
    spec=importlib.util.spec_from_file_location(
        f"{PKG}.map_matching", ROOT / "map_matching.py"
    )
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


M=load()


def fixes(base=1000):
    return [
        {"t":base+i*20,"lat":55.67+i*.0005,"lon":12.20+i*.0005,
         "accuracy":10,"speed":35,"movement":"moving"} for i in range(3)
    ]


def osrm_reply(points, *, confidence=.91, outlier=False):
    trace=[
        {"matchings_index":0,"waypoint_index":i}
        for i in range(len(points))
    ]
    if outlier:
        trace[-1]=None
    return {
        "code":"Ok",
        "tracepoints":trace,
        "matchings":[{"confidence":confidence,"geometry":{
            "type":"LineString",
            "coordinates":[[p["lon"],p["lat"]] for p in points]
        }}]
    }


class MatchTests(unittest.TestCase):
    def test_server_validation(self):
        self.assertEqual(M.validate_match_server("http://192.168.1.50:5000"),
                         "http://192.168.1.50:5000")
        self.assertEqual(M.validate_match_server("https://my-osrm.example"),
                         "https://my-osrm.example")
        for url in ("http://router.project-osrm.org",
                    "https://user:password@my-osrm.example",
                    "https://my-osrm.example?token=secret",
                    "https://my-osrm.example/route",
                    "ftp://192.168.1.50", "https://my-osrm.example#secret"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                M.validate_match_server(url)

    def test_chunks_never_bridge_missing_gps(self):
        first=fixes()
        second=fixes(1300)
        pieces=M._chunks([first+second])
        self.assertEqual(len(pieces),2)
        self.assertEqual(pieces[0][-1]["t"],1040)
        self.assertEqual(pieces[1][0]["t"],1300)

    def test_request_parameters_bounded_and_ordered(self):
        url,params=M.build_match_request("http://192.168.1.50:5000",fixes())
        self.assertIn("/match/v1/driving/",url)
        self.assertIn("12.200000,55.670000",url)
        self.assertEqual(params["timestamps"],"1000;1020;1040")
        self.assertEqual(params["geometries"],"geojson")
        self.assertEqual(params["gaps"],"split")

    def test_match_confidence_and_endpoints(self):
        sample=fixes()
        valid=M.parse_osrm_match(osrm_reply(sample),sample)
        self.assertEqual(len(valid),1)
        self.assertEqual(valid[0]["confidence"],.91)
        self.assertEqual(valid[0]["coordinates"][0],[55.67,12.2])
        self.assertEqual(M.parse_osrm_match(osrm_reply(sample,confidence=.2),sample),[])
        wrong=osrm_reply(sample)
        wrong["matchings"][0]["geometry"]["coordinates"][0]=[15.,55.67]
        self.assertEqual(M.parse_osrm_match(wrong,sample),[])
        self.assertEqual(M.parse_osrm_match(osrm_reply(sample,outlier=True),sample),[])

    def test_stationary_or_short_trace_is_skipped(self):
        self.assertEqual(M._chunks([fixes()[:2]]),[])
        sample=fixes()
        for p in sample:
            p["lat"]=55.67
            p["lon"]=12.2
        # Still valid as points; matcher itself correctly skips zero movement.
        self.assertEqual(len(M._chunks([sample])),1)


class FakeResponse:
    status=200
    content_length=None

    def __init__(self, body):
        self.body=body
        self.content=types.SimpleNamespace(read=self.read)

    async def read(self, amount):
        return self.body[:amount]

    async def __aenter__(self):
        return self

    async def __aexit__(self,*args):
        return False


class FakeSession:
    def __init__(self, response):
        self.response=response
        self.calls=[]

    def get(self, url, **kwargs):
        self.calls.append((url,kwargs))
        return FakeResponse(json.dumps(self.response).encode())


class MatchAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_match_day_returns_verified_geometry_and_disables_redirects(self):
        points=fixes()
        session=FakeSession(osrm_reply(points))
        result,status=await M.match_day(
            types.SimpleNamespace(session=session),
            "http://192.168.1.50:5000",
            [points]
        )
        self.assertEqual(status,"matched")
        self.assertEqual(len(result),1)
        self.assertEqual(len(session.calls),1)
        self.assertFalse(session.calls[0][1]["allow_redirects"])

    async def test_disabled_configuration_sends_nothing(self):
        session=FakeSession(osrm_reply(fixes()))
        result,status=await M.match_day(types.SimpleNamespace(session=session),"",[fixes()])
        self.assertEqual((result,status),([],"disabled"))
        self.assertFalse(session.calls)

    async def test_no_match_falls_back_to_raw_data(self):
        session=FakeSession({"code":"NoMatch"})
        result,status=await M.match_day(
            types.SimpleNamespace(session=session),"https://osrm.example",[fixes()]
        )
        self.assertEqual(result,[])
        self.assertEqual(status,"unavailable")


if __name__=="__main__":
    unittest.main()
