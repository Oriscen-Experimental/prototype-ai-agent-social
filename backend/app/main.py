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
    GoogleAuthRequest,
    GoogleAuthResponse,
    Group,
    Meta,
    OrchestrateRequest,
    OrchestrateResponse,
    Profile,
    RoleplayChatRequest,
    RoleplayChatResponse,
    SaveProfileRequest,
    SaveProfileResponse,
    SortingLabelsRequest,
    SortingLabelsResponse,
)
from .auth import google_auth_config_status, verify_google_id_token
from .booking.task_store import BookingTaskStore
from .db import user_db
from .orchestrator import handle_orchestrate
from .roleplay import roleplay_chat
from .sorting_labels import generate_sorting_labels, generate_sorting_labels_stream
from .store import SessionStore
from .event_store import EventStore, StoredEvent
from .orchestrator.service import set_orchestrator_booking_store
from .tool_library.booking import set_booking_store
from .tool_library.cancel_booking import set_booking_store as set_cancel_booking_store


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
booking_store = BookingTaskStore()
set_booking_store(booking_store)
set_cancel_booking_store(booking_store)
set_orchestrator_booking_store(booking_store)

# Initialize user DB on startup
try:
    user_db.initialize()
    logger.info("User DB initialized with %d users", user_db.user_count)
except Exception as e:
    logger.warning("Failed to initialize user DB: %s (will retry on first use)", e)

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
    return {"status": "ok", "llm": llm_config_status(), "google_auth": google_auth_config_status()}


@app.post("/api/v1/auth/google", response_model=GoogleAuthResponse)
def auth_google(body: GoogleAuthRequest) -> GoogleAuthResponse:
    """Verify Google ID token, create/update user in DB, and return user info."""
    try:
        user_info = verify_google_id_token(body.idToken)

        # Save or update user in database
        db_user_id, needs_onboarding = user_db.create_or_update_user(
            google_uid=user_info["uid"],
            email=user_info.get("email") or "",
            display_name=user_info.get("displayName"),
            photo_url=user_info.get("photoURL"),
        )

        return GoogleAuthResponse(
            uid=db_user_id,  # Use database user ID instead of Google UID
            email=user_info.get("email"),
            displayName=user_info.get("displayName"),
            photoURL=user_info.get("photoURL"),
            needsOnboarding=needs_onboarding,
        )
    except ValueError as e:
        logger.warning("[auth] token verification failed: %s", e)
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        logger.exception("[auth] unexpected error during token verification")
        raise HTTPException(status_code=500, detail="Authentication failed") from e


@app.post("/api/v1/profile", response_model=SaveProfileResponse)
def save_profile(
    body: SaveProfileRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> SaveProfileResponse:
    """Save user onboarding profile data."""
    user_id = (x_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")

    success = user_db.save_user_profile(
        user_id=user_id,
        name=body.name,
        gender=body.gender,
        age=body.age,
        city=body.city,
        interests=body.interests,
        running_profile=body.runningProfile,
    )

    if success:
        return SaveProfileResponse(success=True, message="Profile saved")
    else:
        raise HTTPException(status_code=500, detail="Failed to save profile")


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


@app.post("/api/v1/sorting/labels/stream")
def sorting_labels_stream(body: SortingLabelsRequest) -> StreamingResponse:
    """Stream sorting labels as NDJSON events."""
    return StreamingResponse(
        generate_sorting_labels_stream(name=(body.name or "").strip() or None, answers=body.answers),
        media_type="application/x-ndjson",
    )


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


# ---------------------------------------------------------------------------
# Booking API endpoints
# ---------------------------------------------------------------------------


class BookingSpeedRequest(BaseModel):
    taskId: str
    multiplier: float = Field(ge=0.1, le=3600)


class InvitationRespondRequest(BaseModel):
    response: str = Field(pattern="^(accept|decline)$")


@app.get("/api/v1/booking/status/{task_id}")
def booking_status(task_id: str) -> dict[str, object]:
    """Get booking task status for frontend polling."""
    task = booking_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Booking task not found")

    invitations_summary = []
    for inv in task.invitations:
        invitations_summary.append({
            "id": inv.id,
            "userId": inv.user_id,
            "nickname": inv.user_info.get("nickname", ""),
            "status": inv.status,
            "batchIndex": inv.batch_index,
            "isMock": inv.user_info.get("is_mock", True),
        })

    return {
        "taskId": task.id,
        "status": task.status,
        "activity": task.activity,
        "location": task.location,
        "desiredTime": task.desired_time,
        "acceptedCount": len(task.accepted_users),
        "targetCount": task.headcount,
        "currentBatch": task.current_batch,
        "totalCandidates": len(task.candidates),
        "totalInvitations": len(task.invitations),
        "speedMultiplier": task.speed_multiplier,
        "invitations": invitations_summary,
        "acceptedUsers": [
            {
                "id": u.get("id", ""),
                "nickname": u.get("nickname", ""),
                "location": u.get("location", ""),
                "occupation": u.get("occupation", ""),
                "interests": u.get("interests", []),
                "matchScore": u.get("match_score", 0),
            }
            for u in task.accepted_users
        ],
        "bookedTime": task.booked_time,
        "bookedLocation": task.booked_location,
        "bookedIsoStart": task.booked_iso_start,
        "bookedIsoEnd": task.booked_iso_end,
    }


@app.post("/api/v1/booking/speed")
def booking_speed(body: BookingSpeedRequest) -> dict[str, object]:
    """Adjust speed multiplier for demo."""
    task = booking_store.get(body.taskId)
    if task is None:
        raise HTTPException(status_code=404, detail="Booking task not found")
    task.speed_multiplier = body.multiplier
    return {"ok": True, "multiplier": task.speed_multiplier}


@app.get("/api/v1/booking/notifications/{session_id}")
def booking_notifications(session_id: str) -> dict[str, object]:
    """Get and clear pending notifications for a session (booking + cancel flows)."""
    booking_notifs = booking_store.pop_notifications(session_id)
    cancel_notifs = booking_store.pop_cancel_notifications(session_id)
    return {"notifications": booking_notifs + cancel_notifs}


@app.get("/api/v1/invitations/pending")
def pending_invitations(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> dict[str, object]:
    """Return all pending invitations for the authenticated user."""
    user_id = (x_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    return {"invitations": booking_store.get_pending_invitations_for_user(user_id)}


@app.get("/api/v1/invitation/{invitation_id}")
def get_invitation(invitation_id: str) -> dict[str, object]:
    """Get invitation details for a real user to review."""
    inv = booking_store.get_invitation(invitation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invitation not found")

    task = booking_store.get_task_for_invitation(invitation_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Booking task not found")

    return {
        "invitationId": inv.id,
        "status": inv.status,
        "activity": task.activity,
        "location": task.location,
        "desiredTime": task.desired_time,
        "invitedBy": task.client_id,
        "sentAt": inv.sent_at,
    }


@app.post("/api/v1/invitation/{invitation_id}/respond")
def respond_to_invitation(invitation_id: str, body: InvitationRespondRequest) -> dict[str, object]:
    """Accept or decline an invitation (for real users)."""
    import time

    inv = booking_store.get_invitation(invitation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invitation not found")

    if inv.status != "pending":
        return {"ok": False, "expired": True, "status": inv.status}

    if body.response == "accept":
        inv.status = "accepted"
        inv.responded_at = time.time()
        # The runner will pick this up and add to accepted_users
    elif body.response == "decline":
        inv.status = "declined"
        inv.responded_at = time.time()

    return {"ok": True, "status": inv.status}


# ---------------------------------------------------------------------------
# Cancel Booking API endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v1/cancel/status/{cancel_flow_id}")
def cancel_flow_status(cancel_flow_id: str) -> dict[str, object]:
    """Get cancel flow status for frontend polling."""
    flow = booking_store.get_cancel_flow(cancel_flow_id)
    if flow is None:
        raise HTTPException(status_code=404, detail="Cancel flow not found")

    return {
        "cancelFlowId": flow.id,
        "taskId": flow.task_id,
        "status": flow.status,
        "intention": flow.intention,
        "cancellingUserId": flow.cancelling_user_id,
        "remainingParticipants": [
            {"id": u.get("id"), "nickname": u.get("nickname")}
            for u in flow.remaining_participants
        ],
        "departedParticipants": [
            {"id": u.get("id"), "nickname": u.get("nickname")}
            for u in flow.departed_participants
        ],
        "rescheduleResponses": [
            {"userId": r.user_id, "vote": r.vote}
            for r in flow.reschedule_responses
        ],
        "newSlots": flow.new_slots,
        "backfillApproved": flow.backfill_approved,
        "backfillInvited": len(flow.backfill_invitations),
        "backfillAccepted": sum(
            1 for i in flow.backfill_invitations if i.status == "accepted"
        ),
        "replacementTaskId": flow.replacement_task_id,
    }


@app.get("/api/v1/cancel/notifications/{session_id}")
def cancel_notifications(session_id: str) -> dict[str, object]:
    """Get and clear pending cancel flow notifications for a session."""
    notifications = booking_store.pop_cancel_notifications(session_id)
    return {"notifications": notifications}


class CancelBackfillDecisionRequest(BaseModel):
    cancelFlowId: str
    approve: bool


@app.post("/api/v1/cancel/backfill-decision")
def cancel_backfill_decision(body: CancelBackfillDecisionRequest) -> dict[str, object]:
    """Submit backfill decision (approve or decline)."""
    flow = booking_store.get_cancel_flow(body.cancelFlowId)
    if flow is None:
        raise HTTPException(status_code=404, detail="Cancel flow not found")

    flow.backfill_approved = body.approve
    return {"ok": True, "approved": body.approve}


class CancelRescheduleVoteRequest(BaseModel):
    cancelFlowId: str
    userId: str
    vote: str = Field(pattern="^(accept|decline)$")


@app.post("/api/v1/cancel/reschedule-vote")
def cancel_reschedule_vote(body: CancelRescheduleVoteRequest) -> dict[str, object]:
    """Submit a reschedule vote from a participant."""
    import time as _time

    flow = booking_store.get_cancel_flow(body.cancelFlowId)
    if flow is None:
        raise HTTPException(status_code=404, detail="Cancel flow not found")

    for resp in flow.reschedule_responses:
        if resp.user_id == body.userId:
            resp.vote = body.vote  # type: ignore[assignment]
            resp.responded_at = _time.time()
            return {"ok": True, "vote": body.vote}

    raise HTTPException(
        status_code=404, detail="User not found in reschedule responses"
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
