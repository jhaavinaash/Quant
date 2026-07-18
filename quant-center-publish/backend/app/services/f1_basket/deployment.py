"""F1 Basket broker deployment — uses production ExecutionService path."""



from __future__ import annotations



import sys

from dataclasses import dataclass, field

from typing import Any, Callable, Optional



from app.core.config import settings

from app.services.f1_basket.constants import (

    BASKET_ENGINE,

    BASKET_SIZE,

    BROKER_ZERODHA,

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

from app.services.f1_basket.store import F1BasketStore, get_basket_store





def _ensure_quant_path() -> None:

    root = settings.QUANT_BASE_DIR

    if root not in sys.path:

        sys.path.insert(0, root)





def _broker_connected() -> tuple[bool, str]:

    from app.services.execution_actions_service import _broker_ready



    return _broker_ready(BROKER_ZERODHA)





def _response_to_dict(resp: Any) -> dict:

    if resp is None:

        return {"success": False, "message": "no response from execution"}

    if hasattr(resp, "to_dict"):

        try:

            return resp.to_dict()

        except Exception:

            pass

    if hasattr(resp, "__dict__"):

        return dict(resp.__dict__)

    if isinstance(resp, dict):

        return resp

    return {"success": False, "message": f"unknown response type: {type(resp).__name__}"}





def _default_submit(signal: dict) -> dict:

    """Submit via production ExecutionService + signal_translator (no Kite in web layer)."""

    _ensure_quant_path()

    from Signals.signal_translator import translate

    from execution.execution_service import ExecutionService



    req = translate(signal, engine=BASKET_ENGINE)

    resp = ExecutionService().submit(req)

    return _response_to_dict(resp)





@dataclass

class DeployGateResult:

    allowed: bool

    reason: str = ""





@dataclass

class ConstituentSubmitResult:

    ticker: str

    success: bool

    broker_order_id: str = ""

    fill_status: str = FILL_PENDING

    message: str = ""





@dataclass

class BasketDeployResult:

    success: bool

    basket_id: str

    status: str

    submitted: int = 0

    skipped: int = 0

    failed: int = 0

    results: list[ConstituentSubmitResult] = field(default_factory=list)

    message: str = ""





def check_deploy_gate(

    basket: dict,

    *,

    current_f1_timestamp: str,

    stale: bool,

) -> DeployGateResult:

    if basket.get("status") not in (STATUS_READY, STATUS_DEPLOYING):

        return DeployGateResult(False, f"Basket status is {basket.get('status')}, not deployable.")



    constituents = basket.get("constituents") or []

    if len(constituents) != BASKET_SIZE:

        return DeployGateResult(

            False,

            f"Basket has {len(constituents)} constituents; exactly {BASKET_SIZE} required.",

        )



    if basket.get("status") == STATUS_READY:

        if stale:

            return DeployGateResult(False, "Preview is stale. Rebuild preview from latest F1 output.")



    ready, msg = _broker_connected()

    if not ready:

        return DeployGateResult(False, msg)



    if basket.get("status") == STATUS_READY and basket.get("deployment_started_at"):

        return DeployGateResult(False, "Deployment already started for this basket.")



    return DeployGateResult(True, "")





def _build_buy_signal(constituent: dict, basket_id: str) -> dict:

    qty = int(float(constituent.get("recommended_buy_qty") or constituent.get("quantity") or 0))

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





def deploy_basket_orders(

    basket_id: str,

    *,

    store: F1BasketStore | None = None,

    submit_fn: Callable[[dict], dict] | None = None,

    current_f1_timestamp: str = "",

    preview_stale: bool = False,

    retry_failed_only: bool = False,

) -> BasketDeployResult:

    """Submit BUY orders for basket constituents. Idempotent per constituent."""

    db = store or get_basket_store()

    basket = db.get_basket(basket_id)

    if not basket:

        return BasketDeployResult(False, basket_id, "", message="Basket not found.")



    stale = preview_stale

    if not stale and current_f1_timestamp:

        stale = (

            bool(basket.get("f1_snapshot_timestamp"))

            and basket["f1_snapshot_timestamp"] != current_f1_timestamp

        )



    if retry_failed_only:
        if basket.get("status") != STATUS_DEPLOYING:
            return BasketDeployResult(
                False,
                basket_id,
                str(basket.get("status") or ""),
                message="Retry is only available for DEPLOYING baskets.",
            )
        ready, msg = _broker_connected()
        if not ready:
            return BasketDeployResult(False, basket_id, STATUS_DEPLOYING, message=msg)
    else:

        gate = check_deploy_gate(basket, current_f1_timestamp=current_f1_timestamp, stale=stale)

        if not gate.allowed:

            return BasketDeployResult(

                False,

                basket_id,

                str(basket.get("status") or ""),

                message=gate.reason,

            )



    submit = submit_fn or _default_submit

    if basket.get("status") == STATUS_READY:

        db.mark_deploying(basket_id)



    basket = db.get_basket(basket_id)

    assert basket

    constituents = basket.get("constituents") or []



    results: list[ConstituentSubmitResult] = []

    submitted = skipped = failed = 0



    for c in constituents:

        ticker = str(c["ticker"])

        if retry_failed_only:

            status = str(c.get("fill_status") or "").upper()

            if status not in TERMINAL_FAILURE_STATUSES:

                skipped += 1

                continue

            db.clear_constituent_for_retry(basket_id, ticker)

        elif not _is_submittable(c):

            skipped += 1

            continue

        buy_q = int(float(c.get("recommended_buy_qty") or c.get("quantity") or 0))

        if buy_q <= 0:

            skipped += 1

            continue



        signal = _build_buy_signal(c, basket_id)

        try:

            resp = submit(signal)

        except Exception as exc:

            db.update_constituent_order(

                basket_id,

                ticker,

                fill_status=FILL_FAILED,

                error_message=str(exc),

            )

            failed += 1

            results.append(

                ConstituentSubmitResult(ticker=ticker, success=False, fill_status=FILL_FAILED, message=str(exc))

            )

            continue



        ok = bool(resp.get("success", False))

        broker_order_id = str(resp.get("broker_order_id") or "").strip()

        if ok and broker_order_id:

            db.update_constituent_order(

                basket_id,

                ticker,

                broker_order_id=broker_order_id,

                fill_status=FILL_SUBMITTED,

            )

            submitted += 1

            results.append(

                ConstituentSubmitResult(

                    ticker=ticker,

                    success=True,

                    broker_order_id=broker_order_id,

                    fill_status=FILL_SUBMITTED,

                    message=str(resp.get("message") or "submitted"),

                )

            )

        else:

            db.update_constituent_order(

                basket_id,

                ticker,

                fill_status=FILL_FAILED,

                error_message=str(resp.get("message") or "submission failed"),

            )

            failed += 1

            results.append(

                ConstituentSubmitResult(

                    ticker=ticker,

                    success=False,

                    fill_status=FILL_FAILED,

                    message=str(resp.get("message") or "submission failed"),

                )

            )



    refreshed = db.get_basket(basket_id)

    status = str(refreshed.get("status") if refreshed else STATUS_DEPLOYING)

    msg_parts = [f"submitted={submitted}", f"skipped={skipped}", f"failed={failed}"]

    if failed > 0:

        msg_parts.append("deployment incomplete")

    return BasketDeployResult(

        success=failed == 0 and submitted >= 0,

        basket_id=basket_id,

        status=status,

        submitted=submitted,

        skipped=skipped,

        failed=failed,

        results=results,

        message=" · ".join(msg_parts),

    )


