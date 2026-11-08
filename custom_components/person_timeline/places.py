"""Place detection, zone recognition and destination prediction."""

from datetime import datetime

from .const import DOMAIN, ZONE_SUGGEST_MIN_VISITS
from .utils import _hav


def _nearest_zone_label(hass, lat, lon):
    best = None
    for zone in hass.states.async_all("zone"):
        zla, zlo = zone.attributes.get("latitude"), zone.attributes.get("longitude")
        if zla is None or zlo is None:
            continue
        d = _hav(lat, lon, float(zla), float(zlo))
        radius = float(zone.attributes.get("radius") or 25)
        if d <= radius + 10 and (best is None or d < best[0]):
            best = (d, zone.attributes.get("friendly_name") or zone.entity_id)
    return best[1] if best else ""


def _seed_zones(hass, person):
    """Known zones are destinations from the start; new places are learned from stays."""
    st = hass.data[DOMAIN][person]
    st["seeded"] = True
    places = st.setdefault("places", [])
    for zone in hass.states.async_all("zone"):
        zla, zlo = zone.attributes.get("latitude"), zone.attributes.get("longitude")
        if zla is None or zlo is None:
            continue
        if any(abs(p["lat"] - float(zla)) < 1e-4 and abs(p["lon"] - float(zlo)) < 1e-4
               for p in places):
            continue
        places.append({"lat": float(zla), "lon": float(zlo),
                       "label": zone.attributes.get("friendly_name") or zone.entity_id,
                       "visits": 0, "min": 0, "n": 0, "last": "", "source": "zone"})


def _record_place(hass, person, lat, lon, mins):
    """Learn where a stay happened; merged into a nearby place when one exists."""
    st = hass.data[DOMAIN][person]
    places = st.setdefault("places", [])
    best = None
    for pl in places:
        d = _hav(pl["lat"], pl["lon"], lat, lon)
        if d <= 25 and (best is None or d < best[0]):
            best = (d, pl)
    if best is not None:
        pl = best[1]
        n = pl.get("n", 0)
        if n > 0 and pl.get("source") != "zone":
            pl["lat"] = (pl["lat"] * n + lat) / (n + 1)
            pl["lon"] = (pl["lon"] * n + lon) / (n + 1)
        pl["n"] = n + 1
        pl["visits"] = pl.get("visits", 0) + 1
        pl["min"] = pl.get("min", 0) + mins
        pl["last"] = datetime.now().isoformat(timespec="seconds")
    else:
        places.append({"lat": lat, "lon": lon,
                       "label": _nearest_zone_label(hass, lat, lon),
                       "visits": 1, "min": mins, "n": 1,
                       "last": datetime.now().isoformat(timespec="seconds"), "source": "learned"})


def _predict(st):
    """Predict only from repeated, plausible approach toward a known place.

    Confidence is a heuristic, never a probability or promised arrival time.
    Return type remains (place, distance_m) for backwards compatibility.
    """
    st["destination_confidence"] = 0.0
    recent = st.get("recent") or []
    if len(recent) < 3:
        return None
    t_now, lat, lon = recent[-1]
    base = next(((bla, blo) for t, bla, blo in recent
                 if 120 <= t_now - t <= 900), None)
    if base is None:
        return None
    bla, blo = base
    travel = _hav(bla, blo, lat, lon)
    if travel < 180:
        return None
    best = None
    # Explicitly shared family places also count as known destinations.
    # They do not enter personal visit histories or private learning records.
    family_places = []
    for shared in st.get("family_places") or []:
        if isinstance(shared, dict):
            family_places.append({
                "lat": shared.get("latitude"), "lon": shared.get("longitude"),
                "label": shared.get("name"), "visits": 0,
            })
    for place in list(st.get("places") or []) + family_places:
        try:
            d_now = _hav(lat, lon, place["lat"], place["lon"])
            d_before = _hav(bla, blo, place["lat"], place["lon"])
        except (KeyError, ValueError, TypeError):
            continue
        if not 150 <= d_now <= 150000:
            continue
        approach = d_before - d_now
        direction = approach / travel
        # At least 250m closer and most of the net motion toward the place.
        if approach < 250 or direction < 0.55:
            continue
        visits = max(0, place.get("visits") or 0)
        confidence = min(0.95, 0.42 + min(0.26, direction * 0.26)
                         + min(0.12, visits * 0.03)
                         + min(0.12, approach / 20000))
        if confidence < 0.60:
            continue
        # High visit counts help only modestly; avoid selecting a very
        # distant frequently visited location over the nearer target.
        score = confidence - min(0.30, d_now / 500000)
        if best is None or score > best[0]:
            best = (score, place, d_now, confidence)
    if best is None:
        return None
    st["destination_confidence"] = round(best[3], 2)
    return best[1], best[2]


def estimate_destination_eta(distance_m: float, speed_mps: float) -> int | None:
    """Coarse ETA only for plausible observed speeds and nearby destinations."""
    import math
    if (not all(isinstance(value,(int,float)) and math.isfinite(value)
                for value in (distance_m,speed_mps))
            or not 150 <= distance_m <= 150000
            or not 2.2 <= speed_mps <= 40):
        return None
    minutes=round(distance_m*1.25/speed_mps/60)
    return minutes if 1 <= minutes <= 360 else None


def estimate_home_eta(st: dict, latitude: float, longitude: float,
                      home_latitude: float, home_longitude: float,
                      speed_mps: float) -> int | None:
    """Return a cautious arrival estimate only while approaching home.

    This is based on observed GPS movement and crow-flight distance. Without
    route information it is not a navigation ETA or guaranteed arrival time.
    """
    import math
    recent = st.get("recent") or []
    if len(recent) < 3 or not all(math.isfinite(v) for v in (
        latitude, longitude, home_latitude, home_longitude, speed_mps
    )) or not 2.2 <= speed_mps <= 40:
        return None
    now = recent[-1][0]
    previous = next(((lat, lon) for t, lat, lon in recent
                     if 120 <= now - t <= 600), None)
    if previous is None:
        return None
    old_distance = _hav(previous[0], previous[1],
                        home_latitude, home_longitude)
    distance = _hav(latitude, longitude, home_latitude, home_longitude)
    if not 200 <= distance <= 150000:
        return None
    approach = old_distance - distance
    travel = _hav(previous[0], previous[1], latitude, longitude)
    if approach < 100 or travel < 100 or approach / travel < 0.6:
        return None
    # Road distance often exceeds a straight line; label the result a
    # coarse estimate rather than presenting it as exact navigation.
    minutes = round((distance * 1.25) / speed_mps / 60)
    return min(360, max(1, minutes)) if 1 <= minutes <= 360 else None


def _zone_candidates(hass, places):
    """Learned places outside every zone, visited often enough to be worth a zone."""
    zones = []
    for zone in hass.states.async_all("zone"):
        zla, zlo = zone.attributes.get("latitude"), zone.attributes.get("longitude")
        if zla is None or zlo is None:
            continue
        zones.append((float(zla), float(zlo), float(zone.attributes.get("radius") or 100)))
    out = []
    for pl in places or []:
        if pl.get("visits", 0) < ZONE_SUGGEST_MIN_VISITS:
            continue
        if any(_hav(pl["lat"], pl["lon"], zla, zlo) <= radius + 10
               for (zla, zlo, radius) in zones):
            continue
        label = (pl.get("label") or "").strip()
        if label and label.lower() not in ("ukendt sted", "unknown", "ukendt"):
            continue
        out.append({"navn": label or "ukendt sted",
                    "besoeg": pl.get("visits", 0),
                    "minutter": pl.get("min", 0),
                    "lat": round(float(pl["lat"]), 6), "lon": round(float(pl["lon"]), 6),
                    "label": label})
    out.sort(key=lambda item: item["besoeg"], reverse=True)
    return out
