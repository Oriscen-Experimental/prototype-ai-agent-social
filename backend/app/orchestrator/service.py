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
    UIBlock,
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


def _fetch_profiles_from_history(session, ids: list[str]) -> list[dict[str, Any]]:
    """Fetch profiles from session history by IDs."""
    last_results = session.meta.get("last_results", {})
    if not isinstance(last_results, dict):
        return []

    # Handle both formats: {"people": [...]} and {"type": "people", "items": [...]}
    if last_results.get("type") == "people":
        people = last_results.get("items", [])
    else:
        people = last_results.get("people", [])

    if not isinstance(people, list):
        return []
    return [p for p in people if isinstance(p, dict) and p.get("id") in ids]


def _fetch_groups_from_history(session, ids: list[str]) -> list[dict[str, Any]]:
    """Fetch groups from session history by IDs."""
    last_results = session.meta.get("last_results", {})
    if not isinstance(last_results, dict):
        return []

    # Handle both formats: {"things": [...]} and {"type": "things", "items": [...]}
    if last_results.get("type") == "things":
        things = last_results.get("items", [])
    else:
        things = last_results.get("things", [])

    if not isinstance(things, list):
        return []
    return [g for g in things if isinstance(g, dict) and g.get("id") in ids]


def _resolve_blocks(
    raw_blocks: list[dict[str, Any]] | None,
    session,
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
) -> list[UIBlock]:
    """Resolve planner blocks (with IDs) to full UIBlocks (with data)."""
    if not raw_blocks:
        return []

    resolved: list[UIBlock] = []
    for b in raw_blocks:
        if not isinstance(b, dict):
            continue

        block_type = b.get("type")

        if block_type == "text":
            text = b.get("text", "")
            if text:
                resolved.append(UIBlock(type="text", text=text))

        elif block_type == "profiles":
            ids = b.get("ids", [])
            if isinstance(ids, list) and ids:
                profiles = _fetch_profiles_from_history(session, ids)
                if profiles:
                    resolved.append(UIBlock(
                        type="profiles",
                        profiles=profiles,
                        layout=b.get("layout", "compact"),
                    ))

        elif block_type == "groups":
            ids = b.get("ids", [])
            if isinstance(ids, list) and ids:
                groups = _fetch_groups_from_history(session, ids)
                if groups:
                    resolved.append(UIBlock(
                        type="groups",
                        groups=groups,
                        layout=b.get("layout", "compact"),
                    ))

        elif block_type == "form":
            questions_raw = b.get("questions", [])
            if isinstance(questions_raw, list):
                # Convert to FormQuestion objects
                questions = []
                for q in questions_raw:
                    if isinstance(q, dict):
                        param = q.get("param", "")
                        question_text = q.get("question", "")
                        if not question_text:
                            logger.warning(f"Form question missing 'question' field for param={param}")
                            continue  # Skip invalid question
                        questions.append(FormQuestion(
                            param=param,
                            question=question_text,
                            options=[
                                FormQuestionOption(
                                    label=opt.get("label", ""),
                                    value=opt.get("value"),
                                    followUp=None,  # TODO: handle nested followUp
                                )
                                for opt in q.get("options", [])
                                if isinstance(opt, dict)
                            ],
                        ))
                if questions:
                    resolved.append(UIBlock(
                        type="form",
                        form=FormContent(
                            toolName=tool_name or "",
                            toolArgs=tool_args or {},
                            questions=questions,
                        ),
                    ))

    return resolved


def _build_blocks_from_tool_result(
    result_type: str,
    payload: dict[str, Any],
) -> list[UIBlock]:
    """Build UI blocks from tool execution result."""
    blocks: list[UIBlock] = []

    # Add summary text if present
    summary = (payload.get("assistantMessage") or "").strip()
    if summary:
        blocks.append(UIBlock(type="text", text=summary))

    # Add result cards
    if result_type == "people" and payload.get("people"):
        blocks.append(UIBlock(
            type="profiles",
            profiles=payload["people"],
            layout="compact",
        ))
    elif result_type == "things" and payload.get("things"):
        blocks.append(UIBlock(
            type="groups",
            groups=payload["things"],
            layout="compact",
        ))

    return blocks


def _extract_text_from_blocks(blocks: list[UIBlock]) -> str:
    """Extract text content from blocks for recording in history."""
    texts = [b.text for b in blocks if b.type == "text" and b.text]
    return " ".join(texts) if texts else ""


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
        error_msg = f"Sorry, I encountered an error: unknown tool '{tool_name}'."
        _record_assistant_message(session, store, error_msg)
        return OrchestrateResponse(
            sessionId=session.id,
            blocks=[UIBlock(type="text", text=error_msg)],
            # Legacy fields for backward compatibility
            type="message",
            content=MessageContent(text=error_msg),
            trace=trace,
        )

    try:
        result_type, payload, last_results_payload = tool.execute(session.meta, tool_args)
    except Exception as e:
        logger.exception("[orchestrate] tool_execution_failed tool=%s", tool_name)
        error_msg = "Sorry, I encountered an error while processing your request."
        _record_assistant_message(session, store, error_msg)
        return OrchestrateResponse(
            sessionId=session.id,
            blocks=[UIBlock(type="text", text=error_msg)],
            # Legacy fields for backward compatibility
            type="message",
            content=MessageContent(text=error_msg),
            trace=trace,
        )

    # Store results in session
    if isinstance(last_results_payload, dict) and last_results_payload:
        session.meta["last_results"] = last_results_payload

    # Build blocks from tool result
    blocks = _build_blocks_from_tool_result(result_type, payload)

    # Record assistant message
    summary = (payload.get("assistantMessage") or "").strip() or "Here are your results."
    _record_assistant_message(session, store, summary)

    # Record UI results for the assistant turn
    _record_ui_results_for_last_assistant_turn(
        session,
        visible_candidates(session.meta.get("last_results") if isinstance(session.meta.get("last_results"), dict) else None),
    )

    # Build legacy results content for backward compatibility
    results_data: dict[str, Any] = {}
    if result_type == "people" and payload.get("people"):
        results_data["people"] = payload["people"]
    elif result_type == "things" and payload.get("things"):
        results_data["things"] = payload["things"]

    return OrchestrateResponse(
        sessionId=session.id,
        blocks=blocks,
        # Legacy fields for backward compatibility
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
        error_msg = "Sorry, I had trouble processing that. Please try again."
        _record_assistant_message(session, store, error_msg)
        return OrchestrateResponse(
            sessionId=session.id,
            blocks=[UIBlock(type="text", text=error_msg)],
            type="message",
            content=MessageContent(text=error_msg),
            trace=trace,
        )

    trace["plannerOutput"] = planner.model_dump()

    # Handle each decision type
    decision = planner.decision

    # Helper to build response with blocks
    def _build_message_response(default_msg: str) -> OrchestrateResponse:
        """Build response for message-only decisions."""
        # Use planner blocks if provided, otherwise use message
        if planner.blocks:
            blocks = _resolve_blocks(planner.blocks, session)
            msg = _extract_text_from_blocks(blocks) or default_msg
        else:
            msg = planner.message or default_msg
            blocks = [UIBlock(type="text", text=msg)]

        _record_assistant_message(session, store, msg)
        return OrchestrateResponse(
            sessionId=session.id,
            blocks=blocks,
            type="message",
            content=MessageContent(text=msg),
            trace=trace,
        )

    if decision == "SHOULD_NOT_ANSWER":
        return _build_message_response("I'm sorry, I can't help with that request.")

    if decision == "DO_NOT_KNOW_HOW":
        return _build_message_response("I understand what you want, but I'm not able to help with that.")

    if decision == "SOCIAL_GUIDANCE":
        return _build_message_response("Tell me more about what's on your mind.")

    if decision == "CHITCHAT":
        return _build_message_response("That's interesting!")

    if decision == "CONTEXT_SUFFICIENT":
        # This is the key case: planner can include profile/group cards
        if planner.blocks:
            blocks = _resolve_blocks(planner.blocks, session)
            msg = _extract_text_from_blocks(blocks) or "Based on the information we have..."
        else:
            msg = planner.message or "Based on the information we have..."
            blocks = [UIBlock(type="text", text=msg)]

        _record_assistant_message(session, store, msg)

        # Record UI results if we're showing cards
        profile_ids = []
        group_ids = []
        for b in blocks:
            if b.type == "profiles" and b.profiles:
                profile_ids.extend([p.get("id") for p in b.profiles if isinstance(p, dict) and p.get("id")])
            if b.type == "groups" and b.groups:
                group_ids.extend([g.get("id") for g in b.groups if isinstance(g, dict) and g.get("id")])

        if profile_ids or group_ids:
            _record_ui_results_for_last_assistant_turn(
                session,
                visible_candidates(session.meta.get("last_results") if isinstance(session.meta.get("last_results"), dict) else None),
            )

        return OrchestrateResponse(
            sessionId=session.id,
            blocks=blocks,
            type="message",
            content=MessageContent(text=msg),
            trace=trace,
        )

    if decision == "MISSING_INFO":
        tool_name = planner.toolName or ""
        tool_args = planner.toolArgs or {}

        # Use planner blocks if provided, otherwise build from missingParams
        if planner.blocks:
            blocks = _resolve_blocks(planner.blocks, session, tool_name, tool_args)
            msg = _extract_text_from_blocks(blocks) or "Please provide the following information:"
        else:
            # Legacy: use missingParams
            missing = planner.missingParams or []
            questions = [_convert_missing_param_to_form_question(p) for p in missing]
            msg = "Please provide the following information:"
            blocks = [
                UIBlock(type="text", text=msg),
                UIBlock(type="form", form=FormContent(toolName=tool_name, toolArgs=tool_args, questions=questions)),
            ]

        _record_assistant_message(session, store, msg)

        # Extract form content for legacy response
        form_content = None
        for b in blocks:
            if b.type == "form" and b.form:
                form_content = b.form
                break

        if form_content is None:
            # Fallback: build from missingParams
            missing = planner.missingParams or []
            questions = [_convert_missing_param_to_form_question(p) for p in missing]
            form_content = FormContent(toolName=tool_name, toolArgs=tool_args, questions=questions)

        return OrchestrateResponse(
            sessionId=session.id,
            blocks=blocks,
            type="form",
            content=form_content,
            trace=trace,
        )

    if decision == "USE_TOOLS":
        tool_name = planner.toolName or ""
        tool_args = planner.toolArgs or {}

        # Validate first
        validation = validate_tool_args(tool_name, tool_args)
        if not validation.valid:
            error_detail = "; ".join(validation.errors)
            msg = f"I need a bit more information: {error_detail}"
            _record_assistant_message(session, store, msg)
            return OrchestrateResponse(
                sessionId=session.id,
                blocks=[UIBlock(type="text", text=msg)],
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
        blocks=[UIBlock(type="text", text=msg)],
        type="message",
        content=MessageContent(text=msg),
        trace=trace,
    )
