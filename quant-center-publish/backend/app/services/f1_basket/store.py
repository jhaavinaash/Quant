"""SQLite persistence for F1 Basket previews and lifecycle."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from app.core.config import settings
from app.services.f1_basket.constants import (
    BASKET_SIZE,
    BUY_COST_PCT,
    FILL_PENDING,
    HARD_STOP_PCT,
    INITIAL_CAPITAL,
    PREVIEW_STATUSES,
    PROFIT_TARGET_PCT,
    SELL_COST_PCT,
    STATUS_ACTIVE,
    STATUS_CLOSED,
    STATUS_DEPLOYING,
    STATUS_DRAFT,
    STATUS_EXIT_PENDING,
    STATUS_EXITING,
    STATUS_READY,
    STRATEGY_NAME,
    TERMINAL_FAILURE_STATUSES,
)


def _db_path() -> Path:
    return Path(settings.QUANT_BASE_DIR) / "F0" / "production" / "f1_basket.db"


class F1BasketStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self._path = Path(db_path) if db_path else _db_path()

    @property
    def path(self) -> Path:
        return self._path

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._path), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS f1_baskets (
                    basket_id TEXT PRIMARY KEY,
                    cycle_number INTEGER NOT NULL,
                    strategy_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    selection_source TEXT NOT NULL,
                    f1_snapshot_timestamp TEXT NOT NULL,
                    initial_capital REAL NOT NULL,
                    allocated_capital REAL NOT NULL,
                    cash_remaining REAL NOT NULL,
                    basket_start_value REAL NOT NULL,
                    current_value REAL,
                    gross_pnl REAL,
                    net_pnl REAL,
                    return_pct REAL,
                    profit_target_pct REAL NOT NULL,
                    hard_stop_pct REAL NOT NULL,
                    buy_cost_pct REAL NOT NULL,
                    sell_cost_pct REAL NOT NULL,
                    target_value REAL NOT NULL,
                    stop_value REAL NOT NULL,
                    exit_trigger TEXT,
                    exit_reason TEXT,
                    last_valued_at TEXT,
                    created_by TEXT
                );

                CREATE TABLE IF NOT EXISTS f1_basket_constituents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    basket_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    portfolio_rank REAL,
                    selection_order INTEGER NOT NULL,
                    f1_action_at_selection TEXT,
                    technical_state_at_selection TEXT,
                    sector_state_at_selection TEXT,
                    business_gate_at_selection TEXT,
                    sector_at_selection TEXT,
                    reference_price REAL NOT NULL,
                    target_weight REAL NOT NULL,
                    allocated_amount REAL NOT NULL,
                    quantity REAL NOT NULL,
                    gross_buy_value REAL NOT NULL,
                    estimated_buy_cost REAL NOT NULL,
                    estimated_total_entry_cost REAL NOT NULL,
                    current_price REAL,
                    current_market_value REAL,
                    constituent_pnl REAL,
                    constituent_return_pct REAL,
                    held_globally_at_selection INTEGER NOT NULL DEFAULT 0,
                    broker_order_id TEXT,
                    fill_status TEXT,
                    filled_qty REAL,
                    average_fill_price REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (basket_id, ticker),
                    FOREIGN KEY (basket_id) REFERENCES f1_baskets(basket_id)
                );

                CREATE INDEX IF NOT EXISTS idx_f1_basket_status
                    ON f1_baskets (status);
                """
            )
            self._migrate_schema(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(f1_baskets)").fetchall()}
        if "deployment_started_at" not in cols:
            conn.execute("ALTER TABLE f1_baskets ADD COLUMN deployment_started_at TEXT")
        con_cols = {row[1] for row in conn.execute("PRAGMA table_info(f1_basket_constituents)").fetchall()}
        if "last_error" not in con_cols:
            conn.execute("ALTER TABLE f1_basket_constituents ADD COLUMN last_error TEXT")
        if "broker" not in con_cols:
            conn.execute(
                "ALTER TABLE f1_basket_constituents ADD COLUMN broker TEXT DEFAULT 'zerodha'"
            )
        basket_cols = {
            "triggered_at": "TEXT",
            "trigger_basket_value": "REAL",
            "actual_sell_value": "REAL",
            "actual_sell_cost": "REAL",
            "actual_buy_cost": "REAL",
        }
        for col, typ in basket_cols.items():
            if col not in cols:
                conn.execute(f"ALTER TABLE f1_baskets ADD COLUMN {col} {typ}")
        sell_cols = {
            "sell_broker_order_id": "TEXT",
            "sell_status": "TEXT",
            "sell_filled_qty": "REAL",
            "average_sell_fill_price": "REAL",
            "sell_last_error": "TEXT",
        }
        for col, typ in sell_cols.items():
            if col not in con_cols:
                conn.execute(f"ALTER TABLE f1_basket_constituents ADD COLUMN {col} {typ}")
        attr_cols = {
            "target_slot_exposure": "REAL DEFAULT 0",
            "current_broker_qty": "REAL DEFAULT 0",
            "current_exposure": "REAL DEFAULT 0",
            "exposure_gap": "REAL DEFAULT 0",
            "recommended_buy_qty": "REAL DEFAULT 0",
            "recommended_buy_value": "REAL DEFAULT 0",
            "adopted_existing_qty": "REAL DEFAULT 0",
            "basket_bought_qty": "REAL DEFAULT 0",
            "basket_attributed_qty": "REAL DEFAULT 0",
            "slot_resolved": "INTEGER DEFAULT 0",
            "slot_skipped": "INTEGER DEFAULT 0",
            "attribution_price": "REAL DEFAULT 0",
        }
        for col, typ in attr_cols.items():
            if col not in con_cols:
                conn.execute(f"ALTER TABLE f1_basket_constituents ADD COLUMN {col} {typ}")

    def _next_cycle_number(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT COALESCE(MAX(cycle_number), 0) + 1 AS n FROM f1_baskets").fetchone()
        return int(row["n"]) if row else 1

    def delete_preview_baskets(self) -> None:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT basket_id FROM f1_baskets WHERE status IN ('DRAFT', 'READY')"
            ).fetchall()
            for r in rows:
                bid = r["basket_id"]
                conn.execute("DELETE FROM f1_basket_constituents WHERE basket_id = ?", (bid,))
                conn.execute("DELETE FROM f1_baskets WHERE basket_id = ?", (bid,))

    def create_preview_basket(
        self,
        *,
        allocation: Any,
        f1_timestamp: str,
        status: str = STATUS_READY,
        created_by: str = "preview",
    ) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        basket_id = str(uuid.uuid4())
        with self._conn() as conn:
            cycle = self._next_cycle_number(conn)
            conn.execute(
                """
                INSERT INTO f1_baskets (
                    basket_id, cycle_number, strategy_name, status, created_at,
                    selection_source, f1_snapshot_timestamp,
                    initial_capital, allocated_capital, cash_remaining,
                    basket_start_value, current_value,
                    profit_target_pct, hard_stop_pct, buy_cost_pct, sell_cost_pct,
                    target_value, stop_value, created_by, last_valued_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    basket_id,
                    cycle,
                    STRATEGY_NAME,
                    status,
                    now,
                    "f1_decisions.csv",
                    f1_timestamp,
                    allocation.initial_capital,
                    allocation.allocated_capital,
                    allocation.cash_remaining,
                    allocation.basket_start_value,
                    allocation.basket_start_value,
                    PROFIT_TARGET_PCT,
                    HARD_STOP_PCT,
                    BUY_COST_PCT,
                    SELL_COST_PCT,
                    allocation.target_value,
                    allocation.stop_value,
                    created_by,
                    now,
                ),
            )
            for c in allocation.constituents:
                cand = c.candidate
                conn.execute(
                    """
                    INSERT INTO f1_basket_constituents (
                        basket_id, ticker, portfolio_rank, selection_order,
                        f1_action_at_selection, technical_state_at_selection,
                        sector_state_at_selection, business_gate_at_selection,
                        sector_at_selection, reference_price, target_weight,
                        allocated_amount, quantity, gross_buy_value,
                        estimated_buy_cost, estimated_total_entry_cost,
                        current_price, current_market_value,
                        held_globally_at_selection, created_at, updated_at,
                        fill_status, broker,
                        target_slot_exposure, current_broker_qty, current_exposure,
                        exposure_gap, recommended_buy_qty, recommended_buy_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        basket_id,
                        c.ticker,
                        c.portfolio_rank,
                        c.selection_order,
                        cand.action,
                        cand.technical_state,
                        cand.sector_state,
                        cand.business_gate,
                        cand.sector,
                        c.reference_price,
                        c.target_weight,
                        c.allocated_amount,
                        c.quantity,
                        c.gross_buy_value,
                        c.estimated_buy_cost,
                        c.estimated_total_entry_cost,
                        c.reference_price,
                        c.gross_buy_value,
                        1 if cand.held_globally else 0,
                        now,
                        now,
                        FILL_PENDING,
                        "zerodha",
                        getattr(c, "target_slot_exposure", c.allocated_amount),
                        getattr(c, "current_broker_qty", 0),
                        getattr(c, "current_exposure", 0),
                        getattr(c, "exposure_gap", 0),
                        getattr(c, "recommended_buy_qty", c.quantity),
                        getattr(c, "recommended_buy_value", c.gross_buy_value),
                    ),
                )
        return basket_id

    def get_active_baskets(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM f1_baskets WHERE status IN ('ACTIVE','EXIT_PENDING','EXITING') ORDER BY created_at"
            ).fetchall()
            out = []
            for row in rows:
                b = dict(row)
                cons = conn.execute(
                    "SELECT * FROM f1_basket_constituents WHERE basket_id = ? ORDER BY selection_order",
                    (b["basket_id"],),
                ).fetchall()
                b["constituents"] = [dict(c) for c in cons]
                out.append(b)
            return out

    def get_current_operational_basket(self) -> Optional[dict]:
        """Most recent operational basket including exit/closed lifecycle."""
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM f1_baskets
                WHERE status IN ('READY','DEPLOYING','ACTIVE','EXIT_PENDING','EXITING','CLOSED')
                ORDER BY
                    CASE status
                        WHEN 'EXITING' THEN 0
                        WHEN 'EXIT_PENDING' THEN 1
                        WHEN 'ACTIVE' THEN 2
                        WHEN 'DEPLOYING' THEN 3
                        WHEN 'CLOSED' THEN 4
                        WHEN 'READY' THEN 5
                        ELSE 6
                    END,
                    created_at DESC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            basket = dict(row)
            cons = conn.execute(
                "SELECT * FROM f1_basket_constituents WHERE basket_id = ? ORDER BY selection_order",
                (basket["basket_id"],),
            ).fetchall()
            basket["constituents"] = [dict(c) for c in cons]
            return basket

    def mark_deploying(self, basket_id: str) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE f1_baskets SET status = ?, deployment_started_at = ?
                WHERE basket_id = ? AND status = 'READY'
                """,
                (STATUS_DEPLOYING, now, basket_id),
            )

    def update_constituent_order(
        self,
        basket_id: str,
        ticker: str,
        *,
        broker_order_id: str | None = None,
        fill_status: str | None = None,
        filled_qty: float | None = None,
        average_fill_price: float | None = None,
        error_message: str | None = None,
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fields: list[str] = ["updated_at = ?"]
        values: list[Any] = [now]
        if broker_order_id is not None:
            fields.append("broker_order_id = ?")
            values.append(broker_order_id)
        if fill_status is not None:
            fields.append("fill_status = ?")
            values.append(fill_status)
        if filled_qty is not None:
            fields.append("filled_qty = ?")
            values.append(filled_qty)
        if average_fill_price is not None:
            fields.append("average_fill_price = ?")
            values.append(average_fill_price)
        if error_message is not None:
            fields.append("last_error = ?")
            values.append(error_message)
        values.extend([basket_id, ticker])
        with self._conn() as conn:
            conn.execute(
                f"""
                UPDATE f1_basket_constituents SET {', '.join(fields)}
                WHERE basket_id = ? AND ticker = ?
                """,
                values,
            )

    def clear_constituent_for_retry(self, basket_id: str, ticker: str) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE f1_basket_constituents SET
                    broker_order_id = NULL,
                    fill_status = ?,
                    filled_qty = NULL,
                    average_fill_price = NULL,
                    last_error = NULL,
                    updated_at = ?
                WHERE basket_id = ? AND ticker = ?
                """,
                (FILL_PENDING, now, basket_id, ticker),
            )

    def activate_basket(
        self,
        basket_id: str,
        *,
        allocated_capital: float,
        basket_start_value: float,
        cash_remaining: float,
        target_value: float,
        stop_value: float,
        actual_buy_cost: float,
        constituent_updates: list[dict],
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE f1_baskets SET
                    status = ?, started_at = ?, allocated_capital = ?,
                    basket_start_value = ?, cash_remaining = ?,
                    target_value = ?, stop_value = ?,
                    current_value = ?, actual_buy_cost = ?, last_valued_at = ?
                WHERE basket_id = ? AND status = 'DEPLOYING'
                """,
                (
                    STATUS_ACTIVE,
                    now,
                    allocated_capital,
                    basket_start_value,
                    cash_remaining,
                    target_value,
                    stop_value,
                    basket_start_value,
                    actual_buy_cost,
                    now,
                    basket_id,
                ),
            )
            for u in constituent_updates:
                conn.execute(
                    """
                    UPDATE f1_basket_constituents SET
                        gross_buy_value = ?,
                        estimated_buy_cost = ?,
                        estimated_total_entry_cost = ?,
                        current_price = ?,
                        current_market_value = ?,
                        updated_at = ?
                    WHERE basket_id = ? AND ticker = ?
                    """,
                    (
                        u["gross_buy_value"],
                        u["estimated_buy_cost"],
                        u["estimated_total_entry_cost"],
                        u["current_price"],
                        u["current_market_value"],
                        now,
                        basket_id,
                        u["ticker"],
                    ),
                )

    def mark_exit_pending(
        self, basket_id: str, *, trigger: str, reason: str, trigger_value: float
    ) -> bool:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            cur = conn.execute(
                """
                UPDATE f1_baskets SET
                    status = ?, exit_trigger = ?, exit_reason = ?,
                    triggered_at = ?, trigger_basket_value = ?, last_valued_at = ?
                WHERE basket_id = ? AND status = 'ACTIVE' AND (exit_trigger IS NULL OR exit_trigger = '')
                """,
                (STATUS_EXIT_PENDING, trigger, reason, now, trigger_value, now, basket_id),
            )
            return cur.rowcount > 0

    def mark_exiting(self, basket_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE f1_baskets SET status = ? WHERE basket_id = ? AND status = 'EXIT_PENDING'",
                (STATUS_EXITING, basket_id),
            )

    def update_constituent_sell(
        self,
        basket_id: str,
        ticker: str,
        *,
        sell_broker_order_id: str | None = None,
        sell_status: str | None = None,
        sell_filled_qty: float | None = None,
        average_sell_fill_price: float | None = None,
        error_message: str | None = None,
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fields = ["updated_at = ?"]
        values: list[Any] = [now]
        if sell_broker_order_id is not None:
            fields.append("sell_broker_order_id = ?")
            values.append(sell_broker_order_id)
        if sell_status is not None:
            fields.append("sell_status = ?")
            values.append(sell_status)
        if sell_filled_qty is not None:
            fields.append("sell_filled_qty = ?")
            values.append(sell_filled_qty)
        if average_sell_fill_price is not None:
            fields.append("average_sell_fill_price = ?")
            values.append(average_sell_fill_price)
        if error_message is not None:
            fields.append("sell_last_error = ?")
            values.append(error_message)
        values.extend([basket_id, ticker])
        with self._conn() as conn:
            conn.execute(
                f"UPDATE f1_basket_constituents SET {', '.join(fields)} WHERE basket_id = ? AND ticker = ?",
                values,
            )

    def clear_constituent_sell_for_retry(self, basket_id: str, ticker: str) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE f1_basket_constituents SET
                    sell_broker_order_id = NULL, sell_status = 'PENDING',
                    sell_filled_qty = NULL, average_sell_fill_price = NULL,
                    sell_last_error = NULL, updated_at = ?
                WHERE basket_id = ? AND ticker = ?
                """,
                (now, basket_id, ticker),
            )

    def close_basket(
        self,
        basket_id: str,
        *,
        actual_sell_value: float,
        actual_sell_cost: float,
        actual_buy_cost: float,
        gross_pnl: float,
        net_pnl: float,
        return_pct: float,
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE f1_baskets SET
                    status = ?, completed_at = ?, current_value = ?,
                    actual_sell_value = ?, actual_sell_cost = ?, actual_buy_cost = ?,
                    gross_pnl = ?, net_pnl = ?, return_pct = ?, last_valued_at = ?
                WHERE basket_id = ? AND status = 'EXITING'
                """,
                (
                    STATUS_CLOSED, now, actual_sell_value,
                    actual_sell_value, actual_sell_cost, actual_buy_cost,
                    gross_pnl, net_pnl, return_pct, now, basket_id,
                ),
            )

    def get_current_preview_basket(self) -> Optional[dict]:
        return self.get_current_operational_basket()

    def count_resolved_slots(self, basket_id: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM f1_basket_constituents WHERE basket_id = ? AND slot_resolved = 1",
                (basket_id,),
            ).fetchone()
            return int(row["n"]) if row else 0

    def update_constituent_attribution(
        self,
        basket_id: str,
        ticker: str,
        *,
        adopted_existing_qty: float | None = None,
        basket_bought_qty: float | None = None,
        basket_attributed_qty: float | None = None,
        slot_resolved: int | None = None,
        slot_skipped: int | None = None,
        attribution_price: float | None = None,
        fill_status: str | None = None,
        gross_buy_value: float | None = None,
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fields = ["updated_at = ?"]
        values: list[Any] = [now]
        mapping = {
            "adopted_existing_qty": adopted_existing_qty,
            "basket_bought_qty": basket_bought_qty,
            "basket_attributed_qty": basket_attributed_qty,
            "slot_resolved": slot_resolved,
            "slot_skipped": slot_skipped,
            "attribution_price": attribution_price,
            "fill_status": fill_status,
            "gross_buy_value": gross_buy_value,
        }
        for col, val in mapping.items():
            if val is not None:
                fields.append(f"{col} = ?")
                values.append(val)
        values.extend([basket_id, ticker])
        with self._conn() as conn:
            conn.execute(
                f"UPDATE f1_basket_constituents SET {', '.join(fields)} WHERE basket_id = ? AND ticker = ?",
                values,
            )

    def get_basket(self, basket_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM f1_baskets WHERE basket_id = ?", (basket_id,)
            ).fetchone()
            if not row:
                return None
            basket = dict(row)
            cons = conn.execute(
                "SELECT * FROM f1_basket_constituents WHERE basket_id = ? ORDER BY selection_order",
                (basket_id,),
            ).fetchall()
            basket["constituents"] = [dict(c) for c in cons]
            return basket

    def update_valuation_snapshot(
        self, basket_id: str, valuation: Any, constituents: list[dict]
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE f1_baskets SET
                    current_value = ?, gross_pnl = ?, net_pnl = ?, return_pct = ?,
                    exit_trigger = ?, last_valued_at = ?
                WHERE basket_id = ?
                """,
                (
                    valuation.gross_market_value,
                    valuation.gross_pnl,
                    valuation.net_pnl,
                    valuation.return_pct,
                    valuation.trigger if valuation.trigger != "NONE" else None,
                    now,
                    basket_id,
                ),
            )
            for cv in constituents:
                if isinstance(cv, dict):
                    ticker = cv["ticker"]
                    cp = cv["current_price"]
                    cmv = cv["current_market_value"]
                    pnl = cv["constituent_pnl"]
                    ret = cv["constituent_return_pct"]
                else:
                    ticker = cv.ticker
                    cp = cv.current_price
                    cmv = cv.current_market_value
                    pnl = cv.constituent_pnl
                    ret = cv.constituent_return_pct
                conn.execute(
                    """
                    UPDATE f1_basket_constituents SET
                        current_price = ?, current_market_value = ?,
                        constituent_pnl = ?, constituent_return_pct = ?,
                        updated_at = ?
                    WHERE basket_id = ? AND ticker = ?
                    """,
                    (cp, cmv, pnl, ret, now, basket_id, ticker),
                )


_default_store: F1BasketStore | None = None


def get_basket_store(db_path: Path | None = None) -> F1BasketStore:
    global _default_store
    if db_path is not None:
        store = F1BasketStore(db_path)
        store.init_schema()
        return store
    if _default_store is None:
        _default_store = F1BasketStore()
        _default_store.init_schema()
    return _default_store
