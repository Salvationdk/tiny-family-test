"""Source-level contract tests for Tiny Family mobile layout and timeline follow.

These complement JS syntax checks; final responsive behavior still requires
a physical mobile browser / Home Assistant panel smoke test.
"""
from pathlib import Path
import unittest

PANEL=(Path(__file__).resolve().parents[1]/
       "custom_components/tiny_family/frontend/tiny-family-panel.js")
CARD=(Path(__file__).resolve().parents[1]/
      "custom_components/tiny_family/frontend/tiny-family-card.js")


class MobileExperienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=PANEL.read_text(encoding="utf-8")
        cls.card=CARD.read_text(encoding="utf-8")

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
        self.assertIn('shapeNav.setAttribute("aria-label","Vælg zonens form")',self.js)
        self.assertIn('circleShape.textContent="◯ Cirkelzone"',self.js)
        self.assertIn('polygonShape.textContent="⬡ Polygonzone"',self.js)
        self.assertIn('polygonEditor.hidden=selectedZoneShape!=="polygon"',self.js)
        self.assertIn('shape:selectedZoneShape',self.js)

    def test_single_open_accordion_and_compact_place_proposals(self):
        self.assertIn('addEventListener("toggle",event=>{',self.js)
        self.assertIn('other.dataset.tfAccordionGroup===group&&other.open',self.js)
        for scope in ('admin-sections','admin-members','places-proposals',
                      'places-managed','places-shared','places-own',
                      'places-zones','message-details','today-details'):
            self.assertIn(scope,self.js)
        self.assertIn('expand.textContent="Udvid ▾"',self.js)
        self.assertIn('expand.textContent=card.open?"Luk ▴":"Udvid ▾"',self.js)
        self.assertIn('const managedGroups=[];',self.js)
        self.assertIn('nærliggende registreringer',self.js)

    def test_neon_buttons_custom_icons_and_unobtrusive_draft_notice(self):
        for marker in ('TF_ICON_ART','tinyNeonIcon("family")',
                       'tinyNeonIcon("admin")','.tf-wrap button.tf-save',
                       '.tf-member-state[data-active=true]',
                       '.tf-member-state[data-active=false]',
                       'const hasUnsavedChanges=()=>',
                       'if(!hasUnsavedChanges()){',
                       'Overfør fra ældre installation (valgfrit)',
                       '.tf-wrap [hidden]{display:none!important}'):
            self.assertIn(marker,self.js)

    def test_phone_diagnostics_and_original_neon_icons(self):
        for marker in ('phone:', 'gps:', 'speed:', 'battery:', 'refresh:',
                       'check:', 'warning:', 'trip:', 'stay:',
                       'this.settings.tracker_diagnostics',
                       'tf-phone-diagnostic', 'tf-phone-state',
                       'Kontrollér GPS og sensorer nu',
                       'this.hassInstance.callApi("GET","tiny_family/settings")',
                       'Den samme GPS-telefon må ikke være valgt til to personer'):
            self.assertIn(marker,self.js)

    def test_person_diary_and_activity_share_full_size_scroll_surface(self):
        self.assertIn('.tf-person-diary .tf-daily-scroll{overflow:visible',self.js)
        self.assertIn('.tf-activity-view .tf-daily-scroll{overflow:visible',self.js)
        self.assertIn('const extraStats=document.createElement("details")',self.js)
        self.assertIn('Vis alle 10 nøgletal',self.js)
        self.assertIn('"Gns. målt fart i bevægelse",count(s.avg_recorded_moving_speed_kmh,"km/t"),"speed",true',self.js)
        self.assertIn('summaryFact("speed","Gns. målt "',self.js)
        self.assertIn('.tf-timeline-warning{display:flex;flex-wrap:wrap',self.js)
        self.assertIn('setTimelineFacts([["clock","Målt "',self.js)

    def test_text_diary_has_per_trip_speed_and_messages_use_step_rows(self):
        for marker in ('item.avg_speed_kmh','Gns. ', 'Topfart ',
                       'tf-daily-facts','tf-delivery-steps',
                       '["Accepteret",','["Leveret",','["Læst",'):
            self.assertIn(marker,self.js)
        self.assertIn('["report","Dagsrapport",reportPane]',self.js)
        self.assertIn('["archive","Seneste ture og ophold",archivePane]',self.js)

    def test_place_coordinates_open_inside_panel_not_external_maps(self):
        self.assertIn('async openLocationDialog(place,opener=null)',self.js)
        self.assertIn('dialog.setAttribute("role","dialog")',self.js)
        self.assertIn('this._locationDialogMap=map',self.js)
        self.assertIn('this.openLocationDialog(place,button)',self.js)
        self.assertIn('this.closeLocationDialog();',self.js)
        self.assertNotIn('https://www.google.com/maps',self.js)
        self.assertNotIn('https://www.google.com/maps',self.card)
        self.assertIn('class="pt-map-info"',self.card)

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
        self.assertIn("activeMap.setView(center,zoom,{animate:false})",self.js)
        self.assertIn('previousCenteredFix=loc.join(",")',self.js)
        self.assertIn("const refreshLivePositions=async()=>",self.js)
        self.assertIn("marker.setLatLng([person.latitude,person.longitude])",self.js)
        self.assertIn('},"tiny_family_position_updated")',self.js)
        self.assertIn("},6000)",self.js)
        self.assertNotIn("},30000)",self.js)
        self.assertIn('"&map_match=0"',self.js)
        self.assertIn('"&phase=matching"',self.js)
        self.assertIn('void loadRoadOverlay(person,selectedDate,requestId)',self.js)
        self.assertIn('timelineData.inferred_segments=overlay.inferred_segments||[]',self.js)
        self.assertIn('dashArray:"6 8"',self.js)
        self.assertIn('Anslået position',self.js)
        self.assertIn('const focusEventObservation=(event,segments)=>',self.js)
        self.assertIn('eventFocus=focus?{...focus,kind:event.kind}:null;',self.js)
        self.assertIn('activeMap.unproject([pixel.x,pixel.y+offset],zoom)',self.js)
        self.assertIn('if(!activeMap||!validMapPoint(loc))return;',self.js)

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

    def test_daily_diary_is_per_person_date_and_available_from_map_badges(self):
        self.assertIn('async dailyReport(root,{view="activity",ownOnly=false,fixedPerson=null}={}) {',self.js)
        self.assertIn('"&date="+encodeURIComponent(selectedDay)+"&view=report"',self.js)
        self.assertIn('personSelect.addEventListener("change",()=>{date.value=today;',self.js)
        self.assertIn('className="tf-daily-scroll"',self.js)
        self.assertIn('className="tf-daily-stats"',self.js)
        self.assertIn('dayAction.textContent="Dagens statistik og besøg"',self.js)
        self.assertIn('this._timelineRequestedDate=date.value;',self.js)
        self.assertIn('if(requestedDate && requestedDate>=dockDate.min',self.js)
        self.assertIn('this._activityRequestedPerson=person.person;',self.js)
        self.assertIn('archive.className="tf-person tf-activity-archive";',self.js)
        self.assertIn('diaryHeading.append(tinyNeonIcon("history")',self.js)
        self.assertIn('void this.dailyReport(ownDiary,{view:"today",ownOnly:true});',self.js)
        self.assertIn('void this.dailyReport(memberDiary,{view:"editor",fixedPerson:person.id});',self.js)
        self.assertIn('diarySummary.append(tinyNeonIcon("history")',self.js)


if __name__=="__main__":
    unittest.main()
