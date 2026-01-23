from __future__ import annotations

import json
import logging
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

Intent = Literal["unknown", "find_people", "find_things"]


class LLMOrchestration(BaseModel):
    intent: Intent
    slots: dict[str, Any] = Field(default_factory=dict)
    assistantMessage: str = Field(min_length=1)


def _extract_first_json_object(text: str) -> dict[str, Any]:
    s = (text or "").strip()
    if not s:
        raise ValueError("empty response")
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no json object found")
    snippet = s[start : end + 1]
    return json.loads(snippet)


def call_openai_compatible_json(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    timeout_seconds: float = 25.0,
) -> LLMOrchestration:
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"model": model, "messages": messages, "temperature": 0.4}

    with httpx.Client(timeout=timeout_seconds) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("llm response missing choices")
    msg = (choices[0].get("message") or {}).get("content") or ""
    obj = _extract_first_json_object(msg)
    try:
        return LLMOrchestration.model_validate(obj)
    except ValidationError as e:
        raise RuntimeError(f"llm json validation failed: {e}") from e

