from __future__ import annotations

import os
from dataclasses import dataclass


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    allowed_origins: list[str]
    enable_real_llm: bool
    log_level: str

    default_ai_model: str | None
    xai_api_key: str | None
    xai_base_url: str
    openai_api_key: str | None
    openai_base_url: str


def load_settings() -> Settings:
    raw_origins = os.getenv("ALLOWED_ORIGINS", "*").strip()
    if raw_origins == "*":
        allowed_origins = ["*"]
    else:
        allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    return Settings(
        allowed_origins=allowed_origins,
        enable_real_llm=_truthy(os.getenv("ENABLE_REAL_LLM")),
        log_level=(os.getenv("LOG_LEVEL", "info") or "info").strip().lower(),
        default_ai_model=(os.getenv("DEFAULT_AI_MODEL") or "").strip() or None,
        xai_api_key=(os.getenv("XAI_API_KEY") or "").strip() or None,
        xai_base_url=(os.getenv("XAI_BASE_URL") or "https://api.x.ai/v1").rstrip("/"),
        openai_api_key=(os.getenv("OPENAI_API_KEY") or "").strip() or None,
        openai_base_url=(os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
    )

