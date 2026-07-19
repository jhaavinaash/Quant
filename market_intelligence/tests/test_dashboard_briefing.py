"""Static integration checks for the Personal Market Briefing page."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_PATHS = [
    ROOT / "dashboard" / "app_ai.py",
    ROOT / "quant-center-publish" / "dashboard" / "app_ai.py",
]


class DashboardBriefingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.apps = [
            (path, path.read_text(encoding="utf-8"))
            for path in APP_PATHS
        ]

    def test_required_briefing_sections_are_present(self) -> None:
        required_text = [
            "Market Briefing",
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
        for path, source in self.apps:
            for text in required_text:
                with self.subTest(path=path, text=text):
                    self.assertIn(text, source)

    def test_briefing_loader_uses_only_market_intelligence_pipeline(self) -> None:
        for path, source in self.apps:
            tree = ast.parse(source)
            loader = next(
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_cached_market_briefing"
            )
            loader_source = ast.get_source_segment(source, loader)

            for required in (
                "calculate_market_intelligence",
                "interpret_market_intelligence",
                "determine_driving_mode",
            ):
                with self.subTest(path=path, required=required):
                    self.assertIn(required, loader_source)
            for forbidden in (
                "scan_universe",
                "MASTER_SIGNALS_FILE",
                "ENGINE_STATUS_FILE",
                "TRADES_LOG_FILE",
                "F1",
            ):
                with self.subTest(path=path, forbidden=forbidden):
                    self.assertNotIn(forbidden, loader_source)

    def test_market_briefing_is_first_navigation_tab(self) -> None:
        for path, source in self.apps:
            with self.subTest(path=path):
                self.assertIn(
                    'tab11, tab1, tab2, tab3, tab4, tab5, tab6, tab7, '
                    'tab8, tab9, tab10 = st.tabs([\n    "Market Briefing"',
                    source,
                )

    def test_quant_center_sync_includes_market_intelligence_package(self) -> None:
        sync_script = (ROOT / "scripts" / "sync_quant_center.ps1").read_text(
            encoding="utf-8"
        )
        publish_script = (
            ROOT / "scripts" / "publish_quant_center.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn('"market_intelligence"', sync_script)
        self.assertIn('"market_intelligence"', publish_script)


if __name__ == "__main__":
    unittest.main()
