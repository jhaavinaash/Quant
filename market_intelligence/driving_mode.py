"""Deterministic Driving Mode selection from interpreted conditions only."""

from __future__ import annotations

from collections import Counter

from .config import DrivingModeRules
from .models import (
    ConfidenceLevel,
    DimensionExplanations,
    DrivingMode,
    DrivingModeName,
    LeadershipState,
    MarketConditions,
    ParticipationState,
    StressState,
    TrendState,
)

TRADING_APPROACH_SCOPE = (
    "This Personal Market Briefing is not linked to any specific engine, "
    "including F1. It applies to your overall trading approach."
)

_MODE_GUIDANCE = {
    DrivingModeName.AGGRESSIVE: (
        "Go full-on today. Conditions support broader trading, while normal "
        "trade discipline still applies."
    ),
    DrivingModeName.NORMAL: (
        "Trade normally today. Take valid setups without forcing extra trades."
    ),
    DrivingModeName.CAUTIOUS: (
        "Trade less and be selective today. Avoid forcing marginal setups."
    ),
    DrivingModeName.DEFENSIVE: (
        "Protect capital today. Minimize new trades and wait for conditions "
        "to improve."
    ),
}


def trading_approach_guidance(mode: DrivingModeName) -> str:
    """Return the plain-language overall trading approach for a mode."""

    return _MODE_GUIDANCE[mode]


def _opportunity_counts(
    conditions: MarketConditions,
) -> tuple[int, int, list[str]]:
    favorable = 0
    adverse = 0
    adverse_conditions: list[str] = []

    if conditions.trend.state == TrendState.STRONG:
        favorable += 1
    elif conditions.trend.state == TrendState.WEAK:
        adverse += 1
        adverse_conditions.append("Trend is Weak")

    if conditions.participation.state == ParticipationState.BROAD:
        favorable += 1
    elif conditions.participation.state == ParticipationState.NARROW:
        adverse += 1
        adverse_conditions.append("Participation is Narrow")

    if conditions.leadership.state == LeadershipState.BROAD:
        favorable += 1
    elif conditions.leadership.state == LeadershipState.WEAK:
        adverse += 1
        adverse_conditions.append("Leadership is Weak")

    return favorable, adverse, adverse_conditions


def _unavailable_conditions(conditions: MarketConditions) -> list[str]:
    unavailable = []
    if conditions.trend.state == TrendState.UNAVAILABLE:
        unavailable.append("Trend")
    if conditions.participation.state == ParticipationState.UNAVAILABLE:
        unavailable.append("Participation")
    if conditions.leadership.state == LeadershipState.UNAVAILABLE:
        unavailable.append("Leadership")
    if conditions.stress.state == StressState.UNAVAILABLE:
        unavailable.append("Stress")
    return unavailable


def _confidence(
    conditions: MarketConditions,
    rules: DrivingModeRules,
) -> ConfidenceLevel:
    stances = [
        {
            TrendState.STRONG: 1,
            TrendState.NEUTRAL: 0,
            TrendState.WEAK: -1,
        }.get(conditions.trend.state),
        {
            ParticipationState.BROAD: 1,
            ParticipationState.AVERAGE: 0,
            ParticipationState.NARROW: -1,
        }.get(conditions.participation.state),
        {
            LeadershipState.BROAD: 1,
            LeadershipState.CONCENTRATED: 0,
            LeadershipState.WEAK: -1,
        }.get(conditions.leadership.state),
        {
            StressState.LOW: 1,
            StressState.ELEVATED: -1,
            StressState.HIGH: -1,
        }.get(conditions.stress.state),
    ]
    if any(stance is None for stance in stances):
        return ConfidenceLevel.LOW

    agreement = max(Counter(stances).values())
    if agreement >= rules.high_confidence_agreement_required:
        return ConfidenceLevel.HIGH
    if agreement >= rules.medium_confidence_agreement_required:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _dimension_explanations(
    conditions: MarketConditions,
) -> DimensionExplanations:
    return DimensionExplanations(
        trend=(
            f"{conditions.trend.state.value}: "
            f"{conditions.trend.explanation}"
        ),
        participation=(
            f"{conditions.participation.state.value}: "
            f"{conditions.participation.explanation}"
        ),
        leadership=(
            f"{conditions.leadership.state.value}: "
            f"{conditions.leadership.explanation}"
        ),
        stress=(
            f"{conditions.stress.state.value}: "
            f"{conditions.stress.explanation}"
        ),
    )


def determine_driving_mode(
    conditions: MarketConditions,
    rules: DrivingModeRules | None = None,
) -> DrivingMode:
    """Determine one explainable mode from qualitative conditions.

    The function reads condition states and explanations only. It never reads
    the raw metrics retained inside each condition.
    """

    active_rules = rules or DrivingModeRules()
    favorable, adverse, adverse_conditions = _opportunity_counts(conditions)
    unavailable = _unavailable_conditions(conditions)

    if (
        active_rules.defensive_on_high_stress
        and conditions.stress.state == StressState.HIGH
    ):
        mode = DrivingModeName.DEFENSIVE
        reason = (
            "Stress is High, activating the configured defensive override."
        )
    elif adverse >= active_rules.defensive_adverse_dimensions_required:
        mode = DrivingModeName.DEFENSIVE
        reason = (
            f"{adverse} opportunity dimensions are adverse: "
            + "; ".join(adverse_conditions)
            + "."
        )
    elif unavailable and active_rules.cautious_on_unavailable_condition:
        mode = DrivingModeName.CAUTIOUS
        reason = (
            "Required interpreted conditions are unavailable: "
            + ", ".join(unavailable)
            + "."
        )
    elif (
        active_rules.cautious_on_elevated_stress
        and conditions.stress.state
        in (StressState.ELEVATED, StressState.HIGH)
    ):
        mode = DrivingModeName.CAUTIOUS
        reason = (
            f"Stress is {conditions.stress.state.value}, activating the "
            "configured caution rule."
        )
    elif (
        active_rules.cautious_on_concentrated_leadership
        and conditions.leadership.state == LeadershipState.CONCENTRATED
    ):
        mode = DrivingModeName.CAUTIOUS
        reason = "Leadership is Concentrated, limiting broad deployment."
    elif adverse > active_rules.normal_adverse_dimensions_allowed:
        mode = DrivingModeName.CAUTIOUS
        reason = "Caution is required because " + "; ".join(adverse_conditions) + "."
    elif (
        conditions.stress.state == StressState.LOW
        and not unavailable
        and favorable
        >= active_rules.aggressive_favorable_dimensions_required
    ):
        mode = DrivingModeName.AGGRESSIVE
        reason = (
            f"Stress is Low and {favorable} opportunity dimensions are "
            "favorable."
        )
    else:
        mode = DrivingModeName.NORMAL
        reason = (
            "Conditions contain no defensive or caution trigger and do not "
            "meet the configured Aggressive requirements."
        )

    return DrivingMode(
        as_of=conditions.as_of,
        mode=mode,
        reason=reason,
        dimensions=_dimension_explanations(conditions),
        confidence=_confidence(conditions, active_rules),
    )


class DrivingModeEngine:
    """Apply a configured deterministic rule set to MarketConditions."""

    def __init__(self, rules: DrivingModeRules | None = None) -> None:
        self.rules = rules or DrivingModeRules()

    def determine(self, conditions: MarketConditions) -> DrivingMode:
        """Return the current explainable Driving Mode."""

        return determine_driving_mode(conditions, self.rules)
