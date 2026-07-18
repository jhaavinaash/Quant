"""IST NSE regular-session helpers for AI Scanner live watch scheduling."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# Stable 30-minute scan slots during regular NSE equity session (IST).
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
)


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
    Eligible NSE regular session window for automatic scans.
    Uses 09:15–15:30 IST on weekdays (slightly wider than slot list so 09:30 anchor is valid).
    """
    ts = dt or now_ist()
    if not is_nse_trading_day(ts.date()):
        return False
    t = ts.time()
    return time(9, 15) <= t <= time(15, 30)


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


def current_or_recent_slot(from_dt: datetime | None = None, tolerance_sec: int = 90) -> datetime | None:
    """
    Return the slot datetime if *from_dt* is within *tolerance_sec* after a scheduled slot.
    Used by the watcher to fire at most once per anchored slot.
    """
    ts = from_dt or now_ist()
    if not is_nse_trading_day(ts.date()) or not is_market_session_open(ts):
        return None
    for slot in SCAN_SLOTS:
        slot_dt = slot_datetime(ts.date(), slot)
        delta = (ts - slot_dt).total_seconds()
        if 0 <= delta <= tolerance_sec:
            return slot_dt
    return None


def seconds_until(dt: datetime) -> float:
    return max(0.0, (dt - now_ist()).total_seconds())
