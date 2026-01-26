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
PlannerDecisionType = Literal["chat", "need_more_info", "tool_call", "refuse", "cant_do"]


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
    code: str | None = None
    thought: str | None = None
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
    if start == -1:
        raise ValueError("no json object found")

    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]

    raise ValueError("unterminated json object")


def _loads_json_relaxed(text: str) -> dict[str, Any]:
    try:
        return json5.loads(text)
    except Exception:
        return json.loads(text)


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

    max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "3") or "3")
    max_retries = max(1, min(5, max_retries))

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        effective_prompt = prompt
        if attempt > 1:
            effective_prompt = (
                prompt
                + "\n\n"
                + "IMPORTANT: Your previous response was invalid. Return ONLY a single JSON object. "
                + "No extra text, no markdown, no explanations."
            )
        try:
            if config is None:
                response = client.models.generate_content(model=GEMINI_MODEL, contents=effective_prompt)
            else:
                response = client.models.generate_content(model=GEMINI_MODEL, contents=effective_prompt, config=config)
            text = getattr(response, "text", None) or ""
            snippet = _extract_first_json_object(text)
            obj = _loads_json_relaxed(snippet)
            return response_model.model_validate(obj)
        except Exception as e:
            last_err = e
            logger.info("[llm] json_call_failed attempt=%s/%s err=%s", attempt, max_retries, type(e).__name__)
            continue

    raise RuntimeError(f"gemini json failed after {max_retries} attempts: {last_err}") from last_err


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
        "- occupation: string (required; user can say 'any')\n"
        "\n"
        "find_things slots schema:\n"
        "- title: string\n"
        "- neededCount: int\n"
        "\n"
        "Rules:\n"
        "- assistantMessage must be in English.\n"
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
    session_id: str,
    summary: str,
    history: list[dict[str, Any]],
) -> str:
    return (
        "### Role Definition\n"
        "You are the Orchestrator (Planner) for a Social & Event Connection Agent. Your goal is to help users find people (social_connect) or activities (event_discovery) and facilitate connections between them.\n"
        "\n"
        "### Input Context\n"
        "You have access to Conversation History as a JSON array.\n"
        "Each turn is: {role: 'user'|'assistant'|'system', text: string, 'ui results'?: [ ... ]}.\n"
        "The optional 'ui results' is a compact snapshot of what the user could see on the UI at that moment (e.g. search results with index+id).\n"
        "Use the MOST RECENT 'ui results' to resolve references like 'the second one', 'New York guy', etc.\n"
        "\n"
        "### Decision Logic (State Machine)\n"
        "Analyze the user's latest input and map it to ONE of the 5 states.\n"
        "Return ONLY JSON with keys:\n"
        "- decision: one of [tool_call, refuse, cant_do, chat, need_more_info]\n"
        "- assistantMessage: English only\n"
        "- intent: one of [unknown, find_people, find_things] (for UI routing)\n"
        "- toolName/toolArgs: only when decision=tool_call\n"
        "- code: optional short code string\n"
        "- thought: optional brief explanation of which State you chose and how you resolved references\n"
        "- uiBlocks: optional safe JSON blocks (type=text|choices)\n"
        "- phase: optional [discover, collect, search, answer]\n"
        "\n"
        "#### State 1: Ready to Execute\n"
        "- Condition: intent is clear, supported by tools, and all CRITICAL parameters are present.\n"
        "- Action: decision=tool_call with toolName+toolArgs.\n"
        "Critical Parameter Rules:\n"
        "- intelligent_discovery:\n"
        "  - domain='event': MUST have structured_filters.location (city OR is_online=true) and event_filters.time_range.\n"
        "  - domain='person': MUST have structured_filters.location (city OR is_online=true). gender/age are OPTIONAL (defaults are fine unless dating-like intent).\n"
        "- deep_profile_analysis: MUST have valid non-empty target_ids resolved from Visible Context.\n"
        "- results_refine: MUST have domain + instruction. It refines visible results only (no new search).\n"
        "\n"
        "#### State 2: Policy Violation\n"
        "- Condition: user intent is clear but prohibited (harassment, illegal, minors, NSFW, doxxing).\n"
        "- Action: decision=refuse. Do NOT call tools.\n"
        "\n"
        "#### State 3: Capability Gap\n"
        "- Condition: intent is valid within social/event domain, but no tool can do it (e.g. book flights, write a full resume, etc.).\n"
        "- Action: decision=cant_do, explain limitation, offer relevant alternative.\n"
        "\n"
        "#### State 4: Chit-Chat / Ambiguous\n"
        "- Condition: greeting/small talk or no clear intent.\n"
        "- Action: decision=chat. Be companion-like and gently steer toward people/events.\n"
        "\n"
        "#### State 5: Missing Critical Information\n"
        "- Condition: intent is clear but CRITICAL parameters are missing.\n"
        "- Action: decision=need_more_info.\n"
        "- IMPORTANT UX: Do NOT ask natural-language questions. The UI will show a card deck to collect the missing fields.\n"
        "  So assistantMessage should be a short instruction like: 'Fill the next card.'\n"
        "- IMPORTANT: NEVER send empty target_ids. If you cannot resolve an ID from Visible Context, ask for clarification.\n"
        "\n"
        "### Reference Resolution Rules (Crucial)\n"
        "- Use Visible Context to map implicit references to a specific item id.\n"
        "- If user says 'the guy from New York', find a candidate with city='New York' in Visible Context; use their id.\n"
        "- If multiple match (ambiguous), use State 5 and ask which one (e.g. by name or by index).\n"
        "- If user asks to categorize/compare visible items (e.g. 'which are beginner/newbie?'), resolve target_ids from Visible Context and use deep_profile_analysis (analysis_mode=compare). Do NOT ask for new non-schema fields.\n"
        "- If user asks to filter/rerank/refine the visible list (e.g. 'filter to California', '只看新手', 'top 3'), use results_refine. Do NOT restart discovery.\n"
        "\n"
        "### Output Rule\n"
        "- Return ONLY a single JSON object. No extra text, no markdown.\n"
        "- assistantMessage must be English ONLY.\n"
        "\n"
        f"SessionId: {session_id}\n"
        f"Tools JSON: {json.dumps(tool_schemas, ensure_ascii=False)}\n"
        f"Memory summary: {summary}\n"
        f"Conversation JSON (latest last): {json.dumps(history[-16:], ensure_ascii=False)}\n"
    )


def build_summary_prompt(*, previous_summary: str, recent_turns: list[str], last_results: dict[str, Any] | None) -> str:
    return (
        "You summarize a user session for an agent.\n"
        "Return ONLY valid JSON: {\"summary\": \"...\"}\n"
        "\n"
        "Rules:\n"
        "- Write in English ONLY. Do not use Chinese.\n"
        "- Keep it concise (<= 1200 characters).\n"
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
        "\n"
        "Requirements:\n"
        "- Generate exactly 5 people.\n"
        "- Keep it safe and respectful.\n"
        "- Use the user's constraints.\n"
        "- All free-text fields must be in English ONLY. Do not use Chinese.\n"
        "\n"
        f"User criteria JSON: {json.dumps(criteria, ensure_ascii=False)}\n"
    )


def build_things_generation_prompt(*, criteria: dict[str, Any]) -> str:
    return (
        "You generate imaginary but plausible 'things/activities/groups' results for a social app.\n"
        "Return ONLY valid JSON (no markdown) matching:\n"
        "{\n"
        '  "things": [Group, ...],\n'
        '  "assistantMessage": "optional short English summary"\n'
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
        "- All free-text fields must be in English ONLY. Do not use Chinese.\n"
        "\n"
        f"User criteria JSON: {json.dumps(criteria, ensure_ascii=False)}\n"
    )
