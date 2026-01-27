from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel

from ..llm import call_gemini_json
from ..models import Group, Profile
from .models import ResultsRefineArgs

class _LLMRefineOut(BaseModel):
    assistantMessage: str
    selected_ids: list[str]


def _compact_candidates(domain: Literal["person", "event"], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items[:120]:
        if not isinstance(it, dict):
            continue
        if domain == "person":
            out.append(
                {
                    "id": it.get("id"),
                    "name": it.get("name"),
                    "presence": it.get("presence"),
                    "city": it.get("city"),
                    "headline": it.get("headline"),
                    "score": it.get("score"),
                    "topics": it.get("topics"),
                    "about": (it.get("about") or [])[:2] if isinstance(it.get("about"), list) else None,
                }
            )
        else:
            out.append(
                {
                    "id": it.get("id"),
                    "title": it.get("title"),
                    "city": it.get("city"),
                    "location": it.get("location"),
                    "level": it.get("level"),
                    "availability": it.get("availability"),
                    "memberCount": it.get("memberCount"),
                    "capacity": it.get("capacity"),
                    "notes": (it.get("notes") or [])[:2] if isinstance(it.get("notes"), list) else None,
                }
            )
    return out


def _build_refine_prompt(*, domain: Literal["person", "event"], instruction: str, limit: int, candidates: list[dict[str, Any]]) -> str:
    return (
        "You are the results_refine tool for a social agent.\n"
        "Task: refine a given list of visible results using the user's instruction.\n"
        "Refine means: filter out non-matching items, then rerank the remaining ones.\n"
        "\n"
        "Return ONLY valid JSON (no markdown):\n"
        "{\n"
        '  "assistantMessage": "English explanation of what you filtered/sorted and why",\n'
        '  "selected_ids": ["id1", "id2", ...]\n'
        "}\n"
        "\n"
        "Rules:\n"
        "- You MUST ONLY pick from the provided candidates by id.\n"
        "- Do NOT invent new ids, people, events, or locations.\n"
        "- If nothing matches, return selected_ids=[] and explain briefly.\n"
        "- Respect limit: return at most limit ids (limit can be 0).\n"
        "- All text must be English ONLY.\n"
        "\n"
        f"Domain: {domain}\n"
        f"Limit: {limit}\n"
        f"User instruction: {instruction}\n"
        f"Candidates (compact): {json.dumps(_compact_candidates(domain, candidates), ensure_ascii=False)}\n"
    )


def _stable_limit_from_instruction(instruction: str, default_limit: int) -> int:
    m = (instruction or "").strip()
    mm = re.search(r"\b(\d{1,2})\b", m)
    if not mm:
        return default_limit
    try:
        n = int(mm.group(1))
        return max(0, min(20, n))
    except Exception:
        return default_limit


def execute_results_refine(*, meta: dict[str, Any], args: dict[str, Any]) -> tuple[Literal["people", "things"], dict[str, Any], dict[str, Any]]:
    parsed = ResultsRefineArgs(**(args or {}))
    domain: Literal["person", "event"] = parsed.domain
    instruction = (parsed.instruction or "").strip()
    # Allow instruction-embedded counts even if planner didn't set limit.
    limit = _stable_limit_from_instruction(instruction, parsed.limit)

    candidates = parsed.candidates if isinstance(parsed.candidates, list) else []
    if not candidates:
        raise ValueError("results_refine: missing candidates (this tool can only refine UI-visible results)")

    # Validate candidate shapes (full objects) while keeping the tool resilient.
    valid_items: list[dict[str, Any]] = []
    if domain == "person":
        for it in candidates[:200]:
            try:
                p = Profile.model_validate(it)
                valid_items.append(p.model_dump())
            except Exception:
                continue
    else:
        for it in candidates[:200]:
            try:
                g = Group.model_validate(it)
                valid_items.append(g.model_dump())
            except Exception:
                continue

    if not valid_items:
        raise ValueError("results_refine: provided candidates are missing required fields")

    llm_res = call_gemini_json(
        prompt=_build_refine_prompt(domain=domain, instruction=instruction, limit=limit, candidates=valid_items),
        response_model=_LLMRefineOut,
    )
    allow = {it.get("id") for it in valid_items if isinstance(it.get("id"), str)}
    selected_ids = [x for x in llm_res.selected_ids if isinstance(x, str) and x in allow]
    if limit >= 0:
        selected_ids = selected_ids[:limit]
    selected = [it for it in valid_items if it.get("id") in set(selected_ids)]
    # preserve model ordering (selected_ids) rather than original order
    by_id = {it.get("id"): it for it in selected if isinstance(it.get("id"), str)}
    ordered = [by_id[i] for i in selected_ids if i in by_id]

    msg = (llm_res.assistantMessage or "").strip() or "Refined the visible results."
    if domain == "person":
        people = [Profile.model_validate(x) for x in ordered]
        items = [p.model_dump() for p in people]
        return "people", {"assistantMessage": msg, "people": people, "generatedBy": "llm"}, {"type": "people", "items": items}
    things = [Group.model_validate(x) for x in ordered]
    items = [g.model_dump() for g in things]
    return "things", {"assistantMessage": msg, "things": things, "generatedBy": "llm"}, {"type": "things", "items": items}
