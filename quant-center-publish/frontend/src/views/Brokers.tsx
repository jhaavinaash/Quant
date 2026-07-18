import { useCallback, useEffect, useState } from 'react';
import { brokerService } from '../services/brokerService';
import { ProductionBrokerCard, ProductionBrokerSummary } from '../types/broker';

const fmtInr = (value?: number | null) =>
  value != null ? `₹${Math.round(value).toLocaleString('en-IN')}` : '—';

const statusClass = (status: string) => {
  if (status === 'CONNECTED') return 'text-emerald-400';
  if (status === 'NOT CONFIGURED' || status === 'UNAVAILABLE') return 'text-slate-400';
  return 'text-red-400';
};

const statusBadgeClass = (status: string) => {
  if (status === 'CONNECTED') {
    return 'bg-emerald-900/30 text-emerald-400 border border-emerald-900/50';
  }
  if (status === 'NOT CONFIGURED' || status === 'UNAVAILABLE') {
    return 'bg-slate-800/60 text-slate-400 border border-slate-700/50';
  }
  return 'bg-red-900/30 text-red-400 border border-red-900/50';
};

const Brokers = () => {
  const [summary, setSummary] = useState<ProductionBrokerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadBrokers = useCallback(async () => {
    try {
      const data = await brokerService.getProductionBrokers();
      setSummary(data);
      setError(null);
    } catch {
      setError('Failed to load brokers.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBrokers();
  }, [loadBrokers]);

  const runConnect = async (brokerName: string) => {
    setActionLoading(brokerName);
    setMessage(null);
    try {
      const result = await brokerService.connectProductionBroker(brokerName);
      setMessage({
        kind: result.success ? 'success' : 'error',
        text: result.message || `${brokerName}: ${result.status}`,
      });
      await loadBrokers();
    } catch {
      setMessage({ kind: 'error', text: 'Connection request failed.' });
    } finally {
      setActionLoading(null);
    }
  };

  const runConnectAll = async () => {
    setActionLoading('all');
    setMessage(null);
    try {
      const result = await brokerService.connectAllProductionBrokers();
      const lines = result.results.map((item) => `${item.broker}: ${item.message || item.status}`);
      setMessage({
        kind: result.connectedCount > 0 ? 'success' : 'error',
        text: lines.join(' · ') || 'No brokers connected.',
      });
      await loadBrokers();
    } catch {
      setMessage({ kind: 'error', text: 'Connect-all request failed.' });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <div className="p-8 text-slate-400">Loading brokers...</div>;
  if (error || !summary) return <div className="p-8 text-red-500">{error ?? 'No data'}</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Brokers</h1>
          <p className="text-sm text-slate-500 mt-1">
            Production broker connections via Quant execution layer
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={actionLoading !== null}
            onClick={loadBrokers}
            className="rounded-md border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            Refresh
          </button>
          <button
            type="button"
            disabled={actionLoading !== null}
            onClick={runConnectAll}
            className="rounded-md border border-sky-700/50 bg-sky-950/40 px-4 py-2 text-sm text-sky-300 hover:bg-sky-900/40 disabled:opacity-50"
          >
            {actionLoading === 'all' ? 'Connecting…' : 'Connect All'}
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-300">
        <span className="font-semibold text-slate-100">
          {summary.connectedCount}/{summary.totalCount} CONNECTED
        </span>
        <span className="text-slate-500 ml-2">
          {summary.brokers.map((broker) => broker.displayName).join(' · ')}
        </span>
      </div>

      {message ? (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            message.kind === 'success'
              ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200'
              : 'border-red-500/40 bg-red-500/10 text-red-300'
          }`}
        >
          {message.text}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {summary.brokers.map((broker: ProductionBrokerCard) => {
          const connected = broker.status === 'CONNECTED';
          const canConnect = broker.configured && broker.status !== 'NOT CONFIGURED' && !connected;
          return (
            <div
              key={broker.name}
              className="rounded-lg border border-slate-800 bg-slate-900 p-5"
            >
              <div className="flex items-center justify-between gap-3 mb-4">
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-block h-2.5 w-2.5 rounded-full ${
                      connected ? 'bg-emerald-400' : 'bg-slate-500'
                    }`}
                  />
                  <h2 className="text-lg font-semibold text-slate-100">{broker.displayName}</h2>
                </div>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${statusBadgeClass(
                    broker.status,
                  )}`}
                >
                  {broker.status}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                <div>
                  <div className="text-[11px] uppercase tracking-wider text-slate-500">User Name</div>
                  <div className="text-slate-200">{broker.userName ?? '—'}</div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-wider text-slate-500">User ID</div>
                  <div className="text-slate-300">{broker.userId ?? '—'}</div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-wider text-slate-500">Email</div>
                  <div className="text-slate-300">{broker.email ?? '—'}</div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-wider text-slate-500">
                    Available Cash
                  </div>
                  <div className={`font-semibold ${statusClass(broker.status)}`}>
                    {fmtInr(broker.availableCash)}
                  </div>
                </div>
              </div>

              {broker.error ? (
                <div className="text-xs text-amber-300 mb-4">{broker.error}</div>
              ) : null}

              <button
                type="button"
                disabled={!canConnect || actionLoading !== null}
                onClick={() => runConnect(broker.name)}
                className={`rounded-md border px-4 py-2 text-sm font-medium disabled:opacity-50 ${
                  canConnect
                    ? 'border-sky-700/50 bg-sky-950/40 text-sky-300 hover:bg-sky-900/40'
                    : 'border-slate-700 bg-slate-800 text-slate-500'
                }`}
              >
                {actionLoading === broker.name
                  ? 'Connecting…'
                  : connected
                    ? 'Connected'
                    : broker.status === 'NOT CONFIGURED'
                      ? 'Not Configured'
                      : 'Connect'}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Brokers;
