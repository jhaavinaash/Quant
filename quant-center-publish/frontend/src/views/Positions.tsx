import { useCallback, useEffect, useMemo, useState } from 'react';
import { executionService } from '../services/executionService';
import { positionsService } from '../services/positionsService';
import { Position, PositionExitReason, PositionExitResult } from '../types';
import { ExecutionSnapshot } from '../types/execution';

const EXIT_REASONS: PositionExitReason[] = ['Manual', 'SL', 'TP', 'Strategy Exit'];

const displayText = (value?: string | null) => (value?.trim() ? value : '—');

const displayNumber = (value?: number | null, digits = 2) =>
  value != null ? value.toFixed(digits) : '—';

type StatusFilter =
  | 'all'
  | 'sl-breached'
  | 'near-sl'
  | 'watch-sl'
  | 'near-target'
  | 'profit'
  | 'hold';

const STATUS_FILTERS: {
  id: StatusFilter;
  label: string;
  match: (status: string) => boolean;
  activeClass: string;
  inactiveClass: string;
  countActiveClass: string;
  countInactiveClass: string;
}[] = [
  {
    id: 'all',
    label: 'All',
    match: () => true,
    activeClass: 'border-slate-400 bg-slate-700/90 text-slate-100',
    inactiveClass:
      'border-slate-600 bg-slate-900 text-slate-300 hover:border-slate-500 hover:bg-slate-800',
    countActiveClass: 'text-slate-100',
    countInactiveClass: 'text-slate-400',
  },
  {
    id: 'sl-breached',
    label: 'SL Breached',
    match: (s) => s.includes('SL BREACHED'),
    activeClass: 'border-red-500/80 bg-red-500/20 text-red-300',
    inactiveClass:
      'border-red-500/35 bg-slate-900 text-red-400/90 hover:border-red-500/55 hover:bg-red-500/10',
    countActiveClass: 'text-red-200',
    countInactiveClass: 'text-red-400/80',
  },
  {
    id: 'near-sl',
    label: 'Near SL',
    match: (s) => s.includes('Near SL'),
    activeClass: 'border-amber-500/80 bg-amber-500/20 text-amber-300',
    inactiveClass:
      'border-amber-500/35 bg-slate-900 text-amber-400/90 hover:border-amber-500/55 hover:bg-amber-500/10',
    countActiveClass: 'text-amber-200',
    countInactiveClass: 'text-amber-400/80',
  },
  {
    id: 'watch-sl',
    label: 'Watch SL',
    match: (s) => s.includes('Watch SL'),
    activeClass: 'border-amber-400/70 bg-amber-400/15 text-amber-200',
    inactiveClass:
      'border-amber-400/30 bg-slate-900 text-amber-300/90 hover:border-amber-400/50 hover:bg-amber-400/10',
    countActiveClass: 'text-amber-100',
    countInactiveClass: 'text-amber-300/80',
  },
  {
    id: 'near-target',
    label: 'Near Target',
    match: (s) => s.includes('Near Target'),
    activeClass: 'border-emerald-500/80 bg-emerald-500/20 text-emerald-300',
    inactiveClass:
      'border-emerald-500/35 bg-slate-900 text-emerald-400/90 hover:border-emerald-500/55 hover:bg-emerald-500/10',
    countActiveClass: 'text-emerald-200',
    countInactiveClass: 'text-emerald-400/80',
  },
  {
    id: 'profit',
    label: 'Profit',
    match: (s) => s.includes('Profit'),
    activeClass: 'border-emerald-400/70 bg-emerald-400/15 text-emerald-200',
    inactiveClass:
      'border-emerald-400/30 bg-slate-900 text-emerald-300/90 hover:border-emerald-400/50 hover:bg-emerald-400/10',
    countActiveClass: 'text-emerald-100',
    countInactiveClass: 'text-emerald-300/80',
  },
  {
    id: 'hold',
    label: 'Hold',
    match: (s) => s.includes('Hold'),
    activeClass: 'border-slate-500/80 bg-slate-600/30 text-slate-200',
    inactiveClass:
      'border-slate-600 bg-slate-900 text-slate-400 hover:border-slate-500 hover:bg-slate-800',
    countActiveClass: 'text-slate-100',
    countInactiveClass: 'text-slate-500',
  },
];

const urgencyRank = (status?: string | null) => {
  const value = status?.trim() ?? '';
  if (value.includes('SL BREACHED')) return 0;
  if (value.includes('Near SL')) return 1;
  if (value.includes('Near Target')) return 2;
  if (value.includes('Watch SL')) return 3;
  if (value.includes('Profit')) return 4;
  if (value.includes('Hold')) return 5;
  return 6;
};

const statusClass = (status?: string | null) => {
  const value = status?.trim() ?? '';
  if (value.includes('BREACHED')) return 'text-red-400 font-medium';
  if (value.includes('Near SL')) return 'text-amber-400';
  if (value.includes('Watch SL')) return 'text-amber-300';
  if (value.includes('Target')) return 'text-emerald-400';
  if (value.includes('Profit')) return 'text-emerald-300';
  return 'text-slate-400';
};

const exitStatusClass = (status?: string | null) => {
  const value = status?.trim().toUpperCase() ?? '';
  if (value.includes('SUBMITTED') || value.includes('PENDING')) return 'text-amber-300 font-medium';
  if (value.includes('PARTIAL')) return 'text-amber-400';
  if (value.includes('COMPLETE')) return 'text-emerald-400';
  if (value.includes('REJECT') || value.includes('FAIL')) return 'text-red-400';
  return 'text-slate-400';
};

const isZerodhaConnected = (snapshot: ExecutionSnapshot | null) => {
  const zerodha = snapshot?.brokerState.find((broker) =>
    broker.name.toUpperCase().includes('ZERODHA'),
  );
  return zerodha?.status === 'CONNECTED';
};

const stickyInstrumentClass =
  'sticky left-0 z-10 min-w-[140px] bg-slate-900 border-r border-slate-800';
const stickyEngineClass =
  'sticky left-[140px] z-10 min-w-[88px] bg-slate-900 border-r border-slate-800 shadow-[4px_0_8px_-2px_rgba(0,0,0,0.45)]';
const stickyHeaderClass = 'z-20';

type ConfirmExitState = {
  position: Position;
  exitReason: PositionExitReason;
};

const Positions = () => {
  const [positions, setPositions] = useState<Position[]>([]);
  const [execution, setExecution] = useState<ExecutionSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [actionMessage, setActionMessage] = useState<PositionExitResult | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [confirmExit, setConfirmExit] = useState<ConfirmExitState | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [posData, execData] = await Promise.all([
        positionsService.getPositions(),
        executionService.getSnapshot(),
      ]);
      setPositions(posData);
      setExecution(execData);
      setError(null);
    } catch {
      setError('Failed to load positions.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const brokerConnected = isZerodhaConnected(execution);

  const runAction = async (key: string, action: () => Promise<PositionExitResult>) => {
    setBusyKey(key);
    setActionMessage(null);
    try {
      const result = await action();
      setActionMessage(result);
      await loadData();
    } catch {
      setActionMessage({
        success: false,
        message: 'Request failed. Check network and try again.',
      });
    } finally {
      setBusyKey(null);
    }
  };

  const handleExitConfirmed = async () => {
    if (!confirmExit) return;
    const { position, exitReason } = confirmExit;
    setConfirmExit(null);
    await runAction(`exit-${position.id}`, () =>
      positionsService.requestExit(position.id, exitReason),
    );
  };

  const handleSync = async () => {
    await runAction('sync', () => positionsService.syncExits(false));
  };

  const statusCounts = useMemo(() => {
    const counts = Object.fromEntries(STATUS_FILTERS.map(({ id }) => [id, 0])) as Record<
      StatusFilter,
      number
    >;
    counts.all = positions.length;

    for (const position of positions) {
      const status = position.status?.trim() ?? '';
      for (const filter of STATUS_FILTERS) {
        if (filter.id !== 'all' && filter.match(status)) {
          counts[filter.id] += 1;
        }
      }
    }

    return counts;
  }, [positions]);

  const visiblePositions = useMemo(() => {
    const activeFilter =
      STATUS_FILTERS.find((filter) => filter.id === statusFilter) ?? STATUS_FILTERS[0];

    return [...positions]
      .filter((position) => activeFilter.match(position.status?.trim() ?? ''))
      .sort((a, b) => urgencyRank(a.status) - urgencyRank(b.status));
  }, [positions, statusFilter]);

  if (loading) return <div className="p-8 text-slate-400">Loading positions...</div>;
  if (error) return <div className="p-8 text-red-500">{error}</div>;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
        <div>
          <h1 className="text-2xl font-bold mb-2 text-slate-100">Positions</h1>
          <p className="text-slate-400 text-base">{positions.length} open positions</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span
            className={`text-sm font-medium ${
              brokerConnected ? 'text-emerald-400' : 'text-red-400'
            }`}
          >
            Zerodha {brokerConnected ? 'CONNECTED' : 'NOT CONNECTED'}
          </span>
          <button
            type="button"
            onClick={handleSync}
            disabled={busyKey === 'sync'}
            className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-700 disabled:opacity-50"
          >
            {busyKey === 'sync' ? 'Syncing…' : 'Sync Exits'}
          </button>
        </div>
      </div>

      {!brokerConnected && (
        <p className="mb-4 text-sm text-amber-300/90">
          Broker-backed exit requires Zerodha CONNECTED. Connect on the Brokers page before
          submitting exits.
        </p>
      )}

      {actionMessage && (
        <div
          className={`mb-4 rounded-lg border px-4 py-3 text-sm ${
            actionMessage.success
              ? 'border-emerald-800/60 bg-emerald-900/20 text-emerald-300'
              : 'border-red-800/60 bg-red-900/20 text-red-300'
          }`}
        >
          {actionMessage.message}
          {actionMessage.exitStatusLabel ? ` · ${actionMessage.exitStatusLabel}` : ''}
        </div>
      )}

      <div className="flex flex-wrap gap-2.5 mb-5">
        {STATUS_FILTERS.map((filter) => {
          const active = statusFilter === filter.id;
          return (
            <button
              key={filter.id}
              type="button"
              onClick={() => setStatusFilter(filter.id)}
              className={`rounded-lg border px-4 py-2 text-sm font-semibold transition-colors ${
                active ? filter.activeClass : filter.inactiveClass
              }`}
            >
              {filter.label}
              <span
                className={`ml-2 text-sm font-bold ${
                  active ? filter.countActiveClass : filter.countInactiveClass
                }`}
              >
                {statusCounts[filter.id]}
              </span>
            </button>
          );
        })}
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="min-w-max w-full border-separate border-spacing-0 bg-slate-900 text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-slate-400 whitespace-nowrap">
              <th className={`p-4 ${stickyInstrumentClass} ${stickyHeaderClass}`}>Instrument</th>
              <th className={`p-4 ${stickyEngineClass} ${stickyHeaderClass}`}>Engine</th>
              <th className="p-4">Entry Date</th>
              <th className="p-4">Qty</th>
              <th className="p-4">Avg Price</th>
              <th className="p-4">Current</th>
              <th className="p-4">Return %</th>
              <th className="p-4">PnL</th>
              <th className="p-4">SL</th>
              <th className="p-4">Target</th>
              <th className="p-4">Hold Days</th>
              <th className="p-4">Status</th>
              <th className="p-4">Exit</th>
              <th className="p-4">Technical State</th>
              <th className="p-4">Sector State</th>
              <th className="p-4">Exit Rule</th>
              <th className="p-4">Action</th>
            </tr>
          </thead>
          <tbody>
            {visiblePositions.length > 0 ? (
              visiblePositions.map((position) => {
                const exitActive = position.exitStatus?.trim();
                const canExit = position.canExit !== false && !exitActive;
                const exitDisabled = !brokerConnected || !canExit || busyKey === `exit-${position.id}`;

                return (
                  <tr key={position.id} className="border-b border-slate-800 whitespace-nowrap">
                    <td className={`p-4 font-medium ${stickyInstrumentClass}`}>
                      {position.instrument}
                    </td>
                    <td className={`p-4 ${stickyEngineClass}`}>{displayText(position.engine)}</td>
                    <td className="p-4">{displayText(position.entryDate)}</td>
                    <td className="p-4">{position.quantity}</td>
                    <td className="p-4">{position.avgPrice.toFixed(2)}</td>
                    <td className="p-4">{displayNumber(position.currentPrice)}</td>
                    <td className="p-4">
                      {position.returnPct != null ? `${position.returnPct.toFixed(2)}%` : '—'}
                    </td>
                    <td
                      className={`p-4 ${position.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}
                    >
                      {position.pnl.toFixed(2)}
                    </td>
                    <td className="p-4">{displayNumber(position.sl)}</td>
                    <td className="p-4">{displayNumber(position.target)}</td>
                    <td className="p-4">{displayNumber(position.holdDays, 0)}</td>
                    <td className={`p-4 ${statusClass(position.status)}`}>
                      {displayText(position.status)}
                    </td>
                    <td className={`p-4 ${exitStatusClass(position.exitStatus)}`}>
                      {displayText(position.exitStatus)}
                    </td>
                    <td className="p-4">{displayText(position.technicalState)}</td>
                    <td className="p-4">{displayText(position.sectorState)}</td>
                    <td className="p-4">{displayText(position.exitRule)}</td>
                    <td className="p-4">
                      <button
                        type="button"
                        disabled={exitDisabled}
                        onClick={() =>
                          setConfirmExit({ position, exitReason: 'Manual' })
                        }
                        title={
                          !brokerConnected
                            ? 'Zerodha must be CONNECTED'
                            : !canExit
                              ? 'Exit already in progress'
                              : 'Submit broker SELL exit'
                        }
                        className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-300 hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Exit
                      </button>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={17} className="p-8 text-center text-slate-500 italic">
                  {positions.length > 0 ? 'No positions match this filter' : 'No open positions'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {confirmExit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
            <h2 className="text-lg font-bold text-slate-100 mb-4">Confirm Position Exit</h2>
            <p className="text-sm text-slate-400 mb-4">
              Submit a broker SELL order for this exact open trade. The position closes only after
              a COMPLETE SELL fill is confirmed.
            </p>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm mb-5">
              <dt className="text-slate-500">Ticker</dt>
              <dd className="text-slate-100 font-medium">{confirmExit.position.instrument}</dd>
              <dt className="text-slate-500">Engine</dt>
              <dd className="text-slate-100">{displayText(confirmExit.position.engine)}</dd>
              <dt className="text-slate-500">Qty</dt>
              <dd className="text-slate-100">{confirmExit.position.quantity}</dd>
              <dt className="text-slate-500">Current Price</dt>
              <dd className="text-slate-100">{displayNumber(confirmExit.position.currentPrice)}</dd>
              <dt className="text-slate-500">P&amp;L</dt>
              <dd
                className={
                  confirmExit.position.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'
                }
              >
                {confirmExit.position.pnl.toFixed(2)}
              </dd>
              <dt className="text-slate-500">SL</dt>
              <dd className="text-slate-100">{displayNumber(confirmExit.position.sl)}</dd>
              <dt className="text-slate-500">Target</dt>
              <dd className="text-slate-100">{displayNumber(confirmExit.position.target)}</dd>
            </dl>
            <label className="block text-sm text-slate-400 mb-2" htmlFor="exit-reason">
              Exit Reason
            </label>
            <select
              id="exit-reason"
              value={confirmExit.exitReason}
              onChange={(e) =>
                setConfirmExit({
                  ...confirmExit,
                  exitReason: e.target.value as PositionExitReason,
                })
              }
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100 mb-6"
            >
              {EXIT_REASONS.map((reason) => (
                <option key={reason} value={reason}>
                  {reason}
                </option>
              ))}
            </select>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmExit(null)}
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-300 hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExitConfirmed}
                disabled={!brokerConnected}
                className="rounded-lg border border-red-500/50 bg-red-600/80 px-4 py-2 text-sm font-semibold text-white hover:bg-red-600 disabled:opacity-50"
              >
                Submit SELL Exit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Positions;
