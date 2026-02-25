"""In-memory storage for booking tasks."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


InvitationStatus = Literal["pending", "accepted", "declined", "expired"]
BookingStatus = Literal["running", "completed", "failed", "cancelled"]


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


class BookingTaskStore:
    """In-memory store for booking tasks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, BookingTask] = {}

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

    def pop_notifications(self, session_id: str) -> list[dict[str, Any]]:
        """Get and clear notifications for a session."""
        with self._lock:
            notifications: list[dict[str, Any]] = []
            for task in self._tasks.values():
                if task.session_id == session_id and task.notifications:
                    notifications.extend(task.notifications)
                    task.notifications = []
            return notifications
