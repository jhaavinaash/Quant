import api from './api';
import { SystemHealth } from '../types';

export const healthService = {
  getSystemHealth: async (): Promise<SystemHealth> => {
    const { data } = await api.get<SystemHealth>('http://127.0.0.1:8000/health');
    return data;
  }
};