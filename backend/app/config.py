from __future__ import annotations

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    allowed_origins: list[str]
    log_level: str


def load_settings() -> Settings:
    raw_origins = os.getenv("ALLOWED_ORIGINS", "*").strip()
    if raw_origins == "*":
        allowed_origins = ["*"]
    else:
        allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    return Settings(
        allowed_origins=allowed_origins,
        log_level=(os.getenv("LOG_LEVEL", "info") or "info").strip().lower(),
    )
