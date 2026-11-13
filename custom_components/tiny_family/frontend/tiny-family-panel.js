/* Tiny Family: own Home Assistant panel, independent of Lovelace. */
const TF_VIEWS = [
  ["live", "Kort", "mdi:map-marker-multiple-outline"],
  ["places", "Steder", "mdi:map-marker-radius-outline"],
  ["activity", "Aktivitet", "mdi:walk"],
  ["contact", "Beskeder", "mdi:message-text-outline"]
];
const TF_MORE_VIEWS = [
  ["today", "Min status", "mdi:home-outline"],
  ["routes", "Tidslinje", "mdi:map-outline"],
  ["history", "Hændelser", "mdi:history"],
  ["help", "Hjælp", "mdi:help-circle-outline"]
];
class TinyFamilyPanel extends HTMLElement {
  constructor() { super(); this.active = "live"; this.booted = false; this.settings = null; }
  set hass(value) {
    this.hassInstance = value;
    if (this.isConnected && !this.booted) this.initialize();
    if (this.card) this.card.hass = value;
    if (this.active === "today" && this._todayPerson) this.updateToday();
  }
  set narrow(value) { this.isNarrow = value; }
  set panel(value) { this.panelInfo = value; }
  connectedCallback() { if (this.hassInstance && !this.booted) this.initialize(); }
  disconnectedCallback() {
    if(this._familyTimer){clearInterval(this._familyTimer);this._familyTimer=null;}
    if(this._timelinePlaybackTimer){clearInterval(this._timelinePlaybackTimer);this._timelinePlaybackTimer=null;}
    this.closeLocationDialog();
    if(this._familyMap){this._familyMap.remove();this._familyMap=null;}
  }
  async initialize() {
    if (this.loading || this.booted) return;
    this.loading = true;
    this.innerHTML = `
      <style>
      tiny-family-panel{display:block;background:var(--primary-background-color);min-height:100%;color:var(--primary-text-color)}
      .tf-wrap{max-width:1280px;padding:clamp(12px,2.6vw,24px);margin:auto;font-family:inherit;box-sizing:border-box;min-width:0}
      .tf-wrap *{box-sizing:border-box;min-width:0}
      .tf-wrap button,.tf-wrap select,.tf-wrap input,.tf-wrap textarea{font:inherit}
      .tf-wrap button{touch-action:manipulation}
      .tf-wrap button:focus-visible,.tf-wrap a:focus-visible,.tf-wrap input:focus-visible,.tf-wrap select:focus-visible,.tf-wrap textarea:focus-visible{outline:3px solid var(--primary-color);outline-offset:2px}
      .tf-wrap button:disabled{opacity:.55;cursor:wait}
      .tf-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,185px),1fr));gap:10px}
      .tf-stat{display:grid;gap:5px;border:1px solid var(--divider-color);padding:12px;border-radius:12px;background:var(--card-background-color);overflow-wrap:anywhere}
      .tf-stat strong{font-size:.8rem;color:var(--secondary-text-color)}
      .tf-stat [data-today-metric]{font-weight:600;font-variant-numeric:tabular-nums}
      .tf-card-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px}
      .tf-chip{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--divider-color);padding:4px 9px;border-radius:999px;font-size:.78rem;color:var(--secondary-text-color);max-width:100%;overflow-wrap:anywhere}
      .tf-card-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
      .tf-card-actions>*{flex:0 1 auto}
      .tf-map{height:clamp(295px,48vh,520px);min-height:295px;max-width:100%;border:1px solid var(--divider-color);border-radius:14px;overflow:hidden}
      .tf-empty{padding:18px;border:1px dashed var(--divider-color);border-radius:12px;color:var(--secondary-text-color)}
      .tf-wrap a{color:var(--primary-color)}
      .tf-person p{margin:4px 0;overflow-wrap:anywhere}
      .tf-member-settings>summary{cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:8px;font-weight:750;min-height:43px;list-style:none}
      .tf-member-settings>summary::-webkit-details-marker{display:none}
      .tf-member-settings:not([open])>*:not(summary){display:none}
      .tf-member-settings[open]{border-color:#36bbc9}
      .tf-member-summary .tf-chip{font-size:11px;flex:none}
      .tf-wrap .tf-save.tf-danger{background:#a33842;color:#fff}
      /* Map detail is a true in-panel dialog, above the fixed mobile tabs. */
      .tf-location-overlay{position:fixed;inset:0;z-index:2400;display:grid;place-items:center;padding:12px;background:rgba(8,16,28,.74);backdrop-filter:blur(3px)}
      .tf-location-dialog{width:min(680px,100%);max-height:calc(100dvh - 24px);display:flex;flex-direction:column;gap:9px;overflow:hidden;padding:13px;border:1px solid rgba(57,213,226,.65);border-radius:18px;background:var(--card-background-color);color:var(--primary-text-color);box-shadow:0 12px 50px rgba(0,0,0,.45)}
      .tf-location-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
      .tf-location-head h2{font-size:18px;margin:0;overflow-wrap:anywhere}
      .tf-location-map{height:min(63dvh,530px);min-height:240px;flex:1 1 auto;width:100%;border-radius:12px;border:1px solid var(--divider-color);overflow:hidden}
      .tf-location-coords{font-size:12px;color:var(--secondary-text-color);font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
      .tf-location-actions{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px;align-items:center}
      .tf-location-actions button{min-height:42px}
      @media(max-width:380px){.tf-location-actions{grid-template-columns:minmax(0,1fr)}}
      .tf-daily-report{display:flex;flex-direction:column;gap:9px;min-height:0;flex:1;overflow:hidden}
      .tf-daily-controls{display:grid;grid-template-columns:40px minmax(0,1fr) 40px;gap:6px}
      .tf-daily-controls select{grid-column:1/-1}
      .tf-daily-controls input,.tf-daily-controls select,.tf-daily-controls button{min-height:40px;min-width:0;border:1px solid var(--divider-color);border-radius:10px;background:var(--card-background-color);color:var(--primary-text-color);padding:6px 8px;font:inherit}
      .tf-daily-stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
      .tf-daily-stats .tf-stat{padding:9px;gap:3px}
      .tf-daily-stats .tf-stat span{font-weight:750;font-variant-numeric:tabular-nums}
      .tf-daily-scroll{min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;padding:2px 3px 10px;flex:1}
      .tf-daily-row{display:grid;grid-template-columns:90px minmax(0,1fr);gap:9px;padding:10px 7px;border-bottom:1px solid var(--divider-color)}
      .tf-daily-row time{font-size:12px;font-variant-numeric:tabular-nums;color:var(--secondary-text-color)}
      .tf-daily-row strong{display:block;font-size:13px;overflow-wrap:anywhere}
      .tf-daily-row span{font-size:12px;color:var(--secondary-text-color);overflow-wrap:anywhere}
      .tf-activity-archive{flex:none;max-height:38vh;overflow:auto}
      .tf-activity-archive:not([open])>*:not(summary){display:none}
      .tf-activity-archive summary{cursor:pointer;min-height:34px}
      .tf-person-diary>summary{cursor:pointer;min-height:43px;font-weight:750}
      .tf-person-diary:not([open])>*:not(summary){display:none}
      .tf-person-diary[open] .tf-daily-report{height:min(60dvh,580px);min-height:350px}
      .tf-head{display:flex;align-items:center;gap:10px;margin-bottom:12px}
      .tf-head h1{flex:1;min-width:0}
      .tf-header-action{display:inline-flex;align-items:center;justify-content:center;gap:5px;min-height:44px;min-width:44px;padding:8px;border:1px solid var(--divider-color);border-radius:12px;background:var(--card-background-color);color:var(--primary-text-color);cursor:pointer}
      .tf-more{position:relative}
      .tf-more summary{list-style:none;cursor:pointer}
      .tf-more summary::-webkit-details-marker{display:none}
      .tf-more-menu{position:absolute;z-index:120;right:0;top:calc(100% + 6px);width:210px;max-width:calc(100vw - 30px);display:grid;gap:4px;padding:8px;border-radius:14px;border:1px solid var(--divider-color);background:var(--card-background-color);box-shadow:0 12px 30px rgba(0,0,0,.2)}
      .tf-more-menu button{display:flex;align-items:center;gap:8px;text-align:left;min-height:43px;padding:8px 10px;border:0;border-radius:9px;color:var(--primary-text-color);background:transparent}
      /* Tiny Neon: the same muted cyan/violet accents work in HA light and dark themes. */
      .tf-person-icon{border:0;background:transparent}
      .tf-map-person{display:flex;flex-direction:column;align-items:center;gap:4px;width:132px;min-height:90px;font-family:inherit;transform:translateZ(0);filter:drop-shadow(0 5px 10px rgba(8,15,28,.32))}
      .tf-person-pin{width:48px;height:48px;border:3px solid #57dce8;display:flex;align-items:center;justify-content:center;border-radius:50%;background:linear-gradient(135deg,#152a37,#29233f);color:#fff;font-weight:800;font-size:15px;box-shadow:0 0 0 2px rgba(255,255,255,.90),0 0 13px rgba(44,202,229,.38);letter-spacing:.4px;flex:none}
      .tf-neon-stats{display:flex;gap:6px;justify-content:center;align-items:center;max-width:132px;padding:5px 8px;border:1px solid rgba(87,220,232,.65);border-radius:999px;background:rgba(17,28,42,.96);color:#effcff;white-space:nowrap;box-shadow:0 0 12px rgba(37,201,224,.2);font-size:11px;line-height:1.2;font-weight:700}
      .tf-neon-metric{display:flex;align-items:center;gap:3px;font-variant-numeric:tabular-nums}
      .tf-neon-symbol{display:inline-flex;align-items:center;justify-content:center;color:#6fe9ec}
      .tf-neon-symbol svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
      .tf-neon-metric.battery-low,.tf-neon-metric.battery-low .tf-neon-symbol{color:#ff9b9b}
      .tf-neon-stay{padding:3px 8px;border-radius:999px;background:rgba(36,29,55,.96);border:1px solid rgba(180,152,248,.72);box-shadow:0 0 10px rgba(157,127,235,.25);color:#eee2ff;font-size:11px;font-weight:700;white-space:nowrap}
      .tf-neon-stale .tf-person-pin,.tf-neon-stale .tf-neon-stats{box-shadow:none;filter:saturate(.5);border-color:#a7b2c4}
      .tf-neon-stale .tf-neon-stats{color:#c4ceda}
      .tf-neon-focus{padding:4px 0;min-width:175px;font:inherit}
      .tf-neon-focus strong{display:block;margin:0 0 6px}
      .tf-neon-focus span{display:block;margin:3px 0}
      .tf-wrap .tf-tabs button[aria-current=page]{border-color:#15b7c9;color:var(--primary-text-color);box-shadow:0 0 0 1px rgba(29,183,201,.17),0 0 12px rgba(29,183,201,.10)}
      .tf-wrap .tf-person{border-color:color-mix(in srgb,var(--divider-color) 83%,#7e69be)}
      .tf-wrap .tf-header-action{border-color:color-mix(in srgb,var(--divider-color) 75%,#35b7d2)}
      .tf-wrap .tf-save{background:linear-gradient(125deg,color-mix(in srgb,var(--primary-color) 85%,#0ccacc),color-mix(in srgb,var(--primary-color) 78%,#7863bb));box-shadow:0 3px 13px rgba(23,159,186,.14);color:var(--text-primary-color,#fff)}
      .tf-wrap .tf-save:active{transform:translateY(1px)}
      .tf-add-place{border-color:color-mix(in srgb,var(--divider-color) 65%,#35bbc9)!important}
      .tf-add-place>summary{cursor:pointer;list-style:none;display:flex;align-items:center;min-height:45px;font-weight:750;color:var(--primary-text-color);padding:3px 5px}
      .tf-add-place>summary::-webkit-details-marker{display:none}
      .tf-add-place[open]>summary{color:var(--primary-color);margin-bottom:10px}
      .tf-contact-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
      .tf-contact-actions button:first-child,.tf-contact-actions button:last-child{grid-column:1/-1}
      .tf-contact-actions button{padding:12px 8px}
      .tf-contact-recipient{display:grid;gap:7px}
      .tf-contact-recipient select{padding:10px 12px;border:1px solid var(--divider-color);background:var(--primary-background-color);color:var(--primary-text-color);border-radius:10px;min-height:44px}
      .tf-map-tools{border:1px solid var(--divider-color);border-radius:12px;padding:8px 12px;margin:0 0 12px;background:var(--card-background-color)}
      .tf-map-tools summary{cursor:pointer;font-weight:600;padding:6px 0}
      .tf-map-tools>*:not(summary){margin-top:10px}
      .tf-shared-place-form{display:grid;gap:10px}
      .tf-shared-place-form label{display:grid;gap:5px}
      .tf-shared-place-form input{width:100%;padding:10px;border:1px solid var(--divider-color);border-radius:9px;background:var(--primary-background-color);color:var(--primary-text-color)}
      .tf-shared-place-actions{display:flex;flex-wrap:wrap;gap:8px}
      .tf-shared-place-actions>*{flex:1 1 150px}
      .tf-place-group{margin:15px 0}
      .tf-place-group>summary{padding:10px 0;cursor:pointer;font-weight:600}
      .tf-zone-list{display:grid;gap:8px;margin-top:10px}
      .tf-zone-editor{margin:10px 0}
      .tf-zone-editor>summary{min-height:43px;cursor:pointer;font-weight:750}
      .tf-zone-editor:not([open])>*:not(summary){display:none}
      .tf-zone-polygon-editor{padding-top:12px;border-top:1px solid var(--divider-color)}
      .tf-zone-editor select{width:100%;padding:10px;border:1px solid var(--divider-color);border-radius:9px;background:var(--primary-background-color);color:var(--primary-text-color)}
      .tf-zone-editor .tf-card-actions>*{flex:1 1 130px}
      /* Tiny Neon timeline: frosted bottom dock, real daily samples, no page scroll. */
      .tf-timeline-dock{position:relative;z-index:700;max-width:850px;padding:10px 12px;border:1px solid rgba(66,220,230,.55);border-radius:17px;background:rgba(20,28,44,.94);color:#effbff;box-shadow:0 8px 22px rgba(0,0,0,.23),0 0 16px rgba(50,188,217,.17);font-size:13px}
      .tf-dock-main{display:flex;gap:7px;align-items:center}
      .tf-timeline-dock button,.tf-timeline-dock select,.tf-timeline-dock input[type=date]{border:1px solid rgba(101,209,224,.5);border-radius:10px;background:rgba(12,23,37,.93);color:#fff;min-height:40px;padding:6px 9px;font-size:13px}
      .tf-timeline-dock button[aria-pressed=true]{background:linear-gradient(125deg,#079eac,#6556b0);border-color:#72e9e7}
      .tf-timeline-dock select{min-width:0;flex:1;max-width:100%;text-overflow:ellipsis}
      .tf-history-controls{display:grid;gap:7px;margin-top:9px}
      .tf-history-controls[hidden]{display:none}
      .tf-day-nav{display:grid;grid-template-columns:44px minmax(0,1fr) 44px;gap:6px}
      .tf-day-nav input{width:100%;min-width:0;box-sizing:border-box;color-scheme:dark}
      .tf-day-nav button{font-size:18px}
      .tf-timeline-dock input[type=range]{width:100%;margin:2px 0 0;accent-color:#39d9e4;touch-action:pan-y;min-height:23px}
      .tf-scrub-row{display:grid;grid-template-columns:42px minmax(0,1fr) 76px;gap:6px;align-items:center}
      .tf-scrub-row button{padding:5px 3px}
      .tf-scrub-row select{width:100%;padding:5px 3px;font-size:12px}
      .tf-event-strip{display:flex;overflow-x:auto;gap:6px;padding:3px 0;scrollbar-width:thin}
      .tf-event-strip[hidden]{display:none}
      .tf-event-strip button{white-space:nowrap;flex:none;min-height:31px;font-size:11px;padding:4px 8px;border-color:rgba(188,146,244,.54);background:rgba(55,35,75,.77)}
      .tf-history-info{display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px;line-height:1.25}
      .tf-history-info span{color:#d0e1f0}
      .tf-history-info strong{color:#a6f5f2}
      .tf-timeline-warning{font-size:11px;color:#ddcfed}
      .tf-road-matching{display:flex;align-items:center;gap:7px;min-height:28px;color:#dcf5fd;font-size:12px;cursor:pointer}
      .tf-road-matching input{width:17px;height:17px;accent-color:#38d2dd;flex:none}
      .tf-road-matching[hidden]{display:none}
      .tf-road-match-status{color:#adf0ed;font-size:11px;line-height:1.25}
      .tf-osrm-setting input[type=url]{display:block;width:100%;min-width:0;max-width:100%;box-sizing:border-box;padding:10px;border:1px solid var(--divider-color);border-radius:9px;background:var(--primary-background-color);color:var(--primary-text-color);margin:6px 0}
      .tf-timeline-dock .tf-mini{font-size:12px;padding:5px 7px}
      /* Tiny Neon responsive app shell. Lists scroll within a single screen,
         never underneath the fixed four-tab mobile navigation. */
      .tf-screen-intro{margin:5px 0 8px;color:var(--secondary-text-color);font-size:13px}
      .tf-screen-nav{display:flex;gap:7px;min-height:42px;padding:4px;border:1px solid rgba(70,207,225,.38);border-radius:13px;background:color-mix(in srgb,var(--card-background-color) 89%,#213b54)}
      .tf-screen-nav button{min-width:0;flex:1;border:0;border-radius:10px;padding:8px 6px;background:transparent;color:var(--primary-text-color);font-size:12px;font-weight:700;cursor:pointer}
      .tf-screen-nav button[aria-pressed=true]{background:linear-gradient(120deg,#117e96,#664db4);color:#fff;box-shadow:0 0 9px rgba(48,196,218,.25)}
      .tf-screen-panel{min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;scrollbar-color:#2ebfc3 transparent;padding:4px 3px}
      .tf-screen-panel[hidden]{display:none!important}
      .tf-mobile-title{font-size:19px;margin:2px 0 5px}
      .tf-activity-list{overflow-y:auto;min-height:0;overscroll-behavior:contain;scrollbar-width:thin}
      .tf-admin-form{min-height:0;display:flex;flex-direction:column;overflow:hidden;flex:1}
      .tf-admin-groups{min-height:0;flex:1;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin}
      .tf-admin-group{margin-bottom:9px;border:1px solid color-mix(in srgb,var(--divider-color) 50%,#5f99bf);border-radius:13px;background:var(--card-background-color);padding:8px}
      .tf-admin-group>summary{font-weight:700;cursor:pointer;min-height:39px;padding:8px;list-style:none}
      .tf-admin-group>summary::-webkit-details-marker{display:none}
      .tf-admin-group[open]>summary{color:#38becb}
      .tf-admin-save{width:100%;margin-top:7px;flex:none}
      .tf-head h1{margin:0;font-size:24px}
      .tf-tabs{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;max-width:100%}
      .tf-tabs button{display:flex;align-items:center;justify-content:center;gap:7px;padding:12px 16px;min-height:44px;border-radius:14px;border:1px solid var(--divider-color);color:var(--primary-text-color);background:var(--card-background-color);cursor:pointer}
      .tf-tabs button ha-icon{--mdc-icon-size:20px}
      .tf-tabs button[data-view=editor]{border-color:var(--primary-color);font-weight:700}
      .tf-admin-panel{border:2px solid var(--primary-color);border-radius:16px;padding:clamp(12px,2vw,20px);background:var(--card-background-color)}
      .tf-admin-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
      .tf-admin-head ha-icon{color:var(--primary-color)}
      .tf-advanced{padding:10px;border:1px solid var(--divider-color);border-radius:12px}
      .tf-advanced summary{cursor:pointer;font-weight:600;padding:5px}
      .tf-advanced .tf-fields{margin-top:10px}
      .tf-tabs button[aria-current=page]{border-color:var(--primary-color);color:var(--primary-color)}
      .tf-person{display:grid;gap:8px;padding:12px;background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:12px;margin-bottom:10px}
      .tf-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,170px),1fr));gap:10px;max-width:100%}
      .tf-fields label{display:grid;gap:4px;font-size:13px}
      .tf-fields select,.tf-fields input{padding:7px;max-width:100%;background:var(--primary-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color);border-radius:8px}
      .tf-save{background:var(--primary-color);color:var(--text-primary-color,#fff);border:0;border-radius:10px;padding:12px 18px;min-height:44px;cursor:pointer;overflow-wrap:anywhere}
      .tf-message{margin:14px 0;color:var(--secondary-text-color)}
      @media(max-width:600px){
        .tf-wrap{padding:10px 10px calc(100px + env(safe-area-inset-bottom))}.tf-head h1{font-size:21px}
        .tf-wrap:has(#tf-main.tf-one-screen){height:100dvh;overflow:hidden;padding-bottom:0;display:flex;flex-direction:column}
        .tf-wrap:has(#tf-main.tf-one-screen) .tf-head{flex:none;margin-bottom:4px}
        .tf-wrap:has(#tf-main.tf-one-screen) #tf-message:empty{display:none}
        .tf-wrap:has(#tf-main.tf-one-screen) #tf-message:not(:empty){flex:none;font-size:12px;margin:3px 0;max-height:60px;overflow-y:auto}
        #tf-main.tf-one-screen{height:calc(100dvh - 165px - env(safe-area-inset-bottom));max-height:calc(100dvh - 165px - env(safe-area-inset-bottom));overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;padding:0 1px 4px}
        #tf-main.tf-one-screen.tf-places-view,#tf-main.tf-one-screen.tf-messages-view,
        #tf-main.tf-one-screen.tf-activity-view{display:flex;flex-direction:column;overflow:hidden;gap:7px}
        #tf-main.tf-one-screen.tf-places-view>.tf-screen-panel,
        #tf-main.tf-one-screen.tf-messages-view>.tf-screen-panel,
        #tf-main.tf-one-screen.tf-activity-view>.tf-activity-list{flex:1;min-height:0}
        #tf-main.tf-places-view>h2,#tf-main.tf-messages-view>h2,
        #tf-main.tf-activity-view>h2{font-size:19px;margin:2px 0 1px;flex:none}
        #tf-main.tf-places-view>.tf-screen-intro,
        #tf-main.tf-messages-view>.tf-screen-intro,
        #tf-main.tf-activity-view>.tf-screen-intro{display:none}
        #tf-main.tf-places-view>.tf-screen-nav,
        #tf-main.tf-messages-view>.tf-screen-nav,
        #tf-main.tf-activity-view>.tf-screen-nav{flex:none}
        #tf-main.tf-messages-view>.tf-message{font-size:11px;margin:2px 0}
        #tf-main.tf-activity-view>.tf-save{min-height:39px;padding:9px}
        #tf-main.tf-admin-mobile{display:flex;flex-direction:column;gap:6px;overflow:hidden;padding:5px}
        #tf-main.tf-admin-mobile>.tf-admin-head{flex:none}
        #tf-main.tf-admin-mobile>.tf-message{display:none}
        #tf-main.tf-admin-mobile>.tf-admin-form{flex:1;min-height:0}
        #tf-main.tf-admin-mobile>.tf-save{display:none}
        #tf-main.tf-admin-mobile>.tf-person{display:none}
        .tf-screen-panel .tf-person{margin-bottom:7px}
        .tf-screen-panel .tf-map{height:210px!important;min-height:210px!important}
        .tf-screen-panel .tf-card-actions>*{flex:1 1 auto}
        .tf-admin-save{position:sticky;bottom:0;z-index:5}
        .tf-head h1{font-size:19px}
        .tf-head{margin-bottom:8px}
        .tf-tabs{position:fixed;left:0;right:0;bottom:0;z-index:100;background:var(--card-background-color);border-top:1px solid var(--divider-color);padding:7px 8px calc(7px + env(safe-area-inset-bottom));box-shadow:0 -4px 20px rgba(0,0,0,.08)}
        #tf-main.tf-family-view{position:relative;height:calc(100dvh - 167px - env(safe-area-inset-bottom));min-height:330px;overflow:hidden;margin:0}
        #tf-main.tf-family-view>h2,#tf-main.tf-family-view>.tf-map-tools,
        #tf-main.tf-family-view>.tf-fields,#tf-main.tf-family-view>.tf-save{display:none}
        #tf-main.tf-family-view>.tf-map{height:100%;min-height:0;max-height:none;width:100%;margin:0!important;border-radius:16px}
        #tf-main.tf-family-view>.tf-timeline-dock{position:absolute;left:8px;right:8px;bottom:9px;max-width:none}
        .tf-wrap:has(#tf-main.tf-family-view){height:calc(100dvh - 12px);overflow:hidden;padding-bottom:0}
        .tf-wrap:has(#tf-main.tf-family-view) .tf-head{margin:0 0 7px}
        .tf-wrap:has(#tf-main.tf-family-view) #tf-message:empty{display:none}
        .tf-wrap:has(#tf-main.tf-family-view) .tf-tabs{margin:0}
        .tf-history-info{font-size:11px}
        .tf-timeline-dock{padding:8px 9px}
        .tf-timeline-dock button,.tf-timeline-dock select{min-height:38px;padding:5px 6px}
        .tf-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;overflow:visible}
        .tf-tabs button{display:flex;flex-direction:column;gap:3px;font-size:11px;line-height:1.2;padding:7px 2px;min-height:58px;white-space:normal;text-align:center;border-radius:10px}
        .tf-tabs button ha-icon{--mdc-icon-size:21px}
        .tf-fields{grid-template-columns:1fr}
        .tf-metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
        .tf-stat{padding:10px}
        .tf-person{padding:11px}.tf-map{height:min(57vh,440px);min-height:330px}
        #tf-main.tf-family-view>.tf-map{height:100%;min-height:0;max-height:none}
        .tf-card-actions>*{flex:1 1 100%}
        .tf-wrap .tf-save{width:100%}
        .tf-admin-panel{padding:12px}
      }
      @media(max-width:360px){
        .tf-fields,.tf-metrics{grid-template-columns:1fr}
      }
      @media(prefers-reduced-motion:reduce){.tf-tabs{scroll-behavior:auto}}
      </style>
      <section class="tf-wrap"><header class="tf-head"><ha-icon icon="mdi:account-group"></ha-icon><h1>Tiny Family</h1><div class="tf-admin-access"></div><details class="tf-more"><summary class="tf-header-action" aria-label="Flere funktioner"><ha-icon icon="mdi:dots-horizontal"></ha-icon></summary><div class="tf-more-menu"></div></details></header>
      <nav class="tf-tabs" aria-label="Tiny Family"></nav>
      <p id="tf-message" class="tf-message" aria-live="polite"></p>
      <main id="tf-main"></main></section>`;
    const tabs = this.querySelector(".tf-tabs");
    try {
      // Only an authenticated administrator gets the Administration tab.
      await this.refreshSettings();
      for (const [key, title, icon] of TF_VIEWS) {
        const button = document.createElement("button");
        const pictogram=document.createElement("ha-icon");
        pictogram.setAttribute("icon",icon);
        pictogram.setAttribute("aria-hidden","true");
        const caption=document.createElement("span");caption.textContent=title;
        button.append(pictogram,caption);
        button.dataset.view = key;
        button.type="button";
        button.addEventListener("click", () => this.show(key));
        tabs.appendChild(button);
      }
      const moreMenu=this.querySelector(".tf-more-menu");
      for(const [key,title,icon] of TF_MORE_VIEWS){
        const button=document.createElement("button");
        button.type="button";
        const pictogram=document.createElement("ha-icon");
        pictogram.setAttribute("icon",icon);
        button.append(pictogram,document.createTextNode(title));
        button.addEventListener("click",()=>{
          this.querySelector(".tf-more").open=false;
          this.show(key);
        });
        moreMenu.appendChild(button);
      }
      if(this.settings.editable){
        const adminButton=document.createElement("button");
        adminButton.type="button";
        adminButton.className="tf-header-action";
        adminButton.title="Administration";
        adminButton.setAttribute("aria-label","Åbn administration");
        const shield=document.createElement("ha-icon");
        shield.setAttribute("icon","mdi:shield-crown-outline");
        adminButton.append(shield);
        adminButton.addEventListener("click",()=>this.show("editor"));
        this.querySelector(".tf-admin-access").appendChild(adminButton);
      }
      try {
        const profile=await this.hassInstance.callApi("GET","tiny_family/status");
        this._viewerPerson=profile.viewer_person;
      } catch(error) {this._viewerPerson=null;}
      this.booted = true;
      this.show(this.active);
    } catch (error) { this.message("Fejl ved indlæsning: " + String(error), true); }
    finally { this.loading = false; }
  }
  message(value, error=false) {
    const target = this.querySelector("#tf-message");
    if (target) {
      target.textContent = value;
      target.style.color = error ? "var(--error-color)" : "";
      target.setAttribute("role", error ? "alert" : "status");
    }
  }
  errorText(error) {
    const code = error?.body?.error_code || error?.error_code;
    const explanations={
      no_recipient:"Ingen telefonmodtager er tilknyttet. Kontakt en administrator.",
      invalid_recipient:"Modtageren er ikke længere tilknyttet. Opdater beskedlisten.",
      gps_unavailable:"Der er ingen frisk GPS-position. Beskeden kan sendes uden position.",
      notify_failed:"Ingen notifikationer blev accepteret. Kontrollér Companion-forbindelsen, og prøv igen.",
      rate_limited:"Vent et øjeblik før du forsøger igen.",
      not_linked:"Din HA-konto er ikke tilknyttet et familiemedlem. Kontakt administrator.",
      invalid_action:"Denne handling kan ikke udføres med de aktuelle valg."
    };
    return explanations[code] || error?.body?.message || error?.message || String(error);
  }
  draftKey(scope) {
    // Drafts stay in this browser tab and belong only to the signed-in HA
    // account; never persist unsaved personal places on the HA server.
    return "tiny-family-draft-v1:"+(this.hassInstance?.user?.id||"local")+":"+scope;
  }
  readDraft(scope) {
    if(!this.hassInstance?.user?.id)return null;
    try{
      const saved=JSON.parse(sessionStorage.getItem(this.draftKey(scope))||"null");
      return saved && Date.now()-saved.at<24*3600*1000?saved.data:null;
    }catch(_){return null;}
  }
  writeDraft(scope,data) {
    if(!this.hassInstance?.user?.id)return;
    try{sessionStorage.setItem(this.draftKey(scope),JSON.stringify({at:Date.now(),data}));}
    catch(_){/* Session storage may be unavailable; never block editing. */}
  }
  clearDraft(scope) {
    if(!this.hassInstance?.user?.id)return;
    try{sessionStorage.removeItem(this.draftKey(scope));}catch(_){}
  }
  closeLocationDialog() {
    const overlay=this._locationOverlay;
    if(!overlay)return;
    this._locationOverlay=null;
    this._locationDialogMap?.remove();this._locationDialogMap=null;
    document.removeEventListener("keydown",this._locationKeyHandler);
    overlay.remove();
    if(this._locationDialogReturnFocus?.isConnected)
      this._locationDialogReturnFocus.focus({preventScroll:true});
    this._locationDialogReturnFocus=null;
  }
  async openLocationDialog(place,opener=null) {
    const latitude=Number(place?.latitude),longitude=Number(place?.longitude);
    if(place?.latitude==null||place?.longitude==null||
       !Number.isFinite(latitude)||!Number.isFinite(longitude)||
       latitude < -90||latitude > 90||longitude < -180||longitude > 180){
      this.message("Placeringen har ikke gyldige koordinater.",true);return;
    }
    this.closeLocationDialog();
    const overlay=document.createElement("div");overlay.className="tf-location-overlay";
    const dialog=document.createElement("section");dialog.className="tf-location-dialog";
    dialog.setAttribute("role","dialog");dialog.setAttribute("aria-modal","true");
    const header=document.createElement("div");header.className="tf-location-head";
    const title=document.createElement("h2");title.textContent=String(place.name||"Placering");
    title.id="tf-location-heading";dialog.setAttribute("aria-labelledby",title.id);
    const close=document.createElement("button");close.type="button";
    close.className="tf-header-action";close.textContent="✕";
    close.setAttribute("aria-label","Luk kortvisning");
    close.addEventListener("click",()=>this.closeLocationDialog());
    header.append(title,close);
    const mapElement=document.createElement("div");mapElement.className="tf-location-map";
    mapElement.setAttribute("aria-label","Kort med markeret placering");
    const coordinates=document.createElement("span");coordinates.className="tf-location-coords";
    coordinates.textContent="Position: "+latitude.toFixed(6)+", "+longitude.toFixed(6);
    const status=document.createElement("span");status.className="tf-location-coords";
    status.textContent="Henter kortgrundlag…";
    const actions=document.createElement("div");actions.className="tf-location-actions";
    const copy=document.createElement("button");copy.type="button";
    copy.className="tf-save";copy.textContent="Kopiér koordinater";
    copy.addEventListener("click",async()=>{
      try{await navigator.clipboard.writeText(latitude+", "+longitude);
        copy.textContent="Kopieret";
      }catch(_){copy.textContent="Markér koordinaterne ovenfor for at kopiere";}
    });
    actions.append(coordinates,copy);
    dialog.append(header,mapElement,status,actions);overlay.appendChild(dialog);
    overlay.addEventListener("click",event=>{
      if(event.target===overlay)this.closeLocationDialog();
    });
    this._locationDialogReturnFocus=opener;
    this._locationKeyHandler=event=>{
      if(event.key==="Escape"){event.preventDefault();this.closeLocationDialog();}
      if(event.key==="Tab"&&this._locationOverlay===overlay){
        const focusable=[...overlay.querySelectorAll("button,a[href],input,select")]
          .filter(item=>!item.disabled && item.getClientRects().length);
        const current=overlay.getRootNode().activeElement;
        if(focusable.length&&event.shiftKey&&current===focusable[0]){
          event.preventDefault();focusable[focusable.length-1].focus();
        }else if(focusable.length&&!event.shiftKey&&
                 current===focusable[focusable.length-1]){
          event.preventDefault();focusable[0].focus();
        }
      }
    };
    document.addEventListener("keydown",this._locationKeyHandler);
    this._locationOverlay=overlay;
    (this.querySelector(".tf-wrap")||this).appendChild(overlay);
    close.focus({preventScroll:true});
    try{
      const L=await this.leaflet();
      if(this._locationOverlay!==overlay)return;
      // This second Leaflet map must not replace _familyMap: the live family
      // map and its timeline keep running behind the dialog.
      const map=L.map(mapElement,{zoomControl:true}).setView([latitude,longitude],16);
      this._locationDialogMap=map;
      L.circleMarker([latitude,longitude],{radius:10,color:"#fff",weight:3,
        fillColor:"#19bacb",fillOpacity:1}).addTo(map);
      let url="https://tile.openstreetmap.org/{z}/{x}/{y}.png";
      if(this.hassInstance?.config?.components?.includes("map_tiles")){
        try{const token=await this.mapTilesAccessToken();
          if(this._locationOverlay!==overlay)return;
          if(token)url="/api/map_tiles/raster/{z}/{x}/{y}.png?token="+
            encodeURIComponent(token);
        }catch(_){status.textContent="HA-kortfliser er utilgængelige. Viser placeringen på alternativt kortgrundlag.";}
      }
      if(this._locationOverlay!==overlay)return;
      const tiles=L.tileLayer(url,{maxZoom:19,maxNativeZoom:19,
        referrerPolicy:"origin",attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'});
      tiles.on("tileload",()=>{if(this._locationOverlay===overlay)
        status.textContent="Placeringen er markeret på kortet.";});
      tiles.on("tileerror",()=>{if(this._locationOverlay===overlay)
        status.textContent="Kortfliser kunne ikke indlæses. Koordinaterne og markøren vises fortsat.";});
      tiles.addTo(map);
      setTimeout(()=>{if(this._locationDialogMap===map)map.invalidateSize();},100);
    }catch(error){
      if(this._locationOverlay===overlay)
        status.textContent="Kortet kunne ikke indlæses: "+this.errorText(error);
    }
  }
  async refreshSettings() {
    this.settings = await this.hassInstance.callApi("GET", "tiny_family/settings");
  }
  show(key) {
    if (!this.booted) return;
    const requestedView=key;
    if (key === "editor" && !this.settings?.editable) key = "live";
    if (key === "routes"){
      this._timelineRequestedPerson=this._routeFilterPerson||this._viewerPerson;
      this._routeFilterPerson=null;
      key="live";
    }
    // Tapping the current mobile tab must not throw away unsaved fields.
    if(requestedView===this.active && this.querySelector("#tf-main")?.children.length)return;
    this.closeLocationDialog();
    this.active = key; this.card = null; this._todayPerson = null; this.message("");
    if(this._familyTimer){clearInterval(this._familyTimer);this._familyTimer=null;}
    if(this._timelinePlaybackTimer){clearInterval(this._timelinePlaybackTimer);this._timelinePlaybackTimer=null;}
    if(this._familyMap){this._familyMap.remove();this._familyMap=null;}
    this.querySelectorAll("[data-view]").forEach(b => b.setAttribute("aria-current", b.dataset.view === key ? "page" : "false"));
    const root = this.querySelector("#tf-main");
    // Every page uses the same root. Stale page-specific classes made the
    // map, messages and admin panels inherit each other's mobile layouts.
    root.classList.remove("tf-places-view","tf-activity-view",
      "tf-messages-view","tf-admin-mobile");
    root.classList.toggle("tf-admin-panel",key==="editor");
    root.classList.toggle("tf-family-view",key==="live");
    root.classList.toggle("tf-one-screen",key!=="live");
    root.replaceChildren();
    if (key === "editor") { this.editor(root); return; }
    if (key === "contact") { this.contact(root); return; }
    if (key === "history") { this.history(root); return; }
    if (key === "activity") { this.activity(root); return; }
    if (key === "today") { this.today(root); return; }
    if (key === "live") { this.family(root); return; }
    if (key === "places") { this.places(root); return; }
    if (key === "routes") { this.routes(root); return; }
    if (key === "help") { this.help(root); return; }
    this.message("Ukendt Tiny Family-visning.", true);
  }

  async leaflet() {
    // HA renders custom panels inside nested shadow roots. A stylesheet in
    // document.head does not style Leaflet descendants within that root.
    // Place Leaflet's layout CSS in the *nearest* shadow root of this panel.
    if(!this._leafletStylesLoading){
      this._leafletStylesLoading=new Promise((resolve,reject)=>{
        const root=this.getRootNode();
        const host=(typeof ShadowRoot!=="undefined" &&
                    root instanceof ShadowRoot)?root:document.head;
        let link=host.querySelector('link[data-tiny-family-leaflet]');
        if(link && link.sheet){resolve();return;}
        if(!link){
          link=document.createElement("link");
          link.rel="stylesheet";
          link.dataset.tinyFamilyLeaflet="1";
          link.href="/tiny_family_static/leaflet/leaflet.css";
          link.addEventListener("load",resolve,{once:true});
          link.addEventListener("error",()=>reject(new Error(
            "Leaflet CSS kunne ikke indlæses.")),{once:true});
          host.appendChild(link);
        }else{
          link.addEventListener("load",resolve,{once:true});
          link.addEventListener("error",()=>reject(new Error(
            "Leaflet CSS kunne ikke indlæses.")),{once:true});
        }
      }).catch(error=>{this._leafletStylesLoading=null;throw error;});
    }
    await this._leafletStylesLoading;
    if(window.L)return window.L;
    if(!this._leafletLoading){
      this._leafletLoading=new Promise((resolve,reject)=>{
        const script=document.createElement("script");
        script.src="/tiny_family_static/leaflet/leaflet.js";
        script.onload=()=>resolve(window.L);
        script.onerror=()=>reject(new Error(
          "Leaflet JavaScript kunne ikke indlæses."));
        document.head.appendChild(script);
      }).catch(error=>{this._leafletLoading=null;throw error;});
    }
    return await this._leafletLoading;
  }

  createLeafletMap(element) {
    const map=window.L.map(element,{zoomControl:true});
    this._familyMap=map;
    let frame=0;
    const update=()=>{
      if(frame || this._familyMap!==map || !element.isConnected)return;
      frame=requestAnimationFrame(()=>{
        frame=0;
        if(this._familyMap===map && element.isConnected)
          map.invalidateSize({pan:false,animate:false});
      });
    };
    // Leaflet measures its viewport when the map is created. HA sidebars,
    // responsive breakpoints, mobile rotations and Playwright viewport
    // changes can resize that element without a window resize event.
    const observer=typeof ResizeObserver!=="undefined"
      ?new ResizeObserver(update):null;
    observer?.observe(element);
    window.addEventListener("resize",update);
    map.on("unload",()=>{
      observer?.disconnect();
      window.removeEventListener("resize",update);
      if(frame)cancelAnimationFrame(frame);
    });
    update();
    return map;
  }

  // The built-in HA map_tiles proxy was introduced in HA 2026.9. It avoids
  // 403/Referer problems on OSM's volunteer tile server and caches tiles in HA.
  // Keep Leaflet for editable circles/polygons and route layers.
  async mapTilesAccessToken(force=false) {
    const connection=this.hassInstance?.connection;
    const enabled=this.hassInstance?.config?.components?.includes("map_tiles");
    if(!enabled || !connection?.sendMessagePromise)return null;
    if(!force && this._mapTilesAuth &&
       Date.now()-this._mapTilesAuth.at<20*60*1000)return this._mapTilesAuth.token;
    if(!this._mapTilesPending){
      this._mapTilesPending=connection.sendMessagePromise({
        type:"map_tiles/access_token"
      }).then(result=>{
        if(typeof result?.token!=="string" || !result.token)
          throw new Error("Home Assistant gav ingen kortadgang.");
        this._mapTilesAuth={token:result.token,at:Date.now()};
        return result.token;
      }).finally(()=>{this._mapTilesPending=null;});
    }
    return this._mapTilesPending;
  }

  async addBaseMap(map, element) {
    const feedback=document.createElement("div");
    feedback.className="tf-map-feedback tf-message";
    feedback.setAttribute("role","status");
    const old=element.nextElementSibling;
    if(old?.classList?.contains("tf-map-feedback"))old.remove();
    element.insertAdjacentElement("afterend",feedback);
    const hasProxy=this.hassInstance?.config?.components?.includes("map_tiles");
    const L=window.L;
    const directUrl="https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    let layer=null;
    let failures=0;
    let lastRecovery=0;
    let mode="";
    const notice=(content,allowDirect=false)=>{
      feedback.dataset.error="1";
      feedback.replaceChildren();
      const span=document.createElement("span");
      span.textContent=content;
      feedback.appendChild(span);
      const retry=document.createElement("button");
      retry.type="button";retry.className="tf-save";
      retry.textContent="Prøv kort igen";
      retry.addEventListener("click",async()=>{
        retry.disabled=true;
        try{
          if(mode==="ha"){
            const newToken=await this.mapTilesAccessToken(true);
            setLayer("/api/map_tiles/raster/{z}/{x}/{y}.png?token="+
                     encodeURIComponent(newToken),"ha");
          }else setLayer(directUrl,"osm");
        }catch(error){notice("Home Assistant-kortet kan ikke genindlæses: "+
                             error.message,allowDirect);}
        finally{retry.disabled=false;}
      });
      feedback.appendChild(retry);
      if(allowDirect){
        const fallback=document.createElement("button");
        fallback.type="button";fallback.className="tf-save";
        fallback.textContent="Brug OpenStreetMap direkte";
        fallback.addEventListener("click",()=>{
          if(!window.confirm("Direkte OpenStreetMap kan se kortområdet og "+
            "din Home Assistant-adresses oprindelse (Referer). Fortsæt?"))return;
          this._directTilesAllowed=true;
          setLayer(directUrl,"osm");
        });
        feedback.appendChild(fallback);
      }
    };
    const setLayer=(url,source)=>{
      if(layer)map.removeLayer(layer);
      mode=source;failures=0;
      feedback.replaceChildren();
      feedback.dataset.error="0";
      const status=document.createElement("span");
      status.textContent=source==="ha"
        ?"Kortgrundlag: Home Assistants indbyggede kortfliser."
        :"Kortgrundlag: OpenStreetMap direkte (alternativ).";
      feedback.appendChild(status);
      layer=L.tileLayer(url,{
        attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom:19,maxNativeZoom:19,
        // Direct browser requests must send Referer under the OSM tile policy.
        referrerPolicy:"origin",
        crossOrigin:false,
      });
      // Leaflet's tile-range calculation throws an uncaught exception when a
      // transient mobile resize or malformed map centre produces NaN/Infinity.
      // Check the range before Leaflet attempts to enumerate its tiles. A
      // later valid map movement will retry naturally without losing GPS data.
      const updateTiles=layer._update;
      layer._update=function(center){
        if(!this._map)return;
        const zoom=this._map.getZoom();
        if(!Number.isFinite(zoom)||zoom<0||zoom>22)return;
        if(this._tileZoom!==undefined){
          try{
            const focus=center||this._map.getCenter();
            if(!Number.isFinite(focus.lat)||!Number.isFinite(focus.lng))return;
            const range=this._pxBoundsToTileRange(this._getTiledPixelBounds(focus));
            const values=[range.min.x,range.min.y,range.max.x,range.max.y];
            if(!values.every(Number.isFinite)||
               range.max.x-range.min.x>128||range.max.y-range.min.y>128)return;
          }catch(error){return;}
        }
        try{return updateTiles.call(this,center);}
        catch(error){
          if(error?.message==="Attempted to load an infinite number of tiles")return;
          throw error;
        }
      };
      let retryCount=0;
      let retryTimer=null;
      map.once("unload",()=>{if(retryTimer)clearTimeout(retryTimer);});
      layer.on("tileload",()=>{
        if(map!==this._familyMap || feedback.dataset.error==="1")return;
        const images=Array.from(map.getContainer().querySelectorAll("img.leaflet-tile"));
        if(images.length && images.every(image=>
           image.complete && image.naturalWidth>0 &&
           image.classList.contains("leaflet-tile-loaded"))){
          const status=feedback.querySelector("span");
          if(status)status.textContent=source==="ha"
            ?"Kortgrundlag indlæst via Home Assistant."
            :"Kortgrundlag indlæst fra OpenStreetMap.";
        }
      });
      layer.on("tileerror",()=>{
        failures++;
        if(retryCount<2 && !retryTimer){
          retryTimer=setTimeout(()=>{
            retryTimer=null;
            if(map!==this._familyMap || mode!==source)return;
            retryCount++;
            layer.redraw();
          },retryCount?6500:2500);
        }
        if(failures>=3 && Date.now()-lastRecovery>15000){
          lastRecovery=Date.now();
          notice(source==="ha"
            ?"Home Assistant kunne ikke hente kortfliser. Personer, "+
             "zoner og tegning virker stadig. Du kan prøve igen eller vælge "+
             "direkte kortfliser."
            :"OpenStreetMap afviste kortfliserne. Kontrollér forbindelsen "+
             "og browserens Referer-indstillinger.", source==="ha");
        }
      });
      layer.addTo(map);
      map._tinyFamilyBaseLayer=layer;
      map._tinyFamilyMapSource=source;
      // The HA token is good for at least 30 minutes, but the map may sit
      // open over a rotation. Renew while visible, never log or store token.
      if(source==="ha"){
        const onMove=async()=>{
          if(map!==this._familyMap || !element.isConnected)return;
          if(Date.now()-(this._mapTilesAuth?.at||0)<20*60*1000)return;
          try{
            const token=await this.mapTilesAccessToken(true);
            if(map===this._familyMap && mode==="ha"){
              layer.setUrl("/api/map_tiles/raster/{z}/{x}/{y}.png?token="+
                encodeURIComponent(token));
            }
          }catch(error){notice("Kunne ikke forny Home Assistant-kortadgang. "+
                               "Prøv igen.",true);}
        };
        map.on("moveend",onMove);
      }
    };
    if(hasProxy && !this._directTilesAllowed){
      try{
        const token=await this.mapTilesAccessToken();
        if(map!==this._familyMap || !element.isConnected)return;
        setLayer("/api/map_tiles/raster/{z}/{x}/{y}.png?token="+
                 encodeURIComponent(token),"ha");
      }catch(error){
        notice("Home Assistants kortfliser kunne ikke aktiveres. "+
          "Korttegning er stadig tilgængelig: "+error.message,true);
      }
    }else{
      if(map===this._familyMap && element.isConnected)setLayer(directUrl,"osm");
    }
  }

  async places(root) {
    const title=document.createElement("h2");
    title.textContent="Familiens steder";root.appendChild(title);
    const intro=document.createElement("p");intro.className="tf-message tf-screen-intro";
    intro.textContent="Steder er registrerede ophold, som Tiny Family lærer af GPS. Forslag deles med familien, medmindre administrator markerer dem private. Zoner er geografiske områder med en radius, som administrator opretter for at registrere ankomst og afgang og udløse relevante alarmer.";
    root.appendChild(intro);

    const create=document.createElement("details");create.className="tf-person tf-add-place";
    const head=document.createElement("summary");head.textContent="+ Tilføj et fælles sted";
    create.appendChild(head);
    const form=document.createElement("form");form.className="tf-shared-place-form";
    const nameLabel=document.createElement("label");
    nameLabel.textContent="Stedets navn";
    const name=document.createElement("input");name.type="text";name.maxLength=80;
    name.required=true;name.placeholder="Fx Skole, Arbejde eller Bedstemor";
    nameLabel.appendChild(name);form.appendChild(nameLabel);
    const hint=document.createElement("p");hint.className="tf-message";
    hint.textContent="Vælg et punkt på kortet, eller brug din seneste friske GPS-position.";
    form.appendChild(hint);
    const pointMap=document.createElement("div");pointMap.className="tf-map";
    pointMap.style.height="260px";pointMap.style.minHeight="260px";
    form.appendChild(pointMap);
    const coords=document.createElement("details");
    const coordsTitle=document.createElement("summary");
    coordsTitle.textContent="Koordinater (kan også indtastes)";
    coords.appendChild(coordsTitle);
    const coordRow=document.createElement("div");coordRow.className="tf-fields";
    const latLabel=document.createElement("label");latLabel.textContent="Breddegrad";
    const lat=document.createElement("input");lat.type="number";lat.step="any";lat.min="-90";lat.max="90";
    latLabel.appendChild(lat);
    const lonLabel=document.createElement("label");lonLabel.textContent="Længdegrad";
    const lon=document.createElement("input");lon.type="number";lon.step="any";lon.min="-180";lon.max="180";
    lonLabel.appendChild(lon);coordRow.append(latLabel,lonLabel);coords.appendChild(coordRow);
    form.appendChild(coords);
    const actions=document.createElement("div");actions.className="tf-shared-place-actions";
    const position=document.createElement("button");position.type="button";
    position.className="tf-save";position.textContent="Brug min position";
    const submit=document.createElement("button");submit.type="submit";
    submit.className="tf-save";submit.textContent="Gem som fælles sted";
    actions.append(position,submit);form.appendChild(actions);
    create.appendChild(form);root.appendChild(create);
    const previousPlaceDraft=this.readDraft("places-create");
    if(previousPlaceDraft){
      name.value=previousPlaceDraft.name||"";
      lat.value=previousPlaceDraft.latitude||"";
      lon.value=previousPlaceDraft.longitude||"";
      create.open=Boolean(previousPlaceDraft.open);
    }
    const savePlaceDraft=()=>{
      if(!name.value&&!lat.value&&!lon.value){
        this.clearDraft("places-create");return;
      }
      this.writeDraft("places-create",{
        name:name.value,latitude:lat.value,longitude:lon.value,open:create.open
      });
    };
    form.addEventListener("input",savePlaceDraft);
    form.addEventListener("change",savePlaceDraft);
    create.addEventListener("toggle",savePlaceDraft);
    const sharedTitle=document.createElement("h3");sharedTitle.textContent="Fælles steder";
    root.appendChild(sharedTitle);
    const sharedList=document.createElement("div");root.appendChild(sharedList);
    const ownDetails=document.createElement("details");ownDetails.className="tf-place-group";
    const ownTitle=document.createElement("summary");ownTitle.textContent="Mine registrerede ophold";
    ownDetails.appendChild(ownTitle);
    const ownList=document.createElement("div");ownDetails.appendChild(ownList);
    root.appendChild(ownDetails);
    const adminDetails=document.createElement("details");adminDetails.className="tf-place-group";
    const adminTitle=document.createElement("summary");
    adminTitle.textContent="Stedforslag fra familiens registrerede ophold";
    adminDetails.appendChild(adminTitle);
    const proposalHelp=document.createElement("p");proposalHelp.className="tf-message";
    proposalHelp.textContent="Forslag opstår efter gentagne ophold. Vælg Vis på kort for at se placeringen. Forslag deles med familien; administrator kan gøre enkelte private. Zoner oprettes separat og bruges til ankomst-/afgangsalarmer.";
    adminDetails.appendChild(proposalHelp);
    const proposalMapNode=document.createElement("div");
    proposalMapNode.className="tf-map tf-place-proposal-map";
    proposalMapNode.style.height="225px";proposalMapNode.style.minHeight="225px";
    adminDetails.appendChild(proposalMapNode);
    const proposalMapTitle=document.createElement("p");proposalMapTitle.className="tf-message";
    adminDetails.appendChild(proposalMapTitle);
    const adminList=document.createElement("div");adminDetails.appendChild(adminList);
    const managedDetails=document.createElement("details");
    managedDetails.className="tf-place-group";
    const managedTitle=document.createElement("summary");
    managedTitle.textContent="Registrerede opholdssteder · administrator";
    managedDetails.appendChild(managedTitle);
    const managedList=document.createElement("div");managedDetails.appendChild(managedList);

    root.classList.add("tf-places-view");
    const placeNav=document.createElement("nav");placeNav.className="tf-screen-nav";
    placeNav.setAttribute("aria-label","Vælg stedvisning");
    root.insertBefore(placeNav,create);
    const makePane=()=>{
      const pane=document.createElement("section");pane.className="tf-screen-panel";
      root.appendChild(pane);return pane;
    };
    const sharedPane=makePane(),ownPane=makePane(),adminPane=makePane(),zonePane=makePane();
    adminPane.hidden=true;
    zonePane.hidden=true;
    sharedPane.append(create,sharedTitle,sharedList);
    ownPane.appendChild(ownDetails);
    ownDetails.open=true;
    adminPane.appendChild(adminDetails);
    adminPane.appendChild(managedDetails);
    adminDetails.open=true;
    const savedPlaceView=this.readDraft("places-tab")||"shared";
    const placeViews=[
      {key:"shared",title:"Fælles",pane:sharedPane},
      {key:"mine",title:"Mine ophold",pane:ownPane},
      {key:"proposals",title:"Forslag",pane:adminPane},
      {key:"zones",title:"Zoner",pane:zonePane}
    ];
    const selectPlaceView=key=>{
      this.writeDraft("places-tab",key);
      if(key!=="shared" && map){
        map.remove();if(this._familyMap===map)this._familyMap=null;
        map=null;marker=null;
      }
      if(key!=="proposals" && proposalsMap){
        proposalsMap.remove();if(this._familyMap===proposalsMap)this._familyMap=null;
        proposalsMap=null;proposalLayers=null;
      }
      if(key!=="zones" && zoneMap){
        zoneMap.remove();if(this._familyMap===zoneMap)this._familyMap=null;
        zoneMap=null;zoneLayers=null;zoneDraftLayer=null;
      }
      for(const option of placeViews){
        option.pane.hidden=option.key!==key;
        option.button?.setAttribute("aria-pressed",String(option.key===key));
      }
      if(key==="proposals")ensureProposalMap();
      if(key==="shared" && create.open)ensurePlaceMap();
      if(key==="zones")ensureZoneMap();
    };
    for(const option of placeViews){
      const button=document.createElement("button");
      button.type="button";button.textContent=option.title;
      option.button=button;
      button.addEventListener("click",()=>selectPlaceView(option.key));
      placeNav.appendChild(button);
    }
    let map=null,chosen=(previousPlaceDraft&&Number.isFinite(Number(lat.value))&&
      Number.isFinite(Number(lon.value))&&lat.value!==""&&lon.value!=="")
      ?{latitude:Number(lat.value),longitude:Number(lon.value)}:null;
    let marker=null,mapLoading=false;
    let proposalsMap=null,proposalsLoading=false,proposalRows=[],proposalFocus=null;
    let proposalLayers=null;
    let zoneMap=null,zoneLayers=null,zoneDraftLayer=null,zoneMapLoading=false;
    let sharedDestinations=[];
    const drawProposalPins=()=>{
      if(!proposalsMap)return;
      if(proposalLayers){proposalLayers.remove();proposalLayers=null;}
      const layer=window.L.layerGroup().addTo(proposalsMap);
      proposalLayers=layer;
      const bounds=[];
      for(const row of proposalRows.slice(0,250)){
        const pos=[Number(row.latitude),Number(row.longitude)];
        if(!pos.every(Number.isFinite))continue;
        bounds.push(pos);
        const icon=window.L.circleMarker(pos,{
          radius:7,color:row.private?"#9b6dbb":"#26c9d6",
          weight:2,fillColor:row.private?"#b995e9":"#27b8c3",fillOpacity:.85
        }).addTo(layer);
        const popup=document.createElement("div");
        popup.textContent=row.person_name+" · "+row.name+(row.private?" · Privat":"");
        icon.bindPopup(popup);
      }
      if(proposalFocus){
        proposalsMap.setView([proposalFocus.latitude,proposalFocus.longitude],16);
      }else if(bounds.length){
        proposalsMap.fitBounds(bounds,{padding:[22,22],maxZoom:15});
      }else{
        proposalsMap.setView([this.hassInstance.config.latitude||0,
          this.hassInstance.config.longitude||0],11);
      }
    };
    const ensureProposalMap=async()=>{
      if(proposalsMap||proposalsLoading||adminPane.hidden||!adminDetails.open||this.active!=="places")return;
      proposalsLoading=true;
      try{
        await this.leaflet();
        if(adminPane.hidden||this.active!=="places")return;
        proposalsMap=this.createLeafletMap(proposalMapNode);
        await this.addBaseMap(proposalsMap,proposalMapNode);
        drawProposalPins();
        setTimeout(()=>proposalsMap?.invalidateSize(),140);
      }catch(error){proposalMapTitle.textContent="Kortet kunne ikke indlæses: "+this.errorText(error);}
      finally{proposalsLoading=false;}
    };
    adminDetails.addEventListener("toggle",()=>{
      if(adminDetails.open)ensureProposalMap();
    });
    const focusProposal=place=>{
      proposalFocus=place;
      proposalMapTitle.textContent=place.person_name+" · "+place.name+
        (place.private?" · Privat":" · Fælles stedforslag");
      if(proposalsMap){proposalsMap.setView([place.latitude,place.longitude],16);}
      else ensureProposalMap();
    };
    const choose=(latitude,longitude)=>{
      if(!Number.isFinite(latitude)||!Number.isFinite(longitude))return;
      chosen={latitude:Number(latitude.toFixed(6)),longitude:Number(longitude.toFixed(6))};
      lat.value=String(chosen.latitude);lon.value=String(chosen.longitude);
      savePlaceDraft();
      if(map){
        if(marker)marker.remove();
        marker=window.L.circleMarker([latitude,longitude],{
          radius:9,weight:2,color:"#fff",fillColor:"#9c56c4",fillOpacity:1
        }).addTo(map);
        map.setView([latitude,longitude],Math.max(14,map.getZoom()));
      }
    };
    const ensurePlaceMap=async()=>{
      if(map||mapLoading||!create.open||this.active!=="places")return;
      if(proposalsMap){
        proposalsMap.remove();if(this._familyMap===proposalsMap)this._familyMap=null;
        proposalsMap=null;proposalLayers=null;
      }
      mapLoading=true;
      try{
        await this.leaflet();
        if(this.active!=="places"||!create.open)return;
        map=this.createLeafletMap(pointMap);
        await this.addBaseMap(map,pointMap);
        const status=await this.hassInstance.callApi("GET","tiny_family/status")
          .catch(()=>null);
        if(this.active!=="places")return;
        const mine=status?.people?.find(item=>item.person===status.viewer_person);
        if(mine && Number.isFinite(mine.latitude) && Number.isFinite(mine.longitude)){
          map.setView([mine.latitude,mine.longitude],13);
        }else{
          map.setView([
            this.hassInstance.config.latitude||0,
            this.hassInstance.config.longitude||0
          ],11);
        }
        map.on("click",event=>choose(event.latlng.lat,event.latlng.lng));
        if(chosen)choose(chosen.latitude,chosen.longitude);
        setTimeout(()=>{if(this._familyMap===map)map.invalidateSize();},150);
      }catch(error){
        hint.textContent="Kortet kunne ikke indlæses. Du kan stadig angive koordinater manuelt.";
      }finally{
        mapLoading=false;
      }
    };
    create.addEventListener("toggle",()=>{
      if(create.open){
        ensurePlaceMap();
        if(map)setTimeout(()=>map.invalidateSize(),100);
      }
    });
    selectPlaceView("shared");
    const fill=(place,defaultName="")=>{
      selectPlaceView("shared");
      create.open=true;
      name.value=defaultName || (place.name==="Ukendt sted"?"":place.name)||"";
      choose(Number(place.latitude),Number(place.longitude));
      savePlaceDraft();
      ensurePlaceMap();
      create.scrollIntoView({behavior:"smooth",block:"start"});
      name.focus();
    };
    // Zones are geographical areas; destinations are points. A destination
    // may coincide with a zone's centre or live anywhere inside its border.
    const zoneHeading=document.createElement("h3");
    zoneHeading.textContent="Zoner og destinationer";
    const zoneExplanation=document.createElement("p");
    zoneExplanation.className="tf-screen-intro";
    zoneExplanation.textContent="Cirkelzoner er Home Assistant-zoner til ankomst og afgang. Tegnede polygonområder bruges af Tiny Family. Destinationer er selvstændige punkter og kan ligge både inde i og uden for zoner.";
    const zoneMapNode=document.createElement("div");
    zoneMapNode.className="tf-map tf-zone-map";
    zoneMapNode.style.height="275px";zoneMapNode.style.minHeight="275px";
    const zoneInfo=document.createElement("p");zoneInfo.className="tf-message";
    zoneInfo.textContent="Tryk på en zone eller destination på kortet for flere oplysninger.";
    zonePane.append(zoneHeading,zoneExplanation,zoneMapNode,zoneInfo);
    const zoneTools=document.createElement("details");zoneTools.className="tf-person tf-zone-editor";
    zoneTools.hidden=true;
    const zoneToolsTitle=document.createElement("summary");
    zoneToolsTitle.textContent="+ Tegn eller rediger zone · administrator";
    zoneTools.appendChild(zoneToolsTitle);
    zonePane.appendChild(zoneTools);
    const circular=document.createElement("form");circular.className="tf-shared-place-form";
    const circleLabel=document.createElement("strong");circleLabel.textContent="Home Assistant-zone (cirkel)";
    const makeTextField=(label,type="text")=>{
      const wrap=document.createElement("label");wrap.textContent=label;
      const input=document.createElement("input");input.type=type;
      wrap.appendChild(input);return {wrap,input};
    };
    const circleExisting=document.createElement("select");
    circleExisting.setAttribute("aria-label","Vælg zone, der skal redigeres");
    const circleName=makeTextField("Navn");circleName.input.maxLength=80;circleName.input.required=true;
    const circleRadius=makeTextField("Radius i meter (25–5000)","number");
    circleRadius.input.min="25";circleRadius.input.max="5000";
    circleRadius.input.value="100";circleRadius.input.required=true;
    const circleLocation=document.createElement("p");circleLocation.className="tf-message";
    circleLocation.textContent="Tryk på kortet for at placere centrum.";
    const circleDestination=document.createElement("label");
    const alsoDestination=document.createElement("input");alsoDestination.type="checkbox";
    circleDestination.append(alsoDestination,document.createTextNode(
      " Opret også et fælles destinationspunkt i centrum"));
    const circleActions=document.createElement("div");circleActions.className="tf-card-actions";
    const startCircle=document.createElement("button");startCircle.type="button";
    startCircle.className="tf-save";startCircle.textContent="Vælg centrum på kortet";
    const saveCircle=document.createElement("button");saveCircle.type="submit";
    saveCircle.className="tf-save";saveCircle.textContent="Gem cirkulær zone";
    const removeCircle=document.createElement("button");removeCircle.type="button";
    removeCircle.className="tf-save tf-danger";removeCircle.textContent="Slet valgt zone";
    removeCircle.disabled=true;
    circleActions.append(startCircle,saveCircle,removeCircle);
    circular.append(circleLabel,circleExisting,circleName.wrap,circleRadius.wrap,
      circleLocation,circleDestination,circleActions);
    zoneTools.appendChild(circular);
    const polygonEditor=document.createElement("form");
    polygonEditor.className="tf-shared-place-form tf-zone-polygon-editor";
    const polygonLabel=document.createElement("strong");
    polygonLabel.textContent="Tiny Family-zone (tegn polygon)";
    const polygonExisting=document.createElement("select");
    polygonExisting.setAttribute("aria-label","Vælg polygonområde, der skal redigeres");
    const polygonName=makeTextField("Navn på polygon");
    polygonName.input.maxLength=80;polygonName.input.required=true;
    const polygonHint=document.createElement("p");polygonHint.className="tf-message";
    polygonHint.textContent="Tegn mindst 3 og højst 32 hjørner på kortet.";
    const polygonActions=document.createElement("div");polygonActions.className="tf-card-actions";
    const startPolygon=document.createElement("button");startPolygon.type="button";
    startPolygon.className="tf-save";startPolygon.textContent="Start polygontegning";
    const undoVertex=document.createElement("button");undoVertex.type="button";
    undoVertex.className="tf-save";undoVertex.textContent="Fortryd hjørne";
    const savePolygon=document.createElement("button");savePolygon.type="submit";
    savePolygon.className="tf-save";savePolygon.textContent="Gem polygonzone";
    const deletePolygon=document.createElement("button");deletePolygon.type="button";
    deletePolygon.className="tf-save tf-danger";deletePolygon.textContent="Slet polygon";
    deletePolygon.disabled=true;
    polygonActions.append(startPolygon,undoVertex,savePolygon,deletePolygon);
    polygonEditor.append(polygonLabel,polygonExisting,polygonName.wrap,
      polygonHint,polygonActions);
    zoneTools.appendChild(polygonEditor);
    const zoneList=document.createElement("div");zoneList.className="tf-zone-list";
    zonePane.appendChild(zoneList);
    let zoneRows=[],polygonRows=[],editableZoneRows=[];
    let editingMode=null,circleCenter=null,polygonVertices=[];
    const zoneDraft=this.readDraft("places-zone");
    if(zoneDraft){
      circleName.input.value=zoneDraft.circleName||"";
      circleRadius.input.value=zoneDraft.circleRadius||"100";
      alsoDestination.checked=Boolean(zoneDraft.alsoDestination);
      polygonName.input.value=zoneDraft.polygonName||"";
      circleCenter=Array.isArray(zoneDraft.circleCenter)&&
        zoneDraft.circleCenter.every(Number.isFinite)?zoneDraft.circleCenter:null;
      polygonVertices=Array.isArray(zoneDraft.polygonVertices)?
        zoneDraft.polygonVertices.filter(p=>Array.isArray(p)&&p.length===2&&
          p.every(Number.isFinite)).slice(0,32):[];
      editingMode=["circle","polygon"].includes(zoneDraft.mode)?zoneDraft.mode:null;
      if(editingMode==="polygon")startPolygon.textContent="Afslut tegning";
      if(editingMode==="circle")startCircle.textContent="Tryk på kortet…";
      if(circleCenter)circleLocation.textContent="Centrum: "+
        circleCenter.map(x=>x.toFixed(6)).join(", ");
      circleExisting.dataset.pendingId=zoneDraft.circleId||"";
      polygonExisting.dataset.pendingId=zoneDraft.polygonId||"";
      zoneTools.open=Boolean(zoneDraft.open);
    }
    const saveZoneDraft=()=>this.writeDraft("places-zone",{
      circleId:circleExisting.value,circleName:circleName.input.value,
      circleRadius:circleRadius.input.value,alsoDestination:alsoDestination.checked,
      circleCenter,polygonId:polygonExisting.value,
      polygonName:polygonName.input.value,polygonVertices,mode:editingMode,
      open:zoneTools.open
    });
    zoneTools.addEventListener("input",saveZoneDraft);
    zoneTools.addEventListener("change",saveZoneDraft);
    zoneTools.addEventListener("toggle",saveZoneDraft);
    const metersBetween=(a,b)=>{
      const x=(a[1]-b[1])*111320*Math.cos((a[0]+b[0])*Math.PI/360);
      const y=(a[0]-b[0])*111320;return Math.hypot(x,y);
    };
    const inPolygon=(p,pts)=>{
      let inside=false;
      for(let i=0,j=pts.length-1;i<pts.length;j=i++){
        const a=pts[i],b=pts[j];
        if((a[0]>p[0])!==(b[0]>p[0]) &&
           p[1]<(b[1]-a[1])*(p[0]-a[0])/(b[0]-a[0])+a[1])inside=!inside;
      }
      return inside;
    };
    const polygonInterior=pts=>{
      const middle=[pts.reduce((s,p)=>s+p[0],0)/pts.length,
        pts.reduce((s,p)=>s+p[1],0)/pts.length];
      if(inPolygon(middle,pts))return middle;
      const latitude=(Math.min(...pts.map(p=>p[0]))+
        Math.max(...pts.map(p=>p[0])))/2;
      const hits=[];
      for(let i=0;i<pts.length;i++){
        const a=pts[i],b=pts[(i+1)%pts.length];
        if((a[0]>latitude)!==(b[0]>latitude))
          hits.push(a[1]+(b[1]-a[1])*(latitude-a[0])/(b[0]-a[0]));
      }
      hits.sort((a,b)=>a-b);
      return hits.length>=2?[latitude,(hits[0]+hits[1])/2]:pts[0];
    };
    const zonePreview=()=>{
      if(!zoneMap)return;
      if(zoneDraftLayer){zoneDraftLayer.remove();zoneDraftLayer=null;}
      if(circleCenter){
        const radius=Number(circleRadius.input.value);
        if(Number.isFinite(radius)&&radius>=25&&radius<=5000){
          zoneDraftLayer=window.L.circle(circleCenter,{radius,color:"#f2b76a",
            weight:3,dashArray:"6 5",fillOpacity:.12}).addTo(zoneMap);
        }
      }else if(polygonVertices.length){
        zoneDraftLayer=(polygonVertices.length>=3
          ?window.L.polygon(polygonVertices,{color:"#f2b76a",weight:3,
            dashArray:"6 5",fillOpacity:.15})
          :window.L.polyline(polygonVertices,{color:"#f2b76a",weight:3,
            dashArray:"6 5"})).addTo(zoneMap);
      }
    };
    const drawZoneMap=()=>{
      if(!zoneMap)return;
      if(zoneLayers){zoneLayers.remove();zoneLayers=null;}
      zoneLayers=window.L.layerGroup().addTo(zoneMap);
      const bounds=[];
      for(const zone of zoneRows){
        const pos=[zone.latitude,zone.longitude];
        if(!pos.every(Number.isFinite))continue;
        bounds.push(pos);
        const layer=window.L.circle(pos,{radius:zone.radius_m,color:"#24c9d9",
          weight:2,fillOpacity:.09}).addTo(zoneLayers);
        const tooltip=document.createElement("span");
        tooltip.textContent=zone.name+" · HA-zone";
        layer.bindTooltip(tooltip);
      }
      for(const polygon of polygonRows){
        if(!Array.isArray(polygon.points)||polygon.points.length<3)continue;
        const tooltip=document.createElement("span");
        tooltip.textContent=polygon.name+" · Polygonzone";
        window.L.polygon(polygon.points,{color:"#9f7cd2",weight:2,
          fillOpacity:.12}).addTo(zoneLayers).bindTooltip(tooltip);
        bounds.push(...polygon.points);
      }
      for(const destination of sharedDestinations){
        const pos=[destination.latitude,destination.longitude];
        if(!pos.every(Number.isFinite))continue;
        const tooltip=document.createElement("span");
        tooltip.textContent=destination.name+" · Destination";
        window.L.circleMarker(pos,{radius:6,color:"#fff",weight:2,
          fillColor:"#e6a968",fillOpacity:.95}).addTo(zoneLayers)
          .bindTooltip(tooltip);
      }
      zonePreview();
      if(circleCenter&&zoneTools.open)zoneMap.setView(circleCenter,16);
      else if(polygonVertices.length&&zoneTools.open)
        zoneMap.fitBounds(polygonVertices,{padding:[24,24],maxZoom:16});
      else if(bounds.length)zoneMap.fitBounds(bounds,{padding:[24,24],maxZoom:15});
      else zoneMap.setView([this.hassInstance.config.latitude||0,
        this.hassInstance.config.longitude||0],12);
    };
    const resetZoneDrawing=()=>{
      editingMode=null;circleCenter=null;polygonVertices=[];
      startCircle.textContent="Vælg centrum på kortet";
      startPolygon.textContent="Start polygontegning";
      zonePreview();
    };
    startCircle.addEventListener("click",()=>{
      editingMode="circle";polygonVertices=[];circleCenter=null;
      startCircle.textContent="Tryk på kortet…";
      zonePreview();saveZoneDraft();
    });
    circleRadius.input.addEventListener("input",zonePreview);
    startPolygon.addEventListener("click",()=>{
      editingMode=editingMode==="polygon"?null:"polygon";
      circleCenter=null;
      if(editingMode==="polygon")polygonVertices=[];
      startPolygon.textContent=editingMode==="polygon"
        ?"Afslut tegning":"Start polygontegning";
      zonePreview();saveZoneDraft();
    });
    undoVertex.addEventListener("click",()=>{
      polygonVertices.pop();zonePreview();
      polygonHint.textContent=polygonVertices.length+" hjørner tegnet.";
      saveZoneDraft();
    });
    const ensureZoneMap=async()=>{
      if(zoneMap||zoneMapLoading||zonePane.hidden||this.active!=="places")return;
      zoneMapLoading=true;
      try{
        await this.leaflet();
        if(zonePane.hidden||this.active!=="places")return;
        zoneMap=this.createLeafletMap(zoneMapNode);
        await this.addBaseMap(zoneMap,zoneMapNode);
        zoneMap.on("click",event=>{
          if(editingMode==="circle"){
            circleCenter=[event.latlng.lat,event.latlng.lng];
            circleLocation.textContent="Centrum: "+circleCenter.map(x=>x.toFixed(6)).join(", ");
            editingMode=null;startCircle.textContent="Flyt centrum";
          }else if(editingMode==="polygon"&&polygonVertices.length<32){
            polygonVertices.push([event.latlng.lat,event.latlng.lng]);
            polygonHint.textContent=polygonVertices.length+" hjørner tegnet.";
          }
          zonePreview();
          saveZoneDraft();
        });
        await reloadZones();
        if(zoneMap)zoneMap.invalidateSize();
      }catch(error){zoneInfo.textContent="Zonekortet kunne ikke indlæses: "+this.errorText(error);}
      finally{zoneMapLoading=false;}
    };
    const zoneCard=(label,description,location,focus,related)=>{
      const card=document.createElement("section");card.className="tf-person";
      const heading=document.createElement("strong");heading.textContent=label;
      const details=document.createElement("p");details.className="tf-message";
      details.textContent=description+(related.length?
        " · Destinationer inde i zonen: "+related.map(p=>p.name).join(", "):"");
      const actions=document.createElement("div");actions.className="tf-card-actions";
      const view=document.createElement("button");view.type="button";
      view.className="tf-save";view.textContent="Vis på kort";
      view.addEventListener("click",()=>{if(zoneMap)zoneMap.setView(focus,16);});
      const destination=document.createElement("button");destination.type="button";
      destination.className="tf-save";
      const alreadyExists=related.some(item=>metersBetween(
        [item.latitude,item.longitude],location)<10);
      destination.textContent=alreadyExists?"Destination findes":"Opret destination her";
      destination.disabled=alreadyExists;
      if(!alreadyExists)destination.addEventListener("click",()=>fill({
        latitude:location[0],longitude:location[1],name:label
      },label));
      actions.append(view,destination);card.append(heading,details,actions);
      return card;
    };
    const reloadZones=async()=>{
      const canEdit=!zoneTools.hidden;
      const [status,geo,stored]=await Promise.all([
        this.hassInstance.callApi("GET","tiny_family/status"),
        this.hassInstance.callApi("GET","tiny_family/geofences"),
        canEdit?this.hassInstance.callApi("GET","tiny_family/zones").catch(()=>({zones:[]})):
          Promise.resolve({zones:[]})
      ]);
      zoneRows=[...(status.zones||[])];
      polygonRows=geo.geofences||[];
      editableZoneRows=stored.zones||[];
      // HA's zone entity may be published a moment after storage saves.
      // Show the stored item immediately without drawing it twice later.
      for(const storedZone of editableZoneRows){
        const centre=[storedZone.latitude,storedZone.longitude];
        if(!centre.every(Number.isFinite)||!Number.isFinite(storedZone.radius))continue;
        if(!zoneRows.some(zone=>zone.name===storedZone.name &&
            metersBetween([zone.latitude,zone.longitude],centre)<10)){
          zoneRows.push({id:storedZone.id,name:storedZone.name,
            latitude:storedZone.latitude,longitude:storedZone.longitude,
            radius_m:storedZone.radius});
        }
      }
      const selectedCircle=circleExisting.value||circleExisting.dataset.pendingId||"";
      const selectedPolygon=polygonExisting.value||polygonExisting.dataset.pendingId||"";
      circleExisting.dataset.pendingId="";polygonExisting.dataset.pendingId="";
      circleExisting.replaceChildren();
      const circleNew=document.createElement("option");circleNew.value="";
      circleNew.textContent="Opret ny cirkelzone";circleExisting.appendChild(circleNew);
      for(const zone of editableZoneRows){
        const opt=document.createElement("option");opt.value=zone.id;
        opt.textContent=zone.name;circleExisting.appendChild(opt);
      }
      circleExisting.value=selectedCircle;
      polygonExisting.replaceChildren();
      const polygonNew=document.createElement("option");polygonNew.value="";
      polygonNew.textContent="Opret ny polygon";polygonExisting.appendChild(polygonNew);
      for(const polygon of polygonRows){
        const opt=document.createElement("option");opt.value=polygon.id;
        opt.textContent=polygon.name;polygonExisting.appendChild(opt);
      }
      polygonExisting.value=selectedPolygon;
      removeCircle.disabled=!circleExisting.value;
      deletePolygon.disabled=!polygonExisting.value;
      zoneList.replaceChildren();
      for(const zone of zoneRows){
        const centre=[zone.latitude,zone.longitude];
        const related=sharedDestinations.filter(p=>
          metersBetween(centre,[p.latitude,p.longitude])<=zone.radius_m);
        zoneList.appendChild(zoneCard(zone.name,"HA-cirkel · radius "+
          Math.round(zone.radius_m)+" m",centre,centre,related));
      }
      for(const polygon of polygonRows){
        if(!Array.isArray(polygon.points)||polygon.points.length<3)continue;
        const position=polygonInterior(polygon.points);
        const related=sharedDestinations.filter(p=>
          inPolygon([p.latitude,p.longitude],polygon.points));
        zoneList.appendChild(zoneCard(polygon.name,"Tiny Family-polygon · "+
          polygon.points.length+" hjørner",position,position,related));
      }
      if(!zoneList.children.length){
        const note=document.createElement("p");note.className="tf-empty";
        note.textContent="Ingen zoner endnu. En administrator kan tegne en cirkel eller polygon på kortet.";
        zoneList.appendChild(note);
      }
      drawZoneMap();
    };
    circleExisting.addEventListener("change",()=>{
      resetZoneDrawing();
      const item=editableZoneRows.find(zone=>zone.id===circleExisting.value);
      circleName.input.value=item?.name||"";
      circleRadius.input.value=String(item?.radius||100);
      removeCircle.disabled=!item;
      if(item){circleCenter=[item.latitude,item.longitude];
        zoneMap?.setView(circleCenter,16);zonePreview();}
      saveZoneDraft();
    });
    polygonExisting.addEventListener("change",()=>{
      resetZoneDrawing();
      const item=polygonRows.find(zone=>zone.id===polygonExisting.value);
      polygonName.input.value=item?.name||"";
      polygonVertices=item?.points?.map(p=>[p[0],p[1]])||[];
      deletePolygon.disabled=!item;zonePreview();
      saveZoneDraft();
    });
    circular.addEventListener("submit",async event=>{
      event.preventDefault();
      if(!circleCenter){this.message("Tryk på zonekortet for at vælge centrum.",true);return;}
      saveCircle.disabled=true;
      const payload={name:circleName.input.value.trim(),radius:Number(circleRadius.input.value),
        latitude:circleCenter[0],longitude:circleCenter[1]};
      try{
        await this.hassInstance.callApi(circleExisting.value?"PUT":"POST",
          "tiny_family/zones",{...payload,...(circleExisting.value?
            {zone_id:circleExisting.value}:{})});
        let destinationNotice="";
        if(alsoDestination.checked){
          try{await this.hassInstance.callApi("POST","tiny_family/places",
            {kind:"shared",name:payload.name,latitude:payload.latitude,
              longitude:payload.longitude});
          }catch(error){destinationNotice=" · Destinationen blev ikke gemt: "+this.errorText(error);}
        }
        circleExisting.value="";circleName.input.value="";alsoDestination.checked=false;
        resetZoneDrawing();
        this.clearDraft("places-zone");
        await load();await reloadZones();
        this.message("Zonen er gemt."+destinationNotice,Boolean(destinationNotice));
      }catch(error){this.message("Zonen kunne ikke gemmes: "+this.errorText(error),true);}
      finally{saveCircle.disabled=false;}
    });
    polygonEditor.addEventListener("submit",async event=>{
      event.preventDefault();
      if(polygonVertices.length<3){this.message("Tegn mindst tre hjørner.",true);return;}
      savePolygon.disabled=true;
      try{
        await this.hassInstance.callApi(polygonExisting.value?"PUT":"POST",
          "tiny_family/geofences",{name:polygonName.input.value.trim(),
            points:polygonVertices,...(polygonExisting.value?{id:polygonExisting.value}:{})});
        polygonExisting.value="";polygonName.input.value="";
        resetZoneDrawing();this.clearDraft("places-zone");await reloadZones();
        this.message("Polygonzonen er gemt.");
      }catch(error){this.message("Polygonzonen kunne ikke gemmes: "+this.errorText(error),true);}
      finally{savePolygon.disabled=false;}
    });
    removeCircle.addEventListener("click",async()=>{
      if(!circleExisting.value||!window.confirm("Slet denne HA-zone permanent?"))return;
      removeCircle.disabled=true;
      try{await this.hassInstance.callApi("DELETE","tiny_family/zones",
        {zone_id:circleExisting.value,confirm:true});
        circleExisting.value="";circleName.input.value="";resetZoneDrawing();
        this.clearDraft("places-zone");
        await reloadZones();this.message("Zonen er slettet.");
      }catch(error){this.message("Kunne ikke slette zone: "+this.errorText(error),true);}
      finally{removeCircle.disabled=!circleExisting.value;}
    });
    deletePolygon.addEventListener("click",async()=>{
      if(!polygonExisting.value||!window.confirm("Slet denne polygonzone permanent?"))return;
      deletePolygon.disabled=true;
      try{await this.hassInstance.callApi("DELETE","tiny_family/geofences",
        {id:polygonExisting.value,confirm:true});
        polygonExisting.value="";polygonName.input.value="";resetZoneDrawing();
        this.clearDraft("places-zone");
        await reloadZones();this.message("Polygonzonen er slettet.");
      }catch(error){this.message("Kunne ikke slette polygon: "+this.errorText(error),true);}
      finally{deletePolygon.disabled=!polygonExisting.value;}
    });
    const call=async(method,payload,success,onSaved)=>{
      try{
        const result=await this.hassInstance.callApi(method,"tiny_family/places",payload);
        this.message(result?.existing
          ?"Stedet findes allerede som '"+result.name+"'. Intet dubletsted blev oprettet."
          :success);
        onSaved?.();
        await load();
        return true;
      }catch(error){this.message("Stedet kunne ikke gemmes: "+this.errorText(error),true);return false;}
    };
    const openMaps=place=>{
      const button=document.createElement("button");button.type="button";
      button.className="tf-save";button.textContent="Vis på kort";
      button.addEventListener("click",()=>this.openLocationDialog(place,button));
      return button;
    };
    const labelInput=(title,value)=>{
      const wrapper=document.createElement("label");wrapper.textContent=title;
      const input=document.createElement("input");
      input.type="text";input.value=String(value ?? "");
      input.style.cssText="width:100%;padding:9px;color:var(--primary-text-color);background:var(--primary-background-color);border:1px solid var(--divider-color);border-radius:9px";
      wrapper.appendChild(input);return {wrapper,input};
    };
    const sharedEditDrafts=this.readDraft("places-shared-edits")||{};
    const persistSharedEdits=()=>{
      if(Object.keys(sharedEditDrafts).length)
        this.writeDraft("places-shared-edits",sharedEditDrafts);
      else this.clearDraft("places-shared-edits");
    };
    const load=async()=>{
      const data=await this.hassInstance.callApi("GET","tiny_family/places");
      if(this.active!=="places")return;
      sharedDestinations=data.shared_places||[];
      zoneTools.hidden=!data.can_manage_all_places;
      sharedList.replaceChildren();ownList.replaceChildren();adminList.replaceChildren();
      for(const place of data.shared_places||[]){
        const card=document.createElement("section");card.className="tf-person";
        const heading=document.createElement("strong");heading.textContent=place.name;
        const meta=document.createElement("p");
        meta.className="tf-message";
        meta.textContent="Oprettet af "+(place.created_by_name||"Familiemedlem");
        card.append(heading,meta,openMaps(place));
        if(place.can_edit){
          const edit=document.createElement("details");
          const editTitle=document.createElement("summary");editTitle.textContent="Rediger sted";
          edit.appendChild(editTitle);
          const pending=sharedEditDrafts[place.id];
          edit.open=Boolean(pending?.open);
          const newName=labelInput("Navn",pending?.name??place.name);
          const newLat=labelInput("Breddegrad",pending?.latitude??place.latitude);
          const newLon=labelInput("Længdegrad",pending?.longitude??place.longitude);
          edit.append(newName.wrapper,newLat.wrapper,newLon.wrapper);
          const remember=()=>{
            if(!edit.open && newName.input.value===place.name &&
               newLat.input.value===String(place.latitude) &&
               newLon.input.value===String(place.longitude)){
              delete sharedEditDrafts[place.id];
            }else sharedEditDrafts[place.id]={
              open:edit.open,name:newName.input.value,
              latitude:newLat.input.value,longitude:newLon.input.value
            };
            persistSharedEdits();
          };
          edit.addEventListener("input",remember);
          edit.addEventListener("toggle",remember);
          const editActions=document.createElement("div");editActions.className="tf-card-actions";
          const save=document.createElement("button");save.type="button";
          save.className="tf-save";save.textContent="Gem ændringer";
          save.addEventListener("click",async()=>{
            const latitude=Number(newLat.input.value),longitude=Number(newLon.input.value);
            if(!newLat.input.value.trim()||!newLon.input.value.trim()||
               !Number.isFinite(latitude)||!Number.isFinite(longitude)){
              this.message("Indtast gyldige koordinater.",true);return;
            }
            save.disabled=true;
            await call("PUT",{shared_id:place.id,name:newName.input.value.trim(),
              latitude,longitude},"Fælles sted opdateret.",()=>{
                delete sharedEditDrafts[place.id];persistSharedEdits();
              });
            save.disabled=false;
          });
          const remove=document.createElement("button");remove.type="button";
          remove.className="tf-save";remove.textContent="Slet sted";
          remove.style.background="var(--error-color,#b3261e)";
          remove.addEventListener("click",async()=>{
            if(!window.confirm("Slet dette fælles sted for alle familiemedlemmer?"))return;
            remove.disabled=true;
            await call("DELETE",{shared_id:place.id},"Fælles sted slettet.",()=>{
              delete sharedEditDrafts[place.id];persistSharedEdits();
            });
            remove.disabled=false;
          });
          editActions.appendChild(save);
          if(place.can_delete)editActions.appendChild(remove);
          edit.appendChild(editActions);
          card.appendChild(edit);
        }
        sharedList.appendChild(card);
      }
      if(!sharedList.children.length){
        const empty=document.createElement("p");empty.className="tf-empty";
        empty.textContent="Ingen fælles steder endnu. Opret det første ovenfor.";
        sharedList.appendChild(empty);
      }
      for(const place of data.places||[]){
        if(place.status==="zone")continue; // HA zones have their own Zoner view.
        const card=document.createElement("section");card.className="tf-person";
        const heading=document.createElement("strong");
        heading.textContent=place.name+" · "+(place.status==="suggested"?"Forslag":"Ophold");
        const info=document.createElement("p");
        info.textContent=place.visits+" besøg · "+place.minutes+" minutter";
        const actions=document.createElement("div");actions.className="tf-card-actions";
        const publish=document.createElement("button");publish.type="button";
        publish.className="tf-save";publish.textContent="Del med familien";
        publish.addEventListener("click",()=>fill(place));
        if(!place.private||data.can_manage_all_places)actions.appendChild(publish);
        actions.appendChild(openMaps(place));
        if(place.private){
          const privacyLabel=document.createElement("span");
          privacyLabel.className="tf-chip";privacyLabel.textContent="Privat efter administratorvalg";
          actions.appendChild(privacyLabel);
        }
        card.append(heading,info,actions);
        if(place.status!=="zone" && data.can_manage_all_places){
          const edit=document.createElement("details");
          const editTitle=document.createElement("summary");editTitle.textContent="Ret navn på ophold";
          edit.appendChild(editTitle);
          const renameField=labelInput("Navn",place.name==="Ukendt sted"?"":place.name);
          edit.appendChild(renameField.wrapper);
          const editActions=document.createElement("div");editActions.className="tf-card-actions";
          const rename=document.createElement("button");rename.type="button";
          rename.className="tf-save";rename.textContent="Gem navn";
          rename.addEventListener("click",async()=>{
            rename.disabled=true;
            await call("PUT",{name:renameField.input.value.trim(),
              latitude:place.latitude,longitude:place.longitude},"Stednavn opdateret.");
            rename.disabled=false;
          });
          const remove=document.createElement("button");remove.type="button";
          remove.className="tf-save";remove.textContent="Fjern ophold";
          remove.style.background="var(--error-color,#b3261e)";
          remove.addEventListener("click",async()=>{
            if(!window.confirm("Fjern dette indlærte ophold fra din personlige historik?"))return;
            remove.disabled=true;
            await call("DELETE",{latitude:place.latitude,longitude:place.longitude},
              "Ophold fjernet.");
            remove.disabled=false;
          });
          editActions.appendChild(rename);
          editActions.appendChild(remove);
          edit.appendChild(editActions);
          card.appendChild(edit);
        }
        ownList.appendChild(card);
      }
      if(!ownList.children.length){
        const empty=document.createElement("p");
        empty.textContent="Der er endnu ingen indlærte ophold.";
        ownList.appendChild(empty);
      }
      {
        if(!adminDetails.isConnected)adminPane.prepend(adminDetails);
        managedDetails.hidden=!data.can_manage_all_places;
        managedList.replaceChildren();
        if(data.can_manage_all_places){
          for(const place of data.managed_places||[]){
            const card=document.createElement("section");card.className="tf-person";
            const heading=document.createElement("strong");
            heading.textContent=place.person_name+" · "+place.name;
            const info=document.createElement("p");
            info.textContent=place.visits+" besøg · "+place.minutes+" min"+
              (place.private?" · Privat":"");
            const actions=document.createElement("div");actions.className="tf-card-actions";
            actions.appendChild(openMaps(place));
            const rename=document.createElement("button");rename.type="button";
            rename.className="tf-save";rename.textContent="Ret navn";
            rename.addEventListener("click",async()=>{
              const value=window.prompt("Nyt stednavn",place.name);
              if(value===null||!value.trim())return;
              rename.disabled=true;
              await call("PUT",{person:place.person,name:value.trim(),
                latitude:place.latitude,longitude:place.longitude},"Stedet er opdateret.");
              rename.disabled=false;
            });
            const privacy=document.createElement("button");privacy.type="button";
            privacy.className="tf-save";
            privacy.textContent=place.private?"Gør fælles":"Gør privat";
            privacy.addEventListener("click",async()=>{
              privacy.disabled=true;
              await call("PUT",{kind:"privacy",person:place.person,
                latitude:place.latitude,longitude:place.longitude,
                private:!place.private},"Synlighed opdateret.");
              privacy.disabled=false;
            });
            const remove=document.createElement("button");remove.type="button";
            remove.className="tf-save";remove.textContent="Slet sted";
            remove.style.background="var(--error-color,#b3261e)";
            remove.addEventListener("click",async()=>{
              if(!window.confirm("Slet dette registrerede sted?"))return;
              remove.disabled=true;
              await call("DELETE",{person:place.person,
                latitude:place.latitude,longitude:place.longitude},"Stedet er slettet.");
              remove.disabled=false;
            });
            actions.append(rename,privacy,remove);
            card.append(heading,info,actions);managedList.appendChild(card);
          }
          if(!managedList.children.length)managedList.textContent="Ingen navngivne opholdssteder.";
        }
        proposalRows=data.family_suggestions||[];
        if(proposalFocus && !proposalRows.some(row=>
          row.person===proposalFocus.person && row.latitude===proposalFocus.latitude &&
          row.longitude===proposalFocus.longitude))proposalFocus=null;
        drawProposalPins();
        for(const place of proposalRows){
          const card=document.createElement("section");card.className="tf-person";
          const heading=document.createElement("strong");
          heading.textContent=(place.sources_count>1
            ?"Samlet forslag · "+place.people.join(", ")
            :place.person_name+" · "+place.name);
          const info=document.createElement("p");
          info.textContent=place.visits+" besøg · "+place.minutes+" minutter"+
            (place.sources_count>1?" · "+place.sources_count+" nærliggende registreringer":"")+
            (place.last?" · sidst "+place.last:"")+
            (place.private?" · PRIVAT":"");
          const actions=document.createElement("div");actions.className="tf-card-actions";
          let groupedDetails=null;
          const showOnMap=document.createElement("button");
          showOnMap.type="button";showOnMap.className="tf-save";
          showOnMap.textContent="Vis på kort";
          showOnMap.addEventListener("click",()=>focusProposal(place));
          actions.appendChild(showOnMap);
          const publish=document.createElement("button");publish.type="button";
          publish.className="tf-save";publish.textContent="Opret fælles sted";
          publish.addEventListener("click",()=>fill(place));
          if(!place.private||data.can_manage_all_places)actions.appendChild(publish);
          if(data.can_manage_all_places){
          const zone=document.createElement("button");zone.type="button";
          zone.className="tf-save";zone.textContent="Opret HA-zone";
          zone.addEventListener("click",()=>{
            selectPlaceView("zones");zoneTools.open=true;
            circleExisting.value="";
            circleName.input.value=place.name==="Ukendt sted"?"":place.name;
            circleRadius.input.value="100";
            // Promoting a proposal to a zone also creates its named point,
            // unless the administrator explicitly unchecks this option.
            alsoDestination.checked=true;
            polygonVertices=[];circleCenter=[place.latitude,place.longitude];
            editingMode=null;zonePreview();saveZoneDraft();
            zoneMap?.setView(circleCenter,16);
          });
          if((place.sources_count||1)===1){
          const rename=document.createElement("button");rename.type="button";
          rename.className="tf-save";rename.textContent="Ret stednavn";
          rename.addEventListener("click",async()=>{
            const named=window.prompt("Ret navn for "+place.person_name,place.name==="Ukendt sted"?"":place.name);
            if(named===null||!named.trim())return;
            rename.disabled=true;
            await call("PUT",{person:place.person,name:named.trim(),
              latitude:place.latitude,longitude:place.longitude},"Opholdssted opdateret.");
            rename.disabled=false;
          });
          const privateToggle=document.createElement("button");
          privateToggle.type="button";privateToggle.className="tf-save";
          privateToggle.textContent=place.private?"Gør forslaget fælles":"Markér som privat";
          privateToggle.addEventListener("click",async()=>{
            privateToggle.disabled=true;
            await call("PUT",{kind:"privacy",person:place.person,
              latitude:place.latitude,longitude:place.longitude,
              private:!place.private},
              place.private?"Forslaget er nu synligt for familien.":"Forslaget er nu privat.");
            privateToggle.disabled=false;
          });
          const removeSuggestion=document.createElement("button");
          removeSuggestion.type="button";removeSuggestion.className="tf-save";
          removeSuggestion.style.background="var(--error-color,#b3261e)";
          removeSuggestion.textContent="Slet forslag";
          removeSuggestion.addEventListener("click",async()=>{
            if(!window.confirm("Slet dette indlærte forslag permanent?"))return;
            removeSuggestion.disabled=true;
            await call("DELETE",{person:place.person,
              latitude:place.latitude,longitude:place.longitude},"Forslaget er slettet.");
            removeSuggestion.disabled=false;
          });
          actions.append(zone,rename,privateToggle,removeSuggestion);
          }else{
            actions.appendChild(zone);
            const distinct=document.createElement("details");
            distinct.className="tf-place-group";
            const distinctTitle=document.createElement("summary");
            distinctTitle.textContent="Administrer de "+place.sources_count+" enkelte ophold";
            distinct.appendChild(distinctTitle);
            for(const source of place.sources||[]){
              const row=document.createElement("div");row.className="tf-person";
              const label=document.createElement("strong");
              label.textContent=source.person_name+" · "+source.visits+" besøg";
              const rowActions=document.createElement("div");
              rowActions.className="tf-card-actions";
              const renameOne=document.createElement("button");
              renameOne.type="button";renameOne.className="tf-save";
              renameOne.textContent="Navngiv";
              renameOne.addEventListener("click",async()=>{
                const value=window.prompt("Navn på ophold for "+source.person_name,
                  source.name==="Ukendt sted"?"":source.name);
                if(value===null||!value.trim())return;
                await call("PUT",{person:source.person,name:value.trim(),
                  latitude:source.latitude,longitude:source.longitude},"Opholdet er navngivet.");
              });
              const privateOne=document.createElement("button");
              privateOne.type="button";privateOne.className="tf-save";
              privateOne.textContent=source.private?"Gør fælles":"Gør privat";
              privateOne.addEventListener("click",()=>call("PUT",{
                kind:"privacy",person:source.person,private:!source.private,
                latitude:source.latitude,longitude:source.longitude},"Synlighed ændret."));
              const deleteOne=document.createElement("button");
              deleteOne.type="button";deleteOne.className="tf-save tf-danger";
              deleteOne.textContent="Slet ophold";
              deleteOne.addEventListener("click",async()=>{
                if(!window.confirm("Slet kun dette ophold for "+source.person_name+"?"))return;
                await call("DELETE",{person:source.person,
                  latitude:source.latitude,longitude:source.longitude},"Opholdet er slettet.");
              });
              rowActions.append(renameOne,privateOne,deleteOne);
              row.append(label,rowActions);distinct.appendChild(row);
            }
            groupedDetails=distinct;
          }
          }
          card.append(heading,info,actions);
          if(groupedDetails)card.appendChild(groupedDetails);
          adminList.appendChild(card);
        }
        if(!adminList.children.length)adminList.textContent="Ingen registrerede destinationer endnu.";
      }
    };
    position.addEventListener("click",async()=>{
      position.disabled=true;
      try{
        const status=await this.hassInstance.callApi("GET","tiny_family/status");
        const own=(status.people||[]).find(item=>item.person===status.viewer_person);
        if(!own || own.stale || own.gps_health!=="fresh" ||
           !Number.isFinite(own.latitude)||!Number.isFinite(own.longitude)){
          this.message("Ingen frisk GPS-position fra din valgte telefon.",true);return;
        }
        choose(own.latitude,own.longitude);
      }catch(error){this.message("Kunne ikke hente din GPS-position.",true);}
      finally{position.disabled=false;}
    });
    form.addEventListener("submit",async event=>{
      event.preventDefault();
      const latitude=Number(lat.value),longitude=Number(lon.value);
      if(!lat.value.trim()||!lon.value.trim()||
         !Number.isFinite(latitude)||!Number.isFinite(longitude)||
         latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180){
        this.message("Vælg først stedet på kortet eller indtast gyldige koordinater.",true);
        return;
      }
      submit.disabled=true;
      if(await call("POST",{kind:"shared",name:name.value.trim(),
           latitude,longitude},"Fælles sted er oprettet for hele familien.")){
        name.value="";lat.value="";lon.value="";
        chosen=null;create.open=false;
        this.clearDraft("places-create");
      }
      submit.disabled=false;
    });
    try{
      await load();
      if(["shared","mine","proposals","zones"].includes(savedPlaceView))
        selectPlaceView(savedPlaceView);
    }
    catch(error){this.message("Steder kunne ikke indlæses: "+this.errorText(error),true);}
  }

  async routes(root) {
    const title=document.createElement("h2");title.textContent="Familieruter – seneste 24 timer";
    root.appendChild(title);
    const info=document.createElement("p");info.className="tf-message";
    info.textContent="Kun delbare GPS-spor vises. Historiske privatmarkerede spor beskyttes fortsat. Kortfliser kan hentes fra OpenStreetMap.";
    root.appendChild(info);
    const tools=document.createElement("div");tools.className="tf-fields";
    const people=document.createElement("select");
    people.setAttribute("aria-label","Vis ruter for person");
    const everyone=document.createElement("option");
    everyone.value="";everyone.textContent="Alle tilgængelige personer";people.appendChild(everyone);
    const hours=document.createElement("select");
    hours.setAttribute("aria-label","Tidsrum");
    for(const n of [1,6,12,24]){
      const option=document.createElement("option");
      option.value=String(n);option.textContent="Seneste "+n+" timer";
      hours.appendChild(option);
    }
    hours.value="24";
    tools.append(people,hours);root.appendChild(tools);
    const mapNode=document.createElement("div");
    mapNode.className="tf-map";mapNode.style.marginTop="12px";
    root.appendChild(mapNode);
    const report=document.createElement("p");
    report.className="tf-message";root.appendChild(report);
    const refresh=document.createElement("button");
    refresh.type="button";refresh.className="tf-save";
    refresh.textContent="Opdater ruter";root.appendChild(refresh);
    let routeData=null, names={},health={};
    const draw=async()=>{
      try{
        if(!routeData){
          const [routes,status]=await Promise.all([
            this.hassInstance.callApi("GET","tiny_family/routes"),
            this.hassInstance.callApi("GET","tiny_family/status")
          ]);
          routeData=routes;
          names=Object.fromEntries((status.people||[]).map(p=>[p.person,p.name]));
          health=Object.fromEntries((status.people||[]).map(p=>[p.person,p]));
          const wasSelected=people.value;
          people.replaceChildren(everyone);
          for(const row of routes.paths||[]){
            const option=document.createElement("option");
            option.value=row.person;option.textContent=names[row.person]||row.person;
            people.appendChild(option);
          }
          const wanted=this._routeFilterPerson||wasSelected;
          if([...people.options].some(p=>p.value===wanted))people.value=wanted;
          this._routeFilterPerson=null;
        }
        const L=await this.leaflet();
        if(this.active!=="routes")return;
        if(this._familyMap){this._familyMap.remove();this._familyMap=null;}
        const map=this.createLeafletMap(mapNode);
        await this.addBaseMap(map,mapNode);
        const bounds=[],now=Date.now()/1000,since=now-Number(hours.value)*3600;
        let count=0;
        for(const row of routeData.paths||[]){
          if(people.value && row.person!==people.value)continue;
          for(const segment of row.segments||[]){
            const pts=segment.filter(p=>Array.isArray(p)&&p.length===3 &&
                            Number.isFinite(p[0])&&Number.isFinite(p[1])&&
                            Number.isFinite(p[2])&&p[2]>=since);
            if(!pts.length)continue;
            if(pts.length>1){
              L.polyline(pts.map(p=>[p[0],p[1]]),{
                color:"#389ab8",weight:4,opacity:0.88
              }).addTo(map);
            }
            const routeTip=document.createElement("span");
            routeTip.textContent=names[row.person]||row.person;
            L.circleMarker([pts[pts.length-1][0],pts[pts.length-1][1]],{
              radius:5,color:"#157c9b"
            }).bindTooltip(routeTip).addTo(map);
            bounds.push(...pts.map(p=>[p[0],p[1]]));
            count+=pts.length;
          }
        }
        if(bounds.length)map.fitBounds(bounds,{padding:[35,35],maxZoom:15});
        else map.setView([this.hassInstance.config.latitude||0,
                          this.hassInstance.config.longitude||0],5);
        const selected=(routeData.paths||[]).filter(p=>!people.value||p.person===people.value);
        const gpsStatus=selected.map(p=>{
          const state=health[p.person]||{};
          const label=state.stale?"forældet":state.gps_health==="fresh"?"frisk":"ukendt";
          const age=state.updated_at?Math.max(0,Math.round((Date.now()-Date.parse(state.updated_at))/60000)):null;
          return (names[p.person]||p.person)+": "+label+
            (Number.isFinite(age)?" ("+age+" min)":"");
        });
        const gaps=selected.reduce((total,p)=>
          total+Math.max(0,(p.segments||[]).length-1),0);
        report.textContent=(count?"Viser "+count+" GPS-punkter.":"Ingen delbare spor i det valgte tidsrum. Kontroller GPS og tidsrummet.")+
          (gaps?" · "+gaps+" adskilte rutestykker/GPS-pauser.":"")+
          (gpsStatus.length?" · GPS-status: "+gpsStatus.join("; ")+".":"")+
          " Spor er historiske, ikke en garanti for aktuel position.";
        setTimeout(()=>{if(this._familyMap===map)map.invalidateSize();},120);
      }catch(error){report.textContent="Ruter kunne ikke indlæses: "+error.message;}
    };
    people.addEventListener("change",draw);
    hours.addEventListener("change",draw);
    refresh.addEventListener("click",()=>{
      routeData=null;draw();
    });
    await draw();
  }

  async family(root) {
    const heading=document.createElement("h2");heading.textContent="Familiekort";root.appendChild(heading);
    const help=document.createElement("p");help.className="tf-message";
    help.textContent="Her ser du familiens positioner, fælles steder og ruter. Forældede GPS-positioner markeres særskilt.";
    root.appendChild(help);
    const routesLabel=document.createElement("label");
    routesLabel.className="tf-message";
    const routesToggle=document.createElement("input");
    routesToggle.type="checkbox";routesToggle.checked=false;
    routesLabel.append(routesToggle,
      document.createTextNode(" Vis delte ruter fra de seneste 24 timer"));
    root.appendChild(routesLabel);
    const routeFilters=document.createElement("div");
    routeFilters.className="tf-fields";
    const hoursLabel=document.createElement("label");
    hoursLabel.textContent="Rutehistorik";
    const routeHours=document.createElement("select");
    for(const hours of [1,6,12,24]){
      const option=document.createElement("option");
      option.value=String(hours);option.textContent="Sidste "+hours+" timer";
      routeHours.appendChild(option);
    }
    routeHours.value="24";hoursLabel.appendChild(routeHours);
    const personRouteLabel=document.createElement("label");
    personRouteLabel.textContent="Person på rute";
    const routePerson=document.createElement("select");
    const allRoutes=document.createElement("option");
    allRoutes.value="";allRoutes.textContent="Alle delte personer";
    routePerson.appendChild(allRoutes);
    personRouteLabel.appendChild(routePerson);
    routeFilters.append(hoursLabel,personRouteLabel);
    root.appendChild(routeFilters);
    const zonesLabel=document.createElement("label");
    zonesLabel.className="tf-message";
    const zonesToggle=document.createElement("input");
    zonesToggle.type="checkbox";zonesToggle.checked=false;
    zonesLabel.append(zonesToggle,document.createTextNode(" Vis geografiske zoner og deres radius"));
    root.appendChild(zonesLabel);
    const polygonLabel=document.createElement("label");
    polygonLabel.className="tf-message";
    const polygonsToggle=document.createElement("input");
    polygonsToggle.type="checkbox";polygonsToggle.checked=false;
    polygonLabel.append(polygonsToggle,
      document.createTextNode(" Vis Tiny Family-polygonområder"));
    root.appendChild(polygonLabel);
    const zoneInfo=document.createElement("p");
    zoneInfo.className="tf-message";
    zoneInfo.textContent="Zoner vises som geografiske cirkler. Home Assistant-områder (rum/enheder) har ingen kortgrænser.";
    root.appendChild(zoneInfo);
    let selectedZoneCenter=null;
    const zoneEditor=document.createElement("form");
    zoneEditor.className="tf-person";
    zoneEditor.style.display="none";
    const zoneHeading=document.createElement("strong");
    zoneHeading.textContent="Administrator: opret geografisk zone";
    const zoneExplanation=document.createElement("p");zoneExplanation.className="tf-message";
    zoneExplanation.textContent="En zone er ikke et automatisk lært ophold. Det er et fast område omkring fx hjem, skole eller arbejde. Tiny Family bruger zonens radius til at registrere ankomst og afgang og til zonealarmer. Kun administrator kan oprette, ændre og slette zoner.";
    const zoneName=document.createElement("input");
    zoneName.required=true;zoneName.maxLength=80;
    zoneName.placeholder="Zonenavn (fx Skole eller Træning)";
    zoneName.setAttribute("aria-label","Zonenavn");
    const zoneRadius=document.createElement("input");
    zoneRadius.type="number";zoneRadius.min="25";zoneRadius.max="5000";
    zoneRadius.required=true;zoneRadius.value="100";
    zoneRadius.setAttribute("aria-label","Zoneradius i meter");
    const zoneLocation=document.createElement("span");
    zoneLocation.textContent="Tryk på kortet for at vælge zonens centrum. Radius angives i meter.";
    const zoneSave=document.createElement("button");
    zoneSave.type="submit";zoneSave.className="tf-save";
    zoneSave.textContent="Gem som Home Assistant-zone";
    const storedLabel=document.createElement("label");
    storedLabel.textContent="Eksisterende, redigerbar zone";
    const storedZones=document.createElement("select");
    const emptyZone=document.createElement("option");
    emptyZone.value="";emptyZone.textContent="Opret ny zone";
    storedZones.appendChild(emptyZone);
    storedLabel.appendChild(storedZones);
    const deleteZone=document.createElement("button");
    deleteZone.type="button";deleteZone.className="tf-save";
    deleteZone.style.background="var(--error-color,#ad3131)";
    deleteZone.textContent="Slet valgt zone";
    deleteZone.disabled=true;
    storedZones.addEventListener("change",()=>{
      const selected=[...storedZones.options].find(o=>o.value===storedZones.value);
      deleteZone.disabled=!storedZones.value;
      zoneSave.textContent=storedZones.value?"Gem zoneændringer":"Opret ny zone";
      if(!selected || !storedZones.value){
        selectedZoneCenter=null;
        zoneLocation.textContent="Tryk på kortet for at vælge zonens centrum.";
        return;
      }
      const zone=JSON.parse(selected.dataset.zone);
      selectedZoneCenter={lat:Number(zone.latitude),lon:Number(zone.longitude)};
      zoneName.value=zone.name;zoneRadius.value=String(zone.radius);
      zoneLocation.textContent="Kortcentrum valgt fra "+zone.name+
        ". Tryk på kortet for at flytte zonen.";
    });
    zoneEditor.append(zoneHeading,zoneExplanation,storedLabel,zoneName,zoneRadius,zoneLocation,zoneSave,deleteZone);
    root.appendChild(zoneEditor);
    zoneEditor.addEventListener("submit",async event=>{
      event.preventDefault();
      if(!selectedZoneCenter){this.message("Vælg først centrum ved at trykke på kortet.",true);return;}
      zoneSave.disabled=true;
      try{
        await this.hassInstance.callApi(
          storedZones.value?"PUT":"POST","tiny_family/zones",{
            ...(storedZones.value?{zone_id:storedZones.value}:{}),
            name:zoneName.value.trim(),
            latitude:selectedZoneCenter.lat,longitude:selectedZoneCenter.lon,
            radius:Number(zoneRadius.value)
          }
        );
        zoneName.value="";storedZones.value="";
        deleteZone.disabled=true;zoneSave.textContent="Opret ny zone";
        selectedZoneCenter=null;
        zoneLocation.textContent="Zone gemt. Vælg et nyt centrum på kortet.";
        this.message("Zonen er oprettet i Home Assistant.");
        await draw();
      }catch(error){this.message("Kunne ikke oprette zone: "+error.message,true);}
      finally{zoneSave.disabled=false;}
    });
    deleteZone.addEventListener("click",async()=>{
      if(!storedZones.value)return;
      const zoneNameToDelete=zoneName.value;
      if(!window.confirm("Slet zonen '"+zoneNameToDelete+"' fra Home Assistant? Dette kan ikke fortrydes."))return;
      deleteZone.disabled=true;
      try{
        await this.hassInstance.callApi("DELETE","tiny_family/zones",{
          zone_id:storedZones.value,confirm:true
        });
        storedZones.value="";zoneName.value="";
        selectedZoneCenter=null;zoneSave.textContent="Opret ny zone";
        this.message("Zonen er slettet i Home Assistant.");
        await draw();
      }catch(error){
        this.message("Kunne ikke slette zonen: "+error.message,true);
      }finally{deleteZone.disabled=!storedZones.value;}
    });
    // Polygon geofences are managed independently of circular HA zones.
    let drawingPolygon=false;
    let polygonPoints=[];
    const polygonEditor=document.createElement("form");
    polygonEditor.className="tf-person";
    polygonEditor.style.display="none";
    const polygonHeading=document.createElement("strong");
    polygonHeading.textContent="Administrator: polygonområder (3–32 hjørner)";
    const polygonChoice=document.createElement("select");
    const polygonNew=document.createElement("option");
    polygonNew.value="";polygonNew.textContent="Opret nyt polygonområde";
    polygonChoice.appendChild(polygonNew);
    const polygonName=document.createElement("input");
    polygonName.required=true;polygonName.maxLength=80;
    polygonName.placeholder="Navn på området";
    const polygonHint=document.createElement("span");
    polygonHint.className="tf-message";
    polygonHint.textContent="Vælg Tegn, og tryk mindst tre steder på kortet.";
    const polygonDraw=document.createElement("button");
    polygonDraw.type="button";polygonDraw.className="tf-save";
    polygonDraw.textContent="Start polygontegning";
    polygonDraw.addEventListener("click",()=>{
      drawingPolygon=!drawingPolygon;
      if(drawingPolygon)polygonPoints=[];
      polygonDraw.textContent=drawingPolygon?"Afslut tegning":"Start polygontegning";
      polygonHint.textContent=drawingPolygon
        ?"Tryk på kortet for hvert hjørne. Maks. 32 hjørner."
        :"Området har "+polygonPoints.length+" hjørner.";
    });
    const polygonSave=document.createElement("button");
    polygonSave.type="submit";polygonSave.className="tf-save";
    polygonSave.textContent="Gem polygon";
    const polygonDelete=document.createElement("button");
    polygonDelete.type="button";polygonDelete.className="tf-save";
    polygonDelete.textContent="Slet polygon";
    polygonDelete.style.background="var(--error-color,#ad3131)";
    polygonDelete.disabled=true;
    polygonChoice.addEventListener("change",()=>{
      const selected=polygonChoice.selectedOptions[0];
      polygonDelete.disabled=!polygonChoice.value;
      const item=selected?.dataset?.item ? JSON.parse(selected.dataset.item) : null;
      polygonName.value=item?.name || "";
      polygonPoints=item?.points ? item.points.map(p=>[p[0],p[1]]) : [];
      drawingPolygon=false;polygonDraw.textContent="Start polygontegning";
      polygonHint.textContent=item
        ?"Eksisterende polygon med "+polygonPoints.length+" hjørner. Tegn igen for at ændre formen."
        :"Vælg Tegn og sæt mindst tre hjørner på kortet.";
    });
    polygonEditor.append(
      polygonHeading,polygonChoice,polygonName,polygonHint,
      polygonDraw,polygonSave,polygonDelete
    );
    root.appendChild(polygonEditor);
    polygonEditor.addEventListener("submit",async event=>{
      event.preventDefault();
      if(polygonPoints.length<3){
        this.message("Tegn mindst tre polygonhjørner på kortet.",true);return;
      }
      polygonSave.disabled=true;
      try{
        await this.hassInstance.callApi(
          polygonChoice.value?"PUT":"POST","tiny_family/geofences",{
            ...(polygonChoice.value?{id:polygonChoice.value}:{}),
            name:polygonName.value.trim(),points:polygonPoints
          });
        this.message("Polygonområdet er gemt i Tiny Family.");
        polygonName.value="";polygonPoints=[];drawingPolygon=false;
        polygonChoice.value="";polygonDraw.textContent="Start polygontegning";
        await draw();
      }catch(error){this.message("Polygon blev ikke gemt: "+error.message,true);}
      finally{polygonSave.disabled=false;}
    });
    polygonDelete.addEventListener("click",async()=>{
      if(!polygonChoice.value)return;
      if(!window.confirm("Slet polygonområdet '"+polygonName.value+"' permanent?"))return;
      polygonDelete.disabled=true;
      try{
        await this.hassInstance.callApi("DELETE","tiny_family/geofences",{
          id:polygonChoice.value,confirm:true
        });
        polygonChoice.value="";polygonName.value="";polygonPoints=[];
        this.message("Polygonområdet er slettet.");
        await draw();
      }catch(error){this.message("Polygon kunne ikke slettes: "+error.message,true);}
      finally{polygonDelete.disabled=!polygonChoice.value;}
    });
    const toolsPanel=document.createElement("details");
    toolsPanel.className="tf-map-tools";
    const toolsTitle=document.createElement("summary");
    toolsTitle.textContent="Kortlag og avancerede kortværktøjer";
    toolsPanel.appendChild(toolsTitle);
    for(const element of [help,routesLabel,routeFilters,zonesLabel,polygonLabel,
                          zoneInfo,zoneEditor,polygonEditor]){
      toolsPanel.appendChild(element);
    }
    root.appendChild(toolsPanel);
    const mapElement=document.createElement("div");
    mapElement.className="tf-map";mapElement.style.marginBottom="15px";
    root.insertBefore(mapElement,toolsPanel);
    const list=document.createElement("div");list.className="tf-fields";root.appendChild(list);
    const refresh=document.createElement("button");refresh.className="tf-save";
    refresh.textContent="Opdater personer";
    root.appendChild(refresh);
    // Person, date and the full 24-hour scrubber stay ON the map on mobile.
    const dock=document.createElement("section");
    dock.className="tf-timeline-dock";
    dock.setAttribute("aria-label","Familiens tidslinje");
    dock.innerHTML=`
      <div class="tf-dock-main">
        <button type="button" data-mode="live" aria-pressed="true">● Nu</button>
        <button type="button" data-mode="history" aria-pressed="false">◷ Tidslinje</button>
        <select data-role="timeline-person" aria-label="Vælg person"></select>
      </div>
      <div class="tf-history-controls" hidden>
        <div class="tf-day-nav">
          <button type="button" data-role="prev-day" aria-label="Forrige dato">‹</button>
          <input data-role="timeline-date" type="date" aria-label="Dato for historik">
          <button type="button" data-role="next-day" aria-label="Næste dato">›</button>
        </div>
        <div class="tf-scrub-row">
          <button type="button" data-role="timeline-play" aria-label="Afspil dagsruten">▶</button>
          <input type="range" data-role="timeline-minute" min="0" max="1439"
            step="1" value="1439" aria-label="Gå gennem dagens GPS-tidslinje">
          <select data-role="timeline-speed" aria-label="Afspilningshastighed">
            <option value="1">1× realtid</option>
            <option value="5">5×</option>
            <option value="20">20×</option>
            <option value="60">60×</option>
            <option value="300">300×</option>
          </select>
        </div>
        <div class="tf-history-info"><strong data-role="timeline-time">—</strong>
          <span data-role="timeline-stats">Vælg dato og person</span></div>
        <label class="tf-road-matching" data-role="road-matching-label" hidden>
          <input type="checkbox" data-role="road-matching-toggle">
          Følg vejene (styres af administrator)
        </label>
        <div class="tf-road-match-status" data-role="road-matching-status" aria-live="polite"></div>
        <div class="tf-event-strip" data-role="timeline-events" hidden></div>
        <div class="tf-timeline-warning" data-role="timeline-summary"></div>
      </div>`;
    root.appendChild(dock);
    const liveTab=dock.querySelector('[data-mode="live"]');
    const historyTab=dock.querySelector('[data-mode="history"]');
    const historyControls=dock.querySelector(".tf-history-controls");
    const dockPerson=dock.querySelector('[data-role="timeline-person"]');
    const dockDate=dock.querySelector('[data-role="timeline-date"]');
    const minuteSlider=dock.querySelector('[data-role="timeline-minute"]');
    const playButton=dock.querySelector('[data-role="timeline-play"]');
    const playbackSpeed=dock.querySelector('[data-role="timeline-speed"]');
    let playbackTime=null,playbackTickAt=null;
    const stopPlayback=(resetPosition=true)=>{
      if(this._timelinePlaybackTimer){
        clearInterval(this._timelinePlaybackTimer);
        this._timelinePlaybackTimer=null;
      }
      if(resetPosition)playbackTime=null;
      playbackTickAt=null;
      playButton.textContent="▶";
      playButton.setAttribute("aria-label","Afspil dagsruten");
    };
    const timeLabel=dock.querySelector('[data-role="timeline-time"]');
    const statsLabel=dock.querySelector('[data-role="timeline-stats"]');
    const summaryLabel=dock.querySelector('[data-role="timeline-summary"]');
    const roadMatchLabel=dock.querySelector('[data-role="road-matching-label"]');
    const roadMatchToggle=dock.querySelector('[data-role="road-matching-toggle"]');
    const roadMatchStatus=dock.querySelector('[data-role="road-matching-status"]');
    roadMatchLabel.hidden=!this.settings?.map_matching_enabled;
    roadMatchToggle.checked=Boolean(this.settings?.map_matching_enabled);
    roadMatchToggle.disabled=true;
    roadMatchLabel.title=(this.settings?.map_matching_backend==="osrm")
      ?"OSRM får GPS-koordinater og tidspunkter ved aktivering."
      :"Indbygget motor: kun et vejområdes koordinatgrænser deles med OpenStreetMap ved aktivering.";
    const eventStrip=dock.querySelector('[data-role="timeline-events"]');
    const localDate=d=>new Intl.DateTimeFormat("sv-SE",{
      timeZone:this.hassInstance.config.time_zone||undefined,
      year:"numeric",month:"2-digit",day:"2-digit"
    }).format(d);
    const resetToToday=()=>{
      dockDate.value=localDate(new Date());
      dockDate.max=dockDate.value;
    };
    resetToToday();
    dockDate.min=localDate(new Date(Date.now()-
      ((this.settings?.timeline_retention_days??365)-1)*86400000));
    let timelineMode=false,timelineData=null,timelineMarker=null,activeMap=null;
    let cursorManuallyMoved=false;
    let eventFocus=null;
    let timelineRequest=0,timelineRevision=0;
    let previousCenteredFix=null;
    let drawing=false,pendingRedraw=false;
    let previousSignature="";
    const validMapPoint=loc=>Array.isArray(loc)&&loc.length===2&&
      Number.isFinite(loc[0])&&Number.isFinite(loc[1])&&
      Math.abs(loc[0])<=85.05&&Math.abs(loc[1])<=180;
    const chooseMode=mode=>{
      timelineMode=mode==="history";
      liveTab.setAttribute("aria-pressed",String(!timelineMode));
      historyTab.setAttribute("aria-pressed",String(timelineMode));
      historyControls.hidden=!timelineMode;
    };
    // Locate a real fix on its matched road. Interpolate *along the road*
    // between two observed fixes, never across a GPS/privacy gap.
    const projectedRoadPoint=(coordinates,fix)=>{
      if(!Array.isArray(coordinates)||coordinates.length<2)return null;
      const scaleX=111320*Math.max(.05,Math.cos(fix.lat*Math.PI/180));
      let traveled=0,best=null;
      for(let i=1;i<coordinates.length;i++){
        const first=coordinates[i-1],last=coordinates[i];
        if(!Array.isArray(first)||!Array.isArray(last))continue;
        const dx=(last[1]-first[1])*scaleX;
        const dy=(last[0]-first[0])*111320;
        const length=Math.hypot(dx,dy);
        if(length<.001)continue;
        const px=(fix.lon-first[1])*scaleX,py=(fix.lat-first[0])*111320;
        const fraction=Math.max(0,Math.min(1,(px*dx+py*dy)/(length*length)));
        const miss=Math.hypot(px-fraction*dx,py-fraction*dy);
        if(!best||miss<best.miss){
          best={miss,along:traveled+fraction*length};
        }
        traveled+=length;
      }
      return best;
    };
    const positionOnRoad=(coordinates,distance)=>{
      let traveled=0;
      for(let i=1;i<coordinates.length;i++){
        const a=coordinates[i-1],b=coordinates[i];
        const size=Math.hypot((b[0]-a[0])*111320,
          (b[1]-a[1])*111320*Math.max(.05,Math.cos(a[0]*Math.PI/180)));
        if(size<.001)continue;
        if(traveled+size>=distance){
          const fraction=Math.max(0,Math.min(1,(distance-traveled)/size));
          return [a[0]+(b[0]-a[0])*fraction,a[1]+(b[1]-a[1])*fraction];
        }
        traveled+=size;
      }
      return coordinates[coordinates.length-1];
    };
    const playbackLocation=(fix,next,t)=>{
      const matched=roadMatchToggle.checked?
        (timelineData?.matched_segments||[]):[];
      for(const road of matched){
        if(!Array.isArray(road.coordinates)||road.coordinates.length<2 ||
           road.start_t>fix.t||road.end_t<fix.t||
           (next && road.end_t<next.t))continue;
        const start=projectedRoadPoint(road.coordinates,fix);
        const end=next?projectedRoadPoint(road.coordinates,next):start;
        if(!start||!end||start.miss>100||end.miss>100||
           end.along+5<start.along)continue;
        const progress=next?Math.max(0,Math.min(1,
          (t-fix.t)/(next.t-fix.t))):0;
        return positionOnRoad(road.coordinates,
          start.along+progress*Math.max(0,end.along-start.along));
      }
      if(next && next.t>fix.t && next.t-fix.t<=90){
        const progress=Math.max(0,Math.min(1,(t-fix.t)/(next.t-fix.t)));
        return [fix.lat+(next.lat-fix.lat)*progress,
          fix.lon+(next.lon-fix.lon)*progress];
      }
      return [fix.lat,fix.lon];
    };
    const moveTimelineMarker=loc=>{
      if(!activeMap||!validMapPoint(loc))return;
      // Resolve the camera in one operation. Repeated panTo() + panBy()
      // during 200 ms playback ticks can leave a transient invalid tile
      // viewport when Home Assistant resizes the map beneath the timeline.
      const currentZoom=activeMap.getZoom();
      const zoom=Number.isFinite(currentZoom)?
        Math.max(2,Math.min(19,previousCenteredFix===null?
          Math.max(15,currentZoom):currentZoom)):15;
      let center=loc;
      if(window.matchMedia?.("(max-width: 600px)").matches){
        const mapRect=mapElement.getBoundingClientRect();
        const dockRect=dock.getBoundingClientRect();
        if([mapRect.top,mapRect.bottom,mapRect.height,dockRect.top]
          .every(Number.isFinite)&&mapRect.height>0&&mapRect.height<10000){
          const hiddenHeight=Math.max(0,mapRect.bottom-
            Math.max(mapRect.top,Math.min(mapRect.bottom,dockRect.top-8)));
          const offset=Math.min(mapRect.height*.4,hiddenHeight/2);
          if(offset>1){
            const pixel=activeMap.project(loc,zoom);
            if(Number.isFinite(pixel.x)&&Number.isFinite(pixel.y)){
              const shifted=activeMap.unproject([pixel.x,pixel.y+offset],zoom);
              const candidate=[shifted.lat,shifted.lng];
              if(validMapPoint(candidate))center=candidate;
            }
          }
        }
      }
      if(!timelineMarker){
        const selected=[...dockPerson.options]
          .find(option=>option.value===dockPerson.value);
        const initials=(selected?.textContent||"?").trim()
          .split(/\s+/).slice(0,2).map(word=>word[0]||"")
          .join("").toUpperCase();
        const pin=document.createElement("span");
        pin.className="tf-person-pin";
        pin.style.borderColor="#2ce2eb";
        pin.textContent=initials;
        timelineMarker=window.L.marker(loc,{
          icon:window.L.divIcon({
            className:"tf-person-icon",html:pin.outerHTML,
            iconSize:[48,48],iconAnchor:[24,24]
          }),
          zIndexOffset:1000
        }).addTo(activeMap);
      }else{
        timelineMarker.setLatLng(loc);
      }
      // The map's centre is shifted south by the covered half-height so the
      // actual person marker stays in the visible portion above the controls.
      if(previousCenteredFix!==loc.join(","))
        activeMap.setView(center,zoom,{animate:false});
      previousCenteredFix=loc.join(",");
    };
    const focusEventObservation=(event,segments)=>{
      // Prefer a *measured* point within the selected event. Picking the
      // event's minute start is unreliable because the first fix may be
      // several minutes later, or missing altogether.
      const middle=(event.started_at+event.ended_at)/2;
      let observed=null;
      for(const segment of segments||[]){
        for(const fix of segment||[]){
          if(!Number.isFinite(fix.t)||!Number.isFinite(fix.lat)||
             !Number.isFinite(fix.lon)||fix.t<event.started_at||
             fix.t>event.ended_at)continue;
          if(!observed||Math.abs(fix.t-middle)<Math.abs(observed.t-middle))
            observed=fix;
        }
      }
      if(observed)return {point:[observed.lat,observed.lon],
        time:observed.t,source:"gps"};
      // Activity events from 0.8.7 can carry measured start/end anchors,
      // independently of the sampled route. Never fabricate an old route.
      for(const prefix of ["start","end"]){
        const lat=event[prefix+"_lat"],lon=event[prefix+"_lon"];
        if(Number.isFinite(lat)&&Number.isFinite(lon)&&
           lat>=-90&&lat<=90&&lon>=-180&&lon<=180){
          return {point:[lat,lon],time:prefix==="start"?
            event.started_at:event.ended_at,source:"anchor",prefix};
        }
      }
      return null;
    };
    const inferredLocation=(road,t)=>{
      const coords=road.coordinates;
      let meters=0;
      for(let i=1;i<coords.length;i++){
        meters+=Math.hypot((coords[i][0]-coords[i-1][0])*111320,
          (coords[i][1]-coords[i-1][1])*111320*Math.max(.05,
            Math.cos(coords[i-1][0]*Math.PI/180)));
      }
      const portion=Math.max(0,Math.min(1,
        (t-road.start_t)/(road.end_t-road.start_t)));
      return positionOnRoad(coords,meters*portion);
    };
    const updateCursor=(selectedTime=null)=>{
      if(!timelineMode||!timelineData)return;
      // Select the end of each displayed minute so real fixes with seconds
      // (e.g. 12:23:50) remain visible at 12:23 on the slider.
      const desired=Number.isFinite(selectedTime)?
        Math.max(timelineData.start,Math.min(timelineData.end-1,selectedTime)):
        eventFocus?Math.max(timelineData.start,Math.min(timelineData.end-1,
          eventFocus.time)):
          Math.min(timelineData.end-1,
            timelineData.start+(Number(minuteSlider.value)+1)*60-1);
      const prettyTime=ts=>new Date(ts*1000).toLocaleTimeString("da-DK",{
        hour:"2-digit",minute:"2-digit",second:"2-digit",
        timeZone:timelineData.timezone||undefined
      });
      timeLabel.textContent=prettyTime(desired);
      if(eventFocus?.source==="anchor"){
        statsLabel.textContent=(eventFocus.kind==="stay"?"Ophold":"Tur")+
          " · Registreret "+(eventFocus.prefix==="start"?"start":"slut")+
          "position · Ingen GPS-rute for denne begivenhed";
        moveTimelineMarker(eventFocus.point);
        return;
      }
      let closest=null,next=null;
      for(const segment of timelineData.segments||[]){
        for(let i=0;i<segment.length;i++){
          const fix=segment[i];
          if(fix.t<=desired && (!closest || fix.t>closest.t)){
            closest=fix;next=segment[i+1]||null;
          }
        }
      }
      if(!closest || desired-closest.t>300){
        const estimated=roadMatchToggle.checked?
          (timelineData.inferred_segments||[]).find(road=>
            road.start_t<=desired && road.end_t>=desired &&
            road.end_t>road.start_t && Array.isArray(road.coordinates) &&
            road.coordinates.length>1):null;
        if(estimated){
          const source=estimated.basis==="previous_road_history"
            ?"tidligere rute":"vejnet";
          statsLabel.textContent="Anslået position ("+source+") · Fart ukendt · GPS-afbrud";
          moveTimelineMarker(inferredLocation(estimated,desired));
          return;
        }
        const event=(timelineData.events||[]).find(item=>
          item.started_at<=desired && item.ended_at>=desired);
        statsLabel.textContent=event
          ?(event.kind==="stay"?"Ophold":"Tur")+" · "+
            (event.label||event.duration_min+" min")
          :"Ingen GPS-måling på dette tidspunkt";
        if(timelineMarker && activeMap){activeMap.removeLayer(timelineMarker);timelineMarker=null;}
        previousCenteredFix=null;
        return;
      }
      const metrics=[];
      let speed=closest.speed;
      if(next && Number.isFinite(next.speed)&&Number.isFinite(speed) &&
         next.t>closest.t && desired<next.t){
        const ratio=(desired-closest.t)/(next.t-closest.t);
        speed=speed+(next.speed-speed)*ratio;
      }
      metrics.push(Number.isFinite(speed)?"Fart "+Math.round(speed)+" km/t":"Fart ukendt");
      if(Number.isFinite(closest.battery))metrics.push(Math.round(closest.battery)+" % batteri");
      if(closest.movement==="stationary" && Number.isFinite(closest.stay_min) &&
          closest.stay_min>=0)metrics.push("Ophold "+closest.stay_min+" min");
      statsLabel.textContent=prettyTime(closest.t)+" · "+(metrics.join(" · ")||"Position målt");
      if(activeMap){
        const loc=playbackLocation(closest,
          next && next.t>closest.t && next.t-closest.t<=300?next:null,desired);
        moveTimelineMarker(loc);
      }
    };
    const loadRoadOverlay=async(person,date,requestId)=>{
      try{
        const overlay=await this.hassInstance.callApi("GET",
          "tiny_family/timeline?person="+encodeURIComponent(person)+
          "&date="+encodeURIComponent(date)+"&phase=matching");
        if(requestId!==timelineRequest||this.active!=="live"||
           !timelineMode||dockPerson.value!==person||dockDate.value!==date)return;
        if(!timelineData)return;
        timelineData.matched_segments=overlay.matched_segments||[];
        timelineData.inferred_segments=overlay.inferred_segments||[];
        timelineData.matching_status=overlay.matching_status;
        const verified=timelineData.matched_segments.length;
        const estimated=timelineData.inferred_segments.length;
        roadMatchStatus.textContent=verified||estimated
          ?(verified?"✓ "+verified+" vejtilpassede stykker":"Ingen sikre vejmatch")+
            (estimated?" · ≈ "+estimated+" anslåede vejstykker (stiplet)":"")
          :overlay.matching_status==="not_enough_points"
            ?"For få sammenhængende GPS-målinger. Ukendte vejstykker vises som GPS-spor."
            :"Kunne ikke fastslå vejen. Rå GPS-målinger bevares.";
        roadMatchStatus.title=estimated
          ?"Stiplede vejstykker er estimater fra tidligere ture eller OpenStreetMap, ikke GPS-målinger."
          :"Turens bekræftede vejmatch og de oprindelige GPS-målinger.";
        timelineRevision++;previousSignature="";
        await draw();
      }catch(error){
        if(requestId!==timelineRequest||this.active!=="live")return;
        roadMatchStatus.textContent="Vejmotoren svarer ikke. GPS-tidslinjen er stadig tilgængelig.";
      }
    };
    const loadTimeline=async()=>{
      stopPlayback();
      eventFocus=null;
      chooseMode("history");
      const person=dockPerson.value||this._viewerPerson;
      if(!person){summaryLabel.textContent="Ingen tilknyttet person.";return;}
      const requestId=++timelineRequest;
      // Never leave the previously selected person's route visible while a
      // different person's day is being fetched. Recenter on the new live
      // location immediately, then recenter on the requested historical fix.
      timelineData=null;timelineRevision++;
      previousCenteredFix=null;previousSignature="";
      void draw();
      timeLabel.textContent="Henter tidslinje…";
      const selectedDate=dockDate.value;
      try{
        const url="tiny_family/timeline?person="+encodeURIComponent(person)+
          "&date="+encodeURIComponent(selectedDate)+"&map_match=0";
        const result=await this.hassInstance.callApi("GET",url);
        if(requestId!==timelineRequest||this.active!=="live")return;
        timelineData=result;
        timelineRevision++;
        roadMatchStatus.textContent=roadMatchToggle.checked
          ?"Beregner vejtilpasning i baggrunden…"
          :"Vejtilpasning er slået fra. Administrator kan aktivere den i Administration.";
        eventStrip.replaceChildren();
        for(const event of (result.events||[]).slice(0,40)){
          const eventButton=document.createElement("button");
          eventButton.type="button";
          const eventTime=new Date(event.started_at*1000).toLocaleTimeString("da-DK",{
            hour:"2-digit",minute:"2-digit",timeZone:result.timezone||undefined
          });
          eventButton.textContent=event.kind==="stay"
            ?"◷ "+eventTime+" · Ophold "+event.duration_min+" min"
            :"↗ "+eventTime+" · Tur "+event.duration_min+" min";
          eventButton.title=event.label||eventButton.textContent;
          eventButton.addEventListener("click",()=>{
            const focus=focusEventObservation(event,timelineData?.segments);
            eventFocus=focus?{...focus,kind:event.kind}:null;
            minuteSlider.value=String(Math.max(0,Math.min(
              Number(minuteSlider.max),
              Math.floor(((focus?.time??event.started_at)-result.start)/60)
            )));
            stopPlayback();
            cursorManuallyMoved=true;
            previousCenteredFix=null;
            if(!focus){
              statsLabel.textContent="Denne historiske begivenhed mangler både GPS-punkter og gemt position.";
              if(timelineMarker&&activeMap){
                activeMap.removeLayer(timelineMarker);timelineMarker=null;
              }
              timeLabel.textContent=eventTime;
              return;
            }
            updateCursor();
          });
          eventStrip.appendChild(eventButton);
        }
        eventStrip.hidden=!eventStrip.children.length;
        minuteSlider.max=String(Math.max(0,Math.floor((result.end-result.start)/60)-1));
        const segments=result.segments||[];
        const lastSegment=segments[segments.length-1]||[];
        const lastFix=lastSegment[lastSegment.length-1];
        cursorManuallyMoved=false;
        minuteSlider.value=String(lastFix?
          Math.min(Number(minuteSlider.max),Math.max(0,
            Math.floor((lastFix.t-result.start)/60))):
          Number(minuteSlider.max));
        const sum=result.summary||{};
        const diagnostic=result.gps_diagnostics||{};
        summaryLabel.textContent=!result.points_count
          ?"Ingen GPS-punkter for denne dato. Ture og ophold kan være gemt særskilt; ingen rute kan rekonstrueres."
          :(result.points_count||0)+" GPS-punkter · "+
          (Number.isFinite(sum.distance_km)?sum.distance_km+" km":"ukendt distance")+
          (diagnostic.speed_health==="zero_despite_movement"?
            " · Fartmålinger mangler (0 trods bevægelse)":
            Number.isFinite(sum.max_speed_kmh)?" · top "+sum.max_speed_kmh+" km/t":"")+
          (sum.stays?" · "+sum.stays+" ophold":"")+
          (result.gaps?" · "+result.gaps+" GPS-afbrud"+
            (diagnostic.gap_causes?
              " ("+diagnostic.gap_causes.time+" lange pauser)":""):"")+
          " · Faktiske målinger";
        summaryLabel.title=diagnostic.speed_health==="zero_despite_movement"
          ?"Telefonen melder 0 km/t trods bevægelse. Kontrollér Companion-hastighedssensor, positionstilladelser og batterisparefunktion."
          :diagnostic.speed_health==="missing"
            ?"Der blev ikke leveret brugbare fartmålinger for denne dag."
            :"Rute og afstand baseret på faktisk registrerede GPS-fixes.";
        previousSignature="";
        await draw();
        if(roadMatchToggle.checked&&this.settings?.map_matching_enabled){
          void loadRoadOverlay(person,selectedDate,requestId);
        }
      }catch(error){
        if(requestId!==timelineRequest)return;
        timelineData=null;
        roadMatchStatus.textContent="";
        eventStrip.replaceChildren();eventStrip.hidden=true;
        summaryLabel.textContent="Kunne ikke hente historik: "+this.errorText(error);
        previousSignature="";
        await draw();
      }
    };
    liveTab.addEventListener("click",()=>{
      stopPlayback();
      eventFocus=null;
      previousCenteredFix=null;
      timelineRequest++;timelineData=null;timelineRevision++;
      chooseMode("live");previousSignature="";draw();
    });
    historyTab.addEventListener("click",loadTimeline);
    dockPerson.addEventListener("change",()=>{
      stopPlayback();
      previousCenteredFix=null;
      resetToToday();
      if(timelineMode)loadTimeline();
      else {previousSignature="";draw();}
    });
    dockDate.addEventListener("change",loadTimeline);
    roadMatchToggle.addEventListener("change",()=>{
      if(roadMatchToggle.checked){
        // Administrator has enabled matching for the selected date.
        loadTimeline();
      }else{
        roadMatchStatus.textContent="";
        previousSignature="";timelineRevision++;draw();
      }
    });
    minuteSlider.addEventListener("input",()=>{
      stopPlayback();
      eventFocus=null;
      cursorManuallyMoved=true;
      updateCursor();
    });
    playButton.addEventListener("click",()=>{
      if(this._timelinePlaybackTimer){stopPlayback(false);return;}
      if(!timelineData || !timelineMode)return;
      eventFocus=null;
      if(playbackTime===null){
        if(!cursorManuallyMoved){
          const first=(timelineData.segments||[]).find(segment=>segment.length)?.[0];
          if(first)minuteSlider.value=String(Math.max(0,Math.floor(
            (first.t-timelineData.start)/60)));
          else minuteSlider.value="0";
        }else if(Number(minuteSlider.value)>=Number(minuteSlider.max)){
          minuteSlider.value="0";
        }
        playbackTime=Math.min(timelineData.end-1,timelineData.start+
          Number(minuteSlider.value)*60);
      }
      cursorManuallyMoved=true;
      // One second of real elapsed time advances one second at 1×. The
      // previous fixed 5 min / 180 ms interval ran at about 1,667×.
      playbackTickAt=performance.now();
      playButton.textContent="Ⅱ";
      playButton.setAttribute("aria-label","Sæt dagsruten på pause");
      this._timelinePlaybackTimer=setInterval(()=>{
        if(this.active!=="live"||!timelineMode){stopPlayback();return;}
        const now=performance.now();
        const elapsed=Math.max(0,(now-playbackTickAt)/1000);
        playbackTickAt=now;
        playbackTime+=elapsed*Number(playbackSpeed.value);
        if(playbackTime>=timelineData.end-1){
          minuteSlider.value=minuteSlider.max;
          updateCursor(timelineData.end-1);
          stopPlayback();return;
        }
        minuteSlider.value=String(Math.min(Number(minuteSlider.max),
          Math.floor((playbackTime-timelineData.start)/60)));
        updateCursor(playbackTime);
      },200);
    });
    const moveDay=direction=>{
      const parts=dockDate.value.split("-").map(Number);
      const next=new Date(Date.UTC(parts[0],parts[1]-1,parts[2]+direction))
        .toISOString().slice(0,10);
      if(next>=dockDate.min && next<=dockDate.max){
        dockDate.value=next;loadTimeline();
      }
    };
    dock.querySelector('[data-role="prev-day"]').addEventListener("click",()=>moveDay(-1));
    dock.querySelector('[data-role="next-day"]').addEventListener("click",()=>moveDay(1));
    const draw=async()=>{
      if(this.active!=="live" || !this.isConnected)return;
      if(drawing){pendingRedraw=true;return;}
      drawing=true;
      refresh.disabled=true;
      try {
        const data=await this.hassInstance.callApi("GET","tiny_family/status");
        if (this.active!=="live") return;
        this._viewerPerson=data.viewer_person;
        const previousDockPerson=dockPerson.value;
        dockPerson.replaceChildren();
        for(const person of data.people || []){
          if(person.ghost && person.person!==data.viewer_person)continue;
          const choice=document.createElement("option");
          choice.value=person.person;
          choice.textContent=person.name;
          dockPerson.appendChild(choice);
        }
        const requested=this._timelineRequestedPerson||previousDockPerson||data.viewer_person;
        if([...dockPerson.options].some(option=>option.value===requested)){
          dockPerson.value=requested;
        }
        const polygonData=await this.hassInstance.callApi("GET","tiny_family/geofences");
        if(this.active!=="live")return;
        const previousRoutePerson=routePerson.value;
        routePerson.replaceChildren(allRoutes);
        for(const person of data.people || []){
          if(person.ghost && person.person!==data.viewer_person)continue;
          const option=document.createElement("option");
          option.value=person.person;option.textContent=person.name;
          routePerson.appendChild(option);
        }
        routePerson.value=[...routePerson.options].some(
          o=>o.value===previousRoutePerson)?previousRoutePerson:"";
        const signature=JSON.stringify({
          people:data.people,zones:data.zones,polygons:polygonData.geofences,
          routes:routesToggle.checked,routeHours:routeHours.value,
          routePerson:routePerson.value,
          zoneVisibility:zonesToggle.checked,
          polygonVisibility:polygonsToggle.checked,
          timelineMode,timelineRevision,
          selectedTimelinePerson:dockPerson.value
        });
        if(signature===previousSignature && this._familyMap)return;
        previousSignature=signature;
        zoneEditor.style.display=data.can_manage_zones?"grid":"none";
        polygonEditor.style.display=polygonData.editable?"grid":"none";
        if(polygonData.editable){
          const oldValue=polygonChoice.value;
          polygonChoice.replaceChildren(polygonNew);
          for(const polygon of polygonData.geofences || []){
            const option=document.createElement("option");
            option.value=polygon.id;option.textContent=polygon.name;
            option.dataset.item=JSON.stringify(polygon);
            polygonChoice.appendChild(option);
          }
          polygonChoice.value=[...polygonChoice.options].some(p=>p.value===oldValue)
            ?oldValue:"";
          polygonDelete.disabled=!polygonChoice.value;
        }
        if(data.can_manage_zones){
          const stored = await this.hassInstance.callApi("GET","tiny_family/zones");
          const previous=storedZones.value;
          storedZones.replaceChildren(emptyZone);
          for(const zone of stored.zones || []){
            const opt=document.createElement("option");
            opt.value=zone.id;opt.textContent=zone.name;
            opt.dataset.zone=JSON.stringify(zone);
            storedZones.appendChild(opt);
          }
          storedZones.value=[...storedZones.options].some(o=>o.value===previous)
            ?previous:"";
          deleteZone.disabled=!storedZones.value;
        }
        list.replaceChildren();
        await this.leaflet();
        if(this._familyMap) {this._familyMap.remove();this._familyMap=null;}
        activeMap=null;timelineMarker=null;previousCenteredFix=null;
        const map=this.createLeafletMap(mapElement);
        activeMap=map;
        if(data.can_manage_zones){
          let draft=null, polygonDraft=null;
          map.on("click",event=>{
            if(drawingPolygon){
              if(polygonPoints.length>=32){
                this.message("Maksimalt 32 polygonhjørner.",true);return;
              }
              polygonPoints.push([event.latlng.lat,event.latlng.lng]);
              polygonHint.textContent=polygonPoints.length+
                " hjørner registreret. Tegn videre eller gem polygonen.";
              if(polygonDraft)polygonDraft.remove();
              if(polygonPoints.length>=3){
                polygonDraft=window.L.polygon(polygonPoints,{
                  color:"#9c56c4",fillOpacity:0.13,weight:2,dashArray:"4 5"
                }).addTo(map);
              }else{
                polygonDraft=window.L.polyline(polygonPoints,{
                  color:"#9c56c4",weight:2,dashArray:"4 5"
                }).addTo(map);
              }
              return;
            }
            selectedZoneCenter={lat:event.latlng.lat,lon:event.latlng.lng};
            zoneLocation.textContent="Valgt centrum: "+
              selectedZoneCenter.lat.toFixed(5)+", "+
              selectedZoneCenter.lon.toFixed(5)+
              " · Radius "+zoneRadius.value+" m";
            if(draft)draft.remove();
            draft=window.L.circle(
              [selectedZoneCenter.lat,selectedZoneCenter.lon],
              {radius:Number(zoneRadius.value)||100,color:"#ff9900",weight:2,
               fillColor:"#ff9900",fillOpacity:0.15}
            ).addTo(map);
          });
        }
        await this.addBaseMap(map,mapElement);
        const bounds=[];
        const zoneBounds=[];
        if(polygonsToggle.checked){
          for(const polygon of polygonData.geofences || []){
            if(!Array.isArray(polygon.points)||polygon.points.length<3)continue;
            const shape=window.L.polygon(polygon.points,{
              color:"#9c56c4",weight:2,fillColor:"#9c56c4",fillOpacity:0.10
            }).addTo(map);
            const polygonTip=document.createElement("span");
            polygonTip.textContent=polygon.name;
            shape.bindTooltip(polygonTip);
            zoneBounds.push(polygon.points[0]);
          }
        }
        // Shared places are an explicitly published collection, not private GPS history.
        const sharedData=await this.hassInstance.callApi("GET","tiny_family/places")
          .catch(()=>({shared_places:[]}));
        for(const place of sharedData.shared_places||[]){
          if(!Number.isFinite(place.latitude)||!Number.isFinite(place.longitude))continue;
          const marker=window.L.circleMarker([place.latitude,place.longitude],{
            radius:7,color:"#ffffff",weight:2,fillColor:"#9c56c4",fillOpacity:1
          }).addTo(map);
          const label=document.createElement("span");
          label.textContent=place.name;
          marker.bindPopup(label);
          zoneBounds.push([place.latitude,place.longitude]);
        }
        if(!timelineMode && routesToggle.checked){
          const routes=await this.hassInstance.callApi("GET","tiny_family/routes");
          if(this.active!=="live")return;
          const since=Date.now()/1000-Number(routeHours.value)*3600;
          for(const person of routes.paths || []){
            if(routePerson.value && person.person!==routePerson.value)continue;
            const color=this.settings.colors?.[person.person] || "#00a8a9";
            for(const segment of person.segments || []){
              const selected=segment.filter(p=>p[2]>=since);
              if(selected.length<2)continue;
              window.L.polyline(selected.map(p=>[p[0],p[1]]),{
                color,weight:4,opacity:0.7
              }).addTo(map);
            }
          }
        }
        if(zonesToggle.checked){
          for(const zone of data.zones || []){
            if(!Number.isFinite(zone.latitude) || !Number.isFinite(zone.longitude) ||
               !Number.isFinite(zone.radius_m) || zone.radius_m <= 0)continue;
            const center=[zone.latitude,zone.longitude];
            const circle=window.L.circle(center,{
              radius:zone.radius_m,color:"#548fe2",weight:2,
              fillColor:"#548fe2",fillOpacity:0.08
            }).addTo(map);
            const label=document.createElement("span");
            label.textContent=zone.name+" · "+Math.round(zone.radius_m)+" m";
            circle.bindTooltip(label);
            zoneBounds.push(center);
          }
        }
        let focusedLivePoint=null;
        for(const person of data.people || []){
          const box=document.createElement("section");box.className="tf-person";
          const head=document.createElement("div");head.className="tf-card-head";
          const title=document.createElement("strong");title.textContent=person.name;
          const liveLabel=document.createElement("span");liveLabel.className="tf-chip";
          liveLabel.textContent=person.ghost?"Tidligere privatmarkering":
            person.stale?"GPS forældet":person.gps_health==="fresh"?"Frisk GPS":"GPS ukendt";
          head.append(title,liveLabel);box.appendChild(head);
          const status=document.createElement("p");
          status.textContent=person.ghost ? "Position beskyttet af tidligere privatindstilling" :
            (person.status || "Ukendt")+" · "+(person.stale?"sidste position":"opdateret")+
            (person.battery_percent!=null?" · "+person.battery_percent+" % batteri":"")+
            (person.charging==="on"?" · oplader":"")+
            (person.activity && person.activity!=="unknown"?" · "+person.activity:"")+
            (person.power_save===true?" · Batterisparer aktiv":"");
          box.appendChild(status);
          if(!person.ghost && person.gps_glitch_recent){
            const jitter=document.createElement("p");jitter.className="tf-message";
            jitter.textContent="GPS-usikkerhed registreret: "+person.gps_glitches+
              " mistænkelige målinger er udeladt for at undgå falsk bevægelse.";
            box.appendChild(jitter);
          }
          if(!person.ghost && person.stale){
            const warning=document.createElement("p");
            warning.className="tf-message";
            warning.textContent="Ingen frisk GPS-position. Ruter og ankomsttider er historiske eller utilgængelige.";
            box.appendChild(warning);
          }
          if(person.updated_at && !person.ghost){
            const stamp=document.createElement("small");
            const date=new Date(person.updated_at);
            stamp.textContent=Number.isNaN(date.getTime())?""
              :"Sidste registrerede GPS-fix: "+date.toLocaleString("da-DK")+
                (Number.isFinite(person.gps_age_minutes)?
                  " ("+person.gps_age_minutes+" min siden)":"");
            box.appendChild(stamp);
          }
          if(person.home_eta_minutes && !person.ghost && !person.stale){
            const homeEta=document.createElement("span");
            homeEta.textContent="På vej hjem · anslået "+person.home_eta_minutes+" min (GPS-estimat)";
            box.appendChild(homeEta);
          }
          if(person.destination && !person.ghost && !person.stale){
            const eta=document.createElement("span");
            eta.textContent="Mulig destination: "+person.destination+
              (person.eta_minutes ? " · ETA "+person.eta_minutes+" min" : "")+
              (person.destination_confidence ?
                 " · sikkerhed ca. "+person.destination_confidence+" %" : "");
            box.appendChild(eta);
          }
          if(Number.isFinite(person.latitude) &&
             Number.isFinite(person.longitude) && !person.ghost &&
             person.person===dockPerson.value){
            focusedLivePoint=[person.latitude,person.longitude];
          }
          if(!timelineMode && Number.isFinite(person.latitude) &&
             Number.isFinite(person.longitude) && !person.ghost){
            const point=[person.latitude,person.longitude];
            const battery=person.battery_percent;
            const color=person.stale?"#888888":battery!=null&&battery<20?"#d64646":
              battery!=null&&battery<=50?"#d79b3f":"#1fb77e";
            // Construct a marker from DOM text nodes, never HTML from HA sensor values.
            const markerBody=document.createElement("div");
            markerBody.className="tf-map-person"+(person.stale?" tf-neon-stale":"");
            const pin=document.createElement("span");
            pin.className="tf-person-pin";
            pin.textContent=String(person.name||"?").trim().split(/\s+/)
              .slice(0,2).map(word=>word[0]||"").join("").toUpperCase();
            pin.style.borderColor=color;
            markerBody.appendChild(pin);
            const metricRow=document.createElement("div");
            metricRow.className="tf-neon-stats";
            const addMetric=(symbol,value,title,extraClass="")=>{
              const item=document.createElement("span");
              item.className="tf-neon-metric"+(extraClass?" "+extraClass:"");
              item.title=title;
              const glyph=document.createElement("span");
              glyph.className="tf-neon-symbol";
              // Fixed icon markup: no values from people, names or sensors are injected.
              glyph.innerHTML=symbol==="speed"
                ?'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17a9 9 0 0 1 18 0"/><path d="M12 17l5-6"/><circle cx="12" cy="17" r="1.5"/><path d="M6 21h12"/></svg>'
                :'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="6" width="18" height="12" rx="2"/><path d="M22 10v4"/><path d="M5 9h7v6H5z" fill="currentColor" stroke="none"/></svg>';
              const label=document.createElement("span");
              label.textContent=value;
              item.append(glyph,label);
              metricRow.appendChild(item);
            };
            const speed=Number(person.speed_kmh);
            const hasSpeed=!person.stale && person.speed_kmh!=null &&
              Number.isFinite(speed) && speed>=0;
            const batteryAvailable=Number.isFinite(battery);
            addMetric("speed",hasSpeed?Math.round(speed)+" km/t":"— km/t",
              hasSpeed?"Aktuel hastighed":"Ingen frisk hastighed");
            addMetric("battery",batteryAvailable?Math.round(battery)+" %":"— %",
              batteryAvailable?"Batteriniveau":"Batteriniveau ikke tilgængeligt",
              batteryAvailable&&battery<=20?"battery-low":"");
            markerBody.appendChild(metricRow);
            const stay=Number(person.stay_minutes);
            const staying=!person.stale && person.movement==="stationary" &&
              person.stay_minutes!=null && Number.isFinite(stay) && stay>=0;
            if(staying){
              const stayLabel=document.createElement("span");
              stayLabel.className="tf-neon-stay";
              stayLabel.textContent="◷ Ophold "+(stay>=60?
                Math.floor(stay/60)+" t "+Math.floor(stay%60)+" min":
                Math.floor(stay)+" min");
              markerBody.appendChild(stayLabel);
            }
            const icon=window.L.divIcon({
              className:"tf-person-icon",html:markerBody.outerHTML,
              iconSize:[132,100],iconAnchor:[66,26],popupAnchor:[0,-24]
            });
            const mapMarker=window.L.marker(point,{icon}).addTo(map);
            const popup=document.createElement("div");
            popup.className="tf-neon-focus";
            const popupName=document.createElement("strong");
            popupName.textContent=person.name;
            popup.appendChild(popupName);
            const popupInfo=document.createElement("span");
            popupInfo.textContent=(hasSpeed?Math.round(speed)+" km/t":"Hastighed ikke tilgængelig")+
              " · "+(batteryAvailable?Math.round(battery)+" % batteri":"Batteri ukendt");
            popup.appendChild(popupInfo);
            if(staying){
              const popupStay=document.createElement("span");
              popupStay.textContent="Ophold: "+Math.floor(stay)+" minutter";
              popup.appendChild(popupStay);
            }
            if(person.stale){
              const gps=document.createElement("span");
              gps.textContent="GPS er ikke opdateret";
              popup.appendChild(gps);
            }
            if(person.power_save===true||person.gps_glitch_recent){
              const warning=document.createElement("span");
              warning.textContent=(person.power_save===true?"Batterisparer aktiv · ":"")+
                (person.gps_glitch_recent?"Mulige GPS-hop frasorteret":"GPS kan opdatere sjældnere");
              popup.appendChild(warning);
            }
            const timelineAction=document.createElement("button");
            timelineAction.type="button";
            timelineAction.className="tf-save tf-mini";
            timelineAction.textContent="Vis 24-timers tidslinje";
            timelineAction.addEventListener("click",()=>{
              dockPerson.value=person.person;
              resetToToday();
              previousCenteredFix=null;
              loadTimeline();
            });
            popup.appendChild(timelineAction);
            const dayAction=document.createElement("button");
            dayAction.type="button";dayAction.className="tf-save tf-mini";
            dayAction.textContent="Dagens statistik og besøg";
            dayAction.addEventListener("click",()=>{
              this._activityRequestedPerson=person.person;
              this.show("activity");
            });
            popup.appendChild(dayAction);
            mapMarker.bindPopup(popup);
            bounds.push(point);
            if(!person.stale){
              const navigate=document.createElement("button");
              navigate.type="button";navigate.className="tf-save";
              navigate.textContent="Se personens position";
              navigate.addEventListener("click",()=>this.openLocationDialog({
                latitude:person.latitude,longitude:person.longitude,name:person.name
              },navigate));
              box.appendChild(navigate);
            }
          }
          const cardActions=document.createElement("div");
          cardActions.className="tf-card-actions";
          const dayReportButton=document.createElement("button");
          dayReportButton.type="button";dayReportButton.className="tf-save";
          dayReportButton.textContent="Dagens statistik";
          dayReportButton.disabled=person.ghost && person.person!==data.viewer_person;
          dayReportButton.addEventListener("click",()=>{
            this._activityRequestedPerson=person.person;
            this.show("activity");
          });
          cardActions.appendChild(dayReportButton);
          const goRoute=document.createElement("button");
          goRoute.type="button";goRoute.className="tf-save";
          goRoute.textContent="Vis rute";goRoute.disabled=person.ghost && person.person!==data.viewer_person;
          goRoute.addEventListener("click",()=>{
            this._routeFilterPerson=person.person;this.show("routes");
          });
          cardActions.appendChild(goRoute);
          if(person.person!==data.viewer_person){
            const write=document.createElement("button");
            write.type="button";write.className="tf-save";
            write.textContent="Skriv besked";
            write.addEventListener("click",()=>{
              this._composeRecipient=person.person;this.show("contact");
            });
            cardActions.appendChild(write);
          }
          box.appendChild(cardActions);
          list.appendChild(box);
        }
        if(!list.children.length){
          const empty=document.createElement("p");empty.className="tf-empty";
          empty.textContent="Ingen tilknyttede familiemedlemmer endnu. Tilknyt personer og HA-brugere i Administration.";
          list.appendChild(empty);
        }
        if(timelineMode && timelineData){
          const trackBounds=[];
          const color=this.settings.colors?.[timelineData.person]||"#24d5d9";
          const matched=roadMatchToggle.checked?
            (timelineData.matched_segments||[]):[];
          const drawUnmatched=fixes=>{
            const pts=fixes.map(fix=>[fix.lat,fix.lon]);
            if(pts.length>1){
              window.L.polyline(pts,{color:"#ffffff",weight:5,opacity:.3}).addTo(map);
              window.L.polyline(pts,{color,weight:3,opacity:.9}).addTo(map);
            }else if(pts.length){
              window.L.circleMarker(pts[0],{
                radius:4,color:"#fff",weight:1,fillColor:color,fillOpacity:1
              }).addTo(map);
            }
          };
          for(const segment of timelineData.segments||[]){
            const valid=(segment||[]).filter(p=>Number.isFinite(p.lat) &&
              Number.isFinite(p.lon));
            if(!valid.length)continue;
            trackBounds.push(...valid.map(p=>[p.lat,p.lon]));
            if(!matched.length || valid.length===1){
              drawUnmatched(valid);
            }else{
              // Draw actual OSM road geometry for matched portions, and raw
              // GPS only where a trustworthy road match is unavailable.
              let unmatched=[];
              for(let i=1;i<valid.length;i++){
                const covered=matched.some(road=>road.start_t<=valid[i-1].t &&
                  road.end_t>=valid[i].t);
                if(covered){
                  if(unmatched.length)drawUnmatched(unmatched);
                  unmatched=[];
                }else{
                  if(!unmatched.length)unmatched.push(valid[i-1]);
                  unmatched.push(valid[i]);
                }
              }
              if(unmatched.length)drawUnmatched(unmatched);
            }
          }
          for(const road of matched){
            if(!Array.isArray(road.coordinates)||road.coordinates.length<2)continue;
            window.L.polyline(road.coordinates,{
              color:"#081624",weight:8,opacity:.60
            }).addTo(map);
            window.L.polyline(road.coordinates,{
              color:"#2ce2eb",weight:4,opacity:1
            }).addTo(map);
          }
          const inferred=roadMatchToggle.checked?
            (timelineData.inferred_segments||[]):[];
          for(const road of inferred){
            if(!Array.isArray(road.coordinates)||road.coordinates.length<2)continue;
            const guess=window.L.polyline(road.coordinates,{
              color:"#eeb968",weight:4,opacity:.9,dashArray:"6 8"
            }).addTo(map);
            guess.bindTooltip("≈ Anslået vej ("+
              (road.basis==="previous_road_history"?"tidligere ture":"vejnet")+
              ") · ikke GPS-målt");
          }
          for(const event of timelineData.events||[]){
            if(event.kind!=="stay")continue;
            const observed=(timelineData.segments||[]).flat().find(p=>
              p.t>=event.started_at && p.t<=event.ended_at);
            if(!observed)continue;
            const stop=window.L.circleMarker([observed.lat,observed.lon],{
              radius:7,color:"#ffffff",weight:2,fillColor:"#a777f3",fillOpacity:.85
            }).addTo(map);
            const stopLabel=document.createElement("span");
            stopLabel.textContent="Ophold "+event.duration_min+" min"+
              (event.label?" · "+event.label:"");
            stop.bindTooltip(stopLabel);
          }
          if(trackBounds.length){
            map.setView(trackBounds[trackBounds.length-1],15,{animate:false});
          }else if(focusedLivePoint){
            map.setView(focusedLivePoint,15,{animate:false});
          }else map.setView([this.hassInstance.config.latitude||0,
                            this.hassInstance.config.longitude||0],11);
          updateCursor(playbackTime);
        }else if(focusedLivePoint){
          map.setView(focusedLivePoint,14);
        }else if(!timelineMode && bounds.length){
          map.fitBounds(bounds,{padding:[35,35],maxZoom:15});
        }else if(zoneBounds.length)map.fitBounds(zoneBounds,{padding:[35,35],maxZoom:14});
        else map.setView([this.hassInstance.config.latitude||0,
                           this.hassInstance.config.longitude||0],5);
        setTimeout(()=>{if(this._familyMap===map)map.invalidateSize();},150);
      }catch(error){this.message("Familiekort kunne ikke indlæses: "+error.message,true);}
      finally{
        refresh.disabled=false;drawing=false;
        if(pendingRedraw){pendingRedraw=false;draw();}
      }
    };
    refresh.addEventListener("click",()=>{previousSignature="";draw();});
    zonesToggle.addEventListener("change",()=>{previousSignature="";draw();});
    polygonsToggle.addEventListener("change",()=>{previousSignature="";draw();});
    routesToggle.addEventListener("change",()=>{previousSignature="";draw();});
    routeHours.addEventListener("change",()=>{previousSignature="";draw();});
    routePerson.addEventListener("change",()=>{previousSignature="";draw();});
    await draw();
    if(this._timelineRequestedPerson){
      const requested=this._timelineRequestedPerson;
      this._timelineRequestedPerson=null;
      const requestedDate=this._timelineRequestedDate;
      this._timelineRequestedDate=null;
      if([...dockPerson.options].some(option=>option.value===requested)){
        dockPerson.value=requested;
      }
      if(requestedDate && requestedDate>=dockDate.min && requestedDate<=dockDate.max)
        dockDate.value=requestedDate;
      await loadTimeline();
    }
    this._familyTimer=setInterval(()=>{
      // Do not rebuild the map mid-playback or change the selected history zoom.
      if(this.active==="live" && this.isConnected && !timelineMode)draw();
    },30000);
  }

  async today(root) {
    const heading = document.createElement("h2");
    heading.textContent = "Min dag";
    root.appendChild(heading);
    const info = document.createElement("p");
    info.className = "tf-message";
    root.appendChild(info);
    const sharing=document.createElement("section");sharing.className="tf-person";
    root.appendChild(sharing);
    const trackingTitle=document.createElement("strong");
    trackingTitle.textContent="Sporing via din telefon";
    const trackingNote=document.createElement("p");trackingNote.className="tf-message";
    trackingNote.textContent="Din valgte Home Assistant Companion-telefon leverer GPS, batteri, opladning og aktivitet. Hvis telefonen ikke sender data, vises de som utilgængelige.";
    sharing.append(trackingTitle,trackingNote);
    const routineLabel=document.createElement("strong");
    routineLabel.textContent="Indlæring af destinations- og afgangsmønstre";
    sharing.appendChild(routineLabel);
    const routineNote=document.createElement("p");
    routineNote.className="tf-message";
    routineNote.textContent="Administrator vælger, hvem der får indlært typiske afgangstider. Data gemmes lokalt i op til 60 dage. Destinationsgæt baseret på bevægelse og kendte steder anvendes stadig.";
    sharing.appendChild(routineNote);
    const permissions=document.createElement("section");
    permissions.className="tf-person";
    const permissionsTitle=document.createElement("strong");
    permissionsTitle.textContent="Hvem kan se mine data?";
    const permissionsBody=document.createElement("div");
    permissions.append(permissionsTitle,permissionsBody);
    sharing.appendChild(permissions);
    const refreshPermissions=async()=>{
      try{
        const policy=await this.hassInstance.callApi("GET","tiny_family/sharing");
        const mine=policy.mine;
        permissionsBody.replaceChildren();
        if(!mine){permissionsBody.textContent="Din konto mangler en personbinding.";return;}
        const lines=[
          ["Position og 24-timers ruter",mine.ghost_active
            ?"Skjult i Tiny Family for andre":"Delt med: "+(mine.tiny_family_location_viewers.join(", ")||"ingen tilknyttede familiemedlemmer")],
          ["Systemhændelser",mine.ghost_active?"Privat i Tiny Family":
            "Synlige for familiemedlemmer med adgang"],
          ["Stedforslag","Delt med familien, medmindre administrator markerer dem private"],
          ["Turarkiv","Mine historiske data er personlige; administrator styrer sletning"],
          ["Beskeder","Kun afsender og konfigurerede modtagere"],
          ["Privat historik fra ældre opsætning",mine.ghost_active
            ?"Historiske privatmarkerede data er fortsat beskyttet":"Ingen"],
          ["Pushmodtagere",(mine.configured_phone_recipients||[]).join(", ")||"Ingen"],
        ];
        for(const [name,value] of lines){
          const line=document.createElement("p");
          const label=document.createElement("strong");label.textContent=name+": ";
          line.append(label,document.createTextNode(value));
          permissionsBody.appendChild(line);
        }
        const caveat=document.createElement("p");
        caveat.className="tf-message";
        caveat.textContent="GPS indsamles kun, når Companion-appen og telefonens tilladelser gør det muligt. Home Assistants øvrige adgangsrettigheder og Recorder administreres separat.";
        permissionsBody.appendChild(caveat);
      }catch(error){permissionsBody.textContent="Delingsoversigten kunne ikke indlæses.";}
    };
    try{
      const privacy=await this.hassInstance.callApi("GET","tiny_family/privacy");
      routineNote.textContent=privacy.learn_my_routines===true
        ?"Rutineindlæring er aktiveret af administrator for dig. Dine typiske afgangstider lagres lokalt i op til 60 dage."
        :"Rutineindlæring er ikke aktiveret for dig. Kun administrator kan ændre dette.";
    }catch(error){
      routineNote.textContent="Tilknyt din Home Assistant-bruger til et familiemedlem under Administration for at se personlige data.";
    }
    if(sharing.isConnected)await refreshPermissions();
    const personalData=document.createElement("section");
    personalData.className="tf-person";
    const personalTitle=document.createElement("strong");
    personalTitle.textContent="Mine lokalt gemte data";
    const personalIntro=document.createElement("p");
    personalIntro.textContent="Administrator administrerer sletning af GPS-tidslinjer, ture og steder. Du kan stadig slette dine egne indlærte afgangsmønstre og eksportere dine data. Tidslinjens opbevaring er "+(this.settings.timeline_retention_days??365)+" dage. Home Assistant Recorder er separat.";
    const choices={};
    for(const [key,label] of [
      ["routines","Indlærte afgangsmønstre (administrators valg ændres ikke)"]
    ]){
      const row=document.createElement("label");
      const checked=document.createElement("input");
      checked.type="checkbox";choices[key]=checked;
      row.append(checked,document.createTextNode(" "+label));
      personalData.appendChild(row);
    }
    const erase=document.createElement("button");
    erase.type="button";erase.className="tf-save";
    erase.style.background="var(--error-color,#a52d2d)";
    erase.textContent="Slet mine afgangsmønstre";
    erase.addEventListener("click",async()=>{
      const categories=Object.keys(choices).filter(k=>choices[k].checked);
      if(!categories.length){this.message("Vælg først de data, du vil slette.",true);return;}
      if(!window.confirm("Slet de valgte Tiny Family-data permanent? Dette kan ikke fortrydes."))return;
      erase.disabled=true;
      try{
        await this.hassInstance.callApi("DELETE","tiny_family/personal_data",{
          categories,confirm:true
        });
        for(const input of Object.values(choices))input.checked=false;
        this.message("De valgte personlige data er slettet.");
        await this.hassInstance.callApi("GET","tiny_family/personal_data");
      }catch(error){this.message("Sletning fejlede: "+error.message,true);}
      finally{erase.disabled=false;}
    });
    personalData.prepend(personalTitle,personalIntro);
    personalData.appendChild(erase);
    const exportButton=document.createElement("button");
    exportButton.type="button";exportButton.className="tf-save";
    exportButton.textContent="Eksportér mine Tiny Family-data (JSON)";
    exportButton.addEventListener("click",async()=>{
      exportButton.disabled=true;
      try {
        const data=await this.hassInstance.callApi("GET","tiny_family/export");
        const blob=new Blob([JSON.stringify(data,null,2)],{
          type:"application/json"
        });
        const url=URL.createObjectURL(blob);
        const a=document.createElement("a");
        a.href=url;a.download="tiny-family-personal-export.json";
        a.style.display="none";document.body.appendChild(a);
        a.click();a.remove();
        setTimeout(()=>URL.revokeObjectURL(url),1000);
        this.message("Din personlige eksport er klargjort. Filen indeholder private positionsdata.");
      }catch(error){this.message("Eksport mislykkedes: "+error.message,true);}
      finally{exportButton.disabled=false;}
    });
    personalData.appendChild(exportButton);
    root.appendChild(personalData);
    const recentArchive=document.createElement("section");
    recentArchive.className="tf-person";
    const recentTitle=document.createElement("strong");
    recentTitle.textContent="Seneste afsluttede ture og ophold";
    const recentBody=document.createElement("div");
    recentArchive.append(recentTitle,recentBody);
    root.appendChild(recentArchive);
    try{
      const archive=await this.hassInstance.callApi("GET","tiny_family/activity");
      for(const item of (archive.entries||[]).slice(0,5)){
        const line=document.createElement("p");
        line.textContent=(item.kind==="trip"?"Tur":"Ophold")+" · "+
          new Date(item.ended_at*1000).toLocaleString("da-DK")+" · "+
          item.duration_min+" min"+
          (item.kind==="trip"?" · "+item.distance_km+" km":"");
        recentBody.appendChild(line);
      }
      if(!recentBody.children.length)recentBody.textContent="Ingen afsluttede ture eller ophold endnu.";
    }catch(error){recentBody.textContent="Arkivet er ikke tilgængeligt endnu.";}
    const ownDiary=document.createElement("details");
    ownDiary.className="tf-person tf-person-diary";
    const diaryHeading=document.createElement("summary");
    diaryHeading.textContent="Min teksttidslinje · "+
      (this.settings?.timeline_retention_days??365)+" dages historik";
    ownDiary.appendChild(diaryHeading);
    root.appendChild(ownDiary);
    ownDiary.addEventListener("toggle",()=>{
      if(ownDiary.open && !ownDiary.dataset.loaded){
        ownDiary.dataset.loaded="1";
        void this.dailyReport(ownDiary,{view:"today",ownOnly:true});
      }
    });
    const values = document.createElement("div");
    values.className = "tf-metrics";
    // Show live status first on mobile, without using a detached DOM anchor.
    if(this.active!=="today" || !root.isConnected)return;
    root.insertBefore(values,sharing.parentNode===root?sharing:null);
    const extraDetails=document.createElement("details");
    extraDetails.className="tf-person tf-advanced";
    const extraTitle=document.createElement("summary");
    extraTitle.textContent="Flere aktivitets- og turdetaljer";
    const extraMetrics=document.createElement("div");
    extraMetrics.className="tf-metrics";
    extraDetails.append(extraTitle,extraMetrics);
    root.insertBefore(extraDetails,sharing.parentNode===root?sharing:null);
    const primaryMetrics=new Set([
      "place","battery","charging","activity","speed",
      "gpsHealth","gpsAge","homeEta"
    ]);
    try {
      const data = await this.hassInstance.callApi("GET","tiny_family/communications");
      if (this.active !== "today") return;
      this._todayPerson = data.person;
      const entity = this.hassInstance.states[data.person];
      info.textContent = (entity?.attributes?.friendly_name || data.person) +
        " · personlig status fra Home Assistant Companion";
      for(const [key,label] of [
        ["place","Placering"], ["battery","Batteri"],
        ["charging","Opladning"], ["activity","Telefonaktivitet"],
        ["movement","Bevægelse"], ["distance","Distance i dag"],
        ["distanceWeek","Distance i denne uge"], ["stays","Ophold i dag"],
        ["currentStay","Aktuelt ophold"], ["lastTrip","Sidste tur"],
        ["speed","Aktuel hastighed"], ["maxSpeed","Maks. hastighed i dag"],
        ["destination","Destination"], ["eta","Anslået ankomst"],
        ["homeEta","Anslået hjemkomst"],
        ["usualDeparture","Typisk afgang"], ["gpsHealth","GPS-status"],
        ["gpsAge","Minutter siden GPS"], ["updated","Sidste opdatering"]
      ]) {
        const row = document.createElement("section");
        row.className = "tf-stat";
        const title = document.createElement("strong");title.textContent = label;
        const value = document.createElement("span");
        value.dataset.todayMetric = key;
        row.append(title,value);
        (primaryMetrics.has(key)?values:extraMetrics).appendChild(row);
      }
      try {
        const own=await this.hassInstance.callApi("GET","tiny_family/status");
        this._todayPrivateProfile=(own.people||[]).find(item=>item.person===data.person)||null;
      }catch(error){this._todayPrivateProfile=null;}
      this.updateToday();
    } catch (error) {
      info.textContent = "Din konto skal først knyttes til en person i Administration. " +
        (error.message || String(error));
    }
  }

  updateToday() {
    if (!this._todayPerson || this.active !== "today") return;
    const person = this._todayPerson;
    const all = this.hassInstance.states;
    const slug = person.slice("person.".length);
    const current = all[person];
    const state = key => {
      const value = all["sensor.tiny_family_"+slug+"_"+key]?.state;
      return (!value || ["unknown","unavailable"].includes(value)) ? "—" : value;
    };
    const units = (value,unit) => value==="—" ? "—" : value+" "+unit;
    const batteryEntity = this.settings?.batteries?.[person];
    const batteryState = batteryEntity && all[batteryEntity]?.state;
    const values = {
      place: current?.state || "—",
      battery: batteryState != null ? batteryState+" %" : "Ikke tilknyttet",
      charging: all["binary_sensor.tiny_family_"+slug+"_charging"]?.state==="on"
        ? "Oplader" : all["binary_sensor.tiny_family_"+slug+"_charging"]?.state==="off"
        ? "Ikke tilsluttet" : "—",
      activity: state("activity"),
      movement: state("gps_health")==="fresh" ? state("movement") : "—",
      distance: units(state("distance_today"),"km"),
      distanceWeek: units(state("distance_week"),"km"),
      stays: state("stays_today"),
      currentStay: units(state("current_stay"),"min"),
      lastTrip: state("last_trip"),
      speed: state("gps_health")==="fresh"
        ? units(state("current_speed"),"km/t") : "—",
      maxSpeed: units(state("max_speed"),"km/t"),
      destination: state("gps_health")==="fresh" ? state("destination") : "—",
      eta: state("gps_health")==="fresh" && state("destination")!=="Ingen"
        ? units(state("destination_eta"),"min") : "—",
      homeEta: state("gps_health")==="fresh"
        ? units(state("home_eta"),"min") : "—",
      usualDeparture: this._todayPrivateProfile?.usual_departure || "—",
      gpsHealth: ({fresh:"Frisk",stale:"Forældet",unknown:"Afventer GPS"})[
        state("gps_health")] || "Afventer GPS",
      gpsAge: units(state("gps_age_minutes"),"min"),
      updated: current?.last_updated ?
        new Date(current.last_updated).toLocaleString("da-DK") : "Ingen opdatering",
    };
    this.querySelectorAll("[data-today-metric]").forEach(element =>
      element.textContent = values[element.dataset.todayMetric] || "—");
  }

  async dailyReport(root,{view="activity",ownOnly=false,fixedPerson=null}={}) {
    const timezone=this.hassInstance.config.time_zone||undefined;
    const localDay=()=>new Intl.DateTimeFormat("sv-SE",{
      timeZone:timezone,year:"numeric",month:"2-digit",day:"2-digit"
    }).format(new Date());
    const shiftDay=(day,offset)=>{
      const [year,month,date]=day.split("-").map(Number);
      return new Date(Date.UTC(year,month-1,date+offset)).toISOString().slice(0,10);
    };
    const today=localDay();
    const retention=Math.max(30,Math.min(3650,
      Number(this.settings?.timeline_retention_days??365)||365));
    const firstDay=shiftDay(today,1-retention);
    const panel=document.createElement("section");
    panel.className="tf-daily-report";
    const heading=document.createElement("strong");
    heading.textContent="Dagens statistik og tidslinje";
    const controls=document.createElement("div");
    controls.className="tf-daily-controls";
    const personSelect=document.createElement("select");
    personSelect.setAttribute("aria-label","Person for dagsrapport");
    const back=document.createElement("button");back.type="button";
    back.textContent="‹";back.setAttribute("aria-label","Forrige dag");
    const date=document.createElement("input");date.type="date";
    date.value=today;date.min=firstDay;date.max=today;
    date.setAttribute("aria-label","Dato for dagsrapport");
    const next=document.createElement("button");next.type="button";
    next.textContent="›";next.setAttribute("aria-label","Næste dag");
    controls.append(personSelect,back,date,next);
    const status=document.createElement("p");
    status.className="tf-message";status.setAttribute("role","status");
    status.textContent="Henter registrerede besøg og ture…";
    const stats=document.createElement("div");stats.className="tf-daily-stats";
    const scroll=document.createElement("div");scroll.className="tf-daily-scroll";
    scroll.setAttribute("aria-label","Tekstbaseret dagsforløb");
    const mapButton=document.createElement("button");mapButton.type="button";
    mapButton.className="tf-save";mapButton.textContent="Vis denne dag på kortet";
    // The regular map's selector can hide another person's Ghost records;
    // never send an admin from a private diary to the wrong person's map.
    mapButton.hidden=Boolean(fixedPerson);
    mapButton.addEventListener("click",()=>{
      if(!personSelect.value)return;
      this._timelineRequestedPerson=personSelect.value;
      this._timelineRequestedDate=date.value;
      this.show("live");
    });
    panel.append(heading,controls,status,stats,scroll,mapButton);
    root.appendChild(panel);
    let latestRequest=0;
    const formatTime=(timestamp)=>new Date(timestamp*1000).toLocaleTimeString(
      "da-DK",{hour:"2-digit",minute:"2-digit",timeZone:timezone});
    const count=(number,unit="")=>Number.isFinite(number)?
      String(number).replace(".",",")+(unit?" "+unit:""):"—";
    const updateButtons=()=>{
      back.disabled=date.value<=firstDay;
      next.disabled=date.value>=today;
    };
    const render=async()=>{
      const person=personSelect.value,selectedDay=date.value;
      if(!person || selectedDay<firstDay || selectedDay>today)return;
      const id=++latestRequest;
      updateButtons();
      status.textContent="Henter "+selectedDay+"…";
      stats.replaceChildren();scroll.replaceChildren();
      try{
        const response=await this.hassInstance.callApi("GET",
          "tiny_family/timeline?person="+encodeURIComponent(person)+
          "&date="+encodeURIComponent(selectedDay)+"&view=report");
        if(id!==latestRequest||this.active!==view||!panel.isConnected)return;
        const s=response.summary||{};
        const statistic=[
          ["GPS-distance",count(s.gps_distance_km,"km")],
          ["Arkiverede ture",count(s.archived_trip_distance_km,"km")],
          ["Gået (anslået)",count(s.walking_minutes,"min")],
          ["Kørt (anslået)",count(s.driving_minutes,"min")],
          ["Gåfart (GPS-skøn)",count(s.walking_avg_kmh,"km/t")],
          ["Kørefart (GPS-skøn)",count(s.driving_avg_kmh,"km/t")],
          ["Maks. målt fart",count(s.max_recorded_speed_kmh,"km/t")],
          ["Gns. målt fart i bevægelse",count(s.avg_recorded_moving_speed_kmh,"km/t")],
          ["Ophold / ture",count(s.stays)+" / "+count(s.trips)],
          ["GPS-punkter / afbrud",count(s.gps_points)+" / "+count(s.gps_gaps)],
        ];
        for(const [label,value] of statistic){
          const cell=document.createElement("section");cell.className="tf-stat";
          const title=document.createElement("strong");title.textContent=label;
          const number=document.createElement("span");number.textContent=value;
          cell.append(title,number);stats.appendChild(cell);
        }
        const items=response.items||[];
        status.textContent=!items.length
          ?"Ingen registrerede ophold eller ture for denne dato."
          :items.length+" registreringer · "+count(s.observed_minutes,"min")+
            " med sammenhængende GPS. Kun registrerede perioder tælles.";
        if(s.speed_health==="zero_despite_movement")
          status.textContent+=" Telefonen har meldt 0 km/t trods bevægelse; gå/kør er GPS-skøn.";
        if(s.speed_health==="missing")
          status.textContent+=" Fartsensoren har ikke leveret brugbare målinger.";
        for(const item of items){
          const row=document.createElement("article");row.className="tf-daily-row";
          const clock=document.createElement("time");
          clock.textContent=formatTime(item.started_at)+
            (item.ended_at>item.started_at?"–"+formatTime(item.ended_at):"");
          const content=document.createElement("div");
          const name=document.createElement("strong");
          const kind=item.kind==="stay"?"Ophold":item.kind==="gap"
            ?"GPS-afbrud":item.kind==="position"?"Registreret position":
              item.mode==="walking"?"Gang (anslået)":
              item.mode==="driving"?"Kørsel (anslået)":"Tur / bevægelse";
          name.textContent=kind+" · "+(item.label||"Ukendt sted");
          const details=document.createElement("span");
          const info=[item.duration_min?count(item.duration_min,"min"):"Tidspunkt registreret"];
          if(Number.isFinite(item.distance_km))info.push(count(item.distance_km,"km"));
          if(Number.isFinite(item.max_speed_kmh))
            info.push("op til "+count(item.max_speed_kmh,"km/t"));
          info.push(item.kind==="gap"?"manglende GPS-data":
            item.source==="archive"?"gemt begivenhed":"GPS-baseret skøn");
          if(item.gps_gap)info.push("afbrudt rute");
          details.textContent=info.join(" · ");
          content.append(name,details);row.append(clock,content);scroll.appendChild(row);
        }
      }catch(error){
        if(id!==latestRequest||this.active!==view||!panel.isConnected)return;
        status.textContent="Dagens statistik kunne ikke hentes: "+this.errorText(error);
      }
    };
    personSelect.addEventListener("change",()=>{date.value=today;void render();});
    date.addEventListener("change",render);
    back.addEventListener("click",()=>{
      if(date.value>firstDay){date.value=shiftDay(date.value,-1);void render();}
    });
    next.addEventListener("click",()=>{
      if(date.value<today){date.value=shiftDay(date.value,1);void render();}
    });
    if(fixedPerson){
      // An HA administrator may be unbound to a Tiny Family person. The
      // settings editor already has the verified person ID; don't depend on
      // the normal family status endpoint, which requires a personal binding.
      const member=(this.settings?.available_persons||[])
        .find(item=>item.id===fixedPerson);
      const option=document.createElement("option");
      option.value=fixedPerson;option.textContent=member?.name||fixedPerson;
      personSelect.appendChild(option);
      personSelect.hidden=true;
      await render();
      return;
    }
    try{
      const family=await this.hassInstance.callApi("GET","tiny_family/status");
      if(this.active!==view||!panel.isConnected)return;
      for(const member of family.people||[]){
        if(ownOnly && member.person!==family.viewer_person)continue;
        if(fixedPerson && member.person!==fixedPerson)continue;
        if(member.ghost && member.person!==family.viewer_person)continue;
        const option=document.createElement("option");
        option.value=member.person;option.textContent=member.name;
        personSelect.appendChild(option);
      }
      const requested=fixedPerson || (ownOnly?family.viewer_person:
        (this._activityRequestedPerson||family.viewer_person));
      if(!ownOnly && !fixedPerson)this._activityRequestedPerson=null;
      personSelect.value=[...personSelect.options].some(o=>o.value===requested)
        ?requested:family.viewer_person;
      if(!personSelect.value && personSelect.options.length)
        personSelect.selectedIndex=0;
      personSelect.hidden=ownOnly||Boolean(fixedPerson);
      if(!personSelect.value){
        status.textContent="Ingen person er tilknyttet din konto.";return;
      }
      await render();
    }catch(error){
      if(this.active===view && panel.isConnected)
        status.textContent="Kan ikke hente familiens personliste: "+this.errorText(error);
    }
  }

  async activity(root) {
    root.classList.add("tf-activity-view");
    const heading=document.createElement("h2");
    heading.textContent="Familiens dagsoversigt";root.appendChild(heading);
    const note=document.createElement("p");note.className="tf-message tf-screen-intro";
    note.textContent="Vælg person og dato. Registrerede besøg, ture og GPS-baserede fartskøn vises som tekst. Historik gemmes i "+(this.settings.timeline_retention_days??365)+" dage, som administrator kan ændre.";
    root.appendChild(note);
    void this.dailyReport(root);
    const archive=document.createElement("details");
    archive.className="tf-person tf-activity-archive";
    const archiveHeading=document.createElement("summary");
    archiveHeading.textContent="Seneste afsluttede ture og ophold (min konto)";
    archive.appendChild(archiveHeading);
    root.appendChild(archive);
    const routeButton=document.createElement("button");
    routeButton.className="tf-save";routeButton.type="button";
    routeButton.textContent="Se egne og delte GPS-spor på rutekortet";
    routeButton.addEventListener("click",()=>this.show("routes"));
    archive.appendChild(routeButton);
    const activityNav=document.createElement("nav");activityNav.className="tf-screen-nav";
    activityNav.setAttribute("aria-label","Filtrér ture og ophold");
    archive.appendChild(activityNav);
    const list=document.createElement("div");list.className="tf-activity-list";archive.appendChild(list);
    const activityFilters=[
      ["all","Alle"],["trip","Ture"],["stay","Ophold"]
    ];
    const selectActivity=key=>{
      for(const child of list.children){
        child.hidden=key!=="all" && child.dataset.activityKind!==key;
      }
      for(const [filter,button] of filterButtons){
        button.setAttribute("aria-pressed",String(filter===key));
      }
    };
    const filterButtons=[];
    for(const [key,label] of activityFilters){
      const button=document.createElement("button");
      button.type="button";button.textContent=label;
      button.addEventListener("click",()=>selectActivity(key));
      activityNav.appendChild(button);filterButtons.push([key,button]);
    }
    selectActivity("all");
    try {
      const data=await this.hassInstance.callApi("GET","tiny_family/activity");
      if(this.active!=="activity")return;
      if(data.trip_active){
        const active=document.createElement("section");
        active.className="tf-person";
        active.textContent="En tur er i gang. Den vises først her, når afslutningen er registreret.";
        list.appendChild(active);
      }
      for(const item of data.entries||[]){
        const card=document.createElement("section");card.className="tf-person";
        card.dataset.activityKind=item.kind;
        const title=document.createElement("strong");
        const fmt=t=>new Date(t*1000).toLocaleString("da-DK");
        title.textContent=(item.kind==="trip"?"Tur":"Ophold")+" · "+
          fmt(item.started_at)+" – "+fmt(item.ended_at);
        const body=document.createElement("p");
        const metrics=item.kind==="trip"
          ?item.distance_km+" km · maks. "+item.max_speed_kmh+" km/t"
          :(item.label||"Ukendt sted");
        body.textContent=item.duration_min+" min · "+metrics+
          (item.gps_gap?" · GPS-afbrydelse":"")+
          (item.private?" · historisk privatmarkeret":"");
        card.append(title,body);list.appendChild(card);
      }
      if(!list.children.length){
        const empty=document.createElement("p");empty.className="tf-empty";
        empty.textContent="Ingen afsluttede ture eller ophold endnu. Afbrudte GPS-spor vises som afbrudte ture, når der er oplysninger nok.";
        list.appendChild(empty);
      }
    }catch(error){list.textContent="Turarkivet kunne ikke indlæses: "+error.message;}
  }

  async history(root) {
    const heading=document.createElement("h2");
    heading.textContent="Systemhistorik";root.appendChild(heading);
    const intro=document.createElement("p");intro.className="tf-message";
    intro.textContent="Hændelser fra familien vises kun, når positionen deles med dig. Gamle globale poster uden ejer vises ikke.";
    root.appendChild(intro);
    const filterLabel=document.createElement("label");
    filterLabel.className="tf-person";
    filterLabel.textContent="Vis hændelser";
    const typeFilter=document.createElement("select");
    typeFilter.setAttribute("aria-label","Filtrér systemhistorik efter alarm");
    for(const [value,label] of [
      ["all","Alle hændelser"],["zones","Ankomst og afgang"],
      ["speed","Fartadvarsler"],["battery","Batteriadvarsler"],
      ["gps","GPS og forbindelse"],["trip","Afsluttede ture"],
      ["weekly","Ugerapporter"],["other","Øvrige hændelser"]
    ]){
      const opt=document.createElement("option");opt.value=value;opt.textContent=label;
      typeFilter.appendChild(opt);
    }
    filterLabel.appendChild(typeFilter);root.appendChild(filterLabel);
    const infoLabel=document.createElement("p");
    infoLabel.className="tf-message";
    infoLabel.textContent="Systemhistorikken dokumenterer, at Tiny Family registrerede en hændelse. Den er ikke en kvittering for, at Home Assistant eller telefonen modtog en pushnotifikation. Fartalarmer bygger på GPS-data og kan være upræcise.";
    root.appendChild(infoLabel);
    const list=document.createElement("div");root.appendChild(list);
    let entries=[];
    const types={
      zone_arrived:"zones",zone_departed:"zones",
      speed_warning:"speed",battery_low:"battery",
      battery_saver_warning:"battery",
      tracking_stale:"gps",tracking_restored:"gps",
      trip_ended:"trip",weekly_summary:"weekly",
    };
    const showHistory=()=>{
      list.replaceChildren();
      const selected=typeFilter.value;
      for(const item of entries){
        const category=types[item.event_key]||
          (/fart/i.test(item.kategori||"")?"speed":
           /batteri/i.test(item.kategori||"")?"battery":
           /ankomst|afgang/i.test(item.kategori||"")?"zones":
           /gps/i.test(item.kategori||"")?"gps":
           /tur/i.test(item.kategori||"")?"trip":
           /uge/i.test(item.kategori||"")?"weekly":"other");
        if(selected!=="all" && selected!==category)continue;
        const section=document.createElement("section");section.className="tf-person";
        const head=document.createElement("div");head.className="tf-card-head";
        const title=document.createElement("strong");
        title.textContent=(item.kategori||"Hændelse")+" · "+(item.tid||"");
        const label=document.createElement("span");label.className="tf-chip";
        label.textContent=({zones:"Zone",speed:"Fart",battery:"Batteri",
          gps:"GPS",trip:"Tur",weekly:"Uge",other:"Hændelse"})[category];
        head.append(title,label);
        const body=document.createElement("p");body.textContent=item.tekst||"";
        section.append(head,body);list.appendChild(section);
      }
      if(!list.children.length){
        const empty=document.createElement("p");empty.className="tf-empty";
        empty.textContent="Ingen hændelser i den valgte kategori.";
        list.appendChild(empty);
      }
    };
    typeFilter.addEventListener("change",showHistory);
    const clear=document.createElement("button");
    clear.type="button";clear.textContent="Ryd min systemhistorik";
    clear.className="tf-save";root.appendChild(clear);
    const load=async()=>{
      try{
        const data=await this.hassInstance.callApi("GET","tiny_family/history");
        if(this.active!=="history")return;
        entries=Array.isArray(data.entries)?data.entries:[];
        showHistory();
      }catch(error){
        list.textContent="Historikken er ikke tilgængelig: "+error.message;
        clear.disabled=true;
      }
    };
    clear.addEventListener("click",async()=>{
      if(!window.confirm("Skjul alle synlige systemhændelser i din egen historik?"))return;
      clear.disabled=true;
      try{
        await this.hassInstance.callApi("DELETE","tiny_family/history");
        await load();
      }catch(error){this.message("Rydning fejlede: "+error.message,true);}
      finally{clear.disabled=false;}
    });
    await load();
  }

  help(root) {
    const title = document.createElement("h2");
    title.textContent = "Hjælp til Tiny Family";
    root.appendChild(title);
    const items = [
      ["Kom i gang", "Opret først personer i Home Assistant, og forbind telefonerne med Companion-appen."],
      ["Administration", "Kun administratorer ser fanen Administration. Vælg person, Home Assistant-bruger og Companion-telefon; batteri, opladning og aktivitet hentes fra samme telefon, når sensorerne er registreret."],
      ["Min dag", "Viser den indloggede persons status fra Home Assistant. Manglende eller gamle data bliver ikke gættet."],
      ["Check-in", "Giver andre tilknyttede personer besked om, at du er okay. En frisk position kan medtages."],
      ["På vej hjem", "Sender en frivillig besked. ETA beregnes kun, når hastighed og position er tilstrækkelige."],
      ["SOS", "Sender en hjælpanmodning til de konfigurerede telefoner. Dette er ikke en alarmcentral eller en erstatning for 112."],
      ["Beskedstatus", "Accepteret betyder, at Home Assistants notifikationstjeneste tog imod anmodningen, ikke at telefonen har modtaget beskeden. Læsekvittering kræver, at modtageren markerer beskeden som læst inde i Tiny Family. Ved netværksfejl skal du bekræfte et eventuelt nyt forsøg, da det kan give en dobbeltbesked."],
      ["Automatiske alarmer", "Administrator bestemmer pr. familiemedlem hvilke ankomst-, afgangs-, fart-, batteri- og GPS-advarsler der er aktive. Systemhistorikken viser registrerede hændelser, ikke bekræftet push-levering."],
      ["GPS og sporing", "GPS-sporing bruger den valgte Companion-telefon. Hvis GPS-tilladelsen mangler, vises positionen som forældet eller utilgængelig."],
      ["Android-widget", "Opret en Action Button-widget i Home Assistant Companion: handling = Kald tjeneste. Vælg tiny_family.mobile_checkin, tiny_family.mobile_heading_home eller tiny_family.mobile_sos."],
      ["iPhone og iPad", "Brug Home Assistant Companion-genveje eller en iOS-Genvej, der kalder de tilsvarende Tiny Family-tjenester med den indloggede brugers konto."],
      ["Svar direkte fra push", "Ved en Companion notify.mobile_app_*-modtager kan du skrive svar på telefonens notifikation. Svarnøglen gælder én gang i højst 24 timer og udløber ved HA-genstart/genindlæsning. Andre notify-enheder har almindelige beskeder uden hurtigsvar."],
      ["Position ved beskeder", "Check-in, På vej hjem og SOS kan medtage en frisk GPS-position fra den valgte Companion-telefon. Almindelige fritekstbeskeder vedhæfter ikke GPS automatisk. Tidligere privatindstillinger fra gamle installationer bevares indtil migration."],
      ["Læsekvittering", "Modtageren kan trykke Markér som læst i Tiny Familys beskedhistorik. Dette bekræfter kun en handling inde i panelet, ikke at en pushbesked blev vist eller læst på telefonen."],
      ["Automatiske beskeder", "Aktivér kun efter valg af personer, konti og telefonmodtagere i Administration. Batteri- og fartadvarsler kræver passende Companion-sensorer."],
      ["Rutinegenkendelse", "Valgfri lokal læring af typiske afgangstider. Resultatet bruges kun efter mindst tre sammenlignelige afgangstider."],
      ["Privatliv", "Hver bruger kan kun se sin egen beskedhistorik i Tiny Family. Der er stadig selvstændige Home Assistant-rettigheder til andre entiteter."],
    ];
    items.push(["GPS-datakvalitet", "Når telefonen ikke har sendt et GPS-fix i 15 minutter, markeres data som forældede. Aktive ture og bevægelsesstatus nulstilles uden at opfinde en afsluttet tur. Eventuelle GPS-advarsler aktiveres separat i Administration."]);
    for(const [heading,body] of items) {
      const box = document.createElement("section");box.className="tf-person";
      const h = document.createElement("strong");h.textContent=heading;
      const p = document.createElement("p");p.textContent=body;
      box.append(h,p);root.appendChild(box);
    }
    const mobile=document.createElement("section");
    mobile.className="tf-person";
    const mobileTitle=document.createElement("h3");
    mobileTitle.textContent="Companion-handlinger til telefonen";
    mobile.appendChild(mobileTitle);
    const guide=document.createElement("p");
    guide.textContent="Tilføj en Action Button-widget i Companion på Android, vælg Kald tjeneste og indsæt én af tjenesterne. Slå gerne Kræv godkendelse til for SOS.";
    mobile.appendChild(guide);
    for(const [name,entity] of [
      ["Check-in", "tiny_family.mobile_checkin"],
      ["På vej hjem", "tiny_family.mobile_heading_home"],
      ["SOS", "tiny_family.mobile_sos"],
      ["Besked", "tiny_family.mobile_message"]
    ]) {
      const line=document.createElement("div");line.className="tf-fields";
      const code=document.createElement("code");
      code.textContent=name+": "+entity;line.appendChild(code);
      const copy=document.createElement("button");copy.type="button";
      copy.textContent="Kopiér tjeneste";
      copy.addEventListener("click",async()=>{
        try {
          await navigator.clipboard.writeText(entity);
          copy.textContent="Kopieret";
        }catch(error){this.message("Kopiér tjenesten manuelt: "+entity,true);}
      });
      line.appendChild(copy);mobile.appendChild(line);
    }
    const slug=this._viewerPerson?.startsWith("person.")
      ? this._viewerPerson.slice("person.".length):"din_person";
    const examples=[
      ["Android: Entity State-widget","sensor.tiny_family_"+slug+"_movement"],
      ["Android: GPS-fix alder","sensor.tiny_family_"+slug+"_gps_age_minutes"],
      ["Android: opladningsstatus","binary_sensor.tiny_family_"+slug+"_charging"],
      ["Android: destination","sensor.tiny_family_"+slug+"_destination"],
      ["Android: Template-widget",
       "{{ states('sensor.tiny_family_"+slug+"_distance_today') }} km · "+
       "{{ states('sensor.tiny_family_"+slug+"_movement') }}"],
      ["iOS: Open Page / sidepanel","/tiny-family"]
    ];
    const mobileMore=document.createElement("h3");
    mobileMore.textContent="Flere Companion-widgets og genveje";
    mobile.appendChild(mobileMore);
    const mobileInfo=document.createElement("p");
    mobileInfo.textContent="Android: Tilføj en Home Assistant Companion-widget på telefonens startskærm og vælg Entity State eller Template. iOS: Brug Companion-widgeten Open Page eller en Genvej, som åbner /tiny-family. Kopiér værdierne herunder.";
    mobile.appendChild(mobileInfo);
    for(const [label,value] of examples){
      const wrapper=document.createElement("section");
      wrapper.className="tf-person";
      const title=document.createElement("strong");title.textContent=label;
      const content=document.createElement("code");
      content.textContent=value;
      const button=document.createElement("button");
      button.type="button";button.textContent="Kopiér";
      button.addEventListener("click",async()=>{
        try{await navigator.clipboard.writeText(value);button.textContent="Kopieret";}
        catch(error){this.message("Kopiér værdien manuelt: "+value,true);}
      });
      wrapper.append(title,content,button);mobile.appendChild(wrapper);
    }
    const limitation=document.createElement("p");
    limitation.className="tf-message";
    limitation.textContent="Telefonens widgets og systemtilladelser oprettes ikke automatisk. Det kræver handling i den officielle Companion-app på hver telefon.";
    mobile.appendChild(limitation);
    root.appendChild(mobile);
  }

  async contact(root) {
    root.classList.add("tf-messages-view");
    const heading = document.createElement("h2");
    heading.textContent = "Beskeder";
    root.appendChild(heading);
    const info = document.createElement("p");
    info.className="tf-screen-intro";
    info.textContent = "Skriv til familien, giv besked om at du er på vej, eller send en SOS-hjælpanmodning.";
    root.appendChild(info);

    const note = document.createElement("p");
    note.className = "tf-message";
    note.setAttribute("role", "status");
    root.appendChild(note);
    const form = document.createElement("form");
    form.className = "tf-person";
    const input = document.createElement("textarea");
    input.maxLength = 500; input.rows = 2;
    input.placeholder = "Skriv en besked ...";
    input.setAttribute("aria-label","Besked");
    input.style.cssText = "width:100%;box-sizing:border-box;padding:10px;font:inherit;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:10px";
    form.appendChild(input);
    const includePositionLabel=document.createElement("label");
    const includePositionCheckbox=document.createElement("input");
    includePositionCheckbox.type="checkbox";
    includePositionCheckbox.checked=true;
    includePositionLabel.append(includePositionCheckbox,document.createTextNode(
      " Medtag frisk GPS-position ved Check-in, På vej hjem og SOS"));
    form.appendChild(includePositionLabel);
    const recipientLabel = document.createElement("label");
    recipientLabel.textContent = "Modtager";
    recipientLabel.className = "tf-contact-recipient";
    const recipientSelect = document.createElement("select");
    recipientSelect.setAttribute("aria-label", "Beskedmodtager");
    const everyone = document.createElement("option");
    everyone.value = "";everyone.textContent = "Hele familien";
    recipientSelect.appendChild(everyone);
    recipientLabel.appendChild(recipientSelect);
    form.appendChild(recipientLabel);
    const channelLabel=document.createElement("label");
    channelLabel.className="tf-contact-recipient";
    channelLabel.textContent="Send besked til";
    const channelSelect=document.createElement("select");
    channelSelect.setAttribute("aria-label","Beskedkanal");
    for(const [id,name] of [["phone","Telefon (push)"],["speaker","Smart speaker (dansk oplæsning)"]]){
      const option=document.createElement("option");
      option.value=id;option.textContent=name;channelSelect.appendChild(option);
    }
    channelLabel.appendChild(channelSelect);
    form.appendChild(channelLabel);
    // The HA panel may be remounted mid-typing. A per-user, per-tab draft
    // preserves the unfinished message without sending it to the server.
    const composeDraft=this.readDraft("contact-compose")||{};
    input.value=composeDraft.message||"";
    if(typeof composeDraft.includePosition==="boolean")
      includePositionCheckbox.checked=composeDraft.includePosition;
    if(composeDraft.channel==="speaker")channelSelect.value="speaker";
    let pendingRecipient=composeDraft.recipient||"";
    const saveComposeDraft=()=>this.writeDraft("contact-compose",{
      message:input.value,includePosition:includePositionCheckbox.checked,
      recipient:recipientSelect.value||pendingRecipient,
      channel:channelSelect.value
    });
    form.addEventListener("input",saveComposeDraft);
    form.addEventListener("change",saveComposeDraft);
    const channelNotice=document.createElement("p");
    channelNotice.className="tf-message";
    channelNotice.textContent="Oplæsning kan høres af andre i rummet og kræver én navngiven modtager med højttaler og dansk TTS.";
    form.appendChild(channelNotice);
    let recipientChannels=new Map();
    const syncChannel=()=>{
      const recipient=recipientSelect.value;
      const allowed=recipientChannels.get(recipient)||{};
      channelSelect.querySelector('option[value="speaker"]').disabled=!recipient||!allowed.speaker_available;
      if(channelSelect.value==="speaker" && (!recipient||!allowed.speaker_available))
        channelSelect.value="phone";
    };
    channelSelect.addEventListener("change",()=>{
      if(channelSelect.value==="speaker" && !recipientSelect.value){
        channelSelect.value="phone";
        note.textContent="Vælg en bestemt person, før du sender en oplæst besked.";
      }
    });
    const actions = document.createElement("div");
    actions.className = "tf-contact-actions";
    const ids = [
      ["message","Send besked"], ["checkin","Check-in: Jeg er okay"],
      ["heading_home","På vej hjem"], ["sos","SOS – bed om hjælp"]
    ];
    const buttons = [];
    const deliveryDetails=document.createElement("details");
    deliveryDetails.className="tf-person tf-map-tools";
    deliveryDetails.setAttribute("aria-label","Information om levering");
    const deliverySummary=document.createElement("summary");
    deliverySummary.textContent="Om levering og læsekvitteringer";
    deliveryDetails.appendChild(deliverySummary);
    const deliveryLegend=document.createElement("p");
    deliveryLegend.className="tf-message";
    deliveryLegend.textContent="1. Accepteret: Home Assistant-notifikationstjenesten har modtaget anmodningen. 2. Leveret: telefonens faktiske modtagelse kan ikke bekræftes. 3. Læst: kun når modtageren aktivt markerer beskeden som læst i Tiny Family.";
    deliveryDetails.appendChild(deliveryLegend);
    const retry=document.createElement("button");
    retry.type="button";retry.className="tf-save";
    retry.textContent="Prøv sidste afsendelse igen";
    retry.hidden=true;
    let retryPayload=null;
    const setRetry=(payload)=>{
      retryPayload=payload;
      retry.hidden=!payload;
    };
    const send=async(payload)=>{
      buttons.forEach(b=>b.button.disabled=true);
      retry.disabled=true;
      note.textContent="Sender anmodning til Home Assistant…";
      try {
        const result=await this.hassInstance.callApi("POST","tiny_family/communications",payload);
        const accepted=Number(result.recipients_sent)||0;
        const failed=Number(result.recipients_failed)||0;
        const positionText=result.location_status==="included"?" · Frisk position medtaget.":
          result.location_status==="unavailable"?" · Ingen frisk GPS: sendt uden position.":
          result.location_status==="withheld"?" · Position udeladt efter dine privatlivsvalg.":"";
        note.textContent=result.delivery_channel==="speaker"
          ?"Home Assistant accepterede oplæsning på modtagerens smart speaker. Faktisk afspilning kan ikke bekræftes."
          :"HA-notifikationstjenesten accepterede "+accepted+
          " af "+(Number(result.attempted_recipients)||accepted+failed)+
          " modtager(e)."+(failed?" "+failed+" kunne ikke accepteres.":"")+
          positionText+" Telefonlevering kan ikke verificeres. En læsekvittering kræver handling i Tiny Family.";
        setRetry(null);
        if(payload.action==="message" && accepted>0 && input.value===payload.message){
          input.value="";
          saveComposeDraft();
        }
        try{await loadHistory();}catch(historyError){
          note.textContent+=" Beskedhistorikken kunne ikke opdateres.";
        }
      }catch(error){
        note.textContent="Afsendelsen blev ikke bekræftet: "+this.errorText(error)+
          " Tekst og modtagervalg er bevaret. Ved netværksfejl kan anmodningen allerede være accepteret.";
        const code=error?.body?.error_code||error?.error_code;
        setRetry(["invalid_action","invalid_recipient","not_linked"].includes(code)?null:payload);
      }finally{
        buttons.forEach(b=>b.button.disabled=false);
        retry.disabled=false;
      }
    };
    retry.addEventListener("click",async()=>{
      if(!retryPayload)return;
      if(!window.confirm("Forsøger du igen, kan modtageren få beskeden to gange, hvis det forrige svar gik tabt. Vil du sende på ny?"))return;
      const payload={...retryPayload};
      setRetry(null);
      await send(payload);
    });
    for (const [action,title] of ids) {
      const button=document.createElement("button");
      button.type="button";button.className="tf-save";
      button.textContent=title;
      if(action==="sos")button.style.background="var(--error-color,#c62828)";
      actions.appendChild(button);buttons.push({button,action});
      button.addEventListener("click",async()=>{
        if(action==="sos" && !window.confirm(
          "Send en SOS-hjælpanmodning? Tiny Family er ikke en nødopkaldstjeneste. Positionen medtages kun hvis den er frisk og tilladt."))return;
        const payload={
          action,message:action==="message"?input.value:"",
          include_location:includePositionCheckbox.checked,
          ...(action==="message"?{channel:channelSelect.value}:{}),
          ...(action==="message" && recipientSelect.value?
              {recipient_person:recipientSelect.value}:{})
        };
        setRetry(null);
        await send(payload);
      });
    }
    form.appendChild(actions);
    form.appendChild(retry);
    form.appendChild(deliveryDetails);
    const shortcuts=document.createElement("div");
    shortcuts.style.cssText="display:flex;gap:6px;flex-wrap:wrap";
    for(const phrase of ["👋 Hej", "📍 Hvor er du?", "🚗 På vej", "🏡 Er snart hjemme", "📞 Ring til mig"]){
      const shortcut=document.createElement("button");
      shortcut.type="button";shortcut.textContent=phrase;
      shortcut.style.cssText="padding:7px 10px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);border-radius:10px";
      shortcut.addEventListener("click",()=>{
        input.value=phrase;input.focus();saveComposeDraft();
      });
      shortcuts.appendChild(shortcut);
    }
    const shortcutsPanel=document.createElement("details");
    shortcutsPanel.className="tf-advanced";
    const shortcutsHeading=document.createElement("summary");
    shortcutsHeading.textContent="Hurtige beskeder";
    shortcutsPanel.append(shortcutsHeading,shortcuts);
    form.appendChild(shortcutsPanel);root.appendChild(form);
    recipientSelect.addEventListener("change",()=>{
      syncChannel();
      for(const {button,action} of buttons){
        if(action==="message")button.disabled=false;
      }
    });
    const warning = document.createElement("p");
    warning.className="tf-message";
    warning.textContent="SOS er en frivillig beskedfunktion, ikke en certificeret alarmtjeneste eller erstatning for 112.";
    root.appendChild(warning);
    const title = document.createElement("h3");title.textContent="Din beskedhistorik";root.appendChild(title);
    const history = document.createElement("div");root.appendChild(history);
    const clear=document.createElement("button");
    clear.type="button";clear.textContent="Ryd min beskedvisning";
    clear.style.cssText="margin-top:12px;color:var(--error-color);border:1px solid var(--divider-color);background:transparent;padding:10px;border-radius:10px";
    root.appendChild(clear);
    // Compose and inbox occupy one mobile screen at a time; neither view
    // loses its state when switching between them.
    const messageNav=document.createElement("nav");
    messageNav.className="tf-screen-nav";
    messageNav.setAttribute("aria-label","Beskedvisning");
    root.insertBefore(messageNav,form);
    const composePane=document.createElement("section");
    composePane.className="tf-screen-panel";
    root.insertBefore(composePane,form);
    composePane.append(form,warning);
    const inboxPane=document.createElement("section");
    inboxPane.className="tf-screen-panel";
    root.appendChild(inboxPane);
    inboxPane.append(title,history,clear);
    const messageViews=[
      {key:"compose",title:"Skriv besked",pane:composePane},
      {key:"inbox",title:"Indbakke",pane:inboxPane}
    ];
    const selectMessages=key=>{
      for(const option of messageViews){
        option.pane.hidden=option.key!==key;
        option.button.setAttribute("aria-pressed",String(option.key===key));
      }
    };
    for(const option of messageViews){
      const button=document.createElement("button");
      button.type="button";button.textContent=option.title;
      button.addEventListener("click",()=>selectMessages(option.key));
      option.button=button;messageNav.appendChild(button);
    }
    selectMessages("compose");
    clear.addEventListener("click",async()=>{
      if(!window.confirm("Vil du skjule alle beskeder i din egen historik? De andre deltagere beholder deres kopier."))return;
      clear.disabled=true;
      try{
        await this.hassInstance.callApi("DELETE","tiny_family/communications");
        note.textContent="Din beskedhistorik er ryddet.";
        await loadHistory();
      }catch(error){note.textContent="Kunne ikke rydde: "+error.message;}
      finally{clear.disabled=false;}
    });
    const loadHistory = async () => {
      try {
        const response = await this.hassInstance.callApi("GET","tiny_family/communications");
        const prior = pendingRecipient||recipientSelect.value;
        pendingRecipient="";
        recipientChannels=new Map((response.recipients||[]).map(person=>[person.person,person]));
        recipientSelect.replaceChildren(everyone);
        for (const person of response.recipients || []) {
          const option = document.createElement("option");
          option.value = person.person;option.textContent = person.name;
          recipientSelect.appendChild(option);
        }
        if ([...recipientSelect.options].some(option=>option.value===prior)) {
          recipientSelect.value = prior;
        }else if(prior){
          note.textContent="Den gemte modtager er ikke længere tilgængelig. Vælg en ny modtager.";
          for(const {button,action} of buttons){
            if(action==="message")button.disabled=true;
          }
        }
        syncChannel();
        note.textContent = note.textContent || (response.recipients_configured ?
          "Klar til at kontakte "+response.recipients_configured+" tilknyttet(e) telefonmodtager(e)." :
          "Ingen andre telefonmodtagere er konfigureret. Administrator skal vælge Companion-modtagere i Administration.");
        if(this._composeRecipient){
          const chosen=this._composeRecipient;
          this._composeRecipient=null;
          if([...recipientSelect.options].some(option=>option.value===chosen)){
            recipientSelect.value=chosen;
            input.focus();
            syncChannel();
            saveComposeDraft();
          }else{
            note.textContent="Den valgte person har ingen tilknyttet beskedmodtager. Kontakt administrator i Administration.";
            // Never fall back to 'everyone' when direct messaging was requested.
            recipientSelect.value="";
            for(const {button,action} of buttons){
              if(action==="message")button.disabled=true;
            }
          }
        }
        history.replaceChildren();
        for(const item of response.history || []) {
          const box = document.createElement("section");
          box.className = "tf-person";
          const label = document.createElement("strong");
          label.textContent = (item.kategori || "Besked") + " · " + (item.tid || "");
          const body = document.createElement("p");
          body.textContent = item.tekst || "";
          box.append(label,body);
          if(item.fra === response.person){
            const delivery=document.createElement("span");
            delivery.className="tf-chip";
            const accepted=item.accepted_recipients ?? item.recipient_count ?? 0;
            const rejected=item.failed_recipients ?? 0;
            delivery.textContent="HA accepterede "+accepted+
              (rejected?" · "+rejected+" fejlede":"")+
              " · Telefonlevering ukendt";
            box.appendChild(delivery);
          }
          if (item.fra === response.person && typeof item.recipient_count === "number") {
            const receipt = document.createElement("p");
            receipt.className="tf-message";
            receipt.textContent="Markeret som læst i Tiny Family: "+item.read_count+" af "+item.recipient_count+
              " modtagere (ikke telefonens pushkvittering).";
            box.appendChild(receipt);
          }
          if(item.fra !== response.person && item.id && !item.read_by_me) {
            const acknowledge = document.createElement("button");
            acknowledge.type="button";acknowledge.textContent="Markér som læst";
            acknowledge.className="tf-save";
            acknowledge.addEventListener("click", async()=>{
              acknowledge.disabled=true;
              try {
                await this.hassInstance.callApi("POST","tiny_family/communications",{
                  action:"acknowledge",message_id:item.id
                });
                await loadHistory();
              } catch(error) {
                note.textContent="Kunne ikke kvittere for læsning: "+(error.message||String(error));
                acknowledge.disabled=false;
              }
            });
            box.appendChild(acknowledge);
          } else if(item.fra !== response.person && item.read_by_me) {
            const read = document.createElement("span");
            read.className="tf-message";read.textContent="Markeret som læst i Tiny Family";
            box.appendChild(read);
          }
          if(item.fra && item.fra!==response.person &&
             [...recipientSelect.options].some(o=>o.value===item.fra)){
            const reply=document.createElement("button");
            reply.type="button";reply.textContent="Svar";
            reply.style.cssText="justify-self:start;padding:7px 14px;border:1px solid var(--divider-color);border-radius:10px;color:var(--primary-text-color);background:var(--card-background-color)";
            reply.addEventListener("click",()=>{
              recipientSelect.value=item.fra;
              syncChannel();
              selectMessages("compose");
              input.focus();
              note.textContent="Svar sendes kun til "+item.fra+".";
              saveComposeDraft();
            });
            box.appendChild(reply);
          }
          history.appendChild(box);
        }
        if(!history.children.length){
          const empty=document.createElement("p");empty.className="tf-empty";
          empty.textContent="Ingen beskeder endnu. Hvis du ikke kan sende, skal administrator tilknytte telefonmodtagere i Administration.";
          history.appendChild(empty);
        }
      } catch(error) {
        note.textContent = "Beskeder kunne ikke indlæses: "+this.errorText(error)+
          ". Kontroller din person- og telefonbinding i Administration.";
      }
    };
    await loadHistory();
  }

  editor(root) {
    if (!this.settings.editable) { root.textContent = "Kun administratorer kan ændre indstillinger."; return; }
    const adminHeading=document.createElement("div");adminHeading.className="tf-admin-head";
    const adminIcon=document.createElement("ha-icon");adminIcon.setAttribute("icon","mdi:shield-crown");
    const heading=document.createElement("h2");heading.textContent="Administration – Tiny Family";
    adminHeading.append(adminIcon,heading);root.appendChild(adminHeading);
    const info=document.createElement("p");info.className="tf-message";
    info.textContent="Administrationen samler familiens telefoner, sensorer, notifikationer, fartgrænser, datalagring og zoner. Telefonens sensorer anvendes kun, når administrator har valgt dem, og Companion-appen sender dem.";
    root.appendChild(info);
    const zoneTools=document.createElement("button");
    zoneTools.type="button";zoneTools.className="tf-save";
    zoneTools.textContent="Åbn administratorværktøjer til zoner og polygoner på familiekortet";
    zoneTools.addEventListener("click",()=>this.show("live"));
    root.appendChild(zoneTools);
    const placeTools=document.createElement("button");
    placeTools.type="button";placeTools.className="tf-save";
    placeTools.textContent="Se alle familiens indlærte destinationer og ophold";
    placeTools.addEventListener("click",()=>this.show("places"));
    root.appendChild(placeTools);
    const form = document.createElement("form");
    const autoLabel=document.createElement("label");
    autoLabel.className="tf-person";
    const autoNotifications=document.createElement("input");
    autoNotifications.type="checkbox";
    autoNotifications.checked=Boolean(this.settings.auto_notifications_enabled);
    autoLabel.append(autoNotifications,document.createTextNode(
      " Send administratorvalgte hændelser og advarsler til tilknyttede telefoner"));
    form.appendChild(autoLabel);
    const alertCategoryNames = {
      zone_arrived:"Ankomst", zone_departed:"Afgang",
      battery_low:"Lavt batteri", battery_saver_warning:"Batterisparer over 30 % (kun egen telefon)",
      speed_warning:"Høj fart",
      trip_ended:"Afsluttet tur", weekly_summary:"Ugerapport",
      tracking_stale:"GPS-opdatering mangler", tracking_restored:"GPS igen aktiv"
    };
    const enabledEvents = new Set(this.settings.notification_events || Object.keys(alertCategoryNames));
    const alertOptions = {};
    const categoryBox=document.createElement("section");
    categoryBox.className="tf-person";
    const categoryHeading=document.createElement("strong");
    categoryHeading.textContent="Vælg automatiske notifikationer";
    categoryBox.appendChild(categoryHeading);
    const alertHelp=document.createElement("p");
    alertHelp.className="tf-message";
    alertHelp.textContent="Notifikationer styres af administrator og kræver en gyldig Companion-modtager. Advarslen om batterisparer sendes kun til telefonens egen bruger, når den er aktiv over 30 %; den gentages ikke inden for seks timer. Fartadvarsler kræver to troværdige målinger. Et event garanterer ikke pushlevering.";
    categoryBox.appendChild(alertHelp);
    for(const [key, label] of Object.entries(alertCategoryNames)){
      const labelElement=document.createElement("label");
      const checkbox=document.createElement("input");
      checkbox.type="checkbox";checkbox.checked=enabledEvents.has(key);
      alertOptions[key]=checkbox;
      labelElement.append(checkbox,document.createTextNode(" "+label));
      categoryBox.appendChild(labelElement);
    }
    form.appendChild(categoryBox);
    const speedLabel=document.createElement("label");
    speedLabel.className="tf-person";
    speedLabel.textContent="Fartgrænse for advarsel (km/t)";
    const speedLimit=document.createElement("input");
    speedLimit.type="number";speedLimit.min="30";speedLimit.max="200";speedLimit.step="1";
    speedLimit.required=true;
    speedLimit.value=String(this.settings.speed_limit_kmh ?? 130);
    speedLabel.appendChild(speedLimit);
    const speedHint=document.createElement("span");
    speedHint.className="tf-message";
    speedHint.textContent="Fælles standard. Hver person kan få egen grænse nedenfor. Advarsel kræver to troværdige GPS-målinger.";
    speedLabel.appendChild(speedHint);
    form.appendChild(speedLabel);
    const retentionLabel=document.createElement("label");
    retentionLabel.className="tf-person";
    retentionLabel.textContent="Gem tidslinjer i antal dage (30–3650)";
    const retentionDays=document.createElement("input");
    retentionDays.type="number";retentionDays.min="30";retentionDays.max="3650";
    retentionDays.step="1";retentionDays.required=true;
    retentionDays.value=String(this.settings.timeline_retention_days??365);
    retentionLabel.appendChild(retentionDays);
    const retentionHint=document.createElement("span");retentionHint.className="tf-message";
    retentionHint.textContent="Standard: 365 dage. Ændres perioden til færre dage, slettes ældre GPS-punkter og turhændelser automatisk ved næste indlæsning. Det kan ikke fortrydes.";
    retentionLabel.appendChild(retentionHint);
    form.appendChild(retentionLabel);
    const routinesLabel=document.createElement("label");
    routinesLabel.className="tf-person";
    const routineLearning=document.createElement("input");
    routineLearning.type="checkbox";
    routineLearning.checked=Boolean(this.settings.learn_routines_enabled);
    routinesLabel.append(routineLearning,document.createTextNode(
      " Aktivér lokal rutineindlæring. Kun administrator vælger aktive familiemedlemmer nedenfor; de øvrige kan ikke slå det til eller fra."));
    form.appendChild(routinesLabel);
    const mapMatchPanel=document.createElement("details");
    mapMatchPanel.className="tf-person tf-advanced tf-osrm-setting";
    const mapMatchTitle=document.createElement("summary");
    mapMatchTitle.textContent="Vejtilpasning / Snap-on-road";
    mapMatchPanel.appendChild(mapMatchTitle);
    const mapMatchLabel=document.createElement("label");
    const mapMatchEnabled=document.createElement("input");
    mapMatchEnabled.type="checkbox";
    mapMatchEnabled.checked=Boolean(this.settings.map_matching_enabled);
    mapMatchLabel.append(mapMatchEnabled,document.createTextNode(
      " Tilpas nye og gamle tidslinjer til veje, når datoen vises (slået til som standard; administrator kan ændre)"));
    const mapMatchBackendLabel=document.createElement("label");
    mapMatchBackendLabel.textContent="Vejmotor";
    const mapMatchBackend=document.createElement("select");
    for(const [id,label] of [
      ["builtin","Indbygget OpenStreetMap-vejtilpasning (ingen OSRM)"],
      ["osrm","Ekstern / selvhostet OSRM Match-server"]
    ]){
      const option=document.createElement("option");
      option.value=id;option.textContent=label;mapMatchBackend.appendChild(option);
    }
    mapMatchBackend.value=this.settings.map_matching_backend||
      (this.settings.map_matching_url?"osrm":"builtin");
    mapMatchBackendLabel.appendChild(mapMatchBackend);
    const mapMatchUrlLabel=document.createElement("label");
    mapMatchUrlLabel.textContent="OSRM-server (kun ved valg af OSRM)";
    const mapMatchUrl=document.createElement("input");
    mapMatchUrl.type="url";
    mapMatchUrl.placeholder="http://192.168.1.20:5000";
    mapMatchUrl.maxLength=240;
    mapMatchUrl.value=this.settings.map_matching_url||"";
    mapMatchUrlLabel.appendChild(mapMatchUrl);
    const mapMatchNote=document.createElement("p");
    mapMatchNote.className="tf-message";
    const updateMapBackend=()=>{
      mapMatchUrlLabel.hidden=mapMatchBackend.value!=="osrm";
      mapMatchNote.textContent=mapMatchBackend.value==="builtin"
        ?"Indbygget vejtilpasning kræver ingen OSRM-server. Når en gammel eller ny dato åbnes, hentes vejgeometri fra OpenStreetMap Overpass via HTTPS. Kun et geografisk udsnit (ikke person-id eller GPS-tidspunkter) sendes ud. Match lagres lokalt pr. dato, og originale GPS-spor ændres aldrig."
        :"OSRM er valgfrit og kan være selvhostet. Når en dato åbnes, sender Tiny Family dens synlige GPS-koordinater og tidspunkter til den angivne server. Vejtilpasningen lagres lokalt. Brug helst en lokal server af hensyn til privatlivet.";
    };
    mapMatchBackend.addEventListener("change",updateMapBackend);
    updateMapBackend();
    mapMatchPanel.append(mapMatchLabel,mapMatchBackendLabel,mapMatchUrlLabel,mapMatchNote);
    form.appendChild(mapMatchPanel);
    const rows = [];
    const memberSections=[];
    for (const person of this.settings.available_persons || []) {
      const section = document.createElement("details");
      section.className = "tf-person tf-member-settings";
      section.dataset.personId=person.id;
      const personSummary=document.createElement("summary");
      personSummary.className="tf-member-summary";
      const memberStatus=document.createElement("span");
      memberStatus.className="tf-chip";
      personSummary.append(document.createTextNode(person.name),memberStatus);
      section.appendChild(personSummary);
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = (this.settings.persons || []).includes(person.id);
      const statusMember=()=>memberStatus.textContent=checkbox.checked?"● Aktiv":"○ Ikke tilføjet";
      checkbox.addEventListener("change",statusMember);statusMember();
      label.append(checkbox, document.createTextNode(" Medtag i Tiny Family"));
      section.appendChild(label);
      const fields = document.createElement("div");
      fields.className = "tf-fields";
      const choice = (name, items, current, container=fields) => {
        const wrap = document.createElement("label");
        wrap.appendChild(document.createTextNode(name));
        const select = document.createElement("select");
        const blank = document.createElement("option");
        blank.value = ""; blank.textContent = "Ingen / automatisk"; select.appendChild(blank);
        for (const item of items) {
          const option = document.createElement("option");
          option.value = item.id; option.textContent = item.name; select.appendChild(option);
        }
        select.value = current || "";
        wrap.appendChild(select);container.appendChild(wrap);
        return select;
      };
      const tracker = choice("Telefon (Home Assistant Companion / GPS)", this.settings.available_trackers || [], this.settings.trackers?.[person.id]);
      const detected=document.createElement("p");
      detected.className="tf-message";fields.appendChild(detected);
      const sensorPanel=document.createElement("section");
      sensorPanel.className="tf-person";
      const sensorHeading=document.createElement("strong");
      sensorHeading.textContent="Sensorer administrator kræver fra telefonen";
      sensorPanel.appendChild(sensorHeading);
      const gpsState=document.createElement("p");gpsState.className="tf-message";
      gpsState.textContent="GPS/position: altid påkrævet i Tiny Family (kan ikke slås fra her).";
      sensorPanel.appendChild(gpsState);
      const sensorKeys={battery:"Batteriniveau",charging:"Opladning",activity:"Bevægelsesaktivitet",power_save:"Batterisparetilstand / GPS-kvalitet"};
      const sensors={};
      const enabledSensors=new Set(this.settings.phone_sensor_selection?.[person.id]??Object.keys(sensorKeys));
      for(const [key,title] of Object.entries(sensorKeys)){
        const label=document.createElement("label");
        const checked=document.createElement("input");
        checked.type="checkbox";checked.checked=enabledSensors.has(key);
        sensors[key]=checked;
        const status=document.createElement("span");status.dataset.sensorStatus=key;
        label.append(checked,document.createTextNode(" "+title+" · "),status);
        sensorPanel.appendChild(label);
      }
      const sensorHelp=document.createElement("p");sensorHelp.className="tf-message";
      sensorHelp.textContent="Tilladelser alene aktiverer ikke sensorens kontakt i Companion-appen. Hvis noget mangler: Telefon → Home Assistant → Indstillinger → Companion-app → Administrer sensorer. Kontroller også HA-enhedsregistret. Tiny Family kan ikke tænde de lokale appkontakter eksternt.";
      sensorPanel.appendChild(sensorHelp);fields.appendChild(sensorPanel);
      const routineOption=document.createElement("label");
      const personRoutine=document.createElement("input");personRoutine.type="checkbox";
      personRoutine.checked=(this.settings.routine_learning_people||[]).includes(person.id);
      routineOption.append(personRoutine,document.createTextNode(" Administrator: lær typiske afgangstider for denne person"));
      fields.appendChild(routineOption);
      // The selected Companion phone owns every sensor binding.
      // No independent battery/activity drop-downs: the backend resolves
      // them from the very same HA device registry entry.
      const battery={value:""},charging={value:""},activity={value:""},powerSave={value:""};
      const refreshPhone=()=>{
        const auto=this.settings.device_sensors?.[tracker.value]||{};
        const inventory=this.settings.phone_sensor_inventory?.[tracker.value]||{};
        battery.value=auto.battery||"";
        charging.value=auto.charging||"";
        activity.value=auto.activity||"";
        powerSave.value=auto.power_save||"";
        const descriptions={ready:"aktiv",unavailable:"ingen opdatering",disabled_in_ha:"deaktiveret i HA",missing:"mangler i Companion"};
        for(const key of Object.keys(sensors)){
          const slot=sensorPanel.querySelector('[data-sensor-status="'+key+'"]');
          if(slot)slot.textContent=sensors[key].checked
            ?(descriptions[inventory[key]?.status]||"mangler")
            :"fravalgt af administrator";
        }
        const found=Object.keys(auto).filter(key=>auto[key]);
        detected.textContent=tracker.value
          ?found.length
            ?"Sensorer fra denne telefon: "+found.map(key=>({
                battery:"batteri",charging:"opladning",activity:"aktivitet",power_save:"batterisparer"
              })[key]||key).join(", ")
            :"Ingen Companion-sensorer fundet på telefonen. Aktivér dem i Home Assistant Companion."
          :"Vælg telefonen én gang. GPS og tilgængelige sensorer tilknyttes automatisk.";
      };
      tracker.addEventListener("change",refreshPhone);
      for(const checkbox of Object.values(sensors))checkbox.addEventListener("change",refreshPhone);
      refreshPhone();
      const colorLabel = document.createElement("label");colorLabel.textContent = "Farve";
      const color = document.createElement("input");color.type="color";color.value=this.settings.colors?.[person.id]||"#00a8a9";
      colorLabel.appendChild(color);fields.appendChild(colorLabel);
      section.appendChild(fields);
      const memberDiary=document.createElement("details");
      memberDiary.className="tf-person tf-person-diary";
      const diarySummary=document.createElement("summary");
      diarySummary.textContent="Administrator: personhistorik i tekst ("+
        (this.settings.timeline_retention_days??365)+" dage)";
      memberDiary.appendChild(diarySummary);
      memberDiary.addEventListener("toggle",()=>{
        if(memberDiary.open && !memberDiary.dataset.loaded){
          memberDiary.dataset.loaded="1";
          void this.dailyReport(memberDiary,{view:"editor",fixedPerson:person.id});
        }
      });
      section.appendChild(memberDiary);
      form.appendChild(section);
      memberSections.push(section);
      const owner = choice("Home Assistant-bruger", this.settings.available_users || [],
                           this.settings.owners?.[person.id]);
      const target = choice("Companion push-modtager", this.settings.available_notify_targets || [],
                            this.settings.notification_targets?.[person.id]);
      const speaker = choice("Smart speaker i personens rum (valgfri)",
                             this.settings.available_speakers || [],
                             this.settings.smart_speakers?.[person.id]);
      const ttsEngine = choice("Dansk TTS-stemme (vælg sammen med smart speaker)",
                               this.settings.available_tts_engines || [],
                               this.settings.tts_engines?.[person.id]);
      const personSpeedLabel=document.createElement("label");
      personSpeedLabel.textContent="Personlig fartgrænse (km/t; tom = fælles)";
      const personSpeed=document.createElement("input");
      personSpeed.type="number";personSpeed.min="30";personSpeed.max="200";personSpeed.step="1";
      personSpeed.placeholder=String(this.settings.speed_limit_kmh ?? 130);
      personSpeed.value=String(this.settings.speed_limits_kmh?.[person.id] ?? "");
      personSpeedLabel.appendChild(personSpeed);fields.appendChild(personSpeedLabel);
      const personEventsBox=document.createElement("section");
      personEventsBox.className="tf-person";
      const useGlobalEvents=document.createElement("input");
      useGlobalEvents.type="checkbox";
      useGlobalEvents.checked=!Object.prototype.hasOwnProperty.call(
        this.settings.person_notification_events || {}, person.id);
      const inheritLabel=document.createElement("label");
      inheritLabel.append(useGlobalEvents,
          document.createTextNode(" Brug fælles notifikationsvalg"));
      personEventsBox.appendChild(inheritLabel);
      const individualEvents={};
      const ownEvents = new Set(this.settings.person_notification_events?.[person.id] ??
                                this.settings.notification_events ?? Object.keys(alertCategoryNames));
      for (const [eventName, eventLabel] of Object.entries(alertCategoryNames)) {
        const labelElement=document.createElement("label");
        const checked=document.createElement("input");
        checked.type="checkbox";checked.checked=ownEvents.has(eventName);
        checked.disabled=useGlobalEvents.checked;
        individualEvents[eventName]=checked;
        labelElement.append(checked,document.createTextNode(" "+eventLabel));
        personEventsBox.appendChild(labelElement);
      }
      useGlobalEvents.addEventListener("change",()=>{
        for (const checkbox of Object.values(individualEvents))
          checkbox.disabled=useGlobalEvents.checked;
      });
      fields.appendChild(personEventsBox);
      rows.push({person:person.id,checkbox,tracker,battery,charging,activity,powerSave,sensors,personRoutine,color,
                 owner,target,speaker,ttsEngine,personSpeed,useGlobalEvents,individualEvents,refreshPhone});
    }
    const migrateLabel=document.createElement("label");
    migrateLabel.className="tf-person";
    const migrateTitle=document.createElement("strong");
    migrateTitle.textContent="Overfør tidligere Tiny Family-opsætning";
    const migrateInfo=document.createElement("span");
    migrateInfo.textContent="Indlæs en lokal migrations-preview fra scripts/migration_preview.py. Intet gemmes før du gennemgår valgene og trykker Gem indstillinger.";
    const migrateFile=document.createElement("input");
    migrateFile.type="file";migrateFile.accept=".json,application/json";
    migrateLabel.append(migrateTitle,migrateInfo,migrateFile);
    form.appendChild(migrateLabel);
    const migrationReview=document.createElement("section");
    migrationReview.className="tf-person";migrationReview.style.display="none";
    const migrationHeading=document.createElement("strong");
    migrationHeading.textContent="Gennemgang af ældre funktioner og scripts";
    const migrationDetails=document.createElement("div");
    const migrationConfirm=document.createElement("label");
    const migrationReady=document.createElement("input");
    migrationReady.type="checkbox";
    migrationConfirm.append(migrationReady,document.createTextNode(
      " Jeg har lavet en fuld Home Assistant-backup og gennemgået de scripts, automationer og brugerbindinger, som kræver manuel migration."
    ));
    migrationReview.append(migrationHeading,migrationDetails,migrationConfirm);
    form.appendChild(migrationReview);
    let migrationPending=false;
    migrateFile.addEventListener("change",async()=>{
      const file=migrateFile.files?.[0];
      if(!file)return;
      try{
        if(file.size>1024*1024)throw new Error("Filen er for stor");
        const plan=JSON.parse(await file.text());
        if(plan?.format!=="tiny-family-migration-preview-v1" ||
           !plan.settings || !Array.isArray(plan.settings.persons)){
          throw new Error("Ugyldigt Tiny Family-migrationsformat");
        }
        const selected=new Set(plan.settings.persons);
        migrationPending=true;migrationReady.checked=false;
        migrationReview.style.display="grid";
        migrationDetails.replaceChildren();
        const summary=document.createElement("p");
        summary.textContent=(plan.script_review||[]).length+
          " identificerede scripts og "+(plan.automation_references_count||0)+
          " registrerede automationsreferencer. Ukendte !include-filer skal gennemgås særskilt.";
        migrationDetails.appendChild(summary);
        for(const feature of (plan.feature_coverage||[])){
          const line=document.createElement("p");
          line.textContent=feature.legacy+" → "+feature.new+
            " ("+(feature.mode==="built_in"?"findes i Tiny Family":
                    "kræver gennemgang")+")";
          migrationDetails.appendChild(line);
        }
        for(const script of (plan.script_review||[])){
          const line=document.createElement("p");
          line.textContent="Script "+script.id+" → forslag: "+
            script.possible_replacement+" (skal kontrolleres manuelt)";
          migrationDetails.appendChild(line);
        }
        for(const step of (plan.remaining_manual_steps||[])){
          const line=document.createElement("p");
          line.textContent="Kontrollér: "+step;
          migrationDetails.appendChild(line);
        }
        const known=new Set(rows.map(row=>row.person));
        const missing=[...selected].filter(p=>!known.has(p));
        for(const row of rows){
          row.checkbox.checked=selected.has(row.person);
          for(const [element,key] of [
            [row.tracker,"trackers"]
          ]){
            const value=plan.settings[key]?.[row.person];
            if(value && [...element.options].some(option=>option.value===value))
              element.value=value;
          }
          row.refreshPhone(false);
          const color=plan.settings.colors?.[row.person];
          if(typeof color==="string" && /^#[0-9a-fA-F]{6}$/.test(color))
            row.color.value=color;
        }
        this.message("Migreringsforslaget er indlæst. "+(
          missing.length?missing.length+" person(er) findes ikke i HA. ":"")+
          "Gennemgå brugere, telefonmodtagere og alarmregler før du gemmer.");
      }catch(error){
        this.message("Migrationsfilen blev afvist: "+error.message,true);
      }finally{migrateFile.value="";}
    });
    if (!rows.length) {
      const note = document.createElement("p");
      note.textContent = "Opret personer under Indstillinger → Personer i Home Assistant.";
      form.appendChild(note);
    }
    const erasePanel=document.createElement("section");erasePanel.className="tf-person";
    const eraseIntro=document.createElement("p");eraseIntro.className="tf-message";
    eraseIntro.textContent="Kun administrator kan slette gemte tidslinjer, turarkiv og indlærte steder. Sletningen gælder den valgte person og kan ikke fortrydes. Home Assistant Recorder og fælles HA-zoner berøres ikke.";
    const eraseSelect=document.createElement("select");
    const eraseBlank=document.createElement("option");eraseBlank.value="";
    eraseBlank.textContent="Vælg familiemedlem";eraseSelect.appendChild(eraseBlank);
    for(const p of this.settings.available_persons||[]){
      const item=document.createElement("option");item.value=p.id;item.textContent=p.name;
      eraseSelect.appendChild(item);
    }
    const eraseCounts=document.createElement("p");eraseCounts.className="tf-message";
    eraseSelect.addEventListener("change",async()=>{
      eraseCounts.textContent="";
      if(!eraseSelect.value)return;
      try{
        const data=await this.hassInstance.callApi("GET","tiny_family/personal_data?person="+
          encodeURIComponent(eraseSelect.value));
        if(data.person===eraseSelect.value)eraseCounts.textContent=
          data.routes+" GPS-punkter · "+data.activities+" turhændelser · "+data.places+" steder";
      }catch(error){eraseCounts.textContent="Kunne ikke hente antal gemte data.";}
    });
    const eraseChecks={};
    for(const [key,title] of [["routes","GPS-tidslinjer"],["activities","Tur- og opholdsarkiv"],["places","Indlærte steder"]]){
      const label=document.createElement("label");
      const checked=document.createElement("input");checked.type="checkbox";
      eraseChecks[key]=checked;
      label.append(checked,document.createTextNode(" "+title));erasePanel.appendChild(label);
    }
    const eraseButton=document.createElement("button");eraseButton.type="button";
    eraseButton.className="tf-save";eraseButton.textContent="Slet valgte data for personen";
    eraseButton.style.background="var(--error-color,#a52d2d)";
    eraseButton.addEventListener("click",async()=>{
      const person=eraseSelect.value;
      const categories=Object.keys(eraseChecks).filter(k=>eraseChecks[k].checked);
      if(!person||!categories.length){this.message("Vælg person og datatype før sletning.",true);return;}
      if(!window.confirm("Slet "+categories.join(", ")+" permanent for "+
          eraseSelect.selectedOptions[0].textContent+"? Dette kan ikke fortrydes."))return;
      eraseButton.disabled=true;
      try{
        await this.hassInstance.callApi("DELETE","tiny_family/personal_data",{
          person,categories,confirm:true
        });
        for(const input of Object.values(eraseChecks))input.checked=false;
        eraseSelect.dispatchEvent(new Event("change"));
        this.message("De valgte data er slettet af administrator.");
      }catch(error){this.message("Sletning mislykkedes: "+this.errorText(error),true);}
      finally{eraseButton.disabled=false;}
    });
    erasePanel.prepend(eraseIntro,eraseSelect,eraseCounts);
    erasePanel.appendChild(eraseButton);
    const save = document.createElement("button");
    save.type="submit";save.className="tf-save tf-admin-save";
    save.textContent="Gem indstillinger";form.appendChild(save);
    form.addEventListener("submit",async e => {
      e.preventDefault();
      if(Number(retentionDays.value)<Number(this.settings.timeline_retention_days??365) &&
         !window.confirm("Kortere lagringstid sletter ældre tidslinjer permanent ved genindlæsning. Fortsæt?"))return;
      if(rows.some(row=>row.checkbox.checked&&Boolean(row.speaker.value)!==Boolean(row.ttsEngine.value))){
        this.message("Vælg både højttaler og dansk TTS-stemme for hver person, eller lad begge være tomme.",true);
        return;
      }
      if(migrationPending && !migrationReady.checked){
        this.message("Bekræft først backup og manuel gennemgang af migrationen.",true);
        return;
      }
      save.disabled=true;this.message("Gemmer …");
      const persons=[],trackers={},batteries={},charging_sensors={},activity_sensors={},power_save_sensors={},
            phone_sensor_selection={},routine_learning_people=[],
            colors={},owners={},notification_targets={},smart_speakers={},tts_engines={},
            speed_limits_kmh={},person_notification_events={};
      for(const row of rows) if(row.checkbox.checked) {
        persons.push(row.person);
        trackers[row.person]=row.tracker.value;
        batteries[row.person]=row.battery.value;
        charging_sensors[row.person]=row.charging.value;
        activity_sensors[row.person]=row.activity.value;
        power_save_sensors[row.person]=row.powerSave.value;
        phone_sensor_selection[row.person]=Object.keys(row.sensors).filter(
          key=>row.sensors[key].checked);
        if(row.personRoutine.checked)routine_learning_people.push(row.person);
        colors[row.person]=row.color.value;
        if(row.owner.value) owners[row.person]=row.owner.value;
        if(row.target.value) notification_targets[row.person]=row.target.value;
        if(row.speaker.value) smart_speakers[row.person]=row.speaker.value;
        if(row.ttsEngine.value) tts_engines[row.person]=row.ttsEngine.value;
        if(row.personSpeed.value!=="") speed_limits_kmh[row.person]=Number(row.personSpeed.value);
        if(!row.useGlobalEvents.checked){
          person_notification_events[row.person]=
            Object.keys(row.individualEvents).filter(k=>row.individualEvents[k].checked);
        }
      }
      try {
        await this.hassInstance.callApi("POST","tiny_family/settings",{
          persons,trackers,batteries,charging_sensors,activity_sensors,power_save_sensors,
          phone_sensor_selection,timeline_retention_days:Number(retentionDays.value),
          colors,owners,notification_targets,smart_speakers,tts_engines,
          speed_limit_kmh:Number(speedLimit.value),
          speed_limits_kmh,person_notification_events,
          notification_events:Object.keys(alertOptions).filter(key=>alertOptions[key].checked),
          auto_notifications_enabled:autoNotifications.checked,
          learn_routines_enabled:routineLearning.checked,routine_learning_people,
          map_matching_enabled:mapMatchEnabled.checked,
          map_matching_backend:mapMatchBackend.value,
          map_matching_url:mapMatchUrl.value.trim()
        });
        await this.refreshSettings();
        this.clearDraft("editor");
        this.message("Ændringer gemt. Integrationen genindlæses.");
      } catch(error) { this.message("Kunne ikke gemme: "+error.message,true); }
      finally {save.disabled=false;}
    });
    // Admin settings are grouped in one compact phone-sized view, with the
    // Save control always available. This preserves all existing fields.
    root.classList.add("tf-admin-mobile");
    form.className="tf-admin-form";
    const adminGroups=document.createElement("div");
    adminGroups.className="tf-admin-groups";
    const makeGroup=(label,elements,open=false)=>{
      const panel=document.createElement("details");
      panel.className="tf-admin-group";
      panel.open=open;
      const summary=document.createElement("summary");
      summary.textContent=label;
      panel.appendChild(summary);
      for(const element of elements)panel.appendChild(element);
      adminGroups.appendChild(panel);
      return panel;
    };
    // Native Tiny Family listeners handle alerts. Legacy HA automations are
    // optional leftovers, not prerequisites for battery or speed warnings.
    const managedAlerts=document.createElement("section");
    managedAlerts.className="tf-person";
    const managedTitle=document.createElement("strong");
    managedTitle.textContent="Automatiske alarmer styres af Tiny Family";
    const managedNote=document.createElement("p");
    managedNote.className="tf-message";
    managedNote.textContent="Batteri, fart, zoner, ture og GPS-hændelser registreres direkte i Tiny Family. Ingen separate Home Assistant-automatiseringer er nødvendige. Vælg Companion-telefon og notifikationsmodtagere her; push kræver aktivering.";
    managedAlerts.append(managedTitle,managedNote);
    const legacyAlarmEntities=[
      ["automation.person_timeline_lavt_batteri","Lavt batteri"],
      ["automation.person_timeline_fartalarm","Fartalarm"]
    ];
    const detectedLegacy=legacyAlarmEntities.filter(([entityId])=>
      Object.prototype.hasOwnProperty.call(this.hassInstance?.states||{},entityId));
    if(detectedLegacy.length){
      const legacyStatus=document.createElement("p");
      legacyStatus.className="tf-message";
      legacyStatus.setAttribute("role","status");
      const describeLegacy=()=>detectedLegacy.map(([entityId,label])=>
        label+": "+(this.hassInstance.states?.[entityId]?.state||"ukendt")).join(" · ");
      legacyStatus.textContent="Tidligere Home Assistant-automatiseringer: "+describeLegacy();
      managedAlerts.appendChild(legacyStatus);
      const legacyEnabled=detectedLegacy.filter(([entityId])=>
        this.hassInstance.states?.[entityId]?.state==="on");
      if(legacyEnabled.length){
        const disableLegacy=document.createElement("button");
        disableLegacy.type="button";
        disableLegacy.className="tf-save";
        disableLegacy.textContent="Deaktiver gamle alarmer ("+legacyEnabled.length+")";
        disableLegacy.addEventListener("click",async()=>{
          const entities=legacyEnabled.map(([entityId])=>entityId);
          if(!window.confirm("Deaktivere de gamle batteri- og fartautomatiseringer? De slettes ikke. Kontrollér først dine personers sensorer og notifikationer i Tiny Family."))return;
          disableLegacy.disabled=true;
          try{
            await this.hassInstance.callService("automation","turn_off",
              {entity_id:entities});
            disableLegacy.textContent="Deaktivering sendt";
            legacyStatus.textContent="Deaktivering af gamle automatiseringer er sendt til Home Assistant. Opdater visningen for at kontrollere resultatet.";
            this.message("Tiny Family håndterer fortsat alarmer efter de gemte indstillinger.");
          }catch(error){
            disableLegacy.disabled=false;
            this.message("Kunne ikke deaktivere gamle automatiseringer: "+
              this.errorText(error),true);
          }
        });
        managedAlerts.appendChild(disableLegacy);
      }
      if(detectedLegacy.some(([entityId])=>
        this.hassInstance.states?.[entityId]?.state==="unavailable")){
        const unavailable=document.createElement("p");
        unavailable.className="tf-message";
        unavailable.textContent="En gammel automatisering er utilgængelig. Den kan ikke deaktiveres her, før Home Assistant kan indlæse den.";
        managedAlerts.appendChild(unavailable);
      }
    }
    const peopleGroup=makeGroup("Familiemedlemmer og telefoner",memberSections,true);
    const alertsGroup=makeGroup("Alarmer og fartgrænser",[
      managedAlerts,autoLabel,categoryBox,speedLabel
    ]);
    const routineGroup=makeGroup("Rutiner og samtykke",[routinesLabel]);
    const retentionGroup=makeGroup("Tidslinjer og opbevaring",[retentionLabel]);
    const eraseGroup=makeGroup("Administrator: slet data",[erasePanel]);
    const roadGroup=makeGroup("Vejtilpasning og OSRM",[mapMatchPanel]);
    mapMatchPanel.open=true;
    const migrationGroup=makeGroup("Migrering af gammel opsætning",[
      migrateLabel,migrationReview
    ]);
    const advancedGroup=makeGroup("Kortværktøjer og andre valg",[
      zoneTools,placeTools
    ]);
     for(const group of [peopleGroup,alertsGroup,routineGroup,retentionGroup,eraseGroup,roadGroup,
                        migrationGroup,advancedGroup]){
      group.addEventListener("toggle",()=>{
        if(group.open){
          for(const other of adminGroups.children){
            if(other!==group)other.open=false;
          }
        }
      });
    }
    form.replaceChildren(adminGroups,save);
    root.appendChild(form);
    // Preserve unfinished admin inputs through a panel reload/navigation.
    // Exclude destructive erasure confirmations and local uploaded files.
    erasePanel.classList.add("tf-erase-actions");
    const inputFields=()=>[...form.querySelectorAll("input,select,textarea")]
      .filter(el=>el.type!=="file"&&!el.closest(".tf-erase-actions")&&
        el!==migrationReady);
    const draftFields=inputFields();
    const keys=new Map(),memberIndexes=new Map();
    let globalIndex=0;
    for(const el of draftFields){
      const member=el.closest(".tf-member-settings");
      if(member){
        const index=memberIndexes.get(member)||0;
        keys.set(el,"member:"+member.dataset.personId+":"+index);
        memberIndexes.set(member,index+1);
      }else keys.set(el,"global:"+globalIndex++);
    }
    const fieldKey=el=>keys.get(el);
    const draft=this.readDraft("editor");
    if(draft?.fields){
      for(const el of draftFields){
        const saved=draft.fields[fieldKey(el)];
        if(!saved||saved.type!==el.type)continue;
        if(el.type==="checkbox")el.checked=saved.checked;
        else if(el.tagName==="SELECT"){
          if([...el.options].some(option=>option.value===saved.value))el.value=saved.value;
        }else if(typeof saved.value==="string")el.value=saved.value;
      }
      for(const row of rows){
        row.refreshPhone();
        row.useGlobalEvents.dispatchEvent(new Event("change"));
      }
      for(const item of [...adminGroups.children,...memberSections]){
        if(draft.open?.[item.classList.contains("tf-member-settings")
            ?"member:"+item.dataset.personId:
            "group:"+[...adminGroups.children].indexOf(item)]!==undefined){
          item.open=Boolean(draft.open[item.classList.contains("tf-member-settings")
            ?"member:"+item.dataset.personId:
            "group:"+[...adminGroups.children].indexOf(item)]);
        }
      }
      const notice=document.createElement("div");notice.className="tf-card-actions";
      const note=document.createElement("span");note.className="tf-chip";
      note.textContent="Ikke-gemte indstillinger gendannet fra denne browserfane";
      const discard=document.createElement("button");
      discard.type="button";discard.className="tf-save";
      discard.textContent="Forkast kladde";
      discard.addEventListener("click",()=>{
        this.clearDraft("editor");root.replaceChildren();this.editor(root);
        this.message("Kladde fjernet. De senest gemte indstillinger vises.");
      });
      notice.append(note,discard);root.prepend(notice);
    }
    const saveEditorDraft=()=>{
      const fields={};
      for(const el of draftFields)fields[fieldKey(el)]={
        type:el.type,value:el.value,checked:el.type==="checkbox"?el.checked:undefined
      };
      const open={};
      for(const [index,item] of [...adminGroups.children].entries())
        open["group:"+index]=item.open;
      for(const item of memberSections)open["member:"+item.dataset.personId]=item.open;
      this.writeDraft("editor",{fields,open});
    };
    form.addEventListener("input",saveEditorDraft);
    form.addEventListener("change",saveEditorDraft);
    for(const item of [...adminGroups.children,...memberSections])
      item.addEventListener("toggle",saveEditorDraft);
    const permissions=document.createElement("section");
    permissions.className="tf-person";
    const headingPermissions=document.createElement("strong");
    headingPermissions.textContent="Aktuel deling og alarmer";
    permissions.appendChild(headingPermissions);
    const overview=document.createElement("div");
    permissions.appendChild(overview);
    // Sharing details are available in the same in-page admin sections.
    root.appendChild(permissions);
    advancedGroup.appendChild(permissions);
    this.hassInstance.callApi("GET","tiny_family/sharing").then(policy=>{
      if(this.active!=="editor")return;
      overview.replaceChildren();
      for(const row of policy.family||[]){
        const item=document.createElement("p");
        const status=row.ghost_active?"Ghost aktiv":"Synlig";
        const people=row.tiny_family_location_viewers.join(", ")||"ingen";
        item.textContent=row.name+" · "+status+" · fartgrænse "+
          row.speed_alert_kmh+" km/t · Tiny Family-visning: "+people;
        overview.appendChild(item);
      }
      const note=document.createElement("p");
      note.className="tf-message";
      note.textContent="Oversigten viser gemte indstillinger. Formularens nye valg træder først i kraft, når du gemmer. Almindelige HA-entiteter og Recorder styres særskilt.";
      overview.appendChild(note);
    }).catch(error=>{
      overview.textContent="Delingsoversigten kunne ikke hentes: "+error.message;
    });
  }
}
customElements.define("tiny-family-panel", TinyFamilyPanel);
