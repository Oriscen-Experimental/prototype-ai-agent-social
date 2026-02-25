from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


DiscoveryDomain = Literal["person", "event"]
DiscoverySortStrategy = Literal["relevance", "distance", "time_soonest", "price_asc"]
AnalysisMode = Literal["detail", "compare", "compatibility_check"]
RefineStrategy = Literal["filter_rerank"]


class Location(BaseModel):
    city: str | None = Field(default=None, description="City name, e.g. 'Beijing', 'San Francisco'.")
    region: str | None = Field(default=None, description="District / neighborhood / business area.")
    is_online: bool | None = Field(default=None, description="Whether this is an online/virtual scenario.")

    @model_validator(mode="after")
    def _online_or_city(self) -> "Location":
        # Either provide a city (offline), or explicitly mark as online.
        city = (self.city or "").strip()
        if self.is_online is True:
            return self
        if city:
            return self
        raise ValueError("Either location.city (offline) or location.is_online=true (online) is required")
        return self


class AgeRange(BaseModel):
    min: int | None = Field(default=None, ge=0, le=120)
    max: int | None = Field(default=None, ge=0, le=120)

    @model_validator(mode="after")
    def _order(self) -> "AgeRange":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("age_range.min must be <= age_range.max")
        return self


class PersonFilters(BaseModel):
    age_range: AgeRange | None = Field(default=None, description="Suggested age range. If omitted, a broad default is assumed.")
    gender: Literal["male", "female", "non_binary", "any"] | None = Field(default=None, description="Gender preference.")
    industry: str | None = Field(default=None, description="Industry, e.g. 'Internet', 'Finance'.")
    role: str | None = Field(default=None, description="Role, e.g. 'Product Manager', 'Founder'.")
    intent_tags: list[str] | None = Field(default=None, description="Intent tags, e.g. ['hiring','dating','networking'].")


class TimeRange(BaseModel):
    start: str | None = Field(default=None, description="Start of the window (ISO date-time preferred).")
    end: str | None = Field(default=None, description="End of the window (ISO date-time preferred).")


class PriceRange(BaseModel):
    min: float | None = Field(default=None)
    max: float | None = Field(default=None)
    currency: str = Field(default="CNY")

    @model_validator(mode="after")
    def _price_order(self) -> "PriceRange":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("price_range.min must be <= price_range.max")
        return self


class EventFilters(BaseModel):
    time_range: TimeRange | None = Field(
        default=None,
        description="Time window for events. If user says 'this weekend', planner should convert to ISO date-time strings.",
    )
    price_range: PriceRange | None = Field(default=None, description="Price range. For free events, max=0.")
    category: (
        Literal[
            "party",
            "business",
            "sports",
            "education",
            "arts",
            "games",
            "board_games",
            "outdoors",
            "food_drink",
            "wellness",
            "community",
            "tech",
            "other",
            "unknown",
        ]
        | None
    ) = Field(default=None, description="Event category (taxonomy); use 'unknown' if unclear.")


class StructuredFilters(BaseModel):
    location: Location = Field(description="Required. Offline requires city; online requires is_online=true.")
    person_filters: PersonFilters | None = Field(default=None, description="Only valid when domain='person'.")
    event_filters: EventFilters | None = Field(default=None, description="Only valid when domain='event'.")


class IntelligentDiscoveryArgs(BaseModel):
    domain: DiscoveryDomain = Field(description="REQUIRED. Search domain; controls which filters are valid.")
    semantic_query: str | None = Field(
        default=None,
        description="Optional natural language description for fuzzy matching.",
    )
    structured_filters: StructuredFilters = Field(description="REQUIRED. Structured filters; location is required inside.")
    sort_strategy: DiscoverySortStrategy = Field(
        default="relevance",
        description="Sort strategy.",
    )
    limit: int = Field(default=5, ge=1, le=20, description="Optional. Max number of results (1-20).")

    @model_validator(mode="after")
    def _domain_specific_rules(self) -> "IntelligentDiscoveryArgs":
        sf = self.structured_filters
        if self.domain == "person":
            if sf.event_filters is not None:
                raise ValueError("structured_filters.event_filters is only valid when domain='event'")
        if self.domain == "event":
            if sf.person_filters is not None:
                raise ValueError("structured_filters.person_filters is only valid when domain='person'")
        return self


class DeepProfileAnalysisArgs(BaseModel):
    target_ids: list[str] = Field(
        min_length=1,
        description="IDs of target entities (people or events) to analyze. Must refer to IDs returned by intelligent_discovery in this session.",
    )
    analysis_mode: AnalysisMode = Field(
        description="detail=fetch details, compare=compare multiple candidates, compatibility_check=explain fit between user and target.",
    )
    focus_aspects: list[str] = Field(
        default_factory=list,
        description="Aspects user cares about. Example: ['career_history', 'mutual_connections', 'event_agenda'].",
    )


class ResultsRefineArgs(BaseModel):
    domain: DiscoveryDomain = Field(description="REQUIRED. Which kind of visible results to refine: person or event.")
    instruction: str = Field(description="REQUIRED. The user's refinement request, e.g. 'filter to California' or 'show only beginners'.")
    limit: int = Field(default=5, ge=0, le=20, description="Optional. Max number of results to return (0-20).")
    strategy: RefineStrategy = Field(default="filter_rerank", description="Refinement strategy (prototype: filter + rerank).")
    candidates: list[dict[str, Any]] = Field(
        description="REQUIRED. Full candidate objects from history.",
    )


class BookingArgs(BaseModel):
    activity: str = Field(description="The activity to do, e.g. 'running', 'coffee', 'hiking', 'tennis'.")
    location: str = Field(description="City or area, e.g. 'San Francisco', 'Shanghai'.")
    desired_time: str | None = Field(
        default=None,
        description="When the user wants to do it, e.g. 'Saturday afternoon', 'next weekend', 'tomorrow evening'.",
    )
    headcount: int = Field(
        default=3, ge=1, le=20,
        description="How many people the user wants to find. Default 3.",
    )
    gender_preference: str | None = Field(
        default=None,
        description="Gender preference: 'male', 'female', or 'any'. None means no preference.",
    )
    level: str | None = Field(
        default=None,
        description="Skill level for the activity: 'beginner', 'intermediate', 'advanced', 'competitive'.",
    )
    pace: str | None = Field(
        default=None,
        description="Running pace preference: 'easy', 'moderate', 'fast', 'racing'. Only for running activity.",
    )
    availability_slots: list[str] | None = Field(
        default=None,
        description="Time slots user is available: 'weekday_morning', 'weekday_lunch', 'weekday_evening', 'weekend_morning', 'weekend_afternoon'. Hard filter - only match users with overlapping availability.",
    )
    additional_requirements: str | None = Field(
        default=None,
        description="Any additional requirements from the user in free-form text.",
    )


LastResultsType = Literal["people", "things"]


class MemoryStore(BaseModel):
    profiles: dict[str, dict[str, Any]] = Field(default_factory=dict)
    events: dict[str, dict[str, Any]] = Field(default_factory=dict)
    runs: list[dict[str, Any]] = Field(default_factory=list)
