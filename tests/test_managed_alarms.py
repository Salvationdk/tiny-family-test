"""Regression tests for Tiny Family-owned alerts and legacy HA automation cleanup.

No real family data or Home Assistant configuration is required.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
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

    def test_battery_saver_warns_above_30_once_with_cooldown(self):
        state={"battery_percent":67}
        self.assertEqual(engine.update_battery_saver_warning(state,False,0),[])
        expected=[("battery_saver_warning",{"battery":67})]
        self.assertEqual(engine.update_battery_saver_warning(state,True,10),expected)
        self.assertEqual(engine.update_battery_saver_warning(state,True,20),[])
        self.assertEqual(engine.update_battery_saver_warning(state,False,40),[])
        self.assertEqual(engine.update_battery_saver_warning(state,True,100),[])
        self.assertEqual(engine.update_battery_saver_warning(state,False,21700),[])
        self.assertEqual(engine.update_battery_saver_warning(state,True,21710),expected)

    def test_unknown_sensor_or_low_battery_does_not_trigger(self):
        state={"battery_percent":30}
        self.assertEqual(engine.update_battery_saver_warning(state,True,0),[])
        state["battery_percent"]=50
        self.assertEqual(engine.update_battery_saver_warning(state,None,10),[])
        # Once power saver is known to be active above 30%, warn on transition.
        self.assertEqual(engine.update_battery_saver_warning(state,True,20),[
            ("battery_saver_warning",{"battery":50})])
        self.assertEqual(engine.update_battery_saver_warning(state,False,30),[])
        self.assertEqual(engine.update_battery_saver_warning(state,True,40),[])
        # Initial observation of already-on saver remains silent after startup.
        self.assertEqual(engine.update_battery_saver_warning(
            {"battery_percent":50},True,20),[])
        self.assertIn("GPS",engine.message_for_event(
            "battery_saver_warning","Test",{"battery":50})[1])

    def test_power_saver_alert_is_self_targeted_in_source(self):
        source=(COMPONENT / "automation_engine.py").read_text(encoding="utf-8")
        self.assertIn('recipients = [person] if event == "battery_saver_warning" else selected',source)
        self.assertIn('"battery_saver_warning"',source)


class BatterySaverDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_warning_goes_only_to_affected_owner_not_other_family(self):
        package="_tf_alert_delivery_tests"
        sys.modules[package]=types.ModuleType(package)
        sys.modules[package].__path__=[]
        sys.modules[package+".communications"]=types.SimpleNamespace(
            check_target=lambda target,services,entities: target.startswith("notify.mobile_app_")
        )
        spec=importlib.util.spec_from_file_location(
            package+".automation_engine",COMPONENT/"automation_engine.py")
        delivery_engine=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=delivery_engine
        spec.loader.exec_module(delivery_engine)
        calls=[]
        async def deliver(*args,**kwargs):
            calls.append((args,kwargs))
        hass=types.SimpleNamespace(
            states=types.SimpleNamespace(
                get=lambda person:types.SimpleNamespace(name=person),
                async_all=lambda domain:[],
            ),
            services=types.SimpleNamespace(
                async_services=lambda:{"notify":{"mobile_app_one":{},
                                           "mobile_app_two":{}}},
                async_call=deliver,
            ),
        )
        config={"auto_notifications_enabled":True,
                "notification_events":["battery_saver_warning","battery_low"],
                "persons":["person.one","person.two"],
                "owners":{"person.one":"owner1","person.two":"owner2"},
                "notification_targets":{"person.one":"notify.mobile_app_one",
                                        "person.two":"notify.mobile_app_two"}}
        result=await delivery_engine.notify_family(hass,config,"person.one",
                                              "battery_saver_warning",{"battery":65})
        self.assertEqual(result["sent"],1)
        self.assertEqual([args[1] for args,_ in calls],["mobile_app_one"])
        calls.clear()
        await delivery_engine.notify_family(hass,config,"person.one",
                                           "battery_low",{"battery":19})
        self.assertEqual([args[1] for args,_ in calls],["mobile_app_two"])

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
        self.assertEqual(manifest["version"], "0.8.11")
        self.assertIn('CARD_VERSION = "0.8.11"', constants)


if __name__ == "__main__":
    unittest.main()
