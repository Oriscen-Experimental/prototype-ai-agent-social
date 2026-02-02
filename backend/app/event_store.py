from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StoredEvent:
    client_id: str
    at_ms: int
    type: str
    session_id: str | None
    page: str | None
    payload: dict[str, Any] | None
    user_agent: str | None


class EventStore:
    """Append-only per-client event log (JSONL).

    Notes:
    - Default directory is ephemeral on Render unless you attach a persistent disk.
    - Each client gets its own file: <events_dir>/<client_id>.jsonl
    """

    def __init__(self, events_dir: str) -> None:
        self._events_dir = os.path.abspath(events_dir)
        self._lock = threading.Lock()
        os.makedirs(self._events_dir, exist_ok=True)

    def _path_for(self, client_id: str) -> str:
        safe = "".join(ch for ch in client_id if ch.isalnum() or ch in ("-", "_"))
        if not safe:
            safe = "unknown"
        return os.path.join(self._events_dir, f"{safe}.jsonl")

    def append_many(self, client_id: str, events: list[StoredEvent]) -> None:
        if not client_id or not events:
            return

        path = self._path_for(client_id)
        lines = []
        for e in events:
            lines.append(
                json.dumps(
                    {
                        "client_id": e.client_id,
                        "at_ms": e.at_ms,
                        "type": e.type,
                        "sessionId": e.session_id,
                        "page": e.page,
                        "payload": e.payload,
                        "userAgent": e.user_agent,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )

        with self._lock:
            with open(path, "a", encoding="utf-8") as f:
                for line in lines:
                    f.write(line)
                    f.write("\n")

    def load_all(self, client_id: str, limit: int = 5000) -> list[dict[str, Any]]:
        path = self._path_for(client_id)
        if not os.path.exists(path):
            return []
        out: list[dict[str, Any]] = []
        with self._lock:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if len(out) >= limit:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        v = json.loads(line)
                        if isinstance(v, dict):
                            out.append(v)
                    except Exception:
                        continue
        return out

    def list_clients(self, limit: int = 2000) -> list[dict[str, Any]]:
        """List known client ids with basic file metadata."""
        try:
            names = os.listdir(self._events_dir)
        except Exception:
            return []

        rows: list[dict[str, Any]] = []
        for name in names:
            if not name.endswith(".jsonl"):
                continue
            client_id = name[: -len(".jsonl")]
            if not client_id:
                continue
            path = os.path.join(self._events_dir, name)
            try:
                st = os.stat(path)
            except Exception:
                continue

            # Read first line to get createdAtMs (first event timestamp)
            created_at_ms: int | None = None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        first_event = json.loads(first_line)
                        if isinstance(first_event, dict) and "at_ms" in first_event:
                            created_at_ms = int(first_event["at_ms"])
            except Exception:
                pass

            row: dict[str, Any] = {
                "clientId": client_id,
                "updatedAtMs": int(st.st_mtime * 1000),
                "bytes": int(st.st_size),
            }
            if created_at_ms is not None:
                row["createdAtMs"] = created_at_ms
            rows.append(row)

        rows.sort(key=lambda r: int(r.get("updatedAtMs") or 0), reverse=True)
        return rows[: max(1, min(2000, int(limit)))]

    def raw_path_for_client(self, client_id: str) -> str:
        """Return absolute path to client's JSONL file (may not exist)."""
        return self._path_for(client_id)
