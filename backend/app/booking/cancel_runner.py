"""Background runner for cancel_booking flows.

Handles two main paths:
  - Reschedule: ask participants about time change, narrow slots, backfill if needed
  - Leave: remove user, backfill for remaining group, start new booking for leaver
"""

from __future__ import annotations

import logging
import random
import threading
import time
import uuid
from typing import Any

from .profile_builder import build_profile, build_profiles
from .runner import _has_slot_overlap, _narrow_slots, _resolve_booking_details
from .slot_resolver import pick_nearest_slot
from .task_store import (
    BookingTask,
    BookingTaskStore,
    CancelFlow,
    Invitation,
    RescheduleResponse,
)

logger = logging.getLogger(__name__)

RESCHEDULE_WAIT_SECONDS = 1800  # 30 min simulated wait for reschedule responses
BACKFILL_BATCH_SIZE = 5
BACKFILL_CHECK_INTERVAL = 1.0  # Real seconds between checks
MOCK_RESCHEDULE_ACCEPT_RATE = 0.70
MOCK_BACKFILL_ACCEPT_RATE = 0.30


# ==========================================================================
# Notification helpers
# ==========================================================================


def _notify(flow: CancelFlow, notification: dict[str, Any]) -> None:
    """Append a notification to the cancel flow."""
    notification.setdefault("timestamp", time.time())
    notification.setdefault("cancelFlowId", flow.id)
    notification.setdefault("taskId", flow.task_id)
    flow.notifications.append(notification)


# ==========================================================================
# Reschedule flow (Option A)
# ==========================================================================


def _run_reschedule_flow(
    flow: CancelFlow, task: BookingTask, store: BookingTaskStore
) -> None:
    """
    1. Send reschedule request to all other accepted participants.
    2. Wait for responses (simulate mock users).
    3. If ALL accept -> compute overlapping slots, reschedule.
    4. If SOME decline -> reschedule for remaining, prompt for backfill.
    """
    logger.info(
        "[cancel] reschedule_flow_start flow_id=%s task_id=%s participants=%d",
        flow.id[:8], task.id[:8], len(flow.remaining_participants),
    )
    flow.status = "reschedule_polling"  # type: ignore[assignment]

    # Build response tracking for each participant (excluding the canceller)
    for user_info in flow.remaining_participants:
        flow.reschedule_responses.append(
            RescheduleResponse(
                user_id=user_info.get("id", ""),
                user_info=user_info,
                vote="pending",
            )
        )

    # Notify the cancelling user that we're polling
    _notify(flow, {
        "type": "cancel_reschedule_ask",
        "message": (
            f"I'm asking the other {len(flow.remaining_participants)} participant(s) "
            f"if they can accommodate a different time for {task.activity}."
        ),
        "profiles": build_profiles(flow.remaining_participants, task.activity),
        "activity": task.activity,
        "location": task.location,
    })

    # Wait for responses
    elapsed = 0.0
    wait_target = float(RESCHEDULE_WAIT_SECONDS)

    while elapsed < wait_target:
        time.sleep(BACKFILL_CHECK_INTERVAL)
        elapsed += BACKFILL_CHECK_INTERVAL * max(0.1, task.speed_multiplier)

        # Early exit if everyone responded
        pending = [r for r in flow.reschedule_responses if r.vote == "pending"]
        if not pending:
            break

    pending_count = len([r for r in flow.reschedule_responses if r.vote == "pending"])
    logger.info("[cancel] reschedule_wait_done flow_id=%s pending_remaining=%d", flow.id[:8], pending_count)
    # Simulate mock responses for anyone still pending
    for resp in flow.reschedule_responses:
        if resp.vote != "pending":
            continue
        if resp.user_info.get("is_mock", True):
            if random.random() < MOCK_RESCHEDULE_ACCEPT_RATE:
                resp.vote = "accept"
            else:
                resp.vote = "decline"
            resp.responded_at = time.time()
        else:
            # Real user didn't respond in time -> treat as decline
            resp.vote = "expired"

    # Partition results
    flow.status = "reschedule_narrowing"  # type: ignore[assignment]
    accepted_responses = [
        r for r in flow.reschedule_responses if r.vote == "accept"
    ]
    declined_responses = [
        r for r in flow.reschedule_responses if r.vote in ("decline", "expired")
    ]
    logger.info(
        "[cancel] reschedule_responses flow_id=%s accepted=%d declined=%d",
        flow.id[:8], len(accepted_responses), len(declined_responses),
    )

    # Find the cancelling user's info from original accepted_users
    cancelling_user_info = None
    for u in task.accepted_users:
        if u.get("id") == flow.cancelling_user_id:
            cancelling_user_info = u
            break

    # Build remaining = those who accepted the reschedule + the cancelling user
    remaining = [r.user_info for r in accepted_responses]
    if cancelling_user_info:
        remaining.append(cancelling_user_info)
    flow.remaining_participants = remaining
    flow.departed_participants = [r.user_info for r in declined_responses]

    all_accepted = len(declined_responses) == 0

    # Compute new overlapping time slots among remaining participants
    if remaining:
        new_slots = list(task.availability_slots) if task.availability_slots else []
        for user_info in remaining:
            user_avail = user_info.get("availability", [])
            if user_avail:
                new_slots = _narrow_slots(new_slots, user_avail)
        flow.new_slots = new_slots
        logger.info("[cancel] reschedule_new_slots flow_id=%s slots=%s", flow.id[:8], new_slots)
    else:
        flow.new_slots = []
        logger.info("[cancel] reschedule_no_remaining_participants flow_id=%s", flow.id[:8])

    # Notify result
    if all_accepted:
        result_msg = (
            f"All {len(accepted_responses)} participant(s) accepted the time change!"
        )
    else:
        result_msg = (
            f"{len(accepted_responses)} participant(s) accepted the time change, "
            f"but {len(declined_responses)} couldn't make the new time and have left."
        )
    _notify(flow, {
        "type": "cancel_reschedule_result",
        "message": result_msg,
        "allAccepted": all_accepted,
        "remainingCount": len(accepted_responses),
        "departedCount": len(declined_responses),
        "responses": [
            {
                "userId": r.user_id,
                "vote": r.vote,
                "profile": build_profile(r.user_info, task.activity),
            }
            for r in flow.reschedule_responses
        ],
        "activity": task.activity,
        "location": task.location,
    })

    if not flow.new_slots:
        logger.info("[cancel] reschedule_failed_no_overlap flow_id=%s", flow.id[:8])
        _notify(flow, {
            "type": "cancel_reschedule_failed",
            "message": (
                "Unfortunately there are no overlapping time slots "
                "for the remaining participants."
            ),
        })
        flow.status = "failed"  # type: ignore[assignment]
        return

    if all_accepted:
        # Everyone agrees -> reschedule immediately
        logger.info("[cancel] reschedule_all_accepted flow_id=%s -> apply_reschedule", flow.id[:8])
        _apply_reschedule(flow, task)
        flow.status = "completed"  # type: ignore[assignment]
        return

    # Some declined -> reschedule for remaining, then check if backfill is needed
    logger.info("[cancel] reschedule_partial flow_id=%s -> apply_reschedule + check_backfill", flow.id[:8])
    _apply_reschedule(flow, task)

    spots_open = task.headcount - len(flow.remaining_participants)
    logger.info("[cancel] reschedule_spots_check flow_id=%s spots_open=%d", flow.id[:8], spots_open)
    if spots_open > 0:
        flow.status = "backfill_prompt"  # type: ignore[assignment]
        _notify(flow, _build_backfill_prompt_notification(flow, task, spots_open))
        _wait_for_backfill_decision(flow, task, store)
    else:
        logger.info("[cancel] reschedule_no_backfill_needed flow_id=%s", flow.id[:8])
        flow.status = "completed"  # type: ignore[assignment]


def _apply_reschedule(flow: CancelFlow, task: BookingTask) -> None:
    """Apply the reschedule: update task slots, resolve new time, update accepted_users."""
    task.current_slots = flow.new_slots
    task.accepted_users = list(flow.remaining_participants)

    # Re-resolve concrete booking details
    if flow.new_slots:
        resolved = pick_nearest_slot(flow.new_slots)
        task.booked_time = resolved.formatted
        task.booked_iso_start = resolved.iso_start
        task.booked_iso_end = resolved.iso_end
        logger.info(
            "[cancel] apply_reschedule flow_id=%s new_time=%s participants=%d",
            flow.id[:8], task.booked_time, len(task.accepted_users),
        )

    _notify(flow, {
        "type": "cancel_rescheduled",
        "message": f"Booking rescheduled to {task.booked_time or 'new time'}.",
        "bookedTime": task.booked_time,
        "bookedIsoStart": task.booked_iso_start,
        "bookedIsoEnd": task.booked_iso_end,
        "bookedLocation": task.booked_location,
        "profiles": build_profiles(flow.remaining_participants, task.activity),
        "activity": task.activity,
        "location": task.location,
    })


# ==========================================================================
# Leave flow (Option B)
# ==========================================================================


def _run_leave_flow(
    flow: CancelFlow, task: BookingTask, store: BookingTaskStore
) -> None:
    """
    Run only backfill for the leave path.

    User removal and rebook are handled synchronously in execute_cancel_booking
    (cancel_booking.py) so the rebook goes through the same pipeline as initial
    booking and produces identical UI.
    """
    logger.info("[cancel] leave_flow_start flow_id=%s task_id=%s", flow.id[:8], task.id[:8])
    _leave_backfill_path(flow, task, store)
    logger.info("[cancel] leave_flow_completed flow_id=%s", flow.id[:8])
    flow.status = "completed"  # type: ignore[assignment]


def _leave_backfill_path(
    flow: CancelFlow, task: BookingTask, store: BookingTaskStore
) -> None:
    """Ask remaining participants about backfill, then run backfill if approved."""
    spots_open = task.headcount - len(flow.remaining_participants)
    logger.info("[cancel] leave_backfill_check flow_id=%s spots_open=%d", flow.id[:8], spots_open)
    if spots_open <= 0:
        logger.info("[cancel] leave_backfill_not_needed flow_id=%s", flow.id[:8])
        return

    flow.status = "leave_backfill_prompt"  # type: ignore[assignment]
    _notify(flow, _build_backfill_prompt_notification(flow, task, spots_open))
    _wait_for_backfill_decision(flow, task, store)


# ==========================================================================
# Backfill logic (shared by both paths)
# ==========================================================================


def _build_backfill_prompt_notification(
    flow: CancelFlow, task: BookingTask, spots_open: int
) -> dict[str, Any]:
    return {
        "type": "cancel_backfill_prompt",
        "message": (
            f"There {'is' if spots_open == 1 else 'are'} now {spots_open} open "
            f"spot{'s' if spots_open > 1 else ''} in the {task.activity} booking. "
            f"I'm now searching for replacement participant(s)."
        ),
        "spotsOpen": spots_open,
    }


def _wait_for_backfill_decision(
    flow: CancelFlow, task: BookingTask, store: BookingTaskStore
) -> None:
    """Auto-approve and start backfill immediately."""
    flow.backfill_approved = True
    _run_backfill_loop(flow, task, store)


def _run_backfill_loop(
    flow: CancelFlow, task: BookingTask, store: BookingTaskStore
) -> None:
    """
    Find and invite replacement users until:
      - All spots filled, OR
      - 30 minutes before event start, OR
      - No more candidates available.
    """
    from ..db import user_db

    if flow.status in ("backfill_prompt", "leave_backfill_prompt"):
        flow.status = flow.status.replace("_prompt", "_running")  # type: ignore[assignment]
    else:
        flow.status = "backfill_running"  # type: ignore[assignment]

    spots_needed = task.headcount - len(task.accepted_users)
    logger.info(
        "[cancel] backfill_loop_start flow_id=%s spots_needed=%d status=%s",
        flow.id[:8], spots_needed, flow.status,
    )
    if spots_needed <= 0:
        logger.info("[cancel] backfill_not_needed flow_id=%s", flow.id[:8])
        return

    # Build set of already-contacted user IDs
    already_invited_ids = {inv.user_id for inv in task.invitations}
    already_invited_ids.update(u.get("id", "") for u in task.accepted_users)
    already_invited_ids.update(u.get("id", "") for u in flow.departed_participants)
    already_invited_ids.add(flow.cancelling_user_id)

    # Query for backfill candidates
    candidates, _ = user_db.match(
        activity=task.activity,
        location=task.location,
        gender=task.gender_preference,
        level=task.level,
        pace=task.pace,
        availability_slots=task.current_slots,
        headcount=spots_needed * 5,
        exclude_user_id=flow.cancelling_user_id,
        limit=100,
    )

    flow.backfill_candidates = [
        c for c in candidates if c.get("id") not in already_invited_ids
    ]
    logger.info(
        "[cancel] backfill_candidates flow_id=%s total_from_db=%d after_filter=%d",
        flow.id[:8], len(candidates), len(flow.backfill_candidates),
    )

    backfill_accepted = 0
    backfill_invited = 0

    while (
        backfill_accepted < spots_needed
        and flow.backfill_candidates
        and (flow.backfill_deadline == 0.0 or time.time() < flow.backfill_deadline)
    ):
        # Send a batch
        batch = flow.backfill_candidates[:BACKFILL_BATCH_SIZE]
        flow.backfill_candidates = flow.backfill_candidates[BACKFILL_BATCH_SIZE:]

        batch_invitations: list[Invitation] = []
        for candidate in batch:
            inv = Invitation(
                id=str(uuid.uuid4()),
                task_id=task.id,
                user_id=candidate.get("id", ""),
                user_info=candidate,
                status="pending",
                sent_at=time.time(),
                batch_index=task.current_batch + 1,
            )
            task.invitations.append(inv)
            flow.backfill_invitations.append(inv)
            batch_invitations.append(inv)
            backfill_invited += 1

        # Wait for responses
        wait_elapsed = 0.0
        wait_target = 600.0  # 10 min simulated

        while wait_elapsed < wait_target:
            time.sleep(BACKFILL_CHECK_INTERVAL)
            wait_elapsed += BACKFILL_CHECK_INTERVAL * max(0.1, task.speed_multiplier)

            if flow.backfill_deadline > 0 and time.time() >= flow.backfill_deadline:
                break

            pending = [i for i in batch_invitations if i.status == "pending"]
            if not pending:
                break

        # Simulate mock responses
        for inv in batch_invitations:
            if inv.status != "pending":
                continue
            if inv.user_info.get("is_mock", True):
                if (
                    random.random() < MOCK_BACKFILL_ACCEPT_RATE
                    and backfill_accepted < spots_needed
                ):
                    inv.status = "accepted"
                    inv.responded_at = time.time()
                    task.accepted_users.append(inv.user_info)
                    backfill_accepted += 1
                else:
                    inv.status = "declined"
                    inv.responded_at = time.time()
            else:
                inv.status = "expired"

        backfill_accepted_users = [
            inv.user_info for inv in flow.backfill_invitations if inv.status == "accepted"
        ]
        _notify(flow, {
            "type": "cancel_backfill_progress",
            "message": (
                f"Backfill: {backfill_accepted}/{spots_needed} "
                f"replacements found ({backfill_invited} invited)."
            ),
            "invited": backfill_invited,
            "accepted": backfill_accepted,
            "needed": spots_needed,
            "profiles": build_profiles(backfill_accepted_users, task.activity),
            "activity": task.activity,
            "location": task.location,
        })

    # Final notification
    logger.info(
        "[cancel] backfill_loop_done flow_id=%s filled=%d needed=%d invited=%d",
        flow.id[:8], backfill_accepted, spots_needed, backfill_invited,
    )
    if backfill_accepted >= spots_needed:
        final_msg = f"Backfill complete! All {spots_needed} spots have been filled."
    else:
        final_msg = (
            f"Backfill ended. {backfill_accepted} of {spots_needed} "
            f"spots were filled before the deadline."
        )
    _notify(flow, {
        "type": "cancel_backfill_complete",
        "message": final_msg,
        "filled": backfill_accepted,
        "totalNeeded": spots_needed,
        "profiles": build_profiles(task.accepted_users, task.activity),
        "activity": task.activity,
        "location": task.location,
        "bookedTime": task.booked_time,
        "bookedLocation": task.booked_location,
    })

    # Update task booking details if spots were filled
    if backfill_accepted >= spots_needed:
        _resolve_booking_details(task)


# ==========================================================================
# Thread entry points
# ==========================================================================


def run_cancel_flow(
    flow: CancelFlow, task: BookingTask, store: BookingTaskStore
) -> None:
    """Main entry point for the cancel flow background thread."""
    logger.info(
        "[cancel] run_cancel_flow entry flow_id=%s intention=%s task_id=%s",
        flow.id[:8], flow.intention, task.id[:8],
    )
    try:
        if flow.intention == "reschedule":
            logger.info("[cancel] routing to reschedule_flow flow_id=%s", flow.id[:8])
            _run_reschedule_flow(flow, task, store)
        elif flow.intention == "leave":
            logger.info("[cancel] routing to leave_flow flow_id=%s", flow.id[:8])
            _run_leave_flow(flow, task, store)
        else:
            logger.error("[cancel] invalid intention: %s", flow.intention)
            flow.status = "failed"  # type: ignore[assignment]
    except Exception:
        logger.exception("[cancel] flow=%s failed", flow.id[:8])
        flow.status = "failed"  # type: ignore[assignment]
        _notify(flow, {
            "type": "cancel_error",
            "message": (
                "An error occurred during the cancellation process. "
                "Please try again."
            ),
        })


def start_cancel_flow_thread(
    flow: CancelFlow, task: BookingTask, store: BookingTaskStore
) -> threading.Thread:
    """Start cancel flow in a background thread."""
    thread = threading.Thread(
        target=run_cancel_flow,
        args=(flow, task, store),
        daemon=True,
        name=f"cancel-{flow.id[:8]}",
    )
    thread.start()
    return thread


def start_backfill_only_thread(
    flow: CancelFlow, task: BookingTask, store: BookingTaskStore
) -> threading.Thread:
    """Start only the leave-path backfill in a background thread.

    Used when the rebook is handled synchronously by execute_cancel_booking
    and only the backfill still needs to run in the background.
    """
    thread = threading.Thread(
        target=_run_leave_flow,
        args=(flow, task, store),
        daemon=True,
        name=f"cancel-backfill-{flow.id[:8]}",
    )
    thread.start()
    return thread
