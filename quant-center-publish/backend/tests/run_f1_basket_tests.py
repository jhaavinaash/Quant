"""
F1 Basket Phase 1 — behavioural verification (temp SQLite + mocked F1 decisions).

Run: python tests/run_f1_basket_tests.py
Does NOT modify production f1_decisions.csv, trades_log.csv, open_positions.csv, or signal_layer.db.
"""

from __future__ import annotations

import math
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.f1_basket.allocation import allocate_equal_weight
from app.services.f1_basket.constants import (
    BASKET_SIZE,
    BUY_COST_PCT,
    HARD_STOP_PCT,
    INITIAL_CAPITAL,
    PROFIT_TARGET_PCT,
    SELL_COST_PCT,
)
from app.services.f1_basket.selection import (
    eligibility_from_candidates,
    extract_buy_candidates,
    select_top_n,
)
from app.services.f1_basket.store import F1BasketStore, get_basket_store
from app.services.f1_basket.valuation import evaluate_trigger, value_basket
from app.services.f1_basket_service import F1BasketService


def _mock_df(
    rows: list[dict],
    *,
    timestamp: str = "2026-07-15 09:00:00",
) -> pd.DataFrame:
    base = {
        "Timestamp": timestamp,
        "Ticker": "",
        "Action": "BUY",
        "PortfolioRank": 1,
        "TechnicalState": "OK",
        "SectorState": "OK",
        "BusinessGate": "PASS",
        "Sector": "Test",
        "Close": 100.0,
    }
    out = []
    for r in rows:
        row = {**base, **r}
        out.append(row)
    return pd.DataFrame(out)


def _buy_rows(n: int, *, start_rank: int = 1, price: float = 100.0) -> list[dict]:
    return [
        {
            "Ticker": f"T{i}.NS",
            "PortfolioRank": start_rank + i - 1,
            "Close": price + i,
        }
        for i in range(1, n + 1)
    ]


class F1BasketTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test_f1_basket.db"
        self.store = get_basket_store(self.db_path)
        self._patcher_store = patch(
            "app.services.f1_basket_service.get_basket_store",
            return_value=self.store,
        )
        self._patcher_store.start()

    def tearDown(self) -> None:
        self._patcher_store.stop()
        self._tmpdir.cleanup()

    def _patch_decisions(self, df: pd.DataFrame) -> None:
        self._df_patcher = patch(
            "app.services.f1_basket_service.load_f1_decisions_df",
            return_value=df,
        )
        self._df_patcher.start()
        self.addCleanup(self._df_patcher.stop)

    def test_01_ten_buy_candidates_not_ready(self) -> None:
        df = _mock_df(_buy_rows(10))
        candidates, ts, total = extract_buy_candidates(df)
        el = eligibility_from_candidates(candidates, ts, total)
        self.assertEqual(el["status"], "NOT_READY")
        self.assertEqual(el["available_candidates"], 10)
        self.assertEqual(el["required_constituents"], 12)
        self.assertEqual(el["missing_candidates"], 2)
        self.assertFalse(el["ready"])
        self._patch_decisions(df)
        snap = F1BasketService.create_preview()
        self.assertIsNone(snap.preview)
        self.assertIn("NOT_READY", snap.message)

    def test_02_exactly_twelve_buy_ready_preview(self) -> None:
        df = _mock_df(_buy_rows(12))
        self._patch_decisions(df)
        snap = F1BasketService.create_preview()
        self.assertIsNotNone(snap.preview)
        self.assertEqual(snap.preview.status, "READY")
        self.assertEqual(len(snap.preview.constituents), 12)
        ranks = [c.portfolioRank for c in snap.preview.constituents]
        self.assertEqual(ranks, list(range(1, 13)))

    def test_03_more_than_twelve_top_only(self) -> None:
        df = _mock_df(_buy_rows(15))
        candidates, _, _ = extract_buy_candidates(df)
        selected = select_top_n(candidates)
        self.assertEqual(len(selected), 12)
        self.assertEqual([c.ticker for c in selected], [f"T{i}.NS" for i in range(1, 13)])
        self.assertNotIn("T13.NS", [c.ticker for c in selected])

    def test_04_non_buy_exclusion(self) -> None:
        rows = _buy_rows(8) + [
            {"Ticker": "W1.NS", "Action": "WATCH", "PortfolioRank": 0},
            {"Ticker": "R1.NS", "Action": "ROTATE", "PortfolioRank": 0},
            {"Ticker": "B1.NS", "Action": "BLOCK", "PortfolioRank": 0},
            {"Ticker": "I1.NS", "Action": "IGNORE", "PortfolioRank": 0},
        ]
        df = _mock_df(rows)
        candidates, _, _ = extract_buy_candidates(df)
        self.assertEqual(len(candidates), 8)
        tickers = {c.ticker for c in candidates}
        self.assertTrue(all(t.startswith("T") for t in tickers))

    def test_05_equal_weight_allocation(self) -> None:
        df = _mock_df(_buy_rows(12, price=100.0))
        candidates, _, _ = extract_buy_candidates(df)
        selected = select_top_n(candidates)
        alloc = allocate_equal_weight(
            selected,
            INITIAL_CAPITAL,
            basket_size=BASKET_SIZE,
            profit_target_pct=PROFIT_TARGET_PCT,
            hard_stop_pct=HARD_STOP_PCT,
        )
        self.assertEqual(len(alloc.constituents), 12)
        for c in alloc.constituents:
            self.assertAlmostEqual(c.target_weight, 1.0 / 12, places=6)
            slot = INITIAL_CAPITAL / 12
            equal_weight_allocation = slot / (1.0 + BUY_COST_PCT)
            expected_qty = math.floor(equal_weight_allocation / c.reference_price)
            self.assertEqual(c.quantity, expected_qty)
            self.assertEqual(c.quantity, int(c.quantity))
            self.assertAlmostEqual(
                c.gross_buy_value, c.quantity * c.reference_price, places=2
            )

    def test_06_transaction_cost_buy(self) -> None:
        df = _mock_df(_buy_rows(12, price=200.0))
        candidates, _, _ = extract_buy_candidates(df)
        alloc = allocate_equal_weight(
            select_top_n(candidates),
            INITIAL_CAPITAL,
            basket_size=BASKET_SIZE,
            profit_target_pct=PROFIT_TARGET_PCT,
            hard_stop_pct=HARD_STOP_PCT,
        )
        slot = INITIAL_CAPITAL / 12
        for c in alloc.constituents:
            gross_buy_value = c.quantity * c.reference_price
            fee = gross_buy_value * BUY_COST_PCT
            self.assertAlmostEqual(c.estimated_buy_cost, fee, places=2)
            self.assertAlmostEqual(
                c.estimated_total_entry_cost, gross_buy_value + fee, places=2
            )

    def test_07_basket_start_value(self) -> None:
        df = _mock_df(_buy_rows(12, price=150.0))
        candidates, _, _ = extract_buy_candidates(df)
        alloc = allocate_equal_weight(
            select_top_n(candidates),
            INITIAL_CAPITAL,
            basket_size=BASKET_SIZE,
            profit_target_pct=PROFIT_TARGET_PCT,
            hard_stop_pct=HARD_STOP_PCT,
        )
        expected_start = sum(c.gross_buy_value for c in alloc.constituents)
        self.assertAlmostEqual(alloc.basket_start_value, expected_start, places=2)
        self.assertAlmostEqual(alloc.basket_start_value, alloc.allocated_capital, places=2)

    def test_08_target_trigger(self) -> None:
        start = 100_000.0
        target_val = start * 1.12
        self.assertEqual(
            evaluate_trigger(target_val, start, PROFIT_TARGET_PCT, HARD_STOP_PCT),
            "TARGET",
        )

    def test_09_stop_trigger(self) -> None:
        start = 100_000.0
        stop_val = start * 0.85
        self.assertEqual(
            evaluate_trigger(stop_val, start, PROFIT_TARGET_PCT, HARD_STOP_PCT),
            "STOP",
        )

    def test_10_no_trigger(self) -> None:
        start = 100_000.0
        mid = start * 1.05
        self.assertEqual(
            evaluate_trigger(mid, start, PROFIT_TARGET_PCT, HARD_STOP_PCT),
            "NONE",
        )

    def test_11_f1_action_changes_snapshot_unchanged(self) -> None:
        df1 = _mock_df(_buy_rows(12), timestamp="2026-07-15 09:00:00")
        self._patch_decisions(df1)
        snap1 = F1BasketService.create_preview()
        assert snap1.preview
        orig_tickers = [c.ticker for c in snap1.preview.constituents]
        orig_ranks = [c.portfolioRank for c in snap1.preview.constituents]

        rows = _buy_rows(12)
        rows[0]["Action"] = "ROTATE"
        rows[1]["Action"] = "BLOCK"
        for i, r in enumerate(rows):
            r["PortfolioRank"] = 99 - i
        df2 = _mock_df(rows, timestamp="2026-07-16 09:00:00")
        self._df_patcher.stop()
        self._patch_decisions(df2)

        snap2 = F1BasketService.get_snapshot()
        assert snap2.preview
        self.assertEqual([c.ticker for c in snap2.preview.constituents], orig_tickers)
        self.assertEqual([c.portfolioRank for c in snap2.preview.constituents], orig_ranks)
        self.assertEqual(snap2.preview.currentTrigger, "NONE")

    def test_12_preview_stale(self) -> None:
        df1 = _mock_df(_buy_rows(12), timestamp="2026-07-15 09:00:00")
        self._patch_decisions(df1)
        snap1 = F1BasketService.create_preview()
        assert snap1.preview
        self.assertFalse(snap1.preview.previewStale)

        df2 = _mock_df(_buy_rows(12), timestamp="2026-07-16 10:00:00")
        self._df_patcher.stop()
        self._patch_decisions(df2)
        snap2 = F1BasketService.get_snapshot()
        assert snap2.preview
        self.assertTrue(snap2.preview.previewStale)
        self.assertEqual(snap2.preview.selectionSnapshotTimestamp, "2026-07-15 09:00:00")
        self.assertEqual(snap2.preview.currentF1DecisionTimestamp, "2026-07-16 10:00:00")

    def test_13_rebuild_preview(self) -> None:
        df1 = _mock_df(_buy_rows(12), timestamp="2026-07-15 09:00:00")
        self._patch_decisions(df1)
        F1BasketService.create_preview()

        rows = _buy_rows(14)
        for i, r in enumerate(rows):
            r["PortfolioRank"] = i + 1
        rows.append({"Ticker": "NEW.NS", "PortfolioRank": 0, "Close": 50.0})
        df2 = _mock_df(rows, timestamp="2026-07-16 09:00:00")
        self._df_patcher.stop()
        self._patch_decisions(df2)

        rebuilt = F1BasketService.rebuild_preview()
        assert rebuilt.preview
        tickers = [c.ticker for c in rebuilt.preview.constituents]
        self.assertEqual(tickers[0], "NEW.NS")
        self.assertEqual(len(tickers), 12)

    def test_14_duplicate_ticker_protection(self) -> None:
        df = _mock_df(_buy_rows(12))
        candidates, ts, _ = extract_buy_candidates(df)
        alloc = allocate_equal_weight(
            select_top_n(candidates),
            INITIAL_CAPITAL,
            basket_size=BASKET_SIZE,
            profit_target_pct=PROFIT_TARGET_PCT,
            hard_stop_pct=HARD_STOP_PCT,
        )
        bid = self.store.create_preview_basket(allocation=alloc, f1_timestamp=ts)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO f1_basket_constituents (
                        basket_id, ticker, selection_order, reference_price,
                        target_weight, allocated_amount, quantity,
                        gross_buy_value, estimated_buy_cost, estimated_total_entry_cost,
                        held_globally_at_selection, created_at, updated_at
                    ) VALUES (?, ?, 99, 100, 0.0833, 25000, 1, 24925, 75, 25000, 0, 'x', 'x')
                    """,
                    (bid, alloc.constituents[0].ticker),
                )

    def test_15_held_ticker_visibility(self) -> None:
        rows = _buy_rows(12)
        rows[0]["Ticker"] = "HELD.NS"
        df = _mock_df(rows)
        with patch(
            "app.services.f1_basket.selection._load_held_tickers",
            return_value={"HELD"},
        ):
            candidates, _, _ = extract_buy_candidates(df)
        self.assertEqual(len(candidates), 12)
        held = [c for c in candidates if c.ticker == "HELD.NS"][0]
        self.assertTrue(held.held_globally)
        self.assertTrue(held.held_conflict)
        self.assertEqual(candidates[0].ticker, "HELD.NS")

    def test_16_core_f1_integrity_git(self) -> None:
        quant = Path(__file__).resolve().parents[3].parent
        if not quant.exists():
            quant = Path(r"C:\Users\Avinaash\Quant")
        f1_paths = [
            quant / "F0" / "f1_runner.py",
            quant / "F0" / "f1",
        ]
        for p in f1_paths:
            self.assertTrue(p.exists(), f"Missing F1 path: {p}")
        center = Path(__file__).resolve().parents[2]
        import subprocess

        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=center,
            capture_output=True,
            text=True,
        )
        changed = result.stdout.splitlines()
        forbidden = [c for c in changed if c.startswith("F0/f1") or c.endswith("f1_runner.py")]
        self.assertEqual(forbidden, [], f"F1 core files modified: {forbidden}")


def run_production_eligibility_report() -> dict:
    quant = Path(r"C:\Users\Avinaash\Quant")
    path = quant / "F0" / "data" / "f1" / "f1_decisions.csv"
    if not path.exists():
        return {"error": f"Missing {path}"}
    df = pd.read_csv(path)
    candidates, ts, total = extract_buy_candidates(df)
    el = eligibility_from_candidates(candidates, ts, total)
    return {
        "path": str(path),
        "total_decisions": total,
        "buy_count": len(candidates),
        "f1_timestamp": ts,
        "eligibility": el["status"],
        "missing": el["missing_candidates"],
        "ordered_buys": [
            {"ticker": c.ticker, "portfolio_rank": c.portfolio_rank} for c in candidates
        ],
    }


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(F1BasketTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("\n=== PRODUCTION ELIGIBILITY (read-only) ===")
    report = run_production_eligibility_report()
    for k, v in report.items():
        if k != "ordered_buys":
            print(f"  {k}: {v}")
        else:
            print(f"  ordered_buys ({len(v)}):")
            for row in v:
                print(f"    {row['portfolio_rank']:>3}  {row['ticker']}")
    sys.exit(0 if result.wasSuccessful() else 1)
