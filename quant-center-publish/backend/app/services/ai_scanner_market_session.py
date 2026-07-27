"""IST NSE regular-session helpers for AI Scanner live watch scheduling.

PROTECTED CONTRACT — do not weaken during other feature work:
- Auto-scan every 30 minutes from 09:30 IST through 15:30 IST (inclusive), weekdays.
- Email only NEW qualifying opportunities (same trading_date + ticker once);
  that rule lives in ai_scanner_opportunity_pipeline + ai_scanner_event_store.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# Stable 30-minute scan slots: 09:30 → 15:30 IST inclusive (13 slots).
SCAN_SLOTS: tuple[time, ...] = (
    time(9, 30),
    time(10, 0),
    time(10, 30),
    time(11, 0),
    time(11, 30),
    time(12, 0),
    time(12, 30),
    time(13, 0),
    time(13, 30),
    time(14, 0),
    time(14, 30),
    time(15, 0),
    time(15, 30),
)

# How late after a slot the watcher may still fire it (covers slow wakes / long prior scans).
SLOT_GRACE_SEC = 25 * 60

# Auto-scan window: open slightly before first slot; stay open through last-slot grace.
_AUTO_SCAN_START = time(9, 15)
_AUTO_SCAN_END = time(15, 55)


def now_ist() -> datetime:
    return datetime.now(tz=IST)


def ist_trading_date(dt: datetime | None = None) -> date:
    """IST calendar date used as the trading-day identity for deduplication."""
    return (dt or now_ist()).date()


def is_nse_trading_day(d: date) -> bool:
    """Weekday gate; holidays are not modelled (matches existing dashboard pattern)."""
    return d.weekday() < 5


def is_market_session_open(dt: datetime | None = None) -> bool:
    """
    NSE regular cash session window (shared by F1 basket monitor and status labels).
    09:15–15:30 IST on weekdays.
    """
    ts = dt or now_ist()
    if not is_nse_trading_day(ts.date()):
        return False
    t = ts.time()
    return time(9, 15) <= t <= time(15, 30)


def is_auto_scan_window(dt: datetime | None = None) -> bool:
    """
    Window in which the AI Scanner watcher may start or finish a scheduled slot.
    Extends a few minutes past 15:30 so the 15:30 slot can still fire with grace.
    """
    ts = dt or now_ist()
    if not is_nse_trading_day(ts.date()):
        return False
    t = ts.time()
    return _AUTO_SCAN_START <= t <= _AUTO_SCAN_END


def slot_datetime(trading_day: date, slot: time) -> datetime:
    return datetime.combine(trading_day, slot, tzinfo=IST)


def format_slot_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def next_scheduled_slot(from_dt: datetime | None = None) -> datetime | None:
    """Next anchored scan slot from *from_dt* (no catch-up of missed slots)."""
    ts = from_dt or now_ist()
    day = ts.date()

    for _ in range(8):
        if is_nse_trading_day(day):
            for slot in SCAN_SLOTS:
                candidate = slot_datetime(day, slot)
                if candidate > ts:
                    return candidate
        day += timedelta(days=1)
        ts = slot_datetime(day, time(0, 0))
    return None


def due_scan_slot(
    from_dt: datetime | None = None,
    *,
    grace_sec: int = SLOT_GRACE_SEC,
) -> datetime | None:
    """
    Most recent scheduled slot that is due right now.

    A slot is due when:
      slot_time <= now <= slot_time + grace_sec
    and we are inside the auto-scan window.

    Using a 25-minute grace (not 90 seconds) prevents missed scans when the
    watcher wakes late or a previous universe scan overruns slightly.
    """
    ts = from_dt or now_ist()
    if not is_nse_trading_day(ts.date()) or not is_auto_scan_window(ts):
        return None
    due: datetime | None = None
    for slot in SCAN_SLOTS:
        slot_dt = slot_datetime(ts.date(), slot)
        delta = (ts - slot_dt).total_seconds()
        if 0 <= delta <= grace_sec:
            due = slot_dt
    return due


def current_or_recent_slot(
    from_dt: datetime | None = None,
    tolerance_sec: int = SLOT_GRACE_SEC,
) -> datetime | None:
    """
    Compatibility wrapper used by the watcher.

    Defaults to SLOT_GRACE_SEC (25 min). Prefer due_scan_slot() for new code.
    """
    return due_scan_slot(from_dt, grace_sec=tolerance_sec)


def seconds_until(dt: datetime) -> float:
    return max(0.0, (dt - now_ist()).total_seconds())
