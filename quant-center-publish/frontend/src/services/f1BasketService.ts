import api from './api';
import { BasketActionResult, BasketDeployConfirmation, DeploySelectedRequest, F1BasketSnapshot } from '../types/f1Basket';

export const f1BasketService = {
  getSnapshot: async (): Promise<F1BasketSnapshot> => {
    const { data } = await api.get<F1BasketSnapshot>('/f1-basket/current');
    return data;
  },

  createPreview: async (capital = 200000): Promise<F1BasketSnapshot> => {
    const { data } = await api.post<F1BasketSnapshot>('/f1-basket/preview', { capital });
    return data;
  },

  rebuildPreview: async (capital = 200000): Promise<F1BasketSnapshot> => {
    const { data } = await api.post<F1BasketSnapshot>('/f1-basket/preview/rebuild', { capital });
    return data;
  },

  getDeployConfirmation: async (basketId: string): Promise<BasketDeployConfirmation> => {
    const { data } = await api.get<BasketDeployConfirmation>(
      `/f1-basket/deploy/confirmation/${basketId}`
    );
    return data;
  },

  deployBasket: async (basketId: string): Promise<BasketActionResult> => {
    const { data } = await api.post<BasketActionResult>('/f1-basket/deploy', { basketId });
    return data;
  },

  deploySelected: async (body: DeploySelectedRequest): Promise<BasketActionResult> => {
    const { data } = await api.post<BasketActionResult>('/f1-basket/deploy-selected', body);
    return data;
  },

  syncBasket: async (basketId: string): Promise<BasketActionResult> => {
    const { data } = await api.post<BasketActionResult>('/f1-basket/sync', { basketId });
    return data;
  },

  retryFailed: async (basketId: string): Promise<BasketActionResult> => {
    const { data } = await api.post<BasketActionResult>('/f1-basket/retry-failed', { basketId });
    return data;
  },

  syncValuation: async (basketId: string): Promise<BasketActionResult> => {
    const { data } = await api.post<BasketActionResult>('/f1-basket/valuation/sync', { basketId });
    return data;
  },

  manualExit: async (basketId: string): Promise<BasketActionResult> => {
    const { data } = await api.post<BasketActionResult>('/f1-basket/manual-exit', { basketId });
    return data;
  },

  retryFailedExits: async (basketId: string): Promise<BasketActionResult> => {
    const { data } = await api.post<BasketActionResult>('/f1-basket/retry-failed-exits', { basketId });
    return data;
  },
};
