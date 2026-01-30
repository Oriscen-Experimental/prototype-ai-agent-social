from __future__ import annotations

import hashlib
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from .models import (
    FindPeopleRequest,
    FindPeopleResponse,
    FindThingsRequest,
    FindThingsResponse,
    Card,
    CardDeck,
    FormCard,
    FormField,
    FormOption,
    Group,
    GroupAvailabilityFull,
    GroupAvailabilityOpen,
    GroupAvailabilityScheduled,
    GroupMember,
    Meta,
    OrchestratorState,
    Profile,
)


Intent = Literal[
    "unknown",
    "find_people",
    "find_things",
    "analyze_people",
    "analyze_things",
    "refine_people",
    "refine_things",
]


def _stable_int(seed: str, low: int, high: int) -> int:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    n = int(h[:8], 16)
    return low + (n % (high - low + 1))


def _stable_choice(seed: str, items: list[str]) -> str:
    return items[_stable_int(seed, 0, len(items) - 1)]


def _uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


CITY_HINTS = [
    ("shanghai", ["上海", "Shanghai", "SH"]),
    ("beijing", ["北京", "Beijing", "BJ"]),
    ("guangzhou", ["广州", "Guangzhou", "GZ"]),
    ("shenzhen", ["深圳", "Shenzhen", "SZ"]),
    ("hangzhou", ["杭州", "Hangzhou", "HZ"]),
    ("chengdu", ["成都", "Chengdu", "CD"]),
    ("nanjing", ["南京", "Nanjing", "NJ"]),
    ("wuhan", ["武汉", "Wuhan", "WH"]),
    ("xian", ["西安", "Xi'an", "Xian"]),
    ("san francisco", ["San Francisco", "SF", "旧金山"]),
]


def _guess_city(message: str) -> str | None:
    m = _normalize_text(message)
    if not m:
        return None
    for canonical, hints in CITY_HINTS:
        for h in hints:
            if h.lower() in m.lower():
                return canonical.title()
    # light heuristic: "在X" (Chinese)
    mm = re.search(r"在([\u4e00-\u9fffA-Za-z ]{2,20})", m)
    if mm:
        raw = mm.group(1).strip()
        if raw:
            return raw
    return None


def _guess_genders(message: str) -> list[str]:
    m = _normalize_text(message).lower()
    genders: set[str] = set()
    if any(x in m for x in ["女", "女生", "female", "women", "girls"]):
        genders.add("female")
    if any(x in m for x in ["男", "男生", "male", "men", "boys"]):
        genders.add("male")
    return sorted(genders)


def _guess_age_range(message: str) -> dict[str, int] | None:
    m = _normalize_text(message)
    if not m:
        return None

    # 25-32岁 / 25到32岁 / 25~32
    mm = re.search(r"(\d{1,2})\s*(?:-|~|到|至)\s*(\d{1,2})\s*岁?", m)
    if mm:
        a, b = int(mm.group(1)), int(mm.group(2))
        lo, hi = min(a, b), max(a, b)
        if 0 <= lo <= 120 and 0 <= hi <= 120 and lo <= hi:
            return {"min": lo, "max": hi}

    # 单个年龄：30岁
    mm = re.search(r"(\d{1,2})\s*岁", m)
    if mm:
        a = int(mm.group(1))
        if 0 <= a <= 120:
            return {"min": max(0, a - 2), "max": min(120, a + 2)}

    # 20多 / 30多
    mm = re.search(r"(\d)0\s*多", m)
    if mm:
        decade = int(mm.group(1)) * 10
        return {"min": decade, "max": min(120, decade + 9)}

    return None


OCCUPATION_HINTS = [
    ("Software Engineer", ["程序员", "工程师", "developer", "software", "swe"]),
    ("Product Manager", ["产品", "pm", "product manager"]),
    ("Designer", ["设计", "designer"]),
    ("Teacher", ["老师", "teacher"]),
    ("Doctor", ["医生", "doctor"]),
    ("Lawyer", ["律师", "lawyer"]),
    ("Student", ["学生", "student"]),
    ("Sales", ["销售", "sales"]),
    ("Marketing", ["运营", "market", "marketing"]),
]


def _guess_occupation(message: str) -> str | None:
    m = _normalize_text(message).lower()
    if not m:
        return None
    for occ, hints in OCCUPATION_HINTS:
        if any(h in m for h in hints):
            return occ
    return None


ACTIVITY_HINTS = [
    ("Hiking", ["爬山", "hiking", "徒步"]),
    ("Drinks", ["喝酒", "bar", "drink", "cocktail", "beer"]),
    ("Tennis", ["网球", "tennis"]),
    ("Board Games", ["桌游", "board game"]),
    ("Mafia/Werewolf", ["狼人杀", "mafia", "werewolf"]),
    ("Coffee", ["咖啡", "coffee"]),
    ("Movies", ["电影", "movie", "cinema"]),
    ("Running", ["跑步", "running"]),
]


def _guess_thing_title(message: str) -> str | None:
    m = _normalize_text(message)
    if not m:
        return None

    for title, hints in ACTIVITY_HINTS:
        if any(h.lower() in m.lower() for h in hints):
            return title

    # "一起xxx" take short tail as title
    mm = re.search(r"一起([\u4e00-\u9fffA-Za-z ]{2,20})", m)
    if mm:
        raw = mm.group(1).strip()
        if raw:
            return raw
    return None


def _guess_needed_count(message: str) -> int | None:
    m = _normalize_text(message)
    if not m:
        return None
    mm = re.search(r"缺\s*(\d{1,2})\s*个?\s*人", m)
    if mm:
        return max(1, min(99, int(mm.group(1))))
    mm = re.search(r"需要\s*(\d{1,2})\s*个?\s*人", m)
    if mm:
        return max(1, min(99, int(mm.group(1))))
    mm = re.search(r"(\d{1,2})\s*个?\s*人(?!.*岁)", m)
    if mm and ("缺" in m or "招" in m or "组" in m):
        return max(1, min(99, int(mm.group(1))))
    return None


def route_intent(message: str) -> Intent:
    m = _normalize_text(message).lower()
    if not m:
        return "unknown"

    if re.search(r"缺\s*\d+\s*个?\s*人", m) or "缺人" in m:
        return "find_things"

    if any(k in m for k in ["找人", "认识", "交友", "找对象", "找朋友", "搭子", "buddy"]):
        return "find_people"

    if any(k in m for k in ["找事", "组队", "组局", "活动", "招募", "拼桌", "报名"]):
        return "find_things"

    # fallback: if message mentions gender/age strongly, lean people
    if _guess_genders(m) or _guess_age_range(m):
        return "find_people"

    return "unknown"


def _merge_slots(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for k, v in (incoming or {}).items():
        if v is None:
            continue
        merged[k] = v
    return merged


@dataclass(frozen=True)
class RoutingResult:
    intent: Intent
    slots: dict[str, Any]
    missing: list[str]
    assistant_message: str
    form: FormCard | None


def _missing_people(slots: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not (slots.get("location") or "").strip():
        missing.append("location")
    genders = slots.get("genders")
    if not isinstance(genders, list) or not genders:
        missing.append("genders")
    age_range = slots.get("ageRange")
    if not isinstance(age_range, dict) or not isinstance(age_range.get("min"), int) or not isinstance(age_range.get("max"), int):
        missing.append("ageRange")
    # Occupation is treated as required for this prototype flow.
    if not (slots.get("occupation") or "").strip():
        missing.append("occupation")
    return missing


def _missing_things(slots: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not (slots.get("title") or "").strip():
        missing.append("title")
    needed = slots.get("neededCount")
    if not isinstance(needed, int) or not (1 <= needed <= 99):
        missing.append("neededCount")
    return missing


def build_deck(intent: Intent, slots: dict[str, Any]) -> tuple[CardDeck | None, list[str]]:
    if intent not in {"find_people", "find_things"}:
        return None, []

    cards: list[Card] = []
    missing = _missing_people(slots) if intent == "find_people" else _missing_things(slots)

    def is_completed(field_key: str) -> bool:
        if field_key == "location":
            return bool((slots.get("location") or "").strip())
        if field_key == "genders":
            v = slots.get("genders")
            return isinstance(v, list) and len(v) > 0
        if field_key == "ageRange":
            v = slots.get("ageRange")
            return isinstance(v, dict) and isinstance(v.get("min"), int) and isinstance(v.get("max"), int)
        if field_key == "occupation":
            return bool((slots.get("occupation") or "").strip())
        if field_key == "title":
            return bool((slots.get("title") or "").strip())
        if field_key == "neededCount":
            v = slots.get("neededCount")
            return isinstance(v, int) and (1 <= v <= 99)
        return False

    def status_for(field_key: str, active_key: str | None) -> Literal["completed", "active", "upcoming"]:
        if is_completed(field_key):
            return "completed"
        if active_key == field_key:
            return "active"
        return "upcoming"

    # active is first missing required field
    active_key: str | None = missing[0] if missing else None

    if intent == "find_people":
        cards.append(
            Card(
                id="location",
                title="Location",
                status=status_for("location", active_key),
                fields=[
                    FormField(
                        key="location",
                        label="Location",
                        type="text",
                        required=True,
                        placeholder="e.g., Shanghai / Beijing / San Francisco",
                        value=slots.get("location"),
                    )
                ],
                required=True,
            )
        )
        cards.append(
            Card(
                id="genders",
                title="Gender (multi-select)",
                status=status_for("genders", active_key),
                fields=[
                    FormField(
                        key="genders",
                        label="Gender (multi-select)",
                        type="multi_select",
                        required=True,
                        options=[
                            FormOption(value="female", label="Female"),
                            FormOption(value="male", label="Male"),
                            FormOption(value="any", label="Any"),
                        ],
                        value=slots.get("genders"),
                    )
                ],
                required=True,
            )
        )
        cards.append(
            Card(
                id="ageRange",
                title="Age Range",
                status=status_for("ageRange", active_key),
                fields=[
                    FormField(
                        key="ageRange",
                        label="Age Range",
                        type="range",
                        required=True,
                        min=18,
                        max=60,
                        value=slots.get("ageRange"),
                    )
                ],
                required=True,
            )
        )
        # optional card: occupation
        cards.append(
            Card(
                id="occupation",
                title="Occupation",
                status=status_for("occupation", active_key),
                fields=[
                    FormField(
                        key="occupation",
                        label="Occupation",
                        type="text",
                        required=True,
                        placeholder="e.g., Designer / Engineer / Product Manager (or 'Any')",
                        value=slots.get("occupation"),
                    )
                ],
                required=True,
            )
        )

    if intent == "find_things":
        cards.append(
            Card(
                id="title",
                title="Activity / What you want to do",
                status=status_for("title", active_key),
                fields=[
                    FormField(
                        key="title",
                        label="Activity / What you want to do",
                        type="text",
                        required=True,
                        placeholder="e.g., Weekend hiking / Board games / Tennis practice",
                        value=slots.get("title"),
                    )
                ],
                required=True,
            )
        )
        cards.append(
            Card(
                id="neededCount",
                title="How many people needed",
                status=status_for("neededCount", active_key),
                fields=[
                    FormField(
                        key="neededCount",
                        label="How many people needed",
                        type="number",
                        required=True,
                        min=1,
                        max=20,
                        value=slots.get("neededCount"),
                    )
                ],
                required=True,
            )
        )

    active_card_id = None
    for c in cards:
        if c.status == "active":
            active_card_id = c.id
            break

    return CardDeck(activeCardId=active_card_id, cards=cards), missing


def _build_people_form(slots: dict[str, Any], missing: list[str]) -> FormCard:
    fields: list[FormField] = []
    if "location" in missing:
        fields.append(
            FormField(
                key="location",
                label="Location",
                type="text",
                required=True,
                placeholder="e.g., Shanghai / Beijing / San Francisco",
                value=slots.get("location"),
            )
        )
    if "genders" in missing:
        fields.append(
            FormField(
                key="genders",
                label="Gender (multi-select)",
                type="multi_select",
                required=True,
                options=[
                    FormOption(value="female", label="Female"),
                    FormOption(value="male", label="Male"),
                    FormOption(value="any", label="Any"),
                ],
                value=slots.get("genders"),
            )
        )
    if "ageRange" in missing:
        fields.append(
            FormField(
                key="ageRange",
                label="Age Range",
                type="range",
                required=True,
                min=18,
                max=60,
                value=slots.get("ageRange"),
            )
        )
    # always expose optional occupation
    fields.append(
        FormField(
            key="occupation",
            label="Occupation (optional)",
            type="text",
            required=False,
            placeholder="e.g., Designer / Engineer / Product Manager",
            value=slots.get("occupation"),
        )
    )
    return FormCard(
        title="Complete your search criteria",
        description="After completing the form, I'll generate mock matching candidates for you.",
        fields=fields,
    )


def _build_things_form(slots: dict[str, Any], missing: list[str]) -> FormCard:
    fields: list[FormField] = []
    if "title" in missing:
        fields.append(
            FormField(
                key="title",
                label="Activity / What you want to do",
                type="text",
                required=True,
                placeholder="e.g., Weekend hiking / Board games / Tennis practice",
                value=slots.get("title"),
            )
        )
    if "neededCount" in missing:
        fields.append(
            FormField(
                key="neededCount",
                label="How many people needed",
                type="number",
                required=True,
                min=1,
                max=20,
                value=slots.get("neededCount"),
            )
        )
    return FormCard(
        title="Complete your activity details",
        description="After completing the form, I'll generate mock activities/groups you can join or create.",
        fields=fields,
    )


def orchestrate(message: str | None, state: OrchestratorState | None, form_data: dict[str, Any]) -> RoutingResult:
    message = _normalize_text(message or "")
    prev_state = state or OrchestratorState(intent=None, slots={})

    # Merge form inputs first (explicit > inferred)
    slots = _merge_slots(prev_state.slots, form_data)

    intent: Intent
    if prev_state.intent and prev_state.intent != "unknown":
        intent = prev_state.intent
    else:
        intent = route_intent(message)

    if intent == "find_people":
        inferred = {
            "location": _guess_city(message),
            "genders": _guess_genders(message) or None,
            "ageRange": _guess_age_range(message),
            "occupation": _guess_occupation(message),
        }
        slots = _merge_slots(slots, inferred)
        missing = _missing_people(slots)
        if missing:
            assistant_message = "I can help you find people (mock). Please complete the following information:"
            return RoutingResult(
                intent=intent,
                slots=slots,
                missing=missing,
                assistant_message=assistant_message,
                form=_build_people_form(slots, missing),
            )
        assistant_message = "Got it, I'll generate some matching candidates based on your criteria (mock)."
        return RoutingResult(intent=intent, slots=slots, missing=[], assistant_message=assistant_message, form=None)

    if intent == "find_things":
        inferred = {
            "title": _guess_thing_title(message),
            "neededCount": _guess_needed_count(message),
        }
        slots = _merge_slots(slots, inferred)
        missing = _missing_things(slots)
        if missing:
            assistant_message = "I can help you find activities/groups (mock). Please complete the following information:"
            return RoutingResult(
                intent=intent,
                slots=slots,
                missing=missing,
                assistant_message=assistant_message,
                form=_build_things_form(slots, missing),
            )
        assistant_message = "Got it, I'll generate some activity/group suggestions based on your details (mock)."
        return RoutingResult(intent=intent, slots=slots, missing=[], assistant_message=assistant_message, form=None)

    # unknown → chat to clarify
    assistant_message = (
        "I'm listening.\n"
        "Let's take it slow: do you want to be understood/accompanied, or take a specific social action right away?\n"
        "Tell me two things:\n"
        "1) What do you most want to solve right now (loneliness, boredom, need a buddy, want to meet certain people, or organize an activity)?\n"
        "2) Do you prefer chatting online or meeting offline? (You can also mention a city)\n"
        "I'll help you narrow it down to: find people / find activities."
    )
    return RoutingResult(intent="unknown", slots=slots, missing=[], assistant_message=assistant_message, form=None)


def companion_reply(message: str | None, step: int) -> str:
    m = _normalize_text(message or "")
    ml = m.lower()

    def has_any(keys: list[str]) -> bool:
        return any(k in m for k in keys) or any(k in ml for k in keys)

    mood = None
    if has_any(["sad", "lonely", "anxious", "depressed", "stressed", "overwhelmed", "emo"]):
        mood = "heavy"
    if has_any(["bored", "boring", "nothing to do"]):
        mood = "bored"

    if step <= 0:
        if mood == "heavy":
            return (
                "Sounds like you're going through a tough time. I'm here.\n"
                "Let's not rush to 'solve the problem'. Would you like to share: what was the most painful moment or thought just now?\n"
                "Also, let me know if you'd prefer: someone to listen, or to take a concrete social action (meet people/join activities)."
            )
        if mood == "bored":
            return (
                "I get it, feeling bored or empty can make things feel even emptier.\n"
                "What would you prefer: meeting someone to do something together, or directly joining/organizing an activity?\n"
                "Just give me a direction, and I'll help turn it into an actionable next step."
            )
        return (
            "I'm listening.\n"
            "First, tell me: do you need someone to talk to/be understood, or do you want to take a concrete social action?\n"
            "You don't have to be complete, just say anything."
        )

    if step == 1:
        return (
            "Thanks for sharing.\n"
            "To make sure I don't lead you astray, which one are you closer to:\n"
            "A) Find people: you want to meet/connect with a specific person (more like 'buddy/friend/date')\n"
            "B) Find activities: you want to join/organize an activity (more like 'group/team/looking for members')\n"
            "Just reply 'A' or 'B', and mention your city / whether you prefer online or offline."
        )

    if step == 2:
        return (
            "OK, let's break it down into a small next step.\n"
            "Which would you prefer to start with?\n"
            "1) Chat with someone for 10 minutes (online) to see if you click\n"
            "2) Meet offline directly (low pressure: coffee/walk/light exercise)\n"
            "3) Join an existing activity/group (easier)\n"
            "Pick a number, and I'll ask 1-2 more questions to give you (mock) results."
        )

    return (
        "Let's take it slow.\n"
        "Tell me: do you want to 'find people' or 'find activities'? If you're not sure, describe your ideal scenario (where, with whom, doing what)."
    )


def generate_people(req: FindPeopleRequest, request_id: str, generated_by: Literal["mock", "llm"] = "mock") -> FindPeopleResponse:
    seed_base = f"people|{req.location}|{','.join(req.genders)}|{req.ageRange.min}-{req.ageRange.max}|{req.occupation or ''}"
    first_names = ["Alex", "Sam", "Lena", "Kai", "Mina", "Chris", "Nora", "Jules", "Zoe", "Ethan"]
    headlines = [
        "Chill vibes—down for a low-pressure hang",
        "Likes deep talks + good coffee",
        "Active on weekends—hikes, tennis, or long walks",
        "New in town—looking to make real friends",
        "Sincere and direct—no ghosting",
    ]
    topics = ["Music", "Movies", "Coffee", "Fitness", "Travel", "Board games", "AI/Tech", "Photography"]
    badges = [
        {"id": "photo", "label": "Photo Verified", "description": "Completed a photo/liveness check (mock)."},
        {"id": "linkedin", "label": "LinkedIn Verified", "description": "LinkedIn connected (mock)."},
        {"id": "id", "label": "ID Verified", "description": "Basic identity verification (mock)."},
    ]

    people: list[Profile] = []
    for i in range(5):
        pid = _uuid(f"{seed_base}|{i}")
        name = _stable_choice(f"{seed_base}|name|{i}", first_names)
        presence = "online" if _stable_int(f"{seed_base}|presence|{i}", 0, 1) == 0 else "offline"
        age = _stable_int(f"{seed_base}|age|{i}", req.ageRange.min, req.ageRange.max)
        occ = req.occupation or _stable_choice(f"{seed_base}|occ|{i}", [o for o, _ in OCCUPATION_HINTS])
        headline = f"{_stable_choice(f'{seed_base}|hl|{i}', headlines)} · {occ} · {age}"
        score = _stable_int(f"{seed_base}|score|{i}", 72, 95)
        people.append(
            Profile(
                id=pid,
                kind="human",
                name=name,
                presence=presence,
                city=req.location,
                headline=headline,
                score=score,
                badges=[
                    badges[_stable_int(f"{seed_base}|badge|{i}", 0, len(badges) - 1)],
                    badges[_stable_int(f"{seed_base}|badge2|{i}", 0, len(badges) - 1)],
                ],
                about=[
                    f"Looking for: {', '.join(req.genders)} (mock preference)",
                    f"Usually around {req.location}",
                    "Happy to start with a quick chat first",
                ],
                matchReasons=[
                    f"Location match: {req.location}",
                    f"Age range fit: {req.ageRange.min}-{req.ageRange.max}",
                    f"Shared vibe with your request (mock)",
                ],
                topics=[
                    _stable_choice(f"{seed_base}|t0|{i}", topics),
                    _stable_choice(f"{seed_base}|t1|{i}", topics),
                    _stable_choice(f"{seed_base}|t2|{i}", topics),
                ],
            )
        )

    return FindPeopleResponse(
        people=people,
        meta=Meta(
            requestId=request_id,
            generatedBy=generated_by,
            model=None,
        ),
    )


def generate_things(req: FindThingsRequest, request_id: str, generated_by: Literal["mock", "llm"] = "mock") -> FindThingsResponse:
    seed_base = f"things|{req.title}|{req.neededCount}"
    cities = ["Shanghai", "Beijing", "Hangzhou", "Shenzhen", "San Francisco"]
    levels = [
        "Beginner-friendly · no pressure · good vibes",
        "Intermediate · structured · clear rules",
        "Advanced · fast-paced · competitive but kind",
    ]
    locations = ["Downtown (mock)", "Near a metro station (mock)", "Cafe meetup spot (mock)", "Park entrance (mock)"]
    names = ["Ava", "Ben", "Cici", "Dio", "Elle", "Finn", "Gus", "Hana", "Ian", "Juno"]

    now = int(time.time() * 1000)
    things: list[Group] = []
    for i in range(5):
        gid = _uuid(f"{seed_base}|{i}")
        city = _stable_choice(f"{seed_base}|city|{i}", cities)
        capacity = max(req.neededCount + 2, _stable_int(f"{seed_base}|cap|{i}", req.neededCount + 2, req.neededCount + 8))
        member_count = max(0, capacity - req.neededCount)

        availability_seed = _stable_int(f"{seed_base}|avail|{i}", 0, 2)
        if availability_seed == 0:
            availability = GroupAvailabilityOpen()
        elif availability_seed == 1:
            start_at = now + _stable_int(f"{seed_base}|start|{i}", 1, 72) * 60 * 60 * 1000
            availability = GroupAvailabilityScheduled(startAt=start_at)
        else:
            start_at = now + _stable_int(f"{seed_base}|start|{i}", 1, 72) * 60 * 60 * 1000
            availability = GroupAvailabilityFull(startAt=start_at)

        members: list[GroupMember] = []
        member_avatars: list[str] = []
        for j in range(min(member_count, 10)):
            nm = _stable_choice(f"{seed_base}|m|{i}|{j}", names)
            members.append(
                GroupMember(
                    id=_uuid(f"{seed_base}|m|{i}|{j}"),
                    name=nm,
                    headline=_stable_choice(f"{seed_base}|mh|{i}|{j}", ["Friendly", "On time", "Good communicator", "Newbie-friendly"]),
                    badges=[],
                )
            )
            member_avatars.append(nm[:1].upper())

        things.append(
            Group(
                id=gid,
                title=f"{city} · {req.title} · need {req.neededCount} more (mock)",
                city=city,
                location=_stable_choice(f"{seed_base}|loc|{i}", locations),
                level=_stable_choice(f"{seed_base}|lvl|{i}", levels),
                availability=availability,
                memberCount=member_count,
                capacity=capacity,
                memberAvatars=member_avatars,
                members=members,
                notes=[
                    "This is a prototype result (mock)",
                    "Join/RSVP is not implemented",
                ],
            )
        )

    return FindThingsResponse(
        things=things,
        meta=Meta(
            requestId=request_id,
            generatedBy=generated_by,
            model=None,
        ),
    )
