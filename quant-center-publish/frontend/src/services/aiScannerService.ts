import api from './api';
import {
  AddPaperTradeRequest,
  AIScannerActionResult,
  AIScannerSnapshot,
  ExitPaperTradeRequest,
} from '../types/aiScanner';

export const aiScannerService = {
  getSnapshot: async (): Promise<AIScannerSnapshot> => {
    const { data } = await api.get<AIScannerSnapshot>('/ai-scanner');
    return data;
  },

  rescan: async (): Promise<AIScannerSnapshot> => {
    const { data } = await api.post<AIScannerSnapshot>('/ai-scanner/rescan');
    return data;
  },

  addPaperTrade: async (body: AddPaperTradeRequest): Promise<AIScannerActionResult> => {
    const { data } = await api.post<AIScannerActionResult>('/ai-scanner/paper-trades', body);
    return data;
  },

  exitPaperTrade: async (
    ticker: string,
    body: ExitPaperTradeRequest,
  ): Promise<AIScannerActionResult> => {
    const { data } = await api.post<AIScannerActionResult>(
      `/ai-scanner/paper-trades/${encodeURIComponent(ticker)}/exit`,
      body,
    );
    return data;
  },
};
