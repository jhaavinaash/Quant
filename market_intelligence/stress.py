"""Stress dimension calculation."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .config import MarketIntelligenceConfig
from .models import StressResult


def _equal_weight_universe(close_prices: pd.DataFrame) -> pd.Series:
    returns = close_prices.pct_change(fill_method=None)
    universe_returns = returns.mean(axis=1, skipna=True).fillna(0.0)
    return (1.0 + universe_returns).cumprod()


def _breadth_series(close_prices: pd.DataFrame, window: int) -> pd.Series:
    averages = close_prices.rolling(window, min_periods=window).mean()
    valid = close_prices.notna() & averages.notna()
    counts = valid.sum(axis=1)
    above = ((close_prices > averages) & valid).sum(axis=1)
    return above.div(counts.where(counts > 0))


def calculate_stress(
    close_prices: pd.DataFrame,
    config: MarketIntelligenceConfig,
) -> StressResult:
    """Calculate raw current-damage and downside-instability measurements.

    The result is not a Stress Index and applies no weights, thresholds, state
    labels, or defensive decision rules.
    """

    if close_prices.empty:
        raise ValueError("Stress calculation requires at least one price row")

    universe = _equal_weight_universe(close_prices)
    drawdown_reference = universe.rolling(
        config.drawdown_window,
        min_periods=config.drawdown_window,
    ).max().iloc[-1]
    universe_drawdown: Optional[float] = None
    if pd.notna(drawdown_reference) and drawdown_reference > 0:
        universe_drawdown = float(1.0 - universe.iloc[-1] / drawdown_reference)

    rolling_lows = close_prices.rolling(
        config.drawdown_window,
        min_periods=config.drawdown_window,
    ).min()
    latest = close_prices.iloc[-1]
    low_valid = latest.notna() & rolling_lows.iloc[-1].notna()
    new_lows = (latest <= rolling_lows.iloc[-1]) & low_valid
    new_low_count = int(new_lows.sum())
    new_low_coverage = int(low_valid.sum())
    new_low_share = (
        None
        if new_low_coverage == 0
        else float(new_low_count / new_low_coverage)
    )

    breadth = _breadth_series(close_prices, config.medium_window)
    stress_window = config.stress_window
    breadth_change: Optional[float] = None
    if len(breadth) > stress_window:
        current = breadth.iloc[-1]
        previous = breadth.iloc[-1 - stress_window]
        if pd.notna(current) and pd.notna(previous):
            breadth_change = float(current - previous)

    recent_breadth_changes = breadth.diff().iloc[-stress_window:].dropna()
    breadth_declining_days = int((recent_breadth_changes < 0).sum())

    recent_returns = universe.pct_change(fill_method=None).iloc[-stress_window:]
    recent_returns = recent_returns.dropna()
    downside_deviation: Optional[float] = None
    if not recent_returns.empty:
        downside_returns = recent_returns.clip(upper=0.0)
        downside_deviation = float(
            np.sqrt(np.square(downside_returns).mean())
            * np.sqrt(config.annualization_periods)
        )

    return StressResult(
        as_of=close_prices.index[-1].to_pydatetime(),
        constituent_count=int(latest.notna().sum()),
        universe_drawdown=universe_drawdown,
        new_low_count=new_low_count,
        new_low_coverage=new_low_coverage,
        new_low_share=new_low_share,
        persistent_breadth_change=breadth_change,
        breadth_declining_days=breadth_declining_days,
        breadth_change_observations=int(len(recent_breadth_changes)),
        downside_deviation=downside_deviation,
    )
