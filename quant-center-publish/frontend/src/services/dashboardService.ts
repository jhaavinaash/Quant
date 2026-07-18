import api from './api';
import { ControlResult, DashboardSnapshot } from '../types';

export const dashboardService = {
  getDashboard: async (): Promise<DashboardSnapshot> => {
    const { data } = await api.get<DashboardSnapshot>('/dashboard');
    return data;
  },

  getControlResult: async (): Promise<ControlResult | null> => {
    const { data } = await api.get<ControlResult | null>('/dashboard/control-result');
    return data;
  },

  refreshData: async (): Promise<ControlResult> => {
    const { data } = await api.post<ControlResult>('/dashboard/refresh');
    return data;
  },

  runEngines: async (): Promise<ControlResult> => {
    const { data } = await api.post<ControlResult>('/dashboard/run-engines');
    return data;
  },

  runS1: async (): Promise<ControlResult> => {
    const { data } = await api.post<ControlResult>('/dashboard/run-s1');
    return data;
  },
};
