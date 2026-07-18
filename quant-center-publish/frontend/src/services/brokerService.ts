import api from './api';
import {
  BrokerConnectivityItem,
  ProductionBrokerConnectAllResult,
  ProductionBrokerConnectResult,
  ProductionBrokerSummary,
} from '../types/broker';

export const brokerService = {
  getProductionBrokers: async (): Promise<ProductionBrokerSummary> => {
    const { data } = await api.get<ProductionBrokerSummary>('/brokers/production');
    return data;
  },

  connectProductionBroker: async (brokerName: string): Promise<ProductionBrokerConnectResult> => {
    const { data } = await api.post<ProductionBrokerConnectResult>(
      `/brokers/production/${brokerName}/connect`,
    );
    return data;
  },

  connectAllProductionBrokers: async (): Promise<ProductionBrokerConnectAllResult> => {
    const { data } = await api.post<ProductionBrokerConnectAllResult>('/brokers/production/connect-all');
    return data;
  },

  getConnectivityStatus: async (): Promise<BrokerConnectivityItem[]> => {
    const { data } = await api.get<BrokerConnectivityItem[]>('/dashboard/broker-status');
    return data;
  },
};
