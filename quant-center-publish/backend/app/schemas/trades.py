from typing import Optional

from pydantic import BaseModel, Field


class TradesSummary(BaseModel):
    closedTrades: int = 0
    realizedPnl: float = 0.0
    winRate: float = 0.0
    winners: int = 0
    losers: int = 0


class ClosedTradeRow(BaseModel):
    id: str
    ticker: str = ""
    engine: str = ""
    entryDate: str = ""
    exitDate: str = ""
    quantity: Optional[float] = None
    entryPrice: Optional[float] = None
    exitPrice: Optional[float] = None
    returnPct: Optional[float] = None
    pnl: Optional[float] = None
    holdDays: Optional[int] = None
    exitReason: str = ""
    outcome: str = ""
    status: str = ""
    notes: str = ""


class TradesSnapshot(BaseModel):
    summary: TradesSummary
    engines: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    trades: list[ClosedTradeRow] = Field(default_factory=list)
