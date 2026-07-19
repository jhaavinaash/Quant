"""Focused tests for the Market Intelligence foundation."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from market_intelligence import (
    MarketIntelligence,
    MarketIntelligenceConfig,
    MarketIntelligenceEngine,
    calculate_market_intelligence,
)


def _price_frame(days: int = 300) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=days)
    rows = []
    for offset, current_date in enumerate(dates):
        closes = {
            "ALPHA": 100.0 + offset,
            "BETA": 180.0 + 0.4 * offset,
            "GAMMA": 250.0 - 0.3 * offset,
            "DELTA": 140.0 + 5.0 * np.sin(offset / 12.0),
        }
        rows.extend(
            {
                "Date": current_date,
                "Ticker": ticker,
                "Close": close,
            }
            for ticker, close in closes.items()
        )
    return pd.DataFrame(rows)


class FoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prices = _price_frame()
        self.sectors = pd.DataFrame(
            {
                "Ticker": ["ALPHA", "BETA", "GAMMA", "DELTA"],
                "Sector": ["Technology", "Finance", "Finance", "Industrial"],
            }
        )

    def test_engine_returns_four_independent_dimensions(self) -> None:
        result = MarketIntelligenceEngine().calculate(
            self.prices,
            self.sectors,
        )

        self.assertIsInstance(result, MarketIntelligence)
        self.assertEqual(result.universe_size, 4)
        self.assertEqual(result.trend.constituent_count, 4)
        self.assertEqual(result.participation.constituent_count, 4)
        self.assertEqual(result.leadership.sector_count, 3)
        self.assertEqual(result.stress.constituent_count, 4)

        serialized = result.as_dict()
        self.assertEqual(
            set(serialized),
            {
                "as_of",
                "universe_size",
                "trend",
                "participation",
                "leadership",
                "stress",
            },
        )
        self.assertNotIn("driving_mode", serialized)
        self.assertNotIn("score", serialized)

    def test_as_of_uses_only_available_history(self) -> None:
        as_of = pd.Timestamp("2024-10-01")
        result = calculate_market_intelligence(
            self.prices,
            self.sectors,
            as_of=as_of,
        )

        self.assertLessEqual(pd.Timestamp(result.as_of), as_of)
        self.assertEqual(result.as_of, result.trend.as_of)
        self.assertEqual(result.as_of, result.participation.as_of)
        self.assertEqual(result.as_of, result.leadership.as_of)
        self.assertEqual(result.as_of, result.stress.as_of)

    def test_future_prices_cannot_change_as_of_results(self) -> None:
        as_of = pd.Timestamp("2024-10-01")
        original = calculate_market_intelligence(
            self.prices,
            self.sectors,
            as_of=as_of,
        )

        changed = self.prices.copy()
        future = changed["Date"] > as_of
        changed.loc[future, "Close"] = changed.loc[future, "Close"] * 100.0
        recalculated = calculate_market_intelligence(
            changed,
            self.sectors,
            as_of=as_of,
        )

        self.assertEqual(original, recalculated)

    def test_short_history_returns_unavailable_long_metrics(self) -> None:
        config = MarketIntelligenceConfig(
            medium_window=10,
            long_window=40,
            drawdown_window=50,
        )
        result = MarketIntelligenceEngine(config).calculate(
            _price_frame(days=25),
            self.sectors,
        )

        self.assertIsNotNone(result.trend.medium_average)
        self.assertIsNone(result.trend.long_average)
        self.assertIsNone(result.participation.above_long_share)
        self.assertIsNone(result.stress.universe_drawdown)
        self.assertIsNone(result.stress.new_low_share)

    def test_missing_price_columns_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            MarketIntelligenceEngine().calculate(
                self.prices.drop(columns=["Close"])
            )


if __name__ == "__main__":
    unittest.main()
