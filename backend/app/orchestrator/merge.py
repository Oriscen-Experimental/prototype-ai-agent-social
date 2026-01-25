from __future__ import annotations

from typing import Any


def _deep_set(target: dict[str, Any], path: list[str], value: Any) -> None:
    cur: dict[str, Any] = target
    for key in path[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[path[-1]] = value


def merge_slots(base: dict[str, Any] | None, incoming: dict[str, Any] | None) -> dict[str, Any]:
    """
    Merge slots with support for dotted keys produced by the deck UI.
    Example: {"structured_filters.location": "Shanghai"} becomes {"structured_filters": {"location": "Shanghai"}}.
    """
    merged: dict[str, Any] = dict(base or {})
    for k, v in (incoming or {}).items():
        if v is None:
            continue
        if not isinstance(k, str) or not k:
            continue
        if "." not in k:
            merged[k] = v
            continue
        path = [p for p in k.split(".") if p]
        if not path:
            continue
        _deep_set(merged, path, v)
    return merged


def normalize_tool_args(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """
    Best-effort normalization of values coming from the UI:
    - Split comma-separated strings into lists for known list fields (tags, target_ids).
    """
    out = dict(args or {})

    if tool_name == "deep_profile_analysis":
        v = out.get("target_ids")
        if isinstance(v, str):
            ids = [x.strip() for x in v.split(",") if x.strip()]
            out["target_ids"] = ids
        return out

    if tool_name == "intelligent_discovery":
        sf = out.get("structured_filters")
        if isinstance(sf, dict):
            tags = sf.get("tags")
            if isinstance(tags, str):
                sf = dict(sf)
                sf["tags"] = [x.strip() for x in tags.split(",") if x.strip()]
                out["structured_filters"] = sf
        return out

    return out

