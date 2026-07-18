"""AI Opportunity Scanner — wraps dashboard/app_ai.py Tab 8 (AI Intelligence).

Calls production core.ai_scanner for scan/score/rank. Paper-trade helpers mirror
app_ai.py inline functions against data/ai_paper_trades.csv.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from app.core.config import settings
from app.schemas.ai_scanner import (
    AIScannerActionResult,
    AIScannerSnapshot,
    AddPaperTradeRequest,
    ExitPaperTradeRequest,
    LiveWatchStatus,
    NewTodayEventRow,
    PaperTradeRow,
    PaperTradeSummary,
    ScanResultRow,
    ScannerKpis,
    SectorStrengthRow,
    StrongBuyTableRow,
    WatchlistTableRow,
)
from app.services.ai_scanner_event_store import get_event_store
from app.services.ai_scanner_market_session import ist_trading_date
from app.services.ai_scanner_opportunity_pipeline import process_qualifying_opportunities
from app.services.ai_scanner_watcher import get_watch_status

SCAN_TTL_SECONDS = 3600
PAPER_CMP_TTL_SECONDS = 180

_scan_cache: Optional[dict[str, Any]] = None
_scan_cached_at: float = 0.0
_paper_cmp_cache: dict[str, tuple[float, dict[str, float]]] = {}


def _ensure_quant_path() -> Path:
    root = Path(settings.QUANT_BASE_DIR)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def _paper_trades_path() -> Path:
    return _ensure_quant_path() / "data" / "ai_paper_trades.csv"


def _trades_log_path() -> Path:
    try:
        _ensure_quant_path()
        import config  # type: ignore

        val = getattr(config, "TRADES_LOG_FILE", None)
        if val:
            return Path(str(val))
    except Exception:
        pass
    return _ensure_quant_path() / "portfolio" / "trades_log.csv"


def _pt_cols() -> list[str]:
    return [
        "AddedDate",
        "AddedTS",
        "Source",
        "Ticker",
        "Score",
        "Entry",
        "SL",
        "Target",
        "Qty",
        "Risk",
        "Status",
        "ExitPrice",
        "ExitDate",
    ]


def _load_paper_trades() -> pd.DataFrame:
    path = _paper_trades_path()
    if not path.exists():
        return pd.DataFrame(columns=_pt_cols())
    try:
        df = pd.read_csv(path)
        for col in _pt_cols():
            if col not in df.columns:
                df[col] = np.nan
        return df[_pt_cols()].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=_pt_cols())


def _load_open_trades() -> pd.DataFrame:
    path = _trades_log_path()
    if not path.exists():
        return pd.DataFrame()
    try:
        from core.utils import safe_read_csv

        trades = safe_read_csv(path)
    except Exception:
        try:
            trades = pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    if trades.empty or "Status" not in trades.columns:
        return pd.DataFrame()
    return trades[trades["Status"].astype(str).str.upper() == "OPEN"].copy()


def _paper_cmp(tickers_tuple: tuple[str, ...]) -> dict[str, float]:
    if not tickers_tuple:
        return {}
    key = "|".join(sorted(tickers_tuple))
    now = time.time()
    cached = _paper_cmp_cache.get(key)
    if cached and now - cached[0] < PAPER_CMP_TTL_SECONDS:
        return cached[1]
    prices: dict[str, float] = {}
    try:
        raw = yf.download(
            list(tickers_tuple),
            period="2d",
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )
        if len(tickers_tuple) == 1:
            t = tickers_tuple[0]
            try:
                prices[t] = float(raw["Close"].dropna().iloc[-1])
            except Exception:
                pass
        else:
            for t in tickers_tuple:
                try:
                    prices[t] = float(raw[t]["Close"].dropna().iloc[-1])
                except Exception:
                    pass
    except Exception:
        pass
    _paper_cmp_cache[key] = (now, prices)
    return prices


def _save_paper_trade_from_result(result_row: ScanResultRow, source: str) -> bool:
    df = _load_paper_trades()
    if not df.empty:
        if not df[(df["Ticker"] == result_row.ticker) & (df["Status"] == "OPEN")].empty:
            return False
    now = pd.Timestamp.now()
    new_row = {
        "AddedDate": now.strftime("%Y-%m-%d"),
        "AddedTS": now.strftime("%Y-%m-%d %H:%M:%S"),
        "Source": source,
        "Ticker": result_row.ticker,
        "Score": round(float(result_row.compositeScore), 1),
        "Entry": round(float(result_row.suggestedEntry), 2),
        "SL": round(float(result_row.suggestedStop), 2),
        "Target": round(float(result_row.suggestedTarget), 2),
        "Qty": int(result_row.suggestedQty),
        "Risk": round(float(result_row.maxRiskInr), 0),
        "Status": "OPEN",
        "ExitPrice": np.nan,
        "ExitDate": np.nan,
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    path = _paper_trades_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return True


def _exit_paper_trade(ticker: str, exit_price: Optional[float] = None) -> bool:
    path = _paper_trades_path()
    if not path.exists():
        return False
    df = pd.read_csv(path)
    mask = (df["Ticker"].astype(str) == ticker) & (df["Status"] == "OPEN")
    if not mask.any():
        return False
    idx = df[mask].index[-1]
    df["ExitPrice"] = df["ExitPrice"].astype(object)
    df["ExitDate"] = df["ExitDate"].astype(object)
    df.loc[idx, "Status"] = "EXITED"
    df.loc[idx, "ExitPrice"] = exit_price if exit_price else np.nan
    df.loc[idx, "ExitDate"] = pd.Timestamp.now().strftime("%Y-%m-%d")
    df.to_csv(path, index=False)
    return True


def _auto_exit_paper_trades() -> int:
    path = _paper_trades_path()
    if not path.exists():
        return 0
    try:
        df = pd.read_csv(path)
    except Exception:
        return 0
    open_mask = df["Status"] == "OPEN"
    if not open_mask.any():
        return 0
    for col in ["Entry", "SL", "Target", "Qty"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["ExitPrice"] = df["ExitPrice"].astype(object)
    df["ExitDate"] = df["ExitDate"].astype(object)
    open_tickers = tuple(df.loc[open_mask, "Ticker"].dropna().unique().tolist())
    live_px = _paper_cmp(open_tickers)
    if not live_px:
        return 0
    n_exited = 0
    exit_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    for idx in df[open_mask].index:
        ticker = df.loc[idx, "Ticker"]
        cmp = live_px.get(ticker, np.nan)
        if pd.isna(cmp):
            continue
        target = df.loc[idx, "Target"]
        sl = df.loc[idx, "SL"]
        if pd.notna(target) and cmp >= target:
            df.loc[idx, "Status"] = "TP ✓"
            df.loc[idx, "ExitPrice"] = round(float(cmp), 2)
            df.loc[idx, "ExitDate"] = exit_date
            n_exited += 1
        elif pd.notna(sl) and cmp <= sl:
            df.loc[idx, "Status"] = "SL ✗"
            df.loc[idx, "ExitPrice"] = round(float(cmp), 2)
            df.loc[idx, "ExitDate"] = exit_date
            n_exited += 1
    if n_exited > 0:
        df.to_csv(path, index=False)
    return n_exited


def _enrich_paper_trades(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    for col in ["Entry", "SL", "Target", "Qty", "Risk"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    open_mask = df["Status"] == "OPEN"
    open_tickers = tuple(df.loc[open_mask, "Ticker"].dropna().unique().tolist())
    live_px = _paper_cmp(open_tickers)

    def _cmp(row):
        if row["Status"] == "OPEN":
            return live_px.get(row["Ticker"], np.nan)
        ep = row.get("ExitPrice", np.nan)
        return ep if pd.notna(ep) else np.nan

    df["CMP"] = df.apply(_cmp, axis=1)
    df["Return %"] = ((df["CMP"] - df["Entry"]) / df["Entry"] * 100).round(2)
    df["P&L ₹"] = ((df["CMP"] - df["Entry"]) * df["Qty"]).round(0)
    today = pd.Timestamp.today().normalize()
    df["Days"] = (
        (today - pd.to_datetime(df["AddedDate"], dayfirst=True, errors="coerce"))
        .dt.days.fillna(0)
        .astype(int)
    )

    def _outcome(row):
        if row["Status"] in ("TP ✓", "SL ✗", "EXITED", "CLOSED"):
            return row["Status"]
        cmp = row["CMP"]
        if pd.isna(cmp):
            return "OPEN"
        if cmp >= row["Target"]:
            return "TP ✓"
        if cmp <= row["SL"]:
            return "SL ✗"
        return "OPEN"

    df["Outcome"] = df.apply(_outcome, axis=1)
    return df


def _scan_result_row(r) -> ScanResultRow:
    stars = "★" * int(r.conviction) + "☆" * (5 - int(r.conviction))
    next_display = (
        f"{r.next_event_label} {r.next_event_days}d" if r.next_event_label else ""
    )
    return ScanResultRow(
        ticker=r.ticker,
        companyName=r.company_name or "",
        sector=r.sector or "",
        action=r.action or "",
        conviction=int(r.conviction or 0),
        compositeScore=float(r.composite_score or 0),
        groupsFired=int(r.groups_fired or 0),
        trendScore=float(getattr(r, "trend_score", 50) or 50),
        momentumScore=float(getattr(r, "momentum_score", 50) or 50),
        setupScore=float(getattr(r, "setup_score", 50) or 50),
        sectorScore=float(getattr(r, "sector_score", 50) or 50),
        currentPrice=float(r.current_price or 0),
        suggestedEntry=float(r.suggested_entry or 0),
        suggestedStop=float(r.suggested_stop or 0),
        suggestedTarget=float(r.suggested_target or 0),
        suggestedQty=int(r.suggested_qty or 0),
        capitalUsed=float(getattr(r, "capital_used", 0) or 0),
        maxRiskInr=float(r.max_risk_inr or 0),
        rrRatio=float(r.rr_ratio or 0),
        expectedReturnPct=float(r.expected_return_pct or 0),
        rsi=r.rsi,
        atr14=getattr(r, "atr_14", None),
        pctFrom52wHigh=getattr(r, "pct_from_52w_high", None),
        pctFrom52wLow=getattr(r, "pct_from_52w_low", None),
        avgVolume20d=getattr(r, "avg_volume_20d", None),
        ret1m=r.ret_1m,
        ret3m=getattr(r, "ret_3m", None),
        rsVsNifty60d=r.rs_vs_nifty_60d,
        bullSignals=list(r.bull_signals or []),
        bearSignals=list(r.bear_signals or []),
        nextEventDays=r.next_event_days,
        nextEventLabel=r.next_event_label,
        isExistingPosition=bool(r.is_existing_position),
        currentPnlPct=r.current_pnl_pct,
        nextEventDisplay=next_display,
        stars=stars,
    )


def _strong_buy_table_row(r) -> StrongBuyTableRow:
    stars = "★" * int(r.conviction)
    cat = f"{r.next_event_label} {r.next_event_days}d" if r.next_event_label else "—"
    return StrongBuyTableRow(
        ticker=r.ticker,
        company=(r.company_name or "")[:28],
        sector=((r.sector or "—")[:18]),
        stars=stars,
        score=float(r.composite_score or 0),
        groups=int(r.groups_fired or 0),
        entry=float(r.suggested_entry or 0),
        stopLoss=float(r.suggested_stop or 0),
        target=float(r.suggested_target or 0),
        rrRatio=float(r.rr_ratio or 0),
        qty=int(r.suggested_qty or 0),
        riskInr=float(r.max_risk_inr or 0),
        expectedReturnPct=float(r.expected_return_pct or 0),
        ret1m=float(r.ret_1m or 0) if r.ret_1m is not None else 0.0,
        rsi=float(r.rsi or 0) if r.rsi else 0.0,
        rsVsNifty60d=float(r.rs_vs_nifty_60d or 0) if r.rs_vs_nifty_60d is not None else 0.0,
        catalyst=cat,
    )


def _watchlist_table_row(r) -> WatchlistTableRow:
    return WatchlistTableRow(
        ticker=r.ticker,
        company=(r.company_name or "")[:30],
        sector=((r.sector or "—")[:18]),
        score=float(r.composite_score or 0),
        groups=int(r.groups_fired or 0),
        action=r.action or "",
        cmp=float(r.current_price or 0),
        rsi=float(r.rsi or 0) if r.rsi else 0.0,
        ret1m=float(r.ret_1m or 0) if r.ret_1m is not None else 0.0,
        rsVsNifty60d=float(r.rs_vs_nifty_60d or 0) if r.rs_vs_nifty_60d is not None else 0.0,
        keySignal=" · ".join(r.bull_signals[:2]) if r.bull_signals else "—",
    )


def execute_production_scan(force: bool = True) -> tuple[Optional[dict[str, Any]], str]:
    """
    Production scan path shared by Rescan, live watch, and opportunity pipeline.
    Uses scan_universe() (yfinance via _bulk_history) — same as manual Rescan.
    """
    scan, err = _run_scan(force=force)
    if not scan:
        return None, err
    _ensure_quant_path()
    try:
        from core.ai_scanner import mark_existing_positions
    except Exception as exc:
        return scan, str(exc)
    open_trades = _load_open_trades()
    scan = mark_existing_positions(
        scan, open_trades if not open_trades.empty else None
    )
    return scan, err


def _run_scan(force: bool = False) -> tuple[Optional[dict[str, Any]], str]:
    global _scan_cache, _scan_cached_at
    now = time.time()
    if not force and _scan_cache is not None and now - _scan_cached_at < SCAN_TTL_SECONDS:
        return _scan_cache, ""

    _ensure_quant_path()
    try:
        from config import RESULT_CALENDAR_FILE, UNIVERSE_FILE
        from core.ai_scanner import scan_universe
        from core.utils import safe_read_csv
    except Exception as exc:
        return None, str(exc)

    try:
        universe = safe_read_csv(UNIVERSE_FILE)
        result_cal = safe_read_csv(RESULT_CALENDAR_FILE)
        scan = scan_universe(
            universe_df=universe,
            result_calendar_df=result_cal if not result_cal.empty else None,
            progress_callback=None,
        )
        _scan_cache = scan
        _scan_cached_at = now
        return scan, ""
    except Exception as exc:
        return None, str(exc)


def _lookup_scan_result(ticker: str) -> Optional[ScanResultRow]:
    if not _scan_cache or not _scan_cache.get("all_results"):
        return None
    target = ticker.strip().upper()
    for r in _scan_cache["all_results"]:
        if str(r.ticker).upper() == target:
            return _scan_result_row(r)
    return None


def _live_watch_payload() -> LiveWatchStatus:
    ws = get_watch_status()
    store = get_event_store()
    td = ist_trading_date().isoformat()
    return LiveWatchStatus(
        status=ws.status,
        lastAutomaticScan=ws.lastAutomaticScan,
        nextScheduledScan=ws.nextScheduledScan,
        lastScanStatus=ws.lastScanStatus,
        newSignalsToday=store.count_for_trading_date(td),
        emailsSentToday=store.count_emails_sent_for_trading_date(td),
        lastError=ws.lastError or "",
    )


def _new_today_payload() -> list[NewTodayEventRow]:
    store = get_event_store()
    td = ist_trading_date().isoformat()
    rows: list[NewTodayEventRow] = []
    for ev in store.list_for_trading_date(td):
        err = ev.email_error or ""
        low = err.lower()
        if "password" in low or ("smtp" in low and "@" in err):
            err = "Email delivery failed"
        rows.append(
            NewTodayEventRow(
                eventId=ev.event_id,
                detectedAt=ev.detected_at,
                ticker=ev.ticker,
                score=ev.score,
                signal=ev.signal or "",
                groupsMet=ev.groups_met,
                entry=ev.entry,
                sl=ev.sl,
                target=ev.target,
                qty=ev.qty,
                risk=ev.risk,
                sector=ev.sector or "",
                reason=ev.reason or "",
                scanSource=ev.scan_source,
                emailStatus=ev.email_status,
                emailError=err[:120] if err else "",
            )
        )
    return rows


class AIScannerService:
    @classmethod
    def clear_scan_cache(cls) -> None:
        global _scan_cache, _scan_cached_at
        _scan_cache = None
        _scan_cached_at = 0.0

    @classmethod
    def get_snapshot(cls, *, run_auto_exit: bool = True) -> AIScannerSnapshot:
        _ensure_quant_path()
        try:
            from core.ai_scanner import CAPITAL_PER_PICK, mark_existing_positions
        except Exception:
            CAPITAL_PER_PICK = 15_000
            mark_existing_positions = None  # type: ignore

        scan, scan_error = _run_scan(force=False)
        auto_exited = _auto_exit_paper_trades() if run_auto_exit else 0

        if not scan or not scan.get("all_results"):
            pt_raw = _load_paper_trades()
            pt = _enrich_paper_trades(pt_raw)
            summary, rows, open_tickers = cls._paper_trade_payload(pt)
            return AIScannerSnapshot(
                capitalPerPick=int(CAPITAL_PER_PICK),
                scanAvailable=False,
                scanError=scan_error or "No scan results",
                paperTradesAutoExited=auto_exited,
                paperTradeSummary=summary,
                paperTrades=rows,
                openPaperTickers=open_tickers,
                noStrongBuyMessage=(
                    "No scan results yet. Check that sector_map_fixed.csv has a Ticker column "
                    "and that yfinance can reach Yahoo from this machine."
                ),
                liveWatch=_live_watch_payload(),
                newTodayEvents=_new_today_payload(),
            )

        open_trades = _load_open_trades()
        if mark_existing_positions is not None:
            scan = mark_existing_positions(
                scan, open_trades if not open_trades.empty else None
            )

        strong_buys = scan["strong_buys"]
        exits = scan["exits"]
        watchlist = scan["watchlist"]
        all_results = scan["all_results"]
        sec_mom = scan["sector_momentum"]
        scanned_at = scan["scanned_at"]

        avg_score = (
            float(pd.Series([r.composite_score for r in all_results]).mean())
            if all_results
            else 0.0
        )
        best_sector = "—"
        best_sector_score = 0.0
        if sec_mom:
            best_sector = max(sec_mom, key=sec_mom.get)
            best_sector_score = float(sec_mom[best_sector])

        kpis = ScannerKpis(
            strongBuys=len(strong_buys),
            exitFlags=len(exits),
            watchlist=len(watchlist),
            universe=len(all_results),
            topSector=best_sector[:14],
            topSectorScore=best_sector_score,
            avgScore=avg_score,
        )

        sector_rows: list[SectorStrengthRow] = []
        if all_results:
            sec_data: dict[str, list[float]] = {}
            for r in all_results:
                sec = r.sector or "Unknown"
                sec_data.setdefault(sec, []).append(float(r.composite_score))
            for sec, scores in sec_data.items():
                if len(scores) < 2:
                    continue
                sector_rows.append(
                    SectorStrengthRow(
                        sector=sec[:32],
                        stocks=len(scores),
                        momentum1mPct=float(sec_mom.get(sec, 0.0)),
                        avgScore=float(pd.Series(scores).mean()),
                        topStockScore=max(scores),
                    )
                )
            sector_rows.sort(key=lambda x: x.avgScore, reverse=True)

        no_sb_msg = ""
        if not strong_buys:
            no_sb_msg = (
                "No STRONG BUY opportunities meeting conservative criteria right now. "
                "The model requires composite ≥ 75 AND at least 4 of 5 factor groups firing "
                "positively (trend, momentum, setup, sector, catalyst). "
                "Check the Watchlist section for high-scoring picks that haven't fully converged yet."
            )

        pt_raw = _load_paper_trades()
        pt = _enrich_paper_trades(pt_raw)
        summary, rows, open_tickers = cls._paper_trade_payload(pt)

        scanned_str = (
            scanned_at.strftime("%d-%b %H:%M:%S")
            if hasattr(scanned_at, "strftime")
            else str(scanned_at)
        )
        footer = (
            f"Last scan: {scanned_str} · Refreshes hourly · "
            f"Capital per pick: ₹{int(CAPITAL_PER_PICK):,} · "
            f"Conservative mode (composite ≥ 75, 4+ converging signals) · "
            f"Research aid only, not financial advice"
        )

        return AIScannerSnapshot(
            scannedAt=scanned_str,
            capitalPerPick=int(CAPITAL_PER_PICK),
            scanAvailable=True,
            kpis=kpis,
            exits=[_scan_result_row(r) for r in exits],
            topOpportunities=[_scan_result_row(r) for r in strong_buys[:3]],
            strongBuys=[_strong_buy_table_row(r) for r in strong_buys],
            watchlist=[_watchlist_table_row(r) for r in watchlist[:15]],
            sectorStrength=sector_rows,
            noStrongBuyMessage=no_sb_msg,
            paperTradesAutoExited=auto_exited,
            paperTradeSummary=summary,
            paperTrades=rows,
            openPaperTickers=open_tickers,
            footerNote=footer,
            liveWatch=_live_watch_payload(),
            newTodayEvents=_new_today_payload(),
        )

    @staticmethod
    def _paper_trade_payload(pt: pd.DataFrame) -> tuple[PaperTradeSummary, list[PaperTradeRow], list[str]]:
        if pt.empty:
            return PaperTradeSummary(), [], []
        open_count = int((pt["Outcome"] == "OPEN").sum())
        tp_count = int(pt["Outcome"].astype(str).str.startswith("TP").sum())
        sl_count = int(pt["Outcome"].astype(str).str.startswith("SL").sum())
        exited_count = int((pt["Outcome"] == "EXITED").sum())
        closed = tp_count + sl_count + exited_count
        hit_rate = tp_count / closed * 100 if closed > 0 else None
        total_pnl = float(pt["P&L ₹"].sum()) if "P&L ₹" in pt.columns else None
        summary = PaperTradeSummary(
            total=len(pt),
            open=open_count,
            tp=tp_count,
            sl=sl_count,
            hitRate=round(hit_rate, 1) if hit_rate is not None else None,
            totalPnlInr=round(total_pnl, 0) if total_pnl is not None else None,
        )
        rows: list[PaperTradeRow] = []
        for _, row in pt.iterrows():
            rows.append(
                PaperTradeRow(
                    addedDate=str(row.get("AddedDate", "") or ""),
                    addedTs=str(row.get("AddedTS", "") or ""),
                    source=str(row.get("Source", "") or ""),
                    ticker=str(row.get("Ticker", "") or ""),
                    score=float(row["Score"]) if pd.notna(row.get("Score")) else None,
                    entry=float(row["Entry"]) if pd.notna(row.get("Entry")) else None,
                    sl=float(row["SL"]) if pd.notna(row.get("SL")) else None,
                    target=float(row["Target"]) if pd.notna(row.get("Target")) else None,
                    qty=float(row["Qty"]) if pd.notna(row.get("Qty")) else None,
                    risk=float(row["Risk"]) if pd.notna(row.get("Risk")) else None,
                    status=str(row.get("Status", "") or ""),
                    exitPrice=float(row["ExitPrice"]) if pd.notna(row.get("ExitPrice")) else None,
                    exitDate=str(row.get("ExitDate", "") or ""),
                    cmp=float(row["CMP"]) if pd.notna(row.get("CMP")) else None,
                    returnPct=float(row["Return %"]) if pd.notna(row.get("Return %")) else None,
                    pnlInr=float(row["P&L ₹"]) if pd.notna(row.get("P&L ₹")) else None,
                    days=int(row.get("Days", 0) or 0),
                    outcome=str(row.get("Outcome", "") or ""),
                )
            )
        open_tickers = pt.loc[pt["Outcome"] == "OPEN", "Ticker"].astype(str).unique().tolist()
        return summary, rows, open_tickers

    @classmethod
    def rescan(cls) -> AIScannerSnapshot:
        cls.clear_scan_cache()
        scan, scan_error = execute_production_scan(force=True)
        if scan:
            try:
                process_qualifying_opportunities(scan, scan_source="MANUAL")
            except Exception:
                pass
        if not scan:
            snap = cls.get_snapshot(run_auto_exit=True)
            if scan_error and not snap.scanError:
                snap.scanError = scan_error
            return snap
        global _scan_cache, _scan_cached_at
        _scan_cache = scan
        _scan_cached_at = time.time()
        return cls.get_snapshot(run_auto_exit=True)

    @classmethod
    def add_paper_trade(cls, body: AddPaperTradeRequest) -> AIScannerActionResult:
        row = _lookup_scan_result(body.ticker)
        if row is None:
            scan, _ = _run_scan(force=False)
            if scan:
                row = _lookup_scan_result(body.ticker)
        if row is None:
            return AIScannerActionResult(
                success=False,
                message=f"Ticker {body.ticker} not found in current scan results",
            )
        added = _save_paper_trade_from_result(row, source=body.source or "AI Scanner")
        if not added:
            return AIScannerActionResult(
                success=False,
                message=f"{row.ticker} already in open paper trades",
            )
        snapshot = cls.get_snapshot(run_auto_exit=False)
        return AIScannerActionResult(
            success=True,
            message=f"✓ {row.ticker} added — see tracker below",
            snapshot=snapshot,
        )

    @classmethod
    def exit_paper_trade(cls, ticker: str, body: ExitPaperTradeRequest) -> AIScannerActionResult:
        exit_px = body.exitPrice if body.exitPrice > 0 else None
        ok = _exit_paper_trade(ticker, exit_px)
        if not ok:
            return AIScannerActionResult(
                success=False,
                message=f"No open paper trade for {ticker}",
            )
        snapshot = cls.get_snapshot(run_auto_exit=False)
        return AIScannerActionResult(
            success=True,
            message=f"✓ {ticker} marked as EXITED",
            snapshot=snapshot,
        )
