"""
F1 Basket Phase 2 — deployment & reconciliation tests (mocked broker only).

Run: python tests/run_f1_basket_phase2_tests.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.f1_basket.allocation import allocate_equal_weight
from app.services.f1_basket.constants import (
    BASKET_SIZE,
    FILL_COMPLETE,
    FILL_FAILED,
    FILL_PARTIAL,
    FILL_PENDING,
    FILL_REJECTED,
    FILL_SUBMITTED,
    HARD_STOP_PCT,
    INITIAL_CAPITAL,
    PROFIT_TARGET_PCT,
    STATUS_ACTIVE,
    STATUS_DEPLOYING,
    STATUS_READY,
)
from app.services.f1_basket.deployment import check_deploy_gate, deploy_basket_orders
from app.services.f1_basket.reconciliation import sync_basket_fills
from app.services.f1_basket.selection import extract_buy_candidates, select_top_n
from app.services.f1_basket.store import get_basket_store
from app.services.f1_basket_service import F1BasketService


def _mock_df(rows: list[dict], ts: str = "2026-07-15 09:00:00") -> pd.DataFrame:
    base = {
        "Timestamp": ts,
        "Ticker": "",
        "Action": "BUY",
        "PortfolioRank": 1,
        "TechnicalState": "OK",
        "SectorState": "OK",
        "BusinessGate": "PASS",
        "Sector": "Test",
        "Close": 100.0,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def _buy_rows(n: int) -> list[dict]:
    return [{"Ticker": f"T{i}.NS", "PortfolioRank": i, "Close": 100.0 + i} for i in range(1, n + 1)]


@dataclass
class MockFill:
    status: str
    fill_qty: int = 0
    fill_price: float = 0.0
    error: str = ""
    raw_status: str = ""


class Phase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "phase2_basket.db"
        self.store = get_basket_store(self.db_path)
        self._order_counter = 0
        self._submit_log: list[str] = []

        self._patcher_store = patch(
            "app.services.f1_basket_service.get_basket_store",
            return_value=self.store,
        )
        self._patcher_dep_store = patch(
            "app.services.f1_basket.deployment.get_basket_store",
            return_value=self.store,
        )
        self._patcher_rec_store = patch(
            "app.services.f1_basket.reconciliation.get_basket_store",
            return_value=self.store,
        )
        self._patcher_store.start()
        self._patcher_dep_store.start()
        self._patcher_rec_store.start()

        self._broker_patch = patch(
            "app.services.f1_basket.deployment._broker_connected",
            return_value=(True, ""),
        )
        self._broker_patch.start()

    def tearDown(self) -> None:
        self._broker_patch.stop()
        self._patcher_rec_store.stop()
        self._patcher_dep_store.stop()
        self._patcher_store.stop()
        self._tmpdir.cleanup()

    def _create_ready_basket(self, n: int = 12, *, held: bool = False) -> str:
        df = _mock_df(_buy_rows(n))
        candidates, ts, _ = extract_buy_candidates(df)
        selected = select_top_n(candidates)
        alloc = allocate_equal_weight(
            selected,
            INITIAL_CAPITAL,
            basket_size=BASKET_SIZE,
            profit_target_pct=PROFIT_TARGET_PCT,
            hard_stop_pct=HARD_STOP_PCT,
        )
        if held and alloc.constituents:
            alloc.constituents[0].candidate.held_globally = True
            alloc.constituents[0].candidate.held_conflict = True
        bid = self.store.create_preview_basket(allocation=alloc, f1_timestamp=ts, status=STATUS_READY)
        if held:
            with self.store._conn() as conn:
                conn.execute(
                    "UPDATE f1_basket_constituents SET held_globally_at_selection = 1 WHERE basket_id = ? AND selection_order = 1",
                    (bid,),
                )
        return bid

    def _mock_submit(self, signal: dict) -> dict:
        ticker = signal.get("Ticker", "")
        self._submit_log.append(ticker)
        self._order_counter += 1
        return {
            "success": True,
            "broker_order_id": f"MOCK-{self._order_counter}",
            "message": "ok",
        }

    def _mock_submit_fail_on(self, fail_ticker: str):
        def fn(signal: dict) -> dict:
            ticker = signal.get("Ticker", "")
            if ticker == fail_ticker:
                return {"success": False, "message": "broker rejected"}
            return self._mock_submit(signal)
        return fn

    def test_01_ready_deploys_12_buy_requests(self) -> None:
        bid = self._create_ready_basket(12)
        result = deploy_basket_orders(
            bid,
            submit_fn=self._mock_submit,
            current_f1_timestamp="2026-07-15 09:00:00",
        )
        self.assertEqual(result.submitted, 12)
        self.assertEqual(len(self._submit_log), 12)
        basket = self.store.get_basket(bid)
        assert basket
        self.assertEqual(basket["status"], STATUS_DEPLOYING)

    def test_02_ten_stock_not_ready_cannot_deploy(self) -> None:
        df = _mock_df(_buy_rows(10))
        candidates, ts, _ = extract_buy_candidates(df)
        selected = select_top_n(candidates)
        alloc = allocate_equal_weight(
            selected, INITIAL_CAPITAL, basket_size=BASKET_SIZE,
            profit_target_pct=PROFIT_TARGET_PCT, hard_stop_pct=HARD_STOP_PCT,
        )
        # manually create invalid 10-stock basket
        bid = self.store.create_preview_basket(allocation=alloc, f1_timestamp=ts)
        basket = self.store.get_basket(bid)
        assert basket
        gate = check_deploy_gate(basket, current_f1_timestamp=ts, stale=False)
        self.assertFalse(gate.allowed)

    def test_03_stale_preview_cannot_deploy(self) -> None:
        bid = self._create_ready_basket(12)
        basket = self.store.get_basket(bid)
        assert basket
        gate = check_deploy_gate(basket, current_f1_timestamp="2026-07-16 10:00:00", stale=True)
        self.assertFalse(gate.allowed)

    def test_04_disconnected_zerodha_cannot_deploy(self) -> None:
        bid = self._create_ready_basket(12)
        with patch(
            "app.services.f1_basket.deployment._broker_connected",
            return_value=(False, "Zerodha is NOT CONNECTED"),
        ):
            result = deploy_basket_orders(bid, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00")
        self.assertEqual(result.submitted, 0)
        self.assertIn("NOT CONNECTED", result.message)

    def test_05_held_position_allows_controlled_deploy(self) -> None:
        bid = self._create_ready_basket(12, held=True)
        basket = self.store.get_basket(bid)
        assert basket
        gate = check_deploy_gate(basket, current_f1_timestamp="2026-07-15 09:00:00", stale=False)
        self.assertTrue(gate.allowed)

    def test_06_double_deploy_no_duplicates(self) -> None:
        bid = self._create_ready_basket(12)
        deploy_basket_orders(bid, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00")
        self._submit_log.clear()
        result2 = deploy_basket_orders(bid, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00")
        self.assertEqual(result2.submitted, 0)
        self.assertEqual(len(self._submit_log), 0)

    def test_07_restart_deploy_no_duplicates(self) -> None:
        bid = self._create_ready_basket(12)
        deploy_basket_orders(bid, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00")
        # simulate restart — new store instance same db
        store2 = get_basket_store(self.db_path)
        self._submit_log.clear()
        result = deploy_basket_orders(
            bid, store=store2, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00"
        )
        self.assertEqual(result.submitted, 0)

    def test_08_all_complete_becomes_active(self) -> None:
        bid = self._create_ready_basket(12)
        deploy_basket_orders(bid, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00")
        basket = self.store.get_basket(bid)
        fills = {}
        for c in basket["constituents"]:
            fills[c["broker_order_id"]] = MockFill("COMPLETE", int(c["quantity"]), 105.0)

        def fetch_fn(_broker: str, oid: str):
            return fills[oid]

        sync = sync_basket_fills(bid, fetch_fn=fetch_fn)
        self.assertTrue(sync.activated)
        refreshed = self.store.get_basket(bid)
        assert refreshed
        self.assertEqual(refreshed["status"], STATUS_ACTIVE)

    def test_09_fill_prices_recalculate_start_value(self) -> None:
        bid = self._create_ready_basket(12)
        deploy_basket_orders(bid, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00")
        basket = self.store.get_basket(bid)
        fills = {}
        expected_gross = 0.0
        for c in basket["constituents"]:
            qty = int(c["quantity"])
            price = 110.0
            fills[c["broker_order_id"]] = MockFill("COMPLETE", qty, price)
            expected_gross += qty * price

        sync_basket_fills(bid, fetch_fn=lambda b, oid: fills[oid])
        refreshed = self.store.get_basket(bid)
        assert refreshed
        self.assertAlmostEqual(refreshed["basket_start_value"], expected_gross, places=2)

    def test_10_partial_remains_deploying(self) -> None:
        bid = self._create_ready_basket(12)
        deploy_basket_orders(bid, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00")
        basket = self.store.get_basket(bid)
        c0 = basket["constituents"][0]

        def fetch_fn(_b: str, oid: str):
            if oid == c0["broker_order_id"]:
                return MockFill("PARTIAL", 1, 100.0)
            return MockFill("COMPLETE", 10, 100.0)

        sync = sync_basket_fills(bid, fetch_fn=fetch_fn)
        self.assertFalse(sync.activated)
        refreshed = self.store.get_basket(bid)
        assert refreshed
        self.assertEqual(refreshed["status"], STATUS_DEPLOYING)

    def test_11_one_rejected_eleven_complete_incomplete(self) -> None:
        bid = self._create_ready_basket(12)
        deploy_basket_orders(bid, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00")
        basket = self.store.get_basket(bid)
        reject_oid = basket["constituents"][0]["broker_order_id"]

        def fetch_fn(_b: str, oid: str):
            if oid == reject_oid:
                return MockFill("REJECTED", 0, 0.0)
            c = next(x for x in basket["constituents"] if x["broker_order_id"] == oid)
            return MockFill("COMPLETE", int(c["quantity"]), 100.0)

        sync = sync_basket_fills(bid, fetch_fn=fetch_fn)
        self.assertFalse(sync.activated)
        self.assertIn("INCOMPLETE", sync.message)

    def test_12_retry_failed_only_failed(self) -> None:
        bid = self._create_ready_basket(12)
        fail_ticker = "T8.NS"
        deploy_basket_orders(
            bid,
            submit_fn=self._mock_submit_fail_on(fail_ticker),
            current_f1_timestamp="2026-07-15 09:00:00",
        )
        self._submit_log.clear()
        result = deploy_basket_orders(
            bid,
            submit_fn=self._mock_submit,
            current_f1_timestamp="2026-07-15 09:00:00",
            retry_failed_only=True,
        )
        self.assertEqual(result.submitted, 1)
        self.assertEqual(self._submit_log, [fail_ticker])

    def test_13_retry_never_resubmits_complete(self) -> None:
        bid = self._create_ready_basket(12)
        deploy_basket_orders(bid, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00")
        basket = self.store.get_basket(bid)
        c0 = basket["constituents"][0]
        self.store.update_constituent_order(
            bid, c0["ticker"], fill_status=FILL_COMPLETE, filled_qty=int(c0["quantity"]), average_fill_price=100.0
        )
        self.store.update_constituent_order(
            bid, basket["constituents"][7]["ticker"],
            fill_status=FILL_FAILED,
            broker_order_id="",
        )
        self._submit_log.clear()
        result = deploy_basket_orders(
            bid, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00", retry_failed_only=True
        )
        self.assertEqual(result.submitted, 1)
        self.assertNotIn(c0["ticker"], self._submit_log)

    def test_14_constituents_locked_after_f1_changes(self) -> None:
        bid = self._create_ready_basket(12)
        deploy_basket_orders(bid, submit_fn=self._mock_submit, current_f1_timestamp="2026-07-15 09:00:00")
        orig = [c["ticker"] for c in self.store.get_basket(bid)["constituents"]]
        with patch(
            "app.services.f1_basket_service.load_f1_decisions_df",
            return_value=_mock_df(_buy_rows(14), "2026-07-16 09:00:00"),
        ):
            snap = F1BasketService.get_snapshot()
        assert snap.preview
        self.assertEqual([c.ticker for c in snap.preview.constituents], orig)

    def test_15_f1_core_integrity(self) -> None:
        center = Path(__file__).resolve().parents[2]
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=center,
            capture_output=True,
            text=True,
        )
        changed = result.stdout.splitlines()
        forbidden = [c for c in changed if "f1_basket" not in c and (c.startswith("F0/f1") or "f1_runner" in c)]
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
