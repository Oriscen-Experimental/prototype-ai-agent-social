"""Background runner for booking tasks - sends invitations in batches with dynamic slot narrowing."""

from __future__ import annotations

import logging
import random
import threading
import time
import uuid
from typing import Any

from .task_store import BookingTask, BookingTaskStore, Invitation

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
WAIT_TIME_SECONDS = 3600  # 1 hour per batch

# Mock response rates
MOCK_ACCEPT_RATE = 0.25
MOCK_DECLINE_RATE = 0.35
# Remaining ~40% = no response (expires)


# =============================================================================
# Slot Narrowing Helper Functions
# =============================================================================


def _has_slot_overlap(user_slots: list[str] | None, current_slots: list[str]) -> bool:
    """Check if user has any availability overlapping with current slots."""
    if not current_slots:
        return True  # No slot constraint
    return bool(set(user_slots or []).intersection(set(current_slots)))


def _narrow_slots(current_slots: list[str], accepter_availability: list[str] | None) -> list[str]:
    """
    Narrow current_slots to intersection with accepter's availability.

    current_slots = current_slots ∩ accepter.availability
    """
    if not accepter_availability:
        # Accepter has no availability info, don't narrow
        logger.warning("[booking] accepter has empty availability, not narrowing slots")
        return current_slots

    new_slots = list(set(current_slots).intersection(set(accepter_availability)))

    if not new_slots:
        # Edge case: intersection is empty (shouldn't happen if filtered properly)
        logger.warning("[booking] slot narrowing resulted in empty set, keeping original")
        return current_slots

    return new_slots


def _get_invited_ids(task: BookingTask) -> set[str]:
    """Get set of user IDs that have already been invited."""
    return {inv.user_id for inv in task.invitations}


def _handle_acceptance(task: BookingTask, accepter_info: dict[str, Any]) -> int:
    """
    Handle a new acceptance: narrow slots and filter candidate pool.

    Returns: number of candidates that would be dropped due to narrowing
    """
    old_slots = set(task.current_slots)
    accepter_availability = accepter_info.get("availability", [])

    # Step 1: Narrow current_slots
    new_slots = _narrow_slots(task.current_slots, accepter_availability)

    dropped_count = 0
    if set(new_slots) != old_slots:
        logger.info(
            "[booking] task=%s slots narrowed: %s -> %s (accepter: %s)",
            task.id[:8], list(old_slots), new_slots, accepter_info.get("nickname", "?")
        )
        task.current_slots = new_slots

        # Step 2: Count how many candidates would be dropped
        # (We don't actually remove from task.candidates to preserve order for stats)
        invited_ids = _get_invited_ids(task)
        for candidate in task.candidates:
            cid = candidate.get("id", "")
            if cid in invited_ids:
                continue
            if not _has_slot_overlap(candidate.get("availability"), task.current_slots):
                dropped_count += 1

        if dropped_count > 0:
            logger.info(
                "[booking] task=%s %d candidates no longer have slot overlap after narrowing",
                task.id[:8], dropped_count
            )

    return dropped_count


def _drop_batch_no_overlap(
    task: BookingTask,
    batch_invitations: list[Invitation]
) -> list[Invitation]:
    """
    Drop pending invitations in current batch that no longer have slot overlap.

    Returns: list of remaining valid (pending) invitations
    """
    remaining: list[Invitation] = []

    for inv in batch_invitations:
        if inv.status != "pending":
            # Already resolved (accepted/declined/expired/dropped)
            continue

        if not _has_slot_overlap(inv.user_info.get("availability"), task.current_slots):
            inv.status = "dropped"
            logger.info(
                "[booking] task=%s dropped pending invitation for %s (no slot overlap with %s)",
                task.id[:8], inv.user_info.get("nickname", inv.user_id), task.current_slots
            )
        else:
            remaining.append(inv)

    return remaining


def _refill_batch(
    task: BookingTask,
    batch_invitations: list[Invitation],
    target_size: int = BATCH_SIZE,
) -> list[Invitation]:
    """
    Refill batch to target size from candidate pool.

    Returns: list of new invitations added (for tracking)
    """
    pending_count = len([inv for inv in batch_invitations if inv.status == "pending"])
    needed = target_size - pending_count

    if needed <= 0:
        return []

    invited_ids = _get_invited_ids(task)

    # Get available candidates from pool (not yet invited, has slot overlap)
    available = [
        c for c in task.candidates
        if c.get("id") not in invited_ids
        and _has_slot_overlap(c.get("availability"), task.current_slots)
    ]

    to_invite = available[:needed]
    new_invitations: list[Invitation] = []

    for candidate in to_invite:
        inv = Invitation(
            id=str(uuid.uuid4()),
            task_id=task.id,
            user_id=candidate.get("id", ""),
            user_info=candidate,
            status="pending",
            sent_at=time.time(),
            batch_index=task.current_batch,
        )
        task.invitations.append(inv)
        batch_invitations.append(inv)
        new_invitations.append(inv)

    if new_invitations:
        logger.info(
            "[booking] task=%s refilled batch with %d candidates (now %d pending)",
            task.id[:8], len(new_invitations), pending_count + len(new_invitations)
        )

    return new_invitations


# =============================================================================
# Mock Response Simulation
# =============================================================================


def _simulate_mock_responses(
    task: BookingTask,
    batch_invitations: list[Invitation]
) -> list[dict[str, Any]]:
    """
    Simulate responses for mock users in a batch.

    Returns: list of newly accepted user_info dicts (for slot narrowing)
    """
    newly_accepted: list[dict[str, Any]] = []

    for inv in batch_invitations:
        if not inv.user_info.get("is_mock", True):
            # Real user - don't simulate
            continue

        if inv.status != "pending":
            continue

        # Check if user still has slot overlap (might have been narrowed)
        if not _has_slot_overlap(inv.user_info.get("availability"), task.current_slots):
            inv.status = "dropped"
            continue

        # Stop accepting once headcount is met
        if len(task.accepted_users) >= task.headcount:
            inv.status = "expired"
            continue

        roll = random.random()
        if roll < MOCK_ACCEPT_RATE:
            inv.status = "accepted"
            inv.responded_at = time.time()
            task.accepted_users.append(inv.user_info)
            newly_accepted.append(inv.user_info)
            logger.info(
                "[booking] mock user %s ACCEPTED task=%s",
                inv.user_info.get("nickname", inv.user_id),
                task.id[:8],
            )
        elif roll < MOCK_ACCEPT_RATE + MOCK_DECLINE_RATE:
            inv.status = "declined"
            inv.responded_at = time.time()
        else:
            inv.status = "expired"

    return newly_accepted


def _check_real_user_responses(task: BookingTask, batch_invitations: list[Invitation]) -> None:
    """Check and expire pending real-user invitations after wait time."""
    for inv in batch_invitations:
        if inv.user_info.get("is_mock", True):
            continue

        if inv.status == "pending":
            inv.status = "expired"

        if inv.status == "accepted" and inv.user_info not in task.accepted_users:
            # Only add if headcount not yet met
            if len(task.accepted_users) < task.headcount:
                task.accepted_users.append(inv.user_info)


# =============================================================================
# Notification Builders
# =============================================================================


def _build_completion_notification(task: BookingTask) -> dict[str, Any]:
    """Build the completion notification message."""
    accepted_names = [u.get("nickname", "Someone") for u in task.accepted_users]
    names_str = ", ".join(accepted_names[:5])
    if len(accepted_names) > 5:
        names_str += f" and {len(accepted_names) - 5} more"

    # Build time string from final narrowed slots
    time_str = ""
    if task.desired_time:
        time_str = f" on {task.desired_time}"
    elif task.current_slots:
        slot_names = [s.replace("_", " ") for s in task.current_slots]
        time_str = f" ({', '.join(slot_names)})"

    loc_str = f" in {task.location}" if task.location else ""

    message = (
        f"Great news! I've confirmed {len(task.accepted_users)} "
        f"{'person' if len(task.accepted_users) == 1 else 'people'} "
        f"for {task.activity}{loc_str}{time_str}. "
        f"Here's who's joining: {names_str}."
    )

    # Build profile cards for accepted users
    profiles = []
    for u in task.accepted_users:
        profiles.append({
            "id": u.get("id", ""),
            "kind": "human",
            "name": u.get("nickname", ""),
            "presence": "online",
            "city": u.get("location", ""),
            "headline": u.get("occupation", ""),
            "score": u.get("match_score", 80),
            "badges": [],
            "about": [f"Interested in: {', '.join(u.get('interests', [])[:3])}"],
            "matchReasons": [f"Matched for {task.activity}"],
            "topics": u.get("interests", [])[:5],
            # Running-specific fields
            "runningLevel": u.get("running_level"),
            "runningPace": u.get("running_pace"),
            "runningDistance": u.get("running_distance"),
            "availability": u.get("availability", []),
        })

    return {
        "type": "booking_completed",
        "message": message,
        "profiles": profiles,
        "bookingTaskId": task.id,
        "timestamp": time.time(),
        "finalSlots": task.current_slots,  # Include final narrowed slots
    }


def _build_failure_notification(task: BookingTask) -> dict[str, Any]:
    """Build notification when booking fails (ran out of candidates)."""
    accepted = len(task.accepted_users)
    message = (
        f"I wasn't able to find enough people for {task.activity}. "
        f"I reached out to {len(task.invitations)} people, "
        f"but only {accepted} accepted "
        f"(you needed {task.headcount}). "
        f"Would you like to try again with different criteria?"
    )
    return {
        "type": "booking_failed",
        "message": message,
        "bookingTaskId": task.id,
        "timestamp": time.time(),
        "finalSlots": task.current_slots,
    }


def _build_progress_notification(task: BookingTask, batch_num: int, batch_size: int) -> dict[str, Any]:
    """Build progress notification after each batch."""
    accepted = len(task.accepted_users)
    total_invited = len(task.invitations)

    # Count remaining valid candidates (not invited, has slot overlap)
    invited_ids = _get_invited_ids(task)
    remaining_candidates = sum(
        1 for c in task.candidates
        if c.get("id") not in invited_ids
        and _has_slot_overlap(c.get("availability"), task.current_slots)
    )
    total_valid = total_invited + remaining_candidates

    # Build progress message
    if accepted == 0:
        status_msg = "Waiting for responses..."
    elif accepted < task.headcount:
        status_msg = f"{accepted}/{task.headcount} confirmed so far"
    else:
        status_msg = f"{accepted} confirmed!"

    message = (
        f"Batch {batch_num + 1}: Invited {total_invited}/{total_valid} people. "
        f"{status_msg}"
    )

    return {
        "type": "booking_progress",
        "message": message,
        "bookingTaskId": task.id,
        "timestamp": time.time(),
        "progress": {
            "currentBatch": batch_num + 1,
            "totalCandidates": total_valid,
            "totalInvited": total_invited,
            "acceptedCount": accepted,
            "targetCount": task.headcount,
            "batchSize": batch_size,
            "currentSlots": task.current_slots,
        },
    }


# =============================================================================
# Main Booking Loop
# =============================================================================


def run_booking_task(task: BookingTask, store: BookingTaskStore) -> None:
    """
    Main booking loop with dynamic slot narrowing.

    Key features:
    1. Initializes current_slots from user's availability
    2. On each accept: narrows slots (current_slots ∩ accepter.availability)
    3. Drops batch members with no slot overlap
    4. Refills batch from candidate pool
    5. Skips to next batch if all current batch dropped/responded
    """
    # Initialize current_slots if not set
    if not task.current_slots:
        task.current_slots = list(task.availability_slots)

    logger.info(
        "[booking] starting task=%s activity=%s headcount=%d candidates=%d current_slots=%s",
        task.id[:8], task.activity, task.headcount, len(task.candidates), task.current_slots,
    )

    try:
        while task.status == "running":
            # === Step 1: Build initial batch from valid candidates ===
            invited_ids = _get_invited_ids(task)
            available_candidates = [
                c for c in task.candidates
                if c.get("id") not in invited_ids
                and _has_slot_overlap(c.get("availability"), task.current_slots)
            ]

            batch_candidates = available_candidates[:BATCH_SIZE]

            if not batch_candidates:
                # No more valid candidates
                if len(task.accepted_users) >= task.headcount:
                    task.status = "completed"
                    task.notifications.append(_build_completion_notification(task))
                    logger.info(
                        "[booking] task=%s COMPLETED (exhausted candidates) with %d accepted",
                        task.id[:8], len(task.accepted_users),
                    )
                else:
                    task.status = "failed"
                    task.notifications.append(_build_failure_notification(task))
                    logger.info("[booking] task=%s FAILED exhausted candidates", task.id[:8])
                break

            # === Step 2: Create invitations for this batch ===
            batch_invitations: list[Invitation] = []
            for candidate in batch_candidates:
                inv = Invitation(
                    id=str(uuid.uuid4()),
                    task_id=task.id,
                    user_id=candidate.get("id", ""),
                    user_info=candidate,
                    status="pending",
                    sent_at=time.time(),
                    batch_index=task.current_batch,
                )
                task.invitations.append(inv)
                batch_invitations.append(inv)

            logger.info(
                "[booking] task=%s sent batch %d (%d invitations, current_slots=%s)",
                task.id[:8], task.current_batch, len(batch_invitations), task.current_slots,
            )

            # Send progress notification - batch sent
            task.notifications.append(_build_progress_notification(
                task, task.current_batch, len(batch_invitations)
            ))

            # === Step 3: Wait loop with dynamic slot processing ===
            target_simulated_time = float(WAIT_TIME_SECONDS)
            elapsed_simulated = 0.0
            check_interval_real = 1.0

            while elapsed_simulated < target_simulated_time and task.status == "running":
                time.sleep(check_interval_real)
                elapsed_simulated += check_interval_real * max(0.1, task.speed_multiplier)

                # Check for real user responses and process accepts
                for inv in batch_invitations:
                    if inv.status == "accepted" and inv.user_info not in task.accepted_users:
                        task.accepted_users.append(inv.user_info)
                        # Narrow slots on accept
                        _handle_acceptance(task, inv.user_info)
                        # Drop batch members with no overlap
                        batch_invitations = _drop_batch_no_overlap(task, batch_invitations)
                        # Try to refill batch
                        _refill_batch(task, batch_invitations, BATCH_SIZE)

                # Early exit if headcount met
                if len(task.accepted_users) >= task.headcount:
                    break

                # Early exit if all batch invitations are resolved (not pending)
                pending_count = sum(1 for inv in batch_invitations if inv.status == "pending")
                if pending_count == 0:
                    logger.info(
                        "[booking] task=%s batch %d all resolved, skipping to next",
                        task.id[:8], task.current_batch
                    )
                    break

            if task.status != "running":
                break

            # === Step 4: Simulate mock responses ===
            newly_accepted = _simulate_mock_responses(task, batch_invitations)

            # Process each acceptance for slot narrowing
            for accepter_info in newly_accepted:
                _handle_acceptance(task, accepter_info)

            # Drop remaining batch members with no overlap after narrowing
            _drop_batch_no_overlap(task, batch_invitations)

            # Check real user responses
            _check_real_user_responses(task, batch_invitations)

            # === Step 5: Check completion ===
            if len(task.accepted_users) >= task.headcount:
                task.status = "completed"
                task.notifications.append(_build_completion_notification(task))
                logger.info(
                    "[booking] task=%s COMPLETED with %d accepted, final_slots=%s",
                    task.id[:8], len(task.accepted_users), task.current_slots,
                )
                break

            logger.info(
                "[booking] task=%s batch %d done: %d/%d accepted, current_slots=%s",
                task.id[:8], task.current_batch,
                len(task.accepted_users), task.headcount, task.current_slots,
            )

            # Send progress notification - batch responses received
            task.notifications.append(_build_progress_notification(
                task, task.current_batch, len(batch_invitations)
            ))

            task.current_batch += 1

    except Exception as e:
        logger.exception("[booking] task=%s failed with error", task.id[:8])
        task.status = "failed"
        task.notifications.append({
            "type": "booking_error",
            "message": f"An error occurred while arranging your {task.activity}. Please try again.",
            "bookingTaskId": task.id,
            "timestamp": time.time(),
        })


def start_booking_task_thread(task: BookingTask, store: BookingTaskStore) -> threading.Thread:
    """Start booking task in a background thread."""
    thread = threading.Thread(
        target=run_booking_task,
        args=(task, store),
        daemon=True,
        name=f"booking-{task.id[:8]}",
    )
    thread.start()
    return thread
