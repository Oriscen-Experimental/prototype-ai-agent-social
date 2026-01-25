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

_CITY_HINTS = [
    ("Shanghai", ["上海", "shanghai", "sh"]),
    ("Beijing", ["北京", "beijing", "bj"]),
    ("Guangzhou", ["广州", "guangzhou", "gz"]),
    ("Shenzhen", ["深圳", "shenzhen", "sz"]),
    ("Hangzhou", ["杭州", "hangzhou", "hz"]),
    ("Chengdu", ["成都", "chengdu", "cd"]),
    ("Nanjing", ["南京", "nanjing", "nj"]),
    ("Wuhan", ["武汉", "wuhan", "wh"]),
    ("Xi'an", ["西安", "xian", "xi'an"]),
]


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

    def guess_weekend_time_range(text: str) -> dict[str, str] | None:
        t = (text or "").strip().lower()
        if not t:
            return None
        if ("周末" not in t) and ("this weekend" not in t) and ("weekend" not in t):
            return None
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        # Find next Saturday (weekday: Mon=0 ... Sun=6)
        days_ahead = (5 - now.weekday()) % 7
        if days_ahead == 0:
            # It's Saturday; consider "this weekend" as today+tomorrow.
            start_day = now
        else:
            start_day = now + timedelta(days=days_ahead)
        start = start_day.replace(hour=10, minute=0, second=0, microsecond=0)
        end = (start + timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
        return {"start": start.isoformat().replace("+00:00", "Z"), "end": end.isoformat().replace("+00:00", "Z")}

    def guess_city(text: str) -> str | None:
        t = (text or "").strip()
        tl = t.lower()
        for canonical, hints in _CITY_HINTS:
            if any(h in t for h in hints) or any(h in tl for h in hints):
                return canonical
        return None

    def guess_online(text: str) -> bool | None:
        t = (text or "").strip().lower()
        if any(x in t for x in ["线上", "online", "remote", "virtual", "视频", "语音"]):
            return True
        if any(x in t for x in ["线下", "同城", "附近", "meetup", "offline"]):
            return False
        return None

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

    city = guess_city(m)
    is_online = guess_online(m)

    tool_args: dict[str, Any] = {
        "domain": domain,
        "semantic_query": m,
        "structured_filters": {
            "location": {
                "city": city,
                "region": None,
                "is_online": is_online,
            }
        },
        "sort_strategy": "relevance",
        "limit": 5,
    }

    # Domain-specific nested filters (optional).
    if domain == "person":
        # Business default is wide; planner can refine later.
        tool_args["structured_filters"]["person_filters"] = {
            "age_range": None,
            "gender": None,
            "industry": None,
            "role": None,
            "intent_tags": None,
        }
    else:
        tool_args["structured_filters"]["event_filters"] = {
            "time_range": guess_weekend_time_range(m),
            "price_range": None,
            "category": None,
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
    visible_context: list[dict[str, Any]] | None = None,
    user_profile: dict[str, Any] | None = None,
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
                visible_context=visible_context,
                user_profile=user_profile,
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
