import api from './api';
import { EngineStatus } from '../types/engine';

export const engineService = {
  getStatuses: async (): Promise<EngineStatus[]> => {
    // Corrected path to /engines/status; base URL /api/v1 is handled by api.ts
    const response = await api.get<EngineStatus[]>('/engines/status');
    return response.data;
  }
};