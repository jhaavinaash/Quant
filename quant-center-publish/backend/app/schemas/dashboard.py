from typing import Literal, Optional

from pydantic import BaseModel, Field


class MarketIndexQuote(BaseModel):
    name: str
    ticker: str
    price: Optional[float] = None
    changePct: Optional[float] = None


class EngineCagrCard(BaseModel):
    engine: str
    cagr: Optional[float] = None
    roc: Optional[float] = None
    trades: Optional[int] = None
    days: Optional[int] = None
    subtitle: str = ""


class DashboardSnapshot(BaseModel):
    marketOpen: bool
    timestamp: str
    refreshLabel: str
    totalPnl: float
    realizedPnl: float
    unrealizedPnl: float
    openPositions: int
    capitalDeployed: float
    winRate: float
    totalClosed: int
    activeSignals: int
    portfolioCagr: Optional[float] = None
    portfolioRoc: Optional[float] = None
    portfolioInception: Optional[str] = None
    engineCagrs: list[EngineCagrCard] = Field(default_factory=list)
    marketIndices: list[MarketIndexQuote] = Field(default_factory=list)


class ControlResult(BaseModel):
    kind: Literal["success", "warning", "error"] = "success"
    main: str
    hint: str = ""
