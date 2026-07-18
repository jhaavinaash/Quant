import { useCallback, useEffect, useMemo, useState } from 'react';
import { executionService } from '../services/executionService';
import {
  ExecutionActionResult,
  ExecutionLifecycleFilter,
  ExecutionOrderRow,
  ExecutionSnapshot,
} from '../types/execution';

const displayText = (value?: string | null) => (value?.trim() ? value : '—');

const LIFECYCLE_FILTERS: {
  id: ExecutionLifecycleFilter;
  label: string;
  countKey: keyof ExecutionSnapshot['counts'] | null;
}[] = [
  { id: 'all', label: 'All', countKey: null },
  { id: 'pending', label: 'Pending', countKey: 'pending' },
  { id: 'approved', label: 'Approved', countKey: 'approved' },
  { id: 'submitted', label: 'Submitted', countKey: 'submitted' },
  { id: 'filled', label: 'Filled', countKey: 'filled' },
  { id: 'rejected_failed', label: 'Rejected / Failed', countKey: 'rejectedFailed' },
];

const statusBadgeClass = (status: string) => {
  const value = status.toUpperCase();
  if (value.includes('COMPLETE') || value.includes('APPROVED') || value === 'ATTEMPT') {
    return 'bg-emerald-900/30 text-emerald-400 border border-emerald-900/50';
  }
  if (value.includes('PENDING') || value.includes('PARTIAL')) {
    return 'bg-amber-900/30 text-amber-300 border border-amber-900/50';
  }
  if (value.includes('REJECT') || value.includes('FAIL') || value.includes('ERROR')) {
    return 'bg-red-900/30 text-red-400 border border-red-900/50';
  }
  return 'bg-slate-800/60 text-slate-400 border border-slate-700/50';
};

const brokerStatusClass = (status: string) => {
  if (status === 'CONNECTED') return 'text-emerald-400';
  if (status === 'NOT CONFIGURED' || status === 'UNAVAILABLE') return 'text-slate-400';
  return 'text-red-400';
};

const rowsForFilter = (snapshot: ExecutionSnapshot, filter: ExecutionLifecycleFilter) => {
  if (filter === 'pending') return snapshot.pending;
  if (filter === 'approved') return snapshot.approved;
  if (filter === 'submitted') return snapshot.submitted;
  if (filter === 'filled') return snapshot.filled;
  if (filter === 'rejected_failed') return snapshot.rejectedFailed;
  return [
    ...snapshot.pending,
    ...snapshot.approved,
    ...snapshot.submitted,
    ...snapshot.filled,
    ...snapshot.rejectedFailed,
  ];
};

const countForFilter = (snapshot: ExecutionSnapshot, filter: ExecutionLifecycleFilter) => {
  if (filter === 'all') {
    return (
      snapshot.counts.pending +
      snapshot.counts.approved +
      snapshot.counts.submitted +
      snapshot.counts.filled +
      snapshot.counts.rejectedFailed
    );
  }
  return rowsForFilter(snapshot, filter).length;
};

const isZerodhaConnected = (snapshot: ExecutionSnapshot) => {
  const zerodha = snapshot.brokerState.find((broker) => broker.name.toUpperCase().includes('ZERODHA'));
  return zerodha?.status === 'CONNECTED';
};

const canSyncRow = (row: ExecutionOrderRow) =>
  Boolean(row.brokerOrderId?.trim()) &&
  (row.lifecycle === 'approved' || row.lifecycle === 'submitted' || row.lifecycle === 'filled');

type ConfirmSubmitState = {
  row: ExecutionOrderRow;
};

const Execution = () => {
  const [snapshot, setSnapshot] = useState<ExecutionSnapshot | null>(null);
  const [filter, setFilter] = useState<ExecutionLifecycleFilter>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<ExecutionActionResult | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [confirmSubmit, setConfirmSubmit] = useState<ConfirmSubmitState | null>(null);

  const loadExecution = useCallback(async () => {
    try {
      const data = await executionService.getSnapshot();
      setSnapshot(data);
      setError(null);
    } catch {
      setError('Failed to load execution data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExecution();
  }, [loadExecution]);

  const visibleRows = useMemo(
    () => (snapshot ? rowsForFilter(snapshot, filter) : []),
    [snapshot, filter],
  );

  const brokerConnected = snapshot ? isZerodhaConnected(snapshot) : false;

  const runAction = async (key: string, action: () => Promise<ExecutionActionResult>) => {
    setBusyKey(key);
    setActionMessage(null);
    try {
      const result = await action();
      setActionMessage(result);
      await loadExecution();
    } catch {
      setActionMessage({
        success: false,
        kind: 'error',
        message: 'Request failed. Check network and try again.',
      });
    } finally {
      setBusyKey(null);
    }
  };

  const handleSubmitConfirmed = async () => {
    if (!confirmSubmit) return;
    const { row } = confirmSubmit;
    setConfirmSubmit(null);
    if (!row.requestId) return;
    await runAction(`submit-${row.requestId}`, () => executionService.submitPending(row.requestId!));
  };

  const handleReject = async (row: ExecutionOrderRow) => {
    if (!row.requestId) return;
    await runAction(`reject-${row.requestId}`, () => executionService.rejectPending(row.requestId!));
  };

  const handleSync = async (force = false) => {
    await runAction(force ? 'sync-force' : 'sync', () => executionService.syncOrderStatus(force));
  };

  if (loading) return <div className="p-8 text-slate-400">Loading execution...</div>;
  if (error || !snapshot) return <div className="p-8 text-red-500">{error ?? 'No data'}</div>;

  const zerodha = snapshot.brokerState.find((broker) => broker.name.toUpperCase().includes('ZERODHA'));

  return (
    <div className="space-y-6">
      {confirmSubmit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="submit-order-title"
            className="w-full max-w-md rounded-lg border border-slate-700 bg-slate-900 p-6 shadow-xl"
          >
            <h2 id="submit-order-title" className="text-lg font-semibold text-slate-100">
              Confirm broker submission
            </h2>
            <p className="mt-2 text-sm text-slate-400">
              Production pipeline submits immediately on confirm (approval and broker placement are
              one step).
            </p>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Ticker</dt>
                <dd className="font-medium text-slate-100">{displayText(confirmSubmit.row.ticker)}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Side</dt>
                <dd className="font-medium text-slate-100">{displayText(confirmSubmit.row.side)}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Qty</dt>
                <dd className="font-medium text-slate-100">{confirmSubmit.row.quantity ?? '—'}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Engine</dt>
                <dd className="font-medium text-slate-100">{displayText(confirmSubmit.row.engine)}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Broker</dt>
                <dd className="font-medium text-slate-100">{displayText(confirmSubmit.row.broker)}</dd>
              </div>
            </dl>
            {!brokerConnected && (
              <p className="mt-4 text-sm text-red-400">
                Zerodha is not connected. Connect on the Brokers page before submitting.
              </p>
            )}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmSubmit(null)}
                className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!brokerConnected || busyKey !== null}
                onClick={handleSubmitConfirmed}
                className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Submit to broker
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Execution</h1>
          <p className="text-sm text-slate-500 mt-1">
            Production signal queue — reject pending orders or submit to broker when connected
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busyKey !== null}
            onClick={() => handleSync(false)}
            className="rounded-md border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            Sync Order Status
          </button>
          <button
            type="button"
            disabled={busyKey !== null}
            onClick={() => handleSync(true)}
            className="rounded-md border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
            title="Re-check PENDING and SYNC_FAILED orders"
          >
            Force Re-sync
          </button>
          <button
            type="button"
            onClick={loadExecution}
            disabled={busyKey !== null}
            className="rounded-md border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            Refresh
          </button>
        </div>
      </div>

      {actionMessage && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            actionMessage.success
              ? 'border-emerald-900/50 bg-emerald-900/20 text-emerald-300'
              : 'border-red-900/50 bg-red-900/20 text-red-300'
          }`}
        >
          {actionMessage.message}
        </div>
      )}

      <div className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 text-sm flex flex-wrap gap-4">
        <div>
          <span className="text-slate-500">Zerodha</span>
          <span className={`ml-2 font-semibold ${brokerStatusClass(zerodha?.status ?? 'UNAVAILABLE')}`}>
            {zerodha?.status ?? 'UNAVAILABLE'}
          </span>
        </div>
        {!brokerConnected && (
          <span className="text-amber-400 text-xs self-center">
            Submit to broker requires Zerodha CONNECTED — reject is always available
          </span>
        )}
        {snapshot.brokerState
          .filter((broker) => !broker.name.toUpperCase().includes('ZERODHA'))
          .map((broker) => (
            <div key={broker.name}>
              <span className="text-slate-500">{broker.name}</span>
              <span className={`ml-2 font-medium ${brokerStatusClass(broker.status)}`}>
                {broker.status}
              </span>
            </div>
          ))}
      </div>

      <div className="flex flex-wrap gap-2.5">
        {LIFECYCLE_FILTERS.map((item) => {
          const active = filter === item.id;
          const count = countForFilter(snapshot, item.id);
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setFilter(item.id)}
              className={`rounded-lg border px-4 py-2 text-sm font-semibold transition-colors ${
                active
                  ? 'border-slate-500 bg-slate-700/90 text-slate-100'
                  : 'border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-600 hover:text-slate-200'
              }`}
            >
              {item.label}
              <span className={`ml-2 ${active ? 'text-slate-100' : 'text-slate-500'}`}>{count}</span>
            </button>
          );
        })}
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="min-w-max w-full bg-slate-900 text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-slate-400 whitespace-nowrap">
              <th className="p-4">Lifecycle</th>
              <th className="p-4">Status</th>
              <th className="p-4">Engine</th>
              <th className="p-4">Ticker</th>
              <th className="p-4">Side</th>
              <th className="p-4">Qty</th>
              <th className="p-4">Broker</th>
              <th className="p-4">Broker Order ID</th>
              <th className="p-4">Request ID</th>
              <th className="p-4">Timestamp</th>
              <th className="p-4">Message</th>
              <th className="p-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.length > 0 ? (
              visibleRows.map((row: ExecutionOrderRow) => {
                const isPending = row.lifecycle === 'pending';
                const showSync = canSyncRow(row);
                const submitDisabled = !brokerConnected || busyKey !== null;
                const rowBusy =
                  busyKey?.includes(row.requestId ?? row.id) ||
                  (row.requestId ? busyKey === `submit-${row.requestId}` || busyKey === `reject-${row.requestId}` : false);

                return (
                  <tr key={`${row.lifecycle}-${row.id}`} className="border-b border-slate-800 whitespace-nowrap">
                    <td className="p-4 capitalize text-slate-300">{row.lifecycle.replace('_', ' ')}</td>
                    <td className="p-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${statusBadgeClass(
                          row.status,
                        )}`}
                      >
                        {row.status}
                      </span>
                    </td>
                    <td className="p-4">{displayText(row.engine)}</td>
                    <td className="p-4 font-medium">{displayText(row.ticker)}</td>
                    <td className="p-4">{displayText(row.side)}</td>
                    <td className="p-4">{row.quantity ?? '—'}</td>
                    <td className="p-4">{displayText(row.broker)}</td>
                    <td className="p-4 font-mono text-xs">{displayText(row.brokerOrderId)}</td>
                    <td className="p-4 font-mono text-xs">{displayText(row.requestId)}</td>
                    <td className="p-4">{displayText(row.timestamp)}</td>
                    <td className="p-4 max-w-[320px] truncate text-slate-400" title={row.message ?? ''}>
                      {displayText(row.message)}
                    </td>
                    <td className="p-4">
                      <div className="flex gap-2">
                        {isPending && (
                          <>
                            <button
                              type="button"
                              disabled={submitDisabled || Boolean(rowBusy)}
                              title={
                                brokerConnected
                                  ? 'Submit to broker (production approve path)'
                                  : 'Connect Zerodha before submitting'
                              }
                              onClick={() => setConfirmSubmit({ row })}
                              className="rounded border border-emerald-800 bg-emerald-900/40 px-2 py-1 text-xs font-semibold text-emerald-300 hover:bg-emerald-900/60 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              Submit
                            </button>
                            <button
                              type="button"
                              disabled={busyKey !== null || Boolean(rowBusy)}
                              onClick={() => handleReject(row)}
                              className="rounded border border-red-900/60 bg-red-900/30 px-2 py-1 text-xs font-semibold text-red-300 hover:bg-red-900/50 disabled:opacity-40"
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {showSync && (
                          <button
                            type="button"
                            disabled={busyKey !== null}
                            onClick={() => handleSync(false)}
                            className="rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-300 hover:bg-slate-700 disabled:opacity-40"
                          >
                            Sync Status
                          </button>
                        )}
                        {!isPending && !showSync && <span className="text-slate-600 text-xs">—</span>}
                      </div>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={12} className="p-8 text-center text-slate-500 italic">
                  No orders in this lifecycle stage
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Execution;
