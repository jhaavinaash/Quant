export interface MarketBriefingMetric {
  name: string;
  value: string;
}

export interface MarketBriefingHighlight {
  dimension: string;
  state: string;
  explanation: string;
}

export interface MarketBriefingDimension {
  name: string;
  state: string;
  explanation: string;
  metrics: MarketBriefingMetric[];
}

export interface MarketBriefingSnapshot {
  scope: string;
  approach: 'Aggressive' | 'Normal' | 'Cautious' | 'Defensive';
  confidence: 'High' | 'Medium' | 'Low';
  oneLineSummary: string;
  reason: string;
  keyPositives: MarketBriefingHighlight[];
  keyRisks: MarketBriefingHighlight[];
  dimensions: MarketBriefingDimension[];
  rawMetrics: Record<string, unknown>;
  dataDate: string;
  universeSize: number;
  sectorCoverage: number;
  lastRefreshTime: string;
}
