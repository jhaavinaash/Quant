"""Tests for raw Leadership Quality calculations."""

from __future__ import annotations

import unittest

from market_intelligence import MarketIntelligenceConfig, calculate_leadership
from market_intelligence.tests.fixtures import (
    production_close_prices,
    production_sectors,
    synthetic_close_prices,
)


class LeadershipTests(unittest.TestCase):
    def test_leadership_describes_stock_and_sector_distribution(self) -> None:
        sectors = {
            "ALPHA": "Technology",
            "BETA": "Finance",
            "GAMMA": "Finance",
            "DELTA": "Industrial",
        }
        result = calculate_leadership(
            synthetic_close_prices(),
            MarketIntelligenceConfig(),
            sectors,
        )

        self.assertEqual(result.eligible_constituent_count, 4)
        self.assertEqual(result.sector_count, 3)
        self.assertGreater(result.positive_constituent_count, 0)
        self.assertGreater(result.positive_return_share, 0.0)
        self.assertGreater(result.leadership_concentration, 0.0)
        self.assertLessEqual(result.leadership_concentration, 1.0)
        self.assertGreater(result.effective_leader_count, 0.0)
        self.assertLessEqual(
            result.effective_leader_count,
            result.positive_constituent_count,
        )
        self.assertGreaterEqual(result.positive_sector_share, 0.0)
        self.assertLessEqual(result.positive_sector_share, 1.0)

    def test_production_leadership_has_mapped_sector_coverage(self) -> None:
        result = calculate_leadership(
            production_close_prices(),
            MarketIntelligenceConfig(),
            production_sectors(),
        )

        self.assertGreater(result.eligible_constituent_count, 0)
        self.assertGreater(result.sector_count, 0)
        for share in (
            result.positive_return_share,
            result.positive_sector_share,
        ):
            self.assertIsNotNone(share)
            self.assertGreaterEqual(share, 0.0)
            self.assertLessEqual(share, 1.0)


if __name__ == "__main__":
    unittest.main()
