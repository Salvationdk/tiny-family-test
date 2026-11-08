"""Stable runtime identifiers; keep the existing entity domain for compatibility."""

DOMAIN = "person_timeline"
STATIC_URL = "/person_timeline_static"
CARD_VERSION = "0.6.7"
PLACES_FILE = "person_timeline_places.json"
HISTORY_FILE = "person_timeline_historik.json"
HISTORY_KEY = f"{DOMAIN}_history"
HISTORY_MAX = 200
HISTORY_EXPOSE = 50
ZONE_SUGGEST_MIN_VISITS = 3
