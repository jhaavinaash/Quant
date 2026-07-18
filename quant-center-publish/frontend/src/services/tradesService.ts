import api from './api';
import { TradesSnapshot } from '../types/trades';

export const tradesService = {
  getSnapshot: async (): Promise<TradesSnapshot> => {
    const { data } = await api.get<TradesSnapshot>('/trades');
    return data;
  },
};
