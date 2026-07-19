"""Participation dimension calculation."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .config import MarketIntelligenceConfig
from .models import ParticipationResult


def _share(numerator: int, denominator: int) -> Optional[float]:
    return None if denominator == 0 else float(numerator / denominator)


def _breadth_series(close_prices: pd.DataFrame, window: int) -> pd.Series:
    averages = close_prices.rolling(window, min_periods=window).mean()
    valid = close_prices.notna() & averages.notna()
    counts = valid.sum(axis=1)
    above = ((close_prices > averages) & valid).sum(axis=1)
    return above.div(counts.where(counts > 0))


def calculate_participation(
    close_prices: pd.DataFrame,
    config: MarketIntelligenceConfig,
) -> ParticipationResult:
    """Calculate current participation level and medium-breadth change."""

    if close_prices.empty:
        raise ValueError("Participation calculation requires at least one price row")

    medium_average = close_prices.rolling(
        config.medium_window,
        min_periods=config.medium_window,
    ).mean()
    long_average = close_prices.rolling(
        config.long_window,
        min_periods=config.long_window,
    ).mean()

    latest = close_prices.iloc[-1]
    medium_valid = latest.notna() & medium_average.iloc[-1].notna()
    long_valid = latest.notna() & long_average.iloc[-1].notna()
    above_medium = (latest > medium_average.iloc[-1]) & medium_valid
    above_long = (latest > long_average.iloc[-1]) & long_valid

    medium_coverage = int(medium_valid.sum())
    long_coverage = int(long_valid.sum())
    above_medium_count = int(above_medium.sum())
    above_long_count = int(above_long.sum())

    breadth = _breadth_series(close_prices, config.medium_window)
    change_window = config.participation_change_window
    breadth_change: Optional[float] = None
    if len(breadth) > change_window:
        current = breadth.iloc[-1]
        previous = breadth.iloc[-1 - change_window]
        if pd.notna(current) and pd.notna(previous):
            breadth_change = float(current - previous)

    return ParticipationResult(
        as_of=close_prices.index[-1].to_pydatetime(),
        constituent_count=int(latest.notna().sum()),
        medium_coverage=medium_coverage,
        long_coverage=long_coverage,
        above_medium_count=above_medium_count,
        above_long_count=above_long_count,
        above_medium_share=_share(above_medium_count, medium_coverage),
        above_long_share=_share(above_long_count, long_coverage),
        medium_breadth_change=breadth_change,
        change_window=change_window,
    )
