export interface DashboardMetrics {
  portfolioValue: number;
  todayPnL: number;
  activePositions: number;
  pendingOrders: number;
  activeEngines: number;
  systemHealth: number;
}

export interface MarketIndexQuote {
  name: string;
  ticker: string;
  price?: number | null;
  changePct?: number | null;
}

export interface EngineCagrCard {
  engine: string;
  cagr?: number | null;
  roc?: number | null;
  trades?: number | null;
  days?: number | null;
  subtitle: string;
}

export interface DashboardSnapshot {
  marketOpen: boolean;
  timestamp: string;
  refreshLabel: string;
  totalPnl: number;
  realizedPnl: number;
  unrealizedPnl: number;
  openPositions: number;
  capitalDeployed: number;
  winRate: number;
  totalClosed: number;
  activeSignals: number;
  portfolioCagr?: number | null;
  portfolioRoc?: number | null;
  portfolioInception?: string | null;
  engineCagrs: EngineCagrCard[];
  marketIndices: MarketIndexQuote[];
}

export interface ControlResult {
  kind: 'success' | 'warning' | 'error';
  main: string;
  hint?: string;
}

export interface Position {
  id: string;
  instrument: string;
  quantity: number;
  avgPrice: number;
  pnl: number;
  entryDate?: string;
  currentPrice?: number | null;
  returnPct?: number | null;
  engine?: string;
  sector?: string;
  holdDays?: number | null;
  sl?: number | null;
  target?: number | null;
  technicalState?: string;
  sectorState?: string;
  exitRule?: string;
  status?: string;
  exitStatus?: string;
  exitReason?: string;
  canExit?: boolean;
}

export type PositionExitReason = 'Manual' | 'SL' | 'TP' | 'Strategy Exit';

export interface PositionExitResult {
  success: boolean;
  message: string;
  tradeKey?: string;
  exitId?: string;
  brokerOrderId?: string;
  status?: string;
  exitStatusLabel?: string;
}

export interface Signal {
  id: string;
  timestamp: string; // ISO format
  instrument: string;
  type: 'BUY' | 'SELL';
  price: number;
}

export interface Instrument {
  id: number;
  exchange: string;
  segment: string;
  symbol: string;
  trading_symbol: string;
  instrument_token?: string | null;
  isin?: string | null;
  asset_type: string;
  expiry?: string | null;
  strike?: number | null;
  option_type?: string | null;
  tick_size: number;
  lot_size: number;
  currency: string;
  is_active: boolean;
}

export interface InstrumentPaginatedResponse {
  items: Instrument[];
  total_count: number;
  page: number;
  size: number;
}

export type HealthStatus = 'healthy' | 'warning' | 'offline';

export interface SystemHealth {
  database: HealthStatus;
  api: HealthStatus;
  quantBaseDir: HealthStatus;
  quantExecution: HealthStatus;
  engines: HealthStatus;
}

export interface UserSettings {
  theme: 'dark' | 'light';
  notificationsEnabled: boolean;
}