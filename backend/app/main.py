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
    LLMPlannerDecision,
    LLMSummary,
    LLMThings,
    build_planner_prompt,
    build_people_generation_prompt,
    build_summary_prompt,
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
from .tools import tool_by_name, tool_schemas
from .focus import (
    Focus,
    list_result_labels,
    pick_focus,
    planner_last_results_payload,
    redact_last_results_for_summary,
    should_include_results_in_planner,
)


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
    def is_navigation_query(message: str) -> bool:
        m = (message or "").strip()
        if not m:
            return False
        nav_tokens = ["怎么走", "怎么去", "路线", "地铁", "公交", "打车", "导航", "几号线", "换乘"]
        return any(t in m for t in nav_tokens)

    def navigation_fallback_message(message: str) -> str:
        m = (message or "").strip()
        if not m:
            return "我现在主要能帮你“找人/组局”。如果你想问路线，请告诉我出发地和目的地所在城市。"

        # Special-case a common ambiguity: 北京黄庄 vs 上海人民广场
        if "黄庄" in m and "人民广场" in m:
            return (
                "你说的“黄庄”通常指北京的黄庄（地铁站），而“人民广场”通常指上海。"
                "你要去的是哪个城市的“人民广场”？\n"
                "如果是上海人民广场：需要先从北京到上海（高铁/飞机），到上海后再坐地铁到“人民广场站”。\n"
                "如果你在北京、想去北京某个“人民广场/人民公园”之类的地点，请给我更具体的名称或附近地铁站。"
            )

        return "我现在主要能帮你“找人/组局”。如果你想问路线导航，请告诉我：出发地/目的地各在哪个城市，以及更具体的地名或地铁站。"

    def merge_slots(base: dict, incoming: dict) -> dict:
        merged = dict(base or {})
        for k, v in (incoming or {}).items():
            if v is None:
                continue
            merged[k] = v
        return merged

    def safe_ui_blocks(blocks: object) -> list[dict[str, object]]:
        if not isinstance(blocks, list):
            return []
        safe: list[dict[str, object]] = []
        for b in blocks[:8]:
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if not isinstance(t, str) or not t:
                continue
            # allow a small set for now; executor will inject deck/results blocks itself
            if t not in {"text", "choices"}:
                continue
            safe.append({k: v for k, v in b.items()})
        return safe

    def append_assistant_and_summarize(session, assistant_message: str) -> None:
        store.append(session, "assistant", assistant_message)
        prev_summary = (session.meta.get("summary") or "") if isinstance(session.meta.get("summary"), str) else ""
        recent_turns = [f"{t.role}: {t.text}" for t in session.history[-16:]]
        last_results_full = session.meta.get("last_results") if isinstance(session.meta.get("last_results"), dict) else None
        last_results = redact_last_results_for_summary(last_results_full)
        try:
            llm_sum = call_gemini_json(
                prompt=build_summary_prompt(
                    previous_summary=prev_summary,
                    recent_turns=recent_turns,
                    last_results=last_results,
                ),
                response_model=LLMSummary,
            )
            session.meta["summary"] = (llm_sum.summary or "").strip()
            store.touch(session)
        except Exception:
            # Best-effort: never fail the request due to summarization.
            logger.info("[orchestrate] summarizer_failed session_id=%s", session.id, exc_info=True)

    request_id = str(uuid.uuid4())
    store.cleanup()

    session = store.get(body.sessionId or "") if body.sessionId else None
    if session is None:
        session = store.create()
    if body.reset:
        store.reset(session)

    trace: dict[str, object] = {"planner": None, "toolCalls": []}

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

    # IMPORTANT: submit-only should NOT re-run the planner.
    if body.message:
        history_lines = [f"{t.role}: {t.text}" for t in session.history[-12:]]
        current_slots = session.state.slots
        current_intent = session.state.intent or "unknown"
        last_results_full = session.meta.get("last_results") if isinstance(session.meta.get("last_results"), dict) else None
        summary = (session.meta.get("summary") or "") if isinstance(session.meta.get("summary"), str) else ""

        previous_focus: Focus | None = None
        try:
            raw_focus = session.meta.get("focus")
            if isinstance(raw_focus, dict) and raw_focus.get("type") in {"people", "things"} and isinstance(raw_focus.get("index"), int):
                label = raw_focus.get("label") if isinstance(raw_focus.get("label"), str) else ""
                item = raw_focus.get("item") if isinstance(raw_focus.get("item"), dict) else {}
                previous_focus = Focus(type=raw_focus["type"], index=raw_focus["index"], label=label, item=item)
        except Exception:
            previous_focus = None

        focus = pick_focus(body.message, last_results_full, previous_focus)
        if focus is not None:
            session.meta["focus"] = {"type": focus.type, "index": focus.index, "label": focus.label, "item": focus.item}
        include_results = should_include_results_in_planner(body.message, last_results_full, focus)
        raw_labels = list_result_labels(last_results_full)
        if not include_results and summary and raw_labels and any(lab in summary for lab in raw_labels):
            # Avoid the planner getting anchored by a copied profile bio in memory.
            summary = ""
        result_labels = raw_labels if include_results else []
        last_results_for_planner = planner_last_results_payload(last_results_full, focus) if include_results else None
        focus_for_prompt = {"type": focus.type, "label": focus.label} if (include_results and focus) else None

        try:
            planner = call_gemini_json(
                prompt=build_planner_prompt(
                    tool_schemas=tool_schemas(),
                    summary=summary,
                    history_lines=history_lines,
                    current_intent=current_intent,
                    current_slots=current_slots,
                    user_message=body.message,
                    last_results=last_results_for_planner,
                    focus=focus_for_prompt,
                    result_labels=result_labels,
                ),
                response_model=LLMPlannerDecision,
            )
        except Exception as e:
            logger.exception("[orchestrate] planner_failed request_id=%s session_id=%s", request_id, session.id)
            raise HTTPException(status_code=503, detail=f"Gemini call failed: {e}") from e

        trace["planner"] = planner.model_dump()
        session.state = OrchestratorState(
            intent=planner.intent,
            slots=merge_slots(session.state.slots, planner.slots),
        )
        store.touch(session)

        assistant_message = planner.assistantMessage
        proposed_blocks = safe_ui_blocks(planner.uiBlocks)

        if planner.decision == "chat":
            append_assistant_and_summarize(session, assistant_message)
            return OrchestrateResponse(
                requestId=request_id,
                sessionId=session.id,
                intent=session.state.intent or "unknown",
                action="chat",
                assistantMessage=assistant_message,
                missingFields=[],
                deck=None,
                form=None,
                results=None,
                state=session.state,
                uiBlocks=proposed_blocks or [{"type": "text", "text": assistant_message}],
                trace=trace,
            )

        if planner.decision == "tool":
            # Tool args default to current merged slots; allow planner override.
            tool_name = (planner.toolName or session.state.intent or "").strip()
            tool = tool_by_name(tool_name)
            if tool is None:
                if is_navigation_query(body.message or ""):
                    assistant_message = navigation_fallback_message(body.message or "")
                else:
                    assistant_message = "我现在主要能帮你“找人”或“找事/组局”。你是想找人，还是想组一个活动/找搭子？"
                append_assistant_and_summarize(session, assistant_message)
                return OrchestrateResponse(
                    requestId=request_id,
                    sessionId=session.id,
                    intent=session.state.intent or "unknown",
                    action="chat",
                    assistantMessage=assistant_message,
                    missingFields=[],
                    deck=None,
                    form=None,
                    results=None,
                    state=session.state,
                    uiBlocks=[{"type": "text", "text": assistant_message}],
                    trace=trace,
                )

            effective_args = merge_slots(session.state.slots, planner.toolArgs or {})
            session.state = OrchestratorState(intent=tool.name, slots=effective_args)
            store.touch(session)

            deck, missing = build_deck(tool.name, effective_args)
            if deck is not None and missing:
                # Ask for missing info (planner already wrote assistant_message)
                append_assistant_and_summarize(session, assistant_message)
                blocks = proposed_blocks or [{"type": "text", "text": assistant_message}]
                blocks.append({"type": "deck", "deck": deck.model_dump()})
                return OrchestrateResponse(
                    requestId=request_id,
                    sessionId=session.id,
                    intent=tool.name,
                    action="form",
                    assistantMessage=assistant_message,
                    missingFields=missing,
                    deck=deck,
                    form=None,
                    results=None,
                    state=session.state,
                    uiBlocks=blocks,
                    trace=trace,
                )

            try:
                trace_tool_calls = trace.get("toolCalls")
                if isinstance(trace_tool_calls, list):
                    trace_tool_calls.append({"name": tool.name, "args": effective_args})
                result_type, payload, last_results_payload = tool.execute(effective_args)
            except Exception as e:
                logger.exception("[orchestrate] tool_failed request_id=%s session_id=%s tool=%s", request_id, session.id, tool.name)
                raise HTTPException(status_code=503, detail=f"Tool execution failed: {e}") from e

            session.meta["last_results"] = last_results_payload
            final_message = (payload.get("assistantMessage") or "").strip() or assistant_message
            if not final_message:
                final_message = "好，我已经生成结果了。"

            append_assistant_and_summarize(session, final_message)
            if result_type == "people":
                people = payload.get("people") or []
                results = {"people": people, "meta": Meta(requestId=request_id, generatedBy="llm", model=GEMINI_MODEL)}
            else:
                things = payload.get("things") or []
                results = {"things": things, "meta": Meta(requestId=request_id, generatedBy="llm", model=GEMINI_MODEL)}

            blocks = proposed_blocks or [{"type": "text", "text": final_message}]
            blocks.append({"type": "results", "results": results})
            return OrchestrateResponse(
                requestId=request_id,
                sessionId=session.id,
                intent=tool.name,
                action="results",
                assistantMessage=final_message,
                missingFields=[],
                deck=None,
                form=None,
                results=results,
                state=session.state,
                uiBlocks=blocks,
                trace=trace,
            )

        # decision == collect
        deck, missing = build_deck(session.state.intent or "unknown", session.state.slots)
        if deck is not None and missing:
            append_assistant_and_summarize(session, assistant_message)
            blocks = proposed_blocks or [{"type": "text", "text": assistant_message}]
            blocks.append({"type": "deck", "deck": deck.model_dump()})
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
                uiBlocks=blocks,
                trace=trace,
            )

        # Nothing missing → planner wanted collect but we can proceed with a direct tool based on intent.
        assistant_message = assistant_message or "我已经收集到足够信息了，你要我开始生成结果吗？"
        append_assistant_and_summarize(session, assistant_message)
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent=session.state.intent or "unknown",
            action="chat",
            assistantMessage=assistant_message,
            missingFields=[],
            deck=None,
            form=None,
            results=None,
            state=session.state,
            uiBlocks=proposed_blocks or [{"type": "text", "text": assistant_message}],
            trace=trace,
        )

    # No message: respond based on deck/results only (submit/reset flow).
    if session.state.intent in {"find_people", "find_things"}:
        assistant_message = "继续补全下一张卡片。"
    else:
        assistant_message = "你可以先说一句你的需求，我来帮你把它拆成一张张卡。"

    deck, missing = build_deck(session.state.intent or "unknown", session.state.slots)

    if session.state.intent == "find_people" and not missing:
        try:
            tool = tool_by_name("find_people")
            assert tool is not None
            result_type, payload, last_results_payload = tool.execute(session.state.slots)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Gemini call failed: {e}") from e

        final_message = (payload.get("assistantMessage") or "").strip() or "好，我按你的条件生成了一批候选人。"
        session.meta["last_results"] = last_results_payload
        append_assistant_and_summarize(session, final_message)
        people = payload.get("people") or []
        results = {"people": people, "meta": Meta(requestId=request_id, generatedBy="llm", model=GEMINI_MODEL)}
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent="find_people",
            action="results",
            assistantMessage=final_message,
            missingFields=[],
            deck=None,
            form=None,
            results=results,
            state=session.state,
            uiBlocks=[{"type": "text", "text": final_message}, {"type": "results", "results": results}],
            trace=trace,
        )

    if session.state.intent == "find_things" and not missing:
        try:
            tool = tool_by_name("find_things")
            assert tool is not None
            result_type, payload, last_results_payload = tool.execute(session.state.slots)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Gemini call failed: {e}") from e

        final_message = (payload.get("assistantMessage") or "").strip() or "好，我给你生成了一些可加入/可发起的活动建议。"
        session.meta["last_results"] = last_results_payload
        append_assistant_and_summarize(session, final_message)
        things = payload.get("things") or []
        results = {"things": things, "meta": Meta(requestId=request_id, generatedBy="llm", model=GEMINI_MODEL)}
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent="find_things",
            action="results",
            assistantMessage=final_message,
            missingFields=[],
            deck=None,
            form=None,
            results=results,
            state=session.state,
            uiBlocks=[{"type": "text", "text": final_message}, {"type": "results", "results": results}],
            trace=trace,
        )

    if deck is not None and missing:
        append_assistant_and_summarize(session, assistant_message)
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
            uiBlocks=[{"type": "text", "text": assistant_message}, {"type": "deck", "deck": deck.model_dump()}],
            trace=trace,
        )

    append_assistant_and_summarize(session, assistant_message)
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
        uiBlocks=[{"type": "text", "text": assistant_message}],
        trace=trace,
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
