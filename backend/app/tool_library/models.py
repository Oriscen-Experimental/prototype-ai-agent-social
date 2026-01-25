from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


DiscoveryDomain = Literal["person", "event"]
DiscoverySortStrategy = Literal["relevance", "distance", "time_soonest", "popularity", "match_score"]
AnalysisMode = Literal["detail", "compare", "compatibility_check"]


class TimeRange(BaseModel):
    start: str | None = Field(
        default=None,
        description="Start time of the desired window (ISO string or natural language). Example: '2026-02-01 18:00' or 'this weekend'.",
    )
    end: str | None = Field(
        default=None,
        description="End time of the desired window (ISO string or natural language).",
    )


class PriceRange(BaseModel):
    min: float | None = Field(default=None, description="Minimum price/budget (currency-agnostic).")
    max: float | None = Field(default=None, description="Maximum price/budget (currency-agnostic).")


class Demographics(BaseModel):
    age_range: dict[str, int] | None = Field(
        default=None,
        description="Age range constraint. Example: {\"min\": 25, \"max\": 32}.",
    )
    gender: str | None = Field(
        default=None,
        description="Gender preference (free text for now). Example: 'female' or 'any'.",
    )
    industry: str | None = Field(
        default=None,
        description="Industry constraint. Example: 'design', 'fintech', 'education'.",
    )


class StructuredFilters(BaseModel):
    location: str | None = Field(
        default=None,
        description="Hard filter for location. Can be a city name, neighborhood, or coordinates.",
    )
    time_range: TimeRange | None = Field(
        default=None,
        description="Hard filter for event time window (events only).",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Hard filter tags. Example: ['hiking', 'coffee', 'board_games'].",
    )
    price_range: PriceRange | None = Field(
        default=None,
        description="Hard filter for event price/budget (events only).",
    )
    demographics: Demographics | None = Field(
        default=None,
        description="Hard filter for person demographics (people only).",
    )


class IntelligentDiscoveryArgs(BaseModel):
    domain: DiscoveryDomain = Field(description="Search domain: person for social_connect, event for event_discovery.")
    semantic_query: str = Field(
        min_length=1,
        description="User's fuzzy need for semantic retrieval. Example: 'want to talk to someone building products' or 'low-pressure weekend outdoor activity'.",
    )
    structured_filters: StructuredFilters | None = Field(
        default=None,
        description="Hard structured filters as key-value constraints.",
    )
    sort_strategy: DiscoverySortStrategy = Field(
        default="relevance",
        description="Sorting logic. match_score is for deep matching to the user's profile.",
    )
    limit: int = Field(default=5, ge=1, le=20, description="Max number of results to return (1-20).")

    @model_validator(mode="after")
    def _domain_specific_rules(self) -> "IntelligentDiscoveryArgs":
        sf = self.structured_filters
        if sf is None:
            return self

        if self.domain == "person":
            if sf.time_range is not None or sf.price_range is not None:
                raise ValueError("structured_filters.time_range/price_range are only valid when domain='event'")
        if self.domain == "event":
            if sf.demographics is not None:
                raise ValueError("structured_filters.demographics is only valid when domain='person'")
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


LastResultsType = Literal["people", "things"]


class MemoryStore(BaseModel):
    profiles: dict[str, dict[str, Any]] = Field(default_factory=dict)
    events: dict[str, dict[str, Any]] = Field(default_factory=dict)
    runs: list[dict[str, Any]] = Field(default_factory=list)

