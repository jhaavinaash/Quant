import api from './api';

import { ExecutionActionResult, ExecutionSnapshot } from '../types/execution';



export const executionService = {

  getSnapshot: async (): Promise<ExecutionSnapshot> => {

    const { data } = await api.get<ExecutionSnapshot>('/execution');

    return data;

  },



  submitPending: async (requestId: string): Promise<ExecutionActionResult> => {

    const { data } = await api.post<ExecutionActionResult>(

      `/execution/pending/${encodeURIComponent(requestId)}/submit`,

    );

    return data;

  },



  rejectPending: async (requestId: string, reason?: string): Promise<ExecutionActionResult> => {

    const { data } = await api.post<ExecutionActionResult>(

      `/execution/pending/${encodeURIComponent(requestId)}/reject`,

      { reason: reason ?? 'user rejected via Quant-Center' },

    );

    return data;

  },



  syncOrderStatus: async (force = false): Promise<ExecutionActionResult> => {

    const { data } = await api.post<ExecutionActionResult>('/execution/sync', null, {

      params: { force },

    });

    return data;

  },

};

