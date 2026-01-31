from __future__ import annotations

import logging
import os
import uuid
import io
import zipfile

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi import Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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
    RoleplayChatRequest,
    RoleplayChatResponse,
    SortingLabelsRequest,
    SortingLabelsResponse,
)
from .orchestrator import handle_orchestrate
from .roleplay import roleplay_chat
from .sorting_labels import generate_sorting_labels
from .store import SessionStore
from .event_store import EventStore, StoredEvent


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
ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD", "jacksoncui@oriscen.ai") or "jacksoncui@oriscen.ai").strip()

app = FastAPI(title="agent-social prototype backend", version="0.1.0")
store = SessionStore(ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "21600") or "21600"))
event_store = EventStore(events_dir=os.getenv("EVENTS_DIR", "/tmp/agent-social-events") or "/tmp/agent-social-events")

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
def orchestrator(
    body: OrchestrateRequest,
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
) -> OrchestrateResponse:
    client_id = (x_client_id or "").strip() or None
    return handle_orchestrate(store=store, body=body, client_id=client_id)


@app.post("/api/v1/chat", response_model=RoleplayChatResponse)
def chat(body: RoleplayChatRequest) -> RoleplayChatResponse:
    """Roleplay chat endpoint - AI performs method acting as the character."""
    try:
        # Convert profile and messages to dict format for roleplay_chat
        profile_dict = body.profile.model_dump()
        messages_list = [{"role": m.role, "content": m.content} for m in body.messages]

        reply = roleplay_chat(profile=profile_dict, messages=messages_list)
        return RoleplayChatResponse(reply=reply)
    except Exception as e:
        logger.exception("[chat] roleplay_chat failed")
        raise HTTPException(status_code=503, detail=f"Chat failed: {e}") from e


@app.post("/api/v1/sorting/labels", response_model=SortingLabelsResponse)
def sorting_labels(body: SortingLabelsRequest) -> SortingLabelsResponse:
    try:
        return generate_sorting_labels(name=(body.name or "").strip() or None, answers=body.answers)
    except Exception as e:
        logger.exception("[sorting_labels] failed")
        raise HTTPException(status_code=500, detail=f"Failed to generate labels: {e}") from e


class ClientEvent(BaseModel):
    type: str = Field(min_length=1)
    at_ms: int = Field(ge=0)
    sessionId: str | None = None
    page: str | None = None
    payload: dict[str, object] | None = None


class EventsIngestRequest(BaseModel):
    events: list[ClientEvent] = Field(default_factory=list, max_length=50)

def _require_admin(x_admin_password: str | None) -> None:
    if (x_admin_password or "") != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/api/v1/events")
def ingest_events(
    body: EventsIngestRequest,
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
    user_agent: str | None = Header(default=None, alias="User-Agent"),
) -> dict[str, object]:
    client_id = (x_client_id or "").strip()
    if not client_id:
        raise HTTPException(status_code=400, detail="Missing X-Client-Id header.")

    events: list[StoredEvent] = []
    for e in body.events:
        events.append(
            StoredEvent(
                client_id=client_id,
                at_ms=e.at_ms,
                type=e.type,
                session_id=e.sessionId,
                page=e.page,
                payload=e.payload,
                user_agent=(user_agent or "").strip() or None,
            )
        )
    event_store.append_many(client_id, events)

    return {"status": "ok", "received": len(events)}


@app.get("/api/v1/events/me")
def export_my_events(
    limit: int = 5000,
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
) -> dict[str, object]:
    client_id = (x_client_id or "").strip()
    if not client_id:
        raise HTTPException(status_code=400, detail="Missing X-Client-Id header.")
    limit = max(1, min(5000, int(limit)))
    events = event_store.load_all(client_id, limit=limit)
    return {"clientId": client_id, "events": events}


@app.get("/api/v1/admin/clients")
def admin_clients(
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
    limit: int = 2000,
) -> dict[str, object]:
    _require_admin(x_admin_password)
    limit = max(1, min(2000, int(limit)))
    return {"clients": event_store.list_clients(limit=limit)}


@app.get("/api/v1/admin/events/{client_id}")
def admin_events(
    client_id: str,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
    limit: int = 5000,
) -> dict[str, object]:
    _require_admin(x_admin_password)
    limit = max(1, min(5000, int(limit)))
    events = event_store.load_all(client_id, limit=limit)
    return {"clientId": client_id, "events": events}


@app.get("/api/v1/admin/download/all.zip")
def admin_download_all(
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
    limit_clients: int = 2000,
) -> StreamingResponse:
    _require_admin(x_admin_password)
    clients = event_store.list_clients(limit=max(1, min(2000, int(limit_clients))))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for c in clients:
            cid = (c.get("clientId") or "").strip()
            if not cid:
                continue
            path = event_store.raw_path_for_client(cid)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "rb") as f:
                    z.writestr(f"{cid}.jsonl", f.read())
            except Exception:
                continue

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="agent-social-events.zip"'},
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
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")

    candidate = _safe_dist_path(full_path)
    if candidate and os.path.isfile(candidate):
        return FileResponse(candidate)

    index_path = _safe_dist_path("index.html")
    if index_path and os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend dist not found")
