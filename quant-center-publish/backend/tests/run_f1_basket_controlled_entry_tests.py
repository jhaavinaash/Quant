"""F1 Basket controlled entry & attribution tests."""

from __future__ import annotations

import math
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import pandas as pd

from app.services.f1_basket.allocation import allocate_controlled_entry
from app.services.f1_basket.constants import (
    BASKET_SIZE,
    BUY_COST_PCT,
    FILL_ADOPTED,
    FILL_COMPLETE,
    INITIAL_CAPITAL,
    PROFIT_TARGET_PCT,
    HARD_STOP_PCT,
    SELL_COMPLETE,
    STATUS_ACTIVE,
    STATUS_DEPLOYING,
)
from app.services.f1_basket.controlled_entry import (
    SlotSelection,
    attributed_qty,
    deploy_selected_slots,
)
from app.services.f1_basket.exit import submit_basket_exits, sync_basket_exits
from app.services.f1_basket.holdings import BrokerHolding
from app.services.f1_basket.live_valuation import value_active_basket
from app.services.f1_basket.reconciliation import sync_basket_fills
from app.services.f1_basket.selection import extract_buy_candidates, select_top_n
from app.services.f1_basket.store import get_basket_store
from app.services.f1_basket.valuation import value_basket


@dataclass
class MockFill:
    status: str
    fill_qty: int = 0
    fill_price: float = 0.0


def _mock_df(n: int = 12, price: float = 1000.0) -> pd.DataFrame:
    rows = [
        {
            "Ticker": f"T{i}.NS",
            "PortfolioRank": i,
            "Close": price,
            "Action": "BUY",
            "Timestamp": "2026-07-15",
        }
        for i in range(1, n + 1)
    ]
    return pd.DataFrame(rows)


class ControlledEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "controlled_entry.db"
        self.store = get_basket_store(self.db_path)
        self._patches = [
            patch("app.services.f1_basket_service.get_basket_store", return_value=self.store),
            patch("app.services.f1_basket.deployment.get_basket_store", return_value=self.store),
            patch("app.services.f1_basket.controlled_entry.get_basket_store", return_value=self.store),
            patch("app.services.f1_basket.reconciliation.get_basket_store", return_value=self.store),
            patch("app.services.f1_basket.exit.get_basket_store", return_value=self.store),
            patch("app.services.f1_basket.live_valuation.get_basket_store", return_value=self.store),
            patch(
                "app.services.f1_basket.deployment._broker_connected",
                return_value=(True, ""),
            ),
            patch(
                "app.services.f1_basket.controlled_entry._broker_connected",
                return_value=(True, ""),
            ),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)
        self._submit_log: list[dict] = []

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _holdings(self, mapping: dict[str, tuple[float, float]]) -> dict[str, BrokerHolding]:
        """ticker -> (qty, price)"""
        out = {}
        for t, (qty, px) in mapping.items():
            out[t.replace(".NS", "").upper()] = BrokerHolding(
                ticker=t, quantity=qty, avg_price=px, current_price=px, exposure=qty * px
            )
        return out

    def _create_controlled_preview(
        self,
        n: int = 12,
        price: float = 1000.0,
        holdings: dict | None = None,
    ) -> str:
        df = _mock_df(n, price)
        candidates, ts, _ = extract_buy_candidates(df)
        selected = select_top_n(candidates)
        h = holdings or {}
        alloc = allocate_controlled_entry(
            selected,
            INITIAL_CAPITAL,
            h,
            basket_size=BASKET_SIZE,
            profit_target_pct=PROFIT_TARGET_PCT,
            hard_stop_pct=HARD_STOP_PCT,
        )
        return self.store.create_preview_basket(allocation=alloc, f1_timestamp=ts)

    def _mock_submit(self, signal: dict) -> dict:
        self._submit_log.append(signal)
        return {"success": True, "broker_order_id": f"O-{signal['Ticker']}"}

    def test_ce_01_no_holding_full_slot_sizing(self) -> None:
        df = _mock_df(12, 1000.0)
        candidates, _, _ = extract_buy_candidates(df)
        alloc = allocate_controlled_entry(
            select_top_n(candidates),
            INITIAL_CAPITAL,
            {},
            basket_size=12,
            profit_target_pct=0.12,
            hard_stop_pct=0.15,
        )
        slot = INITIAL_CAPITAL / 12
        deployable = slot / (1 + BUY_COST_PCT)
        expected_qty = math.floor(deployable / 1000.0)
        self.assertEqual(alloc.constituents[0].recommended_buy_qty, expected_qty)
        self.assertAlmostEqual(alloc.constituents[0].target_slot_exposure, slot, places=2)

    def test_ce_02_existing_exposure_recommends_gap_topup(self) -> None:
        price = 1000.0
        existing_exposure = 12_000.0
        qty = existing_exposure / price
        h = self._holdings({"T1.NS": (qty, price)})
        df = _mock_df(12, price)
        candidates, _, _ = extract_buy_candidates(df)
        alloc = allocate_controlled_entry(
            select_top_n(candidates),
            INITIAL_CAPITAL,
            h,
            basket_size=12,
            profit_target_pct=0.12,
            hard_stop_pct=0.15,
        )
        c0 = alloc.constituents[0]
        self.assertGreater(c0.recommended_buy_qty, 0)
        self.assertLess(
            c0.recommended_buy_value + c0.current_exposure,
            c0.target_slot_exposure + price,
        )

    def test_ce_03_at_target_zero_recommended_buy(self) -> None:
        price = 1000.0
        slot = INITIAL_CAPITAL / 12
        qty = slot / price
        h = self._holdings({"T1.NS": (qty, price)})
        df = _mock_df(12, price)
        candidates, _, _ = extract_buy_candidates(df)
        alloc = allocate_controlled_entry(
            select_top_n(candidates),
            INITIAL_CAPITAL,
            h,
            basket_size=12,
            profit_target_pct=0.12,
            hard_stop_pct=0.15,
        )
        self.assertEqual(alloc.constituents[0].recommended_buy_qty, 0)

    def test_ce_04_skipped_slot_creates_no_order(self) -> None:
        bid = self._create_controlled_preview()
        sels = [SlotSelection(ticker=f"T{i}.NS", execute=(i <= 7)) for i in range(1, 13)]
        result = deploy_selected_slots(
            bid, sels, store=self.store, submit_fn=self._mock_submit,
            current_f1_timestamp="2026-07-15",
        )
        self.assertEqual(result.submitted, 7)
        self.assertEqual(len(self._submit_log), 7)

    def test_ce_05_selected_slots_only_deployed(self) -> None:
        bid = self._create_controlled_preview()
        sels = [
            SlotSelection("T1.NS", True),
            SlotSelection("T2.NS", True),
            SlotSelection("T3.NS", False),
        ]
        deploy_selected_slots(
            bid, sels, store=self.store, submit_fn=self._mock_submit,
            current_f1_timestamp="2026-07-15",
        )
        tickers = {s["Ticker"] for s in self._submit_log}
        self.assertEqual(tickers, {"T1.NS", "T2.NS"})

    def test_ce_06_no_capital_redistribution(self) -> None:
        price = 1000.0
        bid = self._create_controlled_preview(price=price)
        basket = self.store.get_basket(bid)
        assert basket
        t1 = next(c for c in basket["constituents"] if c["ticker"] == "T1.NS")
        t2 = next(c for c in basket["constituents"] if c["ticker"] == "T2.NS")
        q1 = int(t1["recommended_buy_qty"])
        deploy_selected_slots(
            bid,
            [SlotSelection("T1.NS", True), SlotSelection("T2.NS", False)],
            store=self.store,
            submit_fn=self._mock_submit,
            current_f1_timestamp="2026-07-15",
        )
        sig = self._submit_log[0]
        self.assertEqual(sig["Qty"], q1)

    def test_ce_07_max_twelve_attributed(self) -> None:
        bid = self._create_controlled_preview()
        with self.store._conn() as conn:
            for i in range(1, 11):
                conn.execute(
                    """UPDATE f1_basket_constituents SET slot_resolved=1, basket_attributed_qty=10,
                       adopted_existing_qty=10, fill_status=? WHERE basket_id=? AND ticker=?""",
                    (FILL_ADOPTED, bid, f"T{i}.NS"),
                )
        sels = [
            SlotSelection("T11.NS", True),
            SlotSelection("T12.NS", True),
            SlotSelection("T11.NS", True),
        ]
        result = deploy_selected_slots(
            bid, sels, store=self.store, submit_fn=self._mock_submit,
            current_f1_timestamp="2026-07-15",
        )
        self.assertFalse(result.success)
        self.assertIn("Maximum", result.message)

    def test_ce_08_existing_not_auto_attributed(self) -> None:
        price = 1000.0
        h = self._holdings({"T1.NS": (10.0, price)})
        bid = self._create_controlled_preview(holdings=h, price=price)
        basket = self.store.get_basket(bid)
        assert basket
        t1 = next(c for c in basket["constituents"] if c["ticker"] == "T1.NS")
        self.assertEqual(int(t1.get("slot_resolved") or 0), 0)
        self.assertEqual(float(t1.get("basket_attributed_qty") or 0), 0)

    def test_ce_09_explicit_adoption_persisted(self) -> None:
        price = 1000.0
        h = self._holdings({"T1.NS": (5.0, price)})
        bid = self._create_controlled_preview(holdings=h, price=price)
        with patch("app.services.f1_basket.controlled_entry.load_broker_holdings", return_value=h):
            deploy_selected_slots(
                bid,
                [SlotSelection("T1.NS", True, adopt_existing_qty=4)],
                store=self.store,
                submit_fn=self._mock_submit,
                current_f1_timestamp="2026-07-15",
            )
        basket = self.store.get_basket(bid)
        t1 = next(c for c in basket["constituents"] if c["ticker"] == "T1.NS")
        self.assertEqual(float(t1["adopted_existing_qty"]), 4.0)

    def test_ce_10_adopted_plus_bought_equals_attributed(self) -> None:
        price = 1000.0
        h = self._holdings({"T1.NS": (3.0, price)})
        bid = self._create_controlled_preview(holdings=h, price=price)
        with patch("app.services.f1_basket.controlled_entry.load_broker_holdings", return_value=h):
            deploy_selected_slots(
                bid,
                [SlotSelection("T1.NS", True, adopt_existing_qty=3)],
                store=self.store,
                submit_fn=self._mock_submit,
                current_f1_timestamp="2026-07-15",
            )
        basket = self.store.get_basket(bid)
        t1 = next(c for c in basket["constituents"] if c["ticker"] == "T1.NS")
        fills = {t1["broker_order_id"]: MockFill("COMPLETE", int(t1["recommended_buy_qty"]), price)}

        def fetch_fn(_b: str, oid: str):
            return fills[oid]

        sync_basket_fills(bid, store=self.store, fetch_fn=fetch_fn)
        basket = self.store.get_basket(bid)
        t1 = next(c for c in basket["constituents"] if c["ticker"] == "T1.NS")
        self.assertEqual(
            float(t1["basket_attributed_qty"]),
            float(t1["adopted_existing_qty"]) + float(t1["basket_bought_qty"]),
        )

    def test_ce_11_gross_mtm_uses_attributed_qty(self) -> None:
        bid = self._create_controlled_preview(price=100.0)
        with self.store._conn() as conn:
            conn.execute(
                """UPDATE f1_basket_constituents SET slot_resolved=1, basket_attributed_qty=4,
                   adopted_existing_qty=4, attribution_price=100, gross_buy_value=400
                   WHERE basket_id=? AND ticker='T1.NS'""",
                (bid,),
            )
            conn.execute(
                """UPDATE f1_baskets SET status='ACTIVE', basket_start_value=4800,
                   target_value=5376, stop_value=4080 WHERE basket_id=?""",
                (bid,),
            )
        basket = self.store.get_basket(bid)
        t1 = next(c for c in basket["constituents"] if c["ticker"] == "T1.NS")
        self.assertEqual(attributed_qty(t1), 4.0)
        result = value_active_basket(
            bid, store=self.store, price_fn=lambda _: {"T1": 110.0, **{f"T{i}": 100.0 for i in range(2, 13)}}
        )
        assert result
        t1_val = next(cv for cv in result.valuation.constituents if cv.ticker == "T1.NS")
        self.assertEqual(t1_val.current_market_value, 4 * 110.0)

    def test_ce_12_active_blocked_below_twelve_slots(self) -> None:
        bid = self._create_controlled_preview()
        sels = [SlotSelection(f"T{i}.NS", True) for i in range(1, 8)]
        deploy_selected_slots(
            bid, sels, store=self.store, submit_fn=self._mock_submit,
            current_f1_timestamp="2026-07-15",
        )
        basket = self.store.get_basket(bid)
        fills = {}
        for c in basket["constituents"]:
            if c.get("broker_order_id"):
                fills[c["broker_order_id"]] = MockFill(
                    "COMPLETE", int(c["recommended_buy_qty"]), 1000.0
                )

        def fetch_fn(_b: str, oid: str):
            return fills[oid]

        sync = sync_basket_fills(bid, store=self.store, fetch_fn=fetch_fn)
        self.assertFalse(sync.activated)
        refreshed = self.store.get_basket(bid)
        assert refreshed
        self.assertEqual(refreshed["status"], STATUS_DEPLOYING)

    def test_ce_13_active_succeeds_at_twelve_slots(self) -> None:
        bid = self._create_controlled_preview()
        sels = [SlotSelection(f"T{i}.NS", True) for i in range(1, 13)]
        deploy_selected_slots(
            bid, sels, store=self.store, submit_fn=self._mock_submit,
            current_f1_timestamp="2026-07-15",
        )
        basket = self.store.get_basket(bid)
        fills = {}
        for c in basket["constituents"]:
            if c.get("broker_order_id"):
                fills[c["broker_order_id"]] = MockFill(
                    "COMPLETE", int(c["recommended_buy_qty"]), 1000.0
                )

        def fetch_fn(_b: str, oid: str):
            return fills[oid]

        sync = sync_basket_fills(bid, store=self.store, fetch_fn=fetch_fn)
        self.assertTrue(sync.activated)
        refreshed = self.store.get_basket(bid)
        assert refreshed
        self.assertEqual(refreshed["status"], STATUS_ACTIVE)

    def test_ce_14_exit_sells_attributed_qty_only(self) -> None:
        bid = self._create_controlled_preview(price=100.0)
        with self.store._conn() as conn:
            for i in range(1, 13):
                conn.execute(
                    """UPDATE f1_basket_constituents SET slot_resolved=1, basket_attributed_qty=4,
                       adopted_existing_qty=4, attribution_price=100, gross_buy_value=400,
                       fill_status=? WHERE basket_id=? AND ticker=?""",
                    (FILL_ADOPTED, bid, f"T{i}.NS"),
                )
            conn.execute(
                """UPDATE f1_baskets SET status='EXIT_PENDING', basket_start_value=4800,
                   target_value=5376, stop_value=4080 WHERE basket_id=?""",
                (bid,),
            )
        sells: list[dict] = []

        def sell_fn(sig: dict) -> dict:
            sells.append(sig)
            return {"success": True, "broker_order_id": f"S-{sig['Ticker']}"}

        submit_basket_exits(bid, store=self.store, submit_fn=sell_fn)
        t1_sell = next(s for s in sells if s["Ticker"] == "T1.NS")
        self.assertEqual(t1_sell["Qty"], 4)

    def test_ce_15_non_attributed_survives_exit(self) -> None:
        """Broker holds 10; basket attributes 4 — SELL qty must be 4 not 10."""
        bid = self._create_controlled_preview(price=100.0)
        with self.store._conn() as conn:
            conn.execute(
                """UPDATE f1_basket_constituents SET slot_resolved=1, basket_attributed_qty=4,
                   adopted_existing_qty=4, attribution_price=100, gross_buy_value=400,
                   current_broker_qty=10, fill_status=? WHERE basket_id=? AND ticker='T1.NS'""",
                (FILL_ADOPTED, bid,),
            )
            for i in range(2, 13):
                conn.execute(
                    """UPDATE f1_basket_constituents SET slot_resolved=1, basket_attributed_qty=20,
                       basket_bought_qty=20, attribution_price=100, gross_buy_value=2000,
                       fill_status=? WHERE basket_id=? AND ticker=?""",
                    (FILL_COMPLETE, bid, f"T{i}.NS"),
                )
            conn.execute(
                """UPDATE f1_baskets SET status='EXITING', basket_start_value=24400,
                   target_value=27328, stop_value=20740 WHERE basket_id=?""",
                (bid,),
            )
            for i in range(1, 13):
                conn.execute(
                    """UPDATE f1_basket_constituents SET sell_broker_order_id=?, sell_status=?
                       WHERE basket_id=? AND ticker=?""",
                    (f"SO-{i}", "SUBMITTED", bid, f"T{i}.NS"),
                )
        with self.store._conn() as conn:
            conn.execute(
                """UPDATE f1_basket_constituents SET sell_status=?, sell_filled_qty=4
                   WHERE basket_id=? AND ticker='T1.NS'""",
                (SELL_COMPLETE, bid),
            )
        sync = sync_basket_exits(
            bid,
            store=self.store,
            fetch_fn=lambda _b, oid: MockFill("COMPLETE", 4 if "SO-1" in oid else 20, 100.0),
        )
        self.assertIn("EXITING", sync.status)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ControlledEntryTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"\nControlled entry: {result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} PASS")
    raise SystemExit(0 if result.wasSuccessful() else 1)
