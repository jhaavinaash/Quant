"""F1 Basket BUY fill reconciliation — broker fetch only, no trades_log writes."""



from __future__ import annotations



import sys

from dataclasses import dataclass, field

from typing import Callable, Optional



from app.core.config import settings

from app.services.f1_basket.constants import (

    BASKET_SIZE,

    BROKER_ZERODHA,

    BUY_COST_PCT,

    FILL_ADOPTED,

    FILL_CANCELLED,

    FILL_COMPLETE,

    FILL_PARTIAL,

    FILL_PENDING,

    FILL_REJECTED,

    FILL_SUBMITTED,

    HARD_STOP_PCT,

    PROFIT_TARGET_PCT,

    STATUS_ACTIVE,

    STATUS_DEPLOYING,

    TERMINAL_FAILURE_STATUSES,

)

from app.services.f1_basket.controlled_entry import finalize_slot_on_buy_fill
from app.services.f1_basket.store import F1BasketStore, get_basket_store





def _ensure_quant_path() -> None:

    root = settings.QUANT_BASE_DIR

    if root not in sys.path:

        sys.path.insert(0, root)





def _map_broker_status(raw: str) -> str:

    s = str(raw or "").upper()

    if s in ("COMPLETE", "FILLED"):

        return FILL_COMPLETE

    if s == "PARTIAL":

        return FILL_PARTIAL

    if s in ("REJECTED",):

        return FILL_REJECTED

    if s in ("CANCELLED", "CANCELED"):

        return FILL_CANCELLED

    if s in ("SYNC_FAILED", "FAILED"):

        return FILL_REJECTED

    if s in ("PENDING", "OPEN", "SUBMITTED", "PUT ORDER REQ RECEIVED", "TRIGGER PENDING"):

        return FILL_SUBMITTED

    return FILL_SUBMITTED





@dataclass

class BasketSyncResult:

    basket_id: str

    status: str

    synced: int = 0

    complete: int = 0

    partial: int = 0

    pending: int = 0

    failed: int = 0

    activated: bool = False

    message: str = ""

    errors: list[str] = field(default_factory=list)





def _default_fetch(broker: str, broker_order_id: str):

    _ensure_quant_path()

    from execution.broker_order_fetcher import BrokerFetcherFactory



    return BrokerFetcherFactory.get(broker).fetch(broker_order_id)





def _try_activate_basket(db: F1BasketStore, basket_id: str) -> bool:

    basket = db.get_basket(basket_id)

    if not basket or basket.get("status") != STATUS_DEPLOYING:

        return False



    constituents = basket.get("constituents") or []

    if len(constituents) != BASKET_SIZE:

        return False



    resolved = [c for c in constituents if int(c.get("slot_resolved") or 0) == 1]

    if len(resolved) != BASKET_SIZE:

        return False



    buy_cost_pct = float(basket.get("buy_cost_pct") or BUY_COST_PCT)

    profit_target = float(basket.get("profit_target_pct") or PROFIT_TARGET_PCT)

    hard_stop = float(basket.get("hard_stop_pct") or HARD_STOP_PCT)

    initial_capital = float(basket.get("initial_capital") or 0)



    total_gross = 0.0

    total_buy_cost = 0.0

    updates: list[dict] = []



    for c in resolved:

        attributed_qty = float(c.get("basket_attributed_qty") or 0)

        attr_price = float(

            c.get("attribution_price")

            or c.get("average_fill_price")

            or c.get("reference_price")

            or 0

        )

        gross = attributed_qty * attr_price

        bought = float(c.get("basket_bought_qty") or c.get("filled_qty") or 0)

        avg_buy = float(c.get("average_fill_price") or attr_price)

        buy_cost = bought * avg_buy * buy_cost_pct

        total_gross += gross

        total_buy_cost += buy_cost

        updates.append(

            {

                "ticker": c["ticker"],

                "gross_buy_value": gross,

                "estimated_buy_cost": buy_cost,

                "estimated_total_entry_cost": gross + buy_cost,

                "current_price": attr_price,

                "current_market_value": gross,

            }

        )



    cash_remaining = initial_capital - total_gross - total_buy_cost

    target_value = total_gross * (1.0 + profit_target)

    stop_value = total_gross * (1.0 - hard_stop)



    db.activate_basket(

        basket_id,

        allocated_capital=total_gross,

        basket_start_value=total_gross,

        cash_remaining=cash_remaining,

        target_value=target_value,

        stop_value=stop_value,
        actual_buy_cost=total_buy_cost,
        constituent_updates=updates,

    )

    return True





def sync_basket_fills(

    basket_id: str,

    *,

    store: F1BasketStore | None = None,

    fetch_fn: Callable | None = None,

) -> BasketSyncResult:

    """Sync constituent fills from broker. Does not write trades_log.csv."""

    db = store or get_basket_store()

    basket = db.get_basket(basket_id)

    if not basket:

        return BasketSyncResult(basket_id, "", message="Basket not found.")



    status = str(basket.get("status") or "")

    if status not in (STATUS_DEPLOYING, STATUS_ACTIVE):

        return BasketSyncResult(basket_id, status, message=f"Basket status {status} — nothing to sync.")



    fetch = fetch_fn or _default_fetch

    synced = complete = partial = pending = failed = 0

    errors: list[str] = []



    for c in basket.get("constituents") or []:

        if int(c.get("slot_resolved") or 0) == 1:

            if str(c.get("fill_status") or "").upper() in (FILL_COMPLETE, FILL_ADOPTED):

                complete += 1

            continue



        broker_order_id = str(c.get("broker_order_id") or "").strip()

        if not broker_order_id:

            continue



        current = str(c.get("fill_status") or "").upper()

        if current == FILL_COMPLETE:

            complete += 1

            continue



        try:

            record = fetch(str(c.get("broker") or BROKER_ZERODHA), broker_order_id)

        except Exception as exc:

            errors.append(f"{c['ticker']}: {exc}")

            continue



        synced += 1

        mapped = _map_broker_status(record.status)

        filled_qty = int(record.fill_qty or 0)

        avg_price = float(record.fill_price or 0)



        if mapped == FILL_COMPLETE:

            complete += 1

            db.update_constituent_order(

                basket_id,

                c["ticker"],

                fill_status=FILL_COMPLETE,

                filled_qty=filled_qty,

                average_fill_price=avg_price,

            )

            refreshed_c = db.get_basket(basket_id)

            row = next(

                (x for x in (refreshed_c or {}).get("constituents") or [] if x["ticker"] == c["ticker"]),

                c,

            )

            finalize_slot_on_buy_fill(

                db, basket_id, row, filled_qty=filled_qty, avg_price=avg_price,

                buy_cost_pct=float(basket.get("buy_cost_pct") or BUY_COST_PCT),

            )

        elif mapped == FILL_PARTIAL:

            partial += 1

            db.update_constituent_order(

                basket_id,

                c["ticker"],

                fill_status=FILL_PARTIAL,

                filled_qty=filled_qty,

                average_fill_price=avg_price,

            )

        elif mapped in TERMINAL_FAILURE_STATUSES:

            failed += 1

            db.update_constituent_order(

                basket_id,

                c["ticker"],

                fill_status=mapped,

                filled_qty=filled_qty,

                average_fill_price=avg_price,

                error_message=str(record.error or record.raw_status or mapped),

            )

        else:

            pending += 1

            db.update_constituent_order(

                basket_id,

                c["ticker"],

                fill_status=FILL_SUBMITTED,

                filled_qty=filled_qty if filled_qty > 0 else None,

                average_fill_price=avg_price if avg_price > 0 else None,

            )



    activated = _try_activate_basket(db, basket_id)

    refreshed = db.get_basket(basket_id)

    new_status = str(refreshed.get("status") if refreshed else status)



    if activated:

        msg = "All 12 basket slots resolved — basket ACTIVE."

    elif failed > 0:

        msg = "DEPLOYMENT INCOMPLETE — one or more constituents rejected/failed."

    elif partial > 0:

        msg = f"DEPLOYING — {partial} partial fill(s)."

    elif pending > 0:

        msg = f"DEPLOYING — {pending} order(s) still pending at broker."

    else:

        msg = f"synced={synced}"



    return BasketSyncResult(

        basket_id=basket_id,

        status=new_status,

        synced=synced,

        complete=complete,

        partial=partial,

        pending=pending,

        failed=failed,

        activated=activated,

        message=msg,

        errors=errors,

    )





def deployment_progress(constituents: list[dict]) -> dict:

    counts = {

        "total": len(constituents),

        "complete": 0,

        "resolved": 0,

        "submitted": 0,

        "pending": 0,

        "partial": 0,

        "failed": 0,

    }

    for c in constituents:

        if int(c.get("slot_resolved") or 0) == 1:

            counts["resolved"] += 1

        s = str(c.get("fill_status") or FILL_PENDING).upper()

        if s in (FILL_COMPLETE, FILL_ADOPTED):

            counts["complete"] += 1

        elif s == FILL_PARTIAL:

            counts["partial"] += 1

        elif s in TERMINAL_FAILURE_STATUSES:

            counts["failed"] += 1

        elif s == FILL_SUBMITTED:

            counts["submitted"] += 1

        elif s == FILL_PENDING:

            counts["pending"] += 1

        else:

            counts["pending"] += 1

    return counts


