import { useEffect, useState } from 'react';
import { brokerService } from '../services/brokerService';
import { BrokerConnectivityItem } from '../types/broker';

const statusClass = (status: string) => {
  if (status === 'CONNECTED') return 'bg-emerald-900/30 text-emerald-400 border border-emerald-900/50';
  if (status === 'NOT CONFIGURED' || status === 'UNAVAILABLE') {
    return 'bg-slate-800/60 text-slate-400 border border-slate-700/50';
  }
  return 'bg-red-900/30 text-red-400 border border-red-900/50';
};

export const BrokerStatus = () => {
  const [brokers, setBrokers] = useState<BrokerConnectivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    brokerService
      .getConnectivityStatus()
      .then((data) => {
        setBrokers(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        console.error('BrokerStatus load error:', err);
        setError(err.response?.data?.detail || 'Failed to load broker status');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-slate-500 text-sm italic">Loading status...</div>;
  if (error) return <div className="text-red-500 text-sm">{error}</div>;

  return (
    <div className="space-y-3">
      {brokers.length > 0 ? (
        brokers.map((broker) => (
          <div key={broker.name} className="flex justify-between items-center text-sm">
            <span className="text-slate-300 font-medium">{broker.name}</span>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${statusClass(
                broker.status,
              )}`}
            >
              {broker.status}
            </span>
          </div>
        ))
      ) : (
        <div className="text-slate-500 text-sm">Broker status unavailable.</div>
      )}
    </div>
  );
};
