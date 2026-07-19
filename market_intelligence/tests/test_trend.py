"""Tests for raw Trend Structure calculations."""

from __future__ import annotations

import math
import unittest

from market_intelligence import MarketIntelligenceConfig, calculate_trend
from market_intelligence.tests.fixtures import (
    production_close_prices,
    synthetic_close_prices,
)


class TrendTests(unittest.TestCase):
    def test_rising_universe_has_positive_trend_distances(self) -> None:
        result = calculate_trend(
            synthetic_close_prices(),
            MarketIntelligenceConfig(),
        )

        self.assertIsNotNone(result.medium_average)
        self.assertIsNotNone(result.long_average)
        self.assertGreater(result.distance_from_medium, 0.0)
        self.assertGreater(result.distance_from_long, 0.0)

    def test_production_metrics_are_finite_when_history_is_available(self) -> None:
        result = calculate_trend(
            production_close_prices(),
            MarketIntelligenceConfig(),
        )

        self.assertGreater(result.constituent_count, 0)
        self.assertGreater(result.universe_level, 0.0)
        for value in (
            result.medium_average,
            result.long_average,
            result.distance_from_medium,
            result.distance_from_long,
        ):
            self.assertIsNotNone(value)
            self.assertTrue(math.isfinite(value))


if __name__ == "__main__":
    unittest.main()
