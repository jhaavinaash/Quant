"""Server-side 30-minute AI Scanner live watch (IST market-session anchored).

PROTECTED CONTRACT — do not weaken during other feature work:
- Runs every 30 minutes from 09:30 IST through 15:30 IST (inclusive) on weekdays.
- Starts with FastAPI lifespan; must keep running while the backend is up.
- Emails only NEW opportunities (pipeline + event store dedupe by trading_date+ticker).
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Optional

import structlog

from app.services.ai_scanner_market_session import (
    current_or_recent_slot,
    due_scan_slot,
    format_slot_key,
    is_auto_scan_window,
    is_market_session_open,
    next_scheduled_slot,
    now_ist,
    seconds_until,
)
from app.services.ai_scanner_opportunity_pipeline import PipelineResult, process_qualifying_opportunities

log = structlog.get_logger(__name__)

_owner_lock = threading.Lock()
_watcher_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None
_started = False


@dataclass
class WatchStatus:
    status: str = "INACTIVE"  # ACTIVE | INACTIVE | ERROR
    lastAutomaticScan: str = ""
    nextScheduledScan: str = ""
    lastScanStatus: str = ""
    newSignalsToday: int = 0
    emailsSentToday: int = 0
    lastError: str = ""
    lastSlotKey: str = ""
    ownerPid: int = 0
    _executed_slots: set[str] = field(default_factory=set)


_status = WatchStatus()


def get_watch_status() -> WatchStatus:
    return _status


def _refresh_today_counts() -> None:
    from app.services.ai_scanner_event_store import get_event_store
    from app.services.ai_scanner_market_session import ist_trading_date

    store = get_event_store()
    td = ist_trading_date().isoformat()
    _status.newSignalsToday = store.count_for_trading_date(td)
    _status.emailsSentToday = store.count_emails_sent_for_trading_date(td)


def _update_next_slot() -> None:
    nxt = next_scheduled_slot()
    _status.nextScheduledScan = nxt.strftime("%Y-%m-%d %H:%M:%S IST") if nxt else ""


def _run_auto_cycle() -> PipelineResult | None:
    """Execute one automatic scan + opportunity pipeline cycle."""
    from app.services.ai_scanner_service import execute_production_scan

    scan, err = execute_production_scan(force=True)
    if not scan or err:
        _status.status = "ERROR"
        _status.lastScanStatus = f"ERROR: {err or 'scan failed'}"
        _status.lastError = _status.lastScanStatus
        log.error("ai_scanner_watch_scan_failed", error=err)
        return None

    try:
        pipe = process_qualifying_opportunities(scan, scan_source="AUTO")
        _status.lastAutomaticScan = now_ist().strftime("%Y-%m-%d %H:%M:%S IST")
        _status.lastScanStatus = (
            f"OK — qualifying={pipe.qualifying_count} "
            f"new={pipe.events_created} sent={pipe.emails_sent}"
        )
        _status.lastError = ""
        _status.status = "ACTIVE" if is_auto_scan_window() else "INACTIVE"
        _refresh_today_counts()
        log.info(
            "ai_scanner_watch_cycle_ok",
            qualifying=pipe.qualifying_count,
            new=pipe.events_created,
            emails_sent=pipe.emails_sent,
        )
        return pipe
    except Exception as exc:
        _status.status = "ERROR"
        _status.lastScanStatus = f"ERROR: pipeline failed"
        _status.lastError = str(exc)[:300]
        log.exception("ai_scanner_watch_pipeline_failed")
        return None


def _wait_for(stop: threading.Event, seconds: float, *, cap: float = 3600.0) -> None:
    """Sleep until the next wake, never shorter than 1s when a positive wait is intended."""
    wait_s = min(max(float(seconds), 1.0), cap)
    stop.wait(timeout=wait_s)


def _watcher_loop(stop: threading.Event) -> None:
    import os

    _status.ownerPid = os.getpid()
    log.info(
        "ai_scanner_watcher_started",
        pid=_status.ownerPid,
        schedule="09:30-15:30 IST every 30m",
    )

    while not stop.is_set():
        try:
            ts = now_ist()
            _update_next_slot()
            _refresh_today_counts()

            if not is_auto_scan_window(ts):
                _status.status = "INACTIVE"
                nxt = next_scheduled_slot(ts)
                if nxt:
                    _wait_for(stop, seconds_until(nxt) + 1.0, cap=3600.0)
                else:
                    _wait_for(stop, 300.0)
                continue

            _status.status = "ACTIVE"
            # Prefer due_scan_slot (25-min grace). current_or_recent_slot is the same API.
            slot_dt = due_scan_slot(ts) or current_or_recent_slot(ts)
            if slot_dt:
                slot_key = format_slot_key(slot_dt)
                if slot_key not in _status._executed_slots:
                    # Mark executed only after a successful cycle so failures retry
                    # within the same slot's grace window.
                    pipe = _run_auto_cycle()
                    if pipe is not None:
                        _status._executed_slots.add(slot_key)
                        _status.lastSlotKey = slot_key
                        nxt = next_scheduled_slot(now_ist())
                        if nxt:
                            _wait_for(stop, seconds_until(nxt) + 1.0, cap=3600.0)
                        continue
                    # Scan/pipeline failed — retry soon while still inside grace.
                    _wait_for(stop, 60.0)
                    continue

            nxt = next_scheduled_slot(ts)
            if nxt:
                _wait_for(stop, seconds_until(nxt) + 1.0, cap=3600.0)
            else:
                _wait_for(stop, 60.0)
        except Exception as exc:
            _status.status = "ERROR"
            _status.lastError = str(exc)[:300]
            log.exception("ai_scanner_watcher_loop_error")
            _wait_for(stop, 60.0)

    log.info("ai_scanner_watcher_stopped", pid=_status.ownerPid)


def start_ai_scanner_watcher() -> bool:
    """
    Start the background watcher thread once per process.
    Returns True if this call started the thread, False if already running.
    """
    global _watcher_thread, _stop_event, _started

    with _owner_lock:
        if _started and _watcher_thread and _watcher_thread.is_alive():
            return False
        _stop_event = threading.Event()
        _watcher_thread = threading.Thread(
            target=_watcher_loop,
            args=(_stop_event,),
            name="ai-scanner-watcher",
            daemon=True,
        )
        _watcher_thread.start()
        _started = True
        _update_next_slot()
        _refresh_today_counts()
        return True


def stop_ai_scanner_watcher() -> None:
    global _started
    with _owner_lock:
        if _stop_event:
            _stop_event.set()
        if _watcher_thread and _watcher_thread.is_alive():
            _watcher_thread.join(timeout=5)
        _started = False


async def start_ai_scanner_watcher_async() -> None:
    """Hook for FastAPI lifespan — starts daemon thread once."""
    started = start_ai_scanner_watcher()
    if started:
        await asyncio.to_thread(lambda: None)  # yield to log
        log.info("ai_scanner_watcher_registered")


async def stop_ai_scanner_watcher_async() -> None:
    stop_ai_scanner_watcher()
