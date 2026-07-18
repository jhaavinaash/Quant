from typing import Any, Optional

from pydantic import BaseModel, Field


class PendingDeployTrade(BaseModel):
    ticker: str = ""
    engine: str = ""
    close: float = 0.0
    suggestedQty: float = 1.0
    rank: str = ""
    sector: str = ""
    technical: str = ""
    business: str = ""


class TradeBookRow(BaseModel):
    rowIndex: int
    date: str = ""
    engine: str = ""
    ticker: str = ""
    action: str = ""
    entryPrice: Optional[float] = None
    qty: Optional[float] = None
    stopLoss: Optional[float] = None
    target: Optional[float] = None
    cmp: Optional[float] = None
    pnl: Optional[float] = None
    status: str = ""
    exitDate: str = ""
    exitPrice: Optional[float] = None
    notes: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class TradeEntrySnapshot(BaseModel):
    trades: list[TradeBookRow] = Field(default_factory=list)
    pendingDeploy: Optional[PendingDeployTrade] = None


class TradeEntryAddRequest(BaseModel):
    tradeDate: str = Field(..., description="ISO date YYYY-MM-DD")
    engine: str = "MANUAL"
    action: str = "BUY"
    ticker: str
    entryPrice: float
    qty: float
    stopLoss: float = 0.0
    target: float = 0.0
    notes: str = ""


class TradeEntryEditRequest(BaseModel):
    tradeDate: str
    engine: str
    action: str
    ticker: str
    qty: float
    entryPrice: float
    stopLoss: float = 0.0
    target: float = 0.0
    status: str = "OPEN"
    notes: str = ""
    exitPrice: Optional[float] = None
    exitDate: Optional[str] = None


class TradeEntryCloseRequest(BaseModel):
    exitPrice: float
    exitDate: str = Field(..., description="ISO date YYYY-MM-DD")


class TradeEntryActionResult(BaseModel):
    success: bool
    message: str
    pnl: Optional[float] = None
    rebuiltOpenPositions: bool = False
