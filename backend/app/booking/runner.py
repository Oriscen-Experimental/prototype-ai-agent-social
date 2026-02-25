"""Background runner for booking tasks - sends invitations in batches."""

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


def _simulate_mock_responses(task: BookingTask, batch_invitations: list[Invitation]) -> None:
    """Simulate responses for mock users in a batch."""
    for inv in batch_invitations:
        if not inv.user_info.get("is_mock", True):
            # Real user - don't simulate, check actual response
            continue

        if inv.status != "pending":
            continue

        roll = random.random()
        if roll < MOCK_ACCEPT_RATE:
            inv.status = "accepted"
            inv.responded_at = time.time()
            task.accepted_users.append(inv.user_info)
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


def _check_real_user_responses(task: BookingTask, batch_invitations: list[Invitation]) -> None:
    """Check and expire pending real-user invitations after wait time."""
    for inv in batch_invitations:
        if inv.user_info.get("is_mock", True):
            continue

        if inv.status == "pending":
            inv.status = "expired"

        if inv.status == "accepted" and inv.user_info not in task.accepted_users:
            task.accepted_users.append(inv.user_info)


def _build_completion_notification(task: BookingTask) -> dict[str, Any]:
    """Build the completion notification message."""
    accepted_names = [u.get("nickname", "Someone") for u in task.accepted_users]
    names_str = ", ".join(accepted_names[:5])
    if len(accepted_names) > 5:
        names_str += f" and {len(accepted_names) - 5} more"

    time_str = f" on {task.desired_time}" if task.desired_time else ""
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
        })

    return {
        "type": "booking_completed",
        "message": message,
        "profiles": profiles,
        "bookingTaskId": task.id,
        "timestamp": time.time(),
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
    }


def run_booking_task(task: BookingTask, store: BookingTaskStore) -> None:
    """
    Main booking loop. Runs in a background thread.

    Sends invitations in batches of 10, waits for responses,
    and continues until headcount is met or candidates exhausted.
    """
    logger.info(
        "[booking] starting task=%s activity=%s headcount=%d candidates=%d",
        task.id[:8], task.activity, task.headcount, len(task.candidates),
    )

    try:
        while task.status == "running":
            # Get next batch
            start_idx = task.current_batch * BATCH_SIZE
            end_idx = start_idx + BATCH_SIZE
            batch_candidates = task.candidates[start_idx:end_idx]

            if not batch_candidates:
                # Ran out of candidates
                logger.info("[booking] task=%s exhausted candidates", task.id[:8])
                task.status = "failed"
                task.notifications.append(_build_failure_notification(task))
                break

            # Create invitations for this batch
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
                "[booking] task=%s sent batch %d (%d invitations)",
                task.id[:8], task.current_batch, len(batch_invitations),
            )

            # Wait for responses using simulated time
            # This allows speed_multiplier changes to take effect immediately
            target_simulated_time = float(WAIT_TIME_SECONDS)  # 1 hour in simulated time
            elapsed_simulated = 0.0
            check_interval_real = 1.0  # Check every 1 second of real time

            while elapsed_simulated < target_simulated_time and task.status == "running":
                time.sleep(check_interval_real)
                # Each real second advances simulated time by speed_multiplier seconds
                elapsed_simulated += check_interval_real * max(0.1, task.speed_multiplier)

                # Check if any real users have responded during wait
                for inv in batch_invitations:
                    if inv.status == "accepted" and inv.user_info not in task.accepted_users:
                        task.accepted_users.append(inv.user_info)

                # Early exit if headcount already met
                if len(task.accepted_users) >= task.headcount:
                    break

            if task.status != "running":
                break

            # After wait: simulate mock responses
            _simulate_mock_responses(task, batch_invitations)

            # Check real user responses one final time
            _check_real_user_responses(task, batch_invitations)

            # Check if headcount met
            if len(task.accepted_users) >= task.headcount:
                task.status = "completed"
                task.notifications.append(_build_completion_notification(task))
                logger.info(
                    "[booking] task=%s COMPLETED with %d accepted",
                    task.id[:8], len(task.accepted_users),
                )
                break

            logger.info(
                "[booking] task=%s batch %d done: %d/%d accepted so far",
                task.id[:8], task.current_batch,
                len(task.accepted_users), task.headcount,
            )

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
