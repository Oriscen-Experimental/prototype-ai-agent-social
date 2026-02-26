"""
Cancel booking tool: initiates the cancel flow for a completed booking.

Two-phase interactive flow:
  Phase 1 (no intention): Ask user whether to reschedule or leave.
  Phase 2 (intention set): Start the appropriate background runner.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from ..booking.task_store import BookingTaskStore

logger = logging.getLogger(__name__)

_booking_store: BookingTaskStore | None = None


def set_booking_store(store: BookingTaskStore) -> None:
    global _booking_store
    _booking_store = store


def get_booking_store() -> BookingTaskStore:
    if _booking_store is None:
        raise RuntimeError("BookingTaskStore not initialized")
    return _booking_store


def execute_cancel_booking(
    meta: dict[str, Any],
    args: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """
    Entry point for the cancel_booking tool.

    Returns: (result_type, payload, last_results_payload)
    """
    # Lazy import to avoid circular dependency at module level
    from ..booking.cancel_runner import start_cancel_flow_thread

    store = get_booking_store()
    session_id = meta.get("session_id", "")
    client_id = meta.get("client_id")

    task_id = args.get("task_id", "")
    intention = args.get("intention")
    cancel_flow_id = args.get("cancel_flow_id")

    # Validate the booking task exists and is completed
    task = store.get(task_id)
    if task is None:
        return (
            "cancel_booking",
            {
                "assistantMessage": (
                    "I couldn't find that booking. Could you check the booking ID?"
                ),
            },
            {},
        )

    if task.status not in ("completed", "running"):
        return (
            "cancel_booking",
            {
                "assistantMessage": (
                    f"This booking is currently '{task.status}' and cannot be cancelled."
                ),
            },
            {},
        )

    # ------------------------------------------------------------------
    # Running bookings: direct cancellation (no reschedule/leave flow)
    # ------------------------------------------------------------------
    if task.status == "running":
        import time as _time

        task.status = "cancelled"
        accepted_count = len(task.accepted_users)
        if accepted_count > 0:
            names = [u.get("nickname", "Someone") for u in task.accepted_users]
            names_str = ", ".join(names[:5])
            msg = (
                f"I've cancelled the {task.activity} booking. "
                f"{accepted_count} participant(s) had already confirmed ({names_str}), "
                f"and they will be notified. "
                f"Would you like to start a new booking with different criteria?"
            )
        else:
            msg = (
                f"I've cancelled the {task.activity} booking. "
                f"No participants had confirmed yet. "
                f"Would you like to start a new booking?"
            )
        task.notifications.append({
            "type": "booking_cancelled",
            "message": msg,
            "bookingTaskId": task.id,
            "timestamp": _time.time(),
        })
        return (
            "cancel_booking",
            {"assistantMessage": msg},
            {},
        )

    # ------------------------------------------------------------------
    # Completed bookings: two-phase interactive flow
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Phase 1: No intention yet -> create CancelFlow and ask the user
    # ------------------------------------------------------------------
    if not intention:
        existing = store.get_cancel_flow_by_task(task_id)
        if existing and existing.status == "awaiting_intention":
            flow = existing
        else:
            flow = store.create_cancel_flow(
                task_id=task_id,
                session_id=session_id,
                cancelling_user_id=client_id or "",
            )
            task.cancel_flow_id = flow.id

        return (
            "cancel_booking",
            {
                "assistantMessage": "I understand you want to cancel this booking.",
                "cancelFlowId": flow.id,
                "taskId": task_id,
                "status": "awaiting_intention",
                "requiresInput": True,
                "options": [
                    {"label": "Reschedule with the group", "value": "reschedule"},
                    {"label": "Leave this booking entirely", "value": "leave"},
                ],
            },
            {},
        )

    # ------------------------------------------------------------------
    # Phase 2: Intention provided -> start background flow
    # ------------------------------------------------------------------
    flow = None
    if cancel_flow_id:
        flow = store.get_cancel_flow(cancel_flow_id)
    if flow is None:
        flow = store.get_cancel_flow_by_task(task_id)
    if flow is None:
        flow = store.create_cancel_flow(
            task_id=task_id,
            session_id=session_id,
            cancelling_user_id=client_id or "",
        )
        task.cancel_flow_id = flow.id

    if intention not in ("reschedule", "leave"):
        return (
            "cancel_booking",
            {
                "assistantMessage": "Please choose either 'reschedule' or 'leave'.",
                "cancelFlowId": flow.id,
                "taskId": task_id,
                "status": "awaiting_intention",
            },
            {},
        )

    flow.intention = intention  # type: ignore[assignment]

    # Populate remaining_participants (everyone except the cancelling user)
    flow.remaining_participants = [
        u for u in task.accepted_users if u.get("id") != flow.cancelling_user_id
    ]

    # Compute backfill deadline: 30 minutes before booked event start
    if task.booked_iso_start:
        try:
            event_start = datetime.fromisoformat(task.booked_iso_start)
            flow.backfill_deadline = (event_start - timedelta(minutes=30)).timestamp()
        except ValueError:
            flow.backfill_deadline = 0.0

    # Record excluded slots for the leave path (so the re-booking avoids them)
    if intention == "leave" and task.current_slots:
        flow.excluded_slots = list(task.current_slots)

    # Start background thread
    start_cancel_flow_thread(flow, task, store)

    if intention == "reschedule":
        flow.status = "reschedule_polling"  # type: ignore[assignment]
        msg = (
            f"Got it! I'm now asking the other {len(flow.remaining_participants)} "
            f"participant(s) if they can accommodate a time change. "
            f"I'll keep you posted on their responses."
        )
    else:
        flow.status = "leave_backfill_prompt"  # type: ignore[assignment]
        msg = (
            f"Understood. I've removed you from this booking. "
            f"I'm now checking with the remaining {len(flow.remaining_participants)} "
            f"participant(s) about finding a replacement, and simultaneously "
            f"searching for a new match for you."
        )

    return (
        "cancel_booking",
        {
            "assistantMessage": msg,
            "cancelFlowId": flow.id,
            "taskId": task_id,
            "status": flow.status,
        },
        {},
    )
