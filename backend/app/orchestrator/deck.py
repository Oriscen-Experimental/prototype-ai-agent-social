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
        if err.get("type") != "missing":
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
    return "active" if missing and missing[0] == key else ("upcoming" if key in missing else "completed")


def build_deck_for_tool(tool_name: str, tool_args: dict[str, Any]) -> DeckBuildResult:
    """
    Build a small card deck to collect missing required fields for a given tool.

    The deck uses dotted keys for nested fields (e.g. structured_filters.location).
    """
    tool = tool_by_name(tool_name)
    if tool is None:
        return DeckBuildResult(deck=None, missing_fields=[], validation_message="Unknown tool")

    try:
        tool.input_model(**(tool_args or {}))
        return DeckBuildResult(deck=None, missing_fields=[])
    except ValidationError as e:
        missing = _missing_from_validation_error(e)
        if not missing:
            return DeckBuildResult(deck=None, missing_fields=[], validation_message=str(e))

    cards: list[Card] = []

    if tool_name == "intelligent_discovery":
        cards.append(
            Card(
                id="domain",
                title="你想找：人 / 活动",
                status=_status_for(missing, "domain"),
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
            )
        )
        cards.append(
            Card(
                id="semantic_query",
                title="你想要的感觉（越口语越好）",
                status=_status_for(missing, "semantic_query"),
                fields=[
                    FormField(
                        key="semantic_query",
                        label="描述",
                        type="text",
                        required=True,
                        placeholder="例如：想找能聊创业产品的人 / 周末低压力的户外活动",
                        value=tool_args.get("semantic_query"),
                    )
                ],
                required=True,
            )
        )
        # Optional but helpful: location card (not required by schema, still included when missing explicit location mention)
        cards.append(
            Card(
                id="structured_filters_location",
                title="地点（可选，但会更准）",
                status=_status_for(missing, "structured_filters.location"),
                fields=[
                    FormField(
                        key="structured_filters.location",
                        label="地点",
                        type="text",
                        required=False,
                        placeholder="例如：上海 / 北京 / San Francisco",
                        value=((tool_args.get("structured_filters") or {}) if isinstance(tool_args.get("structured_filters"), dict) else {}).get("location"),
                    )
                ],
                required=False,
            )
        )

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

