from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import HTTPException

from ..focus import (
    Focus,
    list_result_labels,
    pick_focus,
    planner_last_results_payload,
    redact_last_results_for_summary,
    should_include_results_in_planner,
    visible_candidates,
)
from ..llm import GEMINI_MODEL, LLMSummary, build_summary_prompt, call_gemini_json
from ..models import Meta, OrchestrateRequest, OrchestrateResponse, OrchestratorState
from ..store import SessionStore
from ..tools import tool_by_name, tool_schemas
from .deck import build_deck_for_tool
from .merge import merge_slots, normalize_tool_args


logger = logging.getLogger("agent-social.orchestrator")

_COMPARE_TOKENS = ["对比", "比较", "compare", "which one", "best", "更适合", "哪个好", "推荐哪个"]


def _looks_like_compare(message: str) -> bool:
    m = (message or "").strip().lower()
    if not m:
        return False
    return any(tok in m for tok in _COMPARE_TOKENS)


def _safe_ui_blocks(blocks: object) -> list[dict[str, object]]:
    if not isinstance(blocks, list):
        return []
    safe: list[dict[str, object]] = []
    for b in blocks[:8]:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if not isinstance(t, str) or not t:
            continue
        if t not in {"text", "choices"}:
            continue
        safe.append({k: v for k, v in b.items()})
    return safe


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
            deck_res = build_deck_for_tool(tool_name, tool_args)
            if deck_res.deck is not None and deck_res.missing_fields:
                msg = "Almost there — fill the next card so I can run it."
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
                trace["toolCalls"].append({"toolName": tool_name, "toolArgs": tool_args})
            except Exception as e:
                raise HTTPException(status_code=503, detail=f"Tool execution failed: {e}") from e

            session.meta.pop("pending_tool", None)
            if isinstance(last_results_payload, dict) and last_results_payload:
                session.meta["last_results"] = last_results_payload

            assistant_message = (payload.get("assistantMessage") or "").strip() or "Done."
            _append_assistant_and_summarize(store, session, assistant_message)

            if result_type == "people" and payload.get("people") is not None:
                results = {"people": payload.get("people"), "meta": Meta(requestId=request_id, generatedBy=_generated_by(payload), model=GEMINI_MODEL)}
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
        msg = "Tell me what you want, and I’ll help you find people or activities."
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

    focus = pick_focus(body.message or "", last_results_full, previous_focus)
    if focus is not None:
        session.meta["focus"] = {"type": focus.type, "index": focus.index, "label": focus.label, "item": focus.item}

    include_results = should_include_results_in_planner(body.message or "", last_results_full, focus)
    raw_labels = list_result_labels(last_results_full)
    if not include_results and summary and raw_labels and any(lab in summary for lab in raw_labels):
        summary = ""

    result_labels = raw_labels if include_results else []
    visible = visible_candidates(last_results_full) if include_results else []
    if include_results:
        # If user is comparing multiple candidates, keep the full list instead of narrowing to one focus item.
        last_results_for_planner = last_results_full if _looks_like_compare(body.message or "") else planner_last_results_payload(last_results_full, focus)
    else:
        last_results_for_planner = None
    focus_for_prompt = {"type": focus.type, "label": focus.label} if (include_results and focus and not _looks_like_compare(body.message or "")) else None

    try:
        from ..planner import run_planner

        planner = run_planner(
            tool_schemas=tool_schemas(),
            summary=summary,
            history_lines=history_lines,
            current_intent=current_intent,
            current_slots=current_slots,
            user_message=body.message or "",
            last_results=last_results_for_planner,
            focus=focus_for_prompt,
            result_labels=result_labels,
            visible_context=visible,
            user_profile={},
        )
    except Exception as e:
        logger.exception("[orchestrate] planner_failed request_id=%s session_id=%s", request_id, session.id)
        raise HTTPException(status_code=503, detail=f"Planner call failed: {e}") from e

    trace["planner"] = planner.model_dump()

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

    # State 5: always use the card deck UI (no natural-language slot filling).
    if planner.decision == "need_more_info":
        tool_name = (planner.toolName or "").strip() or "intelligent_discovery"
        tool = tool_by_name(tool_name)
        tool_args = merge_slots(session.state.slots, planner.toolArgs or {})
        tool_args = normalize_tool_args(tool_name, tool_args)

        deck_res = build_deck_for_tool(tool_name, tool_args)
        # Even if planner asked for more info, we still only show a deck when we can generate one.
        if deck_res.deck is not None:
            session.meta["pending_tool"] = {"toolName": tool_name}
            session.state = OrchestratorState(intent=session.state.intent, slots=merge_slots(session.state.slots, tool_args))
            store.touch(session)
            # UX: no natural-language slot-filling questions; always keep it as card-driven.
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

        # Fallback: if we can't build a deck, return a short message (still no long questioning).
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
            uiBlocks=proposed_blocks or [{"type": "text", "text": msg}],
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

    # Validate args and produce deck if missing.
    deck_res = build_deck_for_tool(tool_name, tool_args)
    if deck_res.deck is not None and deck_res.missing_fields:
        session.meta["pending_tool"] = {"toolName": tool_name}
        session.state = OrchestratorState(intent=session.state.intent, slots=merge_slots(session.state.slots, tool_args))
        store.touch(session)
        _append_assistant_and_summarize(store, session, assistant_message)
        blocks = proposed_blocks or [{"type": "text", "text": assistant_message}]
        blocks.append({"type": "deck", "deck": deck_res.deck.model_dump()})
        return OrchestrateResponse(
            requestId=request_id,
            sessionId=session.id,
            intent=session.state.intent or "unknown",
            action="form",
            assistantMessage=assistant_message,
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
        trace["toolCalls"].append({"toolName": tool_name, "toolArgs": tool_args})
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
