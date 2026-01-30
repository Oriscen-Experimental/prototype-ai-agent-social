from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Literal, TypeVar

import json5
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"

# Planner model options for UI selection
PLANNER_MODELS = {
    "light": "gemini-2.5-flash-lite",
    "medium": "gemini-2.5-flash",
    "heavy": "gemini-2.5-pro",
}


def resolve_planner_model(key: str | None) -> str:
    """Resolve planner model key to actual model ID."""
    if not key:
        return GEMINI_MODEL
    return PLANNER_MODELS.get(key, GEMINI_MODEL)


# New simplified decision types
PlannerDecisionType = Literal[
    "USE_TOOLS",           # Call a tool, results shown directly to user
    "CONTEXT_SUFFICIENT",  # Understood intent, history has enough info, no tool needed
    "SHOULD_NOT_ANSWER",   # Safety issue, refuse to answer
    "DO_NOT_KNOW_HOW",     # Understood but cannot handle
    "SOCIAL_GUIDANCE",     # Listen, empathize, guide toward social action
    "CHITCHAT",            # Pure small talk, no guidance intent
    "MISSING_INFO",        # Want to call tool but missing required params
]


class MissingParamOption(BaseModel):
    """An option for a MissingParam question."""
    label: str
    value: Any
    followUp: list["MissingParam"] | None = None  # Nested questions if this option is selected


class MissingParam(BaseModel):
    """A parameter that needs to be collected from user.

    Supports tree-structured conditional questions via followUp on options.
    """
    param: str  # Parameter name in tool schema
    question: str  # Question to ask user
    options: list[MissingParamOption] = Field(default_factory=list)


# Enable forward references for nested structure
MissingParam.model_rebuild()


class PlannerDecision(BaseModel):
    """Planner output with UI blocks."""
    decision: PlannerDecisionType
    # AI-specified UI blocks (text, profiles, groups, form)
    blocks: list[dict[str, Any]] | None = None
    # For USE_TOOLS and MISSING_INFO
    toolName: str | None = None
    toolArgs: dict[str, Any] | None = None
    # Deprecated: use blocks with type="text" instead
    message: str | None = None
    # Deprecated: use blocks with type="form" instead
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


def call_gemini_json(*, prompt: str, response_model: type[T], model: str | None = None) -> T:
    client = _get_gemini_client()
    effective_model = model or GEMINI_MODEL
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
                response = client.models.generate_content(model=effective_model, contents=effective_prompt)
            else:
                response = client.models.generate_content(model=effective_model, contents=effective_prompt, config=config)
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
    """Build planner prompt with UI blocks support."""
    return (
        "### Role\n"
        "You are the Planner for a Social & Event Connection Agent.\n"
        "Your job: analyze user messages, decide the best action, and compose the UI response.\n"
        "\n"
        "### Input\n"
        "- Conversation history: JSON array of {role, text, results?}\n"
        "- 'results' field shows what user can see (search results with id/name/city etc)\n"
        "- Use most recent 'results' to resolve references like 'the second one', 'that guy'\n"
        "\n"
        "### UI Blocks\n"
        "You control what the user sees. Return a 'blocks' array to compose the UI response.\n"
        "\n"
        "**Available block types:**\n"
        '- text: {"type": "text", "text": "Your message"}\n'
        '- profiles: {"type": "profiles", "ids": ["id1", "id2"], "layout": "compact"}\n'
        '- groups: {"type": "groups", "ids": ["id1"], "layout": "compact"}\n'
        '- form: {"type": "form", "questions": [{"param": "paramName", "question": "Question text to show user?", "options": [{"label": "Option", "value": "val"}]}]} (question field is REQUIRED)\n'
        "\n"
        "**Principles:**\n"
        "1. Show, don't just tell - if your answer references a specific person/event, include their card\n"
        "2. Don't show cards redundantly - if info was just displayed, a text summary is enough\n"
        "3. Combine blocks freely - text + cards, multiple cards, text + form, etc.\n"
        "4. Match user intent - 'which one?' wants to see the card; 'how many?' just wants a number\n"
        "5. For USE_TOOLS: no blocks needed, tool execution generates the UI automatically\n"
        "\n"
        "**ID Resolution:**\n"
        "- profiles/groups blocks use 'ids' to reference results from history\n"
        "- Use exact id values from the results in conversation history\n"
        "- Backend resolves ids to full objects before sending to frontend\n"
        "\n"
        "### Decision Priority (FOLLOW THIS ORDER)\n"
        "\n"
        "Evaluate decisions in this exact order. Stop at the first match.\n"
        "\n"
        "**Step 1: Safety Check**\n"
        "→ SHOULD_NOT_ANSWER if request involves harassment, illegal, minors, NSFW, doxxing.\n"
        "Output: {decision, blocks, thought}\n"
        "\n"
        "**Step 2: Can you answer from visible history?**\n"
        "Check the 'results' field in recent history. If the answer is already there:\n"
        "→ CONTEXT_SUFFICIENT - Answer using the data in history.\n"
        "This includes: filtering visible results, answering questions about displayed items,\n"
        "counting items, comparing items already shown, questions about event members, etc.\n"
        "Output: {decision, blocks, thought}\n"
        "\n"
        "**Step 3: Is this social/emotional or small talk?**\n"
        "→ SOCIAL_GUIDANCE if user expresses emotions, loneliness, or needs encouragement.\n"
        "→ CHITCHAT if pure small talk (greetings, weather, casual remarks).\n"
        "Output: {decision, blocks, thought}\n"
        "\n"
        "**Step 4: Does user need NEW data from a tool?**\n"
        "Only reach here if CONTEXT_SUFFICIENT does not apply.\n"
        "→ USE_TOOLS if user wants NEW search/discovery AND all required params available.\n"
        "Output: {decision, toolName, toolArgs, thought} - NO blocks needed, tool generates UI.\n"
        "→ MISSING_INFO if you want to call a tool BUT required params are missing.\n"
        "Output: {decision, toolName, toolArgs, blocks, thought}\n"
        "Include a form block to collect missing parameters.\n"
        "\n"
        "**Step 5: Fallback**\n"
        "→ DO_NOT_KNOW_HOW if understood but cannot help (no suitable tool, out of scope).\n"
        "Output: {decision, blocks, thought}\n"
        "\n"
        "### Examples\n"
        "\n"
        'User: "help me find people to play tennis with in Shanghai"\n'
        "→ USE_TOOLS with intelligent_discovery (no blocks)\n"
        "\n"
        'User: "which one did you mean?" (after showing results)\n'
        "→ CONTEXT_SUFFICIENT with blocks: [text explaining + groups/profiles card]\n"
        "\n"
        'User: "how many people are in this event?" (event card visible)\n'
        "→ CONTEXT_SUFFICIENT with blocks: [text with the number only]\n"
        "\n"
        'User: "which members are male?" (event with members visible)\n'
        "→ CONTEXT_SUFFICIENT with blocks: [text listing relevant members from visible data]\n"
        "\n"
        'User: "tell me more about him" (profile visible)\n'
        "→ CONTEXT_SUFFICIENT with blocks: [detailed text + profile card]\n"
        "\n"
        'User: "I want to meet new people"\n'
        "→ MISSING_INFO with blocks: [text greeting + form asking location]\n"
        "\n"
        "### Tool Parameter Rules\n"
        "- intelligent_discovery: REQUIRED domain, location\n"
        "- deep_profile_analysis: REQUIRED target_ids, analysis_mode; OPTIONAL focus_aspects\n"
        "- results_refine: REQUIRED domain, instruction, candidates\n"
        "\n"
        "### Output Rules\n"
        "- Return ONLY a single JSON object, no markdown\n"
        "- All text content must be in English\n"
        "- Use exact id values from results, never generate IDs\n"
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
