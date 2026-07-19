"""Structured results returned by Market Intelligence calculations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class TrendResult:
    """Current medium- and long-term structure of the universe."""

    as_of: datetime
    constituent_count: int
    universe_level: float
    medium_average: Optional[float]
    long_average: Optional[float]
    distance_from_medium: Optional[float]
    distance_from_long: Optional[float]


@dataclass(frozen=True)
class ParticipationResult:
    """Current breadth level and change across constituents."""

    as_of: datetime
    constituent_count: int
    medium_coverage: int
    long_coverage: int
    above_medium_count: int
    above_long_count: int
    above_medium_share: Optional[float]
    above_long_share: Optional[float]
    medium_breadth_change: Optional[float]
    change_window: int


@dataclass(frozen=True)
class LeadershipResult:
    """Distribution of current strength across stocks and sectors."""

    as_of: datetime
    lookback: int
    eligible_constituent_count: int
    positive_constituent_count: int
    positive_return_share: Optional[float]
    leadership_concentration: Optional[float]
    effective_leader_count: Optional[float]
    sector_count: int
    positive_sector_share: Optional[float]


@dataclass(frozen=True)
class StressResult:
    """Current damage and downside instability in the universe."""

    as_of: datetime
    constituent_count: int
    universe_drawdown: Optional[float]
    new_low_count: int
    new_low_coverage: int
    new_low_share: Optional[float]
    persistent_breadth_change: Optional[float]
    breadth_declining_days: int
    breadth_change_observations: int
    downside_deviation: Optional[float]


@dataclass(frozen=True)
class MarketIntelligence:
    """Complete foundation result with four independent dimensions."""

    as_of: datetime
    universe_size: int
    trend: TrendResult
    participation: ParticipationResult
    leadership: LeadershipResult
    stress: StressResult

    def as_dict(self) -> dict[str, Any]:
        """Return a serialization-friendly nested dictionary."""

        result = asdict(self)
        result["as_of"] = self.as_of.isoformat()
        for dimension in ("trend", "participation", "leadership", "stress"):
            result[dimension]["as_of"] = result[dimension]["as_of"].isoformat()
        return result
