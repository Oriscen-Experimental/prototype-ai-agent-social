from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel

from .llm import LLMPeople, LLMThings, build_people_generation_prompt, build_things_generation_prompt, call_gemini_json
from .models import FindPeopleRequest, FindThingsRequest, Group, Profile


ToolName = Literal["find_people", "find_things"]


@dataclass(frozen=True)
class ToolSpec:
    name: ToolName
    description: str
    input_model: type[BaseModel]
    execute: Callable[[dict[str, Any]], tuple[str, dict[str, Any], dict[str, Any]]]
    """
    Returns: (result_type, results_payload, last_results_payload)
    - result_type: "people" | "things"
    - results_payload: dict to return to client, e.g. {"people": [Profile, ...]}
    - last_results_payload: dict to store in session.meta["last_results"]
    """


def _execute_find_people(args: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    req = FindPeopleRequest(**(args or {}))
    llm_res = call_gemini_json(
        prompt=build_people_generation_prompt(criteria=req.model_dump()),
        response_model=LLMPeople,
    )
    people = [Profile.model_validate(p) for p in llm_res.people]
    return (
        "people",
        {"people": people, "assistantMessage": (llm_res.assistantMessage or "").strip()},
        {"type": "people", "items": [p.model_dump() for p in people]},
    )


def _execute_find_things(args: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    req = FindThingsRequest(**(args or {}))
    llm_res = call_gemini_json(
        prompt=build_things_generation_prompt(criteria=req.model_dump()),
        response_model=LLMThings,
    )
    things = [Group.model_validate(g) for g in llm_res.things]
    return (
        "things",
        {"things": things, "assistantMessage": (llm_res.assistantMessage or "").strip()},
        {"type": "things", "items": [g.model_dump() for g in things]},
    )


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="find_people",
        description="Generate 5 imaginary but plausible people matches for a social app based on criteria.",
        input_model=FindPeopleRequest,
        execute=_execute_find_people,
    ),
    ToolSpec(
        name="find_things",
        description="Generate 5 imaginary but plausible groups/activities based on a title and neededCount.",
        input_model=FindThingsRequest,
        execute=_execute_find_things,
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
                "inputSchema": t.input_model.model_json_schema(),
            }
        )
    return out

