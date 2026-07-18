export interface BasketStrategyParams {
  strategyName: string;
  basketSize: number;
  initialCapital: number;
  profitTargetPct: number;
  hardStopPct: number;
  buyCostPct: number;
  sellCostPct: number;
  weighting: string;
}

export interface F1BuyCandidateRow {
  ticker: string;
  portfolioRank: number;
  action: string;
  technicalState: string;
  sectorState: string;
  businessGate: string;
  sector: string;
  referencePrice: number;
  heldGlobally: boolean;
  heldConflict: boolean;
}

export interface BasketEligibility {
  f1DecisionTimestamp: string;
  totalDecisions: number;
  buyCandidateCount: number;
  requiredConstituents: number;
  availableCandidates: number;
  missingCandidates: number;
  ready: boolean;
  status: string;
  topCandidates: F1BuyCandidateRow[];
}

export interface BasketConstituentRow {
  selectionOrder: number;
  ticker: string;
  portfolioRank: number;
  targetWeight: number;
  referencePrice: number;
  quantity: number;
  grossAllocation: number;
  buyCost: number;
  totalEntryCost: number;
  currentPrice: number;
  currentValue: number;
  pnl: number;
  returnPct: number;
  heldGloballyAtSelection: boolean;
  brokerOrderId?: string;
  fillStatus?: string;
  filledQty?: number;
  averageFillPrice?: number;
  lastError?: string;
  targetSlotExposure?: number;
  currentBrokerQty?: number;
  currentExposure?: number;
  exposureGap?: number;
  recommendedBuyQty?: number;
  recommendedBuyValue?: number;
  adoptedExistingQty?: number;
  basketBoughtQty?: number;
  basketAttributedQty?: number;
  slotResolved?: boolean;
  slotSkipped?: boolean;
  attributionPrice?: number;
  f1ActionAtSelection?: string;
  technicalStateAtSelection?: string;
  sectorStateAtSelection?: string;
  businessGateAtSelection?: string;
  sectorAtSelection?: string;
  sellBrokerOrderId?: string;
  sellStatus?: string;
  sellFilledQty?: number;
  averageSellFillPrice?: number;
  sellLastError?: string;
  avgBuyPrice?: number;
}

export interface BasketDeploymentProgress {
  total: number;
  complete: number;
  resolved: number;
  submitted: number;
  pending: number;
  partial: number;
  failed: number;
}

export interface BasketDeployConfirmation {
  basketId: string;
  capital: number;
  stockCount: number;
  totalEstimatedInvestment: number;
  estimatedBuyCost: number;
  cashRemaining: number;
  broker: string;
  constituents: BasketConstituentRow[];
}

export interface BasketActionResult {
  success: boolean;
  message: string;
  snapshot?: F1BasketSnapshot;
}

export interface BasketPreviewSummary {
  basketId: string;
  status: string;
  createdAt: string;
  selectionSnapshotTimestamp: string;
  currentF1DecisionTimestamp: string;
  previewStale: boolean;
  capital: number;
  allocated: number;
  cashRemaining: number;
  basketStartValue: number;
  targetValue: number;
  stopValue: number;
  estimatedBuyCost: number;
  estimatedExitCost: number;
  grossMarketValue: number;
  netLiquidationValue: number;
  grossPnl: number;
  netPnl: number;
  basketReturnPct: number;
  distanceToTargetPct: number;
  distanceToStopPct: number;
  currentTrigger: string;
  heldConflicts: string[];
  constituents: BasketConstituentRow[];
  deploymentProgress?: BasketDeploymentProgress | null;
  deployAllowed?: boolean;
  deployBlockReason?: string;
  canRetryFailed?: boolean;
  canManualExit?: boolean;
  canRetryFailedExits?: boolean;
  deploymentIncomplete?: boolean;
  broker?: string;
  startedAt?: string;
  resolvedSlots?: number;
  maxSlots?: number;
  canDeploySelected?: boolean;
}

export interface DeploySlotSelection {
  ticker: string;
  execute: boolean;
  adoptExistingQty: number;
}

export interface DeploySelectedRequest {
  basketId: string;
  selections: DeploySlotSelection[];
}

export interface F1BasketSnapshot {
  strategy: BasketStrategyParams;
  eligibility: BasketEligibility;
  preview?: BasketPreviewSummary | null;
  message: string;
}
