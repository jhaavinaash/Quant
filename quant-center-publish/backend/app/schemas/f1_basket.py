from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class BasketStrategyParams(BaseModel):
    strategyName: str
    basketSize: int = 12
    initialCapital: float = 200_000
    profitTargetPct: float = 12.0
    hardStopPct: float = 15.0
    buyCostPct: float = 0.30
    sellCostPct: float = 0.30
    weighting: str = "equal"


class F1BuyCandidateRow(BaseModel):
    ticker: str
    portfolioRank: float
    action: str
    technicalState: str = ""
    sectorState: str = ""
    businessGate: str = ""
    sector: str = ""
    referencePrice: float = 0.0
    heldGlobally: bool = False
    heldConflict: bool = False


class BasketEligibility(BaseModel):
    f1DecisionTimestamp: str = ""
    totalDecisions: int = 0
    buyCandidateCount: int = 0
    requiredConstituents: int = 12
    availableCandidates: int = 0
    missingCandidates: int = 0
    ready: bool = False
    status: str = "NOT_READY"
    topCandidates: list[F1BuyCandidateRow] = Field(default_factory=list)


class BasketConstituentRow(BaseModel):
    selectionOrder: int
    ticker: str
    portfolioRank: float
    targetWeight: float
    referencePrice: float
    quantity: float
    grossAllocation: float
    buyCost: float
    totalEntryCost: float
    currentPrice: float
    currentValue: float
    pnl: float
    returnPct: float
    heldGloballyAtSelection: bool = False
    f1ActionAtSelection: str = ""
    technicalStateAtSelection: str = ""
    sectorStateAtSelection: str = ""
    businessGateAtSelection: str = ""
    sectorAtSelection: str = ""
    brokerOrderId: str = ""
    fillStatus: str = ""
    filledQty: float = 0.0
    averageFillPrice: float = 0.0
    lastError: str = ""
    avgBuyPrice: float = 0.0
    sellBrokerOrderId: str = ""
    sellStatus: str = ""
    sellFilledQty: float = 0.0
    averageSellFillPrice: float = 0.0
    sellLastError: str = ""
    targetSlotExposure: float = 0.0
    currentBrokerQty: float = 0.0
    currentExposure: float = 0.0
    exposureGap: float = 0.0
    recommendedBuyQty: float = 0.0
    recommendedBuyValue: float = 0.0
    adoptedExistingQty: float = 0.0
    basketBoughtQty: float = 0.0
    basketAttributedQty: float = 0.0
    slotResolved: bool = False
    slotSkipped: bool = False
    attributionPrice: float = 0.0


class BasketExitProgress(BaseModel):
    total: int = 12
    complete: int = 0
    submitted: int = 0
    pending: int = 0
    partial: int = 0
    failed: int = 0


class BasketDeploymentProgress(BaseModel):
    total: int = 12
    complete: int = 0
    resolved: int = 0
    submitted: int = 0
    pending: int = 0
    partial: int = 0
    failed: int = 0


class BasketDeployConfirmation(BaseModel):
    basketId: str
    capital: float
    stockCount: int = 12
    totalEstimatedInvestment: float
    estimatedBuyCost: float
    cashRemaining: float
    broker: str = "Zerodha"
    constituents: list[BasketConstituentRow] = Field(default_factory=list)


class BasketPreviewSummary(BaseModel):
    basketId: str = ""
    status: str = ""
    createdAt: str = ""
    selectionSnapshotTimestamp: str = ""
    currentF1DecisionTimestamp: str = ""
    previewStale: bool = False
    capital: float = 0.0
    allocated: float = 0.0
    cashRemaining: float = 0.0
    basketStartValue: float = 0.0
    targetValue: float = 0.0
    stopValue: float = 0.0
    estimatedBuyCost: float = 0.0
    estimatedExitCost: float = 0.0
    grossMarketValue: float = 0.0
    netLiquidationValue: float = 0.0
    grossPnl: float = 0.0
    netPnl: float = 0.0
    basketReturnPct: float = 0.0
    distanceToTargetPct: float = 0.0
    distanceToStopPct: float = 0.0
    currentTrigger: str = "NONE"
    heldConflicts: list[str] = Field(default_factory=list)
    constituents: list[BasketConstituentRow] = Field(default_factory=list)
    deploymentProgress: Optional[BasketDeploymentProgress] = None
    deployAllowed: bool = False
    deployBlockReason: str = ""
    canRetryFailed: bool = False
    deploymentIncomplete: bool = False
    broker: str = "Zerodha"
    startedAt: str = ""
    completedAt: str = ""
    exitTrigger: str = ""
    exitReason: str = ""
    triggeredAt: str = ""
    lastValuedAt: str = ""
    canManualExit: bool = False
    canRetryFailedExits: bool = False
    exitIncomplete: bool = False
    exitProgress: Optional[BasketExitProgress] = None
    resolvedSlots: int = 0
    maxSlots: int = 12
    canDeploySelected: bool = False


class DeploySlotSelection(BaseModel):
    ticker: str
    execute: bool = False
    adoptExistingQty: int = 0


class DeploySelectedRequest(BaseModel):
    basketId: str
    selections: list[DeploySlotSelection] = Field(default_factory=list)


class F1BasketSnapshot(BaseModel):
    strategy: BasketStrategyParams = Field(default_factory=BasketStrategyParams)
    eligibility: BasketEligibility = Field(default_factory=BasketEligibility)
    preview: Optional[BasketPreviewSummary] = None
    message: str = ""


class CreateBasketPreviewRequest(BaseModel):
    capital: float = 200_000


class BasketActionRequest(BaseModel):
    basketId: str


class BasketActionResult(BaseModel):
    success: bool
    message: str = ""
    snapshot: Optional[F1BasketSnapshot] = None
