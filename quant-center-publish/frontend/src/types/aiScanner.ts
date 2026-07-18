export interface ScannerKpis {
  strongBuys: number;
  exitFlags: number;
  watchlist: number;
  universe: number;
  topSector: string;
  topSectorScore: number;
  avgScore: number;
}

export interface ScanResultRow {
  ticker: string;
  companyName: string;
  sector: string;
  action: string;
  conviction: number;
  compositeScore: number;
  groupsFired: number;
  currentPrice: number;
  suggestedEntry: number;
  suggestedStop: number;
  suggestedTarget: number;
  suggestedQty: number;
  maxRiskInr: number;
  rrRatio: number;
  expectedReturnPct: number;
  rsi?: number | null;
  ret1m?: number | null;
  rsVsNifty60d?: number | null;
  bullSignals: string[];
  bearSignals: string[];
  nextEventDisplay: string;
  nextEventLabel?: string | null;
  nextEventDays?: number | null;
  currentPnlPct?: number | null;
  stars: string;
}

export interface StrongBuyTableRow {
  ticker: string;
  company: string;
  sector: string;
  stars: string;
  score: number;
  groups: number;
  entry: number;
  stopLoss: number;
  target: number;
  rrRatio: number;
  qty: number;
  riskInr: number;
  expectedReturnPct: number;
  ret1m: number;
  rsi: number;
  rsVsNifty60d: number;
  catalyst: string;
}

export interface WatchlistTableRow {
  ticker: string;
  company: string;
  sector: string;
  score: number;
  groups: number;
  action: string;
  cmp: number;
  rsi: number;
  ret1m: number;
  rsVsNifty60d: number;
  keySignal: string;
}

export interface SectorStrengthRow {
  sector: string;
  stocks: number;
  momentum1mPct: number;
  avgScore: number;
  topStockScore: number;
}

export interface PaperTradeRow {
  addedDate: string;
  addedTs: string;
  source: string;
  ticker: string;
  score?: number | null;
  entry?: number | null;
  sl?: number | null;
  target?: number | null;
  qty?: number | null;
  risk?: number | null;
  status: string;
  exitPrice?: number | null;
  exitDate: string;
  cmp?: number | null;
  returnPct?: number | null;
  pnlInr?: number | null;
  days: number;
  outcome: string;
}

export interface PaperTradeSummary {
  total: number;
  open: number;
  tp: number;
  sl: number;
  hitRate?: number | null;
  totalPnlInr?: number | null;
}

export interface LiveWatchStatus {
  status: string;
  lastAutomaticScan: string;
  nextScheduledScan: string;
  lastScanStatus: string;
  newSignalsToday: number;
  emailsSentToday: number;
  lastError: string;
}

export interface NewTodayEventRow {
  eventId: string;
  detectedAt: string;
  ticker: string;
  score?: number | null;
  signal: string;
  groupsMet?: number | null;
  entry?: number | null;
  sl?: number | null;
  target?: number | null;
  qty?: number | null;
  risk?: number | null;
  sector: string;
  reason: string;
  scanSource: string;
  emailStatus: string;
  emailError: string;
}

export interface AIScannerSnapshot {
  scannedAt: string;
  capitalPerPick: number;
  scanAvailable: boolean;
  scanError?: string;
  kpis: ScannerKpis;
  exits: ScanResultRow[];
  topOpportunities: ScanResultRow[];
  strongBuys: StrongBuyTableRow[];
  watchlist: WatchlistTableRow[];
  sectorStrength: SectorStrengthRow[];
  noStrongBuyMessage: string;
  paperTradesAutoExited: number;
  paperTradeSummary: PaperTradeSummary;
  paperTrades: PaperTradeRow[];
  openPaperTickers: string[];
  footerNote: string;
  liveWatch: LiveWatchStatus;
  newTodayEvents: NewTodayEventRow[];
}

export interface AddPaperTradeRequest {
  ticker: string;
  source?: string;
}

export interface ExitPaperTradeRequest {
  exitPrice?: number;
}

export interface AIScannerActionResult {
  success: boolean;
  message: string;
  autoExited?: number;
  snapshot?: AIScannerSnapshot;
}
