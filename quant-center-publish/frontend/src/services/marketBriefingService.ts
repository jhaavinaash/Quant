import api from './api';
import { MarketBriefingSnapshot } from '../types/marketBriefing';

export const marketBriefingService = {
  getSnapshot: async (refresh = false): Promise<MarketBriefingSnapshot> => {
    const { data } = await api.get<MarketBriefingSnapshot>('/market-briefing', {
      params: refresh ? { refresh: true } : undefined,
    });
    return data;
  },
};
