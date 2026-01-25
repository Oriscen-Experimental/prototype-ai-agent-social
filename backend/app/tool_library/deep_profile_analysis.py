from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel

from ..llm import call_gemini_json
from .memory import get_entity_by_id
from .models import DeepProfileAnalysisArgs


logger = logging.getLogger(__name__)


class _LLMAnalysis(BaseModel):
    assistantMessage: str
    data: dict[str, Any] | None = None


def _build_analysis_prompt(*, args: dict[str, Any], targets: list[dict[str, Any]]) -> str:
    return (
        "You are the deep_profile_analysis tool.\n"
        "You analyze PEOPLE or EVENTS that were previously returned by intelligent_discovery.\n"
        "Return ONLY valid JSON (no markdown):\n"
        "{\n"
        '  "assistantMessage": "English explanation and recommendations",\n'
        '  "data": { "highlights": [...], "risks": [...], "next_steps": [...], "comparison": {...} }\n'
        "}\n"
        "\n"
        "Rules:\n"
        "- Use ONLY the provided target objects as factual ground truth.\n"
        "- You may add general advice (non-factual) and suggestions for next steps.\n"
        "- Keep it safe and respectful.\n"
        "- All text must be English ONLY.\n"
        "\n"
        f"Args JSON: {json.dumps(args, ensure_ascii=False)}\n"
        f"Targets JSON: {json.dumps(targets, ensure_ascii=False)}\n"
    )


def execute_deep_profile_analysis(
    *, meta: dict[str, Any], args: dict[str, Any]
) -> tuple[Literal["people", "things"], dict[str, Any], dict[str, Any]]:
    parsed = DeepProfileAnalysisArgs(**(args or {}))

    targets: list[dict[str, Any]] = []
    domain_counts = {"person": 0, "event": 0}
    for tid in parsed.target_ids[:20]:
        dom, ent = get_entity_by_id(meta, tid)
        if dom and isinstance(ent, dict):
            targets.append(ent)
            domain_counts[dom] += 1

    if not targets:
        msg = "I can analyze items you’ve already generated in this session, but I can’t find those IDs. Try selecting from the latest results."
        return "people", {"assistantMessage": msg, "analysis": {"code": "NOT_FOUND"}, "generatedBy": "mock"}, {"type": "people", "items": []}

    # Decide a result channel for the API contract (keep as chat-like by default).
    result_type: Literal["people", "things"]
    if domain_counts["event"] > domain_counts["person"]:
        result_type = "things"
    else:
        result_type = "people"

    args_dict = parsed.model_dump()
    try:
        llm_res = call_gemini_json(prompt=_build_analysis_prompt(args=args_dict, targets=targets), response_model=_LLMAnalysis)
        payload = {"assistantMessage": llm_res.assistantMessage, "analysis": llm_res.data or {}, "generatedBy": "llm"}
        # last_results_payload: keep existing last_results unchanged for analysis (do not overwrite discovery results)
        return result_type, payload, {}
    except Exception as e:
        logger.info("[deep_profile_analysis] llm_failed fallback err=%s", type(e).__name__)

    # Deterministic fallback.
    mode = parsed.analysis_mode
    if mode == "detail":
        msg = "Here’s a quick detail view (mock):\n" + "\n".join([f"- {t.get('name') or t.get('title')}" for t in targets[:5]])
    elif mode == "compare":
        msg = "Here’s a lightweight comparison (mock):\n" + "\n".join([f"- Candidate: {t.get('name') or t.get('title')}" for t in targets[:5]])
    else:
        msg = "Here’s a quick compatibility take (mock):\n" + "\n".join([f"- {t.get('name') or t.get('title')}: looks promising." for t in targets[:3]])
    return result_type, {"assistantMessage": msg, "analysis": {"code": "LLM_UNAVAILABLE"}, "generatedBy": "mock"}, {}
