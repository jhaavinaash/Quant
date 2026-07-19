"""Static integration checks for the Personal Market Briefing page."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[2] / "dashboard" / "app_ai.py"


class DashboardBriefingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = APP_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_required_briefing_sections_are_present(self) -> None:
        required_text = [
            "Today's Market Approach",
            "One-line summary",
            "Daily Market Brief",
            "Why this approach was selected",
            "Key positives",
            "Key risks",
            "Market Conditions",
            "Raw Metrics — Full Transparency",
            "Data date",
            "Universe size",
            "Sector coverage",
            "Last refresh time",
        ]
        for text in required_text:
            with self.subTest(text=text):
                self.assertIn(text, self.source)

    def test_briefing_loader_uses_only_market_intelligence_pipeline(self) -> None:
        loader = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_cached_market_briefing"
        )
        loader_source = ast.get_source_segment(self.source, loader)

        for required in (
            "calculate_market_intelligence",
            "interpret_market_intelligence",
            "determine_driving_mode",
        ):
            self.assertIn(required, loader_source)
        for forbidden in (
            "scan_universe",
            "MASTER_SIGNALS_FILE",
            "ENGINE_STATUS_FILE",
            "TRADES_LOG_FILE",
            "F1",
        ):
            self.assertNotIn(forbidden, loader_source)


if __name__ == "__main__":
    unittest.main()
