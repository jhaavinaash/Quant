export interface F1LastRun {
  timestamp: string;
  universe: string;
  elapsedSec: string;
  failures: number;
  ok: boolean;
}

export interface F1KpiCard {
  label: string;
  value: string;
  sub: string;
}

export interface F1CapitalAllocation {
  f1Capital: number;
  deployed: number;
  deployedPct: number;
  cashFree: number;
  positionsOpen: number;
  maxPositions: number;
  freeSlots: number;
  capitalPerTrade: number;
  deployToday: number;
  buySignals: number;
  alreadyOwned: number;
  cards: F1KpiCard[];
}

export interface F1Performance {
  initialCapital: number;
  portfolioValue: number;
  totalReturn: number;
  totalReturnPct: number;
  cagrPct?: number | null;
  maxDrawdownPct: number;
  openTrades: number;
  closedTrades: number;
  wins: number;
  winRate?: number | null;
  cards: F1KpiCard[];
}

export interface F1DeployCandidate {
  rowIndex: number;
  rankIndex: number;
  ticker: string;
  portfolioRank?: number | null;
  sector: string;
  phase: string;
  close: number;
  rs55?: number | null;
  entryDistPct?: number | null;
  technicalState: string;
  sectorState: string;
  businessGate: string;
  suggestedCapital: number;
  suggestedQty: number;
  positionValue: number;
  isDeployable: boolean;
  heldElsewhere: boolean;
  heldInF1: boolean;
  heldByEngine: string;
  buttonLabel: string;
  buttonDisabled: boolean;
}

export interface F1ReadyToDeploy {
  candidates: F1DeployCandidate[];
  candidateCount: number;
  deployableCount: number;
  suggestedCapital: number;
  deployToday: number;
  emptyMessage: string;
  allHeldMessage: string;
  noCandidatesMessage: string;
  phaseBreakdown: { label: string; count: number }[];
  actionBreakdown: { label: string; count: number }[];
}

export interface F1HeldRow {
  ticker: string;
  sector: string;
  phase: string;
  portfolioRank?: number | null;
  technicalState: string;
  sectorState: string;
  rs55?: number | null;
  close?: number | null;
  heldIn: string;
}

export interface F1OpenPositionRow {
  signal: string;
  ticker: string;
  entry: number;
  cmp: number;
  returnPct: number;
  pnlInr: number;
  qty: number;
  phase: string;
  technical: string;
  exitPriority: string;
  exitRule: string;
}

export interface F1DecisionAuditRow {
  date: string;
  engine: string;
  ticker: string;
  decision: string;
  reason: string;
  technicalState: string;
  sectorState: string;
  businessGate: string;
  portfolioRank: string;
}

export interface F1DecisionAudit {
  rows: F1DecisionAuditRow[];
  totalF1: number;
  dateOptions: string[];
}

export interface F1ProductionComponent {
  icon: string;
  component: string;
  status: string;
  detail: string;
}

export interface F1ProductionStatus {
  overall: string;
  generatedAt: string;
  components: F1ProductionComponent[];
  emptyMessage: string;
}

export interface F1TodayDecisionCounts {
  total: number;
  buy: number;
  rotate: number;
  block: number;
  watch: number;
  ignore: number;
  other: number;
}

export interface F1Snapshot {
  totalCapital: number;
  maxPositions: number;
  lastRun?: F1LastRun | null;
  todayDecisionCounts: F1TodayDecisionCounts;
  capitalAllocation: F1CapitalAllocation;
  performance: F1Performance;
  readyToDeploy: F1ReadyToDeploy;
  alreadyOwned: F1HeldRow[];
  alreadyOwnedSummary: string;
  openPositions: F1OpenPositionRow[];
  openPositionsEmptyMessage: string;
  decisionAudit: F1DecisionAudit;
  productionStatus: F1ProductionStatus;
}

export interface F1RunResult {
  success: boolean;
  message: string;
  elapsedSec?: number | null;
  stdoutTail: string[];
  stderrTail?: string;
  snapshot?: F1Snapshot;
}

export interface F1DeployResult {
  success: boolean;
  message: string;
  snapshot?: F1Snapshot;
}
