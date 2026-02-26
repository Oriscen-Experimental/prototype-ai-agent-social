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


def _phase1_response(
    flow_id: str, task_id: str
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Return the Phase 1 (awaiting_intention) response asking user to choose."""
    return (
        "cancel_booking",
        {
            "assistantMessage": "I understand you want to cancel this booking.",
            "cancelFlowId": flow_id,
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

    logger.info(
        "[cancel] execute_cancel_booking entry task_id=%s intention=%s "
        "cancel_flow_id=%s session_id=%s client_id=%s",
        task_id, intention, cancel_flow_id, session_id, client_id,
    )

    # Validate the booking task exists and is completed
    task = store.get(task_id)
    if task is None:
        logger.info("[cancel] task_not_found task_id=%s", task_id)
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
        logger.info("[cancel] task_status_invalid task_id=%s status=%s", task_id, task.status)
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

        logger.info(
            "[cancel] direct_cancel_running task_id=%s accepted=%d",
            task_id, len(task.accepted_users),
        )
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
            logger.info("[cancel] phase1 reusing_existing_flow flow_id=%s", flow.id)
        else:
            flow = store.create_cancel_flow(
                task_id=task_id,
                session_id=session_id,
                cancelling_user_id=client_id or "",
            )
            task.cancel_flow_id = flow.id
            logger.info("[cancel] phase1 created_new_flow flow_id=%s", flow.id)

        return _phase1_response(flow.id, task_id)

    # ------------------------------------------------------------------
    # Phase 2: Intention provided -> start background flow
    # ------------------------------------------------------------------
    flow = None
    if cancel_flow_id:
        flow = store.get_cancel_flow(cancel_flow_id)
    if flow is None:
        flow = store.get_cancel_flow_by_task(task_id)

    logger.info(
        "[cancel] phase2 flow_resolved flow_id=%s flow_status=%s",
        flow.id if flow else None, flow.status if flow else None,
    )

    # KEY FIX: If no active flow exists (previous flow completed/failed,
    # or never existed), this is a FRESH cancel request. Always go through
    # Phase 1 regardless of whether the planner pre-filled an intention.
    # This ensures the user gets the reschedule/leave choice every time.
    if flow is None or flow.status in ("completed", "failed"):
        logger.info("[cancel] phase2 fresh_cancel_detected -> redirect to phase1")
        flow = store.create_cancel_flow(
            task_id=task_id,
            session_id=session_id,
            cancelling_user_id=client_id or "",
        )
        task.cancel_flow_id = flow.id
        return _phase1_response(flow.id, task_id)

    if intention not in ("reschedule", "leave"):
        logger.info("[cancel] invalid_intention=%s flow_id=%s", intention, flow.id)
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
    logger.info("[cancel] intention_set flow_id=%s intention=%s", flow.id, intention)

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

    if intention == "reschedule":
        logger.info(
            "[cancel] reschedule_path flow_id=%s remaining_participants=%d",
            flow.id, len(flow.remaining_participants),
        )
        # Start full cancel flow (reschedule) in background
        start_cancel_flow_thread(flow, task, store)

        flow.status = "reschedule_polling"  # type: ignore[assignment]
        msg = (
            f"Got it! I'm now asking the other {len(flow.remaining_participants)} "
            f"participant(s) if they can accommodate a time change. "
            f"I'll keep you posted on their responses."
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

    # ------------------------------------------------------------------
    # Leave path: synchronous rebook + background backfill
    # ------------------------------------------------------------------
    from ..booking.cancel_runner import start_backfill_only_thread
    from ..db import user_db
    from .booking import execute_start_booking

    logger.info(
        "[cancel] leave_path flow_id=%s remaining_participants=%d",
        flow.id, len(flow.remaining_participants),
    )
    flow.status = "leave_backfill_prompt"  # type: ignore[assignment]

    # Actually remove the cancelling user from the booking
    task.accepted_users = list(flow.remaining_participants)

    # Synchronous rebook: call the same function as the initial booking
    rebook_payload: dict[str, Any] | None = None
    if flow.excluded_slots:
        user_record = user_db.get_user(flow.cancelling_user_id)
        original_availability = list(user_record.availability) if user_record else []
        new_availability = [
            s for s in original_availability if s not in set(flow.excluded_slots)
        ]

        logger.info(
            "[cancel] leave_rebook excluded_slots=%s original=%d new_availability=%d",
            flow.excluded_slots, len(original_availability), len(new_availability),
        )
        if new_availability:
            rebook_meta = {"session_id": session_id, "client_id": client_id}
            rebook_args = {
                "activity": task.activity,
                "location": task.location,
                "headcount": task.headcount,
                "gender_preference": task.gender_preference,
                "level": task.level,
                "pace": task.pace,
                "availability_slots": new_availability,
                "additional_requirements": task.additional_requirements,
            }
            rebook_result_type, rebook_result, _ = execute_start_booking(
                rebook_meta, rebook_args
            )
            if rebook_result_type == "booking":
                rebook_payload = rebook_result
                flow.replacement_task_id = rebook_result.get("bookingTaskId")
                logger.info(
                    "[cancel] leave_rebook_success replacement_task_id=%s",
                    flow.replacement_task_id,
                )
            else:
                logger.info("[cancel] leave_rebook_no_booking result_type=%s", rebook_result_type)

    # Start only the backfill in a background thread (rebook is done above)
    start_backfill_only_thread(flow, task, store)
    logger.info("[cancel] backfill_thread_started flow_id=%s", flow.id)

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
            "rebookPayload": rebook_payload,
        },
        {},
    )
