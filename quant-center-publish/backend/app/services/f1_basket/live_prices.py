"""Live NSE prices for F1 Basket — reuses F1 production yfinance path."""

from __future__ import annotations

from app.services.f1_service import _live_prices


def fetch_live_prices(tickers: list[str]) -> dict[str, float]:
    """Return bare_upper_ticker -> price using shared _live_prices (60s cache)."""
    if not tickers:
        return {}
    return _live_prices(tuple(sorted(set(tickers))))
