"""Calculation settings for the Market Intelligence foundation."""

from __future__ import annotations

from dataclasses import dataclass, field


def _validate_proportion(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class MarketIntelligenceConfig:
    """Window and column settings used by the four dimension calculators.

    These values define observation periods only. They are not decision
    thresholds and do not imply a market state.
    """

    medium_window: int = 50
    long_window: int = 200
    participation_change_window: int = 5
    leadership_lookback: int = 20
    stress_window: int = 20
    drawdown_window: int = 252
    annualization_periods: int = 252

    date_column: str = "Date"
    ticker_column: str = "Ticker"
    close_column: str = "Close"
    sector_ticker_column: str = "Ticker"
    sector_column: str = "Sector"

    def __post_init__(self) -> None:
        windows = {
            "medium_window": self.medium_window,
            "long_window": self.long_window,
            "participation_change_window": self.participation_change_window,
            "leadership_lookback": self.leadership_lookback,
            "stress_window": self.stress_window,
            "drawdown_window": self.drawdown_window,
            "annualization_periods": self.annualization_periods,
        }
        invalid = [name for name, value in windows.items() if value <= 0]
        if invalid:
            names = ", ".join(invalid)
            raise ValueError(f"Configuration values must be positive: {names}")

        columns = {
            "date_column": self.date_column,
            "ticker_column": self.ticker_column,
            "close_column": self.close_column,
            "sector_ticker_column": self.sector_ticker_column,
            "sector_column": self.sector_column,
        }
        blank = [name for name, value in columns.items() if not value.strip()]
        if blank:
            names = ", ".join(blank)
            raise ValueError(f"Column names cannot be blank: {names}")


@dataclass(frozen=True)
class TrendInterpretationThresholds:
    """Configurable boundaries for Trend Structure interpretation."""

    strong_distance: float = 0.02
    weak_distance: float = -0.02

    def __post_init__(self) -> None:
        if self.weak_distance >= self.strong_distance:
            raise ValueError("weak_distance must be below strong_distance")


@dataclass(frozen=True)
class ParticipationInterpretationThresholds:
    """Configurable boundaries for Participation interpretation."""

    broad_share: float = 0.60
    narrow_share: float = 0.40

    def __post_init__(self) -> None:
        _validate_proportion("broad_share", self.broad_share)
        _validate_proportion("narrow_share", self.narrow_share)
        if self.narrow_share >= self.broad_share:
            raise ValueError("narrow_share must be below broad_share")


@dataclass(frozen=True)
class LeadershipInterpretationThresholds:
    """Configurable boundaries for Leadership Quality interpretation."""

    broad_positive_share: float = 0.60
    weak_positive_share: float = 0.40
    broad_sector_share: float = 0.60
    weak_sector_share: float = 0.40
    broad_effective_leader_share: float = 0.25

    def __post_init__(self) -> None:
        values = {
            "broad_positive_share": self.broad_positive_share,
            "weak_positive_share": self.weak_positive_share,
            "broad_sector_share": self.broad_sector_share,
            "weak_sector_share": self.weak_sector_share,
            "broad_effective_leader_share": self.broad_effective_leader_share,
        }
        for name, value in values.items():
            _validate_proportion(name, value)
        if self.weak_positive_share >= self.broad_positive_share:
            raise ValueError(
                "weak_positive_share must be below broad_positive_share"
            )
        if self.weak_sector_share >= self.broad_sector_share:
            raise ValueError("weak_sector_share must be below broad_sector_share")


@dataclass(frozen=True)
class StressInterpretationThresholds:
    """Configurable boundaries for Market Stress interpretation."""

    elevated_drawdown: float = 0.05
    high_drawdown: float = 0.10
    elevated_new_low_share: float = 0.05
    high_new_low_share: float = 0.15
    elevated_breadth_decline: float = 0.10
    high_breadth_decline: float = 0.20
    elevated_declining_day_share: float = 0.60
    high_declining_day_share: float = 0.75
    elevated_downside_deviation: float = 0.20
    high_downside_deviation: float = 0.35

    def __post_init__(self) -> None:
        pairs = {
            "drawdown": (self.elevated_drawdown, self.high_drawdown),
            "new_low_share": (
                self.elevated_new_low_share,
                self.high_new_low_share,
            ),
            "breadth_decline": (
                self.elevated_breadth_decline,
                self.high_breadth_decline,
            ),
            "declining_day_share": (
                self.elevated_declining_day_share,
                self.high_declining_day_share,
            ),
            "downside_deviation": (
                self.elevated_downside_deviation,
                self.high_downside_deviation,
            ),
        }
        for name, (elevated, high) in pairs.items():
            if elevated < 0 or high < 0:
                raise ValueError(f"{name} thresholds cannot be negative")
            if elevated >= high:
                raise ValueError(
                    f"Elevated {name} threshold must be below high threshold"
                )
        for name, value in {
            "elevated_drawdown": self.elevated_drawdown,
            "high_drawdown": self.high_drawdown,
            "elevated_new_low_share": self.elevated_new_low_share,
            "high_new_low_share": self.high_new_low_share,
            "elevated_breadth_decline": self.elevated_breadth_decline,
            "high_breadth_decline": self.high_breadth_decline,
            "elevated_declining_day_share": self.elevated_declining_day_share,
            "high_declining_day_share": self.high_declining_day_share,
        }.items():
            _validate_proportion(name, value)


@dataclass(frozen=True)
class InterpretationConfig:
    """Independent threshold groups used by the interpretation layer."""

    trend: TrendInterpretationThresholds = field(
        default_factory=TrendInterpretationThresholds
    )
    participation: ParticipationInterpretationThresholds = field(
        default_factory=ParticipationInterpretationThresholds
    )
    leadership: LeadershipInterpretationThresholds = field(
        default_factory=LeadershipInterpretationThresholds
    )
    stress: StressInterpretationThresholds = field(
        default_factory=StressInterpretationThresholds
    )


@dataclass(frozen=True)
class DrivingModeRules:
    """Configurable deterministic rules for Driving Mode selection.

    Counts apply only to the three opportunity dimensions: Trend,
    Participation, and Leadership.
    """

    aggressive_favorable_dimensions_required: int = 3
    defensive_adverse_dimensions_required: int = 2
    normal_adverse_dimensions_allowed: int = 0
    defensive_on_high_stress: bool = True
    cautious_on_elevated_stress: bool = True
    cautious_on_concentrated_leadership: bool = True
    cautious_on_unavailable_condition: bool = True
    high_confidence_agreement_required: int = 4
    medium_confidence_agreement_required: int = 3

    def __post_init__(self) -> None:
        opportunity_counts = {
            "aggressive_favorable_dimensions_required": (
                self.aggressive_favorable_dimensions_required
            ),
            "defensive_adverse_dimensions_required": (
                self.defensive_adverse_dimensions_required
            ),
            "normal_adverse_dimensions_allowed": (
                self.normal_adverse_dimensions_allowed
            ),
        }
        for name, value in opportunity_counts.items():
            if not 0 <= value <= 3:
                raise ValueError(f"{name} must be between 0 and 3")

        if (
            self.normal_adverse_dimensions_allowed
            >= self.defensive_adverse_dimensions_required
        ):
            raise ValueError(
                "normal_adverse_dimensions_allowed must be below "
                "defensive_adverse_dimensions_required"
            )

        if not 1 <= self.medium_confidence_agreement_required <= 4:
            raise ValueError(
                "medium_confidence_agreement_required must be between 1 and 4"
            )
        if not 1 <= self.high_confidence_agreement_required <= 4:
            raise ValueError(
                "high_confidence_agreement_required must be between 1 and 4"
            )
        if (
            self.medium_confidence_agreement_required
            >= self.high_confidence_agreement_required
        ):
            raise ValueError(
                "medium confidence agreement must be below high confidence "
                "agreement"
            )
