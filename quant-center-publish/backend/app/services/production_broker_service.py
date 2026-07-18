"""Production broker layer — wraps Quant execution/BrokerManager (dashboard/app_ai.py).

Uses a process-singleton BrokerManager so connect state persists across API calls,
matching Streamlit st.session_state['broker_manager'] behaviour.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.schemas.broker_connectivity import BrokerConnectivityItem
from app.schemas.production_broker import (
    ProductionBrokerCard,
    ProductionBrokerConnectAllResult,
    ProductionBrokerConnectResult,
    ProductionBrokerSummary,
)

_manager = None
_execution_available: Optional[bool] = None

_EXTRA_BROKERS = [
    {"name": "angel", "display_name": "ANGEL ONE"},
]


def _ensure_quant_path() -> Path:
    quant_root = Path(settings.QUANT_BASE_DIR)
    if str(quant_root) not in sys.path:
        sys.path.insert(0, str(quant_root))
    return quant_root


def get_production_broker_manager():
    """Session-equivalent singleton from dashboard/app_ai.py get_broker_manager()."""
    global _manager, _execution_available

    if _execution_available is False:
        return None

    if _manager is not None:
        return _manager

    quant_root = _ensure_quant_path()
    if not quant_root.exists():
        _execution_available = False
        return None

    try:
        from execution.broker_factory import create_broker_manager

        _manager = create_broker_manager()
        _execution_available = True
        return _manager
    except Exception:
        _execution_available = False
        return None


def _zerodha_configured() -> bool:
    try:
        _ensure_quant_path()
        from credentials.broker_credentials import ZERODHA_ACCESS_TOKEN, ZERODHA_API_KEY

        return bool(str(ZERODHA_API_KEY or "").strip() and str(ZERODHA_ACCESS_TOKEN or "").strip())
    except Exception:
        return False


def _aliceblue_configured() -> bool:
    return False


def _angel_configured() -> bool:
    try:
        _ensure_quant_path()
        from credentials.broker_credentials import ANGEL_API_KEY, ANGEL_CLIENT_ID

        return bool(str(ANGEL_API_KEY or "").strip() and str(ANGEL_CLIENT_ID or "").strip())
    except Exception:
        return False


def _broker_configured(name: str) -> bool:
    key = name.lower()
    if key == "zerodha":
        return _zerodha_configured()
    if key == "aliceblue":
        return _aliceblue_configured()
    if key == "angel":
        return _angel_configured()
    return False


def _adapter_implemented(name: str) -> bool:
    key = name.lower()
    if key == "zerodha":
        return True
    if key == "aliceblue":
        return False
    if key == "angel":
        return False
    return False


def _resolve_status(name: str, configured: bool, implemented: bool, is_connected: bool) -> str:
    if not implemented:
        return "NOT CONFIGURED"
    if not configured:
        return "NOT CONFIGURED"
    return "CONNECTED" if is_connected else "NOT CONNECTED"


def _safe_account(adapter) -> dict:
    try:
        return adapter.get_account() or {}
    except Exception as exc:
        return {"connected": False, "_error": f"{type(exc).__name__}: {exc}"}


def _card_from_adapter(manager, broker_name: str) -> ProductionBrokerCard:
    adapter = manager.get(broker_name)
    configured = _broker_configured(broker_name)
    implemented = _adapter_implemented(broker_name)

    if adapter is None:
        return ProductionBrokerCard(
            name=broker_name,
            displayName=broker_name.upper(),
            status="UNAVAILABLE",
            configured=configured,
        )

    account = _safe_account(adapter) if implemented and configured else {}
    account_connected = bool(account.get("connected", False))
    is_connected = account_connected or adapter.is_connected()
    status = _resolve_status(broker_name, configured, implemented, is_connected)

    cash = account.get("available_cash", 0.0)
    try:
        available_cash = float(cash) if cash is not None else None
    except (TypeError, ValueError):
        available_cash = None

    return ProductionBrokerCard(
        name=broker_name,
        displayName=broker_name.upper(),
        status=status,
        configured=configured and implemented,
        userName=str(account.get("user_name") or "") or None,
        userId=str(account.get("user_id") or "") or None,
        email=str(account.get("email") or "") or None,
        availableCash=available_cash,
        error=str(account.get("_error") or "") or None,
    )


def _static_card(name: str, display_name: str) -> ProductionBrokerCard:
    configured = _broker_configured(name)
    implemented = _adapter_implemented(name)
    return ProductionBrokerCard(
        name=name,
        displayName=display_name,
        status=_resolve_status(name, configured, implemented, False),
        configured=configured and implemented,
    )


class ProductionBrokerService:
    @classmethod
    def get_summary(cls) -> ProductionBrokerSummary:
        manager = get_production_broker_manager()
        if manager is None:
            cards = [
                ProductionBrokerCard(
                    name="broker-layer",
                    displayName="BROKER LAYER",
                    status="UNAVAILABLE",
                    configured=False,
                )
            ]
            return ProductionBrokerSummary(connectedCount=0, totalCount=len(cards), brokers=cards)

        cards: list[ProductionBrokerCard] = []
        registered = set(manager.list_brokers())

        for broker_name in sorted(registered):
            cards.append(_card_from_adapter(manager, broker_name))

        for extra in _EXTRA_BROKERS:
            if extra["name"] not in registered:
                cards.append(_static_card(extra["name"], extra["display_name"]))

        connected_count = sum(1 for card in cards if card.status == "CONNECTED")
        return ProductionBrokerSummary(
            connectedCount=connected_count,
            totalCount=len(cards),
            brokers=cards,
        )

    @classmethod
    def get_connectivity_statuses(cls) -> list[BrokerConnectivityItem]:
        summary = cls.get_summary()
        if len(summary.brokers) == 1 and summary.brokers[0].name == "broker-layer":
            return [BrokerConnectivityItem(name="BROKER LAYER", status="UNAVAILABLE")]

        return [
            BrokerConnectivityItem(name=card.displayName, status=card.status)
            for card in summary.brokers
        ]

    @classmethod
    def connect(cls, broker_name: str) -> ProductionBrokerConnectResult:
        manager = get_production_broker_manager()
        if manager is None:
            return ProductionBrokerConnectResult(
                broker=broker_name,
                success=False,
                status="UNAVAILABLE",
                message="Broker execution layer unavailable.",
            )

        key = broker_name.lower().strip()
        if not _adapter_implemented(key):
            return ProductionBrokerConnectResult(
                broker=key,
                success=False,
                status="NOT CONFIGURED",
                message="Broker adapter not implemented in production system.",
            )

        if not _broker_configured(key):
            return ProductionBrokerConnectResult(
                broker=key,
                success=False,
                status="NOT CONFIGURED",
                message="Broker credentials not configured in production system.",
            )

        adapter = manager.get(key)
        if adapter is None:
            return ProductionBrokerConnectResult(
                broker=key,
                success=False,
                status="UNAVAILABLE",
                message="Broker adapter not registered.",
            )

        try:
            response = adapter.connect()
            success = bool(getattr(response, "success", False))
            message = str(getattr(response, "message", "") or "")
            status = "CONNECTED" if success and adapter.is_connected() else "NOT CONNECTED"
            return ProductionBrokerConnectResult(
                broker=key,
                success=success,
                status=status,
                message=message,
            )
        except Exception as exc:
            return ProductionBrokerConnectResult(
                broker=key,
                success=False,
                status="NOT CONNECTED",
                message=f"{type(exc).__name__}: {exc}",
            )

    @classmethod
    def connect_all(cls) -> ProductionBrokerConnectAllResult:
        manager = get_production_broker_manager()
        if manager is None:
            return ProductionBrokerConnectAllResult(results=[], connectedCount=0, totalCount=0)

        results: list[ProductionBrokerConnectResult] = []
        for broker_name in manager.list_brokers():
            if _adapter_implemented(broker_name) and _broker_configured(broker_name):
                results.append(cls.connect(broker_name))
            else:
                results.append(
                    ProductionBrokerConnectResult(
                        broker=broker_name,
                        success=False,
                        status="NOT CONFIGURED",
                        message="Broker not configured or adapter not implemented.",
                    )
                )

        connected_count = sum(1 for item in results if item.success)
        return ProductionBrokerConnectAllResult(
            results=results,
            connectedCount=connected_count,
            totalCount=len(results),
        )
