import { useCallback, useEffect, useMemo, useState } from 'react';
import { f1Service } from '../services/f1Service';
import { F1DeployResult, F1RunResult, F1Snapshot } from '../types/f1';

const fmtInr = (value: number, signed = true) => {
  const sign = signed && value > 0 ? '+' : '';
  return `${sign}₹${Math.round(value).toLocaleString('en-IN')}`;
};

const pnlClass = (value: number) => (value >= 0 ? 'text-emerald-400' : 'text-red-400');

const KpiGrid = ({ cards }: { cards: { label: string; value: string; sub: string }[] }) => (
  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
    {cards.map((card) => (
      <div key={card.label} className="rounded-lg border border-slate-800 bg-slate-900 p-3">
        <div className="text-[10px] uppercase tracking-wider text-slate-500">{card.label}</div>
        <div className="text-lg font-semibold text-slate-100 mt-1">{card.value}</div>
        {card.sub ? <div className="text-xs text-slate-500 mt-1">{card.sub}</div> : null}
      </div>
    ))}
  </div>
);

const sectionTitle = 'text-base font-semibold text-slate-100 mb-3 mt-6';
const tableWrap = 'overflow-x-auto rounded-lg border border-slate-800';
const tableClass = 'min-w-max w-full text-sm bg-slate-900';
const thClass = 'p-3 text-left text-slate-400 border-b border-slate-800 whitespace-nowrap';
const tdClass = 'p-3 border-b border-slate-800/60 text-slate-300 whitespace-nowrap';

const F1 = () => {
  const [snapshot, setSnapshot] = useState<F1Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionOk, setActionOk] = useState(true);
  const [runOutput, setRunOutput] = useState<string[]>([]);

  const [auditDate, setAuditDate] = useState('All');
  const [auditDecision, setAuditDecision] = useState('All');
  const [auditTicker, setAuditTicker] = useState('');

  const loadSnapshot = useCallback(async () => {
    setBusy(true);
    try {
      const data = await f1Service.getSnapshot();
      setSnapshot(data);
      setError(null);
    } catch {
      setError('Failed to load F1 Control Center.');
    } finally {
      setLoading(false);
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    loadSnapshot();
  }, [loadSnapshot]);

  const handleRunF1 = async () => {
    setBusy(true);
    setActionMessage(null);
    setRunOutput([]);
    try {
      const result: F1RunResult = await f1Service.runF1();
      setActionOk(result.success);
      setActionMessage(result.message);
      if (result.stdoutTail?.length) setRunOutput(result.stdoutTail);
      if (result.stderrTail) setRunOutput((prev) => [...prev, result.stderrTail!]);
      if (result.snapshot) setSnapshot(result.snapshot);
      else if (result.success) await loadSnapshot();
    } catch {
      setActionOk(false);
      setActionMessage('Run F1 request failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleDeploy = async (ticker: string) => {
    setBusy(true);
    setActionMessage(null);
    try {
      const result: F1DeployResult = await f1Service.deploy(ticker);
      setActionOk(result.success);
      setActionMessage(result.message);
      if (result.snapshot) setSnapshot(result.snapshot);
    } catch {
      setActionOk(false);
      setActionMessage('Deploy request failed.');
    } finally {
      setBusy(false);
    }
  };

  const filteredAudit = useMemo(() => {
    if (!snapshot) return [];
    let rows = snapshot.decisionAudit.rows;
    if (auditDate !== 'All') rows = rows.filter((r) => r.date.startsWith(auditDate) || r.date === auditDate);
    if (auditDecision !== 'All') rows = rows.filter((r) => r.decision === auditDecision);
    if (auditTicker.trim()) {
      const q = auditTicker.trim().toLowerCase();
      rows = rows.filter((r) => r.ticker.toLowerCase().includes(q));
    }
    return rows;
  }, [snapshot, auditDate, auditDecision, auditTicker]);

  if (loading && !snapshot) return <div className="p-8 text-slate-400">Loading F1 Control Center...</div>;
  if (error && !snapshot) return <div className="p-8 text-red-500">{error}</div>;
  if (!snapshot) return null;

  const dc = snapshot.todayDecisionCounts;

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-100">F1 Control Center</h1>
      <p className="text-slate-400 text-sm mt-1 mb-4">
        ₹{snapshot.totalCapital.toLocaleString('en-IN')} F1 portfolio · max {snapshot.maxPositions}{' '}
        positions · run, deploy, monitor
      </p>

      <div className="flex flex-wrap items-center gap-4 mb-4">
        <button
          type="button"
          disabled={busy}
          onClick={handleRunF1}
          className="rounded-lg border border-emerald-600/50 bg-emerald-700 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
        >
          {busy ? 'Running…' : 'Run F1'}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={loadSnapshot}
          className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-700 disabled:opacity-50"
        >
          Refresh
        </button>
        {snapshot.lastRun ? (
          <span className="text-xs text-slate-500">
            Last run: <b className="text-slate-300">{snapshot.lastRun.timestamp}</b> ·{' '}
            {snapshot.lastRun.universe} tickers · {snapshot.lastRun.elapsedSec}s ·{' '}
            {snapshot.lastRun.ok ? '✔' : `⚠ ${snapshot.lastRun.failures}`}
          </span>
        ) : null}
      </div>

      {actionMessage && (
        <div
          className={`mb-4 rounded-lg border px-4 py-3 text-sm ${
            actionOk
              ? 'border-emerald-800/60 bg-emerald-900/20 text-emerald-300'
              : 'border-red-800/60 bg-red-900/20 text-red-300'
          }`}
        >
          {actionMessage}
        </div>
      )}
      {runOutput.length > 0 && (
        <pre className="mb-4 rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs text-slate-400 overflow-x-auto">
          {runOutput.join('\n')}
        </pre>
      )}

      <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-4 text-xs">
        <div className="rounded border border-slate-800 bg-slate-900 p-2">
          <span className="text-slate-500">Today decisions</span>
          <div className="text-slate-100 font-semibold">{dc.total}</div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900 p-2">
          <span className="text-slate-500">BUY</span>
          <div className="text-emerald-400 font-semibold">{dc.buy}</div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900 p-2">
          <span className="text-slate-500">ROTATE</span>
          <div className="text-amber-300 font-semibold">{dc.rotate}</div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900 p-2">
          <span className="text-slate-500">BLOCK</span>
          <div className="text-red-400 font-semibold">{dc.block}</div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900 p-2">
          <span className="text-slate-500">WATCH</span>
          <div className="text-blue-300 font-semibold">{dc.watch}</div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900 p-2">
          <span className="text-slate-500">IGNORE</span>
          <div className="text-slate-400 font-semibold">{dc.ignore}</div>
        </div>
      </div>

      <h2 className={sectionTitle}>F1 CAPITAL ALLOCATION</h2>
      <KpiGrid cards={snapshot.capitalAllocation.cards} />

      <h2 className={sectionTitle}>F1 PERFORMANCE</h2>
      <KpiGrid cards={snapshot.performance.cards} />

      <h2 className={sectionTitle}>READY TO DEPLOY</h2>
      {snapshot.readyToDeploy.candidates.length > 0 ? (
        <>
          <p className="text-sm text-slate-400 mb-3">
            <span className="text-emerald-400 font-semibold">
              {snapshot.readyToDeploy.candidateCount} CANDIDATES · {snapshot.readyToDeploy.deployToday}{' '}
              DEPLOYABLE
            </span>
            {' · '}
            capital/trade ₹{Math.round(snapshot.readyToDeploy.suggestedCapital).toLocaleString('en-IN')}
            {' · '}
            top {snapshot.readyToDeploy.deployToday} fit slots+cash
          </p>
          <div className="space-y-3">
            {snapshot.readyToDeploy.candidates.map((c) => (
              <div
                key={c.ticker}
                className="rounded-lg border border-slate-800 bg-slate-900 p-4 grid grid-cols-1 lg:grid-cols-12 gap-3 items-center"
              >
                <div className="lg:col-span-1">
                  <span
                    className={`text-lg font-extrabold ${
                      c.heldElsewhere ? 'text-amber-400' : c.isDeployable ? 'text-emerald-400' : 'text-slate-500'
                    }`}
                  >
                    #{c.portfolioRank != null ? Math.trunc(c.portfolioRank) : '—'}
                  </span>
                </div>
                <div className="lg:col-span-3">
                  <div className="font-bold text-slate-100">{c.ticker}</div>
                  <div className="text-sm text-slate-400">
                    {c.sector} · {c.phase}
                  </div>
                  {c.heldByEngine ? (
                    <span className="inline-block mt-1 text-[10px] font-bold bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded">
                      HELD IN {c.heldByEngine}
                    </span>
                  ) : null}
                </div>
                <div className="lg:col-span-3 text-sm">
                  <div>
                    Close: <b>₹{c.close.toLocaleString('en-IN')}</b>
                    {c.rs55 != null ? ` · RS55: ${c.rs55.toFixed(1)}` : ''}
                    {c.entryDistPct != null ? ` · Dist: ${c.entryDistPct.toFixed(1)}%` : ''}
                  </div>
                  <div className="text-slate-400 mt-1 font-semibold">
                    {c.technicalState} · {c.sectorState} · {c.businessGate}
                  </div>
                </div>
                <div className="lg:col-span-3 text-sm">
                  {c.heldElsewhere ? (
                    <span className="text-amber-400 font-semibold">— already owned —</span>
                  ) : c.isDeployable && c.close > 0 ? (
                    <>
                      <div className="text-emerald-400 font-bold">
                        Cap: ₹{Math.round(c.suggestedCapital).toLocaleString('en-IN')}
                      </div>
                      <div className="text-slate-400">
                        Qty: <b>{c.suggestedQty}</b> · Value: ₹
                        {Math.round(c.positionValue).toLocaleString('en-IN')}
                      </div>
                    </>
                  ) : (
                    <span className="text-slate-500">— no cash/slots —</span>
                  )}
                </div>
                <div className="lg:col-span-2">
                  <button
                    type="button"
                    disabled={busy || c.buttonDisabled}
                    onClick={() => handleDeploy(c.ticker)}
                    className={`w-full rounded-lg px-3 py-2 text-sm font-semibold disabled:opacity-40 ${
                      c.isDeployable && !c.buttonDisabled
                        ? 'bg-emerald-700 text-white hover:bg-emerald-600'
                        : 'border border-slate-600 bg-slate-800 text-slate-300'
                    }`}
                  >
                    {c.buttonLabel}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-300">
          {snapshot.readyToDeploy.allHeldMessage ||
            snapshot.readyToDeploy.emptyMessage ||
            snapshot.readyToDeploy.noCandidatesMessage ||
            'No deploy candidates.'}
          {snapshot.readyToDeploy.phaseBreakdown.length > 0 && (
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div className="text-slate-400 mb-2 font-semibold">By Phase</div>
                <table className="text-xs w-full">
                  <tbody>
                    {snapshot.readyToDeploy.phaseBreakdown.map((r) => (
                      <tr key={r.label}>
                        <td className="py-1 text-slate-300">{r.label}</td>
                        <td className="py-1 text-right text-slate-100">{r.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div>
                <div className="text-slate-400 mb-2 font-semibold">By Action</div>
                <table className="text-xs w-full">
                  <tbody>
                    {snapshot.readyToDeploy.actionBreakdown.map((r) => (
                      <tr key={r.label}>
                        <td className="py-1 text-slate-300">{r.label}</td>
                        <td className="py-1 text-right text-slate-100">{r.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {snapshot.alreadyOwned.length > 0 && (
        <>
          <h2 className={sectionTitle}>ALREADY IN PORTFOLIO</h2>
          <p className="text-sm text-slate-400 mb-3">{snapshot.alreadyOwnedSummary}</p>
          <div className={tableWrap}>
            <table className={tableClass}>
              <thead>
                <tr>
                  {['Ticker', 'Sector', 'Phase', 'Rank', 'Technical', 'Sector', 'RS55', 'Close', 'Held In'].map(
                    (h) => (
                      <th key={h} className={thClass}>
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {snapshot.alreadyOwned.map((r) => (
                  <tr key={r.ticker}>
                    <td className={`${tdClass} font-medium`}>{r.ticker}</td>
                    <td className={tdClass}>{r.sector}</td>
                    <td className={tdClass}>{r.phase}</td>
                    <td className={tdClass}>{r.portfolioRank ?? '—'}</td>
                    <td className={tdClass}>{r.technicalState}</td>
                    <td className={tdClass}>{r.sectorState}</td>
                    <td className={tdClass}>{r.rs55?.toFixed(1) ?? '—'}</td>
                    <td className={tdClass}>{r.close != null ? fmtInr(r.close, false) : '—'}</td>
                    <td className={tdClass}>{r.heldIn}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h2 className={sectionTitle}>F1 OPEN POSITIONS</h2>
      {snapshot.openPositions.length === 0 ? (
        <p className="text-slate-500 text-sm">{snapshot.openPositionsEmptyMessage}</p>
      ) : (
        <>
          <div className={tableWrap}>
            <table className={tableClass}>
              <thead>
                <tr>
                  {['', 'Ticker', 'Entry', 'CMP', 'Return %', 'PnL ₹', 'Qty', 'Phase', 'Technical', 'Exit Priority', 'Exit Rule'].map(
                    (h) => (
                      <th key={h || 'sig'} className={thClass}>
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {snapshot.openPositions.map((r) => (
                  <tr key={r.ticker}>
                    <td className={tdClass}>{r.signal}</td>
                    <td className={`${tdClass} font-medium`}>{r.ticker}</td>
                    <td className={tdClass}>{fmtInr(r.entry, false)}</td>
                    <td className={tdClass}>{fmtInr(r.cmp, false)}</td>
                    <td className={`${tdClass} ${pnlClass(r.returnPct)}`}>{r.returnPct.toFixed(2)}%</td>
                    <td className={`${tdClass} ${pnlClass(r.pnlInr)}`}>{fmtInr(r.pnlInr)}</td>
                    <td className={tdClass}>{r.qty}</td>
                    <td className={tdClass}>{r.phase}</td>
                    <td className={tdClass}>{r.technical}</td>
                    <td className={tdClass}>{r.exitPriority}</td>
                    <td className={tdClass}>{r.exitRule}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            🟢 HOLD — Technical intact · 🟡 WATCH — approaching exit signal · 🔴 EXIT — Technical FADING
            confirmed (F1 production exit rule)
          </p>
        </>
      )}

      <h2 className={sectionTitle}>DECISION AUDIT</h2>
      {snapshot.decisionAudit.rows.length === 0 ? (
        <p className="text-slate-500 text-sm">No decisions in log.</p>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <select
              className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100"
              value={auditDate}
              onChange={(e) => setAuditDate(e.target.value)}
            >
              <option value="All">All dates</option>
              {snapshot.decisionAudit.dateOptions.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <select
              className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100"
              value={auditDecision}
              onChange={(e) => setAuditDecision(e.target.value)}
            >
              {['All', 'BUY', 'EXIT', 'HOLD', 'BLOCK', 'SKIP'].map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <input
              className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100"
              placeholder="Ticker filter"
              value={auditTicker}
              onChange={(e) => setAuditTicker(e.target.value)}
            />
          </div>
          <p className="text-sm text-slate-400 mb-2">
            {filteredAudit.length} of {snapshot.decisionAudit.totalF1} F1 decisions
          </p>
          <div className={tableWrap}>
            <table className={tableClass}>
              <thead>
                <tr>
                  {['Date', 'Engine', 'Ticker', 'Decision', 'Reason', 'Technical', 'Sector', 'Business', 'Rank'].map(
                    (h) => (
                      <th key={h} className={thClass}>
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {filteredAudit.slice(0, 200).map((r, i) => (
                  <tr key={`${r.ticker}-${r.date}-${i}`}>
                    <td className={tdClass}>{r.date}</td>
                    <td className={tdClass}>{r.engine}</td>
                    <td className={`${tdClass} font-medium`}>{r.ticker}</td>
                    <td className={tdClass}>{r.decision}</td>
                    <td className={tdClass}>{r.reason}</td>
                    <td className={tdClass}>{r.technicalState}</td>
                    <td className={tdClass}>{r.sectorState}</td>
                    <td className={tdClass}>{r.businessGate}</td>
                    <td className={tdClass}>{r.portfolioRank}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h2 className={sectionTitle}>PRODUCTION STATUS</h2>
      {snapshot.productionStatus.emptyMessage ? (
        <p className="text-slate-500 text-sm">{snapshot.productionStatus.emptyMessage}</p>
      ) : (
        <>
          <p className="text-sm mb-3">
            <span
              className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${
                snapshot.productionStatus.overall === 'HEALTHY'
                  ? 'bg-emerald-500/20 text-emerald-300'
                  : snapshot.productionStatus.overall === 'WARNING'
                    ? 'bg-amber-500/20 text-amber-300'
                    : 'bg-red-500/20 text-red-300'
              }`}
            >
              {snapshot.productionStatus.overall}
            </span>
            <span className="text-slate-500 text-xs ml-2">
              as of {snapshot.productionStatus.generatedAt}
            </span>
          </p>
          <div className={tableWrap}>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}></th>
                  <th className={thClass}>Component</th>
                  <th className={thClass}>Status</th>
                  <th className={thClass}>Detail</th>
                </tr>
              </thead>
              <tbody>
                {snapshot.productionStatus.components.map((c) => (
                  <tr key={c.component}>
                    <td className={tdClass}>{c.icon}</td>
                    <td className={tdClass}>{c.component}</td>
                    <td className={tdClass}>{c.status}</td>
                    <td className={tdClass}>{c.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};

export default F1;
