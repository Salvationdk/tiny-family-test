"""Optional local routine analysis. No coordinates and no cloud processing."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median

MAX_SAMPLES_PER_PERSON = 80
RETENTION_DAYS = 60
MIN_OBSERVATIONS = 3
MAX_VARIATION_MIN = 45


def prune_records(data: dict, now: datetime, *, selected_people: set | None = None) -> bool:
    """Retain at most 60 days and 80 samples per opted-in person."""
    cutoff = (now - timedelta(days=RETENTION_DAYS)).timestamp()
    before = {k: list(v) if isinstance(v, list) else v
              for k, v in data.items()}
    for person in list(data):
        if selected_people is not None and person not in selected_people:
            data.pop(person, None)
            continue
        records = data.get(person)
        if not isinstance(records, list):
            data.pop(person, None)
            continue
        valid = [row for row in records if isinstance(row, dict) and
                 isinstance(row.get("timestamp"), (int, float)) and
                 cutoff <= row["timestamp"] <= now.timestamp() + 60 and
                 isinstance(row.get("minutes"), (int, float)) and
                 0 <= row["minutes"] < 1440 and
                 isinstance(row.get("weekday"), int) and
                 0 <= row["weekday"] <= 6]
        if valid:
            data[person] = valid[-MAX_SAMPLES_PER_PERSON:]
        else:
            data.pop(person, None)
    return data != before


def record_departure(data: dict, person: str, departure: datetime,
                     *, now: datetime | None = None):
    """Store local weekday/time only, with one observation per local date.

    Raw GPS coordinates, tracking devices and trip routes are never persisted.
    """
    if departure.tzinfo is None:
        raise ValueError("Departure requires an aware datetime")
    now = now or datetime.now(timezone.utc)
    prune_records(data, now)
    local_day = departure.date().isoformat()
    records = data.get(person, [])
    if any(row.get("local_date") == local_day for row in records):
        return typical_departure(data, person, departure.weekday())
    records.append({
        "timestamp": departure.timestamp(),
        "local_date": local_day,
        "weekday": departure.weekday(),
        "minutes": departure.hour * 60 + departure.minute,
    })
    data[person] = records[-MAX_SAMPLES_PER_PERSON:]
    return typical_departure(data, person, departure.weekday())


def typical_departure(data: dict, person: str, weekday: int) -> dict | None:
    """Infer a repeatable local departure from distinct dates, never a promise."""
    rows = [row for row in data.get(person, []) if isinstance(row, dict) and
            row.get("weekday") == weekday and
            isinstance(row.get("minutes"), (float, int))]
    if len(rows) < MIN_OBSERVATIONS:
        return None
    # Old stored records lack local_date; use timestamp as independent fallback.
    distinct = {}
    for row in rows:
        key = row.get("local_date") or row.get("timestamp")
        if key is not None:
            distinct[key] = row
    if len(distinct) < MIN_OBSERVATIONS:
        return None
    minutes = [r["minutes"] for r in distinct.values()]
    typical = median(minutes)
    if max(abs(m - typical) for m in minutes) > MAX_VARIATION_MIN:
        return None
    minute = round(typical)
    return {"weekday": weekday, "time": f"{minute//60:02d}:{minute%60:02d}",
            "observations": len(minutes),
            "confidence": min(1.0, len(minutes) / 6.0)}


def clear_person(data: dict, person: str) -> None:
    """Immediately discard this person's locally learned patterns."""
    data.pop(person,None)
