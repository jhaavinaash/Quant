"""Shared AI Scanner opportunity detection + email pipeline (AUTO and MANUAL).

PROTECTED CONTRACT — email only NEW opportunities:
- Qualifying set = scan['strong_buys'] only (not watchlist).
- One event per (trading_date, ticker); duplicates never re-email once SENT.
- Failed emails may retry while the ticker is still qualifying the same day.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import structlog

from app.services.ai_scanner_event_store import (
    AIScannerEventStore,
    OpportunityEvent,
    get_event_store,
    normalize_ticker,
)
from app.services.ai_scanner_market_session import ist_trading_date, now_ist

log = structlog.get_logger(__name__)

EmailSender = Callable[[str, str], bool]


@dataclass
class PipelineResult:
    scan_run_id: str = ""
    trading_date: str = ""
    qualifying_count: int = 0
    events_created: int = 0
    emails_attempted: int = 0
    emails_sent: int = 0
    emails_failed: int = 0
    errors: list[str] = field(default_factory=list)


def _default_email_sender(subject: str, body: str) -> bool:
    try:
        import sys
        from pathlib import Path

        from app.core.config import settings

        root = Path(settings.QUANT_BASE_DIR)
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from alerts.notifier import send_email

        return bool(send_email(subject, body))
    except Exception as exc:
        log.warning("ai_scanner_email_sender_failed", error=str(exc))
        return False


def _reason_from_result(r: Any) -> str:
    bulls = getattr(r, "bull_signals", None) or []
    if bulls:
        return " · ".join(list(bulls)[:4])
    return ""


def _build_email_body(event: OpportunityEvent) -> str:
    detected = event.detected_at
    lines = [
        "AI Opportunity Scanner — NEW qualifying opportunity",
        "",
        f"Ticker: {event.ticker}",
        f"Detected (IST): {detected}",
        f"Score: {event.score if event.score is not None else '—'}",
        f"Signal: {event.signal or '—'}",
        f"Groups Met: {event.groups_met if event.groups_met is not None else '—'}",
        f"Entry: {event.entry if event.entry is not None else '—'}",
        f"Stop Loss: {event.sl if event.sl is not None else '—'}",
        f"Target: {event.target if event.target is not None else '—'}",
        f"Quantity: {event.qty if event.qty is not None else '—'}",
        f"Risk (₹): {event.risk if event.risk is not None else '—'}",
        f"Sector: {event.sector or '—'}",
        "",
        "Technical summary:",
        event.reason or "—",
        "",
        "Automated production scanner notification. Research aid only — not financial advice.",
    ]
    return "\n".join(lines)


def _attempt_email(
    store: AIScannerEventStore,
    event: OpportunityEvent,
    email_sender: EmailSender,
) -> bool:
    subject = f"AI Opportunity Scanner — NEW Opportunity — {event.ticker}"
    body = _build_email_body(event)
    try:
        ok = email_sender(subject, body)
    except Exception as exc:
        store.update_email_failed(event.event_id, str(exc))
        return False
    if ok:
        store.update_email_sent(event.event_id)
        return True
    store.update_email_failed(event.event_id, "notifier returned failure")
    return False


def process_qualifying_opportunities(
    scan: dict[str, Any],
    *,
    scan_source: str,
    store: AIScannerEventStore | None = None,
    email_sender: EmailSender | None = None,
    trading_date: str | None = None,
) -> PipelineResult:
    """
    Consume production scan output after mark_existing_positions.
    Qualifying set = scan['strong_buys'] (STRONG BUY classification only).
    """
    result = PipelineResult()
    result.trading_date = trading_date or ist_trading_date().isoformat()
    result.scan_run_id = uuid.uuid4().hex
    store = store or get_event_store()
    send = email_sender or _default_email_sender

    strong_buys = scan.get("strong_buys") or []
    result.qualifying_count = len(strong_buys)
    qualifying_norms = {normalize_ticker(getattr(r, "ticker", "")) for r in strong_buys}

    for r in strong_buys:
        ticker = str(getattr(r, "ticker", "") or "").strip()
        if not ticker:
            continue
        existing = store.get_by_trading_date_ticker(result.trading_date, ticker)

        if existing is None:
            event, created = store.insert_event(
                trading_date=result.trading_date,
                ticker=ticker,
                scan_source=scan_source,
                scan_run_id=result.scan_run_id,
                score=float(getattr(r, "composite_score", 0) or 0),
                signal=str(getattr(r, "action", "") or "STRONG BUY"),
                groups_met=int(getattr(r, "groups_fired", 0) or 0),
                entry=float(getattr(r, "suggested_entry", 0) or 0),
                sl=float(getattr(r, "suggested_stop", 0) or 0),
                target=float(getattr(r, "suggested_target", 0) or 0),
                qty=int(getattr(r, "suggested_qty", 0) or 0),
                risk=float(getattr(r, "max_risk_inr", 0) or 0),
                sector=str(getattr(r, "sector", "") or "") or None,
                reason=_reason_from_result(r) or None,
            )
            if not created or event is None:
                existing = store.get_by_trading_date_ticker(result.trading_date, ticker)
            else:
                result.events_created += 1
                result.emails_attempted += 1
                if _attempt_email(store, event, send):
                    result.emails_sent += 1
                else:
                    result.emails_failed += 1
                continue

        if existing is None:
            continue

        norm = normalize_ticker(ticker)
        if existing.email_status == store.EMAIL_SENT:
            continue

        if existing.email_status == store.EMAIL_FAILED and norm in qualifying_norms:
            result.emails_attempted += 1
            refreshed = store.get_by_trading_date_ticker(result.trading_date, ticker)
            if refreshed and _attempt_email(store, refreshed, send):
                result.emails_sent += 1
            else:
                result.emails_failed += 1
        elif existing.email_status == store.EMAIL_PENDING:
            result.emails_attempted += 1
            if _attempt_email(store, existing, send):
                result.emails_sent += 1
            else:
                result.emails_failed += 1

    return result
