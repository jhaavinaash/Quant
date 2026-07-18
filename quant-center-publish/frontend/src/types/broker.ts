export interface BrokerConnectivityItem {
  name: string;
  status: string;
}

export interface ProductionBrokerCard {
  name: string;
  displayName: string;
  status: string;
  configured: boolean;
  userName?: string | null;
  userId?: string | null;
  email?: string | null;
  availableCash?: number | null;
  error?: string | null;
}

export interface ProductionBrokerSummary {
  connectedCount: number;
  totalCount: number;
  brokers: ProductionBrokerCard[];
}

export interface ProductionBrokerConnectResult {
  broker: string;
  success: boolean;
  status: string;
  message: string;
}

export interface ProductionBrokerConnectAllResult {
  results: ProductionBrokerConnectResult[];
  connectedCount: number;
  totalCount: number;
}
