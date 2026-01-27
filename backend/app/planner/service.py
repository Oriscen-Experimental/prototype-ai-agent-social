from __future__ import annotations

from typing import Any

from ..llm import LLMPlannerDecision, build_planner_prompt, call_gemini_json


def run_planner(
    *,
    tool_schemas: list[dict[str, Any]],
    session_id: str,
    summary: str,
    history: list[dict[str, Any]],
) -> LLMPlannerDecision:
    return call_gemini_json(
        prompt=build_planner_prompt(
            tool_schemas=tool_schemas,
            session_id=session_id,
            summary=summary,
            history=history,
        ),
        response_model=LLMPlannerDecision,
    )

