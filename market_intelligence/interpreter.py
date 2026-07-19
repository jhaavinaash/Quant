"""Independent qualitative interpretation of raw dimension metrics."""

from __future__ import annotations

from .config import (
    InterpretationConfig,
    LeadershipInterpretationThresholds,
    ParticipationInterpretationThresholds,
    StressInterpretationThresholds,
    TrendInterpretationThresholds,
)
from .models import (
    LeadershipCondition,
    LeadershipResult,
    LeadershipState,
    MarketConditions,
    MarketIntelligence,
    ParticipationCondition,
    ParticipationResult,
    ParticipationState,
    StressCondition,
    StressResult,
    StressState,
    TrendCondition,
    TrendResult,
    TrendState,
)


def _percent(value: float) -> str:
    return f"{value:.1%}"


def interpret_trend(
    raw: TrendResult,
    thresholds: TrendInterpretationThresholds,
) -> TrendCondition:
    """Interpret Trend Structure without using another dimension."""

    medium = raw.distance_from_medium
    long = raw.distance_from_long
    if medium is None or long is None:
        return TrendCondition(
            raw=raw,
            state=TrendState.UNAVAILABLE,
            explanation="Trend history is insufficient for both observation windows.",
        )

    if (
        medium >= thresholds.strong_distance
        and long >= thresholds.strong_distance
    ):
        state = TrendState.STRONG
        explanation = (
            f"Universe structure is {_percent(medium)} above its medium trend "
            f"and {_percent(long)} above its long trend."
        )
    elif medium <= thresholds.weak_distance and long <= thresholds.weak_distance:
        state = TrendState.WEAK
        explanation = (
            f"Universe structure is {_percent(abs(medium))} below its medium "
            f"trend and {_percent(abs(long))} below its long trend."
        )
    else:
        state = TrendState.NEUTRAL
        explanation = (
            "Medium- and long-term universe structure is mixed or close to "
            "its configured boundaries."
        )
    return TrendCondition(raw=raw, state=state, explanation=explanation)


def interpret_participation(
    raw: ParticipationResult,
    thresholds: ParticipationInterpretationThresholds,
) -> ParticipationCondition:
    """Interpret Participation without using another dimension."""

    medium = raw.above_medium_share
    long = raw.above_long_share
    if medium is None or long is None:
        return ParticipationCondition(
            raw=raw,
            state=ParticipationState.UNAVAILABLE,
            explanation="Participation history is insufficient for both breadth views.",
        )

    if medium >= thresholds.broad_share and long >= thresholds.broad_share:
        state = ParticipationState.BROAD
        explanation = (
            f"{_percent(medium)} of covered stocks are above their medium "
            f"trend and {_percent(long)} are above their long trend."
        )
    elif medium <= thresholds.narrow_share and long <= thresholds.narrow_share:
        state = ParticipationState.NARROW
        explanation = (
            f"Only {_percent(medium)} of covered stocks are above their medium "
            f"trend and {_percent(long)} are above their long trend."
        )
    else:
        state = ParticipationState.AVERAGE
        explanation = (
            "Stock participation is mixed between the medium- and long-term "
            "breadth views."
        )
    return ParticipationCondition(raw=raw, state=state, explanation=explanation)


def interpret_leadership(
    raw: LeadershipResult,
    thresholds: LeadershipInterpretationThresholds,
) -> LeadershipCondition:
    """Interpret Leadership Quality without using another dimension."""

    positive_share = raw.positive_return_share
    sector_share = raw.positive_sector_share
    if (
        positive_share is None
        or sector_share is None
        or raw.effective_leader_count is None
        or raw.eligible_constituent_count <= 0
    ):
        return LeadershipCondition(
            raw=raw,
            state=LeadershipState.UNAVAILABLE,
            explanation=(
                "Leadership interpretation requires stock strength, "
                "concentration, and sector participation."
            ),
        )

    weak_stock_breadth = positive_share <= thresholds.weak_positive_share
    weak_sector_breadth = (
        sector_share is not None
        and sector_share <= thresholds.weak_sector_share
    )
    if weak_stock_breadth or weak_sector_breadth:
        details = [f"{_percent(positive_share)} of stocks have positive strength"]
        if sector_share is not None:
            details.append(f"{_percent(sector_share)} of sectors are positive")
        return LeadershipCondition(
            raw=raw,
            state=LeadershipState.WEAK,
            explanation="; ".join(details) + ".",
        )

    effective_share = raw.effective_leader_count / raw.eligible_constituent_count

    sectors_are_broad = sector_share >= thresholds.broad_sector_share
    if (
        positive_share >= thresholds.broad_positive_share
        and effective_share >= thresholds.broad_effective_leader_share
        and sectors_are_broad
    ):
        explanation = (
            f"Strength spans {_percent(positive_share)} of stocks with an "
            f"effective leader share of {_percent(effective_share)}"
        )
        explanation += f" and {_percent(sector_share)} positive sectors"
        return LeadershipCondition(
            raw=raw,
            state=LeadershipState.BROAD,
            explanation=explanation + ".",
        )

    return LeadershipCondition(
        raw=raw,
        state=LeadershipState.CONCENTRATED,
        explanation=(
            "Positive strength exists, but its stock or sector distribution "
            "is not broad enough to qualify as broad leadership."
        ),
    )


def interpret_stress(
    raw: StressResult,
    thresholds: StressInterpretationThresholds,
) -> StressCondition:
    """Interpret Market Stress without using another dimension."""

    declining_day_share = None
    if raw.breadth_change_observations > 0:
        declining_day_share = (
            raw.breadth_declining_days / raw.breadth_change_observations
        )

    metrics = [
        (
            "universe drawdown",
            raw.universe_drawdown,
            thresholds.elevated_drawdown,
            thresholds.high_drawdown,
        ),
        (
            "new-low pressure",
            raw.new_low_share,
            thresholds.elevated_new_low_share,
            thresholds.high_new_low_share,
        ),
        (
            "persistent breadth decline",
            (
                None
                if raw.persistent_breadth_change is None
                else max(-raw.persistent_breadth_change, 0.0)
            ),
            thresholds.elevated_breadth_decline,
            thresholds.high_breadth_decline,
        ),
        (
            "declining breadth frequency",
            declining_day_share,
            thresholds.elevated_declining_day_share,
            thresholds.high_declining_day_share,
        ),
        (
            "downside deviation",
            raw.downside_deviation,
            thresholds.elevated_downside_deviation,
            thresholds.high_downside_deviation,
        ),
    ]
    if any(value is None for _, value, _, _ in metrics):
        return StressCondition(
            raw=raw,
            state=StressState.UNAVAILABLE,
            explanation="Stress history is insufficient across all required metrics.",
        )
    available = [
        (name, value, elevated, high)
        for name, value, elevated, high in metrics
        if value is not None
    ]

    high_triggers = [
        name for name, value, _, high in available if value >= high
    ]
    if high_triggers:
        return StressCondition(
            raw=raw,
            state=StressState.HIGH,
            explanation="High stress is present in " + ", ".join(high_triggers) + ".",
        )

    elevated_triggers = [
        name
        for name, value, elevated, _ in available
        if value >= elevated
    ]
    if elevated_triggers:
        return StressCondition(
            raw=raw,
            state=StressState.ELEVATED,
            explanation=(
                "Elevated stress is present in "
                + ", ".join(elevated_triggers)
                + "."
            ),
        )

    return StressCondition(
        raw=raw,
        state=StressState.LOW,
        explanation="Available damage and downside metrics remain below elevated boundaries.",
    )


class MarketIntelligenceInterpreter:
    """Interpret each dimension independently and preserve its raw result."""

    def __init__(self, config: InterpretationConfig | None = None) -> None:
        self.config = config or InterpretationConfig()

    def interpret(self, intelligence: MarketIntelligence) -> MarketConditions:
        """Return four independent qualitative conditions."""

        return MarketConditions(
            as_of=intelligence.as_of,
            trend=interpret_trend(intelligence.trend, self.config.trend),
            participation=interpret_participation(
                intelligence.participation,
                self.config.participation,
            ),
            leadership=interpret_leadership(
                intelligence.leadership,
                self.config.leadership,
            ),
            stress=interpret_stress(intelligence.stress, self.config.stress),
        )


def interpret_market_intelligence(
    intelligence: MarketIntelligence,
    config: InterpretationConfig | None = None,
) -> MarketConditions:
    """Convenience public API for one-off independent interpretation."""

    return MarketIntelligenceInterpreter(config).interpret(intelligence)
