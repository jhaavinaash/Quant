"""Calculation settings for the Market Intelligence foundation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketIntelligenceConfig:
    """Window and column settings used by the four dimension calculators.

    These values define observation periods only. They are not decision
    thresholds and do not imply a market state.
    """

    medium_window: int = 50
    long_window: int = 200
    participation_change_window: int = 5
    leadership_lookback: int = 20
    stress_window: int = 20
    drawdown_window: int = 252
    annualization_periods: int = 252

    date_column: str = "Date"
    ticker_column: str = "Ticker"
    close_column: str = "Close"
    sector_ticker_column: str = "Ticker"
    sector_column: str = "Sector"

    def __post_init__(self) -> None:
        windows = {
            "medium_window": self.medium_window,
            "long_window": self.long_window,
            "participation_change_window": self.participation_change_window,
            "leadership_lookback": self.leadership_lookback,
            "stress_window": self.stress_window,
            "drawdown_window": self.drawdown_window,
            "annualization_periods": self.annualization_periods,
        }
        invalid = [name for name, value in windows.items() if value <= 0]
        if invalid:
            names = ", ".join(invalid)
            raise ValueError(f"Configuration values must be positive: {names}")

        columns = {
            "date_column": self.date_column,
            "ticker_column": self.ticker_column,
            "close_column": self.close_column,
            "sector_ticker_column": self.sector_ticker_column,
            "sector_column": self.sector_column,
        }
        blank = [name for name, value in columns.items() if not value.strip()]
        if blank:
            names = ", ".join(blank)
            raise ValueError(f"Column names cannot be blank: {names}")
