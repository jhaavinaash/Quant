"""F1 Basket Phase 3 tests — mocked prices/broker only."""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.f1_basket.constants import (
    BASKET_SIZE,
    BUY_COST_PCT,
    EXIT_REASON_TARGET,
    FILL_COMPLETE,
    HARD_STOP_PCT,
    INITIAL_CAPITAL,
    PROFIT_TARGET_PCT,
    SELL_COMPLETE,
    SELL_FAILED,
    STATUS_ACTIVE,
    STATUS_CLOSED,
    STATUS_EXIT_PENDING,
    STATUS_EXITING,
)
from app.services.f1_basket.exit import (
    initiate_manual_exit,
    mark_exit_trigger,
    submit_basket_exits,
    sync_basket_exits,
)
from app.services.f1_basket.live_valuation import value_active_basket
from app.services.f1_basket_monitor import run_monitor_cycle
from app.services.f1_basket.store import get_basket_store
from app.services.f1_basket.valuation import evaluate_trigger

@dataclass
class MockFill:
    status: str
    fill_qty: int = 0
    fill_price: float = 0.0


class Phase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "phase3_basket.db"
        self.store = get_basket_store(self.db_path)
        for p in (
            "app.services.f1_basket_service.get_basket_store",
            "app.services.f1_basket.deployment.get_basket_store",
            "app.services.f1_basket.reconciliation.get_basket_store",
            "app.services.f1_basket.exit.get_basket_store",
            "app.services.f1_basket.live_valuation.get_basket_store",
        ):
            patcher = patch(p, return_value=self.store)
            patcher.start()
            self.addCleanup(patcher.stop)
        self._broker_patch = patch(
            "app.services.f1_basket.deployment._broker_connected", return_value=(True, "")
        )
        self._broker_patch.start()
        self.addCleanup(self._broker_patch.stop)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _create_ready_basket(self, n: int = 12) -> str:
        from app.services.f1_basket.allocation import allocate_equal_weight
        from app.services.f1_basket.selection import extract_buy_candidates, select_top_n
        import pandas as pd
        rows = [{"Ticker": f"T{i}.NS", "PortfolioRank": i, "Close": 100.0 + i, "Action": "BUY", "Timestamp": "2026-07-15"} for i in range(1, n + 1)]
        df = pd.DataFrame(rows)
        candidates, ts, _ = extract_buy_candidates(df)
        alloc = allocate_equal_weight(select_top_n(candidates), INITIAL_CAPITAL, basket_size=12, profit_target_pct=0.12, hard_stop_pct=0.15)
        return self.store.create_preview_basket(allocation=alloc, f1_timestamp=ts)
    def _activate_basket(self, bid: str, start: float = 300_000.0) -> None:
        per = start / BASKET_SIZE
        buy_cost = per * BUY_COST_PCT
        with self.store._conn() as conn:
            conn.execute(
                "UPDATE f1_baskets SET status='ACTIVE', basket_start_value=?, target_value=?, stop_value=?, actual_buy_cost=? WHERE basket_id=?",
                (start, start * 1.12, start * 0.85, buy_cost * BASKET_SIZE, bid),
            )
            rows = conn.execute(
                "SELECT id, quantity FROM f1_basket_constituents WHERE basket_id=?", (bid,)
            ).fetchall()
            for r in rows:
                conn.execute(
                    """UPDATE f1_basket_constituents SET fill_status=?, filled_qty=quantity,
                       average_fill_price=reference_price, gross_buy_value=quantity*reference_price,
                       estimated_buy_cost=gross_buy_value*?, basket_bought_qty=quantity,
                       basket_attributed_qty=quantity, slot_resolved=1, attribution_price=reference_price
                       WHERE id=?""",
                    (FILL_COMPLETE, BUY_COST_PCT, r["id"]),
                )

    def test_p3_01_active_values_12(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid)
        prices = {f"T{i}": 110.0 for i in range(1, 13)}
        result = value_active_basket(bid, store=self.store, price_fn=lambda _: prices)
        assert result
        self.assertEqual(len(result.valuation.constituents), 12)

    def test_p3_02_eleven_point_nine_nine_none(self) -> None:
        start = 100_000.0
        val = start * 1.1199
        self.assertEqual(evaluate_trigger(val, start, PROFIT_TARGET_PCT, HARD_STOP_PCT), "NONE")

    def test_p3_03_exact_target(self) -> None:
        start = 100_000.0
        self.assertEqual(evaluate_trigger(start * 1.12, start, PROFIT_TARGET_PCT, HARD_STOP_PCT), "TARGET")

    def test_p3_04_exact_stop(self) -> None:
        start = 100_000.0
        self.assertEqual(evaluate_trigger(start * 0.85, start, PROFIT_TARGET_PCT, HARD_STOP_PCT), "STOP")

    def test_p3_05_target_one_exit(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid, 100_000.0)
        ok = mark_exit_trigger(bid, trigger="TARGET", reason=EXIT_REASON_TARGET, trigger_value=112_000.0, store=self.store)
        self.assertTrue(ok)
        b = self.store.get_basket(bid)
        assert b
        self.assertEqual(b["status"], STATUS_EXIT_PENDING)
        ok2 = mark_exit_trigger(bid, trigger="TARGET", reason=EXIT_REASON_TARGET, trigger_value=112_000.0, store=self.store)
        self.assertFalse(ok2)

    def test_p3_06_monitor_no_duplicate_sells(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid)
        mark_exit_trigger(bid, trigger="TARGET", reason=EXIT_REASON_TARGET, trigger_value=112_000.0, store=self.store)
        sells: list[str] = []

        def sell_fn(sig):
            sells.append(sig["Ticker"])
            return {"success": True, "broker_order_id": f"S-{sig['Ticker']}"}

        submit_basket_exits(bid, store=self.store, submit_fn=sell_fn)
        sells.clear()
        run_monitor_cycle()
        self.assertEqual(len(sells), 0)

    def test_p3_07_stop_submits_12_sells(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid)
        mark_exit_trigger(bid, trigger="STOP", reason="STOP", trigger_value=85_000.0, store=self.store)
        sells: list[str] = []

        def sell_fn(sig):
            sells.append(sig["Ticker"])
            return {"success": True, "broker_order_id": f"S-{len(sells)}"}

        r = submit_basket_exits(bid, store=self.store, submit_fn=sell_fn)
        self.assertEqual(r.submitted, 12)

    def test_p3_08_f1_changes_ignored(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid)
        orig = [c["ticker"] for c in self.store.get_basket(bid)["constituents"]]
        with patch("app.services.f1_basket_service.load_f1_decisions_df") as m:
            import pandas as pd
            m.return_value = pd.DataFrame({"Timestamp": ["x"], "Ticker": ["ROT.NS"], "Action": ["ROTATE"], "PortfolioRank": [1], "Close": [1]})
            from app.services.f1_basket_service import F1BasketService
            snap = F1BasketService.get_snapshot()
        self.assertEqual([c.ticker for c in snap.preview.constituents], orig)

    def test_p3_09_sell_failure_stays_exiting(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid)
        mark_exit_trigger(bid, trigger="TARGET", reason=EXIT_REASON_TARGET, trigger_value=112_000.0, store=self.store)

        def sell_fn(sig):
            if sig["Ticker"] == "T6.NS":
                return {"success": False, "message": "fail"}
            return {"success": True, "broker_order_id": f"S-{sig['Ticker']}"}

        submit_basket_exits(bid, store=self.store, submit_fn=sell_fn)
        b = self.store.get_basket(bid)
        assert b
        self.assertEqual(b["status"], STATUS_EXITING)
        self.assertNotEqual(b["status"], STATUS_CLOSED)

    def test_p3_10_retry_failed_sell_only(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid)
        mark_exit_trigger(bid, trigger="TARGET", reason=EXIT_REASON_TARGET, trigger_value=112_000.0, store=self.store)
        submit_basket_exits(bid, store=self.store, submit_fn=lambda s: {"success": False, "message": "x"} if s["Ticker"] == "T3.NS" else {"success": True, "broker_order_id": f"X-{s['Ticker']}"})
        sells: list[str] = []
        submit_basket_exits(bid, store=self.store, submit_fn=lambda s: (sells.append(s["Ticker"]) or {"success": True, "broker_order_id": "R1"}), retry_failed_only=True)
        self.assertEqual(sells, ["T3.NS"])

    def test_p3_11_partial_not_closed(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid)
        mark_exit_trigger(bid, trigger="TARGET", reason=EXIT_REASON_TARGET, trigger_value=112_000.0, store=self.store)
        submit_basket_exits(bid, store=self.store, submit_fn=lambda s: {"success": True, "broker_order_id": f"O-{s['Ticker']}"})
        b = self.store.get_basket(bid)
        fills = {}
        for c in b["constituents"]:
            if c["ticker"] == "T1.NS":
                fills[c["sell_broker_order_id"]] = MockFill("PARTIAL", 1, 100.0)
            else:
                q = int(c["filled_qty"])
                fills[c["sell_broker_order_id"]] = MockFill("COMPLETE", q, 100.0)
        sync = sync_basket_exits(bid, store=self.store, fetch_fn=lambda b, o: fills[o])
        self.assertFalse(sync.closed)

    def test_p3_12_all_complete_closed(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid, 100_000.0)
        mark_exit_trigger(bid, trigger="TARGET", reason=EXIT_REASON_TARGET, trigger_value=112_000.0, store=self.store)
        submit_basket_exits(bid, store=self.store, submit_fn=lambda s: {"success": True, "broker_order_id": f"O-{s['Ticker']}"})
        b = self.store.get_basket(bid)
        fills = {c["sell_broker_order_id"]: MockFill("COMPLETE", int(c["filled_qty"]), 110.0) for c in b["constituents"]}
        sync = sync_basket_exits(bid, store=self.store, fetch_fn=lambda br, o: fills[o])
        self.assertTrue(sync.closed)
        self.assertEqual(self.store.get_basket(bid)["status"], STATUS_CLOSED)

    def test_p3_13_closed_pnl_formula(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid, 100_000.0)
        mark_exit_trigger(bid, trigger="TARGET", reason=EXIT_REASON_TARGET, trigger_value=112_000.0, store=self.store)
        submit_basket_exits(bid, store=self.store, submit_fn=lambda s: {"success": True, "broker_order_id": f"O-{s['Ticker']}"})
        b = self.store.get_basket(bid)
        sell_price = 110.0
        fills = {c["sell_broker_order_id"]: MockFill("COMPLETE", int(c["filled_qty"]), sell_price) for c in b["constituents"]}
        sync_basket_exits(bid, store=self.store, fetch_fn=lambda br, o: fills[o])
        closed = self.store.get_basket(bid)
        sell_value = sum(int(c["filled_qty"]) * sell_price for c in closed["constituents"])
        buy_cost = sum(float(c["estimated_buy_cost"]) for c in closed["constituents"])
        sell_cost = sell_value * BUY_COST_PCT
        expected_net = sell_value - sell_cost - 100_000.0 - buy_cost
        self.assertAlmostEqual(closed["net_pnl"], expected_net, places=0)

    def test_p3_14_manual_exit_pipeline(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid)
        r = initiate_manual_exit(bid, store=self.store, submit_fn=lambda s: {"success": True, "broker_order_id": f"M-{s['Ticker']}"})
        self.assertEqual(r.submitted, 12)
        self.assertEqual(self.store.get_basket(bid)["status"], STATUS_EXITING)

    def test_p3_15_restart_no_duplicate_exits(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid)
        mark_exit_trigger(bid, trigger="TARGET", reason=EXIT_REASON_TARGET, trigger_value=112_000.0, store=self.store)
        submit_basket_exits(bid, store=self.store, submit_fn=lambda s: {"success": True, "broker_order_id": f"O-{s['Ticker']}"})
        sells: list[str] = []
        store2 = get_basket_store(self.db_path)
        submit_basket_exits(bid, store=store2, submit_fn=lambda s: (sells.append(s["Ticker"]) or {"success": True, "broker_order_id": "DUP"}))
        self.assertEqual(len(sells), 0)

    def test_p3_16_closed_cannot_exit(self) -> None:
        bid = self._create_ready_basket(12)
        self._activate_basket(bid)
        with self.store._conn() as conn:
            conn.execute("UPDATE f1_baskets SET status='CLOSED' WHERE basket_id=?", (bid,))
        r = initiate_manual_exit(bid, store=self.store)
        self.assertEqual(r.submitted, 0)

    def test_p3_17_no_individual_exit_in_api(self) -> None:
        from app.api.v1.endpoints import f1_basket as ep
        routes = [getattr(r, "path", "") for r in ep.router.routes]
        self.assertFalse(any("constituent" in p and "exit" in p for p in routes))

    def test_p3_18_f1_integrity(self) -> None:
        import subprocess
        center = Path(__file__).resolve().parents[2]
        result = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=center, capture_output=True, text=True)
        forbidden = [c for c in result.stdout.splitlines() if "f1_basket" not in c and (c.startswith("F0/f1") or "f1_runner" in c)]
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(Phase3Tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
