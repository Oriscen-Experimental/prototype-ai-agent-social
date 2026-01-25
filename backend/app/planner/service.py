from __future__ import annotations

from typing import Any

from ..llm import LLMPlannerDecision, build_planner_prompt, call_gemini_json


_OUT_OF_SCOPE_TOKENS = [
    "股票",
    "股价",
    "炒股",
    "基金",
    "期货",
    "crypto",
    "bitcoin",
    "eth",
    "buy",
    "sell",
    "portfolio",
    "trading",
]

_PEOPLE_TOKENS = ["找人", "认识", "交友", "找对象", "找朋友", "搭子", "buddy", "date"]
_EVENT_TOKENS = ["活动", "组局", "组队", "找事", "报名", "局", "session", "event", "activity", "group"]
_COMPARE_TOKENS = ["对比", "比较", "哪个好", "推荐哪个", "best", "compare", "which one"]


def _heuristic_planner(
    *,
    summary: str,
    history_lines: list[str],
    current_intent: str,
    current_slots: dict[str, Any],
    user_message: str,
    last_results: dict[str, Any] | None,
    focus: dict[str, Any] | None,
) -> LLMPlannerDecision:
    m = (user_message or "").strip()
    ml = m.lower()

    if any(tok in m for tok in _OUT_OF_SCOPE_TOKENS) or any(tok in ml for tok in _OUT_OF_SCOPE_TOKENS):
        return LLMPlannerDecision(
            decision="refuse",
            code="OUT_OF_SCOPE",
            intent="unknown",
            slots={},
            phase="discover",
            assistantMessage="I can’t help with finance/stock picking. If you want, tell me what kind of social connection you’re looking for (a person to talk to, or an activity to join).",
        )

    # If user is likely asking about shown results, try deep analysis.
    if isinstance(last_results, dict) and isinstance(last_results.get("items"), list) and last_results.get("items"):
        items = [it for it in last_results.get("items") if isinstance(it, dict)]
        if items and (focus is not None or any(tok in m for tok in _COMPARE_TOKENS) or any(tok in ml for tok in _COMPARE_TOKENS)):
            ids: list[str] = []
            if focus is not None:
                # Focus payload is {type,label} from orchestrator; use first item when narrowed.
                fid = items[0].get("id")
                if isinstance(fid, str) and fid:
                    ids = [fid]
            if not ids:
                for it in items[:2]:
                    iid = it.get("id")
                    if isinstance(iid, str) and iid:
                        ids.append(iid)
            mode = "compare" if len(ids) >= 2 else "detail"
            intent = "find_things" if last_results.get("type") == "things" else "find_people"
            return LLMPlannerDecision(
                decision="tool_call",
                intent=intent,  # keep frontend contract
                slots={},
                toolName="deep_profile_analysis",
                toolArgs={"target_ids": ids, "analysis_mode": mode, "focus_aspects": []},
                phase="answer",
                assistantMessage="Got it — I’ll analyze the candidates you’re referring to.",
            )

    # Companion mode for emotions / vague chat.
    if any(tok in m for tok in ["孤独", "难过", "心情", "压力", "emo", "lonely", "sad", "anxious"]) or any(
        tok in ml for tok in ["lonely", "sad", "anxious", "burnt out", "bored"]
    ):
        return LLMPlannerDecision(
            decision="chat",
            intent="unknown",
            slots={},
            phase="discover",
            assistantMessage="I’m here with you. If you want, tell me what kind of connection would feel most helpful right now — a low-pressure chat with one person, or joining a small activity?",
        )

    domain: str | None = None
    if any(tok in m for tok in _PEOPLE_TOKENS) or any(tok in ml for tok in _PEOPLE_TOKENS):
        domain = "person"
    if any(tok in m for tok in _EVENT_TOKENS) or any(tok in ml for tok in _EVENT_TOKENS):
        domain = "event" if domain is None else domain
    # Light Chinese heuristic: contains "人" + a seeking verb -> person
    if domain is None and ("人" in m) and any(x in m for x in ["找", "认识", "想找", "约", "聊聊", "聊天"]):
        domain = "person"
    # Light Chinese heuristic: contains action nouns -> event
    if domain is None and any(x in m for x in ["一起", "周末", "活动", "局", "组队", "报名", "运动", "爬山", "桌游"]):
        domain = "event"

    if domain is None:
        return LLMPlannerDecision(
            decision="chat",
            intent="unknown",
            slots={},
            phase="discover",
            assistantMessage="What kind of social help do you want right now — meeting a specific type of person, or finding an activity/event to join? Give me one sentence and I’ll turn it into options.",
        )

    tool_args: dict[str, Any] = {
        "domain": domain,
        "semantic_query": m,
        "structured_filters": {},
        "sort_strategy": "relevance",
        "limit": 5,
    }
    intent = "find_people" if domain == "person" else "find_things"
    return LLMPlannerDecision(
        decision="tool_call",
        intent=intent,
        slots={"domain": domain, "semantic_query": m},
        toolName="intelligent_discovery",
        toolArgs=tool_args,
        phase="search",
        assistantMessage="Okay — I’ll generate a few options based on your request.",
    )


def run_planner(
    *,
    tool_schemas: list[dict[str, Any]],
    summary: str,
    history_lines: list[str],
    current_intent: str,
    current_slots: dict[str, Any],
    user_message: str,
    last_results: dict[str, Any] | None,
    focus: dict[str, Any] | None,
    result_labels: list[str],
) -> LLMPlannerDecision:
    try:
        return call_gemini_json(
            prompt=build_planner_prompt(
                tool_schemas=tool_schemas,
                summary=summary,
                history_lines=history_lines,
                current_intent=current_intent,
                current_slots=current_slots,
                user_message=user_message,
                last_results=last_results,
                focus=focus,
                result_labels=result_labels,
            ),
            response_model=LLMPlannerDecision,
        )
    except Exception:
        return _heuristic_planner(
            summary=summary,
            history_lines=history_lines,
            current_intent=current_intent,
            current_slots=current_slots,
            user_message=user_message,
            last_results=last_results,
            focus=focus,
        )
