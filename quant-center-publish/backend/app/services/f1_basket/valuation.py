"""Basket NAV and trigger evaluation — mirrors basket_backtester valuation semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.f1_basket.constants import SELL_COST_PCT

TriggerResult = Literal["TARGET", "STOP", "NONE"]


@dataclass
class ConstituentValuation:
    ticker: str
    quantity: float
    current_price: float
    current_market_value: float
    gross_buy_value: float
    constituent_pnl: float
    constituent_return_pct: float


@dataclass
class BasketValuation:
    gross_market_value: float
    estimated_exit_cost: float
    net_liquidation_value: float
    basket_start_value: float
    gross_pnl: float
    net_pnl: float
    return_pct: float
    distance_to_target_pct: float
    distance_to_stop_pct: float
    trigger: TriggerResult
    target_value: float
    stop_value: float
    constituents: list[ConstituentValuation]


def evaluate_trigger(
    basket_gross_value: float,
    basket_start_value: float,
    profit_target_pct: float,
    hard_stop_pct: float,
) -> TriggerResult:
    """
    Research: _basket_value_at_close compared to target/stop thresholds.
    Uses gross market value (no exit cost in trigger check).
    """
    if basket_start_value <= 0:
        return "NONE"
    target = basket_start_value * (1.0 + profit_target_pct)
    stop = basket_start_value * (1.0 - hard_stop_pct)
    if basket_gross_value >= target:
        return "TARGET"
    if basket_gross_value <= stop:
        return "STOP"
    return "NONE"


def value_basket(
    *,
    basket_start_value: float,
    target_value: float,
    stop_value: float,
    profit_target_pct: float,
    hard_stop_pct: float,
    sell_cost_pct: float,
    constituents: list[dict],
) -> BasketValuation:
    """
    constituents: dicts with ticker, quantity, gross_buy_value, current_price
    """
    gross_total = 0.0
    exit_cost = 0.0
    net_total = 0.0
    cvals: list[ConstituentValuation] = []

    for c in constituents:
        qty = float(c["quantity"])
        price = float(c.get("current_price") or c.get("reference_price") or 0)
        gross_mv = qty * price
        gross_pos = float(c.get("gross_buy_value") or 0)
        sell_fee = gross_mv * sell_cost_pct
        net_pos = gross_mv * (1.0 - sell_cost_pct)
        pnl = gross_mv - gross_pos
        ret = (gross_mv / gross_pos - 1.0) * 100 if gross_pos > 0 else 0.0
        cvals.append(
            ConstituentValuation(
                ticker=str(c["ticker"]),
                quantity=qty,
                current_price=price,
                current_market_value=gross_mv,
                gross_buy_value=gross_pos,
                constituent_pnl=pnl,
                constituent_return_pct=ret,
            )
        )
        gross_total += gross_mv
        exit_cost += sell_fee
        net_total += net_pos

    trigger = evaluate_trigger(
        gross_total, basket_start_value, profit_target_pct, hard_stop_pct
    )
    gross_pnl = gross_total - basket_start_value
    net_pnl = net_total - basket_start_value
    ret_pct = (gross_total / basket_start_value - 1.0) * 100 if basket_start_value > 0 else 0.0
    dist_target = (
        ((target_value / gross_total) - 1.0) * 100 if gross_total > 0 else 0.0
    )
    dist_stop = (
        ((gross_total / stop_value) - 1.0) * 100 if stop_value > 0 else 0.0
    )

    return BasketValuation(
        gross_market_value=gross_total,
        estimated_exit_cost=exit_cost,
        net_liquidation_value=net_total,
        basket_start_value=basket_start_value,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        return_pct=ret_pct,
        distance_to_target_pct=dist_target,
        distance_to_stop_pct=dist_stop,
        trigger=trigger,
        target_value=target_value,
        stop_value=stop_value,
        constituents=cvals,
    )
