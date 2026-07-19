"""Shared synthetic and production-data fixtures for dimension tests."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def synthetic_close_prices(days: int = 300) -> pd.DataFrame:
    """Return deterministic close history with varied constituent behavior."""

    dates = pd.bdate_range("2024-01-01", periods=days)
    offsets = np.arange(days, dtype=float)
    return pd.DataFrame(
        {
            "ALPHA": 100.0 + offsets,
            "BETA": 180.0 + 0.4 * offsets,
            "GAMMA": 250.0 - 0.3 * offsets,
            "DELTA": 140.0 + 5.0 * np.sin(offsets / 12.0),
        },
        index=dates,
    )


@lru_cache(maxsize=1)
def production_close_prices() -> pd.DataFrame:
    """Load the repository's production price history as a close matrix."""

    prices = pd.read_csv(
        ROOT / "Data" / "stock_prices_clean.csv",
        usecols=["Date", "Ticker", "Close"],
        parse_dates=["Date"],
    )
    prices["Close"] = pd.to_numeric(prices["Close"], errors="coerce")
    prices = prices.dropna(subset=["Date", "Ticker", "Close"])
    return prices.pivot_table(
        index="Date",
        columns="Ticker",
        values="Close",
        aggfunc="last",
    ).sort_index()


@lru_cache(maxsize=1)
def production_sectors() -> dict[str, str]:
    """Load the repository's production ticker-to-sector mapping."""

    sectors = pd.read_csv(
        ROOT / "Data" / "sector_map_fixed.csv",
        usecols=["Ticker", "Sector"],
    ).dropna()
    return dict(zip(sectors["Ticker"], sectors["Sector"]))
