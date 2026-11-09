"""Standalone regression tests for HA event-loop writes and service contexts.

Mocks only Home Assistant framework types: these tests run without a complete
Home Assistant installation in GitHub Actions.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "person_timeline"
PKG = "_tiny_family_runtime_tests"


class HomeAssistantError(Exception):
    pass


class Entity:
    hass = None
    platform = None

    def async_write_ha_state(self):
        if asyncio.get_running_loop() is not self.hass.loop:
            raise AssertionError("Home Assistant entity was written off the event loop")
        self.writes = getattr(self, "writes", 0) + 1


def add_module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def load(filename):
    name = f"{PKG}.{filename.removesuffix('.py')}"
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def make_modules():
    for name in ("homeassistant", "homeassistant.components", PKG):
        add_module(name, __path__=[])
    add_module("homeassistant.components.sensor", SensorEntity=Entity)
    add_module("homeassistant.components.binary_sensor", BinarySensorEntity=Entity)
    add_module("homeassistant.exceptions", HomeAssistantError=HomeAssistantError)
    add_module(f"{PKG}.const", DOMAIN="person_timeline")
    add_module(f"{PKG}.places", _zone_candidates=lambda *args: [])
    add_module(f"{PKG}.companion", companion_readings=lambda *args, **kwargs: {})
    add_module(f"{PKG}.utils", _pretty=lambda x: x, _slug=lambda x: x,
               _sensor=lambda *args: args)
    return (load("sensors.py"), load("sensor.py"),
            load("binary_sensor.py"), load("authz.py"))


SENSORS, SENSOR, BINARY, AUTHZ = make_modules()


class ThreadSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_registered_sensor_mutation_happens_on_loop(self):
        loop = asyncio.get_running_loop()
        sensor = SENSOR.TinyFamilySensor("sensor.test", 1, {"unit_of_measurement": "km"})
        sensor.hass = types.SimpleNamespace(loop=loop)
        sensor.platform = object()
        with ThreadPoolExecutor(max_workers=1) as executor:
            await loop.run_in_executor(
                executor, sensor.update_from_payload,
                "42", {"unit_of_measurement": "km"}
            )
        await asyncio.sleep(0)
        self.assertEqual(sensor._attr_native_value, 42.0)
        self.assertEqual(sensor.writes, 1)

    async def test_binary_sensor_mutation_happens_on_loop(self):
        loop = asyncio.get_running_loop()
        sensor = BINARY.TinyFamilyBinarySensor("binary_sensor.test", "off", {})
        sensor.hass = types.SimpleNamespace(loop=loop)
        sensor.platform = object()
        with ThreadPoolExecutor(max_workers=1) as executor:
            await loop.run_in_executor(executor, sensor.update_from_payload, "on", {})
        await asyncio.sleep(0)
        self.assertTrue(sensor._attr_is_on)
        self.assertEqual(sensor.writes, 1)

    async def test_publisher_schedules_entire_update_on_loop(self):
        loop = asyncio.get_running_loop()
        calls = []

        def payloads(hass, person):
            self.assertIs(asyncio.get_running_loop(), loop)
            calls.append(person)
            return ([("sensor.tiny_test", 12, {})], [])

        class States:
            def async_set(self, entity_id, value, attrs):
                self.assert_is_loop()
                calls.append((entity_id, value))

            def assert_is_loop(self):
                if asyncio.get_running_loop() is not loop:
                    raise AssertionError("State set ran off loop")

        hass = types.SimpleNamespace(
            loop=loop,
            data={"tiny_family_runtime": {"registered_entities": {}}},
            states=States(),
        )
        previous = SENSORS.generated_payloads
        SENSORS.generated_payloads = payloads
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                await loop.run_in_executor(executor, SENSORS._publish, hass, "person.one")
            await asyncio.sleep(0)
            self.assertEqual(calls, ["person.one", ("sensor.tiny_test", 12)])
        finally:
            SENSORS.generated_payloads = previous


class PermissionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_home_assistant_automation_can_log_system_event(self):
        class Auth:
            async def async_get_user(self, user_id):
                raise AssertionError("System automation must not require a user lookup")

        hass = types.SimpleNamespace(auth=Auth())
        call = types.SimpleNamespace(context=types.SimpleNamespace(
            user_id=None, parent_id="trigger-context"
        ))
        await AUTHZ.require_history_log_permission(hass, {}, call)

    async def test_logged_in_non_admin_cannot_log_system_event(self):
        class Auth:
            async def async_get_user(self, user_id):
                return types.SimpleNamespace(is_active=True, is_admin=False)

        hass = types.SimpleNamespace(auth=Auth())
        call = types.SimpleNamespace(context=types.SimpleNamespace(user_id="member"))
        with self.assertRaises(HomeAssistantError):
            await AUTHZ.require_history_log_permission(hass, {}, call)

    async def test_unauthenticated_member_changes_remain_denied(self):
        hass = types.SimpleNamespace()
        call = types.SimpleNamespace(context=types.SimpleNamespace(user_id=None))
        with self.assertRaises(HomeAssistantError):
            await AUTHZ.require_permission(
                hass, {"persons": ["person.one"]}, call, person="person.one"
            )

    async def test_missing_context_does_not_bypass_log_permissions(self):
        with self.assertRaises(HomeAssistantError):
            await AUTHZ.require_history_log_permission(
                types.SimpleNamespace(), {}, types.SimpleNamespace(context=None)
            )


if __name__ == "__main__":
    unittest.main()
