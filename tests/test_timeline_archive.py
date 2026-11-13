"""Regression tests for persisted daily family GPS timelines (no HA install needed)."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tiny_family"
PKG = "_tiny_family_archive_test"


def load_timeline_module():
    sys.modules[PKG] = types.ModuleType(PKG)
    sys.modules[PKG].__path__ = []
    sys.modules[f"{PKG}.communications"] = types.SimpleNamespace(
        own_person=lambda uid, people, owners: next(
            (person for person in people if owners.get(person) == uid), None
        )
    )
    if "aiohttp" not in sys.modules:
        sys.modules["aiohttp"] = types.ModuleType("aiohttp")
    if "aiohttp.web" not in sys.modules:
        sys.modules["aiohttp.web"] = types.ModuleType("aiohttp.web")
    sys.modules["aiohttp"].web = sys.modules["aiohttp.web"]
    if "homeassistant" not in sys.modules:
        sys.modules["homeassistant"] = types.ModuleType("homeassistant")
        sys.modules["homeassistant"].__path__ = []
    if "homeassistant.components" not in sys.modules:
        sys.modules["homeassistant.components"] = types.ModuleType("homeassistant.components")
        sys.modules["homeassistant.components"].__path__ = []
    sys.modules["homeassistant.components.http"] = types.SimpleNamespace(
        HomeAssistantView=object
    )
    # Timeline's optional OSRM dependency is outside the SQLite archive tests.
    async def no_match(*args, **kwargs):
        return [], "disabled"
    sys.modules[f"{PKG}.map_matching"] = types.SimpleNamespace(match_day=no_match)
    sys.modules[f"{PKG}.road_engine"] = types.SimpleNamespace(match_day_embedded=no_match)
    spec = importlib.util.spec_from_file_location(f"{PKG}.timeline", ROOT / "timeline.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


T = load_timeline_module()


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name) / "timeline.sqlite3"
        self.now=datetime(2026,11,9,12,tzinfo=timezone.utc).timestamp()
        T.initialize_archive(self.path,now=self.now)

    def tearDown(self):
        self.tmp.cleanup()

    def sample(self, ts, lat=55.6700, lon=12.2000, **extra):
        return {"person":"person.one","ts":ts,"lat":lat,"lon":lon,
                "speed":extra.get("speed",15),"battery":extra.get("battery",74),
                "movement":extra.get("movement","moving"),
                "accuracy":12,"stay_min":extra.get("stay_min",0),
                "gap":extra.get("gap",False),"private":extra.get("private",False)}

    def test_five_second_fix_sampling_preserves_bends(self):
        buf=[]
        last={}
        base=self.now-300
        for offset in (0,6,12):
            self.assertTrue(T.enqueue_fix(buf,person="person.one",
                ts=base+offset,lat=55.67+offset*0.0001,lon=12.2,
                speed_kmh=40,battery=74,movement="moving",
                accuracy=8,stay_min=0,gap=False,private=False,
                last_samples=last))
        self.assertEqual(len(buf),3)
        T.persist_archive(self.path,buf)
        # Save/load a second time (restart), routes must still be present.
        T.initialize_archive(self.path,now=self.now)
        result=T.query_day(self.path,"person.one",base-1,base+60,
                           viewer="person.one")
        self.assertEqual(result["points_count"],3)
        self.assertEqual(len(result["segments"][0]),3)

    def test_old_route_and_activity_migration_preserves_history(self):
        base=self.now-600
        routes={"person.one":[{"ts":base,"lat":55.67,"lon":12.2,
                               "private":False,"gap":False}]}
        events={"person.one":[{"id":"f"*32,"kind":"stay",
            "started_at":base-1800,"ended_at":base,
            "duration_min":30,"label":"Arbejdsplads",
            "private":False}]}
        T.initialize_archive(self.path,routes,events,now=self.now)
        day=T.query_day(self.path,"person.one",base-2500,base+1,
                        viewer="person.one")
        self.assertEqual(day["points_count"],1)
        self.assertEqual(day["summary"]["stays"],1)
        self.assertEqual(day["events"][0]["label"],"Arbejdsplads")

    def test_private_fix_creates_visible_gap_for_other_family(self):
        base=self.now-800
        items=[
            self.sample(base,55.67,12.20),
            self.sample(base+20,55.671,12.201,private=True),
            self.sample(base+40,55.672,12.202)
        ]
        T.persist_archive(self.path,items)
        theirs=T.query_day(self.path,"person.one",base-5,base+60,
                           viewer="person.two")
        own=T.query_day(self.path,"person.one",base-5,base+60,
                        viewer="person.one")
        self.assertEqual(theirs["points_count"],2)
        self.assertEqual(len(theirs["segments"]),2)
        self.assertEqual(own["points_count"],3)
        self.assertEqual(len(own["segments"]),1)

    def test_distant_fixes_do_not_create_fabricated_road(self):
        base=self.now-1500
        points=[self.sample(base),
                self.sample(base+700,55.69,12.3)]
        result=T.build_day(points,[])
        self.assertEqual(result["points_count"],2)
        self.assertEqual(len(result["segments"]),2)
        self.assertEqual(result["summary"]["distance_km"],0)

    def test_calendar_day_uses_local_timezone_and_dst(self):
        now=datetime(2026,11,9,tzinfo=timezone.utc)
        start,end=T.day_window("2026-10-25","Europe/Copenhagen",now=now)
        self.assertEqual(end-start,25*3600)
        with self.assertRaises(ValueError):
            T.day_window("2026-11-10","Europe/Copenhagen",now=now)

    def test_erasure_is_scoped_to_person_and_data_kind(self):
        base=self.now-900
        one=self.sample(base)
        two={**self.sample(base), "person":"person.two"}
        T.persist_archive(self.path,[one,two])
        removed=T.delete_archive(self.path,"person.one",routes=True)
        self.assertEqual(removed["fixes"],1)
        self.assertEqual(T.archive_stats(self.path,"person.one")["fixes"],0)
        self.assertEqual(T.archive_stats(self.path,"person.two")["fixes"],1)

    def test_speed_battery_stay_are_preserved_per_fix(self):
        base=self.now-300
        T.persist_archive(self.path,[self.sample(base,
            movement="stationary",speed=0,battery=39,stay_min=52)])
        day=T.query_day(self.path,"person.one",base-10,base+10,
                        viewer="person.one")
        point=day["segments"][0][0]
        self.assertEqual((point["speed"],point["battery"],point["stay_min"]),
                         (0.0,39,52))

    def test_old_data_outside_retention_is_pruned(self):
        too_old=self.now-(T.RETENTION_DAYS+2)*86400
        T.persist_archive(self.path,[self.sample(too_old)])
        T.initialize_archive(self.path,now=self.now)
        self.assertEqual(T.archive_stats(self.path,"person.one")["fixes"],0)

    def test_admin_can_choose_a_shorter_retention(self):
        old=self.now-80*86400
        T.persist_archive(self.path,[self.sample(old)])
        T.initialize_archive(self.path,now=self.now,retention_days=60)
        self.assertEqual(T.archive_stats(self.path,"person.one")["fixes"],0)
        with self.assertRaises(ValueError):
            T.day_window("2026-08-01","Europe/Copenhagen",
                         now=datetime.fromtimestamp(self.now,timezone.utc),
                         retention_days=60)
        with self.assertRaises(ValueError):
            T.validate_retention_days(10000)

    def test_road_overlay_is_cached_per_viewer_and_erased_with_route(self):
        source=T.match_fingerprint([[{"t":self.now-100,"lat":55,"lon":11}]],"builtin")
        line=[{"start_t":self.now-100,"end_t":self.now-90,"points":[[55,11],[55.1,11.1]]}]
        T.save_matched_day(self.path,"person.one","2026-11-09","person.one",
                           source,line,"matched")
        self.assertEqual(T.read_matched_day(self.path,"person.one","2026-11-09",
                                            "person.one",source),(line,"matched"))
        self.assertIsNone(T.read_matched_day(self.path,"person.one","2026-11-09",
                                             "person.two",source))
        self.assertIsNone(T.read_matched_day(self.path,"person.one","2026-11-09",
                                             "person.one","different-hash"))
        T.delete_archive(self.path,"person.one",routes=True)
        self.assertIsNone(T.read_matched_day(self.path,"person.one","2026-11-09",
                                             "person.one",source))


if __name__=="__main__":
    unittest.main()
