"""Restart-tolerant per-person weekly distance and Monday report bookkeeping."""
from __future__ import annotations

from datetime import datetime


def week_key(now: datetime) -> str:
    if now.tzinfo is None:
        raise ValueError("Local aware datetime required")
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def rollover(state: dict, local_now: datetime) -> bool:
    """Copy completed week before clearing totals; no duplicate rollovers."""
    key=week_key(local_now)
    old=state.get("week")
    if old is None:
        state["week"]=key
        state.setdefault("totals",{})
        return True
    if key==old:
        return False
    state["pending"]={"week":old,"totals":dict(state.get("totals") or {})}
    state["totals"]={}
    state["week"]=key
    return True


def increment(state: dict, person: str, distance_m: float) -> None:
    if not (0 < distance_m < 50000):
        return
    totals=state.setdefault("totals",{})
    totals[person]=round(float(totals.get(person,0)) + distance_m, 2)


def due_reports(state: dict, local_now: datetime) -> list[tuple[str,float]]:
    """Exactly once on Monday 08:00 or later; checkpoint before notifications.

    If HA was down at 08:00, report at the next scheduled run Monday.
    """
    rollover(state,local_now)
    if local_now.weekday()!=0 or local_now.hour<8:
        return []
    pending=state.get("pending") or {}
    week=pending.get("week")
    if not week or state.get("sent_week")==week:
        return []
    state["sent_week"]=week
    return [(person,round(float(metres)/1000,1))
            for person,metres in (pending.get("totals") or {}).items()]
