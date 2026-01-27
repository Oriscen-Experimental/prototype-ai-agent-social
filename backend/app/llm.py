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

# New simplified decision types
PlannerDecisionType = Literal[
    "USE_TOOLS",          # Call a tool, results shown directly to user
    "SHOULD_NOT_ANSWER",  # Safety issue, refuse to answer
    "DO_NOT_KNOW_HOW",    # Understood but cannot handle
    "SOCIAL_GUIDANCE",    # Listen, empathize, guide toward social action
    "CHITCHAT",           # Pure small talk, no guidance intent
    "MISSING_INFO",       # Want to call tool but missing required params
]


class MissingParam(BaseModel):
    """A parameter that needs to be collected from user."""
    param: str  # Parameter name in tool schema
    question: str  # Question to ask user
    options: list[dict[str, Any]] = Field(default_factory=list)  # [{label: str, value: Any}]


class PlannerDecision(BaseModel):
    """New simplified planner output."""
    decision: PlannerDecisionType
    # For USE_TOOLS and MISSING_INFO
    toolName: str | None = None
    toolArgs: dict[str, Any] | None = None
    # For SHOULD_NOT_ANSWER, DO_NOT_KNOW_HOW, SOCIAL_GUIDANCE, CHITCHAT
    message: str | None = None
    # For MISSING_INFO only
    missingParams: list[MissingParam] | None = None
    # Always included for debugging
    thought: str | None = None


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
    # Cap retries to keep latency bounded (and align with planner expectations).
    max_retries = max(1, min(3, max_retries))

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


def build_planner_prompt(
    *,
    tool_schemas: list[dict[str, Any]],
    session_id: str,
    summary: str,
    history: list[dict[str, Any]],
) -> str:
    """Build planner prompt with 6 decision types."""
    return (
        "### Role\n"
        "You are the Planner for a Social & Event Connection Agent.\n"
        "Your job: analyze user messages and decide the best action.\n"
        "\n"
        "### Input\n"
        "- Conversation history: JSON array of {role, text, results?}\n"
        "- 'results' field shows what user can see (search results with id/name/city etc)\n"
        "- Use most recent 'results' to resolve references like 'the second one', 'that guy'\n"
        "\n"
        "### Decision Types (pick exactly ONE)\n"
        "\n"
        "#### A. USE_TOOLS\n"
        "When: User has a clear, actionable request AND all required parameters are available.\n"
        "Output:\n"
        "```json\n"
        '{"decision": "USE_TOOLS", "toolName": "...", "toolArgs": {...}, "thought": "..."}\n'
        "```\n"
        "IMPORTANT: Tool results will be shown directly to user. Only use when ready to execute.\n"
        "\n"
        "#### B. SHOULD_NOT_ANSWER\n"
        "When: Request involves safety issues (harassment, illegal, minors, NSFW, doxxing).\n"
        "Output:\n"
        "```json\n"
        '{"decision": "SHOULD_NOT_ANSWER", "message": "I cannot help with...", "thought": "..."}\n'
        "```\n"
        "\n"
        "#### C. DO_NOT_KNOW_HOW\n"
        "When: You understand what user wants but cannot do it (no suitable tool, out of scope).\n"
        "Examples: book flights, write resume, financial advice.\n"
        "Output:\n"
        "```json\n"
        '{"decision": "DO_NOT_KNOW_HOW", "message": "I understand you want X, but I cannot...", "thought": "..."}\n'
        "```\n"
        "\n"
        "#### D. SOCIAL_GUIDANCE\n"
        "When: User expresses emotions, loneliness, social struggles, or needs encouragement.\n"
        "Goal: Listen, empathize, and gently guide toward social actions.\n"
        "Output:\n"
        "```json\n"
        '{"decision": "SOCIAL_GUIDANCE", "message": "That sounds tough. Tell me more about...", "thought": "..."}\n'
        "```\n"
        "\n"
        "#### E. CHITCHAT\n"
        "When: Pure small talk with no clear intent (greetings, weather, casual remarks).\n"
        "Output:\n"
        "```json\n"
        '{"decision": "CHITCHAT", "message": "Nice weather indeed! ...", "thought": "..."}\n'
        "```\n"
        "\n"
        "#### F. MISSING_INFO\n"
        "When: You want to call a specific tool BUT required parameters are missing.\n"
        "IMPORTANT: You must generate the questions and options to collect missing info.\n"
        "The UI will show these questions directly; user's answers will trigger immediate tool execution.\n"
        "Output:\n"
        "```json\n"
        "{\n"
        '  "decision": "MISSING_INFO",\n'
        '  "toolName": "intelligent_discovery",\n'
        '  "toolArgs": {"domain": "person", "structured_filters": {"location": {"city": "Shanghai"}}},\n'
        '  "missingParams": [\n'
        "    {\n"
        '      "param": "structured_filters.person_filters.age_range",\n'
        '      "question": "What age range are you looking for?",\n'
        '      "options": [\n'
        '        {"label": "18-25", "value": {"min": 18, "max": 25}},\n'
        '        {"label": "25-35", "value": {"min": 25, "max": 35}},\n'
        '        {"label": "Any age", "value": null}\n'
        "      ]\n"
        "    }\n"
        "  ],\n"
        '  "thought": "User wants tennis partner in Shanghai but didn\'t specify age preference"\n'
        "}\n"
        "```\n"
        "\n"
        "### Decision Flow\n"
        "```\n"
        "User message\n"
        "  |\n"
        "  v\n"
        "Safety issue? --> SHOULD_NOT_ANSWER\n"
        "  | no\n"
        "  v\n"
        "Clear actionable request?\n"
        "  | yes --> Tool can handle it?\n"
        "  |           | yes --> All params ready? --> USE_TOOLS\n"
        "  |           |                    | no --> MISSING_INFO\n"
        "  |           | no --> DO_NOT_KNOW_HOW\n"
        "  | no\n"
        "  v\n"
        "Emotional/social struggle? --> SOCIAL_GUIDANCE\n"
        "  | no\n"
        "  v\n"
        "CHITCHAT\n"
        "```\n"
        "\n"
        "### Tool Parameter Rules\n"
        "- intelligent_discovery (find people/events):\n"
        "  - REQUIRED: domain ('person' or 'event')\n"
        "  - REQUIRED: structured_filters.location (city OR is_online=true)\n"
        "  - For events: event_filters.time_range is strongly recommended\n"
        "  - Other filters are optional\n"
        "- deep_profile_analysis (analyze visible results):\n"
        "  - REQUIRED: target_ids (resolved from visible 'results')\n"
        "  - REQUIRED: analysis_mode ('detail', 'compare', 'compatibility_check')\n"
        "- results_refine (filter/rerank visible results):\n"
        "  - REQUIRED: domain, instruction\n"
        "  - Does NOT do new search, only refines what's visible\n"
        "\n"
        "### Reference Resolution\n"
        "- 'the second one' -> use id from index 1 in most recent results\n"
        "- 'the guy from New York' -> find person with city='New York' in results\n"
        "- If ambiguous (multiple matches), use MISSING_INFO to ask which one\n"
        "\n"
        "### Output Rules\n"
        "- Return ONLY a single JSON object\n"
        "- No markdown, no extra text\n"
        "- message field must be in English\n"
        "\n"
        f"SessionId: {session_id}\n"
        f"Tools: {json.dumps(tool_schemas, ensure_ascii=False)}\n"
        f"Summary: {summary}\n"
        f"History: {json.dumps(history[-16:], ensure_ascii=False)}\n"
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
