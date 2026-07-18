import { useCallback, useEffect, useMemo, useState } from 'react';
import { tradesService } from '../services/tradesService';
import { ClosedTradeRow, TradesOutcomeFilter, TradesSnapshot } from '../types/trades';

const fmtInr = (value: number, signed = true) => {
  const sign = signed && value > 0 ? '+' : '';
  return `${sign}₹${Math.round(value).toLocaleString('en-IN')}`;
};

const pnlColor = (value?: number | null) => {
  if (value == null) return 'text-slate-400';
  return value >= 0 ? 'text-emerald-400' : 'text-red-400';
};

const winRateColor = (value: number) =>
  value >= 50 ? 'text-emerald-400' : value >= 35 ? 'text-amber-400' : 'text-red-400';

const displayText = (value?: string | null) => (value?.trim() ? value : '—');

const displayNumber = (value?: number | null, digits = 2) =>
  value != null ? value.toFixed(digits) : '—';

const parseExitDate = (value: string) => {
  const parts = value.split('-');
  if (parts.length !== 3) return 0;
  const [day, month, year] = parts.map(Number);
  return new Date(year, month - 1, day).getTime();
};

const OUTCOME_FILTERS: { id: TradesOutcomeFilter; label: string }[] = [
  { id: 'all', label: 'All trades' },
  { id: 'winners', label: 'Winners' },
  { id: 'losers', label: 'Losers' },
  { id: 'tp', label: 'TP hits' },
  { id: 'sl', label: 'SL hits' },
  { id: 'manual', label: 'Manual exits' },
];

const KpiCard = ({
  label,
  value,
  sub,
  valueClass = 'text-slate-100',
}: {
  label: string;
  value: string;
  sub?: string;
  valueClass?: string;
}) => (
  <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 border-t-2 border-slate-600">
    <div className="text-[11px] uppercase tracking-wider text-slate-500 font-medium mb-1">{label}</div>
    <div className={`text-xl font-semibold ${valueClass}`}>{value}</div>
    {sub ? <div className="text-xs text-slate-500 mt-1">{sub}</div> : null}
  </div>
);

const Trades = () => {
  const [snapshot, setSnapshot] = useState<TradesSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [engineFilter, setEngineFilter] = useState<string>('all');
  const [outcomeFilter, setOutcomeFilter] = useState<TradesOutcomeFilter>('all');

  const loadTrades = useCallback(async () => {
    try {
      const data = await tradesService.getSnapshot();
      setSnapshot(data);
      setError(null);
    } catch {
      setError('Failed to load trades.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTrades();
  }, [loadTrades]);

  const filteredTrades = useMemo(() => {
    if (!snapshot) return [];
    let rows = [...snapshot.trades];

    if (engineFilter !== 'all') {
      rows = rows.filter((row) => row.engine === engineFilter);
    }

    if (outcomeFilter === 'winners') {
      rows = rows.filter((row) => (row.pnl ?? 0) > 0);
    } else if (outcomeFilter === 'losers') {
      rows = rows.filter((row) => (row.pnl ?? 0) < 0);
    } else if (outcomeFilter === 'tp') {
      rows = rows.filter((row) => row.outcome === 'TP');
    } else if (outcomeFilter === 'sl') {
      rows = rows.filter((row) => row.outcome === 'SL');
    } else if (outcomeFilter === 'manual') {
      rows = rows.filter((row) => row.outcome === 'Manual');
    }

    return rows.sort((a, b) => parseExitDate(b.exitDate) - parseExitDate(a.exitDate));
  }, [snapshot, engineFilter, outcomeFilter]);

  if (loading) return <div className="p-8 text-slate-400">Loading trades...</div>;
  if (error || !snapshot) return <div className="p-8 text-red-500">{error ?? 'No data'}</div>;

  const { summary } = snapshot;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Trades</h1>
          <p className="text-sm text-slate-500 mt-1">
            Closed trade book from production trades_log.csv
          </p>
        </div>
        <button
          type="button"
          onClick={loadTrades}
          className="rounded-md border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
        >
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <KpiCard label="Closed Trades" value={String(summary.closedTrades)} />
        <KpiCard
          label="Realized P&L"
          value={fmtInr(summary.realizedPnl)}
          valueClass={pnlColor(summary.realizedPnl)}
        />
        <KpiCard
          label="Win Rate"
          value={`${summary.winRate.toFixed(1)}%`}
          valueClass={winRateColor(summary.winRate)}
          sub={`${summary.closedTrades} samples`}
        />
        <KpiCard label="Winners" value={String(summary.winners)} valueClass="text-emerald-400" />
        <KpiCard label="Losers" value={String(summary.losers)} valueClass="text-red-400" />
      </div>

      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label htmlFor="engine-filter" className="block text-xs text-slate-500 mb-1">
            Engine
          </label>
          <select
            id="engine-filter"
            value={engineFilter}
            onChange={(e) => setEngineFilter(e.target.value)}
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200"
          >
            <option value="all">All engines</option>
            {snapshot.engines.map((engine) => (
              <option key={engine} value={engine}>
                {engine}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="outcome-filter" className="block text-xs text-slate-500 mb-1">
            Outcome / Exit reason
          </label>
          <select
            id="outcome-filter"
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value as TradesOutcomeFilter)}
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200"
          >
            {OUTCOME_FILTERS.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <div className="text-sm text-slate-500 pb-2">
          Showing {filteredTrades.length} of {snapshot.trades.length} closed trades
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="min-w-max w-full bg-slate-900 text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-slate-400 whitespace-nowrap">
              <th className="p-4">Ticker</th>
              <th className="p-4">Engine</th>
              <th className="p-4">Entry Date</th>
              <th className="p-4">Exit Date</th>
              <th className="p-4">Qty</th>
              <th className="p-4">Entry Price</th>
              <th className="p-4">Exit Price</th>
              <th className="p-4">Return %</th>
              <th className="p-4">P&L</th>
              <th className="p-4">Days Held</th>
              <th className="p-4">Exit Reason</th>
              <th className="p-4">Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredTrades.length > 0 ? (
              filteredTrades.map((row: ClosedTradeRow) => (
                <tr key={row.id} className="border-b border-slate-800 whitespace-nowrap">
                  <td className="p-4 font-medium">{displayText(row.ticker)}</td>
                  <td className="p-4">{displayText(row.engine)}</td>
                  <td className="p-4">{displayText(row.entryDate)}</td>
                  <td className="p-4">{displayText(row.exitDate)}</td>
                  <td className="p-4">{row.quantity != null ? Math.round(row.quantity) : '—'}</td>
                  <td className="p-4">{row.entryPrice != null ? `₹${displayNumber(row.entryPrice)}` : '—'}</td>
                  <td className="p-4">{row.exitPrice != null ? `₹${displayNumber(row.exitPrice)}` : '—'}</td>
                  <td className={`p-4 font-medium ${pnlColor(row.returnPct)}`}>
                    {row.returnPct != null ? `${row.returnPct >= 0 ? '+' : ''}${displayNumber(row.returnPct)}%` : '—'}
                  </td>
                  <td className={`p-4 font-semibold ${pnlColor(row.pnl)}`}>
                    {row.pnl != null ? fmtInr(row.pnl) : '—'}
                  </td>
                  <td className="p-4">{row.holdDays ?? '—'}</td>
                  <td className="p-4">{displayText(row.exitReason)}</td>
                  <td className="p-4">{displayText(row.status)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={12} className="p-8 text-center text-slate-500 italic">
                  No closed trades match the selected filters
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Trades;
