"""Execution control actions — thin wrappers over the production pipeline.

Mutations go ONLY through:
  - Signals.signal_dispatcher.approve / reject
  - execution.order_status_sync.OrderStatusSync.run

Never writes directly to signal_layer.db, trades_log.csv, or reconciled_fills.csv.

Note: production SignalDispatcher.approve() combines user approval AND broker
submission in one call. There is no separate approve-only production method.
"""

from __future__ import annotations

import sys

from app.core.config import settings
from app.schemas.execution import ExecutionActionResult, ExecutionSyncSummary
from app.services.production_broker_service import ProductionBrokerService


def _ensure_quant_path() -> None:
    quant_root = settings.QUANT_BASE_DIR
    if quant_root not in sys.path:
        sys.path.insert(0, quant_root)


def _broker_ready(broker: str) -> tuple[bool, str]:
    """Return whether the order's broker is CONNECTED (production BrokerManager)."""
    key = (broker or "zerodha").strip().lower()
    for item in ProductionBrokerService.get_connectivity_statuses():
        name = item.name.lower()
        if key in name or name.replace(" ", "") in key.replace(" ", ""):
            if item.status == "CONNECTED":
                return True, ""
            return False, f"{item.name} is {item.status}. Connect the broker before submitting orders."
    if key == "zerodha" or "zerodha" in key:
        return False, "Zerodha is NOT CONNECTED. Connect Zerodha before submitting orders."
    return False, f"Broker '{broker}' is not connected."


def _sync_message(summary) -> tuple[bool, str]:
    """Mirror dashboard/app_ai.py Sync Fills messaging."""
    parts: list[str] = []
    if summary.filled > 0:
        parts.append(f"{summary.filled} BUY fill(s) written to trades_log")
    exits_closed = getattr(summary, "exits_closed", 0)
    if exits_closed > 0:
        parts.append(f"{exits_closed} position(s) closed via SELL fill")
    if parts:
        msg = " · ".join(parts)
        msg += f" · {summary.pending} still pending · {summary.rejected} rejected"
        return True, msg
    if summary.failed > 0:
        msg = (
            f"{summary.failed} order(s) could not be synced "
            "(broker auth may have expired)."
        )
        if summary.errors:
            msg += f" {summary.errors[0]}"
        return False, msg
    if summary.pending > 0:
        return True, f"{summary.pending} order(s) still PENDING at broker · no new fills to record."
    exits_checked = getattr(summary, "exits_checked", 0)
    if summary.total_checked == 0 and exits_checked == 0:
        return True, "No approved orders to sync. All orders are already reconciled."
    return True, "No new fills. All approved orders are already reconciled."


def _summary_to_schema(summary) -> ExecutionSyncSummary:
    return ExecutionSyncSummary(
        totalChecked=summary.total_checked,
        filled=summary.filled,
        pending=summary.pending,
        rejected=summary.rejected,
        failed=summary.failed,
        exitsChecked=getattr(summary, "exits_checked", 0),
        exitsClosed=getattr(summary, "exits_closed", 0),
        errors=list(summary.errors or []),
    )


class ExecutionActionsService:
    @classmethod
    def submit_pending(cls, request_id: str) -> ExecutionActionResult:
        """Broker submission via Signals.signal_dispatcher.approve.

        Production approve() submits to ExecutionService then records audit on
        success. Broker connectivity is required for submission.
        """
        _ensure_quant_path()
        try:
            from Signals.pending_order_queue import PendingOrderQueue
            from Signals.signal_dispatcher import approve
        except Exception as exc:
            return ExecutionActionResult(
                success=False,
                kind="submit",
                message=f"Production signal layer unavailable: {exc}",
                requestId=request_id,
            )

        row = PendingOrderQueue().get(request_id)
        if row is None:
            return ExecutionActionResult(
                success=False,
                kind="submit",
                outcome="ERROR",
                message=f"unknown request_id={request_id}",
                requestId=request_id,
            )
        if row.get("status") != "PENDING":
            return ExecutionActionResult(
                success=False,
                kind="submit",
                outcome="ERROR",
                message=f"request_id={request_id} is not PENDING",
                requestId=request_id,
            )

        ready, block_msg = _broker_ready(str(row.get("broker", "zerodha")))
        if not ready:
            return ExecutionActionResult(
                success=False,
                kind="submit",
                outcome="BROKER_NOT_CONNECTED",
                message=block_msg,
                requestId=request_id,
            )

        result = approve(request_id)
        success = result.outcome == "AUTO_EXECUTED"
        broker_order_id = ""
        if result.order_response:
            broker_order_id = str(result.order_response.get("broker_order_id", "") or "")

        return ExecutionActionResult(
            success=success,
            kind="submit",
            outcome=result.outcome,
            message=result.message or ("order placed" if success else "submission failed"),
            requestId=request_id,
            brokerOrderId=broker_order_id,
        )

    @classmethod
    def reject_pending(cls, request_id: str, reason: str) -> ExecutionActionResult:
        """User rejection → Signals.signal_dispatcher.reject → PendingOrderQueue.reject."""
        _ensure_quant_path()
        try:
            from Signals.signal_dispatcher import reject
        except Exception as exc:
            return ExecutionActionResult(
                success=False,
                kind="reject",
                message=f"Production signal layer unavailable: {exc}",
                requestId=request_id,
            )

        moved = reject(request_id, reason=reason)
        if not moved:
            return ExecutionActionResult(
                success=False,
                kind="reject",
                outcome="ERROR",
                message=f"unknown request_id={request_id}",
                requestId=request_id,
            )

        symbol = str(moved.get("symbol", "") or "")
        return ExecutionActionResult(
            success=True,
            kind="reject",
            outcome="REJECTED",
            message=f"Moved to rejected audit{f': {symbol}' if symbol else ''}",
            requestId=request_id,
        )

    @classmethod
    def sync_order_status(cls, force: bool = False) -> ExecutionActionResult:
        """Page-level fill reconciliation → OrderStatusSync.run(force=...)."""
        _ensure_quant_path()
        try:
            from execution.order_status_sync import OrderStatusSync
        except Exception as exc:
            return ExecutionActionResult(
                success=False,
                kind="sync",
                message=f"OrderStatusSync unavailable: {exc}",
            )

        summary = OrderStatusSync().run(force=force)
        ok, message = _sync_message(summary)
        return ExecutionActionResult(
            success=ok,
            kind="sync",
            outcome="SYNCED" if ok else "SYNC_PARTIAL",
            message=message,
            sync=_summary_to_schema(summary),
        )
