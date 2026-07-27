"""
AI Scanner Live Watch — behavioural verification (temp DB + mocked email/scanner).

Run: python tests/run_ai_scanner_watch_tests.py
Does NOT send real email or write production ai_scanner_events.db / ai_paper_trades.csv.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.ai_scanner_event_store import AIScannerEventStore, get_event_store
from app.services.ai_scanner_market_session import (
    SCAN_SLOTS,
    due_scan_slot,
    is_auto_scan_window,
    next_scheduled_slot,
    slot_datetime,
)
from app.services.ai_scanner_opportunity_pipeline import process_qualifying_opportunities

IST = ZoneInfo("Asia/Kolkata")


@dataclass
class MockScanResult:
    ticker: str
    action: str = "STRONG BUY"
    composite_score: float = 80.0
    groups_fired: int = 4
    suggested_entry: float = 100.0
    suggested_stop: float = 95.0
    suggested_target: float = 115.0
    suggested_qty: int = 150
    max_risk_inr: float = 750.0
    sector: str = "Test"
    bull_signals: list[str] = field(default_factory=lambda: ["Trend up", "RS strong"])


def _scan(strong: list[MockScanResult]) -> dict[str, Any]:
    return {"strong_buys": strong, "watchlist": [], "exits": [], "all_results": strong}


class WatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db = Path(self._tmpdir.name) / "test_events.db"
        self.store = get_event_store(self.db)
        self.emails: list[tuple[str, str]] = []

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _send(self, subject: str, body: str) -> bool:
        self.emails.append((subject, body))
        return getattr(self, "_email_ok", True)

    def test_01_first_detection(self) -> None:
        pipe = process_qualifying_opportunities(
            _scan([MockScanResult("SFL.NS")]),
            scan_source="AUTO",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-15",
        )
        self.assertEqual(pipe.events_created, 1)
        self.assertEqual(self.store.count_for_trading_date("2026-07-15"), 1)
        self.assertEqual(len(self.emails), 1)

    def test_02_same_day_auto_duplicate(self) -> None:
        self.test_01_first_detection()
        self.emails.clear()
        pipe = process_qualifying_opportunities(
            _scan([MockScanResult("SFL.NS")]),
            scan_source="AUTO",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-15",
        )
        self.assertEqual(pipe.events_created, 0)
        self.assertEqual(self.store.count_for_trading_date("2026-07-15"), 1)
        self.assertEqual(len(self.emails), 0)

    def test_03_same_day_manual_duplicate(self) -> None:
        self.test_01_first_detection()
        self.emails.clear()
        pipe = process_qualifying_opportunities(
            _scan([MockScanResult("SFL.NS")]),
            scan_source="MANUAL",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-15",
        )
        self.assertEqual(pipe.events_created, 0)
        self.assertEqual(len(self.emails), 0)

    def test_04_restart_safety(self) -> None:
        self.test_01_first_detection()
        store2 = AIScannerEventStore(self.db)
        store2.init_schema()
        self.emails.clear()
        pipe = process_qualifying_opportunities(
            _scan([MockScanResult("SFL.NS")]),
            scan_source="AUTO",
            store=store2,
            email_sender=self._send,
            trading_date="2026-07-15",
        )
        self.assertEqual(pipe.events_created, 0)
        self.assertEqual(len(self.emails), 0)

    def test_05_future_date(self) -> None:
        self.test_01_first_detection()
        self.emails.clear()
        pipe = process_qualifying_opportunities(
            _scan([MockScanResult("SFL.NS")]),
            scan_source="AUTO",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-25",
        )
        self.assertEqual(pipe.events_created, 1)
        self.assertEqual(len(self.emails), 1)
        self.assertEqual(self.store.count_for_trading_date("2026-07-25"), 1)

    def test_06_two_tickers(self) -> None:
        pipe = process_qualifying_opportunities(
            _scan([MockScanResult("SFL.NS"), MockScanResult("ALKEM.NS")]),
            scan_source="AUTO",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-16",
        )
        self.assertEqual(pipe.events_created, 2)
        self.assertEqual(len(self.emails), 2)

    def test_07_email_failure(self) -> None:
        self._email_ok = False
        pipe = process_qualifying_opportunities(
            _scan([MockScanResult("SFL.NS")]),
            scan_source="AUTO",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-17",
        )
        self.assertEqual(pipe.events_created, 1)
        ev = self.store.get_by_trading_date_ticker("2026-07-17", "SFL.NS")
        assert ev
        self.assertEqual(ev.email_status, "FAILED")

    def test_08_failed_retry_while_qualifying(self) -> None:
        self._email_ok = False
        process_qualifying_opportunities(
            _scan([MockScanResult("SFL.NS")]),
            scan_source="AUTO",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-18",
        )
        self._email_ok = True
        self.emails.clear()
        pipe = process_qualifying_opportunities(
            _scan([MockScanResult("SFL.NS")]),
            scan_source="AUTO",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-18",
        )
        self.assertEqual(pipe.events_created, 0)
        self.assertEqual(len(self.emails), 1)
        ev = self.store.get_by_trading_date_ticker("2026-07-18", "SFL.NS")
        assert ev
        self.assertEqual(ev.email_status, "SENT")

    def test_09_failed_no_longer_qualifying(self) -> None:
        self._email_ok = False
        process_qualifying_opportunities(
            _scan([MockScanResult("SFL.NS")]),
            scan_source="AUTO",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-19",
        )
        self.emails.clear()
        pipe = process_qualifying_opportunities(
            _scan([]),
            scan_source="AUTO",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-19",
        )
        self.assertEqual(pipe.events_created, 0)
        self.assertEqual(len(self.emails), 0)
        ev = self.store.get_by_trading_date_ticker("2026-07-19", "SFL.NS")
        assert ev
        self.assertEqual(ev.email_status, "FAILED")

    def test_10_watchlist_only(self) -> None:
        wl = MockScanResult("WATCH.NS", action="WATCH", composite_score=68.0, groups_fired=2)
        pipe = process_qualifying_opportunities(
            {"strong_buys": [], "watchlist": [wl], "all_results": [wl]},
            scan_source="AUTO",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-20",
        )
        self.assertEqual(pipe.events_created, 0)
        self.assertEqual(len(self.emails), 0)

    def test_11_paper_trade_isolation(self) -> None:
        quant = Path(os.environ.get("QUANT_BASE_DIR", r"C:\Users\Avinaash\Quant"))
        paper = quant / "data" / "ai_paper_trades.csv"
        before = hashlib.sha256(paper.read_bytes()).hexdigest() if paper.exists() else ""
        rows_before = len(paper.read_text().splitlines()) if paper.exists() else 0
        process_qualifying_opportunities(
            _scan([MockScanResult("SFL.NS")]),
            scan_source="AUTO",
            store=self.store,
            email_sender=self._send,
            trading_date="2026-07-21",
        )
        after = hashlib.sha256(paper.read_bytes()).hexdigest() if paper.exists() else ""
        rows_after = len(paper.read_text().splitlines()) if paper.exists() else 0
        self.assertEqual(before, after)
        self.assertEqual(rows_before, rows_after)

    def test_12_scanner_core_parity_marker(self) -> None:
        """Verify core/ai_scanner.py STRONG BUY constants unchanged."""
        quant = Path(os.environ.get("QUANT_BASE_DIR", r"C:\Users\Avinaash\Quant"))
        src = (quant / "core" / "ai_scanner.py").read_text(encoding="utf-8")
        self.assertIn("STRONG_BUY_SCORE = 75", src)
        self.assertIn("STRONG_BUY_GROUPS = 4", src)
        self.assertIn('action = "STRONG BUY"', src)
        self.assertIn("composite >= STRONG_BUY_SCORE and groups_fired >= STRONG_BUY_GROUPS", src)

    def test_13_schedule_0930_to_1530_every_30_min(self) -> None:
        """Contract: 09:30–15:30 IST inclusive, every 30 minutes (13 slots)."""
        self.assertEqual(SCAN_SLOTS[0], time(9, 30))
        self.assertEqual(SCAN_SLOTS[-1], time(15, 30))
        self.assertEqual(len(SCAN_SLOTS), 13)
        for i in range(1, len(SCAN_SLOTS)):
            prev = datetime.combine(date(2026, 7, 27), SCAN_SLOTS[i - 1])
            cur = datetime.combine(date(2026, 7, 27), SCAN_SLOTS[i])
            self.assertEqual((cur - prev), timedelta(minutes=30))

    def test_14_due_slot_includes_1530_with_grace(self) -> None:
        """15:30 slot must still be due a few minutes after the hour."""
        # Monday 2026-07-27
        at_slot = datetime(2026, 7, 27, 15, 30, 0, tzinfo=IST)
        late = datetime(2026, 7, 27, 15, 40, 0, tzinfo=IST)
        self.assertTrue(is_auto_scan_window(at_slot))
        self.assertTrue(is_auto_scan_window(late))
        self.assertEqual(due_scan_slot(at_slot), slot_datetime(date(2026, 7, 27), time(15, 30)))
        self.assertEqual(due_scan_slot(late), slot_datetime(date(2026, 7, 27), time(15, 30)))

    def test_15_late_wake_still_catches_0930(self) -> None:
        """90s was too tight — a 5-minute late wake must still fire 09:30."""
        late = datetime(2026, 7, 27, 9, 35, 0, tzinfo=IST)
        self.assertEqual(due_scan_slot(late), slot_datetime(date(2026, 7, 27), time(9, 30)))
        nxt = next_scheduled_slot(late)
        self.assertEqual(nxt, slot_datetime(date(2026, 7, 27), time(10, 0)))


def run_all() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WatchTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(run_all())
