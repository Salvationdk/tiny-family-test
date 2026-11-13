"""Regression tests for persisted daily family GPS timelines (no HA install needed)."""
from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


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

    def test_event_anchor_is_preserved_when_route_samples_are_missing(self):
        base=self.now-600
        T.persist_archive(self.path,activity={"person.one":[{
            "id":"b"*32,"kind":"trip","started_at":base-240,
            "ended_at":base,"duration_min":4,"distance_km":1.1,
            "private":False,"start_lat":55.67,"start_lon":12.2,
            "end_lat":55.68,"end_lon":12.21,
        }]})
        visible=T.query_day(self.path,"person.one",base-400,base+1,
                            viewer="person.two")
        self.assertEqual(visible["points_count"],0)
        self.assertEqual(visible["events"][0]["start_lat"],55.67)
        self.assertEqual(visible["events"][0]["end_lon"],12.21)

    def test_private_event_anchor_is_not_visible_to_other_people(self):
        base=self.now-600
        T.persist_archive(self.path,activity={"person.one":[{
            "id":"c"*32,"kind":"stay","started_at":base-600,
            "ended_at":base,"duration_min":10,"private":True,
            "start_lat":55.67,"start_lon":12.2,
        }]})
        stranger=T.query_day(self.path,"person.one",base-800,base+1,
                             viewer="person.two")
        owner=T.query_day(self.path,"person.one",base-800,base+1,
                          viewer="person.one")
        self.assertEqual(stranger["events"],[])
        self.assertEqual(owner["events"][0]["start_lat"],55.67)

    def test_old_events_table_is_upgraded_without_removing_events(self):
        old_path=Path(self.tmp.name)/"old.sqlite3"
        base=self.now-600
        with sqlite3.connect(old_path) as conn:
            conn.execute("""CREATE TABLE events (
              id TEXT PRIMARY KEY, person TEXT NOT NULL, kind TEXT NOT NULL,
              started_at REAL NOT NULL, ended_at REAL NOT NULL,
              duration_min INTEGER NOT NULL, distance_km REAL NOT NULL,
              max_speed_kmh REAL NOT NULL, label TEXT NOT NULL,
              gap INTEGER NOT NULL, private INTEGER NOT NULL)""")
            conn.execute("""INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
              ("d"*32,"person.one","trip",base-180,base,3,0.5,35,"",0,0))
        T.initialize_archive(old_path,now=self.now)
        result=T.query_day(old_path,"person.one",base-200,base+1,
                           viewer="person.one")
        self.assertEqual(result["summary"]["trips"],1)
        self.assertIsNone(result["events"][0]["start_lat"])

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
        self.assertEqual(theirs["segments"][1][0]["gap_origin"], "explicit")
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

    def test_time_gap_is_distinguished_from_hidden_or_invalid_jump(self):
        base=self.now-1500
        short=T.build_day([
            self.sample(base),self.sample(base+600,55.67,12.202)],[])
        self.assertEqual(short["segments"][1][0]["gap_origin"], "time")
        self.assertEqual(short["gps_diagnostics"]["gap_causes"]["time"],1)
        explicitly_broken=T.build_day([
            self.sample(base),self.sample(base+600,55.67,12.202,gap=True)],[])
        self.assertEqual(explicitly_broken["segments"][1][0]["gap_origin"],"explicit")

    def test_stationary_speed_sensor_during_movement_is_diagnosed(self):
        base=self.now-1500
        points=[self.sample(base+30*i,55.67,12.200+i*.0002,speed=0)
                for i in range(12)]
        report=T.build_day(points,[])
        self.assertEqual(report["gps_diagnostics"]["speed_health"],
                         "zero_despite_movement")
        self.assertEqual(report["gps_diagnostics"]["moving_speed_samples"],0)
        self.assertGreater(report["summary"]["distance_km"],.1)

    def test_daily_text_report_distinguishes_measured_and_inferred_motion(self):
        start=self.now-1800
        # 4 min of walking and 4 min of faster travel, always with actual
        # samples. Nobody claims a GPS-based mode is verified transport.
        samples=[self.sample(start+i*60,55.67,12.20+i*.00004,speed=5)
                 for i in range(5)]
        samples.extend(self.sample(start+(4+i)*60,55.67,12.20016+i*.006,
                                   speed=35) for i in range(1,5))
        day=T.build_day(samples,[{"kind":"stay","started_at":start-480,
                                  "ended_at":start-180,"duration_min":5,
                                  "label":"Skolen","distance_km":0,
                                  "max_speed_kmh":0,"gap":False}])
        report=T.build_daily_report(day,start-600,start+900)
        self.assertEqual(report["summary"]["walking_minutes"],4)
        self.assertGreater(report["summary"]["driving_minutes"],0)
        self.assertGreater(report["summary"]["walking_avg_kmh"],0)
        self.assertGreater(report["summary"]["driving_avg_kmh"],20)
        self.assertGreater(report["summary"]["max_recorded_speed_kmh"],30)
        self.assertTrue(any(r["label"]=="Skolen" and r["source"]=="archive"
                            for r in report["items"]))
        self.assertTrue(any(r["mode"]=="driving" and r["source"]=="gps"
                            for r in report["items"]))

    def test_daily_text_report_uses_shared_place_and_stays_within_gps_gaps(self):
        start=self.now-1800
        samples=[self.sample(start+i*60,55.67,12.2,speed=0,movement="stationary")
                 for i in range(6)]
        samples.extend([self.sample(start+1800,55.68,12.3,speed=0,gap=True)])
        day=T.build_day(samples,[])
        report=T.build_daily_report(day,start-60,start+2100,
          shared_places=[{"name":"Hjem","latitude":55.67,"longitude":12.2}])
        self.assertEqual(report["summary"]["stopped_minutes"],5)
        self.assertTrue(any(r["kind"]=="stay" and r["label"]=="Hjem"
                            for r in report["items"]))
        self.assertEqual(report["summary"]["gps_gaps"],1)
        self.assertTrue(any(r["kind"]=="gap" for r in report["items"]))
        self.assertEqual(report["summary"]["gps_distance_km"],0)

    def test_daily_text_report_labels_saved_trip_from_shared_destinations(self):
        start=self.now-1200
        day=T.build_day([],[{"kind":"trip","started_at":start,
                             "ended_at":start+600,"duration_min":10,
                             "start_lat":55.67,"start_lon":12.2,
                             "end_lat":55.68,"end_lon":12.3,
                             "distance_km":2.2,"max_speed_kmh":38,
                             "gap":False}])
        places=[{"name":"Hjem","latitude":55.67,"longitude":12.2},
                {"name":"Arbejde","latitude":55.68,"longitude":12.3}]
        report=T.build_daily_report(day,start-60,start+900,shared_places=places)
        self.assertEqual(report["items"][0]["label"],"Hjem → Arbejde")
        self.assertEqual(report["summary"]["archived_trip_distance_km"],2.2)

    def test_daily_text_report_respects_historical_private_fix_filter(self):
        start=self.now-1000
        rows=[self.sample(start,55.67,12.2,private=True),
              self.sample(start+60,55.68,12.3,private=True)]
        T.persist_archive(self.path,rows)
        other=T.query_day(self.path,"person.one",start-1,start+90,
                          viewer="person.two")
        diary=T.build_daily_report(other,start-1,start+90)
        self.assertEqual(diary["summary"]["gps_points"],0)
        self.assertEqual(diary["items"],[])

    def test_daily_text_report_does_not_misstate_missing_sensor_speed(self):
        start=self.now-1000
        samples=[self.sample(start+i*30,55.67,12.200+i*.0004,speed=0)
                 for i in range(12)]
        day=T.build_day(samples,[])
        diary=T.build_daily_report(day,start-60,start+400)
        self.assertEqual(diary["summary"]["speed_health"],"zero_despite_movement")
        self.assertIsNone(diary["summary"]["max_recorded_speed_kmh"])
        self.assertGreater(diary["summary"]["walking_minutes"],0)

    def test_admin_can_read_private_member_diary_without_person_binding(self):
        now=datetime.now(timezone.utc)
        ts=now.timestamp()-120
        T.persist_archive(self.path,[{**self.sample(ts),"person":"person.two",
                                      "private":True}])
        cfg={"persons":["person.one","person.two"],
             "owners":{"person.one":"ordinary"},
             "ghost_people":["person.two"],"timeline_retention_days":365,
             "map_matching_enabled":True,"map_matching_backend":"builtin"}
        entry=types.SimpleNamespace(data=cfg,options={})
        class Hass:
            data={"tiny_family_runtime":{"entry":entry,"timeline_path":self.path}}
            config=types.SimpleNamespace(time_zone="UTC")
            async def async_add_executor_job(self,func,*args):
                return func(*args)
        class Request(dict):
            def __init__(self,user):
                super().__init__(hass_user=user)
                self.query={"person":"person.two","date":now.date().isoformat(),
                            "view":"report"}
        view=T.TinyFamilyTimelineView(Hass())
        response=lambda payload,status=200,headers=None:(status,payload)
        with patch.object(T.web,"json_response",side_effect=response):
            allowed=asyncio.run(view.get(Request(types.SimpleNamespace(
                id="admin",is_admin=True))))
            denied=asyncio.run(view.get(Request(types.SimpleNamespace(
                id="ordinary",is_admin=False))))
            self.assertEqual(allowed[0],200)
            self.assertEqual(allowed[1]["summary"]["gps_points"],1)
            self.assertEqual(denied[0],403)
            cfg["ghost_people"]=[]
            public=asyncio.run(view.get(Request(types.SimpleNamespace(
                id="ordinary",is_admin=False))))
            self.assertEqual(public[0],200)
            self.assertEqual(public[1]["summary"]["gps_points"],0)

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

    def test_historical_road_cache_is_isolated_by_viewer_and_date(self):
        path=[[55.67,12.200],[55.67,12.202],[55.67,12.204]]
        owner=[{"start_t":self.now-300,"end_t":self.now-280,
                "coordinates":path}]
        other=[{"start_t":self.now-300,"end_t":self.now-280,
                "coordinates":[[55.69,12.3],[55.69,12.302]]}]
        for viewer, lines in (("person.one",owner),("person.two",other)):
            T.save_matched_day(self.path,"person.one","2026-11-09",
                               viewer,"hash",lines,"matched")
        self.assertEqual(T.earlier_matched_roads(self.path,"person.one",
            "2026-11-10","person.one"),owner)
        self.assertEqual(T.earlier_matched_roads(self.path,"person.one",
            "2026-11-10","person.two"),other)
        self.assertEqual(T.earlier_matched_roads(self.path,"person.one",
            "2026-11-09","person.one"),[])


class TimelineApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_history_returns_before_slow_road_match_and_overlay_is_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"timeline.sqlite"
            now=datetime.now(timezone.utc).timestamp()
            T.initialize_archive(path,now=now)
            T.persist_archive(path,[
                {"person":"person.one","ts":now-120+idx*30,
                 "lat":55.67,"lon":12.2+idx*.0002,"speed":30,
                 "battery":74,"movement":"moving","accuracy":8,
                 "stay_min":0,"gap":False,"private":False}
                for idx in range(3)
            ])
            entry=types.SimpleNamespace(data={"persons":["person.one"],
                "owners":{"person.one":"owner1"},
                "map_matching_enabled":True,"map_matching_backend":"builtin"},
                options={})
            runtime={"entry":entry,"timeline_path":path,"timeline_pending":[]}
            async def exec_job(fn,*args):return fn(*args)
            hass=types.SimpleNamespace(
                data={"tiny_family_runtime":runtime},
                config=types.SimpleNamespace(time_zone="UTC"),
                async_add_executor_job=exec_job,
            )
            view=T.TinyFamilyTimelineView(hass)
            user=types.SimpleNamespace(id="owner1")
            day=datetime.fromtimestamp(now,timezone.utc).date().isoformat()
            class Request(dict):
                def __init__(self,query):
                    super().__init__({"hass_user":user})
                    self.query=query
            matches=[]
            async def fake_match(*args,**kwargs):
                matches.append(True)
                return ([{"start_t":now-120,"end_t":now-60,
                          "coordinates":[[55.67,12.2],[55.67,12.201]]}],
                        [],"matched")
            with patch.object(T.web,"json_response",lambda data,**kw:data,
                              create=True), patch.object(T,"match_day_embedded",fake_match):
                raw=await view.get(Request({"person":"person.one",
                                            "date":day,"map_match":"0"}))
                self.assertEqual(raw["points_count"],3)
                self.assertEqual(raw["matched_segments"],[])
                self.assertFalse(matches,"Loading a date must not run network road matching")
                overlay=await view.get(Request({"person":"person.one",
                                                "date":day,"phase":"matching"}))
                self.assertEqual(len(matches),1)
                self.assertEqual(overlay["matching_status"],"matched")
                self.assertIn("matched_segments",overlay)
                self.assertNotIn("segments",overlay,
                    "Road-overlay response must never resend raw personal GPS")


if __name__=="__main__":
    unittest.main()
