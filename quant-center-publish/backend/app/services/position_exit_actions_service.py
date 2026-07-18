"""Broker-backed position exit — thin wrapper over production PositionExitService."""

from __future__ import annotations

import sys

from app.core.config import settings
from app.schemas.position import PositionExitResult
from app.services.execution_actions_service import ExecutionActionsService
from app.services.production_broker_service import (
    ProductionBrokerService,
    get_production_broker_manager,
)


def _ensure_quant_path() -> None:
    quant_root = settings.QUANT_BASE_DIR
    if quant_root not in sys.path:
        sys.path.insert(0, quant_root)


def _zerodha_connected() -> tuple[bool, str]:
    for item in ProductionBrokerService.get_connectivity_statuses():
        name = item.name.lower()
        if "zerodha" in name:
            if item.status == "CONNECTED":
                return True, ""
            return False, f"Zerodha is {item.status}. Connect Zerodha before exiting positions."
    return False, "Zerodha is NOT CONNECTED. Connect Zerodha before exiting positions."


class PositionExitActionsService:
    @classmethod
    def request_exit(cls, trade_key: str, exit_reason: str) -> PositionExitResult:
        """Submit SELL exit for one exact OPEN trade via production pipeline."""
        _ensure_quant_path()
        ready, block_msg = _zerodha_connected()
        if not ready:
            return PositionExitResult(
                success=False,
                message=block_msg,
                tradeKey=trade_key,
                status="BROKER_NOT_CONNECTED",
            )

        try:
            from execution.position_exit_service import PositionExitService
        except Exception as exc:
            return PositionExitResult(
                success=False,
                message=f"Position exit service unavailable: {exc}",
                tradeKey=trade_key,
            )

        manager = get_production_broker_manager()
        svc = PositionExitService(broker_manager=manager)
        result = svc.request_exit(trade_key, exit_reason, broker="zerodha")

        label = ""
        if result.status:
            try:
                from execution.position_exit_service import PositionExitService as PES

                label = PES.exit_status_label(result.status)
            except Exception:
                label = result.status

        return PositionExitResult(
            success=result.success,
            message=result.message,
            tradeKey=result.trade_key or trade_key,
            exitId=result.exit_id,
            brokerOrderId=result.broker_order_id,
            status=result.status,
            exitStatusLabel=label,
        )

    @classmethod
    def sync_exits(cls, force: bool = False) -> PositionExitResult:
        """Reconcile exit fills via production OrderStatusSync.run()."""
        sync_result = ExecutionActionsService.sync_order_status(force=force)
        return PositionExitResult(
            success=sync_result.success,
            message=sync_result.message,
            status=sync_result.outcome,
        )
