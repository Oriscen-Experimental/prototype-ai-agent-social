"""In-memory storage for booking tasks."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


InvitationStatus = Literal["pending", "accepted", "declined", "expired", "dropped"]
BookingStatus = Literal["running", "completed", "failed", "cancelled"]
CancelIntention = Literal["reschedule", "leave"]
CancelFlowStatus = Literal[
    "awaiting_intention",
    "reschedule_polling",
    "reschedule_narrowing",
    "backfill_prompt",
    "backfill_running",
    "leave_backfill_prompt",
    "leave_backfill_running",
    "completed",
    "failed",
]
RescheduleVote = Literal["accept", "decline", "pending", "expired"]


@dataclass
class Invitation:
    id: str
    task_id: str
    user_id: str
    user_info: dict[str, Any]  # nickname, email, etc.
    status: InvitationStatus = "pending"
    sent_at: float = 0.0
    responded_at: float | None = None
    batch_index: int = 0


@dataclass
class BookingTask:
    id: str
    session_id: str
    client_id: str | None
    activity: str
    location: str
    desired_time: str | None
    headcount: int
    status: BookingStatus = "running"
    candidates: list[dict[str, Any]] = field(default_factory=list)
    current_batch: int = 0
    invitations: list[Invitation] = field(default_factory=list)
    accepted_users: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    speed_multiplier: float = 1.0
    notifications: list[dict[str, Any]] = field(default_factory=list)
    # Additional context
    gender_preference: str | None = None
    level: str | None = None
    pace: str | None = None
    availability_slots: list[str] = field(default_factory=list)
    additional_requirements: str | None = None
    # Match statistics for progress display
    match_stats: dict[str, Any] = field(default_factory=dict)
    # The selected time slot when everyone can meet
    selected_slot: str | None = None
    # Dynamic slot narrowing: current available slots (narrows as people accept)
    current_slots: list[str] = field(default_factory=list)
    # Resolved concrete booking details (set on completion)
    booked_time: str | None = None  # "Thu, Feb 27, 7:00 AM – 9:00 AM"
    booked_location: str | None = None  # "Crissy Field"
    booked_iso_start: str | None = None  # "2026-02-27T07:00:00"
    booked_iso_end: str | None = None  # "2026-02-27T09:00:00"
    cancel_flow_id: str | None = None  # Link to active CancelFlow


@dataclass
class RescheduleResponse:
    """Tracks a participant's vote on a reschedule request."""
    user_id: str
    user_info: dict[str, Any]
    vote: RescheduleVote = "pending"
    responded_at: float | None = None


@dataclass
class CancelFlow:
    """Tracks the state of a cancel_booking operation."""
    id: str
    task_id: str
    session_id: str
    cancelling_user_id: str
    intention: CancelIntention | None = None
    status: CancelFlowStatus = "awaiting_intention"
    # Reschedule path state
    reschedule_responses: list[RescheduleResponse] = field(default_factory=list)
    remaining_participants: list[dict[str, Any]] = field(default_factory=list)
    departed_participants: list[dict[str, Any]] = field(default_factory=list)
    new_slots: list[str] = field(default_factory=list)
    # Backfill state (shared by both paths)
    backfill_approved: bool = False
    backfill_candidates: list[dict[str, Any]] = field(default_factory=list)
    backfill_invitations: list[Invitation] = field(default_factory=list)
    backfill_deadline: float = 0.0  # 30 min before event start (epoch seconds)
    # Leave path: new booking for leaving user
    replacement_task_id: str | None = None
    excluded_slots: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    notifications: list[dict[str, Any]] = field(default_factory=list)


class BookingTaskStore:
    """In-memory store for booking tasks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, BookingTask] = {}
        self._cancel_flows: dict[str, CancelFlow] = {}
        self._session_speeds: dict[str, float] = {}  # session_id → speed

    def create(
        self,
        *,
        session_id: str,
        client_id: str | None,
        activity: str,
        location: str,
        desired_time: str | None,
        headcount: int,
        candidates: list[dict[str, Any]],
        gender_preference: str | None = None,
        level: str | None = None,
        pace: str | None = None,
        availability_slots: list[str] | None = None,
        additional_requirements: str | None = None,
        match_stats: dict[str, Any] | None = None,
        selected_slot: str | None = None,
        current_slots: list[str] | None = None,
    ) -> BookingTask:
        task_id = str(uuid.uuid4())
        task = BookingTask(
            id=task_id,
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
            availability_slots=availability_slots or [],
            additional_requirements=additional_requirements,
            match_stats=match_stats or {},
            selected_slot=selected_slot,
            current_slots=current_slots or availability_slots or [],
            speed_multiplier=self._session_speeds.get(session_id, 1.0),
        )
        with self._lock:
            self._tasks[task_id] = task
        return task

    def get(self, task_id: str) -> BookingTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def get_by_session(self, session_id: str) -> list[BookingTask]:
        with self._lock:
            return [t for t in self._tasks.values() if t.session_id == session_id]

    def get_invitation(self, invitation_id: str) -> Invitation | None:
        with self._lock:
            for task in self._tasks.values():
                for inv in task.invitations:
                    if inv.id == invitation_id:
                        return inv
        return None

    def get_task_for_invitation(self, invitation_id: str) -> BookingTask | None:
        with self._lock:
            for task in self._tasks.values():
                for inv in task.invitations:
                    if inv.id == invitation_id:
                        return task
        return None

    def get_pending_invitations_for_user(self, user_id: str) -> list[dict[str, Any]]:
        """Return all pending invitations addressed to *user_id*."""
        with self._lock:
            results: list[dict[str, Any]] = []
            for task in self._tasks.values():
                if task.status != "running":
                    continue
                for inv in task.invitations:
                    if inv.user_id == user_id and inv.status == "pending":
                        results.append({
                            "invitationId": inv.id,
                            "taskId": task.id,
                            "activity": task.activity,
                            "location": task.location,
                            "desiredTime": task.desired_time,
                            "sentAt": inv.sent_at,
                        })
            return results

    def pop_notifications(self, session_id: str) -> list[dict[str, Any]]:
        """Get and clear notifications for a session."""
        with self._lock:
            notifications: list[dict[str, Any]] = []
            for task in self._tasks.values():
                if task.session_id == session_id and task.notifications:
                    notifications.extend(task.notifications)
                    task.notifications = []
            return notifications

    # ------------------------------------------------------------------
    # Session-level speed
    # ------------------------------------------------------------------

    def set_session_speed(self, session_id: str, multiplier: float) -> None:
        """Set speed for ALL tasks in a session and store as default for new tasks."""
        with self._lock:
            self._session_speeds[session_id] = multiplier
            for task in self._tasks.values():
                if task.session_id == session_id:
                    task.speed_multiplier = multiplier

    def get_session_speed(self, session_id: str) -> float:
        return self._session_speeds.get(session_id, 1.0)

    # ------------------------------------------------------------------
    # Cancel flow management
    # ------------------------------------------------------------------

    def create_cancel_flow(
        self,
        *,
        task_id: str,
        session_id: str,
        cancelling_user_id: str,
    ) -> CancelFlow:
        flow_id = str(uuid.uuid4())
        flow = CancelFlow(
            id=flow_id,
            task_id=task_id,
            session_id=session_id,
            cancelling_user_id=cancelling_user_id,
        )
        with self._lock:
            self._cancel_flows[flow_id] = flow
        return flow

    def get_cancel_flow(self, flow_id: str) -> CancelFlow | None:
        with self._lock:
            return self._cancel_flows.get(flow_id)

    def get_cancel_flow_by_task(self, task_id: str) -> CancelFlow | None:
        with self._lock:
            for flow in self._cancel_flows.values():
                if flow.task_id == task_id and flow.status != "completed":
                    return flow
        return None

    def pop_cancel_notifications(self, session_id: str) -> list[dict[str, Any]]:
        """Get and clear cancel flow notifications for a session."""
        with self._lock:
            notifications: list[dict[str, Any]] = []
            for flow in self._cancel_flows.values():
                if flow.session_id == session_id and flow.notifications:
                    notifications.extend(flow.notifications)
                    flow.notifications = []
            return notifications
