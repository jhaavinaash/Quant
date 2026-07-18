from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ScannerKpis(BaseModel):
    strongBuys: int = 0
    exitFlags: int = 0
    watchlist: int = 0
    universe: int = 0
    topSector: str = "—"
    topSectorScore: float = 0.0
    avgScore: float = 0.0


class ScanResultRow(BaseModel):
    ticker: str
    companyName: str = ""
    sector: str = ""
    action: str = ""
    conviction: int = 0
    compositeScore: float = 0.0
    groupsFired: int = 0
    trendScore: float = 50.0
    momentumScore: float = 50.0
    setupScore: float = 50.0
    sectorScore: float = 50.0
    currentPrice: float = 0.0
    suggestedEntry: float = 0.0
    suggestedStop: float = 0.0
    suggestedTarget: float = 0.0
    suggestedQty: int = 0
    capitalUsed: float = 0.0
    maxRiskInr: float = 0.0
    rrRatio: float = 0.0
    expectedReturnPct: float = 0.0
    rsi: Optional[float] = None
    atr14: Optional[float] = None
    pctFrom52wHigh: Optional[float] = None
    pctFrom52wLow: Optional[float] = None
    avgVolume20d: Optional[float] = None
    ret1m: Optional[float] = None
    ret3m: Optional[float] = None
    rsVsNifty60d: Optional[float] = None
    bullSignals: list[str] = Field(default_factory=list)
    bearSignals: list[str] = Field(default_factory=list)
    nextEventDays: Optional[int] = None
    nextEventLabel: Optional[str] = None
    isExistingPosition: bool = False
    currentPnlPct: Optional[float] = None
    nextEventDisplay: str = ""
    stars: str = ""


class StrongBuyTableRow(BaseModel):
    ticker: str
    company: str = ""
    sector: str = ""
    stars: str = ""
    score: float = 0.0
    groups: int = 0
    entry: float = 0.0
    stopLoss: float = 0.0
    target: float = 0.0
    rrRatio: float = 0.0
    qty: int = 0
    riskInr: float = 0.0
    expectedReturnPct: float = 0.0
    ret1m: float = 0.0
    rsi: float = 0.0
    rsVsNifty60d: float = 0.0
    catalyst: str = ""


class WatchlistTableRow(BaseModel):
    ticker: str
    company: str = ""
    sector: str = ""
    score: float = 0.0
    groups: int = 0
    action: str = ""
    cmp: float = 0.0
    rsi: float = 0.0
    ret1m: float = 0.0
    rsVsNifty60d: float = 0.0
    keySignal: str = ""


class SectorStrengthRow(BaseModel):
    sector: str
    stocks: int = 0
    momentum1mPct: float = 0.0
    avgScore: float = 0.0
    topStockScore: float = 0.0


class PaperTradeRow(BaseModel):
    addedDate: str = ""
    addedTs: str = ""
    source: str = ""
    ticker: str = ""
    score: Optional[float] = None
    entry: Optional[float] = None
    sl: Optional[float] = None
    target: Optional[float] = None
    qty: Optional[float] = None
    risk: Optional[float] = None
    status: str = ""
    exitPrice: Optional[float] = None
    exitDate: str = ""
    cmp: Optional[float] = None
    returnPct: Optional[float] = None
    pnlInr: Optional[float] = None
    days: int = 0
    outcome: str = ""


class PaperTradeSummary(BaseModel):
    total: int = 0
    open: int = 0
    tp: int = 0
    sl: int = 0
    hitRate: Optional[float] = None
    totalPnlInr: Optional[float] = None


class LiveWatchStatus(BaseModel):
    status: str = "INACTIVE"  # ACTIVE | INACTIVE | ERROR
    lastAutomaticScan: str = ""
    nextScheduledScan: str = ""
    lastScanStatus: str = ""
    newSignalsToday: int = 0
    emailsSentToday: int = 0
    lastError: str = ""


class NewTodayEventRow(BaseModel):
    eventId: str = ""
    detectedAt: str = ""
    ticker: str = ""
    score: Optional[float] = None
    signal: str = ""
    groupsMet: Optional[int] = None
    entry: Optional[float] = None
    sl: Optional[float] = None
    target: Optional[float] = None
    qty: Optional[int] = None
    risk: Optional[float] = None
    sector: str = ""
    reason: str = ""
    scanSource: str = ""
    emailStatus: str = "PENDING"
    emailError: str = ""


class AIScannerSnapshot(BaseModel):
    scannedAt: str = ""
    capitalPerPick: int = 15000
    scanAvailable: bool = False
    scanError: str = ""
    kpis: ScannerKpis = Field(default_factory=ScannerKpis)
    exits: list[ScanResultRow] = Field(default_factory=list)
    topOpportunities: list[ScanResultRow] = Field(default_factory=list)
    strongBuys: list[StrongBuyTableRow] = Field(default_factory=list)
    watchlist: list[WatchlistTableRow] = Field(default_factory=list)
    sectorStrength: list[SectorStrengthRow] = Field(default_factory=list)
    noStrongBuyMessage: str = ""
    paperTradesAutoExited: int = 0
    paperTradeSummary: PaperTradeSummary = Field(default_factory=PaperTradeSummary)
    paperTrades: list[PaperTradeRow] = Field(default_factory=list)
    openPaperTickers: list[str] = Field(default_factory=list)
    footerNote: str = ""
    liveWatch: LiveWatchStatus = Field(default_factory=LiveWatchStatus)
    newTodayEvents: list[NewTodayEventRow] = Field(default_factory=list)


class AddPaperTradeRequest(BaseModel):
    ticker: str
    source: str = "AI Scanner"


class ExitPaperTradeRequest(BaseModel):
    exitPrice: float = 0.0


class AIScannerActionResult(BaseModel):
    success: bool
    message: str
    autoExited: int = 0
    snapshot: Optional[AIScannerSnapshot] = None
