"""Tests for raw Market Stress calculations."""

from __future__ import annotations

import unittest

from market_intelligence import MarketIntelligenceConfig, calculate_stress
from market_intelligence.tests.fixtures import (
    production_close_prices,
    synthetic_close_prices,
)


class StressTests(unittest.TestCase):
    def test_stress_returns_damage_and_downside_measurements(self) -> None:
        result = calculate_stress(
            synthetic_close_prices(),
            MarketIntelligenceConfig(),
        )

        self.assertIsNotNone(result.universe_drawdown)
        self.assertGreaterEqual(result.universe_drawdown, 0.0)
        self.assertIsNotNone(result.new_low_share)
        self.assertGreaterEqual(result.new_low_share, 0.0)
        self.assertLessEqual(result.new_low_share, 1.0)
        self.assertIsNotNone(result.persistent_breadth_change)
        self.assertLessEqual(
            result.breadth_declining_days,
            result.breadth_change_observations,
        )
        self.assertIsNotNone(result.downside_deviation)
        self.assertGreaterEqual(result.downside_deviation, 0.0)

    def test_production_stress_metrics_are_bounded(self) -> None:
        result = calculate_stress(
            production_close_prices(),
            MarketIntelligenceConfig(),
        )

        self.assertGreater(result.constituent_count, 0)
        self.assertIsNotNone(result.universe_drawdown)
        self.assertGreaterEqual(result.universe_drawdown, 0.0)
        self.assertLessEqual(result.universe_drawdown, 1.0)
        self.assertIsNotNone(result.new_low_share)
        self.assertGreaterEqual(result.new_low_share, 0.0)
        self.assertLessEqual(result.new_low_share, 1.0)
        self.assertIsNotNone(result.persistent_breadth_change)
        self.assertGreaterEqual(result.persistent_breadth_change, -1.0)
        self.assertLessEqual(result.persistent_breadth_change, 1.0)
        self.assertIsNotNone(result.downside_deviation)
        self.assertGreaterEqual(result.downside_deviation, 0.0)


if __name__ == "__main__":
    unittest.main()
