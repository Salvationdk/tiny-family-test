"""Canonical Tiny Family domain and persistent identifiers for version 0.8.4."""

DOMAIN = "tiny_family"
STATIC_URL = "/tiny_family_static"
CARD_VERSION = "0.8.4"
PLACES_FILE = "tiny_family_places.json"
SHARED_PLACES_FILE = "tiny_family_shared_places.json"
HISTORY_FILE = "tiny_family_historik.json"
HISTORY_KEY = f"{DOMAIN}_history"
HISTORY_MAX = 200
HISTORY_EXPOSE = 50
ZONE_SUGGEST_MIN_VISITS = 3


def default_road_matching_options(entry_data, entry_options):
    """Enable built-in matching once for legacy untouched defaults.

    Older config flows saved a hard-coded False in entry.data. An explicit
    admin selection, including False, is stored in entry.options and wins.
    Return None if that selection already exists; never overwrite it.
    """
    if "map_matching_enabled" in entry_options:
        return None
    options = dict(entry_options)
    options["map_matching_enabled"] = True
    options.setdefault("map_matching_backend", "builtin")
    return options
