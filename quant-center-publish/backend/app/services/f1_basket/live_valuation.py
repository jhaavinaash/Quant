"""Live ACTIVE basket valuation and locked TP/SL trigger evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.f1_basket.constants import (
    HARD_STOP_PCT,
    PROFIT_TARGET_PCT,
    SELL_COST_PCT,
    STATUS_ACTIVE,
    STATUS_EXIT_PENDING,
)
from app.services.f1_basket.controlled_entry import attributed_qty
from app.services.f1_basket.live_prices import fetch_live_prices
from app.services.f1_basket.store import F1BasketStore, get_basket_store
from app.services.f1_basket.valuation import BasketValuation, value_basket


def _bare(t: str) -> str:
    return str(t).strip().upper().replace(".NS", "").replace(".BO", "")


@dataclass
class LiveValuationResult:
    basket_id: str
    status: str
    valuation: BasketValuation
    trigger: str
    message: str = ""


def value_active_basket(
    basket_id: str,
    *,
    store: F1BasketStore | None = None,
    price_fn=None,
) -> LiveValuationResult | None:
    """Value ACTIVE/EXIT_PENDING basket with live prices. Trigger uses gross MV (research)."""
    db = store or get_basket_store()
    basket = db.get_basket(basket_id)
    if not basket:
        return None
    if basket["status"] not in (STATUS_ACTIVE, STATUS_EXIT_PENDING):
        return None

    constituents = basket.get("constituents") or []
    tickers = [c["ticker"] for c in constituents]
    prices = (price_fn or fetch_live_prices)(tickers)

    cons_for_val = []
    for c in constituents:
        bare = _bare(c["ticker"])
        price = prices.get(bare) or float(c.get("current_price") or c.get("average_fill_price") or c["reference_price"])
        qty = attributed_qty(c) or float(c.get("filled_qty") or c.get("quantity") or 0)
        cons_for_val.append(
            {
                "ticker": c["ticker"],
                "quantity": qty,
                "gross_buy_value": float(c.get("gross_buy_value") or 0),
                "current_price": price,
            }
        )

    val = value_basket(
        basket_start_value=float(basket["basket_start_value"]),
        target_value=float(basket["target_value"]),
        stop_value=float(basket["stop_value"]),
        profit_target_pct=float(basket.get("profit_target_pct") or PROFIT_TARGET_PCT),
        hard_stop_pct=float(basket.get("hard_stop_pct") or HARD_STOP_PCT),
        sell_cost_pct=float(basket.get("sell_cost_pct") or SELL_COST_PCT),
        constituents=cons_for_val,
    )

    db.update_valuation_snapshot(
        basket_id,
        val,
        [
            {
                "ticker": cv.ticker,
                "current_price": cv.current_price,
                "current_market_value": cv.current_market_value,
                "constituent_pnl": cv.constituent_pnl,
                "constituent_return_pct": cv.constituent_return_pct,
            }
            for cv in val.constituents
        ],
    )

    return LiveValuationResult(
        basket_id=basket_id,
        status=basket["status"],
        valuation=val,
        trigger=val.trigger,
        message=f"gross={val.gross_market_value:.2f} trigger={val.trigger}",
    )
