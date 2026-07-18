"""Server-side F1 Basket monitor — 5-minute ACTIVE valuation + auto TP/SL exit."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Optional

import structlog

from app.services.ai_scanner_market_session import is_market_session_open, now_ist
from app.services.f1_basket.constants import (
    EXIT_REASON_STOP,
    EXIT_REASON_TARGET,
    MONITOR_INTERVAL_SEC,
    STATUS_ACTIVE,
    STATUS_EXIT_PENDING,
    STATUS_EXITING,
)
from app.services.f1_basket.exit import mark_exit_trigger, submit_basket_exits, sync_basket_exits
from app.services.f1_basket.live_valuation import value_active_basket
from app.services.f1_basket.store import get_basket_store

log = structlog.get_logger(__name__)

_owner_lock = threading.Lock()
_watcher_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None


@dataclass
class BasketMonitorStatus:
    status: str = "INACTIVE"
    lastCycleAt: str = ""
    lastMessage: str = ""
    lastError: str = ""
    ownerPid: int = 0
    intervalSec: int = MONITOR_INTERVAL_SEC
    duplicateNote: str = "One monitor thread per Python process; multiple uvicorn workers = multiple monitors."


_status = BasketMonitorStatus()


def get_monitor_status() -> BasketMonitorStatus:
    return _status


def run_monitor_cycle() -> str:
    """Single valuation + trigger + exit cycle. Safe to call from API or watcher."""
    store = get_basket_store()
    messages: list[str] = []

    for basket in store.get_active_baskets():
        bid = basket["basket_id"]
        st = basket["status"]

        if st == STATUS_ACTIVE:
            result = value_active_basket(bid, store=store)
            if not result:
                continue
            if result.trigger in ("TARGET", "STOP"):
                reason = EXIT_REASON_TARGET if result.trigger == "TARGET" else EXIT_REASON_STOP
                if mark_exit_trigger(
                    bid,
                    trigger=result.trigger,
                    reason=reason,
                    trigger_value=result.valuation.gross_market_value,
                    store=store,
                ):
                    messages.append(f"{bid}: {result.trigger} triggered")
                    submit_basket_exits(bid, store=store)
            else:
                messages.append(f"{bid}: valued trigger=NONE")

        elif st == STATUS_EXIT_PENDING:
            submit_basket_exits(bid, store=store)
            messages.append(f"{bid}: exit submit")

        elif st == STATUS_EXITING:
            sync = sync_basket_exits(bid, store=store)
            messages.append(f"{bid}: {sync.message}")

    return " · ".join(messages) if messages else "no active baskets"


def _loop() -> None:
    import os
    _status.ownerPid = os.getpid()
    while _stop_event and not _stop_event.is_set():
        try:
            if is_market_session_open():
                _status.status = "ACTIVE"
                msg = run_monitor_cycle()
                _status.lastCycleAt = now_ist().strftime("%Y-%m-%d %H:%M:%S IST")
                _status.lastMessage = msg
                _status.lastError = ""
            else:
                _status.status = "INACTIVE"
        except Exception as exc:
            _status.status = "ERROR"
            _status.lastError = str(exc)[:300]
            log.exception("f1_basket_monitor_cycle_failed")
        if _stop_event.wait(MONITOR_INTERVAL_SEC):
            break


def start_basket_monitor() -> bool:
    global _watcher_thread, _stop_event
    with _owner_lock:
        if _watcher_thread and _watcher_thread.is_alive():
            return False
        _stop_event = threading.Event()
        _watcher_thread = threading.Thread(target=_loop, name="f1-basket-monitor", daemon=True)
        _watcher_thread.start()
        return True


def stop_basket_monitor() -> None:
    global _watcher_thread, _stop_event
    with _owner_lock:
        if _stop_event:
            _stop_event.set()
        if _watcher_thread:
            _watcher_thread.join(timeout=5)
        _watcher_thread = None
        _stop_event = None


async def start_basket_monitor_async() -> None:
    start_basket_monitor()
    log.info("f1_basket_monitor_started", interval=MONITOR_INTERVAL_SEC)


async def stop_basket_monitor_async() -> None:
    stop_basket_monitor()
    log.info("f1_basket_monitor_stopped")
