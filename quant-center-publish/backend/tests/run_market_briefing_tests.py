"""Market Briefing API adapter verification.

Run: python tests/run_market_briefing_tests.py
Reads repository price/sector fixtures and does not modify production files.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ENCRYPTION_SECRET_KEY", "test-encryption-key")

BACKEND = Path(__file__).resolve().parents[1]
WORKSPACE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(WORKSPACE))

from app.core.config import settings
from app.services.market_briefing_service import MarketBriefingService


class MarketBriefingServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.original_quant_root = settings.QUANT_BASE_DIR
        settings.QUANT_BASE_DIR = str(WORKSPACE)

    @classmethod
    def tearDownClass(cls) -> None:
        settings.QUANT_BASE_DIR = cls.original_quant_root

    def test_snapshot_exposes_existing_pipeline_outputs(self) -> None:
        snapshot = MarketBriefingService.get_snapshot(refresh=True)

        self.assertIn(
            snapshot.approach,
            {"Aggressive", "Normal", "Cautious", "Defensive"},
        )
        self.assertIn(snapshot.confidence, {"High", "Medium", "Low"})
        self.assertTrue(snapshot.oneLineSummary)
        self.assertTrue(snapshot.reason)
        self.assertEqual(
            [dimension.name for dimension in snapshot.dimensions],
            ["Trend", "Participation", "Leadership", "Stress"],
        )
        self.assertGreater(snapshot.universeSize, 0)
        self.assertGreater(snapshot.sectorCoverage, 0)
        self.assertIn("trend", snapshot.rawMetrics)
        self.assertIn("not linked to any specific engine", snapshot.scope)

    def test_cached_snapshot_is_reused_without_refresh(self) -> None:
        refreshed = MarketBriefingService.get_snapshot(refresh=True)
        cached = MarketBriefingService.get_snapshot()

        self.assertIs(refreshed, cached)


if __name__ == "__main__":
    unittest.main()
