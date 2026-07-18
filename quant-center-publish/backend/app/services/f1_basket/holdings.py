"""Canonical broker holdings for F1 Basket controlled entry."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.position_service import PositionService


def _bare(ticker: str) -> str:
    return str(ticker).strip().upper().replace(".NS", "").replace(".BO", "")


@dataclass
class BrokerHolding:
    ticker: str
    quantity: float
    avg_price: float
    current_price: float
    exposure: float


def load_broker_holdings() -> dict[str, BrokerHolding]:
    """
    Aggregate open positions by ticker via PositionService (canonical reader).
    Returns bare ticker key -> holding.
    """
    out: dict[str, BrokerHolding] = {}
    for pos in PositionService.get_open_positions():
        key = _bare(pos.instrument)
        price = pos.currentPrice if pos.currentPrice is not None else pos.avgPrice
        exposure = pos.quantity * price
        if key in out:
            existing = out[key]
            total_qty = existing.quantity + pos.quantity
            total_exposure = existing.exposure + exposure
            avg = total_exposure / total_qty if total_qty else pos.avgPrice
            out[key] = BrokerHolding(
                ticker=key,
                quantity=total_qty,
                avg_price=avg,
                current_price=price,
                exposure=total_exposure,
            )
        else:
            out[key] = BrokerHolding(
                ticker=key,
                quantity=pos.quantity,
                avg_price=pos.avgPrice,
                current_price=price,
                exposure=exposure,
            )
    return out
