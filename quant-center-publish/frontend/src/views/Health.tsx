import { useEffect, useState } from 'react';
import { healthService } from '../services/healthService';
import { HealthStatus, SystemHealth } from '../types';

const StatusBadge = ({ status }: { status: string }) => {
  const colors = {
    healthy: 'bg-emerald-500',
    warning: 'bg-amber-500',
    offline: 'bg-red-500'
  };
  
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${colors[status as keyof typeof colors]}`} />
      <span className="capitalize text-slate-300 text-sm">{status}</span>
    </div>
  );
};

const Health = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const data = await healthService.getSystemHealth();
        setHealth(data);
      } catch {
        setError('Failed to load system health data.');
      } finally {
        setLoading(false);
      }
    };
    fetchHealth();
  }, []);

  if (loading) return <div className="p-8 text-slate-400">Loading system status...</div>;
  if (error) return <div className="p-8 text-red-500">{error}</div>;

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6 text-slate-100">System Health</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {health &&
          Object.entries(health).map(([key, status]) => (
            <div key={key} className="bg-slate-900 p-6 rounded-sm border border-slate-800">
              <h3 className="text-slate-400 text-xs font-semibold uppercase mb-3">{key}</h3>
              <StatusBadge status={status as HealthStatus} />
            </div>
          ))}
      </div>
    </div>
  );
};

export default Health;