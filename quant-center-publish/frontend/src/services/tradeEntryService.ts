import api from './api';
import {
  TradeEntryActionResult,
  TradeEntryAddRequest,
  TradeEntryCloseRequest,
  TradeEntryEditRequest,
  TradeEntrySnapshot,
} from '../types/tradeEntry';

export const tradeEntryService = {
  getSnapshot: async (): Promise<TradeEntrySnapshot> => {
    const { data } = await api.get<TradeEntrySnapshot>('/trade-entry');
    return data;
  },

  discardPendingDeploy: async (): Promise<TradeEntryActionResult> => {
    const { data } = await api.delete<TradeEntryActionResult>('/trade-entry/pending-deploy');
    return data;
  },

  addTrade: async (body: TradeEntryAddRequest): Promise<TradeEntryActionResult> => {
    const { data } = await api.post<TradeEntryActionResult>('/trade-entry', body);
    return data;
  },

  editTrade: async (
    rowIndex: number,
    body: TradeEntryEditRequest,
  ): Promise<TradeEntryActionResult> => {
    const { data } = await api.put<TradeEntryActionResult>(`/trade-entry/${rowIndex}`, body);
    return data;
  },

  closeTrade: async (
    rowIndex: number,
    body: TradeEntryCloseRequest,
  ): Promise<TradeEntryActionResult> => {
    const { data } = await api.post<TradeEntryActionResult>(
      `/trade-entry/${rowIndex}/close`,
      body,
    );
    return data;
  },

  deleteTrade: async (rowIndex: number): Promise<TradeEntryActionResult> => {
    const { data } = await api.delete<TradeEntryActionResult>(`/trade-entry/${rowIndex}`);
    return data;
  },
};
