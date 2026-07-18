from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class F1LastRun(BaseModel):
    timestamp: str = ""
    universe: str = ""
    elapsedSec: str = ""
    failures: int = 0
    ok: bool = True


class F1KpiCard(BaseModel):
    label: str
    value: str
    sub: str = ""


class F1CapitalAllocation(BaseModel):
    f1Capital: float
    deployed: float
    deployedPct: float
    cashFree: float
    positionsOpen: int
    maxPositions: int
    freeSlots: int
    capitalPerTrade: float
    deployToday: int
    buySignals: int
    alreadyOwned: int
    cards: list[F1KpiCard] = Field(default_factory=list)


class F1Performance(BaseModel):
    initialCapital: float
    portfolioValue: float
    totalReturn: float
    totalReturnPct: float
    cagrPct: Optional[float] = None
    maxDrawdownPct: float = 0.0
    openTrades: int = 0
    closedTrades: int = 0
    wins: int = 0
    winRate: Optional[float] = None
    cards: list[F1KpiCard] = Field(default_factory=list)


class F1DeployCandidate(BaseModel):
    rowIndex: int
    rankIndex: int
    ticker: str
    portfolioRank: Optional[float] = None
    sector: str = ""
    phase: str = ""
    close: float = 0.0
    rs55: Optional[float] = None
    entryDistPct: Optional[float] = None
    technicalState: str = ""
    sectorState: str = ""
    businessGate: str = ""
    suggestedCapital: float = 0.0
    suggestedQty: int = 0
    positionValue: float = 0.0
    isDeployable: bool = False
    heldElsewhere: bool = False
    heldInF1: bool = False
    heldByEngine: str = ""
    buttonLabel: str = "Watch"
    buttonDisabled: bool = True


class F1ReadyToDeploy(BaseModel):
    candidates: list[F1DeployCandidate] = Field(default_factory=list)
    candidateCount: int = 0
    deployableCount: int = 0
    suggestedCapital: float = 0.0
    deployToday: int = 0
    emptyMessage: str = ""
    allHeldMessage: str = ""
    noCandidatesMessage: str = ""
    phaseBreakdown: list[dict[str, str | int]] = Field(default_factory=list)
    actionBreakdown: list[dict[str, str | int]] = Field(default_factory=list)


class F1HeldRow(BaseModel):
    ticker: str
    sector: str = ""
    phase: str = ""
    portfolioRank: Optional[float] = None
    technicalState: str = ""
    sectorState: str = ""
    rs55: Optional[float] = None
    close: Optional[float] = None
    heldIn: str = ""


class F1OpenPositionRow(BaseModel):
    signal: str = ""
    ticker: str
    entry: float = 0.0
    cmp: float = 0.0
    returnPct: float = 0.0
    pnlInr: float = 0.0
    qty: int = 0
    phase: str = ""
    technical: str = ""
    exitPriority: str = ""
    exitRule: str = ""


class F1DecisionAuditRow(BaseModel):
    date: str = ""
    engine: str = ""
    ticker: str = ""
    decision: str = ""
    reason: str = ""
    technicalState: str = ""
    sectorState: str = ""
    businessGate: str = ""
    portfolioRank: str = ""


class F1DecisionAudit(BaseModel):
    rows: list[F1DecisionAuditRow] = Field(default_factory=list)
    totalF1: int = 0
    dateOptions: list[str] = Field(default_factory=list)


class F1ProductionComponent(BaseModel):
    icon: str = ""
    component: str
    status: str
    detail: str = ""


class F1ProductionStatus(BaseModel):
    overall: str = ""
    generatedAt: str = ""
    components: list[F1ProductionComponent] = Field(default_factory=list)
    emptyMessage: str = ""


class F1TodayDecisionCounts(BaseModel):
    total: int = 0
    buy: int = 0
    rotate: int = 0
    block: int = 0
    watch: int = 0
    ignore: int = 0
    other: int = 0


class F1Snapshot(BaseModel):
    totalCapital: float
    maxPositions: int
    lastRun: Optional[F1LastRun] = None
    todayDecisionCounts: F1TodayDecisionCounts = Field(default_factory=F1TodayDecisionCounts)
    capitalAllocation: F1CapitalAllocation
    performance: F1Performance
    readyToDeploy: F1ReadyToDeploy
    alreadyOwned: list[F1HeldRow] = Field(default_factory=list)
    alreadyOwnedSummary: str = ""
    openPositions: list[F1OpenPositionRow] = Field(default_factory=list)
    openPositionsEmptyMessage: str = ""
    decisionAudit: F1DecisionAudit = Field(default_factory=F1DecisionAudit)
    productionStatus: F1ProductionStatus = Field(default_factory=F1ProductionStatus)


class F1DeployRequest(BaseModel):
    ticker: str


class F1RunResult(BaseModel):
    success: bool
    message: str
    elapsedSec: Optional[float] = None
    stdoutTail: list[str] = Field(default_factory=list)
    stderrTail: str = ""
    snapshot: Optional[F1Snapshot] = None


class F1DeployResult(BaseModel):
    success: bool
    message: str
    snapshot: Optional[F1Snapshot] = None
