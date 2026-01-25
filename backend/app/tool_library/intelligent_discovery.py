from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel

from ..llm import GEMINI_MODEL, call_gemini_json
from ..models import Group, Profile
from .memory import record_discovery_run, upsert_entities
from .models import IntelligentDiscoveryArgs


logger = logging.getLogger(__name__)


class _LLMDiscoveryPeople(BaseModel):
    people: list[dict[str, Any]]
    assistantMessage: str | None = None


class _LLMDiscoveryEvents(BaseModel):
    events: list[dict[str, Any]]
    assistantMessage: str | None = None


def _build_people_prompt(*, args: dict[str, Any]) -> str:
    return (
        "You are the intelligent_discovery tool for a social agent.\n"
        "Goal: generate imaginary but plausible PEOPLE recommendations that match the user's intent.\n"
        "Domain-aware filters:\n"
        "- Common: structured_filters.location (city/region/is_online)\n"
        "- Person: structured_filters.person_filters (age_range/gender/industry/role/intent_tags)\n"
        "Return ONLY valid JSON (no markdown):\n"
        "{\n"
        '  "people": [Profile, ...],\n'
        '  "assistantMessage": "optional short English summary"\n'
        "}\n"
        "\n"
        "Profile schema:\n"
        "- id: string\n"
        '- kind: \"human\" (string)\n'
        '- presence: \"online\" or \"offline\"\n'
        "- name: string\n"
        "- city: string\n"
        "- headline: string\n"
        "- score: integer 0-100\n"
        "- badges: array of {id,label,description} (0-2 items)\n"
        "- about: array of strings (2-4)\n"
        "- matchReasons: array of strings (2-4)\n"
        "- topics: array of strings (3-6)\n"
        "- aiNote: optional string (1-2 lines) explaining why this is a good next step\n"
        "\n"
        "Requirements:\n"
        "- Generate exactly N people based on args.limit.\n"
        "- Respect structured_filters (especially location + demographics).\n"
        "- Do NOT invent overly sensitive or private details. Keep it safe and respectful.\n"
        "- All free-text fields must be in English ONLY.\n"
        "\n"
        f"Args JSON: {json.dumps(args, ensure_ascii=False)}\n"
    )


def _build_events_prompt(*, args: dict[str, Any]) -> str:
    return (
        "You are the intelligent_discovery tool for a social agent.\n"
        "Goal: generate imaginary but plausible EVENT/GROUP recommendations that match the user's intent.\n"
        "Domain-aware filters:\n"
        "- Common: structured_filters.location (city/region/is_online)\n"
        "- Event: structured_filters.event_filters (time_range/price_range/category)\n"
        "Return ONLY valid JSON (no markdown):\n"
        "{\n"
        '  "events": [Event, ...],\n'
        '  "assistantMessage": "optional short English summary"\n'
        "}\n"
        "\n"
        "Event schema (use this exact shape):\n"
        "- id: string\n"
        "- title: string\n"
        "- city: string\n"
        "- location: string\n"
        "- level: string\n"
        "- availability: {status: \"open\"|\"scheduled\"|\"full\", startAt?: int(ms epoch)}\n"
        "- memberCount: int\n"
        "- capacity: int\n"
        "- memberAvatars: array of 1-letter strings\n"
        "- members: array of {id,name,headline,badges}\n"
        "- notes: array of strings\n"
        "\n"
        "Requirements:\n"
        "- Generate exactly N events based on args.limit.\n"
        "- Respect structured_filters (especially location + time_range + price_range).\n"
        "- Keep it realistic. If time_range is provided, try to align availability.startAt.\n"
        "- All free-text fields must be in English ONLY.\n"
        "\n"
        f"Args JSON: {json.dumps(args, ensure_ascii=False)}\n"
    )


def execute_intelligent_discovery(*, meta: dict[str, Any], args: dict[str, Any]) -> tuple[Literal["people", "things"], dict[str, Any], dict[str, Any]]:
    parsed = IntelligentDiscoveryArgs(**(args or {}))
    args_dict = parsed.model_dump()

    try:
        if parsed.domain == "person":
            llm_res = call_gemini_json(prompt=_build_people_prompt(args=args_dict), response_model=_LLMDiscoveryPeople)
            people = [Profile.model_validate(p) for p in llm_res.people[: parsed.limit]]
            items = [p.model_dump() for p in people]
            upsert_entities(meta=meta, domain="person", items=items)
            record_discovery_run(
                meta=meta,
                domain="person",
                semantic_query=parsed.semantic_query,
                structured_filters=(parsed.structured_filters.model_dump() if parsed.structured_filters else None),
                result_ids=[p["id"] for p in items if isinstance(p.get("id"), str)],
            )
            return (
                "people",
                {"people": people, "assistantMessage": (llm_res.assistantMessage or "").strip(), "generatedBy": "llm"},
                {"type": "people", "items": items},
            )

        llm_res = call_gemini_json(prompt=_build_events_prompt(args=args_dict), response_model=_LLMDiscoveryEvents)
        events = [Group.model_validate(g) for g in llm_res.events[: parsed.limit]]
        items = [g.model_dump() for g in events]
        upsert_entities(meta=meta, domain="event", items=items)
        record_discovery_run(
            meta=meta,
            domain="event",
            semantic_query=parsed.semantic_query,
            structured_filters=(parsed.structured_filters.model_dump() if parsed.structured_filters else None),
            result_ids=[g["id"] for g in items if isinstance(g.get("id"), str)],
        )
        return (
            "things",
            {"things": events, "assistantMessage": (llm_res.assistantMessage or "").strip(), "generatedBy": "llm"},
            {"type": "things", "items": items},
        )
    except Exception as e:
        # Prototype-friendly fallback: keep the tool callable even without LLM credentials.
        logger.info("[intelligent_discovery] llm_failed fallback err=%s", type(e).__name__)

    # Deterministic fallback (minimal but safe).
    loc = parsed.structured_filters.location
    city = (loc.city or "").strip() if loc and not loc.is_online else ""
    if loc and loc.is_online:
        city = "Online"

    if parsed.domain == "person":
        # Extremely lightweight mock: still validates the Profile schema.
        people = [
            Profile(
                id=f"mock_person_{i}",
                kind="human",
                presence="online" if i % 2 == 0 else "offline",
                name=f"Person {i+1}",
                city=city or "Unknown",
                headline=f"{(parsed.semantic_query or 'Discovery')[:48]} · (mock)",
                score=80 - i,
                badges=[{"id": "mock", "label": "Mock", "description": "Generated without LLM credentials."}],
                about=["Prototype result (mock)."],
                matchReasons=["Matches your semantic_query (mock)."],
                topics=["Social", "Chat"],
                aiNote="LLM unavailable; showing a placeholder candidate list.",
            )
            for i in range(min(parsed.limit, 5))
        ]
        items = [p.model_dump() for p in people]
        upsert_entities(meta=meta, domain="person", items=items)
        record_discovery_run(
            meta=meta,
            domain="person",
            semantic_query=parsed.semantic_query,
            structured_filters=(parsed.structured_filters.model_dump() if parsed.structured_filters else None),
            result_ids=[p["id"] for p in items if isinstance(p.get("id"), str)],
        )
        return (
            "people",
            {"people": people, "assistantMessage": "Here are a few mock people (LLM unavailable).", "generatedBy": "mock"},
            {"type": "people", "items": items},
        )

    events = [
        Group(
            id=f"mock_event_{i}",
            title=f"{(parsed.semantic_query or 'Discovery')[:48]} · Event {i+1} (mock)",
            city=city or "Unknown",
            location="Somewhere (mock)",
            level="Beginner-friendly (mock)",
            availability={"status": "open"},
            memberCount=max(0, 6 - i),
            capacity=10,
            memberAvatars=["A", "B"],
            members=[],
            notes=["Prototype result (mock).", "Generated without LLM credentials."],
        )
        for i in range(min(parsed.limit, 5))
    ]
    items = [g.model_dump() for g in events]
    upsert_entities(meta=meta, domain="event", items=items)
    record_discovery_run(
        meta=meta,
        domain="event",
        semantic_query=parsed.semantic_query,
        structured_filters=(parsed.structured_filters.model_dump() if parsed.structured_filters else None),
        result_ids=[g["id"] for g in items if isinstance(g.get("id"), str)],
    )
    return "things", {"things": events, "assistantMessage": "Here are a few mock events (LLM unavailable).", "generatedBy": "mock"}, {"type": "things", "items": items}
