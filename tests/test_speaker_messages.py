"""Isolated tests for opt-in Danish TTS and private Tiny Family direct messages."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "tiny_family"
PKG = "_tiny_family_speaker_tests"
sys.modules[PKG] = types.ModuleType(PKG)
sys.modules[PKG].__path__ = []
utils = types.ModuleType(f"{PKG}.utils")
utils._hav = lambda *args: 0
sys.modules[utils.__name__] = utils
spec = importlib.util.spec_from_file_location(
    f"{PKG}.communications", COMPONENT / "communications.py"
)
MOD = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = MOD
spec.loader.exec_module(MOD)


class States:
    def __init__(self, **values):
        self.values = values

    def get(self, key):
        return self.values.get(key)


class Services:
    def __init__(self):
        self.called = []

    def async_services(self):
        return {"tts": {"speak": object()}}

    async def async_call(self, domain, action, data, *, target, blocking):
        self.called.append((domain, action, data, target, blocking))


class FakeHass:
    def __init__(self, languages=None):
        self.data = {}
        self.services = Services()
        self.states = States(**{
            "media_player.room": types.SimpleNamespace(
                state="idle", attributes={}
            ),
            "tts.danish": types.SimpleNamespace(
                state="available",
                attributes={"supported_languages": languages or ["da-DK", "en-US"]}
            ),
            "person.sender": types.SimpleNamespace(name="Afsender"),
        })


CONFIG = {
    "persons": ["person.sender", "person.receiver"],
    "owners": {"person.sender": "sender-user", "person.receiver": "receiver-user"},
    "smart_speakers": {"person.receiver": "media_player.room"},
    "tts_engines": {"person.receiver": "tts.danish"},
}


class SpeakerMessagesTests(unittest.IsolatedAsyncioTestCase):
    async def test_named_recipient_gets_danish_tts_not_phone_or_broadcast(self):
        hass = FakeHass()
        result = await MOD.deliver_spoken(
            hass, sender_user_id="sender-user", sender_person="person.sender",
            config=CONFIG, recipient_person="person.receiver",
            message="Kom ned og spis",
        )
        self.assertEqual(result["delivery_channel"], "speaker")
        self.assertEqual(result["recipient_people"], ["person.receiver"])
        self.assertEqual(result["delivery_state"], "accepted_by_tts")
        self.assertEqual(len(hass.services.called), 1)
        domain, action, data, target, blocking = hass.services.called[0]
        self.assertEqual((domain, action), ("tts", "speak"))
        self.assertEqual(data["media_player_entity_id"], "media_player.room")
        self.assertEqual(data["language"], "da-DK")
        self.assertIn("Kom ned og spis", data["message"])
        self.assertEqual(target["entity_id"], "tts.danish")
        self.assertTrue(blocking)

    async def test_no_unsolicited_public_speaker_broadcast(self):
        hass = FakeHass()
        for recipient in (None, "person.sender", "person.unknown"):
            with self.subTest(recipient=recipient):
                with self.assertRaises(MOD.CommunicationError):
                    await MOD.deliver_spoken(
                        hass, sender_user_id="sender-user",
                        sender_person="person.sender", config=CONFIG,
                        recipient_person=recipient, message="Hej",
                    )
        self.assertEqual(hass.services.called, [])

    async def test_other_account_cannot_impersonate_sender(self):
        hass = FakeHass()
        with self.assertRaises(MOD.CommunicationError):
            await MOD.deliver_spoken(
                hass, sender_user_id="receiver-user",
                sender_person="person.sender", config=CONFIG,
                recipient_person="person.receiver", message="Hej",
            )
        self.assertEqual(hass.services.called, [])

    async def test_only_danish_tts_or_error_no_english_fallback(self):
        hass = FakeHass(languages=["en-US"])
        with self.assertRaises(MOD.CommunicationError) as caught:
            await MOD.deliver_spoken(
                hass, sender_user_id="sender-user",
                sender_person="person.sender", config=CONFIG,
                recipient_person="person.receiver", message="Hej",
            )
        self.assertEqual(caught.exception.code, "danish_not_supported")
        self.assertEqual(hass.services.called, [])

    async def test_unregistered_speaker_cannot_be_used(self):
        hass = FakeHass()
        cfg = {**CONFIG, "smart_speakers": {"person.receiver": "media_player.invalid"}}
        with self.assertRaises(MOD.CommunicationError):
            await MOD.deliver_spoken(
                hass, sender_user_id="sender-user",
                sender_person="person.sender", config=cfg,
                recipient_person="person.receiver", message="Hej",
            )
        self.assertEqual(hass.services.called, [])

    async def test_rate_limit_prevents_accidental_double_play(self):
        hass = FakeHass()
        kw = dict(sender_user_id="sender-user",
                  sender_person="person.sender",
                  config=CONFIG, recipient_person="person.receiver", message="Hej")
        await MOD.deliver_spoken(hass, **kw)
        with self.assertRaises(MOD.CommunicationError) as ctx:
            await MOD.deliver_spoken(hass, **kw)
        self.assertEqual(ctx.exception.code, "rate_limited")
        self.assertEqual(len(hass.services.called), 1)


class UiContractsTests(unittest.TestCase):
    def test_backend_rejects_non_message_tts_and_ui_requires_one_recipient(self):
        source = (COMPONENT / "api.py").read_text()
        panel = (COMPONENT / "frontend/tiny-family-panel.js").read_text()
        self.assertIn('channel == "speaker" and action != "message"', source)
        self.assertIn('"speaker","Smart speaker (dansk oplæsning)"', panel)
        self.assertIn('if(channelSelect.value==="speaker" && !recipientSelect.value)', panel)


if __name__ == "__main__":
    unittest.main()
