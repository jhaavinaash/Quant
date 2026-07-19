"""Thin read-only adapter for the existing Market Intelligence pipeline."""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.schemas.market_briefing import (
    MarketBriefingDimension,
    MarketBriefingHighlight,
    MarketBriefingMetric,
    MarketBriefingSnapshot,
)

_CACHE_TTL_SECONDS = 3600
_CACHE: tuple[float, MarketBriefingSnapshot] | None = None


def _market_intelligence_api() -> dict[str, Any]:
    quant_root = Path(settings.QUANT_BASE_DIR)
    service_file = Path(__file__).resolve()
    candidates = [
        quant_root,
        service_file.parents[2],
        service_file.parents[3],
        service_file.parents[4],
    ]
    for candidate in candidates:
        if (candidate / "market_intelligence").is_dir():
            candidate_text = str(candidate)
            if candidate_text not in sys.path:
                sys.path.insert(0, candidate_text)

    from market_intelligence import (  # type: ignore
        TRADING_APPROACH_SCOPE,
        briefing_highlights,
        briefing_metrics,
        calculate_market_intelligence,
        determine_driving_mode,
        interpret_market_intelligence,
        trading_approach_guidance,
    )

    return {
        "scope": TRADING_APPROACH_SCOPE,
        "briefing_highlights": briefing_highlights,
        "briefing_metrics": briefing_metrics,
        "calculate": calculate_market_intelligence,
        "determine": determine_driving_mode,
        "interpret": interpret_market_intelligence,
        "guidance": trading_approach_guidance,
    }


def _data_file(filename: str) -> Path:
    root = Path(settings.QUANT_BASE_DIR)
    for directory in ("Data", "data"):
        candidate = root / directory / filename
        if candidate.exists():
            return candidate
    return root / "Data" / filename


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame | None]:
    price_file = _data_file("stock_prices_clean.csv")
    sector_file = _data_file("sector_map_fixed.csv")
    if not price_file.exists():
        raise FileNotFoundError(f"Market price history not found: {price_file}")

    prices = pd.read_csv(
        price_file,
        usecols=["Date", "Ticker", "Close"],
    )
    sectors = (
        pd.read_csv(sector_file, usecols=["Ticker", "Sector"])
        if sector_file.exists()
        else None
    )
    return prices, sectors


def _metric_models(api: dict[str, Any], metrics: dict[str, Any]) -> list[MarketBriefingMetric]:
    return [
        MarketBriefingMetric(name=item.name, value=item.value)
        for item in api["briefing_metrics"](metrics)
    ]


def _build_snapshot() -> MarketBriefingSnapshot:
    api = _market_intelligence_api()
    prices, sectors = _load_inputs()

    intelligence = api["calculate"](prices, sectors)
    conditions = api["interpret"](intelligence)
    driving_mode = api["determine"](conditions)
    raw_metrics = intelligence.as_dict()
    positives, risks = api["briefing_highlights"](conditions)

    condition_rows = [
        ("Trend", conditions.trend, raw_metrics["trend"]),
        ("Participation", conditions.participation, raw_metrics["participation"]),
        ("Leadership", conditions.leadership, raw_metrics["leadership"]),
        ("Stress", conditions.stress, raw_metrics["stress"]),
    ]
    dimensions = [
        MarketBriefingDimension(
            name=name,
            state=condition.state.value,
            explanation=condition.explanation,
            metrics=_metric_models(api, metrics),
        )
        for name, condition, metrics in condition_rows
    ]

    now = datetime.now().astimezone()
    return MarketBriefingSnapshot(
        scope=api["scope"],
        approach=driving_mode.mode.value,
        confidence=driving_mode.confidence.value,
        oneLineSummary=api["guidance"](driving_mode.mode),
        reason=driving_mode.reason,
        keyPositives=[
            MarketBriefingHighlight(
                dimension=item.dimension,
                state=item.state,
                explanation=item.explanation,
            )
            for item in positives
        ],
        keyRisks=[
            MarketBriefingHighlight(
                dimension=item.dimension,
                state=item.state,
                explanation=item.explanation,
            )
            for item in risks
        ],
        dimensions=dimensions,
        rawMetrics=raw_metrics,
        dataDate=intelligence.as_of.strftime("%d %b %Y"),
        universeSize=intelligence.universe_size,
        sectorCoverage=intelligence.leadership.sector_count,
        lastRefreshTime=now.strftime("%d %b %Y · %H:%M:%S"),
    )


class MarketBriefingService:
    """Expose existing Market Intelligence outputs without changing them."""

    @classmethod
    def get_snapshot(cls, refresh: bool = False) -> MarketBriefingSnapshot:
        global _CACHE

        now = time.monotonic()
        if (
            not refresh
            and _CACHE is not None
            and now - _CACHE[0] < _CACHE_TTL_SECONDS
        ):
            return _CACHE[1]

        snapshot = _build_snapshot()
        _CACHE = (now, snapshot)
        return snapshot
