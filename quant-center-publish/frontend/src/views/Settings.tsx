import { useEffect, useState } from 'react';
import { settingsService } from '../services/settingsService';
import { UserSettings } from '../types';

const Settings = () => {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await settingsService.getSettings();
        setSettings(data);
      } catch {
        setError('Failed to load settings.');
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleUpdate = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      await settingsService.updateSettings(settings);
      alert('Settings updated successfully!');
    } catch {
      setError('Failed to save settings.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-slate-400">Loading settings...</div>;
  if (error) return <div className="p-8 text-red-500">{error}</div>;

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>
      {settings && (
        <div className="bg-slate-900 p-6 rounded-lg border border-slate-800 space-y-6">
          <div className="flex items-center justify-between">
            <span className="text-slate-300">Theme</span>
            <select 
              className="bg-slate-800 p-2 rounded border border-slate-700"
              value={settings.theme}
              onChange={(e) => setSettings({...settings, theme: e.target.value as 'dark' | 'light'})}
            >
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-slate-300">Enable Notifications</span>
            <input 
              type="checkbox" 
              checked={settings.notificationsEnabled}
              onChange={(e) => setSettings({...settings, notificationsEnabled: e.target.checked})}
            />
          </div>

          <button 
            onClick={handleUpdate}
            disabled={saving}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded transition"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      )}
    </div>
  );
};

export default Settings;