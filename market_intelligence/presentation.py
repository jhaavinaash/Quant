"""Shared presentation helpers for existing Market Intelligence outputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .models import (
    LeadershipState,
    MarketConditions,
    ParticipationState,
    StressState,
    TrendState,
)

_PERCENTAGE_METRICS = {
    "distance_from_medium",
    "distance_from_long",
    "above_medium_share",
    "above_long_share",
    "medium_breadth_change",
    "positive_return_share",
    "positive_sector_share",
    "universe_drawdown",
    "new_low_share",
    "persistent_breadth_change",
    "downside_deviation",
}


@dataclass(frozen=True)
class BriefingHighlight:
    dimension: str
    state: str
    explanation: str


@dataclass(frozen=True)
class BriefingMetric:
    name: str
    value: str


def briefing_highlights(
    conditions: MarketConditions,
) -> tuple[list[BriefingHighlight], list[BriefingHighlight]]:
    """Group already-interpreted conditions for briefing display only."""

    dimensions = [
        ("Trend", conditions.trend),
        ("Participation", conditions.participation),
        ("Leadership", conditions.leadership),
        ("Stress", conditions.stress),
    ]
    positive_states = {
        TrendState.STRONG,
        ParticipationState.BROAD,
        LeadershipState.BROAD,
        StressState.LOW,
    }
    risk_states = {
        TrendState.WEAK,
        TrendState.UNAVAILABLE,
        ParticipationState.NARROW,
        ParticipationState.UNAVAILABLE,
        LeadershipState.CONCENTRATED,
        LeadershipState.WEAK,
        LeadershipState.UNAVAILABLE,
        StressState.ELEVATED,
        StressState.HIGH,
        StressState.UNAVAILABLE,
    }

    positives = [
        BriefingHighlight(name, condition.state.value, condition.explanation)
        for name, condition in dimensions
        if condition.state in positive_states
    ]
    risks = [
        BriefingHighlight(name, condition.state.value, condition.explanation)
        for name, condition in dimensions
        if condition.state in risk_states
    ]
    return positives, risks


def _format_metric(name: str, value: Any) -> str:
    if value is None:
        return "Unavailable"
    if name == "as_of":
        if isinstance(value, datetime):
            return value.strftime("%d %b %Y")
        try:
            return datetime.fromisoformat(str(value)).strftime("%d %b %Y")
        except ValueError:
            return str(value)
    if name in _PERCENTAGE_METRICS:
        return f"{float(value):.1%}"
    if name == "leadership_concentration":
        return f"{float(value):.4f}"
    if name in {"universe_level", "medium_average", "long_average"}:
        return f"{float(value):.4f}"
    if name == "effective_leader_count":
        return f"{float(value):.1f}"
    return str(value)


def briefing_metrics(metrics: Mapping[str, Any]) -> list[BriefingMetric]:
    """Format existing raw values for transparent display."""

    return [
        BriefingMetric(
            name=name.replace("_", " ").title(),
            value=_format_metric(name, value),
        )
        for name, value in metrics.items()
    ]
