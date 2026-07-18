import api from './api';
import { InstrumentPaginatedResponse } from '../types';

export const instrumentService = {
  /**
   * Fetches paginated instruments.
   * Maps to: GET /instrument/
   */
  getInstruments: async (page: number = 1, size: number = 20): Promise<InstrumentPaginatedResponse> => {
    const response = await api.get<InstrumentPaginatedResponse>('/instrument/', {
      params: { page, size }
    });
    return response.data;
  }
};