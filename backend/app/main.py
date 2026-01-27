from __future__ import annotations

import logging
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import load_settings
from .llm import (
    GEMINI_MODEL,
    LLMPeople,
    LLMThings,
    build_people_generation_prompt,
    build_things_generation_prompt,
    call_gemini_json,
    llm_config_status,
)
from .models import (
    FindPeopleRequest,
    FindPeopleResponse,
    FindThingsRequest,
    FindThingsResponse,
    Group,
    Meta,
    OrchestrateRequest,
    OrchestrateResponse,
    Profile,
)
from .orchestrator import handle_orchestrate
from .store import SessionStore


def _setup_logging(level: str) -> None:
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    logging.basicConfig(
        level=level_map.get(level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


# Local dev: load `backend/.env` if present (Render ignores missing file)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

settings = load_settings()
_setup_logging(settings.log_level)
logger = logging.getLogger("agent-social-backend")

app = FastAPI(title="agent-social prototype backend", version="0.1.0")
store = SessionStore(ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "21600") or "21600"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DIST_DIR = os.getenv(
    "DIST_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "prototype-web", "dist"),
)
DIST_DIR = os.path.abspath(DIST_DIR)


def _safe_dist_path(rel_path: str) -> str | None:
    rel_path = (rel_path or "").lstrip("/")
    candidate = os.path.abspath(os.path.join(DIST_DIR, rel_path))
    if not candidate.startswith(DIST_DIR):
        return None
    return candidate


@app.get("/api/v1/health")
def health() -> dict[str, object]:
    return {"status": "ok", "llm": llm_config_status()}


@app.post("/api/v1/find-people", response_model=FindPeopleResponse)
def find_people(body: FindPeopleRequest) -> FindPeopleResponse:
    request_id = str(uuid.uuid4())
    try:
        llm = call_gemini_json(
            prompt=build_people_generation_prompt(criteria=body.model_dump()),
            response_model=LLMPeople,
        )
        people = [Profile.model_validate(p) for p in llm.people]
    except Exception as e:
        logger.exception("[find-people] gemini_failed request_id=%s", request_id)
        raise HTTPException(status_code=503, detail=f"Gemini call failed: {e}") from e

    return FindPeopleResponse(
        people=people,
        meta=Meta(requestId=request_id, generatedBy="llm", model=GEMINI_MODEL),
    )


@app.post("/api/v1/find-things", response_model=FindThingsResponse)
def find_things(body: FindThingsRequest) -> FindThingsResponse:
    request_id = str(uuid.uuid4())
    try:
        llm = call_gemini_json(
            prompt=build_things_generation_prompt(criteria=body.model_dump()),
            response_model=LLMThings,
        )
        things = [Group.model_validate(g) for g in llm.things]
    except Exception as e:
        logger.exception("[find-things] gemini_failed request_id=%s", request_id)
        raise HTTPException(status_code=503, detail=f"Gemini call failed: {e}") from e

    return FindThingsResponse(
        things=things,
        meta=Meta(requestId=request_id, generatedBy="llm", model=GEMINI_MODEL),
    )


@app.post("/api/v1/orchestrate", response_model=OrchestrateResponse)
def orchestrator(body: OrchestrateRequest) -> OrchestrateResponse:
    return handle_orchestrate(store=store, body=body)


@app.get("/")
def spa_root():
    index_path = _safe_dist_path("index.html")
    if index_path and os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse(
        {
            "status": "ok",
            "message": "Frontend dist not found. For local dev run Vite from prototype-web/, or deploy via Docker on Render.",
        }
    )


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")

    candidate = _safe_dist_path(full_path)
    if candidate and os.path.isfile(candidate):
        return FileResponse(candidate)

    index_path = _safe_dist_path("index.html")
    if index_path and os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend dist not found")
