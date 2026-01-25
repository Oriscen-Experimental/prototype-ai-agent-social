from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from pydantic import ValidationError

from ..models import Card, CardDeck, FormField, FormOption
from ..tools import tool_by_name


@dataclass(frozen=True)
class DeckBuildResult:
    deck: CardDeck | None
    missing_fields: list[str]
    validation_message: str | None = None


def _missing_from_validation_error(e: ValidationError) -> list[str]:
    missing: list[str] = []
    for err in e.errors():
        if err.get("type") not in {"missing", "too_short"}:
            continue
        loc = err.get("loc")
        if not isinstance(loc, tuple) or not loc:
            continue
        parts = [str(p) for p in loc if p is not None]
        if parts:
            missing.append(".".join(parts))
    # dedupe stable order
    seen: set[str] = set()
    out: list[str] = []
    for m in missing:
        if m in seen:
            continue
        seen.add(m)
        out.append(m)
    return out


def _status_for(missing: list[str], key: str) -> str:
    if not missing:
        return "completed"
    if missing[0] == key or missing[0].startswith(key + ".") or key.startswith(missing[0] + "."):
        return "active"
    if any(m == key or m.startswith(key + ".") or key.startswith(m + ".") for m in missing):
        return "upcoming"
    return "completed"


def build_deck_for_tool(tool_name: str, tool_args: dict[str, Any]) -> DeckBuildResult:
    """
    Build a small card deck to collect missing required fields for a given tool.

    The deck uses dotted keys for nested fields (e.g. structured_filters.location).
    """
    tool = tool_by_name(tool_name)
    if tool is None:
        return DeckBuildResult(deck=None, missing_fields=[], validation_message="Unknown tool")

    # Special-case: intelligent_discovery has domain-aware constraints where
    # "missing info" can surface as value_errors (not pydantic "missing").
    # We always compute the deck first, then validate only when nothing is missing.
    if tool_name == "intelligent_discovery":
        domain = (tool_args.get("domain") if isinstance(tool_args.get("domain"), str) else "").strip()
        sf = tool_args.get("structured_filters") if isinstance(tool_args.get("structured_filters"), dict) else {}
        loc = sf.get("location") if isinstance(sf, dict) and isinstance(sf.get("location"), dict) else {}
        is_online_val = loc.get("is_online")
        is_online = is_online_val if isinstance(is_online_val, bool) else None
        city = (loc.get("city") if isinstance(loc.get("city"), str) else "").strip()
        semantic_query = (tool_args.get("semantic_query") if isinstance(tool_args.get("semantic_query"), str) else "").strip()

        has_location = bool(city) or (is_online is True)

        missing = []
        if not domain:
            missing.append("domain")
        # Need at least one: city (offline) OR is_online=true (online).
        # If missing both, ask online/offline first (then city if offline).
        if not has_location:
            missing.append("structured_filters.location.is_online")
        if is_online is False and not city:
            missing.append("structured_filters.location.city")

        def status_domain() -> str:
            if domain:
                return "completed"
            return "active" if (missing and missing[0] == "domain") else "upcoming"

        def status_semantic() -> str:
            if semantic_query:
                return "completed"
            return "upcoming"

        def status_location_mode() -> str:
            if has_location:
                return "completed"
            return "active" if (missing and missing[0] == "structured_filters.location.is_online") else "upcoming"

        def status_city() -> str:
            if is_online is True or city:
                return "completed"
            return "active" if (missing and missing[0] == "structured_filters.location.city") else "upcoming"

        cards: list[Card] = [
            Card(
                id="domain",
                title="你想找：人 / 活动",
                status=status_domain(),
                fields=[
                    FormField(
                        key="domain",
                        label="领域",
                        type="select",
                        required=True,
                        options=[
                            FormOption(value="person", label="找人"),
                            FormOption(value="event", label="找活动/组局"),
                        ],
                        value=tool_args.get("domain"),
                    )
                ],
                required=True,
            ),
            Card(
                id="semantic_query",
                title="你想要的感觉（越口语越好）",
                status=status_semantic(),
                fields=[
                    FormField(
                        key="semantic_query",
                        label="描述",
                        type="text",
                        required=False,
                        placeholder="例如：想找能聊创业产品的人 / 周末低压力的户外活动",
                        value=tool_args.get("semantic_query"),
                    )
                ],
                required=False,
            ),
            Card(
                id="structured_filters_location_mode",
                title="线上 / 线下",
                status=status_location_mode(),
                fields=[
                    FormField(
                        key="structured_filters.location.is_online",
                        label="是否线上",
                        type="select",
                        required=True,
                        options=[
                            FormOption(value="true", label="线上/虚拟"),
                            FormOption(value="false", label="线下/同城"),
                        ],
                        value=str(loc.get("is_online")).lower() if isinstance(loc.get("is_online"), bool) else None,
                    ),
                ],
                required=True,
            ),
            Card(
                id="structured_filters_location_city",
                title="城市（线下必填）",
                status=status_city(),
                fields=[
                    FormField(
                        key="structured_filters.location.city",
                        label="城市",
                        type="text",
                        required=True,
                        placeholder="例如：Shanghai / Beijing / San Francisco",
                        value=loc.get("city"),
                    ),
                    FormField(
                        key="structured_filters.location.region",
                        label="区域/商圈（可选）",
                        type="text",
                        required=False,
                        placeholder="例如：徐汇 / 朝阳 / SOMA",
                        value=loc.get("region"),
                    ),
                ],
                required=True,
            ),
        ]

        deck = CardDeck(layout="stacked", activeCardId=None, cards=cards)
        if missing:
            return DeckBuildResult(deck=deck, missing_fields=missing)

        try:
            tool.input_model(**(tool_args or {}))
            return DeckBuildResult(deck=None, missing_fields=[])
        except ValidationError as e:
            return DeckBuildResult(deck=None, missing_fields=[], validation_message=str(e))

    try:
        tool.input_model(**(tool_args or {}))
        return DeckBuildResult(deck=None, missing_fields=[])
    except ValidationError as e:
        missing = _missing_from_validation_error(e)
        if not missing:
            return DeckBuildResult(deck=None, missing_fields=[], validation_message=str(e))

    cards: list[Card] = []

    if tool_name == "deep_profile_analysis":
        cards.append(
            Card(
                id="analysis_mode",
                title="你想怎么分析",
                status=_status_for(missing, "analysis_mode"),
                fields=[
                    FormField(
                        key="analysis_mode",
                        label="模式",
                        type="select",
                        required=True,
                        options=[
                            FormOption(value="detail", label="看详情"),
                            FormOption(value="compare", label="对比"),
                            FormOption(value="compatibility_check", label="匹配度解释"),
                        ],
                        value=tool_args.get("analysis_mode"),
                    )
                ],
                required=True,
            )
        )
        cards.append(
            Card(
                id="target_ids",
                title="要分析的对象（ID）",
                status=_status_for(missing, "target_ids"),
                fields=[
                    FormField(
                        key="target_ids",
                        label="ID（多个用逗号分隔）",
                        type="text",
                        required=True,
                        placeholder="例如：p_123,p_456（通常不需要手填：你也可以直接说“第一个/第二个”）",
                        value=tool_args.get("target_ids"),
                    )
                ],
                required=True,
            )
        )

    deck = CardDeck(layout="stacked", activeCardId=None, cards=cards)
    return DeckBuildResult(deck=deck, missing_fields=missing)
