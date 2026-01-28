from __future__ import annotations

import logging
from typing import Any

from ..focus import visible_candidates
from ..llm import (
    MissingParam,
    PlannerDecision,
    build_planner_prompt,
    call_gemini_json,
    resolve_planner_model,
)
from ..models import (
    FormContent,
    FormQuestion,
    FormQuestionOption,
    OrchestrateRequest,
    OrchestrateResponse,
    MessageContent,
    ResultsContent,
)
from ..store import SessionStore
from ..tools import tool_by_name, tool_schemas
from ..tool_library.registry import validate_tool_args


logger = logging.getLogger("agent-social.orchestrator")


def _convert_missing_param_to_form_question(mp: MissingParam) -> FormQuestion:
    """Recursively convert MissingParam (with nested followUp) to FormQuestion."""
    options: list[FormQuestionOption] = []
    for opt in mp.options:
        follow_up = None
        if opt.followUp:
            follow_up = [_convert_missing_param_to_form_question(f) for f in opt.followUp]
        options.append(FormQuestionOption(
            label=opt.label,
            value=opt.value,
            followUp=follow_up,
        ))
    return FormQuestion(param=mp.param, question=mp.question, options=options)


def _build_context_history(session, *, max_turns: int = 16) -> list[dict[str, Any]]:
    """Build context history for planner."""
    # Get UI results mapping
    ui_map: dict[int, list[dict[str, Any]]] = {}
    raw = session.meta.get("ui_results_history")
    if isinstance(raw, list):
        for item in raw[-24:]:
            if not isinstance(item, dict):
                continue
            at_ms = item.get("at_ms")
            ui_results = item.get("ui_results")
            if isinstance(at_ms, int) and isinstance(ui_results, list):
                ui_map[at_ms] = [x for x in ui_results if isinstance(x, dict)]

    # Build history with results attached
    turns = session.history[-max_turns:]
    out: list[dict[str, Any]] = []
    for t in turns:
        d: dict[str, Any] = {"role": t.role, "text": t.text}
        ui = ui_map.get(t.at_ms)
        if ui:
            d["results"] = ui
        out.append(d)
    return out


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


def _record_assistant_message(session, store: SessionStore, text: str) -> None:
    """Record assistant message."""
    store.append(session, "assistant", text)
    store.touch(session)


def _execute_tool_and_respond(
    session,
    store: SessionStore,
    tool_name: str,
    tool_args: dict[str, Any],
    trace: dict[str, Any],
) -> OrchestrateResponse:
    """Execute tool and return response."""
    tool = tool_by_name(tool_name)
    if tool is None:
        _record_assistant_message(session, store, f"Unknown tool: {tool_name}")
        return OrchestrateResponse(
            sessionId=session.id,
            type="message",
            content=MessageContent(text=f"Sorry, I encountered an error: unknown tool '{tool_name}'."),
            trace=trace,
        )

    try:
        result_type, payload, last_results_payload = tool.execute(session.meta, tool_args)
    except Exception as e:
        logger.exception("[orchestrate] tool_execution_failed tool=%s", tool_name)
        _record_assistant_message(session, store, f"Tool error: {e}")
        return OrchestrateResponse(
            sessionId=session.id,
            type="message",
            content=MessageContent(text="Sorry, I encountered an error while processing your request."),
            trace=trace,
        )

    # Store results in session
    if isinstance(last_results_payload, dict) and last_results_payload:
        session.meta["last_results"] = last_results_payload

    # Record UI results for future reference resolution
    _record_ui_results_for_last_assistant_turn(
        session,
        visible_candidates(session.meta.get("last_results") if isinstance(session.meta.get("last_results"), dict) else None),
    )

    summary = (payload.get("assistantMessage") or "").strip() or "Here are your results."
    _record_assistant_message(session, store, summary)

    # Build results content
    results_data: dict[str, Any] = {}
    if result_type == "people" and payload.get("people"):
        results_data["people"] = payload["people"]
    elif result_type == "things" and payload.get("things"):
        results_data["things"] = payload["things"]

    return OrchestrateResponse(
        sessionId=session.id,
        type="results",
        content=ResultsContent(results=results_data, summary=summary),
        trace=trace,
    )


def handle_orchestrate(*, store: SessionStore, body: OrchestrateRequest) -> OrchestrateResponse:
    """Orchestrator handler."""
    store.cleanup()

    # Get or create session
    session = store.get(body.sessionId or "") if body.sessionId else None
    if session is None:
        session = store.create()
    if body.reset:
        store.reset(session)

    trace: dict[str, Any] = {"plannerInput": None, "plannerOutput": None}

    # Handle form submission (MISSING_INFO flow)
    if body.formSubmission:
        sub = body.formSubmission
        # Merge answers into toolArgs
        merged_args = dict(sub.toolArgs)
        for param, value in sub.answers.items():
            # Skip null values (placeholders from followUp navigation)
            if value is None:
                continue
            # Support dotted paths like "structured_filters.person_filters.age_range"
            parts = param.split(".")
            target = merged_args
            for p in parts[:-1]:
                if p not in target:
                    target[p] = {}
                target = target[p]
            target[parts[-1]] = value

        # Validate merged args
        validation = validate_tool_args(sub.toolName, merged_args)
        if not validation.valid:
            # Validation failed - record error and re-run planner
            error_msg = f"Validation failed: {'; '.join(validation.errors)}"
            store.append(session, "system", error_msg)
            # Fall through to run planner again
        else:
            # Validation passed - execute tool
            return _execute_tool_and_respond(
                session, store, sub.toolName, validation.normalized_args or merged_args, trace
            )

    # Handle user message
    if body.message:
        store.append(session, "user", body.message)

    # Build context and run planner
    summary = (session.meta.get("summary") or "") if isinstance(session.meta.get("summary"), str) else ""
    context_history = _build_context_history(session, max_turns=16)

    # Resolve planner model from request
    planner_model = resolve_planner_model(body.plannerModel)

    planner_input = {
        "sessionId": session.id,
        "toolSchemas": tool_schemas(),
        "summary": summary,
        "history": context_history,
        "model": planner_model,
    }
    trace["plannerInput"] = planner_input

    try:
        planner = call_gemini_json(
            prompt=build_planner_prompt(
                tool_schemas=tool_schemas(),
                session_id=session.id,
                summary=summary,
                history=context_history,
            ),
            response_model=PlannerDecision,
            model=planner_model,
        )
    except Exception as e:
        logger.exception("[orchestrate] planner_failed session_id=%s", session.id)
        _record_assistant_message(session, store, "Sorry, I had trouble processing that.")
        return OrchestrateResponse(
            sessionId=session.id,
            type="message",
            content=MessageContent(text="Sorry, I had trouble processing that. Please try again."),
            trace=trace,
        )

    trace["plannerOutput"] = planner.model_dump()

    # Handle each decision type
    decision = planner.decision

    if decision == "SHOULD_NOT_ANSWER":
        msg = planner.message or "I'm sorry, I can't help with that request."
        _record_assistant_message(session, store, msg)
        return OrchestrateResponse(
            sessionId=session.id,
            type="message",
            content=MessageContent(text=msg),
            trace=trace,
        )

    if decision == "DO_NOT_KNOW_HOW":
        msg = planner.message or "I understand what you want, but I'm not able to help with that."
        _record_assistant_message(session, store, msg)
        return OrchestrateResponse(
            sessionId=session.id,
            type="message",
            content=MessageContent(text=msg),
            trace=trace,
        )

    if decision == "SOCIAL_GUIDANCE":
        msg = planner.message or "Tell me more about what's on your mind."
        _record_assistant_message(session, store, msg)
        return OrchestrateResponse(
            sessionId=session.id,
            type="message",
            content=MessageContent(text=msg),
            trace=trace,
        )

    if decision == "CHITCHAT":
        msg = planner.message or "That's interesting!"
        _record_assistant_message(session, store, msg)
        return OrchestrateResponse(
            sessionId=session.id,
            type="message",
            content=MessageContent(text=msg),
            trace=trace,
        )

    if decision == "CONTEXT_SUFFICIENT":
        msg = planner.message or "Based on the information we have..."
        _record_assistant_message(session, store, msg)
        return OrchestrateResponse(
            sessionId=session.id,
            type="message",
            content=MessageContent(text=msg),
            trace=trace,
        )

    if decision == "MISSING_INFO":
        tool_name = planner.toolName or ""
        tool_args = planner.toolArgs or {}
        missing = planner.missingParams or []

        # Convert to FormQuestion list (with nested followUp support)
        questions = [_convert_missing_param_to_form_question(p) for p in missing]

        msg = "Please provide the following information:"
        _record_assistant_message(session, store, msg)

        return OrchestrateResponse(
            sessionId=session.id,
            type="form",
            content=FormContent(toolName=tool_name, toolArgs=tool_args, questions=questions),
            trace=trace,
        )

    if decision == "USE_TOOLS":
        tool_name = planner.toolName or ""
        tool_args = planner.toolArgs or {}

        # Validate first
        validation = validate_tool_args(tool_name, tool_args)
        if not validation.valid:
            # This shouldn't happen if planner followed rules, but handle gracefully
            error_detail = "; ".join(validation.errors)
            msg = f"I need a bit more information: {error_detail}"
            _record_assistant_message(session, store, msg)
            return OrchestrateResponse(
                sessionId=session.id,
                type="message",
                content=MessageContent(text=msg),
                trace=trace,
            )

        # Execute tool
        return _execute_tool_and_respond(
            session, store, tool_name, validation.normalized_args or tool_args, trace
        )

    # Fallback for unknown decision types
    msg = "I'm not sure how to proceed. Could you tell me more?"
    _record_assistant_message(session, store, msg)
    return OrchestrateResponse(
        sessionId=session.id,
        type="message",
        content=MessageContent(text=msg),
        trace=trace,
    )
