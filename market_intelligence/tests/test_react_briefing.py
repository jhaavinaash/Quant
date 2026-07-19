"""Static contract checks for the React Market Briefing integration."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ReactBriefingIntegrationTests(unittest.TestCase):
    def test_dashboard_consumes_market_briefing_service(self) -> None:
        dashboard = (
            ROOT
            / "quant-center-publish"
            / "frontend"
            / "src"
            / "views"
            / "Dashboard.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("marketBriefingService.getSnapshot", dashboard)
        self.assertIn("<MarketBriefingPanel", dashboard)
        self.assertIn("snapshot.dimensions.map", dashboard)
        self.assertIn("snapshot.rawMetrics", dashboard)

    def test_frontend_service_uses_read_only_endpoint(self) -> None:
        service = (
            ROOT
            / "quant-center-publish"
            / "frontend"
            / "src"
            / "services"
            / "marketBriefingService.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("api.get<MarketBriefingSnapshot>('/market-briefing'", service)
        self.assertNotIn("api.post", service)

    def test_backend_adapter_calls_existing_pipeline(self) -> None:
        service = (
            ROOT
            / "quant-center-publish"
            / "backend"
            / "app"
            / "services"
            / "market_briefing_service.py"
        ).read_text(encoding="utf-8")

        self.assertIn('"calculate": calculate_market_intelligence', service)
        self.assertIn('"interpret": interpret_market_intelligence', service)
        self.assertIn('"determine": determine_driving_mode', service)
        self.assertNotIn(".rolling(", service)
        self.assertNotIn("DrivingModeRules", service)


if __name__ == "__main__":
    unittest.main()
