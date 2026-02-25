"""Resolve abstract slot names to concrete date + time windows."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta
from typing import NamedTuple


class ResolvedSlot(NamedTuple):
    """Concrete date + time window for a resolved slot."""

    slot_name: str  # Original slot e.g. "weekday_morning"
    date: date  # Concrete date
    start_time: time  # Start of 2-hour window
    end_time: time  # End of 2-hour window
    formatted: str  # Human-readable: "Thu, Feb 27, 7:00 AM – 9:00 AM"
    iso_start: str  # ISO datetime string for start
    iso_end: str  # ISO datetime string for end


# Slot definitions: (start_hour, start_minute, end_hour, end_minute, is_weekend)
SLOT_DEFINITIONS: dict[str, tuple[int, int, int, int, bool]] = {
    "weekday_morning": (7, 0, 9, 0, False),
    "weekday_lunch": (12, 0, 14, 0, False),
    "weekday_evening": (18, 0, 20, 0, False),
    "weekend_morning": (8, 0, 10, 0, True),
    "weekend_afternoon": (14, 0, 16, 0, True),
}

SF_RUNNING_LOCATIONS = [
    "Golden Gate Park (Main Trail)",
    "Embarcadero Waterfront",
    "Crissy Field",
    "Lands End Trail",
    "Lake Merced Loop",
]


def _next_occurrence(today: date, now_time: time, slot_name: str) -> date:
    """Find the next date for a given slot, skipping today if time has passed."""
    defn = SLOT_DEFINITIONS.get(slot_name)
    if defn is None:
        return today + timedelta(days=1)

    sh, _sm, _eh, _em, is_weekend = defn
    slot_start = time(sh, 0)

    for offset in range(0, 8):  # Check today + next 7 days
        candidate = today + timedelta(days=offset)
        day_of_week = candidate.weekday()  # 0=Mon ... 6=Sun
        is_candidate_weekend = day_of_week >= 5  # 5=Sat, 6=Sun

        if is_weekend != is_candidate_weekend:
            continue

        # If it's today, check if the time window has already passed
        if offset == 0 and now_time >= slot_start:
            continue

        return candidate

    # Fallback: should never reach here
    return today + timedelta(days=7)


def _format_time(t: time) -> str:
    """Format time as '7:00 AM' (no leading zero)."""
    hour = t.hour
    minute = t.minute
    ampm = "AM" if hour < 12 else "PM"
    display_hour = hour if hour <= 12 else hour - 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour}:{minute:02d} {ampm}"


def _format_datetime(d: date, start: time, end: time) -> str:
    """Format as 'Thu, Feb 27, 7:00 AM – 9:00 AM'."""
    day_abbr = d.strftime("%a")
    month_abbr = d.strftime("%b")
    day_num = d.day
    start_str = _format_time(start)
    end_str = _format_time(end)
    return f"{day_abbr}, {month_abbr} {day_num}, {start_str} – {end_str}"


def resolve_slot(slot_name: str, now: datetime | None = None) -> ResolvedSlot:
    """Resolve a single abstract slot to a concrete date + time."""
    if now is None:
        now = datetime.now()

    today = now.date()
    now_time = now.time()

    defn = SLOT_DEFINITIONS.get(slot_name)
    if defn is None:
        # Unknown slot — return a reasonable default (tomorrow 9-11 AM)
        target_date = today + timedelta(days=1)
        s, e = time(9, 0), time(11, 0)
        return ResolvedSlot(
            slot_name=slot_name,
            date=target_date,
            start_time=s,
            end_time=e,
            formatted=_format_datetime(target_date, s, e),
            iso_start=datetime.combine(target_date, s).isoformat(),
            iso_end=datetime.combine(target_date, e).isoformat(),
        )

    sh, sm, eh, em, _is_weekend = defn
    start = time(sh, sm)
    end = time(eh, em)
    target_date = _next_occurrence(today, now_time, slot_name)

    return ResolvedSlot(
        slot_name=slot_name,
        date=target_date,
        start_time=start,
        end_time=end,
        formatted=_format_datetime(target_date, start, end),
        iso_start=datetime.combine(target_date, start).isoformat(),
        iso_end=datetime.combine(target_date, end).isoformat(),
    )


def pick_nearest_slot(slots: list[str], now: datetime | None = None) -> ResolvedSlot:
    """From a list of abstract slots, resolve each and return the closest to now."""
    if not slots:
        return resolve_slot("weekday_morning", now)

    resolved = [resolve_slot(s, now) for s in slots]
    resolved.sort(key=lambda r: (r.date, r.start_time))
    return resolved[0]


def pick_location(task_id: str) -> str:
    """Pick a specific SF running location deterministically based on task ID."""
    idx = int(hashlib.md5(task_id.encode()).hexdigest(), 16) % len(SF_RUNNING_LOCATIONS)
    return SF_RUNNING_LOCATIONS[idx]
