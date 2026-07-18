"""Persistent SQLite store for AI Scanner NEW opportunity events."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from app.services.ai_scanner_market_session import IST, ist_trading_date, now_ist


def normalize_ticker(ticker: str) -> str:
    return str(ticker).strip().upper().replace(".NS", "").replace(".BO", "")


def _default_db_path() -> Path:
    from app.core.config import settings

    return Path(settings.QUANT_BASE_DIR) / "F0" / "production" / "ai_scanner_events.db"


@dataclass
class OpportunityEvent:
    id: int
    event_id: str
    trading_date: str
    ticker: str
    ticker_norm: str
    detected_at: str
    score: Optional[float]
    signal: Optional[str]
    groups_met: Optional[int]
    entry: Optional[float]
    sl: Optional[float]
    target: Optional[float]
    qty: Optional[int]
    risk: Optional[float]
    sector: Optional[str]
    reason: Optional[str]
    scan_run_id: Optional[str]
    scan_source: str
    email_status: str
    email_sent_at: Optional[str]
    email_error: Optional[str]
    created_at: str
    updated_at: str


class AIScannerEventStore:
    EMAIL_PENDING = "PENDING"
    EMAIL_SENT = "SENT"
    EMAIL_FAILED = "FAILED"

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = Path(db_path) if db_path else _default_db_path()

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
                CREATE TABLE IF NOT EXISTS ai_opportunity_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    trading_date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    ticker_norm TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    score REAL,
                    signal TEXT,
                    groups_met INTEGER,
                    entry REAL,
                    sl REAL,
                    target REAL,
                    qty INTEGER,
                    risk REAL,
                    sector TEXT,
                    reason TEXT,
                    scan_run_id TEXT,
                    scan_source TEXT NOT NULL,
                    email_status TEXT NOT NULL DEFAULT 'PENDING',
                    email_sent_at TEXT,
                    email_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (trading_date, ticker_norm)
                );
                CREATE INDEX IF NOT EXISTS idx_ai_events_trading_date
                    ON ai_opportunity_events (trading_date);
                CREATE INDEX IF NOT EXISTS idx_ai_events_ticker_norm
                    ON ai_opportunity_events (ticker_norm);
                """
            )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> OpportunityEvent:
        return OpportunityEvent(
            id=int(row["id"]),
            event_id=str(row["event_id"]),
            trading_date=str(row["trading_date"]),
            ticker=str(row["ticker"]),
            ticker_norm=str(row["ticker_norm"]),
            detected_at=str(row["detected_at"]),
            score=row["score"],
            signal=row["signal"],
            groups_met=row["groups_met"],
            entry=row["entry"],
            sl=row["sl"],
            target=row["target"],
            qty=row["qty"],
            risk=row["risk"],
            sector=row["sector"],
            reason=row["reason"],
            scan_run_id=row["scan_run_id"],
            scan_source=str(row["scan_source"]),
            email_status=str(row["email_status"]),
            email_sent_at=row["email_sent_at"],
            email_error=row["email_error"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def get_by_trading_date_ticker(
        self, trading_date: str, ticker: str
    ) -> Optional[OpportunityEvent]:
        norm = normalize_ticker(ticker)
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM ai_opportunity_events
                WHERE trading_date = ? AND ticker_norm = ?
                """,
                (trading_date, norm),
            ).fetchone()
        return self._row_to_event(row) if row else None

    def insert_event(
        self,
        *,
        trading_date: str,
        ticker: str,
        scan_source: str,
        scan_run_id: str,
        detected_at: str | None = None,
        score: float | None = None,
        signal: str | None = None,
        groups_met: int | None = None,
        entry: float | None = None,
        sl: float | None = None,
        target: float | None = None,
        qty: int | None = None,
        risk: float | None = None,
        sector: str | None = None,
        reason: str | None = None,
    ) -> tuple[OpportunityEvent | None, bool]:
        """
        Insert a new event. Returns (event, created).
        created=False when (trading_date, ticker_norm) already exists.
        """
        norm = normalize_ticker(ticker)
        now = detected_at or now_ist().strftime("%Y-%m-%d %H:%M:%S")
        event_id = f"{trading_date}|{norm}|{uuid.uuid4().hex[:8]}"
        with self._conn() as conn:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO ai_opportunity_events (
                        event_id, trading_date, ticker, ticker_norm, detected_at,
                        score, signal, groups_met, entry, sl, target, qty, risk,
                        sector, reason, scan_run_id, scan_source,
                        email_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        trading_date,
                        ticker,
                        norm,
                        now,
                        score,
                        signal,
                        groups_met,
                        entry,
                        sl,
                        target,
                        qty,
                        risk,
                        sector,
                        reason,
                        scan_run_id,
                        scan_source,
                        self.EMAIL_PENDING,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError:
                return None, False
            row = conn.execute(
                "SELECT * FROM ai_opportunity_events WHERE id = ?",
                (int(cur.lastrowid),),
            ).fetchone()
        return (self._row_to_event(row) if row else None), True

    def update_email_sent(self, event_id: str) -> None:
        now = now_ist().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE ai_opportunity_events
                SET email_status = ?, email_sent_at = ?, email_error = NULL, updated_at = ?
                WHERE event_id = ?
                """,
                (self.EMAIL_SENT, now, now, event_id),
            )

    def update_email_failed(self, event_id: str, error: str) -> None:
        now = now_ist().strftime("%Y-%m-%d %H:%M:%S")
        safe = (error or "email failed")[:500]
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE ai_opportunity_events
                SET email_status = ?, email_error = ?, updated_at = ?
                WHERE event_id = ?
                """,
                (self.EMAIL_FAILED, safe, now, event_id),
            )

    def list_for_trading_date(self, trading_date: str) -> list[OpportunityEvent]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM ai_opportunity_events
                WHERE trading_date = ?
                ORDER BY detected_at DESC
                """,
                (trading_date,),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def count_for_trading_date(self, trading_date: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM ai_opportunity_events WHERE trading_date = ?",
                (trading_date,),
            ).fetchone()
        return int(row["c"]) if row else 0

    def count_emails_sent_for_trading_date(self, trading_date: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM ai_opportunity_events
                WHERE trading_date = ? AND email_status = ?
                """,
                (trading_date, self.EMAIL_SENT),
            ).fetchone()
        return int(row["c"]) if row else 0


_default_store: AIScannerEventStore | None = None


def get_event_store(db_path: Path | None = None) -> AIScannerEventStore:
    global _default_store
    if db_path is not None:
        store = AIScannerEventStore(db_path)
        store.init_schema()
        return store
    if _default_store is None:
        _default_store = AIScannerEventStore()
        _default_store.init_schema()
    return _default_store
