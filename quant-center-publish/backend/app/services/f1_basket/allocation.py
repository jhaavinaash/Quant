"""Equal-weight allocation — integer shares for Indian equities."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.f1_basket.constants import BUY_COST_PCT
from app.services.f1_basket.selection import F1BuyCandidate


@dataclass
class ConstituentAllocation:
    ticker: str
    portfolio_rank: float
    selection_order: int
    reference_price: float
    target_weight: float
    allocated_amount: float
    quantity: int
    gross_buy_value: float
    estimated_buy_cost: float
    estimated_total_entry_cost: float
    candidate: F1BuyCandidate
    target_slot_exposure: float = 0.0
    current_broker_qty: float = 0.0
    current_exposure: float = 0.0
    exposure_gap: float = 0.0
    recommended_buy_qty: int = 0
    recommended_buy_value: float = 0.0


@dataclass
class BasketAllocationResult:
    initial_capital: float
    allocated_capital: float
    cash_remaining: float
    basket_start_value: float
    target_value: float
    stop_value: float
    total_estimated_buy_cost: float
    constituents: list[ConstituentAllocation]


def allocate_equal_weight(
    candidates: list[F1BuyCandidate],
    initial_capital: float,
    *,
    basket_size: int,
    profit_target_pct: float,
    hard_stop_pct: float,
    buy_cost_pct: float = BUY_COST_PCT,
) -> BasketAllocationResult:
    """
    Equal-weight slot sizing (locked research cost semantics), integer shares only:
      slot = capital / n_deployable
      equal_weight_allocation = slot / (1 + transaction_cost)
      quantity = floor(equal_weight_allocation / reference_price)
      gross_buy_value = quantity * reference_price
      fee = gross_buy_value * transaction_cost
      basket_start_value = sum(gross_buy_value)  — gross invested, excludes buy fees
    """
    n = len(candidates)
    if n == 0:
        return BasketAllocationResult(
            initial_capital=initial_capital,
            allocated_capital=0.0,
            cash_remaining=initial_capital,
            basket_start_value=0.0,
            target_value=0.0,
            stop_value=0.0,
            total_estimated_buy_cost=0.0,
            constituents=[],
        )

    slot = initial_capital / n
    weight = 1.0 / basket_size
    constituents: list[ConstituentAllocation] = []
    total_gross = 0.0
    total_fees = 0.0
    total_entry = 0.0

    for i, cand in enumerate(candidates, start=1):
        price = cand.reference_price
        if price <= 0:
            price = 1.0  # guard only; preview should use F1 Close
        equal_weight_allocation = slot / (1.0 + buy_cost_pct)
        shares = math.floor(equal_weight_allocation / price)
        gross_buy_value = shares * price
        fee = gross_buy_value * buy_cost_pct
        entry_cost = gross_buy_value + fee
        constituents.append(
            ConstituentAllocation(
                ticker=cand.ticker,
                portfolio_rank=cand.portfolio_rank,
                selection_order=i,
                reference_price=price,
                target_weight=weight,
                allocated_amount=slot,
                quantity=shares,
                gross_buy_value=gross_buy_value,
                estimated_buy_cost=fee,
                estimated_total_entry_cost=entry_cost,
                candidate=cand,
            )
        )
        total_gross += gross_buy_value
        total_fees += fee
        total_entry += entry_cost

    basket_start = total_gross
    cash_remaining = initial_capital - total_entry

    return BasketAllocationResult(
        initial_capital=initial_capital,
        allocated_capital=total_gross,
        cash_remaining=cash_remaining,
        basket_start_value=basket_start,
        target_value=basket_start * (1.0 + profit_target_pct),
        stop_value=basket_start * (1.0 - hard_stop_pct),
        total_estimated_buy_cost=total_fees,
        constituents=constituents,
    )


def allocate_controlled_entry(
    candidates: list[F1BuyCandidate],
    initial_capital: float,
    broker_holdings: dict,
    *,
    basket_size: int,
    profit_target_pct: float,
    hard_stop_pct: float,
    buy_cost_pct: float = BUY_COST_PCT,
) -> BasketAllocationResult:
    """
    Gap-based recommended BUY sizing per slot (capital / basket_size target exposure).
    Does not auto-attribute existing holdings — preview only.
    """
    n = len(candidates)
    if n == 0:
        return BasketAllocationResult(
            initial_capital=initial_capital,
            allocated_capital=0.0,
            cash_remaining=initial_capital,
            basket_start_value=0.0,
            target_value=0.0,
            stop_value=0.0,
            total_estimated_buy_cost=0.0,
            constituents=[],
        )

    slot_target = initial_capital / basket_size
    weight = 1.0 / basket_size
    constituents: list[ConstituentAllocation] = []
    total_recommended_gross = 0.0
    total_fees = 0.0
    total_entry = 0.0

    for i, cand in enumerate(candidates, start=1):
        price = cand.reference_price if cand.reference_price > 0 else 1.0
        bare = cand.ticker.upper().replace(".NS", "").replace(".BO", "")
        holding = broker_holdings.get(bare)
        current_qty = holding.quantity if holding else 0.0
        current_exposure = holding.exposure if holding else 0.0
        gap = max(0.0, slot_target - current_exposure)

        if gap <= 0:
            rec_qty = 0
            rec_gross = 0.0
        else:
            deployable = gap / (1.0 + buy_cost_pct)
            rec_qty = math.floor(deployable / price)
            rec_gross = rec_qty * price

        fee = rec_gross * buy_cost_pct
        entry_cost = rec_gross + fee

        constituents.append(
            ConstituentAllocation(
                ticker=cand.ticker,
                portfolio_rank=cand.portfolio_rank,
                selection_order=i,
                reference_price=price,
                target_weight=weight,
                allocated_amount=slot_target,
                quantity=rec_qty,
                gross_buy_value=rec_gross,
                estimated_buy_cost=fee,
                estimated_total_entry_cost=entry_cost,
                candidate=cand,
                target_slot_exposure=slot_target,
                current_broker_qty=current_qty,
                current_exposure=round(current_exposure, 2),
                exposure_gap=round(gap, 2),
                recommended_buy_qty=rec_qty,
                recommended_buy_value=rec_gross,
            )
        )
        total_recommended_gross += rec_gross
        total_fees += fee
        total_entry += entry_cost

    preview_start = sum(
        min(slot_target, c.current_exposure) + c.recommended_buy_value for c in constituents
    )

    return BasketAllocationResult(
        initial_capital=initial_capital,
        allocated_capital=total_recommended_gross,
        cash_remaining=initial_capital - total_entry,
        basket_start_value=preview_start,
        target_value=preview_start * (1.0 + profit_target_pct) if preview_start else 0.0,
        stop_value=preview_start * (1.0 - hard_stop_pct) if preview_start else 0.0,
        total_estimated_buy_cost=total_fees,
        constituents=constituents,
    )
