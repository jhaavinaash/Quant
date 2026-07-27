import { useCallback, useEffect, useMemo, useState } from 'react';
import { aiScannerService } from '../services/aiScannerService';
import {
  AIScannerActionResult,
  AIScannerSnapshot,
  ScanResultRow,
} from '../types/aiScanner';

const isFiniteNumber = (value?: number | null): value is number =>
  value != null && Number.isFinite(value);

const fmtInr = (value?: number | null, digits = 2) =>
  isFiniteNumber(value)
    ? `₹${value.toLocaleString('en-IN', { maximumFractionDigits: digits })}`
    : '—';

const fmtNum = (value?: number | null, digits = 2) =>
  isFiniteNumber(value) ? value.toFixed(digits) : '—';

const fmtPct = (value?: number | null, signed = true) => {
  if (!isFiniteNumber(value)) return '—';
  const sign = signed && value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
};

const pnlClass = (value?: number | null) => {
  if (value == null) return 'text-slate-400';
  return value >= 0 ? 'text-emerald-400' : 'text-red-400';
};

const scoreClass = (value: number) => {
  if (value >= 80) return 'text-emerald-400 font-bold';
  if (value >= 70) return 'text-emerald-300 font-semibold';
  return 'text-slate-300';
};

const sectionTitle = 'text-base font-semibold text-slate-100 mb-3 mt-6';
const tableWrap = 'overflow-x-auto rounded-lg border border-slate-800';
const tableClass = 'min-w-max w-full text-sm bg-slate-900';
const thClass = 'p-3 text-left text-slate-400 border-b border-slate-800 whitespace-nowrap';
const tdClass = 'p-3 border-b border-slate-800/60 text-slate-300 whitespace-nowrap';

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
  <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
    <div className="text-[11px] uppercase tracking-wider text-slate-500 font-medium">{label}</div>
    <div className={`text-xl font-semibold mt-1 ${valueClass}`}>{value}</div>
    {sub ? <div className="text-xs text-slate-500 mt-1">{sub}</div> : null}
  </div>
);

const OpportunityCard = ({
  row,
  onAddPaperTrade,
  busy,
}: {
  row: ScanResultRow;
  onAddPaperTrade: (ticker: string, source: string) => void;
  busy: boolean;
}) => {
  const bulls = row.bullSignals.slice(0, 3).join(' · ');
  return (
    <div className="rounded-xl border border-slate-800 border-t-[3px] border-t-emerald-500 bg-slate-900 p-4 h-full flex flex-col">
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="text-lg font-bold text-slate-100">{row.ticker}</div>
          <div className="text-sm text-slate-400">{row.companyName.slice(0, 30)}</div>
          <div className="text-xs text-slate-500">{row.sector.slice(0, 30)}</div>
        </div>
        <div className="text-amber-300 text-sm tracking-wider">{row.stars}</div>
      </div>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-bold text-emerald-300">
          STRONG BUY
        </span>
        <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300">
          Score {fmtNum(row.compositeScore, 0)}
        </span>
        <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300">
          ⚡ {row.groupsFired}/5
        </span>
        {row.nextEventDisplay ? (
          <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[11px] text-cyan-300">
            ⚡ {row.nextEventDisplay}
          </span>
        ) : null}
      </div>
      <div className="rounded-lg border border-slate-800 bg-slate-950 p-3 mb-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-slate-500">Entry </span>
          <b className="text-slate-100">{fmtInr(row.suggestedEntry)}</b>
        </div>
        <div>
          <span className="text-slate-500">Qty </span>
          <b className="text-slate-100">{row.suggestedQty}</b>
        </div>
        <div>
          <span className="text-slate-500">SL </span>
          <b className="text-red-400">{fmtInr(row.suggestedStop)}</b>
        </div>
        <div>
          <span className="text-slate-500">Target </span>
          <b className="text-emerald-400">{fmtInr(row.suggestedTarget)}</b>
        </div>
        <div>
          <span className="text-slate-500">R:R </span>
          <b className="text-slate-100">{fmtNum(row.rrRatio, 1)}</b>
        </div>
        <div>
          <span className="text-slate-500">Risk </span>
          <b className="text-amber-300">{fmtInr(row.maxRiskInr, 0)}</b>
        </div>
      </div>
      <div className="text-xs text-slate-500 border-t border-slate-800 pt-2 mb-3 flex-1">{bulls}</div>
      <button
        type="button"
        disabled={busy}
        onClick={() => onAddPaperTrade(row.ticker, 'Top Opportunities')}
        className="w-full rounded-lg border border-slate-600 bg-slate-800 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-700 disabled:opacity-50"
      >
        Add Paper Trade
      </button>
    </div>
  );
};

const AIScanner = () => {
  const [snapshot, setSnapshot] = useState<AIScannerSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<AIScannerActionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [qaTicker, setQaTicker] = useState('');
  const [exitTicker, setExitTicker] = useState('');
  const [exitPrice, setExitPrice] = useState(0);
  const [showQaExpander, setShowQaExpander] = useState(false);
  const [showExitExpander, setShowExitExpander] = useState(false);

  const loadSnapshot = useCallback(async (rescan = false) => {
    setBusy(true);
    setError(null);
    try {
      const data = rescan ? await aiScannerService.rescan() : await aiScannerService.getSnapshot();
      setSnapshot(data);
      setQaTicker((prev) => prev || data.strongBuys[0]?.ticker || '');
      setExitTicker((prev) => prev || data.openPaperTickers[0] || '');
    } catch {
      setError('Failed to load AI Scanner.');
    } finally {
      setLoading(false);
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    loadSnapshot(false);
  }, [loadSnapshot]);

  const runAction = async (action: () => Promise<AIScannerActionResult>) => {
    setBusy(true);
    setActionMessage(null);
    try {
      const result = await action();
      setActionMessage(result);
      if (result.snapshot) {
        setSnapshot(result.snapshot);
      } else if (result.success) {
        await loadSnapshot(false);
      }
    } catch {
      setActionMessage({ success: false, message: 'Request failed.' });
    } finally {
      setBusy(false);
    }
  };

  const handleAddPaperTrade = (ticker: string, source: string) => {
    runAction(() => aiScannerService.addPaperTrade({ ticker, source }));
  };

  const paperOutcomeClass = (outcome: string) => {
    if (outcome.includes('TP')) return 'bg-emerald-500/10';
    if (outcome.includes('SL')) return 'bg-red-500/10';
    if (outcome.includes('EXIT')) return 'bg-slate-500/10';
    return 'bg-blue-500/10';
  };

  const strongBuyTickers = useMemo(
    () => snapshot?.strongBuys.map((r) => r.ticker) ?? [],
    [snapshot],
  );

  if (loading && !snapshot) {
    return <div className="p-8 text-slate-400">Scanning universe… cached for 60min after first run</div>;
  }
  if (error && !snapshot) return <div className="p-8 text-red-500">{error}</div>;

  const data = snapshot!;
  const kpis = data.kpis;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">AI Intelligence · Opportunity Scanner</h1>
          <p className="text-slate-400 text-sm mt-1">
            Multi-factor convergence model · Conservative mode · ₹{data.capitalPerPick.toLocaleString('en-IN')}{' '}
            per pick · Auto-refresh hourly
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => loadSnapshot(true)}
          className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-700 disabled:opacity-50"
        >
          {busy ? 'Scanning…' : 'Rescan'}
        </button>
      </div>

      {actionMessage && (
        <div
          className={`mb-4 rounded-lg border px-4 py-3 text-sm ${
            actionMessage.success
              ? 'border-emerald-800/60 bg-emerald-900/20 text-emerald-300'
              : 'border-amber-800/60 bg-amber-900/20 text-amber-300'
          }`}
        >
          {actionMessage.message}
        </div>
      )}

      {data.paperTradesAutoExited > 0 && (
        <div className="mb-4 rounded-lg border border-emerald-800/50 bg-emerald-900/15 px-4 py-2 text-sm text-emerald-300">
          {data.paperTradesAutoExited} paper trade(s) auto-booked — TP or SL hit
        </div>
      )}

      {data.liveWatch && (
        <div className="mb-4 rounded-lg border border-slate-800 bg-slate-900/80 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div className="flex items-center gap-2">
              <span className="text-[11px] uppercase tracking-wider text-slate-500 font-medium">
                Live Watch
              </span>
              <span
                className={`rounded-md px-2 py-0.5 text-[11px] font-bold ${
                  data.liveWatch.status === 'ACTIVE'
                    ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                    : data.liveWatch.status === 'ERROR'
                      ? 'bg-red-500/15 text-red-300 border border-red-500/30'
                      : 'bg-slate-700/50 text-slate-400 border border-slate-600'
                }`}
              >
                {data.liveWatch.status}
              </span>
              {data.liveWatch.newSignalsToday > 0 && (
                <span className="rounded-md bg-cyan-500/15 border border-cyan-500/30 px-2 py-0.5 text-[11px] font-bold text-cyan-300">
                  NEW {data.liveWatch.newSignalsToday}
                </span>
              )}
            </div>
            <div className="text-xs text-slate-500">
              Auto scan every 30 min · 09:30–15:30 IST · email only NEW
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
            <div>
              <div className="text-slate-500">Last Automatic Scan</div>
              <div className="text-slate-200 mt-0.5">{data.liveWatch.lastAutomaticScan || '—'}</div>
            </div>
            <div>
              <div className="text-slate-500">Next Scheduled Scan</div>
              <div className="text-slate-200 mt-0.5">{data.liveWatch.nextScheduledScan || '—'}</div>
            </div>
            <div>
              <div className="text-slate-500">Last Scan Status</div>
              <div className="text-slate-200 mt-0.5">{data.liveWatch.lastScanStatus || '—'}</div>
            </div>
            <div>
              <div className="text-slate-500">New Signals Today</div>
              <div className="text-cyan-300 font-semibold mt-0.5">{data.liveWatch.newSignalsToday}</div>
            </div>
            <div>
              <div className="text-slate-500">Emails Sent Today</div>
              <div className="text-emerald-300 font-semibold mt-0.5">{data.liveWatch.emailsSentToday}</div>
            </div>
          </div>
          {data.liveWatch.lastError ? (
            <div className="mt-3 text-xs text-red-400/90 border-t border-slate-800 pt-2">
              {data.liveWatch.lastError}
            </div>
          ) : null}
        </div>
      )}

      {data.newTodayEvents && data.newTodayEvents.length > 0 && (
        <>
          <h2 className={`${sectionTitle} text-cyan-400`}>NEW TODAY — AI opportunity events</h2>
          <div className={tableWrap + ' mb-4'}>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}></th>
                  <th className={thClass}>Detected (IST)</th>
                  <th className={thClass}>Ticker</th>
                  <th className={thClass}>Score</th>
                  <th className={thClass}>Signal</th>
                  <th className={thClass}>Groups</th>
                  <th className={thClass}>Entry</th>
                  <th className={thClass}>SL</th>
                  <th className={thClass}>Target</th>
                  <th className={thClass}>Qty</th>
                  <th className={thClass}>Risk</th>
                  <th className={thClass}>Email</th>
                </tr>
              </thead>
              <tbody>
                {data.newTodayEvents.map((ev) => (
                  <tr key={ev.eventId} className="border-l-[3px] border-l-cyan-500/60">
                    <td className={tdClass}>
                      <span className="rounded bg-cyan-500/20 px-1.5 py-0.5 text-[10px] font-bold text-cyan-300">
                        NEW
                      </span>
                    </td>
                    <td className={tdClass}>{ev.detectedAt}</td>
                    <td className={`${tdClass} font-semibold text-slate-100`}>{ev.ticker}</td>
                    <td className={tdClass}>{fmtNum(ev.score, 0)}</td>
                    <td className={tdClass}>{ev.signal}</td>
                    <td className={tdClass}>{ev.groupsMet ?? '—'}</td>
                    <td className={tdClass}>{fmtInr(ev.entry ?? undefined)}</td>
                    <td className={tdClass}>{fmtInr(ev.sl ?? undefined)}</td>
                    <td className={tdClass}>{fmtInr(ev.target ?? undefined)}</td>
                    <td className={tdClass}>{ev.qty ?? '—'}</td>
                    <td className={tdClass}>{fmtInr(ev.risk ?? undefined, 0)}</td>
                    <td className={tdClass}>
                      <span
                        className={
                          ev.emailStatus === 'SENT'
                            ? 'text-emerald-400'
                            : ev.emailStatus === 'FAILED'
                              ? 'text-red-400'
                              : 'text-amber-400'
                        }
                      >
                        {ev.emailStatus}
                      </span>
                      {ev.emailStatus === 'FAILED' && ev.emailError ? (
                        <div className="text-[10px] text-red-400/80 mt-0.5">{ev.emailError}</div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!data.scanAvailable ? (
        <div className="rounded-lg border border-amber-800/40 bg-amber-900/10 p-4 text-amber-200 text-sm">
          {data.noStrongBuyMessage || data.scanError || 'No scan results yet.'}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-2">
            <KpiCard
              label="STRONG BUYS"
              value={String(kpis.strongBuys)}
              sub="composite ≥75, 4+ groups"
              valueClass={kpis.strongBuys > 0 ? 'text-emerald-400' : 'text-slate-500'}
            />
            <KpiCard
              label="EXIT FLAGS"
              value={String(kpis.exitFlags)}
              sub="open positions weakening"
              valueClass={kpis.exitFlags > 0 ? 'text-red-400' : 'text-slate-500'}
            />
            <KpiCard label="WATCHLIST" value={String(kpis.watchlist)} sub="score 65+, not converged" valueClass="text-blue-400" />
            <KpiCard label="UNIVERSE" value={String(kpis.universe)} sub="passed liquidity filter" />
            <KpiCard
              label="TOP SECTOR"
              value={kpis.topSector}
              sub={`${fmtPct(kpis.topSectorScore)} 1M`}
              valueClass={kpis.topSectorScore > 0 ? 'text-emerald-400' : 'text-amber-400'}
            />
          </div>

          {data.exits.length > 0 && (
            <>
              <h2 className={`${sectionTitle} text-red-400`}>
                EXIT SIGNALS — Open positions with weakening scores
              </h2>
              <div className="space-y-2 mb-4">
                {data.exits.map((r) => (
                  <div
                    key={r.ticker}
                    className="rounded-lg border border-red-500/30 border-l-[3px] border-l-red-500 bg-red-500/5 p-4"
                  >
                    <div className="flex flex-wrap justify-between gap-3">
                      <div>
                        <span className="text-red-400 font-bold text-xs tracking-wide mr-2">EXIT</span>
                        <span className="text-slate-100 font-bold text-base">{r.ticker}</span>
                        <span className="text-slate-500 text-sm ml-2">{r.companyName.slice(0, 36)}</span>
                      </div>
                      <div className="flex gap-4 text-xs text-slate-400">
                        <span>
                          Score <b className="text-red-400">{fmtNum(r.compositeScore, 0)}</b>
                        </span>
                        <span>
                          Current P&L{' '}
                          <b className={pnlClass(r.currentPnlPct ?? 0)}>
                            {r.currentPnlPct != null ? fmtPct(r.currentPnlPct) : '—'}
                          </b>
                        </span>
                        <span>
                          CMP <b className="text-slate-200">{fmtInr(r.currentPrice)}</b>
                        </span>
                      </div>
                    </div>
                    <div className="text-sm text-slate-500 mt-2">
                      {r.bearSignals.slice(0, 3).join(' · ') || 'Multiple weak signals'}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {data.topOpportunities.length > 0 ? (
            <>
              <h2 className={sectionTitle}>Top Opportunities</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                {data.topOpportunities.map((row) => (
                  <OpportunityCard
                    key={row.ticker}
                    row={row}
                    onAddPaperTrade={handleAddPaperTrade}
                    busy={busy}
                  />
                ))}
              </div>

              {data.strongBuys.length > 3 && (
                <h2 className={`${sectionTitle} mt-4`}>All Strong Buys</h2>
              )}

              <div className={tableWrap}>
                <table className={tableClass}>
                  <thead>
                    <tr>
                      {[
                        'Ticker',
                        'Company',
                        'Sector',
                        '★',
                        'Score',
                        'Groups',
                        'Entry ₹',
                        'SL ₹',
                        'Target ₹',
                        'R:R',
                        'Qty',
                        'Risk ₹',
                        'Return %',
                        '1M %',
                        'RSI',
                        'vs Nifty',
                        'Catalyst',
                      ].map((h) => (
                        <th key={h} className={thClass}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.strongBuys.map((r) => (
                      <tr key={r.ticker}>
                        <td className={`${tdClass} font-medium`}>{r.ticker}</td>
                        <td className={tdClass}>{r.company}</td>
                        <td className={tdClass}>{r.sector}</td>
                        <td className={tdClass}>{r.stars}</td>
                        <td className={`${tdClass} ${scoreClass(r.score)}`}>{fmtNum(r.score, 1)}</td>
                        <td className={tdClass}>{r.groups}/5</td>
                        <td className={tdClass}>{fmtInr(r.entry)}</td>
                        <td className={tdClass}>{fmtInr(r.stopLoss)}</td>
                        <td className={tdClass}>{fmtInr(r.target)}</td>
                        <td className={tdClass}>{fmtNum(r.rrRatio, 2)}</td>
                        <td className={tdClass}>{r.qty}</td>
                        <td className={tdClass}>{fmtInr(r.riskInr, 0)}</td>
                        <td className={`${tdClass} text-emerald-400`}>
                          {isFiniteNumber(r.expectedReturnPct)
                            ? `+${fmtNum(r.expectedReturnPct, 2)}%`
                            : '—'}
                        </td>
                        <td className={`${tdClass} ${pnlClass(r.ret1m)}`}>{fmtPct(r.ret1m)}</td>
                        <td className={tdClass}>{fmtNum(r.rsi, 0)}</td>
                        <td className={`${tdClass} ${pnlClass(r.rsVsNifty60d)}`}>{fmtPct(r.rsVsNifty60d)}</td>
                        <td className={tdClass}>{r.catalyst}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900">
                <button
                  type="button"
                  onClick={() => setShowQaExpander((v) => !v)}
                  className="w-full text-left px-4 py-3 text-sm font-semibold text-slate-200 hover:bg-slate-800/50"
                >
                  {showQaExpander ? '▾' : '▸'} Add any Strong Buy to Paper Trades
                </button>
                {showQaExpander && (
                  <div className="px-4 pb-4 flex flex-wrap items-end gap-3">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Select ticker</label>
                      <select
                        className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100"
                        value={qaTicker}
                        onChange={(e) => setQaTicker(e.target.value)}
                      >
                        {strongBuyTickers.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    </div>
                    <button
                      type="button"
                      disabled={busy || !qaTicker}
                      onClick={() => handleAddPaperTrade(qaTicker, 'All Strong Buys')}
                      className="rounded-lg border border-emerald-600/50 bg-emerald-700/80 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
                    >
                      Add to Paper Trades
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-4 text-slate-300 text-sm mt-4">
              {data.noStrongBuyMessage}
            </div>
          )}

          {data.watchlist.length > 0 && (
            <>
              <h2 className={sectionTitle}>Watchlist — High score, awaiting convergence</h2>
              <div className={tableWrap}>
                <table className={tableClass}>
                  <thead>
                    <tr>
                      {[
                        'Ticker',
                        'Company',
                        'Sector',
                        'Score',
                        'Groups',
                        'Action',
                        'CMP ₹',
                        'RSI',
                        '1M %',
                        'vs Nifty',
                        'Key Signal',
                      ].map((h) => (
                        <th key={h} className={thClass}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.watchlist.map((r) => (
                      <tr key={r.ticker}>
                        <td className={`${tdClass} font-medium`}>{r.ticker}</td>
                        <td className={tdClass}>{r.company}</td>
                        <td className={tdClass}>{r.sector}</td>
                        <td className={`${tdClass} ${scoreClass(r.score)}`}>{fmtNum(r.score, 1)}</td>
                        <td className={tdClass}>{r.groups}/5</td>
                        <td className={tdClass}>{r.action}</td>
                        <td className={tdClass}>{fmtInr(r.cmp)}</td>
                        <td className={tdClass}>{fmtNum(r.rsi, 0)}</td>
                        <td className={`${tdClass} ${pnlClass(r.ret1m)}`}>{fmtPct(r.ret1m)}</td>
                        <td className={`${tdClass} ${pnlClass(r.rsVsNifty60d)}`}>{fmtPct(r.rsVsNifty60d)}</td>
                        <td className={tdClass}>{r.keySignal}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {data.sectorStrength.length > 0 && (
            <>
              <h2 className={sectionTitle}>Sector Strength</h2>
              <div className={tableWrap}>
                <table className={tableClass}>
                  <thead>
                    <tr>
                      {['Sector', 'Stocks', '1M Momentum %', 'Avg Score', 'Top Stock Score'].map((h) => (
                        <th key={h} className={thClass}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.sectorStrength.map((r) => (
                      <tr key={r.sector}>
                        <td className={tdClass}>{r.sector}</td>
                        <td className={tdClass}>{r.stocks}</td>
                        <td className={`${tdClass} ${pnlClass(r.momentum1mPct)}`}>
                          {fmtPct(r.momentum1mPct, true)}
                        </td>
                        <td className={`${tdClass} ${scoreClass(r.avgScore)}`}>{fmtNum(r.avgScore, 1)}</td>
                        <td className={`${tdClass} ${scoreClass(r.topStockScore)}`}>
                          {fmtNum(r.topStockScore, 1)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}

      <h2 className={`${sectionTitle} mt-8`}>AI Paper Trade Tracker</h2>
      <p className="text-slate-500 text-sm mb-4">
        Manual paper trades from the scanner. Live CMP refreshes every 3 min. TP/SL status flagged
        automatically.
      </p>

      {data.paperTrades.length === 0 ? (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-slate-400 text-sm">
          No paper trades yet. Click Add Paper Trade on any Strong Buy card above to start tracking.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-4">
            <KpiCard label="Total" value={String(data.paperTradeSummary.total)} />
            <KpiCard label="Open" value={String(data.paperTradeSummary.open)} />
            <KpiCard label="TP ✓" value={String(data.paperTradeSummary.tp)} valueClass="text-emerald-400" />
            <KpiCard label="SL ✗" value={String(data.paperTradeSummary.sl)} valueClass="text-red-400" />
            <KpiCard
              label="Hit Rate"
              value={
                isFiniteNumber(data.paperTradeSummary.hitRate)
                  ? `${fmtNum(data.paperTradeSummary.hitRate, 1)}%`
                  : '—'
              }
            />
            <KpiCard
              label="Total P&L"
              value={
                data.paperTradeSummary.totalPnlInr != null
                  ? fmtInr(data.paperTradeSummary.totalPnlInr, 0)
                  : '—'
              }
              valueClass={pnlClass(data.paperTradeSummary.totalPnlInr ?? 0)}
            />
          </div>

          <div className={tableWrap}>
            <table className={tableClass}>
              <thead>
                <tr>
                  {[
                    'Date',
                    'Ticker',
                    'Score',
                    'Entry ₹',
                    'CMP ₹',
                    'SL ₹',
                    'Target ₹',
                    'Qty',
                    'Return %',
                    'P&L ₹',
                    'Days',
                    'Outcome',
                  ].map((h) => (
                    <th key={h} className={thClass}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.paperTrades.map((r) => (
                  <tr key={`${r.ticker}-${r.addedTs}`} className={paperOutcomeClass(r.outcome)}>
                    <td className={tdClass}>{r.addedDate}</td>
                    <td className={`${tdClass} font-medium`}>{r.ticker}</td>
                    <td className={tdClass}>{fmtNum(r.score, 1)}</td>
                    <td className={tdClass}>{fmtInr(r.entry)}</td>
                    <td className={tdClass}>{fmtInr(r.cmp)}</td>
                    <td className={tdClass}>{fmtInr(r.sl)}</td>
                    <td className={tdClass}>{fmtInr(r.target)}</td>
                    <td className={tdClass}>{r.qty ?? '—'}</td>
                    <td className={`${tdClass} ${pnlClass(r.returnPct)}`}>
                      {isFiniteNumber(r.returnPct)
                        ? `${r.returnPct >= 0 ? '+' : ''}${fmtNum(r.returnPct, 2)}%`
                        : '—'}
                    </td>
                    <td className={`${tdClass} ${pnlClass(r.pnlInr)}`}>
                      {r.pnlInr != null ? fmtInr(r.pnlInr, 0) : '—'}
                    </td>
                    <td className={tdClass}>{r.days}</td>
                    <td className={tdClass}>{r.outcome}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.openPaperTickers.length > 0 && (
            <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900">
              <button
                type="button"
                onClick={() => setShowExitExpander((v) => !v)}
                className="w-full text-left px-4 py-3 text-sm font-semibold text-red-300 hover:bg-slate-800/50"
              >
                {showExitExpander ? '▾' : '▸'} Exit / Close a paper trade
              </button>
              {showExitExpander && (
                <div className="px-4 pb-4 flex flex-wrap items-end gap-3">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Select ticker to exit</label>
                    <select
                      className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100 min-w-[180px]"
                      value={exitTicker}
                      onChange={(e) => setExitTicker(e.target.value)}
                    >
                      {data.openPaperTickers.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Exit price (0 = live CMP)</label>
                    <input
                      type="number"
                      min={0}
                      step={0.5}
                      className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100 w-40"
                      value={exitPrice || ''}
                      onChange={(e) => setExitPrice(parseFloat(e.target.value) || 0)}
                    />
                  </div>
                  <button
                    type="button"
                    disabled={busy || !exitTicker}
                    onClick={() =>
                      runAction(() =>
                        aiScannerService.exitPaperTrade(exitTicker, { exitPrice }),
                      )
                    }
                    className="rounded-lg border border-red-500/40 bg-red-600/70 px-4 py-2 text-sm font-semibold text-white hover:bg-red-600 disabled:opacity-50"
                  >
                    Exit
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {data.footerNote ? (
        <p className="text-xs text-slate-500 mt-6">{data.footerNote}</p>
      ) : null}
    </div>
  );
};

export default AIScanner;
