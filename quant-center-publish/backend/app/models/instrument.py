from datetime import date
from decimal import Decimal
from sqlalchemy import String, Numeric, Date, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Instrument(Base, TimestampMixin):
    """
    Centralized Instrument Master Contract Registry.
    
    Serves as the absolute, broker-independent single source of truth for all
    tradable financial vehicles across present and future global asset matrices
    (Equities, ETFs, Options, Futures, Commodities, Currencies, Crypto).
    """
    __tablename__ = "instruments"

    __table_args__ = (
        # Ensure database-level uniqueness for a specific operational symbol per exchange venue
        UniqueConstraint(
            "exchange", 
            "trading_symbol", 
            name="uq_exchange_trading_symbol"
        ),
        # Low-latency multi-index coverage for high-frequency runtime lookups by identification codes
        Index("ix_instruments_exchange_symbol", "exchange", "symbol"),
        Index("ix_instruments_isin", "isin", unique=False),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Exchange Venue Identification Boundaries
    exchange: Mapped[str] = mapped_column(String(20), nullable=False, index=True)          # e.g., "NSE", "NFO", "NASDAQ", "MCX"
    segment: Mapped[str] = mapped_column(String(20), nullable=False, index=True)           # e.g., "NSE_EQ", "NFO_OPT", "NFO_FUT", "NASDAQ_EQ"
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)            # Base underlying symbol (e.g., "RELIANCE", "AAPL")
    trading_symbol: Mapped[str] = mapped_column(String(96), nullable=False, index=True)    # Exact execution ticker string (e.g., "RELIANCE-EQ", "NIFTY26JUL22000CE")
    instrument_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True) # Generic master tracking code if assigned by venue
    isin: Mapped[str | None] = mapped_column(String(32), nullable=True)                    # International Securities Identification Number (Global standard)
    
    # Categorization Matrix
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)        # e.g., "EQUITY", "ETF", "FUTURE", "OPTION", "CURRENCY", "COMMODITY"
    
    # Derivative Specifications (Populated conditionally based on asset footprint)
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    strike: Mapped[Decimal | None] = mapped_column(Numeric(16, 4), nullable=True)
    option_type: Mapped[str | None] = mapped_column(String(8), nullable=True)              # e.g., "CE", "PE", "CALL", "PUT"
    
    # Mathematical Order Entry Matching Properties
    tick_size: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0.05, nullable=False)
    lot_size: Mapped[int] = mapped_column(default=1, nullable=False)
    
    # Multi-Currency Operational Support
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)       # e.g., "INR", "USD", "EUR"
    
    # System Visibility Flag Mapping
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)