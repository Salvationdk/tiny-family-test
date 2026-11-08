"""Shared, dependency-free value helpers."""

import math


def _hav(a, b, c, d):
    r = 6371000.0
    s1 = math.sin(math.radians(c - a) / 2)
    s2 = math.sin(math.radians(d - b) / 2)
    q = s1 * s1 + math.cos(math.radians(a)) * math.cos(math.radians(c)) * s2 * s2
    return 2 * r * math.asin(math.sqrt(max(0.0, min(1.0, q))))


def _slug(person):
    return person.split(".", 1)[1]


def _sensor(entity, value, attrs):
    # HA uses None for an unknown sensor value. Stringifying None as "None"
    # breaks registered numeric entities (ETA, GPS age) on initial setup.
    return (entity, None if value is None else str(value), dict(attrs))


def _pretty(person):
    return person.split(".", 1)[1].replace("_", " ").title()
