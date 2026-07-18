from typing import Optional

from pydantic import BaseModel, Field


class PositionResponse(BaseModel):
    id: str = Field(..., description="Stable composite key: ticker|entryDate|engine")
    instrument: str
    quantity: float
    avgPrice: float
    pnl: float
    entryDate: str = ""
    currentPrice: Optional[float] = None
    returnPct: Optional[float] = None
    engine: str = ""
    sector: str = ""
    holdDays: Optional[float] = None
    sl: Optional[float] = None
    target: Optional[float] = None
    technicalState: str = ""
    sectorState: str = ""
    exitRule: str = ""
    status: str = ""
    exitStatus: str = ""
    exitReason: str = ""
    canExit: bool = True


class PositionExitRequest(BaseModel):
    exitReason: str = Field(..., description="Manual | SL | TP | Strategy Exit")


class PositionExitResult(BaseModel):
    success: bool
    message: str
    tradeKey: str = ""
    exitId: str = ""
    brokerOrderId: str = ""
    status: str = ""
    exitStatusLabel: str = ""
