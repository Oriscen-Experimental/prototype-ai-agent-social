from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


Role = Literal["user", "assistant", "system"]


@dataclass
class ChatTurn:
    role: Role
    text: str
    at_ms: int


@dataclass
class Session:
    id: str
    history: list[ChatTurn] = field(default_factory=list)
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    meta: dict[str, Any] = field(default_factory=dict)


class SessionStore:
    def __init__(self, ttl_seconds: int = 6 * 60 * 60) -> None:
        self._ttl_ms = max(60_000, int(ttl_seconds) * 1000)
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _expired(self, s: Session, now_ms: int) -> bool:
        return (now_ms - s.updated_at_ms) > self._ttl_ms

    def cleanup(self) -> int:
        now_ms = self._now_ms()
        removed = 0
        with self._lock:
            for sid in list(self._sessions.keys()):
                if self._expired(self._sessions[sid], now_ms):
                    self._sessions.pop(sid, None)
                    removed += 1
        return removed

    def create(self) -> Session:
        now_ms = self._now_ms()
        sid = str(uuid.uuid4())
        s = Session(id=sid, created_at_ms=now_ms, updated_at_ms=now_ms)
        with self._lock:
            self._sessions[sid] = s
        return s

    def get(self, session_id: str) -> Session | None:
        if not session_id:
            return None
        now_ms = self._now_ms()
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                return None
            if self._expired(s, now_ms):
                self._sessions.pop(session_id, None)
                return None
            return s

    def touch(self, s: Session) -> None:
        s.updated_at_ms = self._now_ms()

    def append(self, s: Session, role: Role, text: str) -> None:
        s.history.append(ChatTurn(role=role, text=text, at_ms=self._now_ms()))
        self.touch(s)

    def reset(self, s: Session) -> None:
        now_ms = self._now_ms()
        s.history = []
        s.meta = {}
        s.updated_at_ms = now_ms
