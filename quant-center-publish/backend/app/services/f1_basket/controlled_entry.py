"""Smallcase-style controlled basket entry — selective deploy and explicit adoption."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.f1_basket.constants import (
    BASKET_SIZE,
    BROKER_ZERODHA,
    BUY_COST_PCT,
    FILL_ADOPTED,
    FILL_COMPLETE,
    FILL_FAILED,
    FILL_PENDING,
    FILL_REJECTED,
    FILL_CANCELLED,
    FILL_SUBMITTED,
    NON_RESUBMIT_STATUSES,
    STATUS_DEPLOYING,
    STATUS_READY,
    TERMINAL_FAILURE_STATUSES,
)
from app.services.f1_basket.deployment import (
    BasketDeployResult,
    ConstituentSubmitResult,
    DeployGateResult,
    _broker_connected,
    _default_submit,
    _response_to_dict,
)
from app.services.f1_basket.holdings import load_broker_holdings
from app.services.f1_basket.store import F1BasketStore, get_basket_store


def _bare(ticker: str) -> str:
    return str(ticker).strip().upper().replace(".NS", "").replace(".BO", "")


def _buy_qty(constituent: dict) -> int:
    return int(float(constituent.get("recommended_buy_qty") or constituent.get("quantity") or 0))


def attributed_qty(constituent: dict) -> float:
    """Basket-attributed quantity for valuation/exit (explicit only)."""
    explicit = float(constituent.get("basket_attributed_qty") or 0)
    if explicit > 0:
        return explicit
    if int(constituent.get("slot_resolved") or 0) == 1:
        adopted = float(constituent.get("adopted_existing_qty") or 0)
        bought = float(constituent.get("basket_bought_qty") or constituent.get("filled_qty") or 0)
        return adopted + bought
    return 0.0


@dataclass
class SlotSelection:
    ticker: str
    execute: bool = False
    adopt_existing_qty: int = 0


@dataclass
class DeploySelectedResult(BasketDeployResult):
    resolved: int = 0


def check_controlled_deploy_gate(
    basket: dict,
    *,
    current_f1_timestamp: str,
    stale: bool,
    selections: list[SlotSelection] | None = None,
) -> DeployGateResult:
    status = basket.get("status")
    if status not in (STATUS_READY, STATUS_DEPLOYING):
        return DeployGateResult(False, f"Basket status is {status}, not deployable.")

    constituents = basket.get("constituents") or []
    if len(constituents) != BASKET_SIZE:
        return DeployGateResult(
            False,
            f"Basket has {len(constituents)} constituents; exactly {BASKET_SIZE} required.",
        )

    if status == STATUS_READY:
        if stale:
            return DeployGateResult(False, "Preview is stale. Rebuild preview from latest F1 output.")
        if basket.get("deployment_started_at"):
            return DeployGateResult(False, "Deployment already started for this basket.")

    ready, msg = _broker_connected()
    if not ready:
        return DeployGateResult(False, msg)

    if selections is not None:
        executing = [s for s in selections if s.execute]
        if not executing:
            return DeployGateResult(False, "Select at least one slot to deploy.")
        cons_by_ticker = {c["ticker"]: c for c in constituents}
        holdings = load_broker_holdings()
        resolved = sum(1 for c in constituents if int(c.get("slot_resolved") or 0) == 1)
        for sel in executing:
            c = cons_by_ticker.get(sel.ticker)
            if not c:
                return DeployGateResult(False, f"{sel.ticker} is not in the F1 recommended basket.")
            if int(c.get("slot_resolved") or 0) == 1:
                return DeployGateResult(False, f"{sel.ticker} slot already resolved.")
            adopt = int(sel.adopt_existing_qty)
            if adopt < 0:
                return DeployGateResult(False, f"Adopt quantity must be >= 0 for {sel.ticker}.")
            broker_qty = int(float(c.get("current_broker_qty") or 0))
            holding = holdings.get(_bare(sel.ticker))
            max_broker = int(holding.quantity) if holding else broker_qty
            if adopt > max_broker:
                return DeployGateResult(
                    False,
                    f"Cannot adopt {adopt} {sel.ticker}; broker holds {max_broker}.",
                )
            buy_q = _buy_qty(c)
            if buy_q <= 0 and adopt <= 0:
                return DeployGateResult(
                    False,
                    f"{sel.ticker}: no recommended BUY and no shares to adopt.",
                )
        if resolved + len(executing) > BASKET_SIZE:
            return DeployGateResult(False, f"Maximum {BASKET_SIZE} basket-attributed stocks allowed.")

    return DeployGateResult(True, "")


def _build_buy_signal(constituent: dict, basket_id: str, qty: int) -> dict:
    return {
        "Ticker": constituent["ticker"],
        "Qty": qty,
        "order_type": "MARKET",
        "product": "CNC",
        "broker": BROKER_ZERODHA,
        "side": "BUY",
        "Close": float(constituent.get("reference_price") or 0),
        "remarks": f"F1_BASKET:{basket_id}:{constituent['ticker']}",
    }


def _is_submittable(constituent: dict) -> bool:
    if int(constituent.get("slot_resolved") or 0) == 1:
        return False
    status = str(constituent.get("fill_status") or FILL_PENDING).upper()
    broker_order_id = str(constituent.get("broker_order_id") or "").strip()
    if broker_order_id:
        return False
    if status in NON_RESUBMIT_STATUSES:
        return False
    return status in (FILL_PENDING, FILL_FAILED, FILL_REJECTED, FILL_CANCELLED, "")


def _adopt_price(ticker: str, constituent: dict) -> float:
    holdings = load_broker_holdings()
    holding = holdings.get(_bare(ticker))
    if holding and holding.avg_price > 0:
        return holding.avg_price
    return float(constituent.get("reference_price") or 0)


def _resolve_adoption_only(
    db: F1BasketStore,
    basket_id: str,
    constituent: dict,
    adopt_qty: int,
    buy_cost_pct: float,
) -> None:
    price = _adopt_price(constituent["ticker"], constituent)
    gross = adopt_qty * price
    buy_cost = 0.0
    db.update_constituent_attribution(
        basket_id,
        constituent["ticker"],
        adopted_existing_qty=adopt_qty,
        basket_bought_qty=0,
        basket_attributed_qty=adopt_qty,
        slot_resolved=1,
        attribution_price=price,
        fill_status=FILL_ADOPTED,
        gross_buy_value=gross,
    )
    db.update_constituent_order(
        basket_id,
        constituent["ticker"],
        fill_status=FILL_ADOPTED,
        filled_qty=0,
        average_fill_price=price,
    )
    with db._conn() as conn:
        conn.execute(
            """UPDATE f1_basket_constituents SET
               estimated_buy_cost = ?, estimated_total_entry_cost = ?,
               current_price = ?, current_market_value = ?
               WHERE basket_id = ? AND ticker = ?""",
            (buy_cost, gross + buy_cost, price, gross, basket_id, constituent["ticker"]),
        )


def finalize_slot_on_buy_fill(
    db: F1BasketStore,
    basket_id: str,
    constituent: dict,
    *,
    filled_qty: int,
    avg_price: float,
    buy_cost_pct: float = BUY_COST_PCT,
) -> None:
    """Persist basket attribution after a BUY fill (or partial)."""
    adopted = float(constituent.get("adopted_existing_qty") or 0)
    adopt_price = float(constituent.get("attribution_price") or 0) or _adopt_price(
        constituent["ticker"], constituent
    )
    bought = float(filled_qty)
    attributed = adopted + bought
    if adopted > 0 and bought > 0:
        attr_price = (adopted * adopt_price + bought * avg_price) / attributed
    elif adopted > 0:
        attr_price = adopt_price
    else:
        attr_price = avg_price
    gross = attributed * attr_price
    buy_cost = bought * avg_price * buy_cost_pct
    db.update_constituent_attribution(
        basket_id,
        constituent["ticker"],
        basket_bought_qty=bought,
        basket_attributed_qty=attributed,
        slot_resolved=1 if bought >= _buy_qty(constituent) else 0,
        attribution_price=attr_price,
        gross_buy_value=gross,
        fill_status=FILL_COMPLETE if bought >= _buy_qty(constituent) else constituent.get("fill_status"),
    )
    with db._conn() as conn:
        conn.execute(
            """UPDATE f1_basket_constituents SET
               estimated_buy_cost = ?, estimated_total_entry_cost = ?,
               current_price = ?, current_market_value = ?
               WHERE basket_id = ? AND ticker = ?""",
            (buy_cost, gross + buy_cost, attr_price, gross, basket_id, constituent["ticker"]),
        )


def deploy_selected_slots(
    basket_id: str,
    selections: list[SlotSelection],
    *,
    store: F1BasketStore | None = None,
    submit_fn=None,
    current_f1_timestamp: str = "",
    preview_stale: bool = False,
) -> DeploySelectedResult:
    """Deploy only user-selected recommended slots (with optional adoption)."""
    db = store or get_basket_store()
    basket = db.get_basket(basket_id)
    if not basket:
        return DeploySelectedResult(False, basket_id, "", message="Basket not found.")

    stale = preview_stale
    if not stale and current_f1_timestamp:
        stale = (
            bool(basket.get("f1_snapshot_timestamp"))
            and basket["f1_snapshot_timestamp"] != current_f1_timestamp
        )

    gate = check_controlled_deploy_gate(
        basket, current_f1_timestamp=current_f1_timestamp, stale=stale, selections=selections
    )
    if not gate.allowed:
        return DeploySelectedResult(
            False, basket_id, str(basket.get("status") or ""), message=gate.reason
        )

    submit = submit_fn or _default_submit
    if basket.get("status") == STATUS_READY:
        db.mark_deploying(basket_id)

    basket = db.get_basket(basket_id)
    assert basket
    cons_by_ticker = {c["ticker"]: c for c in basket.get("constituents") or []}
    buy_cost_pct = float(basket.get("buy_cost_pct") or BUY_COST_PCT)

    results: list[ConstituentSubmitResult] = []
    submitted = skipped = failed = resolved = 0

    for sel in selections:
        if not sel.execute:
            skipped += 1
            continue
        c = cons_by_ticker.get(sel.ticker)
        if not c or not _is_submittable(c):
            skipped += 1
            continue

        adopt = int(sel.adopt_existing_qty)
        buy_q = _buy_qty(c)
        adopt_px = _adopt_price(sel.ticker, c) if adopt > 0 else 0.0

        if adopt > 0:
            db.update_constituent_attribution(
                basket_id,
                sel.ticker,
                adopted_existing_qty=adopt,
                attribution_price=adopt_px,
            )

        if buy_q <= 0:
            _resolve_adoption_only(db, basket_id, c, adopt, buy_cost_pct)
            resolved += 1
            results.append(
                ConstituentSubmitResult(
                    ticker=sel.ticker,
                    success=True,
                    fill_status=FILL_ADOPTED,
                    message=f"adopted {adopt} shares (no BUY required)",
                )
            )
            continue

        signal = _build_buy_signal(c, basket_id, buy_q)
        try:
            resp = submit(signal)
        except Exception as exc:
            db.update_constituent_order(
                basket_id, sel.ticker, fill_status=FILL_FAILED, error_message=str(exc)
            )
            failed += 1
            results.append(
                ConstituentSubmitResult(
                    ticker=sel.ticker, success=False, fill_status=FILL_FAILED, message=str(exc)
                )
            )
            continue

        ok = bool(resp.get("success", False))
        broker_order_id = str(resp.get("broker_order_id") or "").strip()
        if ok and broker_order_id:
            db.update_constituent_order(
                basket_id,
                sel.ticker,
                broker_order_id=broker_order_id,
                fill_status=FILL_SUBMITTED,
            )
            submitted += 1
            results.append(
                ConstituentSubmitResult(
                    ticker=sel.ticker,
                    success=True,
                    broker_order_id=broker_order_id,
                    fill_status=FILL_SUBMITTED,
                    message=str(resp.get("message") or "submitted"),
                )
            )
        else:
            db.update_constituent_order(
                basket_id,
                sel.ticker,
                fill_status=FILL_FAILED,
                error_message=str(resp.get("message") or "submission failed"),
            )
            failed += 1
            results.append(
                ConstituentSubmitResult(
                    ticker=sel.ticker,
                    success=False,
                    fill_status=FILL_FAILED,
                    message=str(resp.get("message") or "submission failed"),
                )
            )

    refreshed = db.get_basket(basket_id)
    status = str(refreshed.get("status") if refreshed else STATUS_DEPLOYING)
    resolved_total = db.count_resolved_slots(basket_id) if refreshed else resolved
    msg_parts = [
        f"submitted={submitted}",
        f"resolved={resolved_total}",
        f"skipped={skipped}",
        f"failed={failed}",
    ]
    return DeploySelectedResult(
        success=failed == 0 and (submitted > 0 or resolved > 0),
        basket_id=basket_id,
        status=status,
        submitted=submitted,
        skipped=skipped,
        failed=failed,
        resolved=resolved_total,
        results=results,
        message=" · ".join(msg_parts),
    )


def default_all_slot_selections(basket: dict) -> list[SlotSelection]:
    """Legacy bulk deploy: all unresolved slots with recommended BUY, no adoption."""
    out: list[SlotSelection] = []
    for c in basket.get("constituents") or []:
        if int(c.get("slot_resolved") or 0) == 1:
            continue
        if _buy_qty(c) <= 0:
            continue
        out.append(SlotSelection(ticker=c["ticker"], execute=True, adopt_existing_qty=0))
    return out
