import api from './api';
import { F1DeployResult, F1RunResult, F1Snapshot } from '../types/f1';

export const f1Service = {
  getSnapshot: async (): Promise<F1Snapshot> => {
    const { data } = await api.get<F1Snapshot>('/f1');
    return data;
  },

  runF1: async (): Promise<F1RunResult> => {
    const { data } = await api.post<F1RunResult>('/f1/run');
    return data;
  },

  deploy: async (ticker: string): Promise<F1DeployResult> => {
    const { data } = await api.post<F1DeployResult>('/f1/deploy', { ticker });
    return data;
  },
};
