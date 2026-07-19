"""Leadership dimension calculation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Optional

import numpy as np
import pandas as pd

from .config import MarketIntelligenceConfig
from .models import LeadershipResult


def _share(numerator: int, denominator: int) -> Optional[float]:
    return None if denominator == 0 else float(numerator / denominator)


def _concentration(
    constituent_returns: pd.Series,
) -> tuple[Optional[float], Optional[float]]:
    positive_returns = constituent_returns[constituent_returns > 0]
    positive_strength = float(positive_returns.sum())
    if positive_returns.empty or positive_strength <= 0:
        return None, None

    weights = positive_returns / positive_strength
    concentration = float(np.square(weights).sum())
    effective_count = None if concentration == 0 else float(1.0 / concentration)
    return concentration, effective_count


def calculate_leadership(
    close_prices: pd.DataFrame,
    config: MarketIntelligenceConfig,
    sectors: Mapping[str, str] | None = None,
) -> LeadershipResult:
    """Calculate how current strength is distributed across stocks and sectors."""

    if close_prices.empty:
        raise ValueError("Leadership calculation requires at least one price row")

    lookback = config.leadership_lookback
    constituent_returns = pd.Series(dtype=float)
    if len(close_prices) > lookback:
        constituent_returns = (
            close_prices.iloc[-1] / close_prices.iloc[-1 - lookback] - 1.0
        ).replace([np.inf, -np.inf], np.nan).dropna()

    positive_count = int((constituent_returns > 0).sum())
    eligible_count = int(len(constituent_returns))
    concentration, effective_count = _concentration(constituent_returns)

    sector_count = 0
    positive_sector_share: Optional[float] = None
    if sectors and not constituent_returns.empty:
        sector_labels = pd.Series(sectors, dtype="object").reindex(
            constituent_returns.index
        )
        mapped = sector_labels.notna()
        if mapped.any():
            sector_returns = constituent_returns[mapped].groupby(
                sector_labels[mapped]
            ).mean()
            sector_count = int(len(sector_returns))
            positive_sector_share = _share(
                int((sector_returns > 0).sum()),
                sector_count,
            )

    return LeadershipResult(
        as_of=close_prices.index[-1].to_pydatetime(),
        lookback=lookback,
        eligible_constituent_count=eligible_count,
        positive_constituent_count=positive_count,
        positive_return_share=_share(positive_count, eligible_count),
        leadership_concentration=concentration,
        effective_leader_count=effective_count,
        sector_count=sector_count,
        positive_sector_share=positive_sector_share,
    )
