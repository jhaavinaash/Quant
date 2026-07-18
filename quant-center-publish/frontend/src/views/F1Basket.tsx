import { useCallback, useEffect, useState } from 'react';
import { f1BasketService } from '../services/f1BasketService';
import { BasketDeployConfirmation, DeploySelectedRequest, DeploySlotSelection, F1BasketSnapshot } from '../types/f1Basket';

const fmtInr = (v: number, digits = 0) =>
  `₹${v.toLocaleString('en-IN', { maximumFractionDigits: digits })}`;

const fmtPct = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;

const sectionTitle = 'text-base font-semibold text-slate-100 mb-3 mt-6';
const tableWrap = 'overflow-x-auto rounded-lg border border-slate-800';
const tableClass = 'min-w-max w-full text-sm bg-slate-900';
const thClass = 'p-3 text-left text-slate-400 border-b border-slate-800 whitespace-nowrap';
const tdClass = 'p-3 border-b border-slate-800/60 text-slate-300 whitespace-nowrap';

const F1Basket = () => {
  const [snapshot, setSnapshot] = useState<F1BasketSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deployConfirm, setDeployConfirm] = useState<BasketDeployConfirmation | null>(null);
  const [deploySelections, setDeploySelections] = useState<DeploySlotSelection[]>([]);
  const [showDeployModal, setShowDeployModal] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const data = await f1BasketService.getSnapshot();
      setSnapshot(data);
      setError(null);
    } catch {
      setError('Failed to load F1 Basket.');
    } finally {
      setLoading(false);
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const runBasketAction = async (
    fn: () => Promise<{ snapshot?: F1BasketSnapshot; message: string }>
  ) => {
    setBusy(true);
    try {
      const result = await fn();
      if (result.snapshot) setSnapshot(result.snapshot);
      if (result.message) setError(null);
    } catch {
      setError('Action failed.');
    } finally {
      setBusy(false);
    }
  };

  const openDeployModal = async (basketId: string) => {
    setBusy(true);
    try {
      const conf = await f1BasketService.getDeployConfirmation(basketId);
      const snap = snapshot?.preview;
      const selections: DeploySlotSelection[] = (snap?.constituents ?? conf.constituents)
        .filter((c) => !c.slotResolved)
        .map((c) => ({
          ticker: c.ticker,
          execute: (c.recommendedBuyQty ?? c.quantity ?? 0) > 0 || (c.currentBrokerQty ?? 0) > 0,
          adoptExistingQty: 0,
        }));
      setDeploySelections(selections);
      setDeployConfirm(conf);
      setShowDeployModal(true);
    } catch {
      setError('Cannot deploy — check basket eligibility and broker connection.');
    } finally {
      setBusy(false);
    }
  };

  const confirmDeploy = async () => {
    if (!deployConfirm) return;
    setShowDeployModal(false);
    await runBasketAction(async () => {
      const body: DeploySelectedRequest = {
        basketId: deployConfirm.basketId,
        selections: deploySelections,
      };
      const r = await f1BasketService.deploySelected(body);
      return { snapshot: r.snapshot, message: r.message };
    });
    setDeployConfirm(null);
    setDeploySelections([]);
  };

  const updateSelection = (ticker: string, patch: Partial<DeploySlotSelection>) => {
    setDeploySelections((prev) =>
      prev.map((s) => (s.ticker === ticker ? { ...s, ...patch } : s))
    );
  };

  if (loading && !snapshot) {
    return <div className="p-8 text-slate-400">Loading F1 Basket…</div>;
  }
  if (error && !snapshot) {
    return <div className="p-8 text-red-500">{error}</div>;
  }

  const data = snapshot!;
  const s = data.strategy;
  const e = data.eligibility;
  const p = data.preview;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">F1 Basket</h1>
          <p className="text-slate-400 text-sm mt-1">
            Smallcase-like basket portfolio on top of F1 BUY + PortfolioRank · Managed at basket level
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => load()}
            className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-50"
          >
            Refresh
          </button>
          <button
            type="button"
            disabled={busy || !e.ready}
            onClick={() => runBasketAction(async () => ({ snapshot: await f1BasketService.createPreview(), message: '' }))}
            className="rounded-lg border border-emerald-600/50 bg-emerald-900/30 px-4 py-2 text-sm text-emerald-300 hover:bg-emerald-900/50 disabled:opacity-50"
          >
            Create Preview
          </button>
          <button
            type="button"
            disabled={busy || !e.ready || p?.status === 'DEPLOYING' || p?.status === 'ACTIVE'}
            onClick={() => runBasketAction(async () => ({ snapshot: await f1BasketService.rebuildPreview(), message: '' }))}
            className="rounded-lg border border-cyan-600/50 bg-cyan-900/30 px-4 py-2 text-sm text-cyan-300 hover:bg-cyan-900/50 disabled:opacity-50"
          >
            Rebuild Preview
          </button>
          {(p?.deployAllowed || p?.canDeploySelected) ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => openDeployModal(p!.basketId)}
              className="rounded-lg border border-violet-600/50 bg-violet-900/30 px-4 py-2 text-sm text-violet-300 hover:bg-violet-900/50 disabled:opacity-50"
            >
              {p?.status === 'DEPLOYING' ? 'Deploy More Slots' : 'Deploy Selected'}
            </button>
          ) : null}
          {p?.status === 'DEPLOYING' ? (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  runBasketAction(async () => ({
                    snapshot: (await f1BasketService.syncBasket(p.basketId)).snapshot,
                    message: '',
                  }))
                }
                className="rounded-lg border border-blue-600/50 bg-blue-900/30 px-4 py-2 text-sm text-blue-300 hover:bg-blue-900/50 disabled:opacity-50"
              >
                Sync Order Status
              </button>
              {p.canRetryFailed ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    runBasketAction(async () => ({
                      snapshot: (await f1BasketService.retryFailed(p.basketId)).snapshot,
                      message: '',
                    }))
                  }
                  className="rounded-lg border border-orange-600/50 bg-orange-900/30 px-4 py-2 text-sm text-orange-300 hover:bg-orange-900/50 disabled:opacity-50"
                >
                  Retry Failed Orders
                </button>
              ) : null}
            </>
          ) : null}
          {(p?.status === 'ACTIVE' || p?.status === 'EXITING' || p?.status === 'EXIT_PENDING') && p ? (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  runBasketAction(async () => ({
                    snapshot: (await f1BasketService.syncValuation(p.basketId)).snapshot,
                    message: '',
                  }))
                }
                className="rounded-lg border border-blue-600/50 bg-blue-900/30 px-4 py-2 text-sm text-blue-300 hover:bg-blue-900/50 disabled:opacity-50"
              >
                Sync Basket
              </button>
              {p.canManualExit ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    if (window.confirm('Manual emergency exit — submit whole-basket SELL?')) {
                      runBasketAction(async () => ({
                        snapshot: (await f1BasketService.manualExit(p.basketId)).snapshot,
                        message: '',
                      }));
                    }
                  }}
                  className="rounded-lg border border-red-600/50 bg-red-900/30 px-4 py-2 text-sm text-red-300 hover:bg-red-900/50 disabled:opacity-50"
                >
                  Manual Exit Basket
                </button>
              ) : null}
              {p.canRetryFailedExits ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    runBasketAction(async () => ({
                      snapshot: (await f1BasketService.retryFailedExits(p.basketId)).snapshot,
                      message: '',
                    }))
                  }
                  className="rounded-lg border border-orange-600/50 bg-orange-900/30 px-4 py-2 text-sm text-orange-300 hover:bg-orange-900/50 disabled:opacity-50"
                >
                  Retry Failed Exits
                </button>
              ) : null}
            </>
          ) : null}
        </div>
      </div>

      {data.message ? (
        <div className="mb-4 rounded-lg border border-amber-800/40 bg-amber-900/15 px-4 py-2 text-sm text-amber-200">
          {data.message}
        </div>
      ) : null}

      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 mb-4">
        <div className="text-sm font-semibold text-slate-200 mb-2">Locked Strategy</div>
        <div className="flex flex-wrap gap-3 text-xs text-slate-400">
          <span>{s.basketSize} Stocks</span>
          <span>Equal Weight</span>
          <span>+{s.profitTargetPct}% Basket Target</span>
          <span>-{s.hardStopPct}% Basket Stop</span>
          <span>{s.buyCostPct}% Buy Cost</span>
          <span>{s.sellCostPct}% Sell Cost</span>
          <span>Capital {fmtInr(s.initialCapital)}</span>
        </div>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 mb-4">
        <div className="text-sm font-semibold text-slate-200 mb-3">Eligibility</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>
            <div className="text-slate-500 text-xs">F1 BUY Candidates</div>
            <div className="text-lg font-semibold text-slate-100">
              {e.availableCandidates} / {e.requiredConstituents}
            </div>
          </div>
          <div>
            <div className="text-slate-500 text-xs">Basket Status</div>
            <div
              className={`text-lg font-semibold ${
                e.ready ? 'text-emerald-400' : 'text-amber-400'
              }`}
            >
              {e.status}
            </div>
          </div>
          <div>
            <div className="text-slate-500 text-xs">Missing Candidates</div>
            <div className="text-lg font-semibold text-slate-100">{e.missingCandidates}</div>
          </div>
          <div>
            <div className="text-slate-500 text-xs">F1 Decision Time</div>
            <div className="text-sm text-slate-300">{e.f1DecisionTimestamp || '—'}</div>
          </div>
        </div>
      </div>

      <h2 className={sectionTitle}>Top F1 BUY Candidates (PortfolioRank order)</h2>
      <div className={tableWrap + ' mb-6'}>
        <table className={tableClass}>
          <thead>
            <tr>
              <th className={thClass}>#</th>
              <th className={thClass}>Ticker</th>
              <th className={thClass}>PortfolioRank</th>
              <th className={thClass}>Action</th>
              <th className={thClass}>Technical</th>
              <th className={thClass}>Sector</th>
              <th className={thClass}>Business</th>
              <th className={thClass}>Ref Price</th>
              <th className={thClass}>Held</th>
            </tr>
          </thead>
          <tbody>
            {e.topCandidates.map((c, i) => (
              <tr key={c.ticker}>
                <td className={tdClass}>{i + 1}</td>
                <td className={tdClass + ' font-semibold text-slate-100'}>{c.ticker}</td>
                <td className={tdClass}>{c.portfolioRank}</td>
                <td className={tdClass}>{c.action}</td>
                <td className={tdClass}>{c.technicalState}</td>
                <td className={tdClass}>{c.sectorState}</td>
                <td className={tdClass}>{c.businessGate}</td>
                <td className={tdClass}>{fmtInr(c.referencePrice, 2)}</td>
                <td className={tdClass}>
                  {c.heldGlobally ? (
                    <span className="text-amber-400">YES</span>
                  ) : (
                    <span className="text-slate-500">no</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {p ? (
        <>
          <h2 className={sectionTitle}>Basket Preview</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-sm">
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
              <div className="text-slate-500 text-xs">Status</div>
              <div className="text-slate-100 font-semibold">{p.status}</div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
              <div className="text-slate-500 text-xs">Preview Stale</div>
              <div className={p.previewStale ? 'text-amber-400' : 'text-emerald-400'}>
                {p.previewStale ? 'YES' : 'no'}
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
              <div className="text-slate-500 text-xs">Basket Start Value</div>
              <div className="text-slate-100">{fmtInr(p.basketStartValue)}</div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
              <div className="text-slate-500 text-xs">Trigger</div>
              <div className="text-slate-100">{p.currentTrigger}</div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
              <div className="text-slate-500 text-xs">Target / Stop</div>
              <div className="text-emerald-400">{fmtInr(p.targetValue)}</div>
              <div className="text-red-400">{fmtInr(p.stopValue)}</div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
              <div className="text-slate-500 text-xs">Gross / Net Value</div>
              <div className="text-slate-100">{fmtInr(p.grossMarketValue)}</div>
              <div className="text-slate-400">{fmtInr(p.netLiquidationValue)}</div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
              <div className="text-slate-500 text-xs">Basket Return</div>
              <div className={p.basketReturnPct >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                {fmtPct(p.basketReturnPct)}
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
              <div className="text-slate-500 text-xs">Est. Buy / Exit Cost</div>
              <div className="text-slate-300">{fmtInr(p.estimatedBuyCost)}</div>
              <div className="text-slate-400">{fmtInr(p.estimatedExitCost)}</div>
            </div>
          </div>
          {p.heldConflicts.length > 0 ? (
            <div className="mb-4 text-sm text-amber-300">
              Existing holdings detected: {p.heldConflicts.join(', ')} — use adoption controls at deploy to attribute shares into F1 Basket.
            </div>
          ) : null}
          {p.deploymentIncomplete ? (
            <div className="mb-4 rounded-lg border border-red-800/40 bg-red-900/15 px-4 py-2 text-sm text-red-200">
              DEPLOYMENT INCOMPLETE — {p.resolvedSlots ?? p.deploymentProgress?.resolved ?? 0} / {p.maxSlots ?? 12} slots resolved
            </div>
          ) : null}
          {p.status === 'ACTIVE' ? (
            <div className="mb-4 rounded-lg border border-emerald-800/40 bg-emerald-900/15 px-4 py-2 text-sm text-emerald-200">
              ACTIVE basket — started {p.startedAt || '—'}
            </div>
          ) : null}
          {p.deploymentProgress && p.status === 'DEPLOYING' ? (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4 text-sm">
              <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
                <div className="text-slate-500 text-xs">Complete</div>
                <div className="text-emerald-400 font-semibold">
                  {p.deploymentProgress.complete} / {p.deploymentProgress.total}
                </div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
                <div className="text-slate-500 text-xs">Submitted</div>
                <div className="text-slate-100">{p.deploymentProgress.submitted}</div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
                <div className="text-slate-500 text-xs">Pending</div>
                <div className="text-slate-100">{p.deploymentProgress.pending}</div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
                <div className="text-slate-500 text-xs">Partial</div>
                <div className="text-amber-400">{p.deploymentProgress.partial}</div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
                <div className="text-slate-500 text-xs">Failed</div>
                <div className="text-red-400">{p.deploymentProgress.failed}</div>
              </div>
            </div>
          ) : null}
          {p.deployBlockReason && p.status === 'READY' ? (
            <div className="mb-4 text-sm text-amber-300">{p.deployBlockReason}</div>
          ) : null}
          <div className={tableWrap}>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>#</th>
                  <th className={thClass}>Ticker</th>
                  <th className={thClass}>Rank</th>
                  <th className={thClass}>Held Qty</th>
                  <th className={thClass}>Exposure</th>
                  <th className={thClass}>Target</th>
                  <th className={thClass}>Rec BUY Qty</th>
                  <th className={thClass}>Rec BUY Value</th>
                  <th className={thClass}>Attributed</th>
                  <th className={thClass}>Status</th>
                  <th className={thClass}>Ref</th>
                  <th className={thClass}>Current</th>
                  <th className={thClass}>Value</th>
                  {(p.status === 'DEPLOYING' || p.status === 'ACTIVE') && (
                    <>
                      <th className={thClass}>Order ID</th>
                      <th className={thClass}>Fill</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {p.constituents.map((c) => (
                  <tr key={c.ticker}>
                    <td className={tdClass}>{c.selectionOrder}</td>
                    <td className={tdClass + ' font-semibold'}>{c.ticker}</td>
                    <td className={tdClass}>{c.portfolioRank}</td>
                    <td className={tdClass}>{c.currentBrokerQty ?? 0}</td>
                    <td className={tdClass}>{fmtInr(c.currentExposure ?? 0)}</td>
                    <td className={tdClass}>{fmtInr(c.targetSlotExposure ?? c.grossAllocation)}</td>
                    <td className={tdClass}>{c.recommendedBuyQty ?? c.quantity}</td>
                    <td className={tdClass}>{fmtInr(c.recommendedBuyValue ?? c.grossAllocation)}</td>
                    <td className={tdClass}>{c.basketAttributedQty ?? 0}</td>
                    <td className={tdClass}>
                      {c.slotResolved ? (
                        <span className="text-emerald-400">resolved</span>
                      ) : (
                        <span className="text-slate-500">pending</span>
                      )}
                    </td>
                    <td className={tdClass}>{fmtInr(c.referencePrice, 2)}</td>
                    <td className={tdClass}>{fmtInr(c.currentPrice, 2)}</td>
                    <td className={tdClass}>{fmtInr(c.currentValue)}</td>
                    {(p.status === 'DEPLOYING' || p.status === 'ACTIVE') && (
                      <>
                        <td className={tdClass}>{c.brokerOrderId || '—'}</td>
                        <td className={tdClass}>{c.fillStatus || '—'}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {showDeployModal && deployConfirm ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-slate-700 bg-slate-900 p-6">
            <h2 className="text-lg font-semibold text-slate-100 mb-4">Deploy Selected Slots</h2>
            <p className="text-sm text-slate-400 mb-4">
              Choose which recommended BUY/top-up orders to execute now. For existing holdings, set how many shares to adopt into F1 Basket.
            </p>
            <div className="grid grid-cols-2 gap-3 text-sm mb-4">
              <div><span className="text-slate-500">Basket ID</span><div className="text-slate-200 text-xs break-all">{deployConfirm.basketId}</div></div>
              <div><span className="text-slate-500">Capital</span><div className="text-slate-200">{fmtInr(deployConfirm.capital)}</div></div>
              <div><span className="text-slate-500">Stocks</span><div className="text-slate-200">{deployConfirm.stockCount}</div></div>
              <div><span className="text-slate-500">Broker</span><div className="text-slate-200">{deployConfirm.broker}</div></div>
              <div><span className="text-slate-500">Est. Investment</span><div className="text-slate-200">{fmtInr(deployConfirm.totalEstimatedInvestment)}</div></div>
              <div><span className="text-slate-500">Est. Buy Cost</span><div className="text-slate-200">{fmtInr(deployConfirm.estimatedBuyCost)}</div></div>
              <div><span className="text-slate-500">Cash Remaining</span><div className="text-slate-200">{fmtInr(deployConfirm.cashRemaining)}</div></div>
            </div>
            <table className={tableClass + ' mb-4'}>
              <thead>
                <tr>
                  <th className={thClass}>Execute</th>
                  <th className={thClass}>Ticker</th>
                  <th className={thClass}>Held</th>
                  <th className={thClass}>Adopt Qty</th>
                  <th className={thClass}>Rec BUY</th>
                  <th className={thClass}>Est. Value</th>
                </tr>
              </thead>
              <tbody>
                {deploySelections.map((sel) => {
                  const c = deployConfirm.constituents.find((x) => x.ticker === sel.ticker);
                  const maxAdopt = Math.floor(c?.currentBrokerQty ?? 0);
                  return (
                    <tr key={sel.ticker}>
                      <td className={tdClass}>
                        <input
                          type="checkbox"
                          checked={sel.execute}
                          onChange={(e) => updateSelection(sel.ticker, { execute: e.target.checked })}
                        />
                      </td>
                      <td className={tdClass}>{sel.ticker}</td>
                      <td className={tdClass}>{maxAdopt}</td>
                      <td className={tdClass}>
                        <input
                          type="number"
                          min={0}
                          max={maxAdopt}
                          value={sel.adoptExistingQty}
                          disabled={!sel.execute || maxAdopt <= 0}
                          onChange={(e) =>
                            updateSelection(sel.ticker, {
                              adoptExistingQty: Math.min(maxAdopt, Math.max(0, Number(e.target.value) || 0)),
                            })
                          }
                          className="w-16 rounded border border-slate-700 bg-slate-800 px-2 py-1 text-slate-200"
                        />
                      </td>
                      <td className={tdClass}>{c?.recommendedBuyQty ?? c?.quantity ?? 0}</td>
                      <td className={tdClass}>{fmtInr(c?.recommendedBuyValue ?? c?.grossAllocation ?? 0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowDeployModal(false)} className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-300">Cancel</button>
              <button
                type="button"
                disabled={busy || !deploySelections.some((s) => s.execute)}
                onClick={confirmDeploy}
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm text-white hover:bg-violet-500 disabled:opacity-50"
              >
                Deploy Selected
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default F1Basket;
