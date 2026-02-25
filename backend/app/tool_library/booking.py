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
    additional_requirements = args.get("additional_requirements")

    # Get session info from meta
    session_id = meta.get("session_id", "")
    client_id = meta.get("client_id")

    # Query DB for matching users
    candidates = user_db.match(
        activity=activity,
        location=location,
        gender=gender_preference,
        limit=200,
    )

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

    # Create booking task
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
        additional_requirements=additional_requirements,
    )

    # Start background thread
    start_booking_task_thread(task, store)

    time_str = f" on {desired_time}" if desired_time else ""
    loc_str = f" in {location}" if location else ""

    message = (
        f"Got it! I'm now reaching out to people for {activity}{loc_str}{time_str}. "
        f"I found {len(candidates)} potential matches and will contact them "
        f"in batches of 10 until I've confirmed {headcount} "
        f"{'person' if headcount == 1 else 'people'}. "
        f"I'll let you know once everything is set up — sit tight!"
    )

    return (
        "booking",
        {
            "assistantMessage": message,
            "bookingTaskId": task.id,
            "status": "running",
            "candidateCount": len(candidates),
            "headcount": headcount,
        },
        {},
    )
