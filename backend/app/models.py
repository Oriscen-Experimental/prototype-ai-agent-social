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


class FormQuestion(BaseModel):
    """A question to collect missing parameter from user."""
    param: str  # Parameter name in tool schema
    question: str  # Question text
    options: list[dict[str, Any]] = Field(default_factory=list)  # [{label: str, value: Any}]


class MessageContent(BaseModel):
    """Content for type=message responses."""
    text: str


class ResultsContent(BaseModel):
    """Content for type=results responses."""
    results: dict[str, Any]  # {people?: Profile[], things?: Group[]}
    summary: str | None = None  # Brief description of results


class FormContent(BaseModel):
    """Content for type=form responses."""
    toolName: str
    toolArgs: dict[str, Any] = Field(default_factory=dict)  # Already collected params
    questions: list[FormQuestion]


class OrchestrateResponse(BaseModel):
    """Orchestrator response.

    UI renders based on `type`:
    - message: Show text message
    - results: Show people/things results
    - form: Show form to collect missing params
    """
    sessionId: str
    type: Literal["message", "results", "form"]
    content: MessageContent | ResultsContent | FormContent
    trace: dict[str, Any] | None = None


class FormSubmission(BaseModel):
    """User's submission for a form (MISSING_INFO flow)."""
    toolName: str
    toolArgs: dict[str, Any]  # Previously collected args
    answers: dict[str, Any]  # User's answers: {param: value}


class OrchestrateRequest(BaseModel):
    """Orchestrator request."""
    sessionId: str | None = None
    message: str | None = None  # User's text message
    formSubmission: FormSubmission | None = None  # Form answers for MISSING_INFO
    reset: bool = False
