"""Source-level contract tests for Tiny Family mobile layout and timeline follow.

These complement JS syntax checks; final responsive behavior still requires
a physical mobile browser / Home Assistant panel smoke test.
"""
from pathlib import Path
import unittest

PANEL=(Path(__file__).resolve().parents[1]/
       "custom_components/tiny_family/frontend/tiny-family-panel.js")


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

    def test_zone_drawing_is_in_places_panel_with_admin_permissions(self):
        self.assertIn('{key:"zones",title:"Zoner",pane:zonePane}',self.js)
        self.assertIn('editingMode="circle"',self.js)
        self.assertIn('editingMode==="polygon"',self.js)
        self.assertIn('"tiny_family/zones"',self.js)
        self.assertIn('"tiny_family/geofences"',self.js)
        self.assertIn('zoneTools.hidden=!data.can_manage_all_places',self.js)
        self.assertIn('Destinationer inde i zonen:',self.js)

    def test_unsaved_inputs_are_preserved_and_member_settings_collapsed(self):
        self.assertIn('this.readDraft("places-create")',self.js)
        self.assertIn('this.writeDraft("places-create"',self.js)
        self.assertIn('this.readDraft("places-zone")',self.js)
        self.assertIn('this.readDraft("editor")',self.js)
        self.assertIn('this.clearDraft("editor")',self.js)
        self.assertIn('this.readDraft("contact-compose")',self.js)
        self.assertIn('this.writeDraft("contact-compose"',self.js)
        self.assertIn('className = "tf-person tf-member-settings"',self.js)
        self.assertIn('.tf-member-settings:not([open])>*:not(summary)',self.js)
        self.assertIn('if(requestedView===this.active',self.js)
        self.assertIn('root.classList.remove("tf-places-view","tf-activity-view",',self.js)

    def test_admin_settings_remain_complete_in_accordion(self):
        for marker in ('tf-admin-groups','makeGroup("Familiemedlemmer og telefoner"',
                       'makeGroup("Alarmer og fartgrænser"',
                       'makeGroup("Vejtilpasning og OSRM"',
                       'tf-admin-save'):
            self.assertIn(marker,self.js)

    def test_person_stays_centered_during_timeline_replay(self):
        self.assertIn("timelineMarker.setLatLng(loc)",self.js)
        self.assertIn("activeMap.panTo(loc,{animate:false})",self.js)
        self.assertIn('previousCenteredFix=loc.join(",")',self.js)
        self.assertIn("!timelineMode)draw()",self.js)
        self.assertIn('"&map_match=0"',self.js)
        self.assertIn('"&phase=matching"',self.js)
        self.assertIn('void loadRoadOverlay(person,selectedDate,requestId)',self.js)
        self.assertIn('timelineData.inferred_segments=overlay.inferred_segments||[]',self.js)
        self.assertIn('dashArray:"6 8"',self.js)
        self.assertIn('Anslået position',self.js)

    def test_replay_uses_real_elapsed_time_and_resets_date_when_person_changes(self):
        self.assertIn('data-role="timeline-speed"',self.js)
        self.assertIn('option value="1">1× realtid',self.js)
        self.assertIn('performance.now()',self.js)
        self.assertIn('playbackTime+=elapsed*Number(playbackSpeed.value)',self.js)
        self.assertIn('stopPlayback(false);return;',self.js)
        self.assertIn('if(playbackTime===null){',self.js)
        self.assertIn('dockPerson.addEventListener("change",()=>{',self.js)
        self.assertIn('resetToToday();',self.js)
        self.assertIn('playbackLocation(closest,',self.js)


if __name__=="__main__":
    unittest.main()
