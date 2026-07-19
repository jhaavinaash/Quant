"""Orchestration for the four independent Market Intelligence dimensions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Optional, Union

import numpy as np
import pandas as pd

from .config import MarketIntelligenceConfig
from .leadership import calculate_leadership
from .models import MarketIntelligence
from .participation import calculate_participation
from .stress import calculate_stress
from .trend import calculate_trend

AsOf = Optional[Union[str, date, datetime, pd.Timestamp]]


def _prepare_close_prices(
    prices: pd.DataFrame,
    config: MarketIntelligenceConfig,
    as_of: AsOf,
) -> pd.DataFrame:
    required = {
        config.date_column,
        config.ticker_column,
        config.close_column,
    }
    missing = sorted(required.difference(prices.columns))
    if missing:
        raise ValueError(f"Price data is missing required columns: {missing}")

    selected = prices[
        [config.date_column, config.ticker_column, config.close_column]
    ].copy()
    selected[config.date_column] = pd.to_datetime(
        selected[config.date_column],
        errors="coerce",
    )
    selected[config.ticker_column] = (
        selected[config.ticker_column].astype("string").str.strip()
    )
    selected[config.close_column] = pd.to_numeric(
        selected[config.close_column],
        errors="coerce",
    )
    selected = selected.dropna(
        subset=[
            config.date_column,
            config.ticker_column,
            config.close_column,
        ]
    )
    selected = selected[
        (selected[config.ticker_column] != "")
        & (selected[config.close_column] > 0)
    ]

    if as_of is not None:
        as_of_timestamp = pd.Timestamp(as_of)
        if as_of_timestamp.tzinfo is not None:
            as_of_timestamp = as_of_timestamp.tz_localize(None)
        selected = selected[selected[config.date_column] <= as_of_timestamp]

    if selected.empty:
        raise ValueError("No valid price observations are available")

    selected = selected.sort_values(config.date_column).drop_duplicates(
        [config.date_column, config.ticker_column],
        keep="last",
    )
    close_prices = selected.pivot(
        index=config.date_column,
        columns=config.ticker_column,
        values=config.close_column,
    ).sort_index()
    close_prices = close_prices.replace([np.inf, -np.inf], np.nan).dropna(how="all")
    close_prices.columns.name = None

    if close_prices.empty:
        raise ValueError("No valid close-price matrix could be constructed")
    return close_prices


def _prepare_sectors(
    sectors: pd.DataFrame | Mapping[str, str] | None,
    config: MarketIntelligenceConfig,
) -> dict[str, str]:
    if sectors is None:
        return {}
    if isinstance(sectors, Mapping):
        return {
            str(ticker).strip(): str(sector).strip()
            for ticker, sector in sectors.items()
            if str(ticker).strip() and str(sector).strip()
        }

    required = {config.sector_ticker_column, config.sector_column}
    missing = sorted(required.difference(sectors.columns))
    if missing:
        raise ValueError(f"Sector data is missing required columns: {missing}")

    selected = sectors[
        [config.sector_ticker_column, config.sector_column]
    ].dropna().copy()
    selected[config.sector_ticker_column] = (
        selected[config.sector_ticker_column].astype("string").str.strip()
    )
    selected[config.sector_column] = (
        selected[config.sector_column].astype("string").str.strip()
    )
    selected = selected[
        (selected[config.sector_ticker_column] != "")
        & (selected[config.sector_column] != "")
    ].drop_duplicates(config.sector_ticker_column, keep="last")
    return dict(
        zip(
            selected[config.sector_ticker_column],
            selected[config.sector_column],
        )
    )


class MarketIntelligenceEngine:
    """Calculate the four foundation dimensions from current universe data."""

    def __init__(
        self,
        config: MarketIntelligenceConfig | None = None,
    ) -> None:
        self.config = config or MarketIntelligenceConfig()

    def calculate(
        self,
        prices: pd.DataFrame,
        sectors: pd.DataFrame | Mapping[str, str] | None = None,
        *,
        as_of: AsOf = None,
    ) -> MarketIntelligence:
        """Return one structured result without interpretation or decisions."""

        close_prices = _prepare_close_prices(prices, self.config, as_of)
        sector_mapping = _prepare_sectors(sectors, self.config)

        trend = calculate_trend(close_prices, self.config)
        participation = calculate_participation(close_prices, self.config)
        leadership = calculate_leadership(
            close_prices,
            self.config,
            sector_mapping,
        )
        stress = calculate_stress(close_prices, self.config)

        as_of_datetime = close_prices.index[-1].to_pydatetime()
        return MarketIntelligence(
            as_of=as_of_datetime,
            universe_size=int(close_prices.iloc[-1].notna().sum()),
            trend=trend,
            participation=participation,
            leadership=leadership,
            stress=stress,
        )


def calculate_market_intelligence(
    prices: pd.DataFrame,
    sectors: pd.DataFrame | Mapping[str, str] | None = None,
    *,
    as_of: AsOf = None,
    config: MarketIntelligenceConfig | None = None,
) -> MarketIntelligence:
    """Convenience public API for a one-off foundation calculation."""

    return MarketIntelligenceEngine(config).calculate(
        prices,
        sectors,
        as_of=as_of,
    )
