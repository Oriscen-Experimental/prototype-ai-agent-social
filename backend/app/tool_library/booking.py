"""
Booking tool: starts the full end-to-end booking flow.

Queries DB for matching users, creates a BookingTask,
and starts the background batch invitation loop.
"""

from __future__ import annotations

import logging
from typing import Any

from ..booking.runner import start_booking_task_thread
from ..booking.task_store import BookingTaskStore
from ..db import user_db

logger = logging.getLogger(__name__)

# These are set by main.py at startup
_booking_store: BookingTaskStore | None = None


def set_booking_store(store: BookingTaskStore) -> None:
    global _booking_store
    _booking_store = store


def get_booking_store() -> BookingTaskStore:
    if _booking_store is None:
        raise RuntimeError("BookingTaskStore not initialized")
    return _booking_store


def execute_start_booking(
    meta: dict[str, Any],
    args: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """
    Execute the start_booking tool.

    1. Query DB with hard constraints
    2. Create BookingTask
    3. Start background thread
    4. Return immediate confirmation to user

    Returns: (result_type, payload, last_results_payload)
    """
    store = get_booking_store()

    activity = args.get("activity", "")
    location = args.get("location", "")
    desired_time = args.get("desired_time")
    headcount = args.get("headcount", 3)
    gender_preference = args.get("gender_preference")
    level = args.get("level")
    pace = args.get("pace")
    availability_slots = args.get("availability_slots")
    additional_requirements = args.get("additional_requirements")

    # Get session info from meta
    session_id = meta.get("session_id", "")
    client_id = meta.get("client_id")

    # Query DB for matching users with enhanced filters
    candidates, match_stats = user_db.match(
        activity=activity,
        location=location,
        gender=gender_preference,
        level=level,
        pace=pace,
        availability_slots=availability_slots,
        headcount=headcount,
        limit=200,
    )

    # Get the selected time slot from match stats (all candidates share this slot)
    selected_slot = match_stats.get("selected_slot")

    if not candidates:
        return (
            "people",
            {
                "assistantMessage": (
                    f"I couldn't find any matching users for {activity} in {location}. "
                    "Could you try with different criteria or a broader location?"
                ),
            },
            {},
        )

    # Create booking task with dynamic slot narrowing
    task = store.create(
        session_id=session_id,
        client_id=client_id,
        activity=activity,
        location=location,
        desired_time=desired_time,
        headcount=headcount,
        candidates=candidates,
        gender_preference=gender_preference,
        level=level,
        pace=pace,
        availability_slots=availability_slots,
        additional_requirements=additional_requirements,
        match_stats=match_stats,
        selected_slot=selected_slot,
        current_slots=availability_slots,  # Initialize for dynamic narrowing
    )

    # Start background thread
    start_booking_task_thread(task, store)

    loc_str = f" in {location}" if location else ""

    # Build detailed match info for running
    is_running = activity.lower() in ("running", "run", "jog", "jogging")
    filter_desc = ""
    slot_info = ""
    if is_running:
        filters = []
        if level:
            filters.append(f"{level} level")
        if pace:
            filters.append(f"{pace} pace")
        if filters:
            filter_desc = f" ({', '.join(filters)})"

        # Show slot analysis (dynamic mode - no pre-selected slot)
        if availability_slots:
            slot_counts = match_stats.get("candidates_per_slot", {})
            slot_breakdown = ", ".join(
                f"{s.replace('_', ' ')}: {slot_counts.get(s, 0)}"
                for s in availability_slots
            )
            slot_names = [s.replace("_", " ") for s in availability_slots]
            slot_info = (
                f"\n📊 Availability breakdown: {slot_breakdown}\n"
                f"🔄 Will dynamically match on: {', '.join(slot_names)}"
            )

    # Show availability slots if no specific time given
    time_str = ""
    if desired_time:
        time_str = f" on {desired_time}"
    elif availability_slots:
        slot_names = [s.replace("_", " ") for s in availability_slots]
        time_str = f" ({', '.join(slot_names)})"

    message = (
        f"Got it! I found {len(candidates)} runners{filter_desc}{loc_str} that match your criteria."
        f"{slot_info}\n"
        f"Now reaching out in batches of 10 until I've confirmed {headcount} "
        f"{'person' if headcount == 1 else 'people'}{time_str}. "
        f"I'll keep you updated on the progress!"
    )

    return (
        "booking",
        {
            "assistantMessage": message,
            "bookingTaskId": task.id,
            "status": "running",
            "candidateCount": len(candidates),
            "headcount": headcount,
            "matchStats": match_stats,
            "filters": {
                "level": level,
                "pace": pace,
                "availabilitySlots": availability_slots,
                "desiredTime": desired_time,
            },
            "selectedSlot": selected_slot,  # None in dynamic mode, narrowed at runtime
            "initialSlots": availability_slots,  # User's original availability slots
        },
        {},
    )
