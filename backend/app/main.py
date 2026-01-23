from __future__ import annotations

import json
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
    LLMOrchestration,
    build_orchestrator_prompt,
    build_people_generation_prompt,
    build_things_generation_prompt,
    call_gemini_json,
    llm_config_status,
)
from .logic import build_deck
from .models import (
    FindPeopleRequest,
    FindPeopleResponse,
    FindThingsRequest,
    FindThingsResponse,
    Group,
    Meta,
    OrchestrateRequest,
    OrchestrateResponse,
    OrchestratorState,
    Profile,
)
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
    def merge_slots(base: dict, incoming: dict) -> dict:
        merged = dict(base or {})
        for k, v in (incoming or {}).items():
            if v is None:
                continue
            merged[k] = v
        return merged

    request_id = str(uuid.uuid4())
    store.cleanup()

    session = store.get(body.sessionId or "") if body.sessionId else None
    if session is None:
        session = store.create()
    if body.reset:
        store.reset(session)

    if body.message:
        store.append(session, "user", body.message)

    incoming_form = body.submit.data if body.submit else {}
    if incoming_form:
        session.state = OrchestratorState(
            intent=session.state.intent,
            slots=merge_slots(session.state.slots, incoming_form),
        )
        store.touch(session)

    assistant_message = ""

    # IMPORTANT: while user is filling cards (submit-only), do NOT re-run the orchestrator LLM.
    # Otherwise the model may ask extra questions in text and break the 1-card-at-a-time UX.
    if body.message:
        unknown_step = int(session.meta.get("unknown_step", 0) or 0)
        history_lines = [f"{t.role}: {t.text}" for t in session.history[-12:]]
        current_slots = session.state.slots
        current_intent = session.state.intent or "unknown"

        try:
            llm = call_gemini_json(
                prompt=build_orchestrator_prompt(
                    history_lines=history_lines,
                    current_intent=current_intent,
                    current_slots=current_slots,
                    user_message=body.message,
                    unknown_step=unknown_step,
                ),
                response_model=LLMOrchestration,
            )
        except Exception as e:
            logger.exception("[orchestrate] gemini_failed request_id=%s session_id=%s", request_id, session.id)
            raise HTTPException(status_code=503, detail=f"Gemini call failed: {e}") from e

        session.state = OrchestratorState(
            intent=llm.intent,
            slots=merge_slots(session.state.slots, llm.slots),
        )
        assistant_message = llm.assistantMessage
        store.touch(session)

        if session.state.intent == "unknown":
            session.meta["unknown_step"] = unknown_step + 1
        else:
            session.meta.pop("unknown_step", None)
    else:
        # No message: stay in current intent; respond based on deck/results only.
        if session.state.intent == "find_people":
            assistant_message = "继续补全下一张卡片。"
        elif session.state.intent == "find_things":
            assistant_message = "继续补全下一张卡片。"
        else:
            assistant_message = "你可以先说一句你的需求，我来帮你把它拆成一张张卡。"

    deck, missing = build_deck(session.state.intent or "unknown", session.state.slots)

    if session.state.intent == "find_people" and not missing:
        req = FindPeopleRequest(**session.state.slots)
        try:
            llm_res = call_gemini_json(
                prompt=build_people_generation_prompt(criteria=req.model_dump()),
                response_model=LLMPeople,
            )
            people = [Profile.model_validate(p) for p in llm_res.people]
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Gemini call failed: {e}") from e

        final_message = (llm_res.assistantMessage or "").strip() or "好，我按你的条件生成了一批候选人。"
        store.append(session, "assistant", final_message)
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent="find_people",
            action="results",
            assistantMessage=final_message,
            missingFields=[],
            deck=None,
            form=None,
            results={"people": people, "meta": Meta(requestId=request_id, generatedBy="llm", model=GEMINI_MODEL)},
            state=session.state,
        )

    if session.state.intent == "find_things" and not missing:
        req = FindThingsRequest(**session.state.slots)
        try:
            llm_res = call_gemini_json(
                prompt=build_things_generation_prompt(criteria=req.model_dump()),
                response_model=LLMThings,
            )
            things = [Group.model_validate(g) for g in llm_res.things]
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Gemini call failed: {e}") from e

        final_message = (llm_res.assistantMessage or "").strip() or "好，我给你生成了一些可加入/可发起的活动建议。"
        store.append(session, "assistant", final_message)
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent="find_things",
            action="results",
            assistantMessage=final_message,
            missingFields=[],
            deck=None,
            form=None,
            results={"things": things, "meta": Meta(requestId=request_id, generatedBy="llm", model=GEMINI_MODEL)},
            state=session.state,
        )

    if deck is not None and missing:
        store.append(session, "assistant", assistant_message)
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent=session.state.intent or "unknown",
            action="form",
            assistantMessage=assistant_message,
            missingFields=missing,
            deck=deck,
            form=None,
            results=None,
            state=session.state,
        )

    store.append(session, "assistant", assistant_message)
    return OrchestrateResponse(
        requestId=request_id,
        sessionId=session.id,
        intent="unknown",
        action="chat",
        assistantMessage=assistant_message,
        missingFields=[],
        deck=None,
        form=None,
        results=None,
        state=session.state,
    )


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
    # Let FastAPI handle API routes
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")

    # Serve static file if it exists under dist
    candidate = _safe_dist_path(full_path)
    if candidate and os.path.isfile(candidate):
        return FileResponse(candidate)

    # Otherwise serve SPA index.html
    index_path = _safe_dist_path("index.html")
    if index_path and os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend dist not found")
