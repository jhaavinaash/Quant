export interface TradesSummary {
  closedTrades: number;
  realizedPnl: number;
  winRate: number;
  winners: number;
  losers: number;
}

export interface ClosedTradeRow {
  id: string;
  ticker: string;
  engine: string;
  entryDate: string;
  exitDate: string;
  quantity?: number | null;
  entryPrice?: number | null;
  exitPrice?: number | null;
  returnPct?: number | null;
  pnl?: number | null;
  holdDays?: number | null;
  exitReason: string;
  outcome: string;
  status: string;
  notes: string;
}

export interface TradesSnapshot {
  summary: TradesSummary;
  engines: string[];
  outcomes: string[];
  trades: ClosedTradeRow[];
}

export type TradesOutcomeFilter = 'all' | 'winners' | 'losers' | 'tp' | 'sl' | 'manual';
