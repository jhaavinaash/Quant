"""F1 Control Center — mirrors dashboard/app_ai.py Tab 11.

Read-only F1 decision display + safe actions: Run F1 (subprocess f1_runner.py),
Deploy handoff (pending_trade.json). Does NOT modify F1 strategy logic.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import yfinance as yf

from app.core.config import settings
from app.schemas.f1 import (
    F1CapitalAllocation,
    F1DecisionAudit,
    F1DecisionAuditRow,
    F1DeployCandidate,
    F1DeployResult,
    F1HeldRow,
    F1KpiCard,
    F1LastRun,
    F1OpenPositionRow,
    F1Performance,
    F1ProductionComponent,
    F1ProductionStatus,
    F1ReadyToDeploy,
    F1RunResult,
    F1Snapshot,
    F1TodayDecisionCounts,
)

_F1_ENGINE_TAG = "F1"
_LIVE_PRICE_CACHE: dict[str, tuple[float, dict[str, float]]] = {}
_LIVE_PRICE_TTL = 60


def _ensure_quant_path() -> Path:
    root = Path(settings.QUANT_BASE_DIR)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def _cfg(name: str, default: Any = None) -> Any:
    _ensure_quant_path()
    try:
        import config  # type: ignore

        return getattr(config, name, default)
    except Exception:
        return default


def _f1_decisions_path() -> Path:
    return _ensure_quant_path() / "F0" / "data" / "f1" / "f1_decisions.csv"


def _f1_runs_path() -> Path:
    return _ensure_quant_path() / "F0" / "data" / "f1" / "f1_runs.csv"


def _pending_trade_path() -> Path:
    prod = _cfg("PROD_DIR")
    if prod:
        return Path(str(prod)) / "pending_trade.json"
    return _ensure_quant_path() / "F0" / "production" / "pending_trade.json"


def _bare(t: str) -> str:
    return str(t).strip().upper().replace(".NS", "").replace(".BO", "")


def _filter_f1_only(df: pd.DataFrame, engine_col: str = "Engine") -> pd.DataFrame:
    if df.empty or engine_col not in df.columns:
        return df.iloc[0:0]
    return df[df[engine_col].astype(str).str.strip().str.upper() == _F1_ENGINE_TAG].copy()


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        _ensure_quant_path()
        from core.utils import safe_read_csv

        return safe_read_csv(path)
    except Exception:
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()


def _live_prices(tickers_tuple: tuple[str, ...]) -> dict[str, float]:
    if not tickers_tuple:
        return {}
    key = "|".join(sorted(tickers_tuple))
    now = time.time()
    cached = _LIVE_PRICE_CACHE.get(key)
    if cached and now - cached[0] < _LIVE_PRICE_TTL:
        return cached[1]

    result: dict[str, float] = {}

    def _one(t: str):
        bare = t.upper().replace(".NS", "").replace(".BO", "")
        yf_t = t if "." in t else f"{t}.NS"
        try:
            fi = yf.Ticker(yf_t).fast_info
            price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", None)
            return bare, float(price) if price else None
        except Exception:
            return bare, None

    with ThreadPoolExecutor(max_workers=10) as pool:
        for fut in as_completed({pool.submit(_one, t): t for t in tickers_tuple}):
            b, p = fut.result()
            if p:
                result[b] = p

    _LIVE_PRICE_CACHE[key] = (now, result)
    return result


def _save_pending_trade(data: dict) -> None:
    path = _pending_trade_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def _fmt_inr(val: float, signed: bool = True) -> str:
    try:
        v = float(val)
        sign = ("+" if v > 0 else "") if signed else ""
        return f"{sign}₹{v:,.0f}"
    except (TypeError, ValueError):
        return "—"


def _today_decision_counts(today_raw: pd.DataFrame) -> F1TodayDecisionCounts:
    if today_raw.empty or "Action" not in today_raw.columns:
        return F1TodayDecisionCounts()
    actions = today_raw["Action"].astype(str).str.strip().str.upper()
    counts = actions.value_counts()
    known = {"BUY", "ROTATE", "BLOCK", "WATCH", "IGNORE"}
    other = int(sum(v for k, v in counts.items() if k not in known))
    return F1TodayDecisionCounts(
        total=len(today_raw),
        buy=int(counts.get("BUY", 0)),
        rotate=int(counts.get("ROTATE", 0)),
        block=int(counts.get("BLOCK", 0)),
        watch=int(counts.get("WATCH", 0)),
        ignore=int(counts.get("IGNORE", 0)),
        other=other,
    )


def _build_deploy_candidates(
    ready_deploy: pd.DataFrame,
    *,
    suggested_capital: float,
    deploy_today: int,
    globally_owned_tickers: set[str],
    f1_open_tickers: set[str],
    ticker_engine_map: dict[str, str],
) -> list[F1DeployCandidate]:
    out: list[F1DeployCandidate] = []
    if ready_deploy.empty:
        return out

    df = ready_deploy.copy()
    if "PortfolioRank" in df.columns:
        df["PortfolioRank"] = pd.to_numeric(df["PortfolioRank"], errors="coerce")
        df = df.sort_values("PortfolioRank", na_position="last")
    if "Close" in df.columns:
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

    for rank_idx, (idx, row) in enumerate(df.iterrows()):
        ticker_val = str(row.get("Ticker", ""))
        rank_val = row.get("PortfolioRank", "")
        sector_val = str(row.get("Sector", ""))
        close_val = row.get("Close", 0)
        tech_val = str(row.get("TechnicalState", ""))
        biz_val = str(row.get("BusinessGate", ""))
        sec_state = str(row.get("SectorState", ""))
        rs55_val = row.get("RS55", "")
        entry_dist = row.get("EntryDistPct", "")
        phase_val = str(row.get("Phase", ""))

        cap_per = suggested_capital
        try:
            close_f = float(close_val) if pd.notna(close_val) else 0.0
        except Exception:
            close_f = 0.0
        sug_qty = int(cap_per // close_f) if close_f > 0 else 0
        position_value = sug_qty * close_f

        is_deployable = rank_idx < deploy_today
        t_bare = _bare(ticker_val)
        held_elsewhere = (t_bare in globally_owned_tickers) and (t_bare not in f1_open_tickers)
        held_in_f1 = t_bare in f1_open_tickers
        held_by_engine = ticker_engine_map.get(t_bare, "")

        if held_elsewhere:
            btn_label = f"Held ({held_by_engine})" if held_by_engine else "Held elsewhere"
            btn_disabled = True
            is_dep = False
        elif is_deployable:
            btn_label = "Deploy"
            btn_disabled = False
            is_dep = True
        else:
            btn_label = "Watch"
            btn_disabled = True
            is_dep = False

        rs55_f = float(rs55_val) if isinstance(rs55_val, (int, float)) and pd.notna(rs55_val) else None
        ed_f = float(entry_dist) if isinstance(entry_dist, (int, float)) and pd.notna(entry_dist) else None
        rank_f = float(rank_val) if pd.notna(rank_val) else None

        out.append(
            F1DeployCandidate(
                rowIndex=int(idx),
                rankIndex=rank_idx,
                ticker=ticker_val,
                portfolioRank=rank_f,
                sector=sector_val,
                phase=phase_val,
                close=close_f,
                rs55=rs55_f,
                entryDistPct=ed_f,
                technicalState=tech_val,
                sectorState=sec_state,
                businessGate=biz_val,
                suggestedCapital=cap_per,
                suggestedQty=sug_qty,
                positionValue=position_value,
                isDeployable=is_dep,
                heldElsewhere=held_elsewhere,
                heldInF1=held_in_f1,
                heldByEngine=held_by_engine,
                buttonLabel=btn_label,
                buttonDisabled=btn_disabled,
            )
        )
    return out


class F1Service:
    @classmethod
    def get_snapshot(cls) -> F1Snapshot:
        _ensure_quant_path()
        f1_total_capital = float(_cfg("F1_TOTAL_CAPITAL", 300_000))
        f1_max_positions = int(_cfg("F1_MAX_POSITIONS", 15))

        raw = _safe_read_csv(_f1_decisions_path())
        dlog = _safe_read_csv(Path(str(_cfg("DECISION_LOG_FILE", ""))))
        tradebook = _safe_read_csv(Path(str(_cfg("TRADES_LOG_FILE", ""))))
        positions = _safe_read_csv(Path(str(_cfg("OPEN_POSITIONS_FILE", ""))))
        equity_df = _safe_read_csv(Path(str(_cfg("EQUITY_CURVE_FILE", ""))))
        runs_df = _safe_read_csv(_f1_runs_path())

        today_str = datetime.now().strftime("%Y-%m-%d")
        if not raw.empty and "Timestamp" in raw.columns:
            today_raw = raw[raw["Timestamp"].astype(str).str.startswith(today_str)].copy()
        else:
            today_raw = raw.copy()

        f1_trades = _filter_f1_only(tradebook, "Engine")
        if not f1_trades.empty and "Status" in f1_trades.columns:
            f1_open_trades = f1_trades[
                f1_trades["Status"].astype(str).str.upper() == "OPEN"
            ].copy()
            f1_closed = f1_trades[
                f1_trades["Status"].astype(str).str.upper() == "CLOSED"
            ].copy()
        else:
            f1_open_trades = pd.DataFrame()
            f1_closed = pd.DataFrame()

        f1_open_tickers = (
            {_bare(t) for t in f1_open_trades["Ticker"]}
            if not f1_open_trades.empty and "Ticker" in f1_open_trades.columns
            else set()
        )

        globally_owned_tickers: set[str] = set()
        if not tradebook.empty and "Ticker" in tradebook.columns and "Status" in tradebook.columns:
            _open_all = tradebook[tradebook["Status"].astype(str).str.upper() == "OPEN"]
            globally_owned_tickers = {_bare(t) for t in _open_all["Ticker"]}
        if not positions.empty and "Ticker" in positions.columns:
            globally_owned_tickers |= {_bare(t) for t in positions["Ticker"]}

        ticker_engine_map: dict[str, str] = {}
        if (
            not tradebook.empty
            and "Ticker" in tradebook.columns
            and "Engine" in tradebook.columns
            and "Status" in tradebook.columns
        ):
            _o = tradebook[tradebook["Status"].astype(str).str.upper() == "OPEN"]
            for _, _r in _o.iterrows():
                _t = _bare(str(_r.get("Ticker", "")))
                _e = str(_r.get("Engine", "")).strip().upper()
                if _t and _e:
                    ticker_engine_map[_t] = _e

        if not today_raw.empty and "Action" in today_raw.columns:
            all_buys = today_raw[today_raw["Action"].astype(str).str.upper() == "BUY"].copy()
        else:
            all_buys = pd.DataFrame()

        if not all_buys.empty and "Ticker" in all_buys.columns:
            all_buys["_t_bare"] = all_buys["Ticker"].apply(_bare)
            already_owned = all_buys[all_buys["_t_bare"].isin(globally_owned_tickers)].copy()
            ready_deploy = all_buys[~all_buys["_t_bare"].isin(globally_owned_tickers)].copy()
        else:
            already_owned = pd.DataFrame()
            ready_deploy = pd.DataFrame()

        deployed_cap = 0.0
        if not f1_open_trades.empty and "EntryPrice" in f1_open_trades.columns and "Qty" in f1_open_trades.columns:
            deployed_cap = float(
                (
                    pd.to_numeric(f1_open_trades["EntryPrice"], errors="coerce").fillna(0)
                    * pd.to_numeric(f1_open_trades["Qty"], errors="coerce").fillna(0)
                ).sum()
            )

        cash_available = max(0.0, f1_total_capital - deployed_cap)
        n_open_f1 = len(f1_open_trades)
        free_slots = max(0, f1_max_positions - n_open_f1)
        n_buy_signals = len(all_buys)
        n_already_owned = len(already_owned)
        n_ready = len(ready_deploy)

        deploy_today_count = min(n_ready, free_slots)
        if deploy_today_count > 0:
            suggested_capital = cash_available / deploy_today_count
        else:
            suggested_capital = cash_available / max(1, free_slots) if free_slots > 0 else 0.0

        affordable = int(cash_available // suggested_capital) if suggested_capital > 0 else 0
        deploy_today = min(deploy_today_count, max(affordable, 0))

        cap_cards = [
            F1KpiCard(label="F1 CAPITAL", value=_fmt_inr(f1_total_capital, signed=False), sub="total allocated"),
            F1KpiCard(
                label="DEPLOYED",
                value=_fmt_inr(deployed_cap, signed=False),
                sub=f"{(deployed_cap / f1_total_capital * 100 if f1_total_capital > 0 else 0):.1f}% utilised",
            ),
            F1KpiCard(label="CASH FREE", value=_fmt_inr(cash_available, signed=False), sub="available for deployment"),
            F1KpiCard(label="POSITIONS", value=f"{n_open_f1}/{f1_max_positions}", sub=f"{free_slots} free slots"),
            F1KpiCard(label="CAPITAL/TRADE", value=_fmt_inr(suggested_capital, signed=False), sub="suggested allocation"),
            F1KpiCard(
                label="DEPLOY TODAY",
                value=str(deploy_today),
                sub=f"{n_buy_signals} BUY · {n_already_owned} held",
            ),
        ]

        capital_allocation = F1CapitalAllocation(
            f1Capital=f1_total_capital,
            deployed=deployed_cap,
            deployedPct=(deployed_cap / f1_total_capital * 100 if f1_total_capital > 0 else 0),
            cashFree=cash_available,
            positionsOpen=n_open_f1,
            maxPositions=f1_max_positions,
            freeSlots=free_slots,
            capitalPerTrade=suggested_capital,
            deployToday=deploy_today,
            buySignals=n_buy_signals,
            alreadyOwned=n_already_owned,
            cards=cap_cards,
        )

        open_value = 0.0
        if not f1_open_trades.empty and "Ticker" in f1_open_trades.columns and "Qty" in f1_open_trades.columns:
            tickers_tuple = tuple(sorted(f1_open_tickers))
            live_prices = _live_prices(tickers_tuple)
            for _, r in f1_open_trades.iterrows():
                t = str(r.get("Ticker", "")).strip().upper()
                q = pd.to_numeric([r.get("Qty", 0)], errors="coerce")[0] or 0
                ep = pd.to_numeric([r.get("EntryPrice", 0)], errors="coerce")[0] or 0
                cmp_val = live_prices.get(t, ep)
                try:
                    cmp_val = float(cmp_val) if cmp_val else ep
                except Exception:
                    cmp_val = ep
                open_value += float(q) * float(cmp_val)

        realised_pnl = 0.0
        if not f1_closed.empty and "PnL" in f1_closed.columns:
            realised_pnl = float(pd.to_numeric(f1_closed["PnL"], errors="coerce").fillna(0).sum())

        unrealised_pnl = open_value - deployed_cap
        current_portfolio_value = cash_available + open_value + realised_pnl
        total_return = current_portfolio_value - f1_total_capital
        total_return_pct = (total_return / f1_total_capital * 100) if f1_total_capital > 0 else 0

        cagr_pct = None
        if not f1_trades.empty and "Date" in f1_trades.columns:
            try:
                first_date = pd.to_datetime(f1_trades["Date"], dayfirst=True, errors="coerce").min()
                if pd.notna(first_date):
                    days = (datetime.now() - first_date).days
                    if days >= 30 and f1_total_capital > 0 and current_portfolio_value > 0:
                        years = days / 365.25
                        cagr_pct = (
                            (current_portfolio_value / f1_total_capital) ** (1 / years) - 1
                        ) * 100
            except Exception:
                pass

        max_dd_pct = 0.0
        if not equity_df.empty and "Drawdown_Pct" in equity_df.columns:
            try:
                max_dd_pct = float(pd.to_numeric(equity_df["Drawdown_Pct"], errors="coerce").min() or 0)
            except Exception:
                max_dd_pct = 0.0

        n_closed = len(f1_closed)
        n_wins = 0
        if not f1_closed.empty and "PnL" in f1_closed.columns:
            n_wins = int((pd.to_numeric(f1_closed["PnL"], errors="coerce").fillna(0) > 0).sum())
        win_rate = (n_wins / n_closed * 100) if n_closed > 0 else None

        perf_cards = [
            F1KpiCard(label="INITIAL CAPITAL", value=_fmt_inr(f1_total_capital, signed=False), sub="inception"),
            F1KpiCard(
                label="PORTFOLIO VALUE",
                value=_fmt_inr(current_portfolio_value, signed=False),
                sub="cash + open + realised",
            ),
            F1KpiCard(label="TOTAL RETURN", value=f"{total_return_pct:+.2f}%", sub=_fmt_inr(total_return)),
            F1KpiCard(
                label="CAGR",
                value=f"{cagr_pct:+.2f}%" if cagr_pct is not None else "—",
                sub="annualised" if cagr_pct is not None else "needs 30+ days",
            ),
            F1KpiCard(label="MAX DRAWDOWN", value=f"{max_dd_pct:.2f}%", sub="peak-to-trough"),
            F1KpiCard(label="OPEN TRADES", value=str(n_open_f1), sub="active positions"),
            F1KpiCard(label="CLOSED TRADES", value=str(n_closed), sub=f"{n_wins} wins"),
            F1KpiCard(
                label="WIN RATE",
                value=f"{win_rate:.1f}%" if win_rate is not None else "—",
                sub="closed trades",
            ),
        ]

        performance = F1Performance(
            initialCapital=f1_total_capital,
            portfolioValue=current_portfolio_value,
            totalReturn=total_return,
            totalReturnPct=total_return_pct,
            cagrPct=cagr_pct,
            maxDrawdownPct=max_dd_pct,
            openTrades=n_open_f1,
            closedTrades=n_closed,
            wins=n_wins,
            winRate=win_rate,
            cards=perf_cards,
        )

        ready_section = F1ReadyToDeploy(
            candidateCount=len(ready_deploy),
            deployableCount=deploy_today,
            suggestedCapital=suggested_capital,
            deployToday=deploy_today,
            candidates=_build_deploy_candidates(
                ready_deploy,
                suggested_capital=suggested_capital,
                deploy_today=deploy_today,
                globally_owned_tickers=globally_owned_tickers,
                f1_open_tickers=f1_open_tickers,
                ticker_engine_map=ticker_engine_map,
            ),
        )

        if ready_deploy.empty:
            if n_buy_signals > 0:
                ready_section.allHeldMessage = (
                    f"All {n_buy_signals} BUY candidate(s) are already in your F1 portfolio."
                )
            elif not today_raw.empty:
                ready_section.emptyMessage = "No deployable trades today."
                if "Phase" in today_raw.columns:
                    ready_section.phaseBreakdown = [
                        {"label": str(k), "count": int(v)}
                        for k, v in today_raw["Phase"].value_counts().items()
                    ]
                if "Action" in today_raw.columns:
                    ready_section.actionBreakdown = [
                        {"label": str(k), "count": int(v)}
                        for k, v in today_raw["Action"].value_counts().items()
                    ]
            else:
                ready_section.noCandidatesMessage = "Run F1 to generate candidates."

        held_rows: list[F1HeldRow] = []
        already_owned_summary = ""
        if not already_owned.empty:
            n_in_f1 = sum(
                1 for _, r in already_owned.iterrows() if _bare(str(r.get("Ticker", ""))) in f1_open_tickers
            )
            n_in_other = len(already_owned) - n_in_f1
            sub_parts = []
            if n_in_f1:
                sub_parts.append(f"{n_in_f1} in F1")
            if n_in_other:
                sub_parts.append(f"{n_in_other} in other engines")
            already_owned_summary = (
                f"{len(already_owned)} HELD — BUY candidates already owned — "
                f"{' · '.join(sub_parts)} — no action needed"
            )
            held_cols = [
                c
                for c in [
                    "Ticker",
                    "Sector",
                    "Phase",
                    "PortfolioRank",
                    "TechnicalState",
                    "SectorState",
                    "RS55",
                    "Close",
                ]
                if c in already_owned.columns
            ]
            held_show = already_owned[held_cols].copy()
            held_show["Held In"] = held_show["Ticker"].apply(
                lambda t: ticker_engine_map.get(_bare(str(t)), "F1")
            )
            for nc in ["PortfolioRank", "RS55", "Close"]:
                if nc in held_show.columns:
                    held_show[nc] = pd.to_numeric(held_show[nc], errors="coerce")
            if "PortfolioRank" in held_show.columns:
                held_show = held_show.sort_values("PortfolioRank", na_position="last")
            for _, r in held_show.iterrows():
                held_rows.append(
                    F1HeldRow(
                        ticker=str(r.get("Ticker", "")),
                        sector=str(r.get("Sector", "")),
                        phase=str(r.get("Phase", "")),
                        portfolioRank=float(r["PortfolioRank"]) if pd.notna(r.get("PortfolioRank")) else None,
                        technicalState=str(r.get("TechnicalState", "")),
                        sectorState=str(r.get("SectorState", "")),
                        rs55=float(r["RS55"]) if pd.notna(r.get("RS55")) else None,
                        close=float(r["Close"]) if pd.notna(r.get("Close")) else None,
                        heldIn=str(r.get("Held In", "")),
                    )
                )

        open_rows: list[F1OpenPositionRow] = []
        open_empty = "No open F1 positions. Deploy BUY candidates above to start building the portfolio."
        if not f1_open_trades.empty:
            tickers_tuple = tuple(sorted(f1_open_tickers))
            live_prices = _live_prices(tickers_tuple)
            raw_lookup: dict[str, pd.Series] = {}
            if not raw.empty and "Ticker" in raw.columns:
                for t, grp in raw.groupby(raw["Ticker"].astype(str).str.strip().str.upper()):
                    if "Timestamp" in grp.columns:
                        last_row = grp.sort_values("Timestamp").iloc[-1]
                    else:
                        last_row = grp.iloc[-1]
                    raw_lookup[t] = last_row

            for _, r in f1_open_trades.iterrows():
                t = str(r.get("Ticker", "")).strip().upper()
                entry = pd.to_numeric([r.get("EntryPrice", 0)], errors="coerce")[0] or 0
                qty = pd.to_numeric([r.get("Qty", 0)], errors="coerce")[0] or 0
                cmp_val = live_prices.get(t)
                try:
                    cmp_val = float(cmp_val) if cmp_val else float(entry)
                except Exception:
                    cmp_val = float(entry)
                ret_pct = ((cmp_val - entry) / entry * 100) if entry > 0 else 0
                pnl_abs = (cmp_val - entry) * qty

                lookup = raw_lookup.get(t, {})
                current_tech = str(lookup.get("TechnicalState", "")) if len(lookup) else ""
                current_exit_prio = str(lookup.get("ExitPriority", "")) if len(lookup) else ""
                current_phase = str(lookup.get("Phase", "")) if len(lookup) else ""
                current_action = str(lookup.get("Action", "")) if len(lookup) else ""

                if current_action and current_action.upper() in ("ROTATE", "EXIT"):
                    exit_rule = "EXIT NOW — Technical FADING confirmed"
                    exit_signal = "🔴"
                elif current_tech and "FADING" in current_tech.upper():
                    exit_rule = "EXIT NOW — FADING"
                    exit_signal = "🔴"
                elif current_exit_prio and current_exit_prio.upper() in ("HIGH", "URGENT"):
                    exit_rule = f"WATCH — Exit Priority {current_exit_prio}"
                    exit_signal = "🟡"
                elif current_phase and current_phase.upper() == "LANDING":
                    exit_rule = "WATCH — LANDING phase"
                    exit_signal = "🟡"
                else:
                    exit_rule = "HOLD — Technical intact"
                    exit_signal = "🟢"

                open_rows.append(
                    F1OpenPositionRow(
                        signal=exit_signal,
                        ticker=t,
                        entry=float(entry),
                        cmp=float(cmp_val),
                        returnPct=float(ret_pct),
                        pnlInr=float(pnl_abs),
                        qty=int(qty),
                        phase=current_phase or "—",
                        technical=current_tech or "—",
                        exitPriority=current_exit_prio or "NORMAL",
                        exitRule=exit_rule,
                    )
                )
            open_empty = ""

        audit_rows: list[F1DecisionAuditRow] = []
        date_options: list[str] = []
        total_f1 = 0
        if not dlog.empty:
            if "Engine" in dlog.columns:
                dlog_f1 = dlog[dlog["Engine"].astype(str).str.strip().str.upper() == _F1_ENGINE_TAG].copy()
            else:
                dlog_f1 = dlog.copy()
            if "Decision" in dlog_f1.columns:
                dlog_f1["Decision"] = dlog_f1["Decision"].astype(str).str.strip().str.upper()
            if "Date" in dlog_f1.columns:
                dlog_f1["_date"] = pd.to_datetime(dlog_f1["Date"], errors="coerce").dt.date.astype(str)
            else:
                dlog_f1["_date"] = ""
            total_f1 = len(dlog_f1)
            date_options = sorted(dlog_f1["_date"].dropna().unique().tolist(), reverse=True)
            show_cols = [
                c
                for c in [
                    "Date",
                    "Engine",
                    "Ticker",
                    "Decision",
                    "Reason",
                    "TechnicalState",
                    "SectorState",
                    "BusinessGate",
                    "PortfolioRank",
                ]
                if c in dlog_f1.columns
            ]
            for _, row in dlog_f1[show_cols].iterrows():
                audit_rows.append(
                    F1DecisionAuditRow(
                        date=str(row.get("Date", "")),
                        engine=str(row.get("Engine", "")),
                        ticker=str(row.get("Ticker", "")),
                        decision=str(row.get("Decision", "")),
                        reason=str(row.get("Reason", "")),
                        technicalState=str(row.get("TechnicalState", "")),
                        sectorState=str(row.get("SectorState", "")),
                        businessGate=str(row.get("BusinessGate", "")),
                        portfolioRank=str(row.get("PortfolioRank", "")),
                    )
                )

        production = cls._build_production_status()

        last_run = None
        if not runs_df.empty:
            last = runs_df.iloc[-1]
            failures = int(last.get("Failures", 0) or 0)
            last_run = F1LastRun(
                timestamp=str(last.get("Timestamp", "")),
                universe=str(last.get("Universe", "")),
                elapsedSec=str(last.get("ElapsedSec", "")),
                failures=failures,
                ok=failures == 0,
            )

        return F1Snapshot(
            totalCapital=f1_total_capital,
            maxPositions=f1_max_positions,
            lastRun=last_run,
            todayDecisionCounts=_today_decision_counts(today_raw),
            capitalAllocation=capital_allocation,
            performance=performance,
            readyToDeploy=ready_section,
            alreadyOwned=held_rows,
            alreadyOwnedSummary=already_owned_summary,
            openPositions=open_rows,
            openPositionsEmptyMessage=open_empty,
            decisionAudit=F1DecisionAudit(
                rows=audit_rows, totalF1=total_f1, dateOptions=date_options
            ),
            productionStatus=production,
        )

    @staticmethod
    def _build_production_status() -> F1ProductionStatus:
        health_path = Path(str(_cfg("HEALTH_STATUS_FILE", "")))
        health: dict = {}
        if health_path.exists():
            try:
                health = json.loads(health_path.read_text(encoding="utf-8"))
            except Exception:
                health = {}
        if not health:
            return F1ProductionStatus(emptyMessage="No health data.")

        overall = health.get("overall", "UNKNOWN")
        gen_at = health.get("generated_at", "")
        components = health.get("components", {})
        icon_map = {"HEALTHY": "🟢", "WARNING": "🟡", "FAILED": "🔴"}
        file_checks = {
            "Downloader": Path(str(_cfg("PRICE_FILE", ""))).exists() if _cfg("PRICE_FILE") else False,
            "F1 Engine": _f1_decisions_path().exists(),
            "Decision Log": Path(str(_cfg("DECISION_LOG_FILE", ""))).exists(),
            "Position Tracker": Path(str(_cfg("OPEN_POSITIONS_FILE", ""))).exists(),
            "Equity Curve": Path(str(_cfg("EQUITY_CURVE_FILE", ""))).exists(),
        }
        rows: list[F1ProductionComponent] = []
        seen: set[str] = set()
        for name, exists in file_checks.items():
            ck = name.lower().replace(" ", "_")
            seen.add(name)
            if ck in components:
                c = components[ck]
                rows.append(
                    F1ProductionComponent(
                        icon=icon_map.get(c.get("status", ""), "⚪"),
                        component=name,
                        status=str(c.get("status", "")),
                        detail=str(c.get("message", "")),
                    )
                )
            else:
                rows.append(
                    F1ProductionComponent(
                        icon="🟢" if exists else "🟡",
                        component=name,
                        status="HEALTHY" if exists else "WARNING",
                        detail="present" if exists else "missing",
                    )
                )
        for k, c in components.items():
            dn = k.replace("_", " ").title()
            if dn not in seen:
                rows.append(
                    F1ProductionComponent(
                        icon=icon_map.get(c.get("status", ""), "⚪"),
                        component=dn,
                        status=str(c.get("status", "")),
                        detail=str(c.get("message", "")),
                    )
                )
        email_ok = all([_cfg("EMAIL_SMTP_HOST"), _cfg("EMAIL_SENDER")])
        rows.append(
            F1ProductionComponent(
                icon="🟢" if email_ok else "🟡",
                component="Email",
                status="HEALTHY" if email_ok else "WARNING",
                detail="configured" if email_ok else "not configured",
            )
        )
        return F1ProductionStatus(overall=overall, generatedAt=gen_at, components=rows)

    @classmethod
    def run_f1(cls) -> F1RunResult:
        f1_path = _ensure_quant_path() / "F0" / "f1_runner.py"
        if not f1_path.exists():
            return F1RunResult(success=False, message=f"f1_runner.py not found at {f1_path}")

        t0 = time.time()
        try:
            result = subprocess.run(
                [sys.executable, str(f1_path)],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(f1_path.parent),
            )
            elapsed = round(time.time() - t0, 1)
            stdout_tail = [ln for ln in result.stdout.strip().split("\n")[-6:] if ln.strip()]
            if result.returncode == 0:
                snapshot = cls.get_snapshot()
                return F1RunResult(
                    success=True,
                    message=f"F1 completed in {elapsed}s",
                    elapsedSec=elapsed,
                    stdoutTail=stdout_tail,
                    snapshot=snapshot,
                )
            stderr_tail = (result.stderr or result.stdout or "")[-1500:]
            return F1RunResult(
                success=False,
                message=f"F1 failed (exit {result.returncode})",
                elapsedSec=elapsed,
                stdoutTail=stdout_tail,
                stderrTail=stderr_tail,
            )
        except subprocess.TimeoutExpired:
            return F1RunResult(success=False, message="Timed out (300s)")
        except Exception as exc:
            return F1RunResult(success=False, message=f"Failed: {exc}")

    @classmethod
    def deploy(cls, ticker: str) -> F1DeployResult:
        snap = cls.get_snapshot()
        candidate = next(
            (c for c in snap.readyToDeploy.candidates if c.ticker.upper() == ticker.strip().upper()),
            None,
        )
        if candidate is None:
            return F1DeployResult(
                success=False,
                message=f"{ticker} is not in Ready to Deploy or deploy is disabled",
            )
        if candidate.buttonDisabled:
            return F1DeployResult(success=False, message=f"Deploy not available for {ticker}")

        payload = {
            "engine": "F1",
            "ticker": candidate.ticker,
            "close": candidate.close,
            "rank": str(candidate.portfolioRank or ""),
            "sector": candidate.sector,
            "technical": candidate.technicalState,
            "sector_state": candidate.sectorState,
            "business": candidate.businessGate,
            "phase": candidate.phase,
            "suggested_capital": candidate.suggestedCapital,
            "suggested_qty": candidate.suggestedQty,
        }
        _save_pending_trade(payload)
        msg = (
            f"✓ {candidate.ticker} saved — open Trade Entry to execute "
            f"(Qty {candidate.suggestedQty} @ ₹{candidate.close:,.2f} ≈ ₹{candidate.positionValue:,.0f})"
        )
        return F1DeployResult(success=True, message=msg, snapshot=cls.get_snapshot())
