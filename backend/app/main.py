from __future__ import annotations

import json
import logging
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import load_settings
from .llm import call_openai_compatible_json
from .logic import build_deck, companion_reply, generate_people, generate_things, orchestrate
from .models import (
    FindPeopleRequest,
    FindPeopleResponse,
    FindThingsRequest,
    FindThingsResponse,
    OrchestrateRequest,
    OrchestrateResponse,
    OrchestratorState,
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


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/find-people", response_model=FindPeopleResponse)
def find_people(body: FindPeopleRequest) -> FindPeopleResponse:
    request_id = str(uuid.uuid4())
    return generate_people(body, request_id=request_id, generated_by="mock")


@app.post("/api/v1/find-things", response_model=FindThingsResponse)
def find_things(body: FindThingsRequest) -> FindThingsResponse:
    request_id = str(uuid.uuid4())
    return generate_things(body, request_id=request_id, generated_by="mock")


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

    assistant_message: str

    has_llm = bool(settings.enable_real_llm and (settings.xai_api_key or settings.openai_api_key))
    if has_llm and body.message:
        provider = "xai" if settings.xai_api_key else "openai"
        if provider == "xai":
            base_url = settings.xai_base_url
            api_key = settings.xai_api_key or ""
            model = settings.default_ai_model or "grok-4-1-fast-non-reasoning"
        else:
            base_url = settings.openai_base_url
            api_key = settings.openai_api_key or ""
            model = settings.default_ai_model or "gpt-4o-mini"

        history = session.history[-12:]
        history_lines = "\n".join([f"{t.role}: {t.text}" for t in history])
        current_slots = session.state.slots
        current_intent = session.state.intent or "unknown"

        system = (
            "You are an orchestrator for a social agent prototype.\n"
            "Goal: understand intent and extract slots.\n"
            "Return ONLY valid JSON with keys: intent, slots, assistantMessage.\n"
            "intent must be one of: unknown, find_people, find_things.\n"
            "find_people slots schema:\n"
            "- location: string\n"
            "- genders: array of strings from [female, male, any]\n"
            "- ageRange: {min:int, max:int}\n"
            "- occupation: string (optional)\n"
            "find_things slots schema:\n"
            "- title: string\n"
            "- neededCount: int\n"
            "assistantMessage must be in Chinese, empathic, and ask at most ONE question if info is missing.\n"
            "If intent is unknown, respond like a companion: empathize + ask a gentle clarifying question.\n"
        )
        user = (
            f"Conversation (latest last):\n{history_lines}\n\n"
            f"Current intent: {current_intent}\n"
            f"Current slots: {json.dumps(current_slots, ensure_ascii=False)}\n\n"
            f"New user message: {body.message}\n"
        )
        try:
            llm = call_openai_compatible_json(
                base_url=base_url,
                api_key=api_key,
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            session.state = OrchestratorState(
                intent=llm.intent,
                slots=merge_slots(session.state.slots, llm.slots),
            )
            assistant_message = llm.assistantMessage
            store.touch(session)
        except Exception as e:
            logger.warning("[orchestrate] llm_failed=%s; falling back to heuristics", str(e))
            routing = orchestrate(message=body.message, state=session.state, form_data=incoming_form)
            session.state = OrchestratorState(intent=routing.intent, slots=routing.slots)
            assistant_message = routing.assistant_message
    else:
        routing = orchestrate(message=body.message, state=session.state, form_data=incoming_form)
        session.state = OrchestratorState(intent=routing.intent, slots=routing.slots)
        assistant_message = routing.assistant_message

    if session.state.intent == "unknown":
        step = int(session.meta.get("unknown_step", 0) or 0)
        if not has_llm:
            assistant_message = companion_reply(body.message, step=step)
        session.meta["unknown_step"] = step + 1
    else:
        session.meta.pop("unknown_step", None)

    deck, missing = build_deck(session.state.intent or "unknown", session.state.slots)

    if session.state.intent == "find_people" and not missing:
        req = FindPeopleRequest(**session.state.slots)
        res = generate_people(req, request_id=request_id, generated_by="mock")
        store.append(session, "assistant", assistant_message)
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent="find_people",
            action="results",
            assistantMessage=assistant_message,
            missingFields=[],
            deck=None,
            form=None,
            results={"people": res.people, "meta": res.meta},
            state=session.state,
        )

    if session.state.intent == "find_things" and not missing:
        req = FindThingsRequest(**session.state.slots)
        res = generate_things(req, request_id=request_id, generated_by="mock")
        store.append(session, "assistant", assistant_message)
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent="find_things",
            action="results",
            assistantMessage=assistant_message,
            missingFields=[],
            deck=None,
            form=None,
            results={"things": res.things, "meta": res.meta},
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
