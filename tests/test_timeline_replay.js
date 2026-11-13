/* Exercise the browser's own playback geometry without a Home Assistant DOM. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const panel = fs.readFileSync(path.join(__dirname,
  "../custom_components/tiny_family/frontend/tiny-family-panel.js"), "utf8");
const start = panel.indexOf("const projectedRoadPoint=");
const end = panel.indexOf("const updateCursor=", start);
assert(start >= 0 && end > start, "Timeline geometry helpers missing");
const factory = new Function("roadMatchToggle", "timelineData",
  panel.slice(start, end) + "\nreturn playbackLocation;");

// A right-angle road: raw interpolation would cut the corner, while real
// route replay must travel along the actual snapped street geometry.
const route = [[55.0, 12.0], [55.0, 12.001], [55.001, 12.001]];
const fixA = {t: 1000, lat: 55.0, lon: 12.0};
const fixB = {t: 1060, lat: 55.001, lon: 12.001};
const matched = factory({checked:true}, {matched_segments:[{
  start_t:1000, end_t:1060, coordinates:route
}]});
const midpoint = matched(fixA, fixB, 1030);
assert(Math.abs(midpoint[1] - 12.001) < .00001,
  "Playback should follow the street corner before continuing north");
assert(midpoint[0] > 55.0 && midpoint[0] < 55.001);

// Bad/missing road data falls back to real fixes, never interpolating across
// large gaps in observations.
const raw = factory({checked:false}, {matched_segments:[]});
const rawMidpoint = raw(fixA, fixB, 1030);
assert(Math.abs(rawMidpoint[0] - 55.0005) < 1e-9);
assert(Math.abs(rawMidpoint[1] - 12.0005) < 1e-9);
assert.deepEqual(raw(fixA, {...fixB,t:1200}, 1100), [55.0, 12.0]);

// Event selection must prefer a fix inside the event rather than the first
// minute (which may have no GPS). Anchors are a transparent fallback only.
const focusStart=panel.indexOf("const focusEventObservation=");
const focusEnd=panel.indexOf("const inferredLocation=",focusStart);
assert(focusStart>=0 && focusEnd>focusStart,"Event focus helper is missing");
const focusEvent=new Function(panel.slice(focusStart,focusEnd)+
  "\nreturn focusEventObservation;")();
const event={started_at:1000,ended_at:1500,start_lat:55.0,start_lon:12.0};
const focused=focusEvent(event,[[{t:1450,lat:55.5,lon:12.5},
  {t:1410,lat:55.4,lon:12.4}]]);
assert.equal(focused.source,"gps");
assert.deepEqual(focused.point,[55.4,12.4]);
assert.equal(focusEvent(event,[]).source,"anchor");
assert.deepEqual(focusEvent(event,[]).point,[55.0,12.0]);
assert.equal(focusEvent({started_at:1000,ended_at:1500},[]),null,
  "Never invent a location for a time-only old event");

console.log("Timeline road-follow and GPS-gap replay tests passed");
