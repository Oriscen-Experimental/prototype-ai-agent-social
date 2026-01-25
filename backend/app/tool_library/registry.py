from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from .deep_profile_analysis import execute_deep_profile_analysis
from .intelligent_discovery import execute_intelligent_discovery
from .models import DeepProfileAnalysisArgs, IntelligentDiscoveryArgs


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    execute: Callable[[dict[str, Any], dict[str, Any]], tuple[str, dict[str, Any], dict[str, Any]]]
    """
    execute(meta, args) -> (result_type, results_payload, last_results_payload)
    - result_type: "people" | "things" (maps to frontend results renderer)
    - results_payload: dict returned to orchestrator (may include assistantMessage, people/things, analysis)
    - last_results_payload: dict stored into session.meta["last_results"] when non-empty
    """


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="intelligent_discovery",
        description=(
            "Search & recommend people (social_connect) or events (event_discovery) using a fuzzy semantic_query + optional structured_filters. "
            "Returns a ranked list of plausible candidates. Generated results are saved in session memory for later deep analysis."
        ),
        input_model=IntelligentDiscoveryArgs,
        execute=lambda meta, args: execute_intelligent_discovery(meta=meta, args=args),
    ),
    ToolSpec(
        name="deep_profile_analysis",
        description=(
            "Analyze previously generated candidates/events by ID: fetch detail, compare multiple options, or explain compatibility. "
            "Uses only in-session memory (no external data) and returns structured highlights + next-step suggestions."
        ),
        input_model=DeepProfileAnalysisArgs,
        execute=lambda meta, args: execute_deep_profile_analysis(meta=meta, args=args),
    ),
]


def tool_by_name(name: str) -> ToolSpec | None:
    for t in TOOLS:
        if t.name == name:
            return t
    return None


def tool_schemas() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in TOOLS:
        out.append(
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_model.model_json_schema(),
            }
        )
    return out

