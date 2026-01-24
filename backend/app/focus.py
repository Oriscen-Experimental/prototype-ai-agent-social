from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal


LastResultsType = Literal["people", "things"]


@dataclass(frozen=True)
class Focus:
    type: LastResultsType
    index: int
    label: str
    item: dict[str, Any]


_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}


def _normalize(s: str) -> str:
    return (s or "").strip()


def list_result_labels(last_results: dict[str, Any] | None) -> list[str]:
    if not isinstance(last_results, dict):
        return []
    t = last_results.get("type")
    items = last_results.get("items")
    if t not in {"people", "things"} or not isinstance(items, list):
        return []

    out: list[str] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        label = it.get("name") if t == "people" else it.get("title")
        if isinstance(label, str) and label.strip():
            out.append(label.strip())
    return out


def _extract_index_reference(message: str) -> int | None:
    m = _normalize(message)
    if not m:
        return None

    # 第1个 / 第 2 位 / 第三
    mm = re.search(r"第\s*([1-5])\s*(?:个|位|条|名)?", m)
    if mm:
        return int(mm.group(1)) - 1
    mm = re.search(r"第\s*([一二三四五])\s*(?:个|位|条|名)?", m)
    if mm:
        return _CN_NUM.get(mm.group(1), 0) - 1
    return None


_FOLLOWUP_TOKENS = [
    "他",
    "她",
    "ta",
    "TA",
    "这个",
    "那个",
    "上面",
    "刚才",
    "上一",
    "上一个",
    "上一个人",
    "上一个活动",
    "前面",
]


def _looks_like_followup(message: str) -> bool:
    m = _normalize(message)
    if not m:
        return False
    return any(tok in m for tok in _FOLLOWUP_TOKENS)


def pick_focus(message: str, last_results: dict[str, Any] | None, previous: Focus | None) -> Focus | None:
    """
    Best-effort: resolve which person/group the user is referring to.
    - Exact mention by label (name/title)
    - Ordinal reference (第一个/第2个…)
    - Pronoun follow-up (他/她/这个…) → keep previous focus
    """
    if not isinstance(last_results, dict):
        return previous if (previous and _looks_like_followup(message)) else None

    t = last_results.get("type")
    items = last_results.get("items")
    if t not in {"people", "things"} or not isinstance(items, list) or not items:
        return previous if (previous and _looks_like_followup(message)) else None

    msg = _normalize(message)
    msg_lower = msg.lower()

    # 1) explicit label mention
    for idx, it in enumerate(items[:20]):
        if not isinstance(it, dict):
            continue
        label = it.get("name") if t == "people" else it.get("title")
        if not isinstance(label, str) or not label.strip():
            continue
        lab = label.strip()
        if lab.lower() in msg_lower:
            return Focus(type=t, index=idx, label=lab, item=it)

    # 2) ordinal reference
    idx = _extract_index_reference(msg)
    if isinstance(idx, int) and 0 <= idx < len(items):
        it = items[idx]
        if isinstance(it, dict):
            label = it.get("name") if t == "people" else it.get("title")
            lab = label.strip() if isinstance(label, str) else f"第{idx+1}个"
            return Focus(type=t, index=idx, label=lab, item=it)

    # 3) pronoun follow-up keeps previous focus
    if previous and _looks_like_followup(msg):
        return previous

    return None


def should_include_results_in_planner(message: str, last_results: dict[str, Any] | None, focus: Focus | None) -> bool:
    """
    Avoid anchoring the planner on stale results.
    Only include when the user message likely refers to the last results/focus.
    """
    m = _normalize(message)
    if not m or not isinstance(last_results, dict):
        return False
    if focus is not None:
        return True
    labels = list_result_labels(last_results)
    if any(lab and lab.lower() in m.lower() for lab in labels):
        return True
    if _extract_index_reference(m) is not None:
        return True
    if any(tok in m for tok in ["结果", "候选", "上面", "刚才", "这几个人", "这些人", "这些活动", "这些组局"]):
        return True
    return False


def planner_last_results_payload(last_results: dict[str, Any] | None, focus: Focus | None) -> dict[str, Any] | None:
    """
    If we have a focus entity, pass a narrowed view to the planner to reduce distraction.
    """
    if not isinstance(last_results, dict):
        return None
    t = last_results.get("type")
    items = last_results.get("items")
    if t not in {"people", "things"} or not isinstance(items, list):
        return None
    if focus is None:
        return last_results
    if focus.type != t:
        return last_results
    return {"type": t, "items": [focus.item], "focusLabel": focus.label}


def redact_last_results_for_summary(last_results: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Keep memory summary small and non-repetitive: include only lightweight fields.
    """
    if not isinstance(last_results, dict):
        return None
    t = last_results.get("type")
    items = last_results.get("items")
    if t not in {"people", "things"} or not isinstance(items, list):
        return None

    safe_items: list[dict[str, Any]] = []
    for it in items[:10]:
        if not isinstance(it, dict):
            continue
        if t == "people":
            safe_items.append(
                {
                    "name": it.get("name"),
                    "city": it.get("city"),
                    "headline": it.get("headline"),
                    "score": it.get("score"),
                    "topics": it.get("topics"),
                }
            )
        else:
            safe_items.append(
                {
                    "title": it.get("title"),
                    "city": it.get("city"),
                    "location": it.get("location"),
                    "availability": it.get("availability"),
                    "memberCount": it.get("memberCount"),
                    "capacity": it.get("capacity"),
                }
            )
    return {"type": t, "items": safe_items}

