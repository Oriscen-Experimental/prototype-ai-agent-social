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


class FormQuestionOption(BaseModel):
    """An option for a form question."""
    label: str
    value: Any
    followUp: list["FormQuestion"] | None = None  # Nested questions if this option is selected


class FormQuestion(BaseModel):
    """A question to collect missing parameter from user.

    Supports tree-structured conditional questions via followUp on options.
    """
    param: str  # Parameter name in tool schema
    question: str  # Question text
    options: list[FormQuestionOption] = Field(default_factory=list)


# Enable forward references for nested structure
FormQuestion.model_rebuild()


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


class UIBlock(BaseModel):
    """A UI block for rendering.

    Block types:
    - text: {"type": "text", "text": "..."}
    - profiles: {"type": "profiles", "profiles": [...], "layout": "compact"|"full"}
    - groups: {"type": "groups", "groups": [...], "layout": "compact"|"full"}
    - form: {"type": "form", "form": {...}}
    - booking_status: {"type": "booking_status", "bookingTaskId": "...", ...}
    """
    type: Literal["text", "profiles", "groups", "form", "booking_status"]
    # For text blocks
    text: str | None = None
    # For profiles blocks
    profiles: list[Profile] | None = None
    # For groups blocks
    groups: list[Group] | None = None
    # For form blocks
    form: FormContent | None = None
    # Layout option for profiles/groups
    layout: Literal["compact", "full"] | None = None
    # For booking_status blocks
    bookingTaskId: str | None = None
    bookingStatus: str | None = None
    acceptedCount: int | None = None
    targetCount: int | None = None


class OrchestrateResponse(BaseModel):
    """Orchestrator response.

    Primary rendering uses `blocks` array.
    Legacy `type` + `content` fields maintained for backward compatibility.
    """
    sessionId: str
    # New: UI blocks array (primary)
    blocks: list[UIBlock] | None = None
    # Legacy fields (for backward compatibility)
    type: Literal["message", "results", "form"] | None = None
    content: MessageContent | ResultsContent | FormContent | None = None
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
    plannerModel: str | None = None  # "light", "medium", or "heavy"


class RoleplayChatMessage(BaseModel):
    """A message in the roleplay chat history."""
    role: Literal["user", "assistant"]
    content: str


class RoleplayChatRequest(BaseModel):
    """Request for roleplay chat."""
    profile: Profile
    messages: list[RoleplayChatMessage]


class RoleplayChatResponse(BaseModel):
    """Response from roleplay chat."""
    reply: str


# ---------------------------------------------------------------------------
# Sorting labels (onboarding)
# ---------------------------------------------------------------------------

SortingChoiceAB = Literal["A", "B"]
SortingChoiceABCD = Literal["A", "B", "C", "D"]


class SortingAnswers(BaseModel):
    restaurant: SortingChoiceAB
    travel: SortingChoiceAB
    birthday: SortingChoiceAB
    weather: SortingChoiceABCD
    noResponse: SortingChoiceABCD
    awkwardWave: SortingChoiceAB


class SortingWarningLabel(BaseModel):
    warnings: list[str] = Field(default_factory=list, max_length=8)
    bestConsumed: list[str] = Field(default_factory=list, max_length=10)
    doNot: list[str] = Field(default_factory=list, max_length=6)


class SortingNutritionFactLine(BaseModel):
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)


class SortingNutritionFacts(BaseModel):
    servingSize: str = Field(min_length=1)
    servingsPerWeek: str = Field(min_length=1)
    amountPerServing: list[SortingNutritionFactLine] = Field(default_factory=list, max_length=10)
    energyDrainPerHour: str = Field(min_length=1)
    recoveryTimeNeeded: str = Field(min_length=1)
    ingredients: str = Field(min_length=1)
    contains: str = Field(min_length=1)
    mayContain: str = Field(min_length=1)


class SortingTroubleshootingItem(BaseModel):
    issue: str = Field(min_length=1)
    fix: str = Field(min_length=1)


class SortingUserManual(BaseModel):
    modelName: str = Field(min_length=1)
    quickStart: list[str] = Field(default_factory=list, max_length=8)
    optimalOperatingConditions: list[str] = Field(default_factory=list, max_length=10)
    troubleshooting: list[SortingTroubleshootingItem] = Field(default_factory=list, max_length=10)
    warranty: str = Field(min_length=1)


class SortingLabelsRequest(BaseModel):
    name: str | None = None
    answers: SortingAnswers


class SortingLabelsResponse(BaseModel):
    noveltyScore: int = Field(ge=0, le=3)
    securityScore: int = Field(ge=0, le=3)
    archetype: Literal["Explorer", "Builder", "Artist", "Guardian"]
    warningLabel: SortingWarningLabel
    nutritionFacts: SortingNutritionFacts
    userManual: SortingUserManual


# ---------------------------------------------------------------------------
# Auth models
# ---------------------------------------------------------------------------


class GoogleAuthRequest(BaseModel):
    """Request for Google ID token verification."""
    idToken: str = Field(min_length=1)


class GoogleAuthResponse(BaseModel):
    """Response with verified user info."""
    uid: str
    email: str | None = None
    displayName: str | None = None
    photoURL: str | None = None
    needsOnboarding: bool = False


class SaveProfileRequest(BaseModel):
    """Request to save user onboarding profile."""
    name: str = Field(min_length=1)
    gender: str | None = None
    age: str | None = None
    city: str | None = None
    interests: list[str] = Field(default_factory=list)
    runningProfile: dict[str, Any] | None = None


class SaveProfileResponse(BaseModel):
    """Response after saving profile."""
    success: bool
    message: str | None = None
