from __future__ import annotations

import time
from typing import Any, Literal

from .models import MemoryStore


def get_or_init_memory(meta: dict[str, Any]) -> MemoryStore:
    raw = meta.get("memory")
    if isinstance(raw, dict):
        try:
            return MemoryStore.model_validate(raw)
        except Exception:
            pass
    mem = MemoryStore()
    meta["memory"] = mem.model_dump()
    return mem


def record_discovery_run(
    *,
    meta: dict[str, Any],
    domain: Literal["person", "event"],
    semantic_query: str,
    structured_filters: dict[str, Any] | None,
    result_ids: list[str],
) -> None:
    mem = get_or_init_memory(meta)
    mem.runs.append(
        {
            "tool": "intelligent_discovery",
            "domain": domain,
            "semantic_query": semantic_query,
            "structured_filters": structured_filters or {},
            "result_ids": result_ids,
            "at_ms": int(time.time() * 1000),
        }
    )
    meta["memory"] = mem.model_dump()


def upsert_entities(*, meta: dict[str, Any], domain: Literal["person", "event"], items: list[dict[str, Any]]) -> None:
    mem = get_or_init_memory(meta)
    if domain == "person":
        for it in items:
            if isinstance(it, dict) and isinstance(it.get("id"), str) and it["id"].strip():
                mem.profiles[it["id"]] = it
    else:
        for it in items:
            if isinstance(it, dict) and isinstance(it.get("id"), str) and it["id"].strip():
                mem.events[it["id"]] = it
    meta["memory"] = mem.model_dump()


def get_entity_by_id(meta: dict[str, Any], entity_id: str) -> tuple[Literal["person", "event"] | None, dict[str, Any] | None]:
    mem = get_or_init_memory(meta)
    if entity_id in mem.profiles:
        return "person", mem.profiles.get(entity_id)
    if entity_id in mem.events:
        return "event", mem.events.get(entity_id)
    return None, None

