from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import HTTPException

from ..focus import (
    redact_last_results_for_summary,
    visible_candidates,
)
from ..llm import GEMINI_MODEL, LLMSummary, build_summary_prompt, call_gemini_json
from ..models import Meta, OrchestrateRequest, OrchestrateResponse, OrchestratorState
from ..store import SessionStore
from ..tools import tool_by_name, tool_schemas
from ..tool_library.memory import get_or_init_memory
from .deck import build_deck_for_tool
from .merge import merge_slots, normalize_tool_args


logger = logging.getLogger("agent-social.orchestrator")

_ALLOWED_UI_BLOCK_TYPES = {"text", "choices", "deck", "results"}


def _safe_ui_blocks(blocks: object) -> list[dict[str, object]]:
    if not isinstance(blocks, list):
        return []
    safe: list[dict[str, object]] = []
    for b in blocks[:8]:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if not isinstance(t, str) or t not in _ALLOWED_UI_BLOCK_TYPES:
            continue
        safe.append({k: v for k, v in b.items()})
    return safe


def _record_ui_results_for_last_assistant_turn(session, ui_results: list[dict[str, Any]]) -> None:
    if not ui_results:
        return
    if not session.history or session.history[-1].role != "assistant":
        return
    at_ms = session.history[-1].at_ms
    history = session.meta.get("ui_results_history")
    if not isinstance(history, list):
        history = []
    history.append({"at_ms": at_ms, "ui_results": ui_results})
    # Keep small to reduce memory bloat.
    session.meta["ui_results_history"] = history[-12:]


def _build_all_visible_candidates(*, meta: dict[str, Any], domain: str, max_candidates: int = 80) -> list[dict[str, Any]]:
    """
    Collect full candidate objects for refinement from UI-visible history, across multiple result sets.
    Source of truth for full objects is meta["memory"] (populated by intelligent_discovery).
    """
    if domain not in {"person", "event"}:
        return []

    raw = meta.get("ui_results_history")
    if not isinstance(raw, list) or not raw:
        return []

    # Newest-first; stable dedupe by id.
    ids: list[str] = []
    seen: set[str] = set()
    for item in reversed(raw[-24:]):
        if not isinstance(item, dict):
            continue
        ui = item.get("ui_results")
        if not isinstance(ui, list):
            continue
        for it in ui:
            if not isinstance(it, dict):
                continue
            eid = it.get("id")
            if not isinstance(eid, str) or not eid.strip():
                continue
            if domain == "person" and "name" not in it:
                continue
            if domain == "event" and "title" not in it:
                continue
            if eid in seen:
                continue
            seen.add(eid)
            ids.append(eid)
            if len(ids) >= max_candidates:
                break
        if len(ids) >= max_candidates:
            break

    mem = get_or_init_memory(meta).model_dump()
    pool = mem.get("profiles") if domain == "person" else mem.get("events")
    if not isinstance(pool, dict):
        return []

    out: list[dict[str, Any]] = []
    for eid in ids:
        ent = pool.get(eid)
        if isinstance(ent, dict):
            out.append(ent)
    return out


def _build_planner_history(session, *, max_turns: int = 16) -> list[dict[str, Any]]:
    ui_map: dict[int, list[dict[str, Any]]] = {}
    raw = session.meta.get("ui_results_history")
    if isinstance(raw, list):
        for item in raw[-24:]:
            if not isinstance(item, dict):
                continue
            at_ms = item.get("at_ms")
            ui_results = item.get("ui_results")
            if not isinstance(at_ms, int) or not isinstance(ui_results, list):
                continue
            ui_map[at_ms] = [x for x in ui_results if isinstance(x, dict)]

    turns = session.history[-max_turns:]
    out: list[dict[str, Any]] = []
    for t in turns:
        d: dict[str, Any] = {"role": t.role, "text": t.text}
        ui = ui_map.get(t.at_ms)
        if ui:
            d["ui results"] = ui
        out.append(d)
    return out


def _append_assistant_and_summarize(store: SessionStore, session, assistant_message: str) -> None:
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
        logger.info("[orchestrate] summarizer_failed session_id=%s", session.id, exc_info=True)


def _intent_from_last_results(last_results: dict[str, Any] | None) -> str:
    if isinstance(last_results, dict) and last_results.get("type") == "things":
        return "find_things"
    if isinstance(last_results, dict) and last_results.get("type") == "people":
        return "find_people"
    return "unknown"


def _generated_by(payload: dict[str, Any]) -> str:
    gb = payload.get("generatedBy")
    return gb if gb in {"mock", "llm"} else "llm"


def handle_orchestrate(*, store: SessionStore, body: OrchestrateRequest) -> OrchestrateResponse:
    request_id = str(uuid.uuid4())
    store.cleanup()

    session = store.get(body.sessionId or "") if body.sessionId else None
    if session is None:
        session = store.create()
    if body.reset:
        store.reset(session)

    trace: dict[str, object] = {"plannerInput": None, "plannerOutput": None}

    if body.message:
        store.append(session, "user", body.message)

    incoming_form = body.submit.data if body.submit else {}
    if incoming_form:
        session.state = OrchestratorState(
            intent=session.state.intent,
            slots=merge_slots(session.state.slots, incoming_form),
        )
        store.touch(session)

    # Submit-only flow should NOT re-run the planner. If we have a pending tool, validate/execute it.
    if not body.message:
        pending = session.meta.get("pending_tool")
        if isinstance(pending, dict) and isinstance(pending.get("toolName"), str):
            tool_name = pending["toolName"]
            tool = tool_by_name(tool_name)
            if tool is None:
                session.meta.pop("pending_tool", None)
                msg = "I lost track of the pending action. Tell me what you want to do and I’ll regenerate the plan."
                _append_assistant_and_summarize(store, session, msg)
                return OrchestrateResponse(
                    requestId=request_id,
                    sessionId=session.id,
                    intent=session.state.intent or "unknown",
                    action="chat",
                    assistantMessage=msg,
                    missingFields=[],
                    deck=None,
                    form=None,
                    results=None,
                    state=session.state,
                    uiBlocks=[{"type": "text", "text": msg}],
                    trace=trace,
                )

            tool_args = normalize_tool_args(tool_name, session.state.slots)
            if tool_name == "results_refine" and not isinstance(tool_args.get("candidates"), list):
                domain = tool_args.get("domain")
                if isinstance(domain, str) and domain in {"person", "event"}:
                    tool_args = dict(tool_args)
                    tool_args["candidates"] = _build_all_visible_candidates(meta=session.meta, domain=domain)
            deck_res = build_deck_for_tool(tool_name, tool_args)
            if deck_res.deck is not None and deck_res.missing_fields:
                msg = "Fill the next card."
                _append_assistant_and_summarize(store, session, msg)
                blocks = [{"type": "text", "text": msg}, {"type": "deck", "deck": deck_res.deck.model_dump()}]
                return OrchestrateResponse(
                    requestId=request_id,
                    sessionId=session.id,
                    intent=session.state.intent or "unknown",
                    action="form",
                    assistantMessage=msg,
                    missingFields=deck_res.missing_fields,
                    deck=deck_res.deck,
                    form=None,
                    results=None,
                    state=session.state,
                    uiBlocks=blocks,
                    trace=trace,
                )

            try:
                result_type, payload, last_results_payload = tool.execute(session.meta, tool_args)
            except Exception as e:
                raise HTTPException(status_code=503, detail=f"Tool execution failed: {e}") from e

            session.meta.pop("pending_tool", None)
            if isinstance(last_results_payload, dict) and last_results_payload:
                session.meta["last_results"] = last_results_payload

            assistant_message = (payload.get("assistantMessage") or "").strip() or "Done."
            _append_assistant_and_summarize(store, session, assistant_message)
            if result_type == "people" and payload.get("people") is not None:
                results = {"people": payload.get("people"), "meta": Meta(requestId=request_id, generatedBy=_generated_by(payload), model=GEMINI_MODEL)}
                _record_ui_results_for_last_assistant_turn(
                    session,
                    visible_candidates(session.meta.get("last_results") if isinstance(session.meta.get("last_results"), dict) else None),
                )
                return OrchestrateResponse(
                    requestId=request_id,
                    sessionId=session.id,
                    intent="find_people",
                    action="results",
                    assistantMessage=assistant_message,
                    missingFields=[],
                    deck=None,
                    form=None,
                    results=results,
                    state=session.state,
                    uiBlocks=[{"type": "text", "text": assistant_message}, {"type": "results", "results": results}],
                    trace=trace,
                )

            if result_type == "things" and payload.get("things") is not None:
                results = {"things": payload.get("things"), "meta": Meta(requestId=request_id, generatedBy=_generated_by(payload), model=GEMINI_MODEL)}
                _record_ui_results_for_last_assistant_turn(
                    session,
                    visible_candidates(session.meta.get("last_results") if isinstance(session.meta.get("last_results"), dict) else None),
                )
                return OrchestrateResponse(
                    requestId=request_id,
                    sessionId=session.id,
                    intent="find_things",
                    action="results",
                    assistantMessage=assistant_message,
                    missingFields=[],
                    deck=None,
                    form=None,
                    results=results,
                    state=session.state,
                    uiBlocks=[{"type": "text", "text": assistant_message}, {"type": "results", "results": results}],
                    trace=trace,
                )

            return OrchestrateResponse(
                requestId=request_id,
                sessionId=session.id,
                intent=session.state.intent or _intent_from_last_results(session.meta.get("last_results")),
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

        # No message + no pending tool
        if body.submit:
            # 收到表单提交但 pending_tool 丢失，提示用户重新开始
            msg = "会话已过期，请重新告诉我你想找什么。"
        else:
            msg = "Tell me what you want, and I'll help you find people or activities."
        _append_assistant_and_summarize(store, session, msg)
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent=session.state.intent or "unknown",
            action="chat",
            assistantMessage=msg,
            missingFields=[],
            deck=None,
            form=None,
            results=None,
            state=session.state,
            uiBlocks=[{"type": "text", "text": msg}],
            trace=trace,
        )

    # Message flow: run planner
    summary = (session.meta.get("summary") or "") if isinstance(session.meta.get("summary"), str) else ""

    try:
        from ..planner import run_planner

        planner_history = _build_planner_history(session, max_turns=16)
        planner_input = {
            "sessionId": session.id,
            "toolSchemas": tool_schemas(),
            "summary": summary,
            "history": planner_history,
        }
        trace["plannerInput"] = planner_input

        planner = run_planner(
            tool_schemas=tool_schemas(),
            session_id=session.id,
            summary=summary,
            history=planner_history,
        )
    except Exception as e:
        logger.exception("[orchestrate] planner_failed request_id=%s session_id=%s", request_id, session.id)
        raise HTTPException(status_code=503, detail=f"Planner call failed: {e}") from e

    trace["plannerOutput"] = planner.model_dump()

    # Update slots from planner extraction (dotted keys supported).
    session.state = OrchestratorState(
        intent=planner.intent,
        slots=merge_slots(session.state.slots, planner.slots),
    )
    store.touch(session)

    assistant_message = planner.assistantMessage
    proposed_blocks = _safe_ui_blocks(planner.uiBlocks)

    if planner.decision in {"chat", "refuse", "cant_do"}:
        _append_assistant_and_summarize(store, session, assistant_message)
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

    # State 5: need_more_info - planner's uiBlocks take priority over default deck.
    if planner.decision == "need_more_info":
        # If planner returned uiBlocks (e.g., choices for city), use them directly.
        # This makes planner the authoritative source for UI rendering.
        if proposed_blocks:
            msg = (assistant_message or "").strip() or "Please select an option."
            _append_assistant_and_summarize(store, session, msg)
            return OrchestrateResponse(
                requestId=request_id,
                sessionId=session.id,
                intent=session.state.intent or "unknown",
                action="form",
                assistantMessage=msg,
                missingFields=[],
                deck=None,
                form=None,
                results=None,
                state=session.state,
                uiBlocks=proposed_blocks,
                trace=trace,
            )

        # Fallback: planner did not provide uiBlocks, use default deck generation.
        tool_name = (planner.toolName or "").strip() or "intelligent_discovery"
        tool = tool_by_name(tool_name)
        tool_args = merge_slots(session.state.slots, planner.toolArgs or {})
        tool_args = normalize_tool_args(tool_name, tool_args)
        if tool_name == "results_refine" and not isinstance(tool_args.get("candidates"), list):
            domain = tool_args.get("domain")
            if isinstance(domain, str) and domain in {"person", "event"}:
                tool_args = dict(tool_args)
                tool_args["candidates"] = _build_all_visible_candidates(meta=session.meta, domain=domain)

        deck_res = build_deck_for_tool(tool_name, tool_args)
        if deck_res.deck is not None:
            session.meta["pending_tool"] = {"toolName": tool_name}
            session.state = OrchestratorState(intent=session.state.intent, slots=merge_slots(session.state.slots, tool_args))
            store.touch(session)
            msg = "Fill the next card."
            _append_assistant_and_summarize(store, session, msg)
            blocks: list[dict[str, object]] = [{"type": "text", "text": msg}]
            blocks.append({"type": "deck", "deck": deck_res.deck.model_dump()})
            return OrchestrateResponse(
                requestId=request_id,
                sessionId=session.id,
                intent=session.state.intent or "unknown",
                action="form",
                assistantMessage=msg,
                missingFields=deck_res.missing_fields,
                deck=deck_res.deck,
                form=None,
                results=None,
                state=session.state,
                uiBlocks=blocks,
                trace=trace,
            )

        # Fallback: if we can't build a deck either, return a short message.
        msg = (assistant_message or "").strip() or "I need one more detail before I can proceed."
        _append_assistant_and_summarize(store, session, msg)
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent=session.state.intent or "unknown",
            action="chat",
            assistantMessage=msg,
            missingFields=[],
            deck=None,
            form=None,
            results=None,
            state=session.state,
            uiBlocks=[{"type": "text", "text": msg}],
            trace=trace,
        )

    tool_name = (planner.toolName or "").strip()
    if not tool_name:
        msg = assistant_message or "I’m not sure which tool to use yet. Tell me a bit more."
        _append_assistant_and_summarize(store, session, msg)
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent=session.state.intent or "unknown",
            action="chat",
            assistantMessage=msg,
            missingFields=[],
            deck=None,
            form=None,
            results=None,
            state=session.state,
            uiBlocks=proposed_blocks or [{"type": "text", "text": msg}],
            trace=trace,
        )

    tool = tool_by_name(tool_name)
    if tool is None:
        msg = assistant_message or "I don’t have a tool for that yet."
        _append_assistant_and_summarize(store, session, msg)
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent=session.state.intent or "unknown",
            action="chat",
            assistantMessage=msg,
            missingFields=[],
            deck=None,
            form=None,
            results=None,
            state=session.state,
            uiBlocks=proposed_blocks or [{"type": "text", "text": msg}],
            trace=trace,
        )

    tool_args = merge_slots(session.state.slots, planner.toolArgs or {})
    tool_args = normalize_tool_args(tool_name, tool_args)
    if tool_name == "results_refine" and not isinstance(tool_args.get("candidates"), list):
        domain = tool_args.get("domain")
        if isinstance(domain, str) and domain in {"person", "event"}:
            tool_args = dict(tool_args)
            tool_args["candidates"] = _build_all_visible_candidates(meta=session.meta, domain=domain)

    # Validate args and produce deck if missing.
    deck_res = build_deck_for_tool(tool_name, tool_args)
    if deck_res.deck is not None and deck_res.missing_fields:
        session.meta["pending_tool"] = {"toolName": tool_name}
        session.state = OrchestratorState(intent=session.state.intent, slots=merge_slots(session.state.slots, tool_args))
        store.touch(session)
        msg = "Fill the next card."
        _append_assistant_and_summarize(store, session, msg)
        blocks = proposed_blocks or [{"type": "text", "text": msg}]
        blocks.append({"type": "deck", "deck": deck_res.deck.model_dump()})
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent=session.state.intent or "unknown",
            action="form",
            assistantMessage=msg,
            missingFields=deck_res.missing_fields,
            deck=deck_res.deck,
            form=None,
            results=None,
            state=session.state,
            uiBlocks=blocks,
            trace=trace,
        )

    if deck_res.validation_message:
        msg = f"{assistant_message}\n\n(Validation issue: {deck_res.validation_message})"
        _append_assistant_and_summarize(store, session, msg)
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent=session.state.intent or "unknown",
            action="chat",
            assistantMessage=msg,
            missingFields=[],
            deck=None,
            form=None,
            results=None,
            state=session.state,
            uiBlocks=proposed_blocks or [{"type": "text", "text": msg}],
            trace=trace,
        )

    # Execute tool immediately.
    try:
        result_type, payload, last_results_payload = tool.execute(session.meta, tool_args)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Tool execution failed: {e}") from e

    if isinstance(last_results_payload, dict) and last_results_payload:
        session.meta["last_results"] = last_results_payload
    session.meta.pop("pending_tool", None)

    final_message = (payload.get("assistantMessage") or "").strip() or assistant_message or "Done."
    _append_assistant_and_summarize(store, session, final_message)

    if result_type == "people" and payload.get("people") is not None:
        results = {"people": payload.get("people"), "meta": Meta(requestId=request_id, generatedBy=_generated_by(payload), model=GEMINI_MODEL)}
        blocks = proposed_blocks or [{"type": "text", "text": final_message}]
        blocks.append({"type": "results", "results": results})
        _record_ui_results_for_last_assistant_turn(
            session,
            visible_candidates(session.meta.get("last_results") if isinstance(session.meta.get("last_results"), dict) else None),
        )
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
            uiBlocks=blocks,
            trace=trace,
        )

    if result_type == "things" and payload.get("things") is not None:
        results = {"things": payload.get("things"), "meta": Meta(requestId=request_id, generatedBy=_generated_by(payload), model=GEMINI_MODEL)}
        blocks = proposed_blocks or [{"type": "text", "text": final_message}]
        blocks.append({"type": "results", "results": results})
        _record_ui_results_for_last_assistant_turn(
            session,
            visible_candidates(session.meta.get("last_results") if isinstance(session.meta.get("last_results"), dict) else None),
        )
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
            uiBlocks=blocks,
            trace=trace,
        )

    return OrchestrateResponse(
        requestId=request_id,
        sessionId=session.id,
        intent=session.state.intent or _intent_from_last_results(session.meta.get("last_results")),
        action="chat",
        assistantMessage=final_message,
        missingFields=[],
        deck=None,
        form=None,
        results=None,
        state=session.state,
        uiBlocks=proposed_blocks or [{"type": "text", "text": final_message}],
        trace=trace,
    )
