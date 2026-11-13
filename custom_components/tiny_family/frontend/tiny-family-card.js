const PT_COMPACT_ENTITY = "switch.tiny_family_compact";
const PT_LEGACY_COMPACT_ENTITY = "input_boolean.tiny_family_kompakt";

function personTimelineCompact(hass, config) {
  const entity = hass && (hass.states[PT_COMPACT_ENTITY] || hass.states[PT_LEGACY_COMPACT_ENTITY]);
  return !!((config && config.compact === true) || (entity && entity.state === "on"));
}

function personTimelineTheme(owner, hass) {
  if (!owner || !owner.style || !owner.style.setProperty) return;
  let dark = hass && hass.themes && hass.themes.darkMode;
  if (dark === undefined) dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  owner.style.setProperty("--pt-base", dark ? "#182731" : "#f5fafc");
  owner.style.setProperty("--pt-text", dark ? "#edf5f7" : "#17333c");
  owner.style.setProperty("--pt-muted", dark ? "#b8cbd3" : "#465e68");
  owner.style.setProperty("--pt-outline", dark ? "rgba(121,216,223,.38)" : "rgba(0,125,140,.32)");
  owner.style.setProperty("--pt-neon", dark ? "#79d8df" : "#007d8c");
  owner.style.setProperty("--pt-violet", dark ? "#c6a7e9" : "#7540aa");
  owner.style.setProperty("--pt-danger", dark ? "#ff7b7b" : "#b42323");
}

const PT_NEON = `
.pt,.pte{--pt-base:#f5fafc;--pt-text:#17333c;--pt-muted:#465e68;--pt-outline:rgba(0,125,140,.32);--pt-neon:#007d8c;--pt-violet:#7540aa;--pt-danger:#b42323;--pt-surface:linear-gradient(135deg,rgba(0,229,255,.08),rgba(185,103,255,.06));--pt-glow:0 0 12px rgba(0,229,255,.12);--primary-text-color:var(--pt-text);--secondary-text-color:var(--pt-muted);--primary-color:var(--pt-neon);--accent-color:var(--pt-violet);--divider-color:var(--pt-outline);box-sizing:border-box}
.pt{border:1px solid var(--pt-outline);border-radius:18px;background:var(--pt-surface),var(--pt-base);box-shadow:var(--pt-glow);color:var(--pt-text);font-family:var(--paper-font-body1_-_font-family,inherit);padding:14px 16px}
.pt.pt-compact{padding:8px 10px;border-radius:14px}
.pt *{box-sizing:border-box}
.pt :is(button,a,input,select):focus-visible{outline:2px solid var(--pt-neon);outline-offset:3px}
.pt-titlebar{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:2px}
.pt-title{font-weight:600;font-size:15px;text-transform:uppercase;letter-spacing:.6px;text-shadow:0 0 12px rgba(0,229,255,.35)}
.pt-compact .pt-title{font-size:13px}
.pt-rule{height:2px;border-radius:2px;margin:6px 0 8px;background:linear-gradient(90deg,var(--pt-neon),var(--pt-violet));opacity:.55;box-shadow:0 0 8px rgba(0,229,255,.35)}
.pt-sub{font-size:11px;color:var(--pt-muted);margin-bottom:8px}
.pt-panel,.pt-card{border:1px solid var(--pt-outline);background:var(--pt-surface);box-shadow:var(--pt-glow);border-radius:12px}
.pt-neon-btn,.pt-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:32px;padding:6px 12px;border:1px solid var(--pt-outline);border-radius:10px;background:var(--pt-surface);color:var(--pt-text);box-shadow:var(--pt-glow);font:600 12px/1.15 inherit;cursor:pointer;transition:transform .14s ease,border-color .14s ease,box-shadow .14s ease}
.pt-neon-btn:hover,.pt-btn:hover{border-color:var(--pt-neon);box-shadow:0 0 16px rgba(0,229,255,.28);transform:translateY(-1px)}
.pt-neon-btn:active,.pt-btn:active{transform:translateY(0) scale(.98)}
.pt-neon-btn:disabled,.pt-btn:disabled{cursor:default;opacity:.52;transform:none;box-shadow:none}
.pt-neon-btn ha-icon,.pt-btn ha-icon{--mdc-icon-size:17px;color:var(--pt-neon)}
.pt-neon-btn.accent,.pt-btn.accent{border-color:color-mix(in srgb,var(--pt-violet) 65%,transparent)}
.pt-neon-btn.accent ha-icon,.pt-btn.accent ha-icon{color:var(--pt-violet)}
.pt-neon-btn.danger,.pt-btn.danger{border-color:rgba(255,82,82,.62);color:var(--pt-danger)}
.pt-neon-btn.danger ha-icon,.pt-btn.danger ha-icon{color:#ff5252}
.pt-compact .pt-neon-btn,.pt-compact .pt-btn{min-height:26px;padding:4px 8px;font-size:10px;border-radius:8px}
.pt-compact .pt-neon-btn ha-icon,.pt-compact .pt-btn ha-icon{--mdc-icon-size:15px}
.pt input,.pt select,.pt textarea{background:color-mix(in srgb,var(--pt-base) 88%,white 12%);color:var(--pt-text);border:1px solid var(--pt-outline);border-radius:8px;padding:6px 8px;font:inherit}
.pt-empty{padding:12px 2px;font-size:12px;color:var(--pt-muted);text-align:center}
`;
const PT_EDITOR_CSS = PT_NEON + `
.pte{font-family:var(--paper-font-body1_-_font-family,inherit);padding:8px 4px;color:var(--pt-text);font-size:13px}
.pte h4{margin:14px 0 6px;font-size:13px;text-transform:uppercase;letter-spacing:.5px;color:var(--pt-muted)}
.pte h4:first-child{margin-top:0}
.pte label{display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer}
.pte input[type=checkbox]{width:16px;height:16px}
.pte input[type=text],.pte input[type=number],.pte select,.pte textarea{width:100%;background:color-mix(in srgb,var(--pt-base) 88%,white 12%);color:var(--pt-text);border:1px solid var(--pt-outline);border-radius:8px;padding:7px 9px;font:inherit}
.pte .pt-hint{font-size:11px;color:var(--pt-muted);opacity:.85;margin:2px 0 6px}
.pte .pt-section{margin:12px 0;border:1px solid var(--pt-outline);border-radius:12px;background:var(--pt-surface);overflow:hidden}
.pte .pt-section>summary{display:flex;align-items:center;gap:8px;padding:11px 12px;cursor:pointer;list-style:none;font-weight:600}
.pte .pt-section>summary::-webkit-details-marker{display:none}
.pte .pt-section>summary::after{content:"⌄";margin-left:auto;color:var(--pt-muted);transition:transform .15s ease}
.pte .pt-section[open]>summary::after{transform:rotate(180deg)}
.pte .pt-section-body{padding:0 12px 12px;border-top:1px solid var(--pt-outline)}
.pte .pt-field{display:flex;flex-direction:column;gap:4px;margin-top:8px}
`;
const PERSON_TIMELINE_NEON_CSS = PT_NEON;

class PersonTimelineCard extends HTMLElement {
setConfig(c) {
this._cfg = Object.assign({persons: [], compact: false}, c || {});
this._trackers = Object.assign({}, (c || {}).trackers || {});
this._batteries = Object.assign({}, (c || {}).batteries || {});
this._colors = Object.assign({}, (c || {}).colors || {});
if (this._unsub) { try { this._unsub(); } catch (e) {} this._unsub = null; this._sub = false; }
if (!this._built) { this._build(); this._built = true; }
}
_name(person) {
const s = this._hass && this._hass.states[person];
return (s && s.attributes.friendly_name) || person.replace("person.", "").replace(/_/g, " ");
}
_initials(person) {
return this._name(person).split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
}
_build() {
this.innerHTML = '<div class="pt-live-root"><div id="live" class="pt-live-list"></div>'
+ '<div class="pt-live-footer"><button id="lv" class="pt-neon-btn"><ha-icon icon="mdi:access-point"></ha-icon><span>Live: til</span></button><span id="s"></span></div></div>'
+ '<style>' + PT_NEON
+ '.pt-live-list{display:flex;gap:8px;flex-wrap:wrap}.pt-person-card{flex:1;min-width:180px;display:flex;gap:10px;align-items:center;padding:10px 12px;border:1px solid var(--pt-outline,var(--pt-outline,rgba(0,229,255,.20)));border-radius:12px;background:var(--pt-surface,linear-gradient(145deg,rgba(0,229,255,.055),rgba(185,103,255,.045)));box-shadow:var(--pt-glow,0 0 14px rgba(0,229,255,.045));color:var(--pt-text,var(--primary-text-color))}'
+ '.pt-avatar{flex:0 0 40px;width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;box-shadow:0 0 12px var(--pt-outline,rgba(0,229,255,.20))}.pt-person-name{font-weight:650;color:var(--pt-text,var(--primary-text-color))}.pt-person-chip{font-size:13px;color:var(--pt-muted,var(--secondary-text-color))}.pt-person-meta{font-size:12px;color:var(--pt-muted,var(--secondary-text-color))}.pt-destination{font-size:12px;color:var(--pt-neon,#00e5ff)}.pt-live-footer{display:flex;gap:8px;align-items:center;padding:8px 0 0;font-size:12px;color:var(--pt-muted,var(--secondary-text-color))}'
+ '.pt-live-root.pt-compact .pt-live-list{gap:4px}.pt-live-root.pt-compact .pt-person-card{min-width:150px;gap:7px;padding:6px 8px;border-radius:9px}.pt-live-root.pt-compact .pt-avatar{flex-basis:30px;width:30px;height:30px;font-size:12px}.pt-live-root.pt-compact .pt-person-name{font-size:12px}.pt-live-root.pt-compact .pt-person-chip,.pt-live-root.pt-compact .pt-person-meta,.pt-live-root.pt-compact .pt-destination{font-size:10px}.pt-live-root.pt-compact .pt-live-footer{padding-top:4px}'
+ '@keyframes ptpulse{0%{box-shadow:0 0 0 0 rgba(0,229,255,.5)}70%{box-shadow:0 0 0 12px rgba(0,229,255,0)}100%{box-shadow:0 0 0 0 rgba(0,229,255,0)}}'
+ '</style>';
this._liveOn = true;
this.querySelector("#lv").onclick = () => { this._liveOn = !this._liveOn; this.querySelector("#lv span").textContent = this._liveOn ? "Live: til" : "Live: fra"; if (this._liveOn) this._renderLiveList(); };
this._timer = setInterval(() => { if (this._liveOn && this._hass) this._renderLiveList(); }, 15000);
}
set hass(h) {
this._hass = h;
if (!this._cfg) return;
personTimelineTheme(this, h);
this._subscribe();
this._renderLiveList();
}
_subscribe() {
if (this._sub || !this._hass || !this._hass.connection) return;
const ids = [...this._cfg.persons, ...this._cfg.persons.map(p => this._trackers[p]).filter(Boolean), ...Object.values(this._batteries), "input_boolean.tiny_family_live_visning", PT_COMPACT_ENTITY, PT_LEGACY_COMPACT_ENTITY, ...this._cfg.persons.map(p => "input_boolean.tiny_family_vis_" + p.split(".")[1]), ...this._cfg.persons.map(p => "sensor.tiny_family_" + p.split(".")[1] + "_destination")];
try {
this._unsub = this._hass.connection.subscribeMessage(ev => {
const eid = ev && ev.data && ev.data.entity_id;
if (eid && ids.includes(eid)) this._renderLiveList();
}, {type: "subscribe_events", event_type: "state_changed"});
this._sub = true;
} catch (e) {}
}
_statusFor(person) {
const h = this._hass, tr = this._trackers[person];
const t = tr && h.states[tr], p = h.states[person];
if (!t) return {chip: "ukendt", moving: false};
const kmh = Number((t.attributes && t.attributes.speed) || 0) * 3.6;
const zone = p ? p.state : "";
const place = zone === "not_home" ? "ude" : zone === "home" ? "Hjemme" : zone;
if (kmh >= 30) return {chip: "Kører " + Math.round(kmh) + " km/t", moving: true};
if (kmh >= 8) return {chip: "Cykler " + Math.round(kmh) + " km/t", moving: true};
if (kmh >= 3) return {chip: "Går", moving: true};
if (zone === "home") return {chip: "Hjemme", moving: false};
if (zone && zone !== "not_home" && zone !== "unknown") return {chip: place, moving: false};
return {chip: "Står stille", moving: false};
}
_batt(tr) {
const b = this._batteries[tr];
const s = b && this._hass.states[b];
if (!s || s.state === "unknown" || s.state === "unavailable") return "";
const v = Number(s.state), col = v <= 15 ? "#d93025" : v <= 30 ? "#e8710a" : "";
return '<span style="color:' + col + '">Batteri ' + v + "%</span>";
}
_ago(iso) {
if (!iso) return "";
const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
return m < 1 ? "nu" : "for " + m + " min siden";
}
_hav(a, b, c, d) {
const R = 6371000, t = Math.PI / 180;
const s1 = Math.sin((c - a) * t / 2), s2 = Math.sin((d - b) * t / 2);
return 2 * R * Math.asin(Math.sqrt(s1 * s1 + Math.cos(a * t) * Math.cos(c * t) * s2 * s2));
}
_dest(person) {
try {
const slug = person.split(".")[1];
const d = this._hass.states["sensor.tiny_family_" + slug + "_destination"];
if (!d || !d.state || ["Ingen", "unknown", "unavailable", ""].includes(d.state)) return "";
const e = this._hass.states["sensor.tiny_family_" + slug + "_destination_eta"];
const km = this._hass.states["sensor.tiny_family_" + slug + "_destination_afstand"];
const eta = e ? Number(e.state) : 0;
if (!isFinite(eta) || eta <= 0) return "";
const dist = km ? Number(km.state) : 0;
const tail = (isFinite(dist) && dist > 0) ? " (" + dist.toFixed(1) + " km)" : "";
return '<div class="pt-destination">På vej til ' + d.state + " ~" + Math.round(eta) + " min" + tail + "</div>";
} catch (e) { return ""; }
}
_visiblePersons() {
try {
const h = this._hass && this._hass.states["input_select.tiny_family_valg"];
if (h && h.state && h.state !== "Begge") {
const hit = this._cfg.persons.find(p => this._name(p) === h.state);
if (hit) return [hit];
}
return this._cfg.persons;
} catch (e) { return this._cfg.persons; }
}
_ghostOn(person) {
try {
const s = this._hass && this._hass.states["input_boolean.tiny_family_ghost_" + person.split(".")[1]];
return !!(s && s.state === "on");
} catch (e) { return false; }
}
_renderLiveList() {
if (!this._hass || !this._cfg) return;
const root = this.querySelector(".pt-live-root");
if (root) root.classList.toggle("pt-compact", personTimelineCompact(this._hass, this._cfg));
const el = this.querySelector("#live");
if (!el) return;
try {
const lv = this._hass.states["input_boolean.tiny_family_live_visning"];
el.style.display = (!lv || lv.state === "on") ? "" : "none";
} catch (e) {}
el.innerHTML = this._visiblePersons().map(person => {
const tr = this._trackers[person], t = tr && this._hass.states[tr];
const st = this._statusFor(person);
const col = this._colors[person] || "";
const upd = t ? this._ago(t.last_changed) : "";
const batt = tr ? this._batt(tr) : "";
const ghost = this._ghostOn(person);
const chip = ghost ? "Ghost – skjult" : st.chip;
const eta = ghost ? "" : this._dest(person);
return '<div class="pt-person-card">'
+ '<div class="pt-avatar" style="background:' + col + '">' + this._initials(person) + "</div>"
+ '<div><div class="pt-person-name">' + this._name(person) + '</div><div class="pt-person-chip">' + chip + "</div>" + eta
+ '<div class="pt-person-meta">' + batt + (batt && upd ? " • " : "") + upd + "</div></div></div>";
}).join("");
const n = this._visiblePersons().length;
const s = this.querySelector("#s");
if (s) s.textContent = n ? "Liveopdateret (" + n + " personer). Rute og historik vises på kortet herunder." : "Alle personer er skjult – slå dem til under Visning.";
}
getCardSize() { return 3; }
static getConfigElement() { return document.createElement("tiny-family-card-editor"); }
static getStubConfig() { return {persons: [], compact: false}; }
}
customElements.define("tiny-family-card", PersonTimelineCard);

class PersonTimelineCardEditor extends HTMLElement {
setConfig(config) { personTimelineTheme(this,this._hass);
this._config = Object.assign({persons: [], trackers: {}, batteries: {}, compact: false}, config || {});
this._built = false;
if (this._hass) { this._render(); this._built = true; }
}
set hass(h) {
this._hass = h;
if (!this._built) { this._render(); this._built = true; return; }
this.querySelectorAll("ha-entity-picker").forEach(p => { p.hass = h; });
}
_fire() {
const ev = new Event("config-changed", {bubbles: true, composed: true});
ev.detail = {config: this._config};
this.dispatchEvent(ev);
}
_apply(persons, trackers, batteries) {
this._config = Object.assign({}, this._config, {persons: persons, trackers: trackers, batteries: batteries});
this._built = false;
this._render();
this._built = true;
this._fire();
}
_render() {
if (!this._hass || !this._config) return;
const persons = (this._config.persons || []).slice();
const trackers = Object.assign({}, this._config.trackers || {});
const batteries = Object.assign({}, this._config.batteries || {});
this.innerHTML = "";
const wrap = document.createElement("div");
wrap.className="pte";
wrap.style.cssText = "display:flex;flex-direction:column;gap:12px;padding:8px 0";
const lbl = document.createElement("div");
lbl.textContent = "Personer (kommasepareret)";
lbl.style.cssText = "font-weight:600;font-size:13px";
wrap.appendChild(lbl);
const inp = document.createElement("input");
inp.type = "text";
inp.value = persons.join(", ");
inp.placeholder = "person.example, person.example2";
inp.style.cssText = "padding:8px;border:1px solid #ccc;border-radius:6px;font-size:14px;width:100%;box-sizing:border-box";
inp.onchange = () => {
const list = inp.value.split(",").map(s => s.trim()).filter(Boolean);
this._apply(list, trackers, batteries);
};
wrap.appendChild(inp);
const compactLabel = document.createElement("label");
compactLabel.style.cssText = "display:flex;align-items:center;gap:8px;font-size:14px";
const compactInput = document.createElement("input");
compactInput.type = "checkbox";
compactInput.checked = this._config.compact === true;
compactInput.onchange = () => {
this._config = Object.assign({}, this._config, {compact: compactInput.checked});
this._fire();
};
compactLabel.appendChild(compactInput);
compactLabel.appendChild(document.createTextNode("Brug altid kompakt visning"));
wrap.appendChild(compactLabel);
persons.forEach(person => {
const box = document.createElement("div");
box.style.cssText = "border:1px solid #e0e0e0;border-radius:8px;padding:10px;display:flex;flex-direction:column;gap:8px";
const head = document.createElement("div");
head.textContent = (this._hass.states[person] && this._hass.states[person].attributes.friendly_name) || person;
head.style.cssText = "font-weight:600;font-size:14px";
box.appendChild(head);
const tp = document.createElement("ha-entity-picker");
tp.hass = this._hass;
tp.label = "Tracker (enhed)";
tp.value = trackers[person] || "";
tp.includeDomains = ["device_tracker"];
tp.allowCustomEntity = true;
tp.addEventListener("value-changed", ev => {
const v = ev.detail.value || "";
if (v) trackers[person] = v; else delete trackers[person];
this._apply(persons, trackers, batteries);
});
box.appendChild(tp);
const bp = document.createElement("ha-entity-picker");
bp.hass = this._hass;
bp.label = "Batteri-sensor";
bp.value = (trackers[person] && batteries[trackers[person]]) || "";
bp.includeDomains = ["sensor"];
bp.allowCustomEntity = true;
bp.addEventListener("value-changed", ev => {
const v = ev.detail.value || "";
const key = trackers[person] || person;
if (v) batteries[key] = v; else delete batteries[key];
this._apply(persons, trackers, batteries);
});
box.appendChild(bp);
wrap.appendChild(box);
});
this.appendChild(wrap);
}
}
customElements.define("tiny-family-card-editor", PersonTimelineCardEditor);
window.customCards = window.customCards || [];
window.customCards.push({type: "tiny-family-card", name: "Tiny Family Live", description: "Live venne-liste med status, batteri og ETA"});

class PersonTimelinePlacesCard extends HTMLElement {
setConfig(c) {
this._cfg = Object.assign({persons: [], radius: 25, compact: false}, c || {});
}
set hass(h) {
this._hass = h;
if (!this._cfg) return;
personTimelineTheme(this, h);
const signature = JSON.stringify({suggestions: this._suggestions(), compact: this._compact()});
if (signature !== this._signature) {
this._signature = signature;
this._render();
}
}
_compact() {
return personTimelineCompact(this._hass, this._cfg);
}
_name(person) {
const s = this._hass && this._hass.states[person];
return (s && s.attributes.friendly_name) || person.replace("person.", "").replace(/_/g, " ");
}
_escape(value) {
return String(value == null ? "" : value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
}
_suggestions() {
if (!this._hass) return [];
const rows = [];
(this._cfg.persons || []).forEach(person => {
const slug = person.split(".")[1];
const state = this._hass.states["sensor.tiny_family_" + slug + "_kendte_steder"];
const items = state && Array.isArray(state.attributes.zone_forslag) ? state.attributes.zone_forslag : [];
items.forEach(item => rows.push({person: person, name: this._name(person), item: item}));
});
return rows;
}
_render() {
const rows = this._suggestions();
const compact = this._compact();
const body = rows.length ? rows.map((row, index) => {
const item = row.item;
const suggested = item.navn && !["ukendt sted", "unknown", "ukendt"].includes(String(item.navn).toLowerCase()) ? item.navn : "";
return '<div class="pt-place" data-index="' + index + '">'
+ '<div class="pt-place-head"><span class="pt-person">' + this._escape(row.name) + '</span><span>' + this._escape(item.besoeg) + ' besøg · ' + this._escape(item.minutter) + ' min</span></div>'
+ '<button class="pt-coord" data-map="' + index + '" title="Vis på kort">📍 ' + this._escape(item.lat) + ', ' + this._escape(item.lon) + '</button>'
+ '<div class="pt-place-actions"><input data-name="' + index + '" value="' + this._escape(suggested) + '" placeholder="Skriv stedets navn" maxlength="100">'
+ '<button class="pt-save" data-save="' + index + '">Gem sted og zone</button>'
+ '<button class="pt-delete" data-delete="' + index + '">Slet forslag</button></div>'
+ '<div class="pt-status" data-status="' + index + '"></div></div>';
}).join("") : '<div class="pt-empty">Ingen ukendte steder at behandle.</div>';
this.innerHTML = '<ha-card><div class="pt-wrap' + (compact ? ' compact' : '') + '">' + body + '</div></ha-card>'
+ '<div class="pt-modal" hidden><div class="pt-dialog"><div class="pt-dialog-head"><strong>Placering</strong><button class="pt-close" aria-label="Luk">✕</button></div><iframe title="Kort over foreslået sted"></iframe><div class="pt-map-info"></div></div></div>'
+ '<style>'
+ '.pt-wrap{display:flex;flex-direction:column;gap:8px;padding:8px}.pt-place{border:1px solid var(--pt-outline,var(--divider-color));border-radius:10px;padding:9px;background:color-mix(in srgb,var(--pt-base,#fff) 88%,white 12%)}'
+ '.pt-place-head{display:flex;justify-content:space-between;gap:8px;font-size:12px;color:var(--pt-muted,var(--secondary-text-color));margin-bottom:5px}.pt-person{font-weight:700;color:var(--pt-text,var(--primary-text-color))}'
+ '.pt-coord{border:0;background:none;color:var(--primary-color);padding:2px 0;margin:0 0 7px;cursor:pointer;font-size:12px;text-decoration:underline}'
+ '.pt-place-actions{display:flex;gap:6px}.pt-place-actions input{min-width:0;flex:1;padding:7px 9px;border:1px solid var(--pt-outline,var(--divider-color));border-radius:7px;background:color-mix(in srgb,var(--pt-base,#fff) 88%,white 12%);color:var(--pt-text,var(--primary-text-color))}'
+ PERSON_TIMELINE_NEON_CSS
+ '.pt-save,.pt-delete{min-height:30px;border-radius:9px;padding:5px 9px;cursor:pointer;white-space:nowrap;font:600 12px/1.15 inherit;transition:transform .14s ease,box-shadow .14s ease}.pt-save{border:1px solid rgba(0,229,255,.65);background:linear-gradient(135deg,rgba(0,229,255,.22),rgba(185,103,255,.16));color:var(--primary-text-color,#eaf6ff);box-shadow:0 0 12px rgba(0,229,255,.10)}.pt-delete{border:1px solid rgba(255,82,82,.62);background:rgba(255,82,82,.08);color:#ffb4b4}.pt-save:hover,.pt-delete:hover{transform:translateY(-1px);box-shadow:0 0 15px rgba(0,229,255,.22)}.pt-save:disabled,.pt-delete:disabled{opacity:.55;transform:none}.pt-status{font-size:12px;margin-top:5px;color:var(--pt-muted,var(--secondary-text-color))}.pt-empty{padding:12px;color:var(--pt-muted,var(--secondary-text-color))}'
+ '.pt-wrap.compact{gap:4px;padding:4px}.compact .pt-place{padding:6px;border-radius:8px}.compact .pt-place-head{font-size:11px;margin-bottom:2px}.compact .pt-coord{font-size:11px;margin-bottom:4px}.compact .pt-place-actions{gap:4px}.compact .pt-place-actions input,.compact .pt-save,.compact .pt-delete{font-size:12px;padding:5px 7px}.compact .pt-status{font-size:11px;margin-top:3px}.compact .pt-empty{padding:8px}'
+ '.pt-modal{position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;padding:16px}.pt-modal[hidden]{display:none}.pt-dialog{width:min(680px,96vw);background:color-mix(in srgb,var(--pt-base,#fff) 88%,white 12%);border-radius:12px;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,.35)}.pt-dialog-head{display:flex;justify-content:space-between;align-items:center;padding:10px 12px}.pt-close{border:0;background:none;color:var(--pt-text,var(--primary-text-color));font-size:20px;cursor:pointer}.pt-dialog iframe{display:block;width:100%;height:min(55vh,450px);border:0}.pt-map-info{padding:10px 12px;font-size:13px;color:var(--pt-muted,var(--secondary-text-color))}'
+ '@media(max-width:600px){.pt-place-actions{flex-direction:column}.pt-save,.pt-delete{width:100%}.compact .pt-place-actions{display:grid;grid-template-columns:1fr 1fr}.compact .pt-place-actions input{grid-column:1/-1}.compact .pt-save,.compact .pt-delete{width:auto}}'
+ '</style>';
this.querySelectorAll("[data-map]").forEach(button => button.onclick = () => this._openMap(rows[Number(button.dataset.map)].item));
this.querySelectorAll("[data-save]").forEach(button => button.onclick = () => this._save(rows, Number(button.dataset.save), button));
this.querySelectorAll("[data-delete]").forEach(button => button.onclick = () => this._delete(rows, Number(button.dataset.delete), button));
const modal = this.querySelector(".pt-modal");
this.querySelector(".pt-close").onclick = () => { modal.hidden = true; };
modal.onclick = event => { if (event.target === modal) modal.hidden = true; };
}
_openMap(item) {
const lat = Number(item.lat), lon = Number(item.lon), delta = 0.004;
if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) return;
const bbox = [lon - delta, lat - delta, lon + delta, lat + delta].join("%2C");
const modal = this.querySelector(".pt-modal");
modal.querySelector("iframe").src = "https://www.openstreetmap.org/export/embed.html?bbox=" + bbox + "&layer=mapnik&marker=" + lat + "%2C" + lon;
modal.querySelector(".pt-map-info").textContent = "Position: " + lat.toFixed(6) + ", " + lon.toFixed(6) + " · Kortet vises direkte i Home Assistant.";
modal.hidden = false;
}
async _save(rows, index, button) {
const row = rows[index], input = this.querySelector('[data-name="' + index + '"]'), status = this.querySelector('[data-status="' + index + '"]');
const name = (input.value || "").trim();
if (!name) { status.textContent = "Skriv først et navn."; input.focus(); return; }
button.disabled = true;
status.textContent = "Gemmer…";
try {
await this._hass.callService("tiny_family", "save_place_as_zone", {person: row.person, lat: Number(row.item.lat), lon: Number(row.item.lon), navn: name, radius: Number(this._cfg.radius || 25)});
status.textContent = "Gemt. Forslaget fjernes nu.";
} catch (error) {
status.textContent = "Kunne ikke gemme: " + (error && error.message ? error.message : error);
button.disabled = false;
}
}
async _delete(rows, index, button) {
const row = rows[index], status = this.querySelector('[data-status="' + index + '"]');
if (!window.confirm("Slet dette forslag? Stedet kan blive foreslået igen efter et nyt ophold.")) return;
button.disabled = true;
status.textContent = "Sletter…";
try {
await this._hass.callService("tiny_family", "delete_place_suggestion", {person: row.person, lat: Number(row.item.lat), lon: Number(row.item.lon)});
status.textContent = "Forslaget er slettet.";
} catch (error) {
status.textContent = "Kunne ikke slette: " + (error && error.message ? error.message : error);
button.disabled = false;
}
}
getCardSize() { return Math.max(1, this._suggestions().length * 2); }
static getStubConfig() { return {persons: [], radius: 25, compact: false}; }
static getConfigElement() { return document.createElement("tiny-family-places-card-editor"); }
}
customElements.define("tiny-family-places-card", PersonTimelinePlacesCard);
window.customCards.push({type: "tiny-family-places-card", name: "Tiny Family steder", description: "Behandl alle foreslåede steder enkeltvis"});

class PersonTimelinePlacesCardEditor extends HTMLElement {
setConfig(config) {
this._config = Object.assign({persons: [], radius: 25, compact: false}, config || {});
this._built = false;
if (this._hass) { this._render(); this._built = true; }
}
set hass(h) {
this._hass = h;
if (!this._built) { this._render(); this._built = true; return; }
}
_fire() {
const ev = new Event("config-changed", {bubbles: true, composed: true});
ev.detail = {config: this._config};
this.dispatchEvent(ev);
}
_render() {
if (!this._hass || !this._config) return;
const persons = (this._config.persons || []).slice();
this.innerHTML = "";
const wrap = document.createElement("div");
wrap.className="pte";
wrap.style.cssText = "display:flex;flex-direction:column;gap:12px;padding:8px 0";
const lbl = document.createElement("div");
lbl.textContent = "Personer (kommasepareret)";
lbl.style.cssText = "font-weight:600;font-size:13px";
wrap.appendChild(lbl);
const inp = document.createElement("input");
inp.type = "text";
inp.value = persons.join(", ");
inp.placeholder = "person.example, person.example2";
inp.style.cssText = "padding:8px;border:1px solid #ccc;border-radius:6px;font-size:14px;width:100%;box-sizing:border-box";
inp.onchange = () => {
const list = inp.value.split(",").map(s => s.trim()).filter(Boolean);
this._config = Object.assign({}, this._config, {persons: list});
this._fire();
};
wrap.appendChild(inp);
const rlbl = document.createElement("div");
rlbl.textContent = "Radius (meter)";
rlbl.style.cssText = "font-weight:600;font-size:13px;margin-top:8px";
wrap.appendChild(rlbl);
const rinp = document.createElement("input");
rinp.type = "number";
rinp.value = this._config.radius || 25;
rinp.min = 10; rinp.max = 200;
rinp.style.cssText = "padding:8px;border:1px solid #ccc;border-radius:6px;font-size:14px;width:100%;box-sizing:border-box";
rinp.onchange = () => {
this._config = Object.assign({}, this._config, {radius: Number(rinp.value) || 25});
this._fire();
};
wrap.appendChild(rinp);
const compactLabel = document.createElement("label");
compactLabel.style.cssText = "display:flex;align-items:center;gap:8px;margin-top:8px;font-size:14px";
const compactInput = document.createElement("input");
compactInput.type = "checkbox";
compactInput.checked = this._config.compact === true;
compactInput.onchange = () => {
this._config = Object.assign({}, this._config, {compact: compactInput.checked});
this._fire();
};
compactLabel.appendChild(compactInput);
compactLabel.appendChild(document.createTextNode("Brug altid kompakt visning"));
wrap.appendChild(compactLabel);
const compactHint = document.createElement("div");
compactHint.textContent = "Den globale Tiny Family-kontakt kan også aktivere kompakt visning.";
compactHint.style.cssText = "font-size:12px;color:var(--pt-muted,var(--secondary-text-color))";
wrap.appendChild(compactHint);
this.appendChild(wrap);
}
}
customElements.define("tiny-family-places-card-editor", PersonTimelinePlacesCardEditor);

class PersonRouteCard extends HTMLElement {
setConfig(c) {
this._cfg = Object.assign({persons: [], compact: false}, c || {});
this._trackers = Object.assign({}, (c || {}).trackers || {});
this._colors = Object.assign({}, (c || {}).colors || {});
if (!this._built) { this._build(); this._built = true; }
}
_name(person) {
const s = this._hass && this._hass.states[person];
return (s && s.attributes.friendly_name) || person.replace("person.", "").replace(/_/g, " ");
}
_wantPersons() {
try {
const h = this._hass && this._hass.states["input_select.tiny_family_valg"];
if (!h || h.state === "Begge") return this._cfg.persons;
const hit = this._cfg.persons.find(p => this._name(p) === h.state);
return hit ? [hit] : this._cfg.persons;
} catch (e) { return this._cfg.persons; }
}
_build() {
this.innerHTML = '<div class="pt-route-root"><div class="pt-route-controls">'
+ '<span id="who"></span><input type="date" id="d" />'
+ '<button id="b" class="pt-neon-btn"><ha-icon icon="mdi:map-search-outline"></ha-icon>Hent rute</button><span id="s"></span></div>'
+ '<div id="m"></div></div><style>' + PERSON_TIMELINE_NEON_CSS
+ '.pt-route-controls{display:flex;gap:8px;align-items:center;padding:8px;flex-wrap:wrap;font-size:13px}.pt-route-controls #who{font-weight:650;color:var(--pt-text,var(--primary-text-color))}.pt-route-controls #s{color:var(--pt-muted,var(--secondary-text-color));font-size:12px}.pt-route-controls input{min-height:30px;padding:3px 7px;border:1px solid rgba(0,229,255,.35);border-radius:8px;background:color-mix(in srgb,var(--pt-base,#fff) 88%,white 12%);color:var(--pt-text,var(--primary-text-color))}#m{height:420px;width:100%;border-radius:0 0 12px 12px;overflow:hidden}.pt-route-root.pt-compact .pt-route-controls{gap:4px;padding:4px;font-size:11px}.pt-route-root.pt-compact #m{height:300px}.pt-route-root.pt-compact .pt-neon-btn{min-height:26px;padding:3px 7px;font-size:10px}'
+ '</style>';
this.querySelector("#d").value = new Date().toISOString().slice(0, 10);
this.querySelector("#b").onclick = () => this._load();
const css = "/tiny_family_static/leaflet/leaflet.css";
if (!document.querySelector('link[href="' + css + '"]')) {
const l = document.createElement("link"); l.rel = "stylesheet"; l.href = css; document.head.appendChild(l);
}
const js = "/tiny_family_static/leaflet/leaflet.js";
const ensure = () => window.L ? Promise.resolve() : new Promise((res, rej) => {
const s = document.createElement("script"); s.src = js;
s.onload = res; s.onerror = () => rej(new Error("Kunne ikke indlæse kort-biblioteket.")); document.head.appendChild(s);
});
ensure().then(() => {
const el = this.querySelector("#m");
const homeLat = Number(this._hass && this._hass.config && this._hass.config.latitude);
const homeLon = Number(this._hass && this._hass.config && this._hass.config.longitude);
const hasHomePosition = !!(this._hass && this._hass.config && Number.isFinite(homeLat) && Number.isFinite(homeLon));
this._map = window.L.map(el).setView(hasHomePosition ? [homeLat, homeLon] : [0, 0], hasHomePosition ? 13 : 2);
const osm = window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 19, attribution: "© OpenStreetMap"}).addTo(this._map);
const sat = window.L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {maxZoom: 19, attribution: "© Esri World Imagery"});
const topo = window.L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {maxZoom: 17, attribution: "© OpenStreetMap © OpenTopoMap"});
window.L.control.layers({"Kort": osm, "Satellit": sat, "Topo": topo}).addTo(this._map);
let fails = 0;
[osm, sat, topo].forEach(ly => ly.on("tileerror", () => {
fails++;
if (fails === 6) { const st = this.querySelector("#s"); if (st) st.textContent += " Kortbrikker fejler – prøv et andet lag øverst til højre."; }
}));
this._layer = window.L.layerGroup().addTo(this._map);
try {
new ResizeObserver(() => { clearTimeout(this._rszT); this._rszT = setTimeout(() => { try { this._map.invalidateSize(); } catch (e) {} }, 200); }).observe(el);
} catch (e) {}
setTimeout(() => { try { this._map.invalidateSize(); } catch (e) {} }, 500);
if (this._hass) this._load();
}, err => {
const st = this.querySelector("#s");
if (st) st.textContent = "Fejl: " + err.message;
});
}
set hass(h) {
this._hass = h;
if (!this._cfg) return;
personTimelineTheme(this, h);
const root = this.querySelector(".pt-route-root");
if (root) root.classList.toggle("pt-compact", personTimelineCompact(this._hass, this._cfg));
if (this._map && !this._loaded) { this._loaded = true; this._load(); }
}
_hav(a, b, c, d) {
const R = 6371000, t = Math.PI / 180;
const s1 = Math.sin((c - a) * t / 2), s2 = Math.sin((d - b) * t / 2);
return 2 * R * Math.asin(Math.sqrt(Math.max(0, Math.min(1, s1 * s1 + Math.cos(a * t) * Math.cos(c * t) * s2 * s2))));
}
_cphOff(dateStr) {
try {
const noon = new Date(dateStr + "T12:00:00Z");
const p = new Intl.DateTimeFormat("en-CA", {timeZone: "Europe/Copenhagen", hour: "2-digit", minute: "2-digit", hour12: false}).formatToParts(noon);
const h = Number((p.find(x => x.type === "hour") || {}).value || 0), m = Number((p.find(x => x.type === "minute") || {}).value || 0);
let off = (h * 60 + m) - 720;
const sign = off < 0 ? "-" : "+";
off = Math.abs(off);
return sign + String(Math.floor(off / 60)).padStart(2, "0") + ":" + String(off % 60).padStart(2, "0");
} catch (e) { return "+02:00"; }
}
async _hist(tracker, start, end) {
const path = "history/period/" + encodeURIComponent(start) + "?filter_entity_id=" + encodeURIComponent(tracker) + "&minimal_response=false&end_time=" + encodeURIComponent(end);
const r = await this._hass.callApi("GET", path);
return Array.isArray(r) ? (r[0] || []) : [];
}
_toPts(states) {
return states.filter(s => (s.attributes || s.a) && (s.attributes || s.a).latitude != null)
.map(s => { const a = s.attributes || s.a;
return {t: new Date(s.last_changed || s.last_updated || s.lu || s.lc).getTime(), lat: Number(a.latitude), lon: Number(a.longitude),
speed: Number(a.speed || 0), acc: Number(a.gps_accuracy || 999)}; })
.filter(p => isFinite(p.lat) && isFinite(p.lon) && p.acc < 200).sort((a, b) => a.t - b.t);
}
_stays(pts) {
const stays = []; let cur = [];
const done = c => ({lat: c.reduce((s, p) => s + p.lat, 0) / c.length, lon: c.reduce((s, p) => s + p.lon, 0) / c.length,
start: c[0].t, end: c[c.length - 1].t, min: Math.round((c[c.length - 1].t - c[0].t) / 60000)});
for (const p of pts) {
const last = cur[cur.length - 1];
if (!last) { cur = [p]; continue; }
const dt = (p.t - last.t) / 60000, d = this._hav(last.lat, last.lon, p.lat, p.lon);
if (d < 100 && (p.speed * 3.6) < 5 && dt < 30) cur.push(p);
else { if (cur.length > 1 && (cur[cur.length - 1].t - cur[0].t) / 60000 >= 10) stays.push(done(cur)); cur = [p]; }
}
if (cur.length > 1 && (cur[cur.length - 1].t - cur[0].t) / 60000 >= 10) stays.push(done(cur));
return stays;
}
async _snap(coords) {
const out = [];
for (let i = 0; i < coords.length; i += 90) {
const b = coords.slice(i, i + 90);
if (b.length < 2) { out.push(...b.map(p => [p.lat, p.lon])); continue; }
const str = b.map(p => p.lon + "," + p.lat).join(";");
try {
const ctl = ("AbortController" in window) ? new AbortController() : null;
const to = ctl ? setTimeout(() => ctl.abort(), 12000) : null;
const r = await fetch("https://router.project-osrm.org/match/v1/driving/" + str + "?overview=full&geometries=geojson&radiuses=" + b.map(() => 25).join(";"), ctl ? {signal: ctl.signal} : {});
if (to) clearTimeout(to);
const j = await r.json();
if (j.code === "Ok" && j.matchings && j.matchings.length && j.matchings[0].geometry && j.matchings[0].geometry.coordinates) out.push(...j.matchings[0].geometry.coordinates.map(c => [c[1], c[0]]));
else out.push(...b.map(p => [p.lat, p.lon]));
} catch (e) { out.push(...b.map(p => [p.lat, p.lon])); }
}
return out.filter(c => isFinite(c[0]) && isFinite(c[1]));
}
async _load() {
if (!this._hass || !this._map || !this._cfg) return;
const st = this.querySelector("#s"), who = this.querySelector("#who");
const dateStr = (this.querySelector("#d") && this.querySelector("#d").value) || new Date().toISOString().slice(0, 10);
const persons = this._wantPersons();
if (who) who.textContent = persons.map(p => this._name(p)).join(" + ") + " • " + dateStr;
try { this._map.invalidateSize(); } catch (e) {}
const sz = this._map.getSize();
if (!sz || !sz.x || !sz.y) { setTimeout(() => this._load(), 700); return; }
st.textContent = "Henter rute…";
this._layer.clearLayers();
const off = this._cphOff(dateStr);
const start = dateStr + "T00:00:00" + off, end = dateStr + "T23:59:59" + off;
const bounds = [];
try {
for (const person of persons) {
const tracker = this._trackers[person]; if (!tracker) continue;
let pts = this._toPts(await this._hist(tracker, start, end));
pts = pts.filter((p, i) => { if (!i) return true; const q = pts[i - 1];
const dt = (p.t - q.t) / 3600000; if (dt <= 0) return false;
return (this._hav(q.lat, q.lon, p.lat, p.lon) / 1000 / dt) < 200; });
if (pts.length > 600) pts = pts.filter((_, i) => i % Math.ceil(pts.length / 600) === 0);
if (!pts.length) continue;
const stays = this._stays(pts);
let spread = 0;
for (const p of pts) spread = Math.max(spread, this._hav(pts[0].lat, pts[0].lon, p.lat, p.lon));
const line = spread < 200 ? pts.map(p => [p.lat, p.lon]) : await this._snap(pts.map(p => ({lat: p.lat, lon: p.lon})));
if (line.length > 1) {
window.L.polyline(pts.map(p => [p.lat, p.lon]), {color: "#e8710a", weight: 2, dashArray: "6 6", opacity: 0.7}).addTo(this._layer);
const pl = window.L.polyline(line, {color: this._colors[person] || "", weight: 4}).addTo(this._layer);
try { bounds.push(pl.getBounds()); } catch (e) {}
} else if (line.length === 1) {
window.L.circleMarker(line[0], {radius: 6, color: "#fff", weight: 2, fillColor: this._colors[person] || "", fillOpacity: 1}).addTo(this._layer);
try { bounds.push(window.L.latLng(line[0][0], line[0][1])); } catch (e) {}
}
stays.forEach(s => {
const a = new Date(s.start).toLocaleTimeString("da-DK", {hour: "2-digit", minute: "2-digit"});
const b2 = new Date(s.end).toLocaleTimeString("da-DK", {hour: "2-digit", minute: "2-digit"});
window.L.circleMarker([s.lat, s.lon], {radius: 8, color: "#fff", weight: 2, fillColor: "#e8710a", fillOpacity: 1})
.bindPopup("<b>" + this._name(person) + " ophold " + s.min + " min</b><br>" + a + " → " + b2).addTo(this._layer);
try { bounds.push(window.L.latLng(s.lat, s.lon)); } catch (e) {}
});
}
if (!bounds.length) { st.textContent = "Ingen GPS-punkter den dag."; return; }
try {
const flat = [];
bounds.forEach(b => { try { if (b.getNorth) { flat.push(b.getSouthWest(), b.getNorthEast()); } else { flat.push(b); } } catch (e) {} });
if (!flat.length) throw new Error("bad bounds");
const b = window.L.latLngBounds(flat).pad(0.2);
const c = b.getCenter();
if (!isFinite(c.lat) || !isFinite(c.lng)) throw new Error("bad bounds");
if ((b.getEast() - b.getWest()) < 0.004 && (b.getNorth() - b.getSouth()) < 0.004) this._map.setView(c, 15);
else this._map.fitBounds(b);
} catch (e) { st.textContent = "Rute hentet (kortudsnit fejlede)."; return; }
st.textContent = "Blå = vej-snappet rute, orange stiplet = rå GPS, orange prik = ophold (" + this._layer.getLayers().length + " objekter).";
} catch (e) { st.textContent = "Fejl: " + String((e && (e.message || e.error)) || e).slice(0, 160); }
}
getCardSize() { return 6; }
static getConfigElement() { return document.createElement("person-route-card-editor"); }
static getStubConfig() { return {persons: [], trackers: {}, batteries: {}, compact: false}; }
}
customElements.define("person-route-card", PersonRouteCard);
window.customCards = window.customCards || [];
window.customCards.push({type: "person-route-card", name: "Person Rute Historik", description: "Vej-snappet historikrute med ophold for valgt person"});

class PersonRouteCardEditor extends HTMLElement {
setConfig(config) {
this._config = Object.assign({persons: [], trackers: {}, batteries: {}, compact: false}, config || {});
this._built = false;
if (this._hass) { this._render(); this._built = true; }
}
set hass(h) {
this._hass = h;
if (!this._built) { this._render(); this._built = true; return; }
this.querySelectorAll("ha-entity-picker").forEach(p => { p.hass = h; });
}
_fire() {
const ev = new Event("config-changed", {bubbles: true, composed: true});
ev.detail = {config: this._config};
this.dispatchEvent(ev);
}
_render() {
if (!this._hass || !this._config) return;
const persons = (this._config.persons || []).slice();
const trackers = Object.assign({}, this._config.trackers || {});
const batteries = Object.assign({}, this._config.batteries || {});
this.innerHTML = "";
const wrap = document.createElement("div");
wrap.className="pte";
wrap.style.cssText = "display:flex;flex-direction:column;gap:12px;padding:8px 0";
const lbl = document.createElement("div");
lbl.textContent = "Personer (kommasepareret)";
lbl.style.cssText = "font-weight:600;font-size:13px";
wrap.appendChild(lbl);
const inp = document.createElement("input");
inp.type = "text";
inp.value = persons.join(", ");
inp.placeholder = "person.example, person.example2";
inp.style.cssText = "padding:8px;border:1px solid #ccc;border-radius:6px;font-size:14px;width:100%;box-sizing:border-box";
inp.onchange = () => {
const list = inp.value.split(",").map(s => s.trim()).filter(Boolean);
this._config = Object.assign({}, this._config, {persons: list});
this._built = false;
this._render();
this._built = true;
this._fire();
};
wrap.appendChild(inp);
const compactLabel = document.createElement("label");
compactLabel.style.cssText = "display:flex;align-items:center;gap:8px;font-size:14px";
const compactInput = document.createElement("input");
compactInput.type = "checkbox";
compactInput.checked = this._config.compact === true;
compactInput.onchange = () => {
this._config = Object.assign({}, this._config, {compact: compactInput.checked});
this._fire();
};
compactLabel.appendChild(compactInput);
compactLabel.appendChild(document.createTextNode("Brug altid kompakt visning"));
wrap.appendChild(compactLabel);
persons.forEach(person => {
const box = document.createElement("div");
box.style.cssText = "border:1px solid #e0e0e0;border-radius:8px;padding:10px;display:flex;flex-direction:column;gap:8px";
const head = document.createElement("div");
head.textContent = (this._hass.states[person] && this._hass.states[person].attributes.friendly_name) || person;
head.style.cssText = "font-weight:600;font-size:14px";
box.appendChild(head);
const tp = document.createElement("ha-entity-picker");
tp.hass = this._hass;
tp.label = "Tracker (enhed)";
tp.value = trackers[person] || "";
tp.includeDomains = ["device_tracker"];
tp.allowCustomEntity = true;
tp.addEventListener("value-changed", ev => {
const v = ev.detail.value || "";
if (v) trackers[person] = v; else delete trackers[person];
this._config = Object.assign({}, this._config, {trackers: trackers});
this._fire();
});
box.appendChild(tp);
const bp = document.createElement("ha-entity-picker");
bp.hass = this._hass;
bp.label = "Batteri-sensor";
bp.value = (trackers[person] && batteries[trackers[person]]) || "";
bp.includeDomains = ["sensor"];
bp.allowCustomEntity = true;
bp.addEventListener("value-changed", ev => {
const v = ev.detail.value || "";
const key = trackers[person] || person;
if (v) batteries[key] = v; else delete batteries[key];
this._config = Object.assign({}, this._config, {batteries: batteries});
this._fire();
});
box.appendChild(bp);
wrap.appendChild(box);
});
this.appendChild(wrap);
}
}
customElements.define("person-route-card-editor", PersonRouteCardEditor);

class PersonTimelineNeonButtonsCard extends HTMLElement {
setConfig(config) {
this._config = Object.assign({buttons: [], columns: 2, compact: false}, config || {});
if (!Array.isArray(this._config.buttons)) throw new Error("buttons skal være en liste");
this._render();
}
set hass(hass) {
this._hass = hass;
personTimelineTheme(this, hass);
this._render();
}
_escape(value) {
return String(value == null ? "" : value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
}
_render() {
if (!this._config) return;
const compact = personTimelineCompact(this._hass, this._config);
const columns = Math.max(1, Math.min(6, Number(this._config.columns) || 2));
const buttons = this._config.buttons.map((button, index) => {
const tone = ["accent", "danger"].includes(button.tone) ? " " + button.tone : "";
const icon = button.icon ? '<ha-icon icon="' + this._escape(button.icon) + '"></ha-icon>' : "";
return '<button class="pt-neon-btn' + tone + '" data-index="' + index + '">' + icon + '<span>' + this._escape(button.name || button.service || "Handling") + "</span></button>";
}).join("");
this.innerHTML = '<ha-card><div class="pt-neon-grid' + (compact ? " compact" : "") + '" style="--pt-columns:' + columns + ';--pt-mobile-columns:' + Math.min(2, columns) + '">' + buttons + '</div></ha-card><style>'
+ PERSON_TIMELINE_NEON_CSS
+ '.pt-neon-grid{display:grid;grid-template-columns:repeat(var(--pt-columns),minmax(0,1fr));gap:6px;padding:7px}.pt-neon-grid .pt-neon-btn{width:100%;min-width:0}.pt-neon-grid.compact{gap:4px;padding:4px}.pt-neon-grid.compact .pt-neon-btn{min-height:26px;padding:3px 6px;font-size:10px;border-radius:7px}.pt-neon-grid.compact .pt-neon-btn ha-icon{--mdc-icon-size:15px}@media(max-width:500px){.pt-neon-grid{grid-template-columns:repeat(var(--pt-mobile-columns),minmax(0,1fr))}}'
+ '</style>';
this.querySelectorAll("[data-index]").forEach(button => {
button.onclick = () => this._run(Number(button.dataset.index), button);
});
}
async _run(index, element) {
const button = this._config.buttons[index] || {};
if (!this._hass || !button.service || !button.service.includes(".")) return;
if (button.confirmation && !window.confirm(button.confirmation)) return;
const split = button.service.split(".");
const domain = split.shift();
const service = split.join(".");
element.disabled = true;
try {
await this._hass.callService(domain, service, button.data || {}, button.target || {});
} catch (error) {
window.alert("Handlingen fejlede: " + String((error && error.message) || error));
} finally {
element.disabled = false;
}
}
getCardSize() { return Math.max(1, Math.ceil(this._config.buttons.length / (Number(this._config.columns) || 2))); }
static getConfigElement() { return document.createElement("tiny-family-neon-buttons-card-editor"); }
static getStubConfig() {
return {columns: 2, compact: false, buttons: [{name: "Handling", icon: "mdi:gesture-tap-button", service: "script.turn_on", data: {}}]};
}
}
customElements.define("tiny-family-neon-buttons-card", PersonTimelineNeonButtonsCard);
window.customCards = window.customCards || [];
window.customCards.push({type: "tiny-family-neon-buttons-card", name: "Tiny Family neon-knapper", description: "Små konfigurerbare Tiny Neon-knapper til handlinger og beskeder"});

class PersonTimelineNeonButtonsCardEditor extends HTMLElement {
setConfig(config) {
this._config = Object.assign({buttons: [], columns: 2, compact: false}, config || {});
this._render();
}
set hass(hass) { this._hass = hass; }
_fire() {
const event = new Event("config-changed", {bubbles: true, composed: true});
event.detail = {config: this._config};
this.dispatchEvent(event);
}
_setGeneral(key, value) {
this._config = Object.assign({}, this._config, {[key]: value});
this._fire();
}
_setButton(index, key, value) {
const buttons = (this._config.buttons || []).map((button, position) => position === index ? Object.assign({}, button, {[key]: value}) : button);
this._config = Object.assign({}, this._config, {buttons: buttons});
this._fire();
}
_input(label, value, onChange, placeholder) {
const wrap = document.createElement("label");
wrap.style.cssText = "display:flex;flex-direction:column;gap:4px;font-size:12px";
wrap.appendChild(document.createTextNode(label));
const input = document.createElement("input");
input.value = value || "";
input.placeholder = placeholder || "";
input.style.cssText = "padding:7px;border:1px solid var(--pt-outline,var(--divider-color));border-radius:7px;background:color-mix(in srgb,var(--pt-base,#fff) 88%,white 12%);color:var(--pt-text,var(--primary-text-color))";
input.onchange = () => onChange(input.value.trim());
wrap.appendChild(input);
return wrap;
}
_render() {
if (!this._config) return;
personTimelineTheme(this,this._hass);
this.innerHTML = "<style>"+PT_EDITOR_CSS+"</style>";
const root = document.createElement("div");
root.className="pte";
root.style.cssText = "display:flex;flex-direction:column;gap:12px;padding:8px 0";
const columns = this._input("Kolonner", String(this._config.columns || 2), value => this._setGeneral("columns", Math.max(1, Math.min(6, Number(value) || 2))), "2");
columns.querySelector("input").type = "number";
columns.querySelector("input").min = "1";
columns.querySelector("input").max = "6";
root.appendChild(columns);
const compactLabel = document.createElement("label");
compactLabel.style.cssText = "display:flex;align-items:center;gap:8px;font-size:14px";
const compact = document.createElement("input");
compact.type = "checkbox";
compact.checked = this._config.compact === true;
compact.onchange = () => this._setGeneral("compact", compact.checked);
compactLabel.append(compact, document.createTextNode("Brug altid kompakt visning"));
root.appendChild(compactLabel);
(this._config.buttons || []).forEach((button, index) => {
const box = document.createElement("div");
box.style.cssText = "display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:10px;border:1px solid var(--pt-outline,var(--divider-color));border-radius:10px";
box.appendChild(this._input("Navn", button.name, value => this._setButton(index, "name", value), "SOS"));
box.appendChild(this._input("Ikon", button.icon, value => this._setButton(index, "icon", value), "mdi:alarm-light"));
box.appendChild(this._input("Handling", button.service, value => this._setButton(index, "service", value), "script.turn_on"));
box.appendChild(this._input("Målenhed", button.target && button.target.entity_id, value => this._setButton(index, "target", value ? {entity_id: value} : {}), "script.eksempel"));
const toneLabel = document.createElement("label");
toneLabel.style.cssText = "display:flex;flex-direction:column;gap:4px;font-size:12px";
toneLabel.appendChild(document.createTextNode("Farve"));
const tone = document.createElement("select");
tone.style.cssText = "padding:7px;border:1px solid var(--pt-outline,var(--divider-color));border-radius:7px;background:color-mix(in srgb,var(--pt-base,#fff) 88%,white 12%);color:var(--pt-text,var(--primary-text-color))";
[["", "Cyan"], ["accent", "Lilla"], ["danger", "Rød"]].forEach(option => {
const node = document.createElement("option"); node.value = option[0]; node.textContent = option[1]; node.selected = (button.tone || "") === option[0]; tone.appendChild(node);
});
tone.onchange = () => this._setButton(index, "tone", tone.value);
toneLabel.appendChild(tone);
box.appendChild(toneLabel);
const confirmation = this._input("Bekræftelsestekst", button.confirmation, value => this._setButton(index, "confirmation", value), "Valgfri");
box.appendChild(confirmation);
const dataLabel = document.createElement("label");
dataLabel.style.cssText = "grid-column:1/-1;display:flex;flex-direction:column;gap:4px;font-size:12px";
dataLabel.appendChild(document.createTextNode("Handlingsdata (JSON)"));
const data = document.createElement("textarea");
data.rows = 3;
data.value = JSON.stringify(button.data || {}, null, 2);
data.style.cssText = "padding:7px;border:1px solid var(--pt-outline,var(--divider-color));border-radius:7px;background:color-mix(in srgb,var(--pt-base,#fff) 88%,white 12%);color:var(--pt-text,var(--primary-text-color));font-family:monospace";
data.onchange = () => {
try { this._setButton(index, "data", JSON.parse(data.value || "{}")); data.style.borderColor = ""; }
catch (error) { data.style.borderColor = "var(--error-color)"; }
};
dataLabel.appendChild(data);
box.appendChild(dataLabel);
const remove = document.createElement("button");
remove.textContent = "Fjern knap";
remove.style.cssText = "grid-column:1/-1;padding:7px;border:1px solid var(--error-color);border-radius:7px;background:transparent;color:var(--error-color);cursor:pointer";
remove.onclick = () => {
const buttons = this._config.buttons.filter((_, position) => position !== index);
this._config = Object.assign({}, this._config, {buttons: buttons});
this._render(); this._fire();
};
box.appendChild(remove);
root.appendChild(box);
});
const add = document.createElement("button");
add.textContent = "Tilføj knap";
add.style.cssText = "padding:9px;border:1px solid var(--primary-color);border-radius:8px;background:transparent;color:var(--primary-color);cursor:pointer";
add.onclick = () => {
this._config = Object.assign({}, this._config, {buttons: [...(this._config.buttons || []), {name: "Ny handling", icon: "mdi:gesture-tap-button", service: "script.turn_on", data: {}}]});
this._render(); this._fire();
};
root.appendChild(add);
this.appendChild(root);
}
}
customElements.define("tiny-family-neon-buttons-card-editor", PersonTimelineNeonButtonsCardEditor);

window.PersonTimelineTheme = Object.freeze({css:PT_NEON, editorCss:PT_EDITOR_CSS, apply:personTimelineTheme});
