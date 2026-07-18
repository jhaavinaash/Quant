import api from './api';
import { UserSettings } from '../types';

export const settingsService = {
  getSettings: async (): Promise<UserSettings> => {
    const { data } = await api.get<UserSettings>('/settings');
    return data;
  },
  
  updateSettings: async (settings: UserSettings): Promise<void> => {
    await api.put('/settings', settings);
  }
};