"""Tests for raw Participation and Breadth calculations."""

from __future__ import annotations

import unittest

from market_intelligence import MarketIntelligenceConfig, calculate_participation
from market_intelligence.tests.fixtures import (
    production_close_prices,
    synthetic_close_prices,
)


class ParticipationTests(unittest.TestCase):
    def test_participation_returns_counts_shares_and_change(self) -> None:
        result = calculate_participation(
            synthetic_close_prices(),
            MarketIntelligenceConfig(),
        )

        self.assertEqual(result.constituent_count, 4)
        self.assertEqual(result.medium_coverage, 4)
        self.assertEqual(result.long_coverage, 4)
        self.assertGreaterEqual(result.above_medium_count, 0)
        self.assertLessEqual(result.above_medium_count, result.medium_coverage)
        self.assertGreaterEqual(result.above_medium_share, 0.0)
        self.assertLessEqual(result.above_medium_share, 1.0)
        self.assertIsNotNone(result.medium_breadth_change)

    def test_production_participation_is_bounded_and_covered(self) -> None:
        result = calculate_participation(
            production_close_prices(),
            MarketIntelligenceConfig(),
        )

        self.assertGreater(result.medium_coverage, 0)
        self.assertGreater(result.long_coverage, 0)
        for share in (result.above_medium_share, result.above_long_share):
            self.assertIsNotNone(share)
            self.assertGreaterEqual(share, 0.0)
            self.assertLessEqual(share, 1.0)
        self.assertIsNotNone(result.medium_breadth_change)
        self.assertGreaterEqual(result.medium_breadth_change, -1.0)
        self.assertLessEqual(result.medium_breadth_change, 1.0)


if __name__ == "__main__":
    unittest.main()
