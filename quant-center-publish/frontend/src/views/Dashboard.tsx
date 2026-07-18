import { useCallback, useEffect, useState } from 'react';
import { BrokerStatus } from '../components/BrokerStatus';
import { EngineStatus } from '../components/EngineStatus';
import { dashboardService } from '../services/dashboardService';
import { ControlResult, DashboardSnapshot } from '../types';

const fmtInr = (value: number, signed = true) => {
  const sign = signed && value > 0 ? '+' : '';
  return `${sign}₹${Math.round(value).toLocaleString('en-IN')}`;
};

const pnlColor = (value: number) =>
  value >= 0 ? 'text-emerald-400' : 'text-red-400';

const winRateColor = (value: number) =>
  value >= 50 ? 'text-emerald-400' : value >= 35 ? 'text-amber-400' : 'text-red-400';

const cagrColor = (value?: number | null) => {
  if (value == null || Number.isNaN(value)) return 'text-slate-500';
  if (value >= 25) return 'text-emerald-400';
  if (value >= 12) return 'text-sky-400';
  if (value >= 0) return 'text-amber-400';
  return 'text-red-400';
};

const controlBannerClass = (kind: ControlResult['kind']) => {
  if (kind === 'error') return 'border-red-500/40 bg-red-500/10 text-red-300';
  if (kind === 'warning') return 'border-amber-500/40 bg-amber-500/10 text-amber-200';
  return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200';
};

const KpiCard = ({
  label,
  value,
  sub,
  valueClass = 'text-slate-100',
  accent = 'border-slate-600',
}: {
  label: string;
  value: string;
  sub?: string;
  valueClass?: string;
  accent?: string;
}) => (
  <div className={`rounded-lg border border-slate-800 bg-slate-900 p-4 border-t-2 ${accent}`}>
    <div className="text-[11px] uppercase tracking-wider text-slate-500 font-medium mb-1">
      {label}
    </div>
    <div className={`text-xl font-semibold ${valueClass}`}>{value}</div>
    {sub ? <div className="text-xs text-slate-500 mt-1">{sub}</div> : null}
  </div>
);

const Dashboard = () => {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [controlResult, setControlResult] = useState<ControlResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    try {
      const [dashboardData, lastResult] = await Promise.all([
        dashboardService.getDashboard(),
        dashboardService.getControlResult(),
      ]);
      setSnapshot(dashboardData);
      setControlResult(lastResult);
      setError(null);
    } catch {
      setError('Failed to load dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const runAction = async (
    key: string,
    action: () => Promise<ControlResult>,
    refreshAfter = true,
  ) => {
    setActionLoading(key);
    try {
      const result = await action();
      setControlResult(result);
      if (refreshAfter) {
        const dashboardData = await dashboardService.getDashboard();
        setSnapshot(dashboardData);
      }
    } catch {
      setControlResult({
        kind: 'error',
        main: 'Action failed. Check backend logs.',
      });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <div className="p-8 text-slate-400">Loading dashboard...</div>;
  if (error || !snapshot) return <div className="p-8 text-red-500">{error ?? 'No data'}</div>;

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Quant Control Center</h1>
          <p className="text-sm text-slate-500 mt-1">{snapshot.timestamp}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={actionLoading !== null}
            onClick={() => runAction('refresh', dashboardService.refreshData)}
            className="rounded-md border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            {actionLoading === 'refresh' ? 'Refreshing…' : 'Refresh Data'}
          </button>
          <button
            type="button"
            disabled={actionLoading !== null}
            onClick={() => runAction('engines', dashboardService.runEngines, false)}
            className="rounded-md border border-sky-700/50 bg-sky-950/40 px-4 py-2 text-sm font-medium text-sky-300 hover:bg-sky-900/40 disabled:opacity-50"
          >
            {actionLoading === 'engines' ? 'Running…' : 'Run Engines'}
          </button>
          <button
            type="button"
            disabled={actionLoading !== null}
            onClick={() => runAction('s1', dashboardService.runS1, false)}
            className="rounded-md border border-violet-700/50 bg-violet-950/40 px-4 py-2 text-sm font-medium text-violet-300 hover:bg-violet-900/40 disabled:opacity-50"
          >
            {actionLoading === 's1' ? 'Running…' : 'Run S1 (3:15 PM)'}
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-3 rounded-lg border border-slate-800 bg-slate-900 p-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 flex-1">
          {snapshot.marketIndices.map((index) => (
            <div key={index.name} className="min-w-0">
              <div className="text-[11px] uppercase tracking-wider text-slate-500">{index.name}</div>
              <div className="text-lg font-semibold text-slate-100">
                {index.price != null ? index.price.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—'}
              </div>
              <div
                className={`text-xs font-medium ${
                  (index.changePct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                }`}
              >
                {index.changePct != null ? `${index.changePct >= 0 ? '+' : ''}${index.changePct.toFixed(2)}%` : '—'}
              </div>
            </div>
          ))}
        </div>
        <div className="text-sm text-slate-400 lg:text-right">
          <div className="flex items-center gap-2 justify-start lg:justify-end">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                snapshot.marketOpen ? 'bg-emerald-400' : 'bg-slate-500'
              }`}
            />
            <span className="font-medium text-slate-300">
              {snapshot.marketOpen ? 'MARKET OPEN' : 'MARKET CLOSED'}
            </span>
          </div>
          <div className="text-xs text-slate-500 mt-1">{snapshot.refreshLabel}</div>
        </div>
      </div>

      {controlResult ? (
        <div className={`rounded-lg border px-4 py-3 text-sm whitespace-pre-line ${controlBannerClass(controlResult.kind)}`}>
          {controlResult.main}
          {controlResult.hint ? <div className="text-xs mt-2 opacity-80">{controlResult.hint}</div> : null}
        </div>
      ) : null}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7 gap-4">
        <KpiCard
          label="Total P&L"
          value={fmtInr(snapshot.totalPnl)}
          sub="Realized + Unrealized"
          valueClass={pnlColor(snapshot.totalPnl)}
          accent={snapshot.totalPnl >= 0 ? 'border-t-emerald-500/60' : 'border-t-red-500/60'}
        />
        <KpiCard
          label="Realized"
          value={fmtInr(snapshot.realizedPnl)}
          sub={`${snapshot.totalClosed} closed trades`}
          valueClass={pnlColor(snapshot.realizedPnl)}
          accent={snapshot.realizedPnl >= 0 ? 'border-t-emerald-500/60' : 'border-t-red-500/60'}
        />
        <KpiCard
          label="Unrealized"
          value={fmtInr(snapshot.unrealizedPnl)}
          sub={`${snapshot.openPositions} open positions`}
          valueClass={pnlColor(snapshot.unrealizedPnl)}
          accent={snapshot.unrealizedPnl >= 0 ? 'border-t-emerald-500/60' : 'border-t-red-500/60'}
        />
        <KpiCard
          label="Open Positions"
          value={String(snapshot.openPositions)}
          sub="live tracking"
          accent="border-t-sky-500/60"
        />
        <KpiCard
          label="Capital"
          value={fmtInr(snapshot.capitalDeployed, false)}
          sub="outstanding risk"
          valueClass="text-sky-400"
          accent="border-t-sky-500/60"
        />
        <KpiCard
          label="Win Rate"
          value={`${snapshot.winRate.toFixed(1)}%`}
          sub={`${snapshot.totalClosed} samples`}
          valueClass={winRateColor(snapshot.winRate)}
          accent="border-t-amber-500/60"
        />
        <KpiCard
          label="Active Signals"
          value={String(snapshot.activeSignals)}
          sub="in queue"
          valueClass="text-sky-400"
          accent="border-t-sky-500/60"
        />
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 xl:col-span-9 space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            <KpiCard
              label="Portfolio CAGR"
              value={
                snapshot.portfolioCagr != null ? `${snapshot.portfolioCagr >= 0 ? '+' : ''}${snapshot.portfolioCagr.toFixed(1)}%` : '—'
              }
              sub={
                snapshot.portfolioRoc != null && snapshot.portfolioInception
                  ? `ROC ${snapshot.portfolioRoc >= 0 ? '+' : ''}${snapshot.portfolioRoc.toFixed(1)}% · since ${snapshot.portfolioInception}`
                  : 'awaiting data'
              }
              valueClass={cagrColor(snapshot.portfolioCagr)}
              accent="border-t-violet-500/60"
            />
            {snapshot.engineCagrs.map((card) => (
              <KpiCard
                key={card.engine}
                label={`${card.engine} CAGR`}
                value={card.cagr != null ? `${card.cagr >= 0 ? '+' : ''}${card.cagr.toFixed(1)}%` : '—'}
                sub={card.subtitle}
                valueClass={cagrColor(card.cagr)}
                accent="border-t-slate-600"
              />
            ))}
          </div>
          <p className="text-xs text-slate-500">
            CAGR = annualised return on peak daily deployed capital (EntryPrice × Qty, summed across
            all live positions each day). ROC is the raw period return on that base.
          </p>
        </div>

        <div className="col-span-12 xl:col-span-3 space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-800 text-sm font-medium text-slate-300">
              Broker Status
            </div>
            <div className="p-4">
              <BrokerStatus />
            </div>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-800 text-sm font-medium text-slate-300">
              Engine Status
            </div>
            <div className="p-4">
              <EngineStatus />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
