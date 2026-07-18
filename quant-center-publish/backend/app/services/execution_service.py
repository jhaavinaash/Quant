"""Read-only execution pipeline view from Quant production sources."""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.schemas.execution import (
    ExecutionBrokerState,
    ExecutionCounts,
    ExecutionOrderRow,
    ExecutionSnapshot,
)
from app.services.production_broker_service import ProductionBrokerService

# Current lifecycle precedence — higher wins when the same attempt appears in
# multiple production sources (filled overrides submit errors, etc.).
_LIFECYCLE_PRECEDENCE = {
    "pending": 10,
    "submitted": 20,
    "approved": 30,
    "rejected_failed": 40,
    "filled": 50,
}


def _ensure_quant_path() -> None:
    quant_root = Path(settings.QUANT_BASE_DIR)
    if str(quant_root) not in sys.path:
        sys.path.insert(0, str(quant_root))


def _safe_int(value: object) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _key_request_id(value: object) -> str:
    text = str(value or "").strip()
    return f"req:{text}" if text else ""


def _key_broker_order_id(value: object) -> str:
    text = str(value or "").strip()
    return f"bo:{text}" if text else ""


def _key_trade_id(value: object) -> str:
    text = str(value or "").strip()
    return f"tid:{text}" if text else ""


def _concise_message(raw: str) -> str:
    """User-facing failure summary — raw IP/network strings stay out of the UI."""
    msg = str(raw or "").strip()
    if not msg:
        return ""

    lower = msg.lower()
    if "not allowed to place orders" in lower or "allowed ips" in lower:
        return "Broker rejected: IP not whitelisted"
    if "markets are closed" in lower:
        return "Broker rejected: markets closed"
    if "insufficient" in lower and ("fund" in lower or "margin" in lower):
        return "Broker rejected: insufficient funds"
    if "rms" in lower:
        return "Broker rejected: RMS rule"
    if len(msg) > 120:
        return msg[:117] + "..."
    return msg


@dataclass
class _AttemptRecord:
    lifecycle: str
    status: str
    precedence: int
    id: str
    engine: str = ""
    ticker: str = ""
    side: str = ""
    quantity: Optional[int] = None
    broker: str = ""
    broker_order_id: str = ""
    request_id: str = ""
    timestamp: str = ""
    message: str = ""
    alias_keys: set[str] = field(default_factory=set)


class _LifecycleIndex:
    """Merge production records that refer to the same order attempt."""

    def __init__(self) -> None:
        self._alias: dict[str, str] = {}
        self._records: dict[str, _AttemptRecord] = {}

    def _resolve(self, key: str) -> str:
        while key in self._alias and self._alias[key] != key:
            key = self._alias[key]
        return key

    def _link(self, keys: list[str]) -> str:
        keys = [k for k in keys if k]
        if not keys:
            return ""
        canonical = self._resolve(keys[0])
        for key in keys[1:]:
            root = self._resolve(key)
            if root != canonical:
                self._alias[root] = canonical
        return canonical

    def upsert(
        self,
        *,
        keys: list[str],
        lifecycle: str,
        status: str,
        record_id: str,
        engine: str = "",
        ticker: str = "",
        side: str = "",
        quantity: Optional[int] = None,
        broker: str = "",
        broker_order_id: str = "",
        request_id: str = "",
        timestamp: str = "",
        message: str = "",
    ) -> None:
        keys = [k for k in keys if k]
        if not keys:
            return

        canonical = self._link(keys)
        precedence = _LIFECYCLE_PRECEDENCE.get(lifecycle, 0)
        display_message = _concise_message(message) if lifecycle == "rejected_failed" else message.strip()

        candidate = _AttemptRecord(
            lifecycle=lifecycle,
            status=status,
            precedence=precedence,
            id=record_id,
            engine=engine,
            ticker=ticker,
            side=side,
            quantity=quantity,
            broker=broker,
            broker_order_id=broker_order_id,
            request_id=request_id,
            timestamp=timestamp,
            message=display_message,
            alias_keys=set(keys),
        )

        existing = self._records.get(canonical)
        if existing is None:
            self._records[canonical] = candidate
            return

        if precedence > existing.precedence:
            self._records[canonical] = candidate
            return

        if precedence == existing.precedence and timestamp > existing.timestamp:
            self._records[canonical] = candidate

    def to_rows(self) -> list[ExecutionOrderRow]:
        rows: list[ExecutionOrderRow] = []
        for record in self._records.values():
            rows.append(
                ExecutionOrderRow(
                    id=record.id,
                    lifecycle=record.lifecycle,
                    status=record.status,
                    engine=record.engine,
                    ticker=record.ticker,
                    side=record.side,
                    quantity=record.quantity,
                    broker=record.broker,
                    brokerOrderId=record.broker_order_id,
                    requestId=record.request_id,
                    timestamp=record.timestamp,
                    message=record.message,
                )
            )
        return rows


def _read_execution_log(limit: int = 500) -> list[dict]:
    _ensure_quant_path()
    try:
        from execution.execution_log import ExecutionLog

        path = ExecutionLog().path
    except Exception:
        path = Path(settings.QUANT_BASE_DIR) / "F0" / "production" / "execution_log.csv"

    if not path.exists():
        return []

    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        return list(reversed(rows))[:limit]
    except Exception:
        return []


def _pair_execution_log(rows: list[dict]) -> list[dict]:
    """Pair SUBMIT + RESULT by trade_id (OrderRouter correlation key)."""
    submits: dict[str, dict] = {}
    results: dict[str, dict] = {}
    for row in rows:
        trade_id = str(row.get("trade_id") or "").strip()
        if not trade_id:
            continue
        action = str(row.get("action") or "").upper()
        if action == "SUBMIT":
            submits[trade_id] = row
        elif action == "RESULT":
            results[trade_id] = row

    paired: list[dict] = []
    for trade_id, submit in submits.items():
        result = results.get(trade_id, {})
        result_status = str(result.get("status") or "").upper()
        broker_order_id = str(result.get("broker_order_id") or submit.get("broker_order_id") or "").strip()

        if result_status == "ERROR":
            lifecycle = "rejected_failed"
            status = "FAILED"
        elif result_status == "REJECTED":
            lifecycle = "rejected_failed"
            status = "REJECTED"
        elif broker_order_id or result_status in {"PLACED", "PENDING"}:
            lifecycle = "submitted"
            status = result_status or "PLACED"
        elif result_status:
            lifecycle = "submitted"
            status = result_status
        else:
            lifecycle = "submitted"
            status = str(submit.get("status") or "ATTEMPT").upper()

        paired.append(
            {
                "trade_id": trade_id,
                "lifecycle": lifecycle,
                "status": status,
                "engine": str(submit.get("engine") or result.get("engine") or ""),
                "ticker": str(submit.get("symbol") or result.get("symbol") or ""),
                "side": str(submit.get("side") or result.get("side") or ""),
                "quantity": _safe_int(submit.get("quantity") or result.get("quantity")),
                "broker": str(submit.get("broker") or result.get("broker") or ""),
                "broker_order_id": broker_order_id,
                "request_id": "",
                "timestamp": str(result.get("time") or submit.get("time") or ""),
                "message": str(result.get("message") or submit.get("message") or ""),
            }
        )
    return paired


def _build_lifecycle_index(
    pending_rows: list[dict],
    approved_rows: list[dict],
    rejected_broker_rows: list[dict],
    reconciled_rows: list[dict],
    execution_log_rows: list[dict],
) -> _LifecycleIndex:
    index = _LifecycleIndex()

    for row in pending_rows:
        request_id = str(row.get("request_id") or "")
        index.upsert(
            keys=[_key_request_id(request_id)],
            lifecycle="pending",
            status=str(row.get("status") or "PENDING"),
            record_id=request_id or str(row.get("id") or ""),
            engine=str(row.get("engine") or ""),
            ticker=str(row.get("symbol") or ""),
            side=str(row.get("side") or ""),
            quantity=_safe_int(row.get("quantity")),
            broker=str(row.get("broker") or ""),
            request_id=request_id,
            timestamp=str(row.get("created_at") or ""),
            message=str(row.get("remarks") or ""),
        )

    for row in approved_rows:
        request_id = str(row.get("request_id") or "")
        broker_order_id = str(row.get("broker_order_id") or "")
        trade_id = str(row.get("trade_id") or "")
        index.upsert(
            keys=[
                _key_request_id(request_id),
                _key_broker_order_id(broker_order_id),
                _key_trade_id(trade_id),
            ],
            lifecycle="approved",
            status="APPROVED",
            record_id=request_id or broker_order_id or trade_id,
            broker=str(row.get("broker") or ""),
            broker_order_id=broker_order_id,
            request_id=request_id,
            timestamp=str(row.get("approved_at") or ""),
            message=str(row.get("message") or ""),
        )

    for row in rejected_broker_rows:
        request_id = str(row.get("request_id") or "")
        rejected_by = str(row.get("rejected_by") or "")
        status = "REJECTED" if rejected_by == "broker" else rejected_by.upper() or "REJECTED"
        index.upsert(
            keys=[_key_request_id(request_id)],
            lifecycle="rejected_failed",
            status=status,
            record_id=request_id or str(row.get("id") or ""),
            engine=str(row.get("engine") or ""),
            ticker=str(row.get("symbol") or ""),
            side=str(row.get("side") or ""),
            quantity=_safe_int(row.get("quantity")),
            request_id=request_id,
            timestamp=str(row.get("rejected_at") or ""),
            message=str(row.get("broker_message") or ""),
        )

    for row in reconciled_rows:
        request_id = str(row.get("request_id") or "")
        broker_order_id = str(row.get("broker_order_id") or "")
        sync_status = str(row.get("status") or "").upper()

        if sync_status in {"COMPLETE", "PARTIAL"}:
            lifecycle = "filled"
        elif sync_status in {"REJECTED", "CANCELLED", "SYNC_FAILED"}:
            lifecycle = "rejected_failed"
        elif sync_status == "PENDING":
            lifecycle = "submitted"
        else:
            lifecycle = "submitted"

        index.upsert(
            keys=[_key_request_id(request_id), _key_broker_order_id(broker_order_id)],
            lifecycle=lifecycle,
            status=sync_status or "UNKNOWN",
            record_id=broker_order_id or request_id,
            engine=str(row.get("engine") or ""),
            ticker=str(row.get("symbol") or ""),
            side=str(row.get("side") or ""),
            quantity=_safe_int(row.get("fill_qty") or row.get("ordered_qty")),
            broker=str(row.get("broker") or ""),
            broker_order_id=broker_order_id,
            request_id=request_id,
            timestamp=str(row.get("fill_timestamp") or row.get("reconciled_at") or ""),
            message=str(row.get("error") or row.get("raw_status") or ""),
        )

    for attempt in _pair_execution_log(execution_log_rows):
        trade_id = str(attempt.get("trade_id") or "")
        broker_order_id = str(attempt.get("broker_order_id") or "")
        index.upsert(
            keys=[_key_trade_id(trade_id), _key_broker_order_id(broker_order_id)],
            lifecycle=str(attempt.get("lifecycle") or "submitted"),
            status=str(attempt.get("status") or ""),
            record_id=trade_id,
            engine=str(attempt.get("engine") or ""),
            ticker=str(attempt.get("ticker") or ""),
            side=str(attempt.get("side") or ""),
            quantity=attempt.get("quantity"),
            broker=str(attempt.get("broker") or ""),
            broker_order_id=broker_order_id,
            request_id=str(attempt.get("request_id") or ""),
            timestamp=str(attempt.get("timestamp") or ""),
            message=str(attempt.get("message") or ""),
        )

    return index


class ExecutionService:
    @classmethod
    def get_snapshot(cls) -> ExecutionSnapshot:
        _ensure_quant_path()

        pending_rows: list[dict] = []
        approved_rows: list[dict] = []
        rejected_broker_rows: list[dict] = []
        queue_stats = {"pending": 0, "approved": 0, "rejected": 0}

        try:
            from Signals.pending_order_queue import PendingOrderQueue

            queue = PendingOrderQueue()
            queue_stats = queue.stats()
            pending_rows = queue.list_pending()
            approved_rows = queue.list_approved()
            rejected_broker_rows = queue.list_rejected(broker_only=True)
        except Exception:
            pass

        reconciled_rows: list[dict] = []
        fills_stats = {
            "total": 0,
            "complete": 0,
            "partial": 0,
            "pending": 0,
            "rejected": 0,
            "failed": 0,
        }
        try:
            from execution.order_status_sync import OrderStatusSync

            sync = OrderStatusSync()
            reconciled_rows = sync.list_reconciled(limit=500)
            fills_stats = sync.fills_stats()
        except Exception:
            pass

        execution_log_rows = _read_execution_log(limit=500)
        index = _build_lifecycle_index(
            pending_rows,
            approved_rows,
            rejected_broker_rows,
            reconciled_rows,
            execution_log_rows,
        )
        merged = index.to_rows()

        pending = [row for row in merged if row.lifecycle == "pending"]
        approved = [row for row in merged if row.lifecycle == "approved"]
        submitted = [row for row in merged if row.lifecycle == "submitted"]
        filled = [row for row in merged if row.lifecycle == "filled"]
        rejected_failed = [row for row in merged if row.lifecycle == "rejected_failed"]

        broker_items = ProductionBrokerService.get_connectivity_statuses()
        broker_state = [
            ExecutionBrokerState(name=item.name, status=item.status) for item in broker_items
        ]

        counts = ExecutionCounts(
            pending=len(pending),
            approved=len(approved),
            submitted=len(submitted),
            filled=len(filled),
            rejectedFailed=len(rejected_failed),
            queueRejectedBroker=int(queue_stats.get("rejected", 0)),
            reconciledTotal=int(fills_stats.get("total", 0)),
        )

        return ExecutionSnapshot(
            counts=counts,
            brokerState=broker_state,
            pending=pending,
            approved=approved,
            submitted=submitted,
            filled=filled,
            rejectedFailed=rejected_failed,
        )
