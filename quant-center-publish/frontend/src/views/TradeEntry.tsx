import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { tradeEntryService } from '../services/tradeEntryService';
import {
  TradeAction,
  TradeBookRow,
  TradeEntryActionResult,
  TradeEntrySnapshot,
  TradeStatus,
} from '../types/tradeEntry';

const todayIso = () => new Date().toISOString().slice(0, 10);

const ddmmyyyyToIso = (value: string) => {
  const parts = value.trim().split('-');
  if (parts.length !== 3) return todayIso();
  const [day, month, year] = parts;
  if (day.length === 4) return value.slice(0, 10);
  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
};

const displayText = (value?: string | null) => (value?.trim() ? value : '—');

const displayNumber = (value?: number | null, digits = 2) =>
  value != null ? value.toFixed(digits) : '—';

const inputClass =
  'w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100';
const labelClass = 'block text-xs text-slate-500 mb-1';
const sectionClass = 'rounded-lg border border-slate-800 bg-slate-900 p-5 mb-5';
const btnPrimary =
  'rounded-lg border border-emerald-600/50 bg-emerald-700/80 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50';
const btnSecondary =
  'rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-700 disabled:opacity-50';
const btnDanger =
  'rounded-lg border border-red-500/40 bg-red-600/70 px-4 py-2 text-sm font-semibold text-white hover:bg-red-600 disabled:opacity-50';

const tradeLabel = (row: TradeBookRow) =>
  `${row.rowIndex} | ${row.ticker} | ${row.status}`;

const TradeEntry = () => {
  const [snapshot, setSnapshot] = useState<TradeEntrySnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<TradeEntryActionResult | null>(null);
  const [busy, setBusy] = useState(false);

  const [addForm, setAddForm] = useState({
    tradeDate: todayIso(),
    engine: 'MANUAL',
    action: 'BUY' as TradeAction,
    ticker: '',
    entryPrice: 0,
    qty: 1,
    stopLoss: 0,
    target: 0,
    notes: '',
  });

  const [editRowIndex, setEditRowIndex] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    tradeDate: todayIso(),
    engine: '',
    action: 'BUY' as TradeAction,
    ticker: '',
    qty: 1,
    entryPrice: 0,
    stopLoss: 0,
    target: 0,
    status: 'OPEN' as TradeStatus,
    notes: '',
    exitPrice: 0,
    exitDate: todayIso(),
  });

  const [closeRowIndex, setCloseRowIndex] = useState<number | null>(null);
  const [closeForm, setCloseForm] = useState({ exitPrice: 0, exitDate: todayIso() });

  const [deleteRowIndex, setDeleteRowIndex] = useState<number | null>(null);

  const loadSnapshot = useCallback(async () => {
    try {
      const data = await tradeEntryService.getSnapshot();
      setSnapshot(data);
      setError(null);

      if (data.pendingDeploy) {
        const d = data.pendingDeploy;
        const noteParts: string[] = [];
        if (d.rank) noteParts.push(`Rank#${d.rank}`);
        if (d.sector) noteParts.push(d.sector);
        if (d.technical) noteParts.push(`Tech:${d.technical}`);
        if (d.business) noteParts.push(`Biz:${d.business}`);
        setAddForm((prev) => ({
          ...prev,
          engine: d.engine || 'MANUAL',
          ticker: d.ticker || prev.ticker,
          entryPrice: d.close > 0 ? d.close : prev.entryPrice,
          qty: d.suggestedQty > 0 ? d.suggestedQty : prev.qty,
          notes: noteParts.join(' | '),
        }));
      }
    } catch {
      setError('Failed to load trade entry journal.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSnapshot();
  }, [loadSnapshot]);

  const openTrades = useMemo(
    () => (snapshot?.trades ?? []).filter((t) => t.status.toUpperCase() === 'OPEN'),
    [snapshot],
  );

  const allTrades = snapshot?.trades ?? [];

  useEffect(() => {
    if (openTrades.length > 0 && closeRowIndex == null) {
      setCloseRowIndex(openTrades[0].rowIndex);
    }
    if (allTrades.length > 0 && editRowIndex == null) {
      setEditRowIndex(allTrades[0].rowIndex);
    }
    if (allTrades.length > 0 && deleteRowIndex == null) {
      setDeleteRowIndex(allTrades[0].rowIndex);
    }
  }, [openTrades, allTrades, closeRowIndex, editRowIndex, deleteRowIndex]);

  useEffect(() => {
    const row = allTrades.find((t) => t.rowIndex === editRowIndex);
    if (!row) return;
    setEditForm({
      tradeDate: row.date ? ddmmyyyyToIso(row.date) : todayIso(),
      engine: row.engine,
      action: (row.action.toUpperCase() === 'SELL' ? 'SELL' : 'BUY') as TradeAction,
      ticker: row.ticker,
      qty: row.qty ?? 1,
      entryPrice: row.entryPrice ?? 0,
      stopLoss: row.stopLoss ?? 0,
      target: row.target ?? 0,
      status: (row.status.toUpperCase() === 'CLOSED' ? 'CLOSED' : 'OPEN') as TradeStatus,
      notes: row.notes,
      exitPrice: row.exitPrice ?? 0,
      exitDate: row.exitDate ? ddmmyyyyToIso(row.exitDate) : todayIso(),
    });
  }, [editRowIndex, allTrades]);

  const runAction = async (action: () => Promise<TradeEntryActionResult>) => {
    setBusy(true);
    setActionMessage(null);
    try {
      const result = await action();
      setActionMessage(result);
      if (result.success) {
        await loadSnapshot();
      }
    } catch {
      setActionMessage({ success: false, message: 'Request failed.' });
    } finally {
      setBusy(false);
    }
  };

  const handleAddSubmit = (e: FormEvent) => {
    e.preventDefault();
    runAction(() => tradeEntryService.addTrade(addForm));
  };

  const handleEditSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (editRowIndex == null) return;
    runAction(() => tradeEntryService.editTrade(editRowIndex, editForm));
  };

  const handleClose = () => {
    if (closeRowIndex == null) return;
    runAction(() => tradeEntryService.closeTrade(closeRowIndex, closeForm));
  };

  const handleDelete = () => {
    if (deleteRowIndex == null) return;
    if (!window.confirm('Delete this trade from the journal?')) return;
    runAction(() => tradeEntryService.deleteTrade(deleteRowIndex));
  };

  const handleDiscardDeploy = () => {
    runAction(() => tradeEntryService.discardPendingDeploy());
  };

  if (loading) return <div className="p-8 text-slate-400">Loading trade entry journal...</div>;
  if (error) return <div className="p-8 text-red-500">{error}</div>;

  const pending = snapshot?.pendingDeploy;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1 text-slate-100">Trade Entry</h1>
      <p className="text-slate-400 text-sm mb-5">
        Single execution ledger — all engines (F1, E1–E6, R1). Manual journal writes to{' '}
        <span className="text-slate-300">trades_log.csv</span>.
      </p>

      {actionMessage && (
        <div
          className={`mb-4 rounded-lg border px-4 py-3 text-sm ${
            actionMessage.success
              ? 'border-emerald-800/60 bg-emerald-900/20 text-emerald-300'
              : 'border-red-800/60 bg-red-900/20 text-red-300'
          }`}
        >
          {actionMessage.message}
          {actionMessage.rebuiltOpenPositions ? ' · open_positions.csv rebuilt' : ''}
        </div>
      )}

      {pending && (
        <div className={`${sectionClass} border-emerald-800/40`}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <span className="inline-block rounded-md bg-emerald-900/40 px-2 py-0.5 text-xs font-bold text-emerald-300 mb-2">
                DEPLOYING FROM F1
              </span>
              <p className="text-slate-100 font-semibold">
                {pending.ticker}
                {pending.rank ? (
                  <span className="text-slate-400 font-normal ml-2">Rank #{pending.rank}</span>
                ) : null}
                {pending.sector ? (
                  <span className="text-slate-500 font-normal ml-2">{pending.sector}</span>
                ) : null}
              </p>
              <p className="text-sm text-slate-400 mt-1">
                Pre-filled from F1 signal. Enter your actual execution price and quantity, then
                save.
              </p>
            </div>
            <button type="button" onClick={handleDiscardDeploy} disabled={busy} className={btnSecondary}>
              Discard pending trade
            </button>
          </div>
        </div>
      )}

      {/* Add New Trade */}
      <div className={sectionClass}>
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Add New Trade</h2>
        <form onSubmit={handleAddSubmit}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
              <label className={labelClass} htmlFor="add-date">
                Trade Date
              </label>
              <input
                id="add-date"
                type="date"
                className={inputClass}
                value={addForm.tradeDate}
                onChange={(e) => setAddForm({ ...addForm, tradeDate: e.target.value })}
                required
              />
            </div>
            <div>
              <label className={labelClass} htmlFor="add-engine">
                Engine
              </label>
              <input
                id="add-engine"
                className={inputClass}
                value={addForm.engine}
                onChange={(e) => setAddForm({ ...addForm, engine: e.target.value })}
              />
            </div>
            <div>
              <label className={labelClass} htmlFor="add-action">
                Action
              </label>
              <select
                id="add-action"
                className={inputClass}
                value={addForm.action}
                onChange={(e) =>
                  setAddForm({ ...addForm, action: e.target.value as TradeAction })
                }
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="add-ticker">
                Ticker
              </label>
              <input
                id="add-ticker"
                className={inputClass}
                placeholder="RELIANCE.NS"
                value={addForm.ticker}
                onChange={(e) => setAddForm({ ...addForm, ticker: e.target.value })}
                required
              />
            </div>
            <div>
              <label className={labelClass} htmlFor="add-entry">
                Entry Price
                {pending && pending.close > 0 ? (
                  <span className="text-slate-500 ml-1">
                    (suggested: ₹{pending.close.toLocaleString('en-IN')})
                  </span>
                ) : null}
              </label>
              <input
                id="add-entry"
                type="number"
                min={0}
                step={0.05}
                className={inputClass}
                value={addForm.entryPrice || ''}
                onChange={(e) =>
                  setAddForm({ ...addForm, entryPrice: parseFloat(e.target.value) || 0 })
                }
                required
              />
            </div>
            <div>
              <label className={labelClass} htmlFor="add-qty">
                Quantity
              </label>
              <input
                id="add-qty"
                type="number"
                min={1}
                step={1}
                className={inputClass}
                value={addForm.qty}
                onChange={(e) => setAddForm({ ...addForm, qty: parseFloat(e.target.value) || 0 })}
                required
              />
            </div>
            <div>
              <label className={labelClass} htmlFor="add-sl">
                Stop Loss
              </label>
              <input
                id="add-sl"
                type="number"
                min={0}
                step={0.05}
                className={inputClass}
                value={addForm.stopLoss || ''}
                onChange={(e) =>
                  setAddForm({ ...addForm, stopLoss: parseFloat(e.target.value) || 0 })
                }
              />
            </div>
            <div>
              <label className={labelClass} htmlFor="add-target">
                Target
              </label>
              <input
                id="add-target"
                type="number"
                min={0}
                step={0.05}
                className={inputClass}
                value={addForm.target || ''}
                onChange={(e) =>
                  setAddForm({ ...addForm, target: parseFloat(e.target.value) || 0 })
                }
              />
            </div>
            <div>
              <label className={labelClass} htmlFor="add-notes">
                Notes
              </label>
              <input
                id="add-notes"
                className={inputClass}
                value={addForm.notes}
                onChange={(e) => setAddForm({ ...addForm, notes: e.target.value })}
              />
            </div>
          </div>
          <button type="submit" disabled={busy} className={btnPrimary}>
            Save Trade
          </button>
        </form>
      </div>

      {/* Edit */}
      <div className={sectionClass}>
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Edit Existing Trade</h2>
        {allTrades.length === 0 ? (
          <p className="text-slate-500 text-sm italic">Trade book empty</p>
        ) : (
          <>
            <label className={labelClass} htmlFor="edit-select">
              Select Trade to Edit
            </label>
            <select
              id="edit-select"
              className={`${inputClass} mb-4 max-w-xl`}
              value={editRowIndex ?? ''}
              onChange={(e) => setEditRowIndex(Number(e.target.value))}
            >
              {allTrades.map((row) => (
                <option key={row.rowIndex} value={row.rowIndex}>
                  {tradeLabel(row)}
                </option>
              ))}
            </select>
            <form onSubmit={handleEditSubmit}>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div>
                  <label className={labelClass}>Trade Date</label>
                  <input
                    type="date"
                    className={inputClass}
                    value={editForm.tradeDate}
                    onChange={(e) => setEditForm({ ...editForm, tradeDate: e.target.value })}
                  />
                </div>
                <div>
                  <label className={labelClass}>Engine</label>
                  <input
                    className={inputClass}
                    value={editForm.engine}
                    onChange={(e) => setEditForm({ ...editForm, engine: e.target.value })}
                  />
                </div>
                <div>
                  <label className={labelClass}>Action</label>
                  <select
                    className={inputClass}
                    value={editForm.action}
                    onChange={(e) =>
                      setEditForm({ ...editForm, action: e.target.value as TradeAction })
                    }
                  >
                    <option value="BUY">BUY</option>
                    <option value="SELL">SELL</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Ticker</label>
                  <input
                    className={inputClass}
                    value={editForm.ticker}
                    onChange={(e) => setEditForm({ ...editForm, ticker: e.target.value })}
                  />
                </div>
                <div>
                  <label className={labelClass}>Quantity</label>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    className={inputClass}
                    value={editForm.qty}
                    onChange={(e) =>
                      setEditForm({ ...editForm, qty: parseFloat(e.target.value) || 1 })
                    }
                  />
                </div>
                <div>
                  <label className={labelClass}>Entry Price</label>
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    className={inputClass}
                    value={editForm.entryPrice || ''}
                    onChange={(e) =>
                      setEditForm({ ...editForm, entryPrice: parseFloat(e.target.value) || 0 })
                    }
                  />
                </div>
                <div>
                  <label className={labelClass}>Stop Loss</label>
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    className={inputClass}
                    value={editForm.stopLoss || ''}
                    onChange={(e) =>
                      setEditForm({ ...editForm, stopLoss: parseFloat(e.target.value) || 0 })
                    }
                  />
                </div>
                <div>
                  <label className={labelClass}>Target</label>
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    className={inputClass}
                    value={editForm.target || ''}
                    onChange={(e) =>
                      setEditForm({ ...editForm, target: parseFloat(e.target.value) || 0 })
                    }
                  />
                </div>
                <div>
                  <label className={labelClass}>Status</label>
                  <select
                    className={inputClass}
                    value={editForm.status}
                    onChange={(e) =>
                      setEditForm({ ...editForm, status: e.target.value as TradeStatus })
                    }
                  >
                    <option value="OPEN">OPEN</option>
                    <option value="CLOSED">CLOSED</option>
                  </select>
                </div>
                <div className="md:col-span-3">
                  <label className={labelClass}>Notes</label>
                  <input
                    className={inputClass}
                    value={editForm.notes}
                    onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                  />
                </div>
                {editForm.status === 'CLOSED' && (
                  <>
                    <p className="md:col-span-3 text-xs text-slate-500">
                      If Status is CLOSED, fill Exit Price and Exit Date.
                    </p>
                    <div>
                      <label className={labelClass}>Exit Price</label>
                      <input
                        type="number"
                        min={0}
                        step={0.05}
                        className={inputClass}
                        value={editForm.exitPrice || ''}
                        onChange={(e) =>
                          setEditForm({
                            ...editForm,
                            exitPrice: parseFloat(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                    <div>
                      <label className={labelClass}>Exit Date</label>
                      <input
                        type="date"
                        className={inputClass}
                        value={editForm.exitDate}
                        onChange={(e) => setEditForm({ ...editForm, exitDate: e.target.value })}
                      />
                    </div>
                  </>
                )}
              </div>
              <button type="submit" disabled={busy} className={btnPrimary}>
                Save Edits
              </button>
            </form>
          </>
        )}
      </div>

      {/* Close + Delete */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        <div className={sectionClass}>
          <h2 className="text-lg font-semibold text-slate-100 mb-2">Close Trade</h2>
          <p className="text-xs text-slate-500 mb-4">
            Manual journal close — writes CLOSED directly to trades_log.csv. Does not submit broker
            SELL. For broker-backed exits use Positions → Exit.
          </p>
          {openTrades.length === 0 ? (
            <p className="text-slate-500 text-sm italic">No open trades</p>
          ) : (
            <>
              <label className={labelClass}>Select Trade</label>
              <select
                className={`${inputClass} mb-3`}
                value={closeRowIndex ?? ''}
                onChange={(e) => setCloseRowIndex(Number(e.target.value))}
              >
                {openTrades.map((row) => (
                  <option key={row.rowIndex} value={row.rowIndex}>
                    {row.rowIndex} | {row.ticker}
                  </option>
                ))}
              </select>
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <label className={labelClass}>Exit Price</label>
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    className={inputClass}
                    value={closeForm.exitPrice || ''}
                    onChange={(e) =>
                      setCloseForm({ ...closeForm, exitPrice: parseFloat(e.target.value) || 0 })
                    }
                  />
                </div>
                <div>
                  <label className={labelClass}>Exit Date</label>
                  <input
                    type="date"
                    className={inputClass}
                    value={closeForm.exitDate}
                    onChange={(e) => setCloseForm({ ...closeForm, exitDate: e.target.value })}
                  />
                </div>
              </div>
              <button type="button" onClick={handleClose} disabled={busy} className={btnPrimary}>
                Close Trade
              </button>
            </>
          )}
        </div>

        <div className={sectionClass}>
          <h2 className="text-lg font-semibold text-slate-100 mb-4">Delete Trade</h2>
          {allTrades.length === 0 ? (
            <p className="text-slate-500 text-sm italic">Trade book empty</p>
          ) : (
            <>
              <label className={labelClass}>Select Trade</label>
              <select
                className={`${inputClass} mb-4`}
                value={deleteRowIndex ?? ''}
                onChange={(e) => setDeleteRowIndex(Number(e.target.value))}
              >
                {allTrades.map((row) => (
                  <option key={row.rowIndex} value={row.rowIndex}>
                    {tradeLabel(row)}
                  </option>
                ))}
              </select>
              <button type="button" onClick={handleDelete} disabled={busy} className={btnDanger}>
                Delete Trade
              </button>
            </>
          )}
        </div>
      </div>

      {/* Trade Book */}
      <div className={sectionClass}>
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Current Trade Book</h2>
        {allTrades.length === 0 ? (
          <p className="text-slate-500 text-sm italic">No trades available</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-max w-full text-sm text-left">
              <thead>
                <tr className="text-slate-400 border-b border-slate-800">
                  <th className="p-2">#</th>
                  <th className="p-2">Date</th>
                  <th className="p-2">Engine</th>
                  <th className="p-2">Ticker</th>
                  <th className="p-2">Action</th>
                  <th className="p-2">Entry</th>
                  <th className="p-2">Qty</th>
                  <th className="p-2">SL</th>
                  <th className="p-2">Target</th>
                  <th className="p-2">Status</th>
                  <th className="p-2">Exit</th>
                  <th className="p-2">PnL</th>
                  <th className="p-2">Notes</th>
                </tr>
              </thead>
              <tbody>
                {allTrades.map((row) => (
                  <tr key={row.rowIndex} className="border-b border-slate-800/60 text-slate-300">
                    <td className="p-2 text-slate-500">{row.rowIndex}</td>
                    <td className="p-2">{displayText(row.date)}</td>
                    <td className="p-2">{displayText(row.engine)}</td>
                    <td className="p-2 font-medium">{displayText(row.ticker)}</td>
                    <td className="p-2">{displayText(row.action)}</td>
                    <td className="p-2">{displayNumber(row.entryPrice)}</td>
                    <td className="p-2">{displayNumber(row.qty, 0)}</td>
                    <td className="p-2">{displayNumber(row.stopLoss)}</td>
                    <td className="p-2">{displayNumber(row.target)}</td>
                    <td className="p-2">{displayText(row.status)}</td>
                    <td className="p-2">
                      {row.exitPrice != null ? displayNumber(row.exitPrice) : '—'}
                      {row.exitDate ? ` · ${row.exitDate}` : ''}
                    </td>
                    <td
                      className={`p-2 ${
                        (row.pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                      }`}
                    >
                      {displayNumber(row.pnl)}
                    </td>
                    <td className="p-2 max-w-[200px] truncate" title={row.notes}>
                      {displayText(row.notes)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default TradeEntry;
