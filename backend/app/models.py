from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgeRange(BaseModel):
    min: int = Field(ge=0, le=120)
    max: int = Field(ge=0, le=120)


class FindPeopleRequest(BaseModel):
    location: str = Field(min_length=1)
    genders: list[str] = Field(min_length=1)
    ageRange: AgeRange
    occupation: str = Field(min_length=1)


class FindThingsRequest(BaseModel):
    title: str = Field(min_length=1)
    neededCount: int = Field(ge=1, le=99)


class Meta(BaseModel):
    requestId: str
    generatedBy: Literal["mock", "llm"]
    model: str | None = None


class Profile(BaseModel):
    id: str
    kind: Literal["human", "ai"] = "human"
    name: str
    presence: Literal["online", "offline"]
    city: str
    headline: str
    score: int = Field(ge=0, le=100)
    badges: list[dict[str, Any]] = Field(default_factory=list)
    about: list[str] = Field(default_factory=list)
    matchReasons: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    healingReasons: list[str] | None = None
    aiNote: str | None = None


class GroupAvailabilityOpen(BaseModel):
    status: Literal["open"] = "open"


class GroupAvailabilityScheduled(BaseModel):
    status: Literal["scheduled"] = "scheduled"
    startAt: int


class GroupAvailabilityFull(BaseModel):
    status: Literal["full"] = "full"
    startAt: int | None = None


GroupAvailability = GroupAvailabilityOpen | GroupAvailabilityScheduled | GroupAvailabilityFull


class GroupMember(BaseModel):
    id: str
    name: str
    headline: str
    badges: list[dict[str, Any]] = Field(default_factory=list)


class Group(BaseModel):
    id: str
    title: str
    city: str
    location: str
    level: str
    availability: GroupAvailability
    memberCount: int = Field(ge=0, le=999)
    capacity: int = Field(ge=1, le=999)
    memberAvatars: list[str] = Field(default_factory=list)
    members: list[GroupMember] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FindPeopleResponse(BaseModel):
    people: list[Profile]
    meta: Meta


class FindThingsResponse(BaseModel):
    things: list[Group]
    meta: Meta


Intent = Literal[
    "unknown",
    "find_people",
    "find_things",
    "analyze_people",
    "analyze_things",
    "refine_people",
    "refine_things",
]


class FormOption(BaseModel):
    value: str
    label: str


class FormField(BaseModel):
    key: str
    label: str
    type: Literal["text", "number", "select", "multi_select", "range"]
    required: bool = True
    placeholder: str | None = None
    options: list[FormOption] | None = None
    min: int | None = None
    max: int | None = None
    value: Any | None = None


class FormCard(BaseModel):
    title: str
    description: str | None = None
    fields: list[FormField]


class OrchestratorState(BaseModel):
    intent: Intent | None = None
    slots: dict[str, Any] = Field(default_factory=dict)


CardStatus = Literal["completed", "active", "upcoming"]


class Card(BaseModel):
    id: str
    title: str
    status: CardStatus
    fields: list[FormField]
    required: bool = True


class CardDeck(BaseModel):
    layout: Literal["stacked"] = "stacked"
    activeCardId: str | None = None
    cards: list[Card] = Field(default_factory=list)


class CardSubmission(BaseModel):
    cardId: str
    data: dict[str, Any] = Field(default_factory=dict)


class OrchestrateRequest(BaseModel):
    sessionId: str | None = None
    message: str | None = None
    submit: CardSubmission | None = None
    reset: bool = False


class OrchestrateResponse(BaseModel):
    requestId: str
    sessionId: str
    intent: Intent
    action: Literal["chat", "form", "results"]
    assistantMessage: str
    missingFields: list[str] = Field(default_factory=list)
    deck: CardDeck | None = None
    form: FormCard | None = None
    results: dict[str, Any] | None = None
    state: OrchestratorState
    uiBlocks: list[dict[str, Any]] | None = None
    trace: dict[str, Any] | None = None
