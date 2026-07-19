"""Trend dimension calculation."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .config import MarketIntelligenceConfig
from .models import TrendResult


def _equal_weight_universe(close_prices: pd.DataFrame) -> pd.Series:
    returns = close_prices.pct_change(fill_method=None)
    universe_returns = returns.mean(axis=1, skipna=True).fillna(0.0)
    return (1.0 + universe_returns).cumprod()


def _value_or_none(value: float) -> Optional[float]:
    return None if pd.isna(value) else float(value)


def _distance(level: float, reference: Optional[float]) -> Optional[float]:
    if reference is None or reference == 0:
        return None
    return float(level / reference - 1.0)


def calculate_trend(
    close_prices: pd.DataFrame,
    config: MarketIntelligenceConfig,
) -> TrendResult:
    """Calculate raw medium- and long-term universe trend measurements.

    ``close_prices`` must have dates in its index and tickers in its columns.
    The result describes current structure only; it assigns no state or score.
    """

    if close_prices.empty:
        raise ValueError("Trend calculation requires at least one price row")

    universe = _equal_weight_universe(close_prices)
    level = float(universe.iloc[-1])
    medium = _value_or_none(
        universe.rolling(config.medium_window, min_periods=config.medium_window)
        .mean()
        .iloc[-1]
    )
    long = _value_or_none(
        universe.rolling(config.long_window, min_periods=config.long_window)
        .mean()
        .iloc[-1]
    )

    return TrendResult(
        as_of=close_prices.index[-1].to_pydatetime(),
        constituent_count=int(close_prices.iloc[-1].notna().sum()),
        universe_level=level,
        medium_average=medium,
        long_average=long,
        distance_from_medium=_distance(level, medium),
        distance_from_long=_distance(level, long),
    )
