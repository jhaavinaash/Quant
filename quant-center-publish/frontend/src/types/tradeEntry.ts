export interface PendingDeployTrade {
  ticker: string;
  engine: string;
  close: number;
  suggestedQty: number;
  rank: string;
  sector: string;
  technical: string;
  business: string;
}

export interface TradeBookRow {
  rowIndex: number;
  date: string;
  engine: string;
  ticker: string;
  action: string;
  entryPrice?: number | null;
  qty?: number | null;
  stopLoss?: number | null;
  target?: number | null;
  cmp?: number | null;
  pnl?: number | null;
  status: string;
  exitDate: string;
  exitPrice?: number | null;
  notes: string;
  extra?: Record<string, unknown>;
}

export interface TradeEntrySnapshot {
  trades: TradeBookRow[];
  pendingDeploy?: PendingDeployTrade | null;
}

export interface TradeEntryAddRequest {
  tradeDate: string;
  engine: string;
  action: string;
  ticker: string;
  entryPrice: number;
  qty: number;
  stopLoss: number;
  target: number;
  notes: string;
}

export interface TradeEntryEditRequest {
  tradeDate: string;
  engine: string;
  action: string;
  ticker: string;
  qty: number;
  entryPrice: number;
  stopLoss: number;
  target: number;
  status: string;
  notes: string;
  exitPrice?: number | null;
  exitDate?: string | null;
}

export interface TradeEntryCloseRequest {
  exitPrice: number;
  exitDate: string;
}

export interface TradeEntryActionResult {
  success: boolean;
  message: string;
  pnl?: number | null;
  rebuiltOpenPositions?: boolean;
}

export type TradeAction = 'BUY' | 'SELL';
export type TradeStatus = 'OPEN' | 'CLOSED';
