from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Literal, TypeVar

import json5
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash-lite"

Intent = Literal["unknown", "find_people", "find_things"]
OrchestratorPhase = Literal["discover", "collect", "search", "answer"]
PlannerDecisionType = Literal["chat", "collect", "tool"]


class UIBlock(BaseModel):
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class LLMOrchestration(BaseModel):
    intent: Intent
    slots: dict[str, Any] = Field(default_factory=dict)
    assistantMessage: str = Field(min_length=1)
    phase: OrchestratorPhase | None = None


class LLMPlannerDecision(BaseModel):
    decision: PlannerDecisionType
    assistantMessage: str = Field(min_length=1)
    intent: Intent = "unknown"
    slots: dict[str, Any] = Field(default_factory=dict)
    toolName: str | None = None
    toolArgs: dict[str, Any] | None = None
    uiBlocks: list[dict[str, Any]] | None = None
    phase: OrchestratorPhase | None = None


class LLMSummary(BaseModel):
    summary: str = Field(min_length=0)


class LLMPeople(BaseModel):
    people: list[dict[str, Any]]
    assistantMessage: str | None = None


class LLMThings(BaseModel):
    things: list[dict[str, Any]]
    assistantMessage: str | None = None


def _extract_first_json_object(text: str) -> str:
    s = (text or "").strip()
    if not s:
        raise ValueError("empty response")

    # Strip ``` fences if present
    if "```" in s:
        s = s.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no json object found")
    return s[start : end + 1]


def _loads_json_relaxed(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        return json5.loads(text)


@lru_cache(maxsize=1)
def _get_gemini_client():
    from google import genai

    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if api_key:
        logger.info("[llm] using gemini api_key auth")
        return genai.Client(api_key=api_key)

    project = (os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip()
    location = (os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1").strip()
    service_account_file = (os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE") or "/etc/secrets/google-credentials.json").strip()

    if not project:
        raise RuntimeError(
            "Missing Gemini credentials. Set GEMINI_API_KEY (AI Studio) or "
            "set GOOGLE_CLOUD_PROJECT + provide a service account file."
        )

    credentials = None
    if service_account_file and os.path.exists(service_account_file):
        from google.oauth2.service_account import Credentials

        credentials = Credentials.from_service_account_file(
            service_account_file,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        logger.info("[llm] using vertex ai service account file=%s", service_account_file)
    else:
        logger.info("[llm] using vertex ai without service account file (ADC)")

    return genai.Client(vertexai=True, project=project, location=location, credentials=credentials)


T = TypeVar("T", bound=BaseModel)


def call_gemini_json(*, prompt: str, response_model: type[T]) -> T:
    client = _get_gemini_client()
    config = None
    try:
        from google.genai import types

        temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.2") or "0.2")
        config = types.GenerateContentConfig(
            temperature=max(0.0, min(2.0, temperature)),
            response_mime_type="application/json",
        )
    except Exception:
        config = None

    if config is None:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    else:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=config)
    text = getattr(response, "text", None) or ""
    snippet = _extract_first_json_object(text)
    obj = _loads_json_relaxed(snippet)
    try:
        return response_model.model_validate(obj)
    except ValidationError as e:
        raise RuntimeError(f"gemini json validation failed: {e}") from e


def llm_config_status() -> dict[str, Any]:
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if api_key:
        return {
            "provider": "gemini",
            "model": GEMINI_MODEL,
            "authMode": "api_key",
            "configured": True,
        }

    project = (os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip()
    location = (os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1").strip()
    service_account_file = (os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE") or "/etc/secrets/google-credentials.json").strip()

    if project:
        return {
            "provider": "gemini",
            "model": GEMINI_MODEL,
            "authMode": "vertex_ai",
            "configured": True,
            "vertex": {
                "project": project,
                "location": location,
                "serviceAccountFile": service_account_file,
                "serviceAccountFileExists": bool(service_account_file and os.path.exists(service_account_file)),
            },
        }

    return {
        "provider": "gemini",
        "model": GEMINI_MODEL,
        "authMode": "missing",
        "configured": False,
        "hint": "Set GEMINI_API_KEY (AI Studio) OR set GOOGLE_CLOUD_PROJECT and provide /etc/secrets/google-credentials.json",
    }


def build_orchestrator_prompt(
    *,
    history_lines: list[str],
    current_intent: str,
    current_slots: dict[str, Any],
    user_message: str,
    unknown_step: int,
    last_results: dict[str, Any] | None = None,
) -> str:
    return (
        "You are an orchestrator for a social agent.\n"
        "Your job is to understand the user's intent and extract slots.\n"
        "Return ONLY valid JSON (no markdown) with keys: intent, phase, slots, assistantMessage.\n"
        "intent must be one of: unknown, find_people, find_things.\n"
        "phase must be one of: discover, collect, search, answer.\n"
        "\n"
        "find_people slots schema:\n"
        "- location: string\n"
        "- genders: array of strings from [female, male, any]\n"
        "- ageRange: {min:int, max:int}\n"
        "- occupation: string (required; user can say '不限')\n"
        "\n"
        "find_things slots schema:\n"
        "- title: string\n"
        "- neededCount: int\n"
        "\n"
        "Rules:\n"
        "- assistantMessage must be in Chinese.\n"
        "- If intent is unknown, respond like a companion: empathize + one gentle clarifying question.\n"
        "- If intent is find_people/find_things and info is missing, ask at most ONE question and match the active card.\n"
        "- IMPORTANT: Do NOT invent slot values the user did not provide. If user didn't specify a slot, leave it missing.\n"
        "- If the user asks about someone/something in the last results, set phase=answer and answer using ONLY that data.\n"
        "- When phase=answer, do NOT restart collection/search.\n"
        "- Do NOT invent overly specific personal data.\n"
        "\n"
        f"unknown_step: {unknown_step}\n"
        f"Current intent: {current_intent}\n"
        f"Current slots: {json.dumps(current_slots, ensure_ascii=False)}\n"
        f"Last results (may be empty): {json.dumps(last_results or {}, ensure_ascii=False)}\n"
        "\n"
        "Conversation (latest last):\n"
        + "\n".join(history_lines[-12:])
        + "\n\n"
        f"New user message: {user_message}\n"
    )


def build_planner_prompt(
    *,
    tool_schemas: list[dict[str, Any]],
    summary: str,
    history_lines: list[str],
    current_intent: str,
    current_slots: dict[str, Any],
    user_message: str,
    last_results: dict[str, Any] | None = None,
    focus: dict[str, Any] | None = None,
    result_labels: list[str] | None = None,
) -> str:
    """
    Planner decides ONE next step:
    - chat: just talk/answer (including answering based on last_results)
    - collect: ask at most ONE question; optionally propose UI blocks
    - tool: choose a toolName and toolArgs matching input schema
    """
    return (
        "You are a planner for an agentic social app.\n"
        "You receive memory + conversation + tool schemas. Decide the single best next action.\n"
        "Return ONLY valid JSON (no markdown) with keys:\n"
        "- decision: one of [chat, collect, tool]\n"
        "- assistantMessage: Chinese text to show the user\n"
        "- intent: one of [unknown, find_people, find_things]\n"
        "- slots: object (only values the user provided or explicitly confirmed)\n"
        "- toolName/toolArgs (only when decision=tool)\n"
        "- uiBlocks: optional array of blocks: {type: string, ...}\n"
        "- phase: optional string from [discover, collect, search, answer]\n"
        "\n"
        "Rules:\n"
        "- assistantMessage must be in Chinese.\n"
        "- Decide exactly ONE step per response.\n"
        "- Do NOT invent slot values the user did not provide.\n"
        "- This app only supports two tools: find_people and find_things. If the user asks for unrelated tasks (e.g. navigation, translation, coding help), set decision=chat and respond politely; do NOT pick a tool.\n"
        "- If user asks about the last shown results: you may use last_results as the ONLY source of FACTS about those people/groups.\n"
        "  You MAY add general advice (non-factual), and you MAY ask ONE clarifying question if needed.\n"
        "- Only treat the message as 'about last results' when the user clearly refers to a result (name/ordinal/pronoun/focus). Otherwise, ignore last_results.\n"
        "- If the user already provided the information you would ask for (e.g. skill level: 新手/中等/高手), do NOT ask it again; use it.\n"
        "- If information is missing for a tool call, set decision=collect and ask at most ONE question.\n"
        "- If decision=tool: toolName must be one of the provided tools; toolArgs must match the input schema.\n"
        "- uiBlocks (optional): Use small, safe JSON. Do not include HTML/JS.\n"
        "\n"
        "When intent is unclear / no tool should be used (Social Connector mode):\n"
        "- Set decision=chat, intent=unknown, slots={}.\n"
        "- phase should be discover.\n"
        "- Role: 你是一个温暖、敏锐且幽默的社交助手（Social Connector）。核心任务是陪伴用户聊天，提供情绪价值，并在恰当的时机，自然引导用户去探索现实生活中的社交连接（找人或找活动）。\n"
        "- Context: 用户的输入没有明确触发“找人 (find_people)”或“找活动 (find_things)”的功能指令，可能只是闲聊/抱怨/表达模糊情绪。\n"
        "- Objectives: (1) 先情感共鸣；(2) 再用软性引导把话题拉向“与人连接”；(3) 时机成熟再用假设性/建议性的口吻询问是否想看看附近有趣的人或局。\n"
        "- Guidelines: 口语化像朋友，不要像客服；这是长线对话，不强推功能；用“Yes, and…”先肯定再拓展到社交场景。\n"
        "\n"
        f"Tools JSON: {json.dumps(tool_schemas, ensure_ascii=False)}\n"
        f"Memory summary: {summary}\n"
        f"Current intent: {current_intent}\n"
        f"Current slots: {json.dumps(current_slots, ensure_ascii=False)}\n"
        f"Result labels (may be empty): {json.dumps(result_labels or [], ensure_ascii=False)}\n"
        f"Focus (may be null): {json.dumps(focus or None, ensure_ascii=False)}\n"
        f"Last results (may be empty): {json.dumps(last_results or {}, ensure_ascii=False)}\n"
        "\n"
        "Conversation (latest last):\n"
        + "\n".join(history_lines[-12:])
        + "\n\n"
        f"New user message: {user_message}\n"
    )


def build_summary_prompt(*, previous_summary: str, recent_turns: list[str], last_results: dict[str, Any] | None) -> str:
    return (
        "You summarize a user session for an agent.\n"
        "Return ONLY valid JSON: {\"summary\": \"...\"}\n"
        "\n"
        "Rules:\n"
        "- Write in Chinese.\n"
        "- Keep it concise (<= 1200 Chinese characters).\n"
        "- Preserve stable user preferences, constraints, and current goals.\n"
        "- Include what has already been shown in last_results at a high level (names/titles + a few tags only).\n"
        "- Do NOT copy-paste long bios/descriptions from last_results.\n"
        "- Do NOT include personal sensitive details.\n"
        "\n"
        f"Previous summary: {previous_summary}\n"
        f"Last results (may be empty): {json.dumps(last_results or {}, ensure_ascii=False)}\n"
        "Recent turns:\n"
        + "\n".join(recent_turns[-16:])
        + "\n"
    )


def build_people_generation_prompt(*, criteria: dict[str, Any]) -> str:
    return (
        "You generate imaginary but plausible 'people' results for a social app.\n"
        "Return ONLY valid JSON (no markdown) matching:\n"
        "{\n"
        '  "people": [Profile, ...],\n'
        '  "assistantMessage": "optional short Chinese summary"\n'
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
        "\n"
        "Requirements:\n"
        "- Generate exactly 5 people.\n"
        "- Keep it safe and respectful.\n"
        "- Use the user's constraints.\n"
        "\n"
        f"User criteria JSON: {json.dumps(criteria, ensure_ascii=False)}\n"
    )


def build_things_generation_prompt(*, criteria: dict[str, Any]) -> str:
    return (
        "You generate imaginary but plausible 'things/activities/groups' results for a social app.\n"
        "Return ONLY valid JSON (no markdown) matching:\n"
        "{\n"
        '  "things": [Group, ...],\n'
        '  "assistantMessage": "optional short Chinese summary"\n'
        "}\n"
        "\n"
        "Group schema:\n"
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
        "- member.badges: array of {id,label,description} (0-2 items)\n"
        "- notes: array of strings\n"
        "\n"
        "Requirements:\n"
        "- Generate exactly 5 groups.\n"
        "- Respect neededCount: ensure there are >= neededCount open spots for at least 2 groups.\n"
        "- Keep it safe and realistic.\n"
        "\n"
        f"User criteria JSON: {json.dumps(criteria, ensure_ascii=False)}\n"
    )
