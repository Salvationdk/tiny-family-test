"""Source-level contract tests for Tiny Family mobile layout and timeline follow.

These complement JS syntax checks; final responsive behavior still requires
a physical mobile browser / Home Assistant panel smoke test.
"""
from pathlib import Path
import unittest

PANEL=(Path(__file__).resolve().parents[1]/
       "custom_components/person_timeline/frontend/tiny-family-panel.js")


class MobileExperienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=PANEL.read_text(encoding="utf-8")

    def test_four_primary_tabs_remain_compact(self):
        tabs=self.js.split("const TF_VIEWS =",1)[1].split("];",1)[0]
        for title in ('"Kort"','"Steder"','"Aktivitet"','"Beskeder"'):
            self.assertIn(title,tabs)
        self.assertEqual(tabs.count('["'),4)

    def test_one_screen_mobile_shell_and_neon_style(self):
        self.assertIn("#tf-main.tf-one-screen",self.js)
        self.assertIn("height:100dvh",self.js)
        self.assertIn("env(safe-area-inset-bottom)",self.js)
        self.assertIn(".tf-screen-panel",self.js)
        self.assertIn(".tf-screen-nav",self.js)
        self.assertIn("overscroll-behavior:contain",self.js)

    def test_places_activity_messages_have_inner_views(self):
        self.assertIn('root.classList.add("tf-places-view")',self.js)
        self.assertIn('root.classList.add("tf-activity-view")',self.js)
        self.assertIn('root.classList.add("tf-messages-view")',self.js)
        self.assertIn('selectPlaceView("shared")',self.js)
        self.assertIn('selectActivity("all")',self.js)
        self.assertIn('selectMessages("compose")',self.js)

    def test_admin_settings_remain_complete_in_accordion(self):
        for marker in ('tf-admin-groups','makeGroup("Familiemedlemmer og telefoner"',
                       'makeGroup("Alarmer og fartgrænser"',
                       'makeGroup("Vejtilpasning og OSRM"',
                       'tf-admin-save'):
            self.assertIn(marker,self.js)

    def test_person_stays_centered_during_timeline_replay(self):
        self.assertIn("timelineMarker.setLatLng(loc)",self.js)
        self.assertIn("activeMap.panTo(loc,{animate:false})",self.js)
        self.assertIn("previousCenteredFix=closest.t",self.js)
        self.assertIn("!timelineMode)draw()",self.js)
        self.assertIn("map_match=1",self.js)


if __name__=="__main__":
    unittest.main()
