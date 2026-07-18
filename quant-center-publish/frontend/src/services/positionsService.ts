import api from './api';
import { Position, PositionExitReason, PositionExitResult } from '../types';

/**
 * PositionsService
 * Thin wrapper for fetching current trading positions and broker-backed exits.
 */
export const positionsService = {
  /**
   * Fetch all currently open positions.
   */
  getPositions: async (): Promise<Position[]> => {
    const response = await api.get<Position[]>('/positions');
    return response.data;
  },

  requestExit: async (
    tradeKey: string,
    exitReason: PositionExitReason,
  ): Promise<PositionExitResult> => {
    const { data } = await api.post<PositionExitResult>(
      `/positions/${encodeURIComponent(tradeKey)}/exit`,
      { exitReason },
    );
    return data;
  },

  syncExits: async (force = false): Promise<PositionExitResult> => {
    const { data } = await api.post<PositionExitResult>('/positions/sync', null, {
      params: { force },
    });
    return data;
  },
};
