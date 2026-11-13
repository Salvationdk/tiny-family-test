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

// Map the timeline camera in a *single* bounded setView. The pin stays at
// the real measurement while the camera offsets it above the mobile dock.
const validStart=panel.indexOf("const validMapPoint=");
const validEnd=panel.indexOf("const chooseMode=",validStart);
const moveStart=panel.indexOf("const moveTimelineMarker=");
const moveEnd=panel.indexOf("const focusEventObservation=",moveStart);
assert(validStart>0&&validEnd>validStart&&moveStart>0&&moveEnd>moveStart);
const mobileCamera=new Function("window","document","dockPerson","mapElement","dock","map",
  panel.slice(validStart,validEnd)+
  "let activeMap=map,timelineMarker=null,previousCenteredFix=null;"+
  panel.slice(moveStart,moveEnd)+
  "return {move:moveTimelineMarker,getMarker:()=>timelineMarker};");
const views=[];
let pin=null;
const fakeMap={
  getZoom:()=>undefined,
  project:loc=>({x:loc[1]*100,y:loc[0]*100}),
  unproject:coords=>({lat:coords[1]/100,lng:coords[0]/100}),
  setView:(loc,zoom)=>views.push({loc,zoom}),
  panTo:()=>assert.fail("Camera must not pan separately"),
  panBy:()=>assert.fail("Camera must not accumulate pixel offsets")
};
const fakeWindow={
  matchMedia:()=>({matches:true}),
  L:{
    divIcon:()=>({}),
    marker:(loc)=>{
      pin={loc,setLatLng(next){this.loc=next;},addTo(){return this;}};
      return pin;
    }
  }
};
const camera=mobileCamera(fakeWindow,{createElement:()=>({style:{},outerHTML:"pin"})},
  {options:[{value:"a",textContent:"Nicolaj Rusbjerg"}],value:"a"},
  {getBoundingClientRect:()=>({top:0,bottom:900,height:900})},
  {getBoundingClientRect:()=>({top:500})},fakeMap);
camera.move([55.1,12.2]);
assert.deepEqual(camera.getMarker().loc,[55.1,12.2]);
assert.equal(views[0].zoom,15,"Uninitialized zoom must never become NaN");
assert(views[0].loc[0]>55.1,"Mobile map centre must sit below the badge");
camera.move([55.1001,12.2001]);
assert.equal(views.length,2);
camera.move([NaN,12.4]);
camera.move([95,12.4]);
assert.equal(views.length,2,"Invalid or off-world fixes must not shift tiles");

// Guard the vendored Leaflet grid layer: an invalid or unbounded tile range
// must not bubble the red Home Assistant "infinite number of tiles" error.
const tileStart=panel.indexOf("const updateTiles=layer._update;");
const tileEnd=panel.indexOf("let retryCount=0;",tileStart);
assert(tileStart>0&&tileEnd>tileStart);
const guardTileLayer=new Function("layer",panel.slice(tileStart,tileEnd));
let tileCalls=0;
const tileLayer={
  _map:{getZoom:()=>15,getCenter:()=>({lat:55,lng:12})},
  _tileZoom:15,
  _update(){tileCalls++;},
  _getTiledPixelBounds:()=>({}),
  _pxBoundsToTileRange:()=>({min:{x:1,y:2},max:{x:6,y:8}})
};
guardTileLayer(tileLayer);
tileLayer._update();
assert.equal(tileCalls,1);
tileLayer._pxBoundsToTileRange=()=>({min:{x:-Infinity,y:2},max:{x:6,y:8}});
tileLayer._update();
assert.equal(tileCalls,1,"Infinite tile bounds must be discarded");
tileLayer._pxBoundsToTileRange=()=>({min:{x:1,y:2},max:{x:200,y:8}});
tileLayer._update();
assert.equal(tileCalls,1,"Unbounded tile counts must be discarded");

console.log("Timeline geometry, centred playback and tile safety tests passed");
