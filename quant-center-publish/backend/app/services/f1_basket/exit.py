"""Whole-basket SELL exit and sell-fill reconciliation."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.config import settings
from app.services.f1_basket.constants import (
    BASKET_ENGINE,
    BASKET_SIZE,
    BROKER_ZERODHA,
    BUY_COST_PCT,
    EXIT_REASON_MANUAL,
    EXIT_REASON_STOP,
    EXIT_REASON_TARGET,
    SELL_CANCELLED,
    SELL_COMPLETE,
    SELL_FAILED,
    SELL_NON_RESUBMIT,
    SELL_PARTIAL,
    SELL_PENDING,
    SELL_REJECTED,
    SELL_SUBMITTED,
    SELL_TERMINAL_FAILURE,
    STATUS_ACTIVE,
    STATUS_CLOSED,
    STATUS_EXIT_PENDING,
    STATUS_EXITING,
)
from app.services.f1_basket.controlled_entry import attributed_qty
from app.services.f1_basket.store import F1BasketStore, get_basket_store


def _ensure_quant_path() -> None:
    root = settings.QUANT_BASE_DIR
    if root not in sys.path:
        sys.path.insert(0, root)


def _response_to_dict(resp: Any) -> dict:
    if resp is None:
        return {"success": False, "message": "no response"}
    if hasattr(resp, "to_dict"):
        try:
            return resp.to_dict()
        except Exception:
            pass
    if hasattr(resp, "__dict__"):
        return dict(resp.__dict__)
    if isinstance(resp, dict):
        return resp
    return {"success": False, "message": "unknown response"}


def _default_submit_sell(signal: dict) -> dict:
    _ensure_quant_path()
    from Signals.signal_translator import translate
    from execution.execution_service import ExecutionService

    req = translate(signal, engine=BASKET_ENGINE)
    return _response_to_dict(ExecutionService().submit(req))


def _map_sell_status(raw: str) -> str:
    s = str(raw or "").upper()
    if s in ("COMPLETE", "FILLED"):
        return SELL_COMPLETE
    if s == "PARTIAL":
        return SELL_PARTIAL
    if s == "REJECTED":
        return SELL_REJECTED
    if s in ("CANCELLED", "CANCELED"):
        return SELL_CANCELLED
    if s in ("FAILED", "SYNC_FAILED"):
        return SELL_FAILED
    return SELL_SUBMITTED


@dataclass
class ExitSubmitResult:
    basket_id: str
    status: str
    submitted: int = 0
    skipped: int = 0
    failed: int = 0
    message: str = ""


@dataclass
class ExitSyncResult:
    basket_id: str
    status: str
    complete: int = 0
    partial: int = 0
    failed: int = 0
    closed: bool = False
    message: str = ""
    errors: list[str] = field(default_factory=list)


def mark_exit_trigger(
    basket_id: str,
    *,
    trigger: str,
    reason: str,
    trigger_value: float,
    store: F1BasketStore | None = None,
) -> bool:
    """ACTIVE → EXIT_PENDING idempotently (only once)."""
    db = store or get_basket_store()
    return db.mark_exit_pending(basket_id, trigger=trigger, reason=reason, trigger_value=trigger_value)


def _build_sell_signal(constituent: dict, basket_id: str) -> dict:
    qty = int(attributed_qty(constituent) or float(constituent.get("filled_qty") or constituent.get("quantity") or 0))
    if qty <= 0:
        qty = int(float(constituent.get("filled_qty") or constituent.get("quantity") or 0))
    return {
        "Ticker": constituent["ticker"],
        "Qty": qty,
        "order_type": "MARKET",
        "product": "CNC",
        "broker": BROKER_ZERODHA,
        "side": "SELL",
        "remarks": f"F1_BASKET_EXIT:{basket_id}:{constituent['ticker']}",
    }


def _sell_submittable(c: dict) -> bool:
    if str(c.get("sell_broker_order_id") or "").strip():
        return False
    status = str(c.get("sell_status") or SELL_PENDING).upper()
    if status in SELL_NON_RESUBMIT:
        return False
    return status in (SELL_PENDING, SELL_FAILED, SELL_REJECTED, SELL_CANCELLED, "")


def submit_basket_exits(
    basket_id: str,
    *,
    store: F1BasketStore | None = None,
    submit_fn: Callable[[dict], dict] | None = None,
    retry_failed_only: bool = False,
) -> ExitSubmitResult:
    db = store or get_basket_store()
    basket = db.get_basket(basket_id)
    if not basket:
        return ExitSubmitResult(basket_id, "", message="Basket not found")

    status = str(basket.get("status") or "")
    if status not in (STATUS_EXIT_PENDING, STATUS_EXITING):
        return ExitSubmitResult(basket_id, status, message=f"Status {status} not exitable")

    if status == STATUS_EXIT_PENDING:
        db.mark_exiting(basket_id)
        basket = db.get_basket(basket_id)
        assert basket
        status = STATUS_EXITING

    submit = submit_fn or _default_submit_sell
    submitted = skipped = failed = 0

    for c in basket.get("constituents") or []:
        ticker = str(c["ticker"])
        if retry_failed_only:
            st = str(c.get("sell_status") or "").upper()
            if st not in SELL_TERMINAL_FAILURE:
                skipped += 1
                continue
            db.clear_constituent_sell_for_retry(basket_id, ticker)
        elif not _sell_submittable(c):
            skipped += 1
            continue

        try:
            resp = submit(_build_sell_signal(c, basket_id))
        except Exception as exc:
            db.update_constituent_sell(basket_id, ticker, sell_status=SELL_FAILED, error_message=str(exc))
            failed += 1
            continue

        if bool(resp.get("success")) and str(resp.get("broker_order_id") or "").strip():
            db.update_constituent_sell(
                basket_id,
                ticker,
                sell_broker_order_id=str(resp["broker_order_id"]),
                sell_status=SELL_SUBMITTED,
            )
            submitted += 1
        else:
            db.update_constituent_sell(
                basket_id,
                ticker,
                sell_status=SELL_FAILED,
                error_message=str(resp.get("message") or "sell failed"),
            )
            failed += 1

    refreshed = db.get_basket(basket_id)
    st = str(refreshed.get("status") if refreshed else STATUS_EXITING)
    return ExitSubmitResult(
        basket_id=basket_id,
        status=st,
        submitted=submitted,
        skipped=skipped,
        failed=failed,
        message=f"submitted={submitted} skipped={skipped} failed={failed}",
    )


def sync_basket_exits(
    basket_id: str,
    *,
    store: F1BasketStore | None = None,
    fetch_fn: Callable | None = None,
) -> ExitSyncResult:
    db = store or get_basket_store()
    basket = db.get_basket(basket_id)
    if not basket or basket.get("status") != STATUS_EXITING:
        return ExitSyncResult(basket_id, str(basket.get("status") if basket else ""), message="Not EXITING")

    if fetch_fn is None:
        def fetch_fn(broker: str, oid: str):
            _ensure_quant_path()
            from execution.broker_order_fetcher import BrokerFetcherFactory
            return BrokerFetcherFactory.get(broker).fetch(oid)

    complete = partial = failed = 0
    errors: list[str] = []

    for c in basket.get("constituents") or []:
        oid = str(c.get("sell_broker_order_id") or "").strip()
        if not oid:
            continue
        if str(c.get("sell_status") or "").upper() == SELL_COMPLETE:
            complete += 1
            continue
        try:
            rec = fetch_fn(str(c.get("broker") or BROKER_ZERODHA), oid)
        except Exception as exc:
            errors.append(f"{c['ticker']}: {exc}")
            continue

        mapped = _map_sell_status(rec.status)
        fq = int(rec.fill_qty or 0)
        fp = float(rec.fill_price or 0)
        expected = int(attributed_qty(c) or float(c.get("filled_qty") or c.get("quantity") or 0))

        if mapped == SELL_COMPLETE and fq >= expected:
            complete += 1
            db.update_constituent_sell(
                basket_id, c["ticker"],
                sell_status=SELL_COMPLETE, sell_filled_qty=fq, average_sell_fill_price=fp,
            )
        elif mapped == SELL_PARTIAL:
            partial += 1
            db.update_constituent_sell(
                basket_id, c["ticker"],
                sell_status=SELL_PARTIAL, sell_filled_qty=fq, average_sell_fill_price=fp,
            )
        elif mapped in SELL_TERMINAL_FAILURE:
            failed += 1
            db.update_constituent_sell(
                basket_id, c["ticker"],
                sell_status=mapped, sell_filled_qty=fq, average_sell_fill_price=fp,
                error_message=str(rec.error or rec.raw_status or mapped),
            )
        else:
            db.update_constituent_sell(
                basket_id, c["ticker"],
                sell_status=SELL_SUBMITTED, sell_filled_qty=fq if fq else None,
                average_sell_fill_price=fp if fp else None,
            )

    refreshed = db.get_basket(basket_id)
    assert refreshed
    all_complete = all(
        str(c.get("sell_status") or "").upper() == SELL_COMPLETE
        and int(float(c.get("sell_filled_qty") or 0)) >= int(
            attributed_qty(c) or float(c.get("filled_qty") or c.get("quantity") or 0)
        )
        for c in refreshed.get("constituents") or []
        if int(attributed_qty(c) or float(c.get("basket_attributed_qty") or 0) or float(c.get("filled_qty") or 0)) > 0
    ) and len(refreshed.get("constituents") or []) == BASKET_SIZE

    closed = False
    if all_complete:
        sell_value = 0.0
        buy_cost = 0.0
        for c in refreshed["constituents"]:
            fq = float(c.get("sell_filled_qty") or 0)
            fp = float(c.get("average_sell_fill_price") or 0)
            sell_value += fq * fp
            buy_cost += float(c.get("estimated_buy_cost") or 0)
        sell_cost = sell_value * float(refreshed.get("sell_cost_pct") or BUY_COST_PCT)
        start = float(refreshed["basket_start_value"])
        gross_pnl = sell_value - start
        net_pnl = sell_value - sell_cost - start - buy_cost
        ret_pct = (net_pnl / start * 100) if start > 0 else 0.0
        db.close_basket(
            basket_id,
            actual_sell_value=sell_value,
            actual_sell_cost=sell_cost,
            actual_buy_cost=buy_cost,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            return_pct=ret_pct,
        )
        closed = True

    st = STATUS_CLOSED if closed else STATUS_EXITING
    msg = "Basket CLOSED." if closed else f"EXITING complete={complete} partial={partial} failed={failed}"
    return ExitSyncResult(
        basket_id=basket_id, status=st, complete=complete, partial=partial,
        failed=failed, closed=closed, message=msg, errors=errors,
    )


def exit_progress(constituents: list[dict]) -> dict:
    counts = {"total": len(constituents), "complete": 0, "submitted": 0, "pending": 0, "partial": 0, "failed": 0}
    for c in constituents:
        s = str(c.get("sell_status") or SELL_PENDING).upper()
        if s == SELL_COMPLETE:
            counts["complete"] += 1
        elif s == SELL_PARTIAL:
            counts["partial"] += 1
        elif s in SELL_TERMINAL_FAILURE:
            counts["failed"] += 1
        elif s == SELL_SUBMITTED:
            counts["submitted"] += 1
        else:
            counts["pending"] += 1
    return counts


def initiate_manual_exit(
    basket_id: str,
    *,
    store: F1BasketStore | None = None,
    submit_fn: Callable[[dict], dict] | None = None,
) -> ExitSubmitResult:
    db = store or get_basket_store()
    basket = db.get_basket(basket_id)
    if not basket or basket.get("status") != STATUS_ACTIVE:
        return ExitSubmitResult(basket_id, str(basket.get("status") if basket else ""), message="ACTIVE required")
    gv = float(basket.get("current_value") or basket.get("basket_start_value") or 0)
    if not db.mark_exit_pending(basket_id, trigger="MANUAL", reason=EXIT_REASON_MANUAL, trigger_value=gv):
        return ExitSubmitResult(basket_id, basket["status"], message="Could not mark exit pending")
    return submit_basket_exits(basket_id, store=db, submit_fn=submit_fn)
