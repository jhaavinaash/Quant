"""
Quant Control Center — Institutional-Grade Dashboard
=====================================================
READ-ONLY dashboard. Does NOT modify any CSV, signal, engine, or trade.
Reads:
  - master_signals.csv      (signals queue, set by orchestrator)
  - trades_log.csv          (open + closed trades)
  - engine_status.csv       (last run status per engine)
  - blocked_signals.csv     (filtered signals)
  - Google Sheets portfolio (medium-term holdings)
  - yfinance                (live CMP, 60s cache)
  - Google News RSS         (portfolio news, 5min cache)
"""

from __future__ import annotations

import sys
import os
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from core.ai_scanner import (
    scan_universe,
    mark_existing_positions,
    CAPITAL_PER_PICK,
    EXIT_THRESHOLD,
)
from config import UNIVERSE_FILE, RESULT_CALENDAR_FILE
from config import (
    DASHBOARD_TITLE,
    MASTER_SIGNALS_FILE,
    ENGINE_STATUS_FILE,
    TRADES_LOG_FILE,
    BLOCKED_LOG_FILE,
    REFRESH_SECONDS,
    PORTFOLIO_GSHEET_ID,
)
try:
    from config import ENGINE_RULES
except Exception:
    ENGINE_RULES = {}
from core.utils import safe_read_csv
from core.news_fetcher import get_portfolio_news


# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title=DASHBOARD_TITLE,
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =====================================================
# DESIGN TOKENS
# =====================================================
BG_ROOT     = "#0a0e1a"
BG_PANEL    = "#0f172a"
BG_CARD     = "#111827"
BG_HOVER    = "#1e293b"
BORDER      = "#1e293b"
BORDER_SOFT = "#0f1729"

TXT_PRIMARY = "#f1f5f9"
TXT_SECOND  = "#94a3b8"
TXT_MUTED   = "#64748b"
TXT_DIM     = "#475569"

CLR_BULL    = "#10b981"   # green — gains, success
CLR_BEAR    = "#ef4444"   # red — losses, breaches
CLR_WARN    = "#f59e0b"   # amber — caution, near SL
CLR_INFO    = "#3b82f6"   # blue — primary accent
CLR_CYAN    = "#06b6d4"   # cyan — secondary accent


# =====================================================
# INSTITUTIONAL CSS
# =====================================================
st.markdown(f"""
<style>
.stApp {{
    background: linear-gradient(160deg,#0d1525 0%,{BG_ROOT} 60%);
    color: {TXT_PRIMARY};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    font-feature-settings: "tnum", "ss01";
}}
[data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
.block-container {{
    padding-top: 0.4rem;
    padding-bottom: 1rem;
    padding-left: 1.4rem;
    padding-right: 1.4rem;
    max-width: 1700px;
}}

/* ── Brand strip ── */
.qc-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: linear-gradient(180deg, #0f172a 0%, #0a0e1a 100%);
    border-bottom: 1px solid {BORDER};
    padding: 12px 22px;
    margin: -0.4rem -1.4rem 16px -1.4rem;
}}
.qc-brand {{
    display: flex; align-items: center; gap: 12px;
    color: {TXT_PRIMARY}; font-weight: 700;
    font-size: 14px; letter-spacing: 1.2px;
}}
.qc-brand-mark {{
    width: 32px; height: 32px;
    background: linear-gradient(135deg, {CLR_INFO} 0%, {CLR_CYAN} 100%);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 800; font-size: 15px;
    box-shadow: 0 4px 12px {CLR_INFO}40;
}}
.qc-status {{
    display: flex; align-items: center; gap: 22px;
    color: {TXT_SECOND}; font-size: 12px; font-weight: 500;
}}
.qc-dot {{
    width: 7px; height: 7px; border-radius: 50%;
    display: inline-block; margin-right: 7px;
}}
.qc-dot.live  {{ background: {CLR_BULL}; box-shadow: 0 0 8px {CLR_BULL}80; }}
.qc-dot.idle  {{ background: {TXT_MUTED}; }}

/* ── KPI Ribbon ── */
.qc-ribbon {{
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 1px;
    background: {BORDER};
    border: 1px solid {BORDER};
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 18px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.45), 0 1px 0 rgba(255,255,255,0.04) inset;
}}
.qc-kpi {{
    background: {BG_PANEL};
    padding: 14px 18px;
}}
.qc-kpi-label {{
    color: {TXT_SECOND};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.1px;
    text-transform: uppercase;
    margin-bottom: 6px;
}}
.qc-kpi-value {{
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.4px;
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
}}
.qc-kpi-sub {{
    color: {TXT_SECOND};
    font-size: 12px;
    margin-top: 4px;
    font-weight: 500;
}}

/* ── Tabs ── */
div[data-baseweb="tab-list"] {{
    background: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
    gap: 0; padding: 0 4px;
    border-radius: 8px 8px 0 0;
}}
button[data-baseweb="tab"] {{
    height: 44px; padding: 0 18px !important;
    background: transparent !important;
    color: #a8c0d6 !important;
    font-size: 14px !important;
    font-weight: 700 !important;
    letter-spacing: 0.4px;
    border-bottom: 2px solid transparent !important;
}}
button[data-baseweb="tab"]:hover {{ color: {TXT_PRIMARY} !important; }}
button[aria-selected="true"] {{
    color: {TXT_PRIMARY} !important;
    font-weight: 800 !important;
    border-bottom-color: {CLR_INFO} !important;
}}

/* ── Section header ── */
[data-testid="stSubheader"] {{
    color: {TXT_PRIMARY};
    font-weight: 700;
    font-size: 15px;
    letter-spacing: 0.3px;
}}
[data-testid="stCaptionContainer"], .stCaption {{
    color: {TXT_SECOND};
    font-size: 12px;
}}
h1, h2, h3, h4, h5 {{ color: {TXT_PRIMARY}; }}

/* ── Buttons ── */
div.stButton > button {{
    background: {BG_CARD};
    color: {TXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12.5px;
    font-weight: 600;
    letter-spacing: 0.2px;
    transition: all 0.15s;
}}
div.stButton > button:hover {{
    background: #1e293b;
    border-color: {CLR_INFO};
    color: {TXT_PRIMARY};
    box-shadow: 0 0 0 1px {CLR_INFO}33;
}}

/* ── DataFrames ── */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    overflow: hidden;
}}

/* ── Selects ── */
div[data-baseweb="select"] > div {{
    background: {BG_CARD};
    border-color: {BORDER};
    font-size: 13px;
}}
div[data-baseweb="select"] > div:hover {{ border-color: #334155; }}

/* ── Engine status pill ── */
.qc-engine-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 14px 16px;
}}

/* ── Info / Warning / Error ── */
.stAlert {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TXT_SECOND};
}}

/* ── Misc ── */
hr {{ border-color: {BORDER}; margin: 14px 0; }}
.qc-section-title {{
    color: {TXT_PRIMARY};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    margin: 18px 0 10px;
}}
</style>
""", unsafe_allow_html=True)


# =====================================================
# HELPERS
# =====================================================
def fmt_inr(val, signed=True) -> str:
    try:
        v = float(val)
        sign = ("+" if v > 0 else "") if signed else ""
        return f"{sign}₹{v:,.0f}"
    except (ValueError, TypeError):
        return "—"

def fmt_pct(val) -> str:
    try:
        v = float(val)
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.2f}%"
    except (ValueError, TypeError):
        return "—"

def kpi_card(label: str, value: str, color: str | None = None, sub: str | None = None) -> str:
    c = color or TXT_PRIMARY
    sub_html = f'<div class="qc-kpi-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="qc-kpi" style="border-top:2px solid {c}50;">'
        f'<div class="qc-kpi-label">{label}</div>'
        f'<div class="qc-kpi-value" style="color:{c}">{value}</div>'
        f'{sub_html}'
        f'</div>'
    )

def small_pill(text: str, color: str) -> str:
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}44;'
        f'border-radius:6px;padding:2px 10px;font-size:11px;font-weight:700;'
        f'letter-spacing:0.4px;">{text}</span>'
    )


# =====================================================
# LIVE PRICE FETCH (yfinance, 60s cache, parallel)
# =====================================================
@st.cache_data(ttl=60, show_spinner=False)
def _live_prices(tickers_tuple: tuple) -> dict:
    result = {}
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
    return result


# =====================================================
# DATA LOAD + PRE-COMPUTE
# =====================================================
signals = safe_read_csv(MASTER_SIGNALS_FILE)
status  = safe_read_csv(ENGINE_STATUS_FILE)
trades  = safe_read_csv(TRADES_LOG_FILE)
blocked = safe_read_csv(BLOCKED_LOG_FILE)

# Numeric / date casting
if not trades.empty:
    for c in ["EntryPrice", "Qty", "Target", "StopLoss", "CMP", "PnL", "ExitPrice"]:
        if c in trades.columns:
            trades[c] = pd.to_numeric(trades[c], errors="coerce")
    if "Date" in trades.columns:
        trades["Date"] = pd.to_datetime(trades["Date"], format="%d-%m-%Y", errors="coerce")
    if "ExitDate" in trades.columns:
        trades["ExitDate"] = pd.to_datetime(trades["ExitDate"], format="%d-%m-%Y", errors="coerce")

# Open / Closed split
if not trades.empty and "Status" in trades.columns:
    open_trades   = trades[trades["Status"].astype(str).str.upper() == "OPEN"].copy()
    closed_trades = trades[trades["Status"].astype(str).str.upper() == "CLOSED"].copy()
else:
    open_trades   = pd.DataFrame()
    closed_trades = pd.DataFrame()

# Live prices for open positions
live_px = {}
unrealized_pnl = 0.0
if not open_trades.empty and "Ticker" in open_trades.columns:
    tickers_tuple = tuple(open_trades["Ticker"].dropna().astype(str).str.upper().unique().tolist())
    live_px = _live_prices(tickers_tuple)
    open_trades["LiveCMP"] = open_trades["Ticker"].apply(
        lambda t: live_px.get(str(t).upper().replace(".NS", "").replace(".BO", ""))
    )
    open_trades["Live_PnL"] = (open_trades["LiveCMP"] - open_trades["EntryPrice"]) * open_trades["Qty"]
    unrealized_pnl = float(open_trades["Live_PnL"].fillna(0).sum())

# Realized P&L + win rate
realized_pnl = 0.0
win_rate     = 0.0
total_closed = 0
if not closed_trades.empty and "PnL" in closed_trades.columns:
    realized_pnl = float(closed_trades["PnL"].fillna(0).sum())
    total_closed = len(closed_trades)
    if total_closed > 0:
        wins = int((closed_trades["PnL"] > 0).sum())
        win_rate = wins / total_closed * 100

total_pnl            = realized_pnl + unrealized_pnl
active_signals_count = len(signals) if not signals.empty else 0
open_count           = len(open_trades)


# =====================================================
# BRAND STRIP
# =====================================================
now_ts        = pd.Timestamp.now()
market_open   = (9 <= now_ts.hour < 16) and now_ts.weekday() < 5
status_label  = "MARKET OPEN" if market_open else "MARKET CLOSED"
status_dot    = "live" if market_open else "idle"
refresh_label = f"Auto {REFRESH_SECONDS}s" if REFRESH_SECONDS else "Manual refresh"

st.markdown(
    f'<div class="qc-header">'
    f'<div class="qc-brand">'
    f'<div class="qc-brand-mark">Q</div>'
    f'<span>QUANT CONTROL CENTER</span>'
    f'</div>'
    f'<div class="qc-status">'
    f'<span><span class="qc-dot {status_dot}"></span>{status_label}</span>'
    f'<span>{now_ts.strftime("%a, %d %b · %H:%M:%S IST")}</span>'
    f'<span>{refresh_label}</span>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# session state — stores last run result so it survives st.rerun()
if "engine_result" not in st.session_state:
    st.session_state.engine_result = None

rc1, rc2, _ = st.columns([1, 1, 8])
with rc1:
    if st.button("🔄 Refresh data", key="global_refresh"):
        st.session_state.engine_result = None
        _live_prices.clear()
        st.rerun()
with rc2:
    if st.button("⚡ Run Engines", key="run_engines",
                 help="Scan all 6 engines · save signals · send Telegram + Email"):

        _app_root = Path(__file__).resolve().parent.parent
        _run_env  = {**os.environ, "PYTHONIOENCODING": "utf-8"}

        # ── step 1: find orchestrator ──────────────────────────────────
        _orch = None
        for _cand in [
            _app_root / "core" / "orchestrator.py",
            _app_root / "orchestrator.py",
        ]:
            if _cand.exists():
                _orch = _cand
                break

        if _orch is None:
            st.session_state.engine_result = {
                "kind": "error",
                "main": "orchestrator.py not found — expected at project_root/core/ or project_root/",
                "hint": "",
            }
        else:
            # ── step 2: run engines ────────────────────────────────────
            with st.spinner("⚙️ Running all 6 engines…"):
                _result = subprocess.run(
                    [sys.executable, str(_orch)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    cwd=str(_orch.parent),
                    timeout=600,
                    env=_run_env,
                )

            _stdout   = (_result.stdout or "").strip()
            _stderr   = (_result.stderr or "").strip()
            _full_log = (_stdout + ("\n" + _stderr if _stderr else "")).strip()

            _failed = [e for e in ["E1","E2","E3","E4","E5","E6"]
                       if f"{e} FAILED"    in _stdout]
            _done   = [e for e in ["E1","E2","E3","E4","E5","E6"]
                       if f"{e} completed" in _stdout]
            _empty  = [e for e in ["E1","E2","E3","E4","E5","E6"]
                       if e not in _failed and e not in _done
                       and f"Running {e}" in _stdout]

            # save run log
            _log_path = None
            try:
                _log_path = _app_root / "signals" / "engine_run.log"
                _log_path.parent.mkdir(parents=True, exist_ok=True)
                _ts = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(_log_path, "a", encoding="utf-8") as _lf:
                    _lf.write(f"\n{'='*60}\nRun: {_ts}\n{'='*60}\n{_full_log}\n")
            except Exception:
                pass

            # ── step 3: dispatch alerts ────────────────────────────────
            _tg_ok = _em_ok = _no_sigs = _alert_run = False

            if _done:
                _sa = _app_root / "core" / "signal_alerts.py"
                if _sa.exists():
                    _alert_run = True
                    with st.spinner("📨 Sending Telegram + Email alerts…"):
                        _sa_res = subprocess.run(
                            [sys.executable, str(_sa)],
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            cwd=str(_sa.parent),
                            timeout=30,
                            env=_run_env,
                        )
                    _sa_out  = (_sa_res.stdout or "").strip()
                    _tg_ok   = "TELEGRAM: sent ok" in _sa_out
                    _em_ok   = "EMAIL: sent ok"     in _sa_out
                    _no_sigs = "no signals for today" in _sa_out
                    try:
                        if _log_path:
                            with open(_log_path, "a", encoding="utf-8") as _lf:
                                _lf.write(f"\n[ALERTS]\n{_sa_out}\n")
                    except Exception:
                        pass

            # ── step 4: store result → rerun renders it full-width ─────
            _eng_line = (
                f"✅ {len(_done)} ok  ·  "
                f"⬜ {len(_empty)} empty  ·  "
                f"❌ {len(_failed)} failed"
            )
            _alert_line = ""
            if _alert_run and not _no_sigs:
                _alert_line = (
                    ("📱 ✓" if _tg_ok else "📱 ✗") + "   " +
                    ("📧 ✓" if _em_ok else "📧 ✗")
                )

            _hint = ""
            if _alert_run and not _tg_ok and not _em_ok and not _no_sigs:
                _hint = (
                    "Alerts not sent — check TELEGRAM_BOT_TOKEN, "
                    "TELEGRAM_CHAT_ID, EMAIL_SENDER, EMAIL_PASSWORD, "
                    "EMAIL_RECEIVER in config.py"
                )

            _main_msg = _eng_line
            if _alert_line:
                _main_msg += f"   ·   {_alert_line}"
            if not _failed:
                _main_msg += "   ·   click Refresh Data to load signals"
            else:
                _main_msg += "   ·   see signals/engine_run.log"

            st.session_state.engine_result = {
                "kind": "warning" if _failed else "success",
                "main": _main_msg,
                "hint": _hint,
            }

        st.rerun()

# ── full-width status bar (outside any column) ─────────────────────────
if st.session_state.get("engine_result"):
    _er = st.session_state.engine_result
    if _er["kind"] == "error":
        st.error(_er["main"])
    elif _er["kind"] == "warning":
        st.warning(_er["main"])
    else:
        st.success(_er["main"])
    if _er.get("hint"):
        st.info(_er["hint"])
# =====================================================
# RETURN HELPERS
# =====================================================

# Trades before this date are treated as pre-system noise. The live system's
# first trade was 16 Mar 2026; this floor keeps inception/CAGR maths honest if
# any stray or backfilled rows exist in trades_log.csv. Adjust if you backfill.
SYSTEM_START_FLOOR = pd.Timestamp("2026-01-01")

# Allocated capital per engine (the authentic denominator for return-on-capital).
ENGINE_CAPITAL = {
    str(k): float((v or {}).get("capital", 0) or 0)
    for k, v in (ENGINE_RULES or {}).items()
}


@st.cache_data(ttl=300, show_spinner=False)
def _engine_return_table(trades_df):

    cols = [
        "Engine", "CAGR", "ROC", "PnL", "Capital",
        "Days", "Trades", "Inception",
    ]

    if trades_df.empty or "Engine" not in trades_df.columns:
        return pd.DataFrame(columns=cols)

    def _num(frame, col):
        if col in frame.columns:
            return pd.to_numeric(frame[col], errors="coerce")
        return pd.Series(np.nan, index=frame.index, dtype="float64")

    today = pd.Timestamp.today().normalize()

    def _valid_dates(frame):
        if "Date" not in frame.columns:
            return pd.Series([], dtype="datetime64[ns]")
        d = pd.to_datetime(frame["Date"], errors="coerce")
        return d[(d.notna()) & (d >= SYSTEM_START_FLOOR) & (d <= today)]

    rows = []
    engines = sorted(
        trades_df["Engine"].dropna().astype(str).unique().tolist()
    )

    for eng in engines:
        try:
            sub = trades_df[trades_df["Engine"].astype(str) == eng].copy()
            if sub.empty:
                continue

            if "Status" in sub.columns:
                status = sub["Status"].astype(str).str.upper()
            else:
                status = pd.Series(["OPEN"] * len(sub), index=sub.index)

            closed = sub[status == "CLOSED"].copy()
            open_pos = sub[status == "OPEN"].copy()

            # realized P&L from closed trades
            realized = 0.0
            if not closed.empty:
                realized = float(_num(closed, "PnL").fillna(0).sum())

            # unrealized P&L from open trades (live CMP where available)
            unrealized = 0.0
            if not open_pos.empty:
                entry = _num(open_pos, "EntryPrice")
                qty = _num(open_pos, "Qty")
                if "LiveCMP" in open_pos.columns:
                    live_cmp = _num(open_pos, "LiveCMP")
                elif "CMP" in open_pos.columns:
                    live_cmp = _num(open_pos, "CMP")
                else:
                    live_cmp = entry.copy()
                unrealized = float(
                    ((live_cmp.fillna(entry) - entry) * qty).fillna(0).sum()
                )

            total_pnl = float(realized + unrealized)

            # --- denominator: allocated capital from config (authentic) ---
            capital = ENGINE_CAPITAL.get(eng, 0.0)
            if capital <= 0:
                # fallback: total capital deployed across this engine's trades
                deployed = (_num(sub, "EntryPrice") * _num(sub, "Qty"))
                deployed = deployed.replace([np.inf, -np.inf], np.nan).dropna()
                capital = float(deployed.sum()) if not deployed.empty else 0.0
            if capital <= 0:
                continue

            # --- inception (validated) + days since first trade ---
            vdates = _valid_dates(sub)
            if vdates.empty:
                continue
            start_dt = vdates.min().normalize()
            days = max((today - start_dt).days, 1)

            # period return on capital, then annualised CAGR
            roc = total_pnl / capital
            if (1.0 + roc) > 0:
                cagr = ((1.0 + roc) ** (365.0 / days) - 1.0) * 100.0
            else:
                cagr = -100.0

            rows.append({
                "Engine": eng,
                "CAGR": round(cagr, 1),
                "ROC": round(roc * 100.0, 1),
                "PnL": round(total_pnl, 0),
                "Capital": round(capital, 0),
                "Days": int(days),
                "Trades": int(len(sub)),
                "Inception": start_dt,
            })

        except Exception:
            continue

    out = pd.DataFrame(rows, columns=cols)
    if out.empty:
        return pd.DataFrame(columns=cols)

    return out.sort_values("CAGR", ascending=False)

# =====================================================
# KPI RIBBON
# =====================================================
total_acc  = CLR_BULL if total_pnl      >= 0 else CLR_BEAR
real_acc   = CLR_BULL if realized_pnl   >= 0 else CLR_BEAR
unreal_acc = CLR_BULL if unrealized_pnl >= 0 else CLR_BEAR
wr_acc     = CLR_BULL if win_rate >= 50 else CLR_WARN if win_rate >= 35 else CLR_BEAR

st.markdown(
    '<div class="qc-ribbon">'
    + kpi_card("TOTAL P&L",      fmt_inr(total_pnl),       color=total_acc,  sub="Realized + Unrealized")
    + kpi_card("REALIZED",       fmt_inr(realized_pnl),    color=real_acc,   sub=f"{total_closed} closed trades")
    + kpi_card("UNREALIZED",     fmt_inr(unrealized_pnl),  color=unreal_acc, sub=f"{open_count} open positions")
    + kpi_card("OPEN POSITIONS", f"{open_count}",          sub="live tracking")
    + kpi_card("WIN RATE",       f"{win_rate:.1f}%",       color=wr_acc,     sub=f"{total_closed} samples")
    + kpi_card("ACTIVE SIGNALS", f"{active_signals_count}",color=CLR_INFO,   sub="in queue")
    + '</div>',
    unsafe_allow_html=True,
)

# =====================================================
# ENGINE + PORTFOLIO RETURN RIBBON
# =====================================================

return_df = _engine_return_table(trades.copy())

# ----- Combined portfolio CAGR (allocated capital + validated inception) -----
if not trades.empty and "Engine" in trades.columns:
    _traded_engines = trades["Engine"].dropna().astype(str).unique().tolist()
    total_alloc = float(sum(ENGINE_CAPITAL.get(e, 0.0) for e in _traded_engines))
else:
    total_alloc = 0.0

if total_alloc <= 0 and not return_df.empty:
    total_alloc = float(return_df["Capital"].sum())

portfolio_inception = pd.NaT
if not trades.empty and "Date" in trades.columns:
    _ad = pd.to_datetime(trades["Date"], errors="coerce")
    _today = pd.Timestamp.today().normalize()
    _ad = _ad[(_ad.notna()) & (_ad >= SYSTEM_START_FLOOR) & (_ad <= _today)]
    if not _ad.empty:
        portfolio_inception = _ad.min().normalize()

if pd.notna(portfolio_inception) and total_alloc > 0:
    p_days = max((pd.Timestamp.today().normalize() - portfolio_inception).days, 1)
    p_roc = total_pnl / total_alloc
    portfolio_cagr = (
        ((1.0 + p_roc) ** (365.0 / p_days) - 1.0) * 100.0
        if (1.0 + p_roc) > 0 else -100.0
    )
    portfolio_roc = p_roc * 100.0
else:
    p_days = None
    portfolio_cagr = np.nan
    portfolio_roc = np.nan


def _ret_color(v):
    if pd.isna(v):
        return TXT_MUTED
    if v >= 25:
        return CLR_BULL
    if v >= 12:
        return CLR_INFO
    if v >= 0:
        return CLR_WARN
    return CLR_BEAR


cards_html = ""

# ----- Portfolio (combined) card -----
if pd.isna(portfolio_cagr):
    p_txt = "—"
    p_sub = "awaiting data"
else:
    p_txt = f"{portfolio_cagr:+.1f}%"
    _since = (
        portfolio_inception.strftime("%d %b %Y")
        if pd.notna(portfolio_inception) else "inception"
    )
    p_sub = f"ROC {portfolio_roc:+.1f}% · since {_since}"

cards_html += kpi_card(
    "PORTFOLIO CAGR",
    p_txt,
    color=_ret_color(portfolio_cagr),
    sub=p_sub,
)

# ----- Per-engine cards -----
if not return_df.empty:
    for _, r in return_df.iterrows():
        eng = str(r["Engine"])
        cagr_val = r["CAGR"]
        if pd.isna(cagr_val):
            txt = "—"
            sub = f"{int(r['Trades'])} trades"
        else:
            txt = f"{cagr_val:+.1f}%"
            sub = (
                f"ROC {r['ROC']:+.1f}% · "
                f"{int(r['Trades'])} trades · {int(r['Days'])}d"
            )
        cards_html += kpi_card(
            f"{eng} CAGR",
            txt,
            color=_ret_color(cagr_val),
            sub=sub,
        )

st.markdown(
    '<div class="qc-ribbon">'
    + cards_html
    + '</div>',
    unsafe_allow_html=True,
)

st.caption(
    "CAGR = annualised return on each engine's allocated capital "
    "(realized + unrealized P&L) measured from its first trade. ROC is the "
    "raw period return on that capital. Early CAGR is volatile by nature and "
    "stabilises as the track record lengthens."
)

# =====================================================
# TABS
# =====================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "Today Actions",
    "Open Positions",
    "Closed Trades",
    "Engines",
    "Alerts",
    "News",
    "Portfolio",
    "AI Intelligence",
    "Trade Entry",
])


# =====================================================
# TAB 1 — TODAY ACTIONS  (signal queue)
# =====================================================
with tab1:
    sh1, _ = st.columns([6, 1])
    with sh1:
        st.subheader("Signal Queue")
        st.caption(f"Master signal feed from orchestrator · {len(signals)} pending")

    if signals.empty:
        st.info("No signals queued. Run the orchestrator to generate today's signals.")
    else:
        view_cols = [c for c in [
            "Date","Engine","Ticker","Action","Entry","SL","Target","Qty","Capital","Sector","Score","Status"
        ] if c in signals.columns]

        disp = signals[view_cols].sort_values(["Engine","Ticker"]).copy()

        fmt_dict = {}
        for c in ["Entry","SL","Target","Capital","Score"]:
            if c in disp.columns: fmt_dict[c] = "₹{:,.2f}" if c in ("Entry","SL","Target","Capital") else "{:.2f}"
        if "Qty" in disp.columns: fmt_dict["Qty"] = "{:.0f}"

        try:
            styled = disp.style.format(fmt_dict, na_rep="—")
        except Exception:
            styled = disp

        st.dataframe(styled, use_container_width=True, hide_index=True)


# =====================================================
# TAB 2 — OPEN POSITIONS (live)
# =====================================================
with tab2:
    sh1, sh2 = st.columns([6, 1])
    with sh1:
        st.subheader("Live Open Positions")
        st.caption(f"CMP via yfinance · auto-refresh 60s · last: {now_ts.strftime('%H:%M:%S')}")
    with sh2:
        st.write("")
        if st.button("Live", key="pos_refresh"):
            _live_prices.clear()
            st.rerun()

    if open_trades.empty:
        st.info("No open positions.")
    else:
        df = open_trades.copy()
        today = pd.Timestamp.today().normalize()
        df["Days_Held"] = (today - df["Date"].dt.normalize()).dt.days
        df["PnL_%"]   = (df["LiveCMP"] - df["EntryPrice"]) / df["EntryPrice"] * 100
        df["SL_Gap%"] = (df["LiveCMP"] - df["StopLoss"])   / df["LiveCMP"] * 100
        df["TP_Gap%"] = (df["Target"]  - df["LiveCMP"])    / df["LiveCMP"] * 100

        def _alert(r):
            try:
                sl, tp = float(r["SL_Gap%"]), float(r["TP_Gap%"])
                if sl <= 0:   return "🚨 SL BREACHED"
                if sl <= 2:   return "🔴 Near SL"
                if sl <= 5:   return "🟡 Watch SL"
                if tp <= 2:   return "🎯 Near Target"
                if float(r["Live_PnL"]) > 0: return "🟢 Profit"
            except Exception:
                pass
            return "⚪ Hold"
        df["Alert"] = df.apply(_alert, axis=1)

        breached = int((df["Alert"] == "🚨 SL BREACHED").sum())
        near_sl  = int(df["Alert"].str.contains("Near SL|Watch SL", na=False).sum())
        near_tp  = int((df["Alert"] == "🎯 Near Target").sum())
        in_prof  = int((df["Live_PnL"] > 0).sum())

        st.markdown(
            '<div class="qc-ribbon" style="grid-template-columns:repeat(4,1fr);">'
            + kpi_card("BREACHED",     str(breached), color=CLR_BEAR  if breached else TXT_MUTED, sub="below stop loss")
            + kpi_card("NEAR SL",      str(near_sl),  color=CLR_WARN  if near_sl  else TXT_MUTED, sub="within 5%")
            + kpi_card("NEAR TARGET",  str(near_tp),  color=CLR_BULL  if near_tp  else TXT_MUTED, sub="within 2%")
            + kpi_card("IN PROFIT",    f"{in_prof}/{len(df)}", color=CLR_BULL if in_prof else TXT_MUTED, sub="positions")
            + '</div>',
            unsafe_allow_html=True,
        )

        disp = df[[
            "Ticker","Engine","EntryPrice","Qty","LiveCMP","PnL_%","Live_PnL","Days_Held",
            "StopLoss","SL_Gap%","Target","TP_Gap%","Alert"
        ]].sort_values("SL_Gap%", ascending=True).copy()
        disp.columns = [
            "Ticker","Engine","Entry ₹","Qty","CMP ₹","P&L %","P&L ₹","Days",
            "SL ₹","SL Gap%","Target ₹","TP Gap%","Alert"
        ]

        def _bg(row):
            a = str(row["Alert"])
            if "BREACHED" in a: c = "#ef444422"
            elif "Near SL" in a: c = "#f59e0b18"
            elif "Watch"   in a: c = "#f59e0b0c"
            elif "Target"  in a: c = "#10b98120"
            elif "Profit"  in a: c = "#10b98108"
            else:                c = ""
            return [f"background:{c}"] * len(row)

        def _num(val):
            try:
                v = float(str(val).replace("%","").replace("₹","").replace(",","").replace("+",""))
                if v > 0: return f"color:{CLR_BULL};font-weight:600"
                if v < 0: return f"color:{CLR_BEAR};font-weight:600"
            except Exception:
                pass
            return ""

        fmt = {
            "Entry ₹":"₹{:,.2f}","CMP ₹":"₹{:,.2f}","SL ₹":"₹{:,.2f}","Target ₹":"₹{:,.2f}",
            "P&L %":"{:+.2f}%","SL Gap%":"{:+.2f}%","TP Gap%":"{:+.2f}%",
            "P&L ₹":"₹{:,.0f}","Qty":"{:.0f}","Days":"{:.0f}",
        }
        colored = ["P&L %","P&L ₹","SL Gap%","TP Gap%"]
        try:
            styled = disp.style.apply(_bg, axis=1).map(_num, subset=colored).format(fmt, na_rep="—")
        except AttributeError:
            styled = disp.style.apply(_bg, axis=1).applymap(_num, subset=colored).format(fmt, na_rep="—")

        st.dataframe(styled, use_container_width=True, hide_index=True)


# =====================================================
# TAB 3 — CLOSED TRADES / REALIZED P&L  (NEW)
# =====================================================
with tab3:
    st.subheader("Closed Trades · Realized P&L")
    st.caption(f"Historical trade book from trades_log.csv · {total_closed} closed trades")

    if closed_trades.empty:
        st.info("No closed trades in the log yet.")
    else:
        df = closed_trades.copy()
        df["PnL"] = pd.to_numeric(df["PnL"], errors="coerce")

        def _outcome(r):
            try:
                exit_p = float(r["ExitPrice"])
                tgt    = float(r["Target"])
                sl     = float(r["StopLoss"])
                if exit_p >= tgt * 0.98: return "🎯 TP"
                if exit_p <= sl  * 1.02: return "🛑 SL"
                return "✋ Manual"
            except Exception:
                return "—"
        df["Outcome"] = df.apply(_outcome, axis=1)
        df["Return_%"] = (df["ExitPrice"] - df["EntryPrice"]) / df["EntryPrice"] * 100
        if "ExitDate" in df.columns:
            df["Days_Held"] = (df["ExitDate"] - df["Date"]).dt.days

        # ── Top KPIs ──
        n      = len(df)
        wins   = int((df["PnL"] > 0).sum())
        losses = int((df["PnL"] < 0).sum())
        wr     = (wins / n * 100) if n else 0
        avg_w  = df.loc[df["PnL"] > 0, "PnL"].mean() if wins else 0
        avg_l  = df.loc[df["PnL"] < 0, "PnL"].mean() if losses else 0
        gp     = df.loc[df["PnL"] > 0, "PnL"].sum() if wins else 0
        gl     = abs(df.loc[df["PnL"] < 0, "PnL"].sum()) if losses else 0
        pf     = gp / gl if gl > 0 else (float("inf") if gp > 0 else 0)
        pf_str = f"{pf:.2f}" if pf != float("inf") else "∞"
        pf_acc = CLR_BULL if pf >= 1.5 else CLR_WARN if pf >= 1 else CLR_BEAR
        tot_acc= CLR_BULL if realized_pnl >= 0 else CLR_BEAR

        st.markdown(
            '<div class="qc-ribbon">'
            + kpi_card("REALIZED P&L",   fmt_inr(realized_pnl), color=tot_acc)
            + kpi_card("TRADES",         f"{n}", sub=f"▲ {wins} · ▼ {losses}")
            + kpi_card("WIN RATE",       f"{wr:.1f}%", color=CLR_BULL if wr >= 50 else CLR_WARN)
            + kpi_card("AVG WIN",        fmt_inr(avg_w), color=CLR_BULL)
            + kpi_card("AVG LOSS",       fmt_inr(avg_l), color=CLR_BEAR)
            + kpi_card("PROFIT FACTOR",  pf_str, color=pf_acc, sub="gross profit / gross loss")
            + '</div>',
            unsafe_allow_html=True,
        )

        # ── Engine breakdown ──
        if "Engine" in df.columns:
            eng = (
                df.groupby("Engine")
                  .agg(Trades=("PnL","count"), PnL=("PnL","sum"),
                       Wins=("PnL", lambda s: int((s > 0).sum())))
                  .reset_index()
                  .sort_values("Engine")
            )
            eng["WR"] = eng.apply(lambda r: r["Wins"]/r["Trades"]*100 if r["Trades"] else 0, axis=1)

            st.markdown('<div class="qc-section-title">Engine Performance</div>', unsafe_allow_html=True)
            cards = st.columns(max(len(eng), 1))
            for i, row in enumerate(eng.itertuples(index=False)):
                acc = CLR_BULL if row.PnL >= 0 else CLR_BEAR
                with cards[i]:
                    st.markdown(
                        f'<div class="qc-engine-card" style="border-left:3px solid {acc};">'
                        f'<div style="color:{TXT_PRIMARY};font-size:12px;font-weight:700;letter-spacing:1.2px;">{row.Engine}</div>'
                        f'<div style="color:{acc};font-size:18px;font-weight:700;margin-top:2px;">{fmt_inr(row.PnL)}</div>'
                        f'<div style="color:{TXT_SECOND};font-size:12px;margin-top:3px;">'
                        f'{int(row.Trades)} trades · WR {row.WR:.0f}%</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown('<div class="qc-section-title">Trade Book</div>', unsafe_allow_html=True)

        # ── Filters ──
        engines = sorted(df["Engine"].dropna().unique().tolist()) if "Engine" in df.columns else []
        fc1, fc2, fc3 = st.columns([2, 2, 2])
        with fc1:
            engine_sel = st.multiselect(
                "Engine", engines, default=engines,
                key="closed_eng", label_visibility="collapsed",
                placeholder="All engines",
            )
        with fc2:
            outcome_sel = st.selectbox(
                "Outcome",
                ["All trades", "Wins only", "Losses only", "TP hits", "SL hits", "Manual exits"],
                key="closed_outcome", label_visibility="collapsed",
            )
        with fc3:
            sort_sel = st.selectbox(
                "Sort",
                ["Date ↓", "Date ↑", "P&L ↓", "P&L ↑", "Return % ↓", "Return % ↑"],
                key="closed_sort", label_visibility="collapsed",
            )

        f = df.copy()
        if engine_sel and "Engine" in f.columns:
            f = f[f["Engine"].isin(engine_sel)]
        if   outcome_sel == "Wins only":    f = f[f["PnL"] > 0]
        elif outcome_sel == "Losses only":  f = f[f["PnL"] < 0]
        elif outcome_sel == "TP hits":      f = f[f["Outcome"] == "🎯 TP"]
        elif outcome_sel == "SL hits":      f = f[f["Outcome"] == "🛑 SL"]
        elif outcome_sel == "Manual exits": f = f[f["Outcome"] == "✋ Manual"]

        sort_map = {
            "Date ↓":      ("Date",     False),
            "Date ↑":      ("Date",     True),
            "P&L ↓":       ("PnL",      False),
            "P&L ↑":       ("PnL",      True),
            "Return % ↓":  ("Return_%", False),
            "Return % ↑":  ("Return_%", True),
        }
        sc, sa = sort_map[sort_sel]
        if sc in f.columns:
            f = f.sort_values(sc, ascending=sa)

        if f.empty:
            st.info("No trades match the selected filters.")
        else:
            cols_have = [c for c in [
                "Date","ExitDate","Engine","Ticker","EntryPrice","ExitPrice",
                "Qty","PnL","Return_%","Days_Held","Outcome"
            ] if c in f.columns]
            disp = f[cols_have].copy()
            rename = {
                "Date":"Entry","ExitDate":"Exit","EntryPrice":"Entry ₹",
                "ExitPrice":"Exit ₹","PnL":"P&L ₹","Return_%":"Return %","Days_Held":"Days",
            }
            disp.columns = [rename.get(c, c) for c in disp.columns]

            def _bg(row):
                try:
                    v = float(row["P&L ₹"])
                    c = "#10b98112" if v > 0 else "#ef444412" if v < 0 else ""
                except Exception:
                    c = ""
                return [f"background:{c}"] * len(row)

            def _num(val):
                try:
                    v = float(str(val).replace("%","").replace("₹","").replace(",","").replace("+",""))
                    if v > 0: return f"color:{CLR_BULL};font-weight:600"
                    if v < 0: return f"color:{CLR_BEAR};font-weight:600"
                except Exception:
                    pass
                return ""

            fmt = {}
            if "Entry ₹"  in disp.columns: fmt["Entry ₹"]  = "₹{:,.2f}"
            if "Exit ₹"   in disp.columns: fmt["Exit ₹"]   = "₹{:,.2f}"
            if "P&L ₹"    in disp.columns: fmt["P&L ₹"]    = "₹{:,.0f}"
            if "Return %" in disp.columns: fmt["Return %"] = "{:+.2f}%"
            if "Qty"      in disp.columns: fmt["Qty"]      = "{:.0f}"
            if "Days"     in disp.columns: fmt["Days"]     = "{:.0f}"

            colored = [c for c in ["P&L ₹","Return %"] if c in disp.columns]
            try:
                styled = disp.style.apply(_bg, axis=1).map(_num, subset=colored).format(fmt, na_rep="—")
            except AttributeError:
                styled = disp.style.apply(_bg, axis=1).applymap(_num, subset=colored).format(fmt, na_rep="—")

            st.dataframe(styled, use_container_width=True, hide_index=True)

            sel_pnl   = float(f["PnL"].sum())
            sel_acc   = CLR_BULL if sel_pnl >= 0 else CLR_BEAR
            st.markdown(
                f'<div style="color:{TXT_MUTED};font-size:12px;margin-top:8px;">'
                f'Showing <b style="color:{TXT_PRIMARY}">{len(f)}</b> of <b style="color:{TXT_PRIMARY}">{n}</b> trades · '
                f'Selection P&L: <b style="color:{sel_acc}">{fmt_inr(sel_pnl)}</b>'
                f'</div>',
                unsafe_allow_html=True,
            )


# =====================================================
# TAB 4 — ENGINES
# =====================================================
with tab4:
    st.subheader("Engine Health")
    st.caption("Last orchestrator run status per engine")

    if status.empty:
        st.info("No engine status logged yet. Run the orchestrator.")
    else:
        latest = status.copy()
        if "Timestamp" in latest.columns:
            latest["Timestamp"] = pd.to_datetime(latest["Timestamp"], errors="coerce")
            latest = latest.sort_values("Timestamp", ascending=False)
        if "Engine" in latest.columns:
            latest_per_engine = latest.drop_duplicates(subset=["Engine"], keep="first")
        else:
            latest_per_engine = latest.head(6)

        if not latest_per_engine.empty:
            cards = st.columns(max(len(latest_per_engine), 1))
            for i, row in enumerate(latest_per_engine.itertuples(index=False)):
                eng    = getattr(row, "Engine", "?")
                eng_st = str(getattr(row, "Status", "?")).upper()
                detail = str(getattr(row, "Detail", ""))[:40]
                ts     = getattr(row, "Timestamp", None)
                ts_str = ts.strftime("%H:%M") if pd.notna(ts) else "—"
                acc    = CLR_BULL if eng_st == "SUCCESS" else CLR_BEAR if eng_st == "FAILED" else CLR_WARN
                with cards[i]:
                    st.markdown(
                        f'<div class="qc-engine-card" style="border-left:3px solid {acc};">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<span style="color:{TXT_PRIMARY};font-size:12px;font-weight:700;letter-spacing:1.2px;">{eng}</span>'
                        f'<span style="color:{TXT_SECOND};font-size:11px;">{ts_str}</span>'
                        f'</div>'
                        f'<div style="color:{acc};font-size:14px;font-weight:700;margin-top:6px;letter-spacing:0.4px;">{eng_st}</div>'
                        f'<div style="color:{TXT_SECOND};font-size:12px;margin-top:4px;">{detail}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown('<div class="qc-section-title">Run History</div>', unsafe_allow_html=True)
        cols = [c for c in ["Timestamp","Date","Engine","Status","Detail"] if c in status.columns]
        st.dataframe(
            status[cols].sort_values("Timestamp", ascending=False) if "Timestamp" in cols else status[cols],
            use_container_width=True, hide_index=True,
        )


# =====================================================
# TAB 5 — ALERTS / BLOCKS
# =====================================================
with tab5:
    st.subheader("Filtered & Blocked Signals")
    st.caption(f"Signals rejected by risk filters · {len(blocked)} total")

    if blocked.empty:
        st.info("No blocked signals.")
    else:
        if "Reason" in blocked.columns:
            reason_counts = blocked["Reason"].value_counts().head(6)
            if not reason_counts.empty:
                st.markdown('<div class="qc-section-title">Block Reasons</div>', unsafe_allow_html=True)
                rcols = st.columns(len(reason_counts))
                for i, (reason, cnt) in enumerate(reason_counts.items()):
                    with rcols[i]:
                        st.markdown(
                            f'<div class="qc-engine-card" style="border-left:3px solid {CLR_WARN};">'
                            f'<div style="color:{TXT_MUTED};font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">{str(reason)[:24]}</div>'
                            f'<div style="color:{CLR_WARN};font-size:20px;font-weight:700;margin-top:4px;">{cnt}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

        cols = [c for c in ["Date","Engine","Ticker","Reason"] if c in blocked.columns]
        st.markdown('<div class="qc-section-title">Block Log</div>', unsafe_allow_html=True)
        st.dataframe(
            blocked[cols].sort_values(["Date","Engine"], ascending=False) if "Date" in cols else blocked[cols],
            use_container_width=True, hide_index=True,
        )


# =====================================================
# TAB 6 — NEWS
# =====================================================
SOURCE_COLORS = {"mc": CLR_BULL, "nse": CLR_WARN, "news": CLR_INFO}
SOURCE_LABELS = {"mc": "MC", "nse": "NSE", "news": "NEWS"}

@st.cache_data(ttl=300, show_spinner="Loading portfolio news…")
def _cached_news():
    return get_portfolio_news()

with tab6:
    sh1, sh2 = st.columns([6, 1])
    with sh1:
        st.subheader("Portfolio News Feed")
        st.caption("Live news for open positions · auto-refresh 5min")
    with sh2:
        st.write("")
        if st.button("Refresh", key="news_refresh"):
            _cached_news.clear()
            st.rerun()

    news_items = _cached_news()

    if not news_items:
        st.info("No news found. Ensure trades_log.csv has OPEN positions.")
    else:
        mc_n  = sum(1 for i in news_items if i.get("Source_Type") == "mc")
        nse_n = sum(1 for i in news_items if i.get("Source_Type") == "nse")
        gn_n  = sum(1 for i in news_items if i.get("Source_Type") == "news")

        st.markdown(
            '<div class="qc-ribbon" style="grid-template-columns:repeat(4,1fr);">'
            + kpi_card("MONEYCONTROL", str(mc_n),  color=CLR_BULL)
            + kpi_card("NSE FILINGS",  str(nse_n), color=CLR_WARN)
            + kpi_card("MEDIA",        str(gn_n),  color=CLR_INFO)
            + kpi_card("TOTAL STORIES",str(len(news_items)), sub=f"{len(set(i['Ticker'] for i in news_items))} stocks")
            + '</div>',
            unsafe_allow_html=True,
        )

        all_t = ["All stocks"] + sorted(set(i["Ticker"] for i in news_items))
        fc, _ = st.columns([2, 4])
        with fc:
            sel = st.selectbox("Filter", all_t, label_visibility="collapsed", key="news_filter")

        filtered = news_items if sel == "All stocks" else [i for i in news_items if i["Ticker"] == sel]

        for it in filtered:
            ticker   = it.get("Ticker", "")
            title    = it.get("Title", "")
            link     = it.get("Link", "#")
            provider = it.get("Provider", "")
            pub      = it.get("Published", "")
            ago      = it.get("Published_Ago", "")
            stype    = it.get("Source_Type", "news")
            color    = SOURCE_COLORS.get(stype, CLR_INFO)
            badge    = SOURCE_LABELS.get(stype, "NEWS")
            bare     = ticker.replace(".NS", "").replace(".BO", "")

            st.markdown(
                f'<div style="background:{BG_PANEL};border:1px solid {BORDER};'
                f'border-left:3px solid {color};border-radius:8px;padding:14px 18px;margin-bottom:8px;">'
                f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">'
                f'<div style="display:flex;gap:8px;align-items:center;">'
                f'<span style="background:{color}22;color:{color};border:1px solid {color}44;'
                f'border-radius:5px;padding:2px 9px;font-size:10.5px;font-weight:700;letter-spacing:0.4px;">{bare}</span>'
                f'<span style="background:{BG_HOVER};color:{TXT_SECOND};border-radius:5px;'
                f'padding:2px 8px;font-size:10.5px;font-weight:600;">{badge}</span>'
                f'<span style="color:{TXT_MUTED};font-size:11px;">{provider}</span>'
                f'</div>'
                f'<span style="color:{TXT_DIM};font-size:11px;white-space:nowrap;">{ago}</span>'
                f'</div>'
                f'<a href="{link}" target="_blank" style="color:{TXT_PRIMARY};font-size:14px;font-weight:500;'
                f'text-decoration:none;line-height:1.5;display:block;">{title}</a>'
                f'<div style="margin-top:6px;color:{TXT_DIM};font-size:11px;">{pub}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# =====================================================
# PORTFOLIO HELPERS
# =====================================================
def _gsheet_csv(sheet_name: str) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{PORTFOLIO_GSHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    )

def _parse_date(val) -> str:
    s = str(val).strip()
    try:
        f = float(s)
        return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(f))).strftime("%d-%b-%y")
    except (ValueError, TypeError):
        pass
    for fmt in ("%d-%m-%y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return pd.to_datetime(s, format=fmt).strftime("%d-%b-%y")
        except Exception:
            pass
    return s

@st.cache_data(ttl=300, show_spinner="Syncing portfolio from Google Sheets…")
def _load_portfolio():
    live   = pd.read_csv(_gsheet_csv("Live"))
    booked = pd.read_csv(_gsheet_csv("Booked"))
    return live, booked

# =====================================================
# ACTION ENGINE HELPERS
# =====================================================

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"

SECTOR_MAP_FILE = DATA_DIR / "sector_map_fixed.csv"
RESULT_CALENDAR_FILE = DATA_DIR / "result_calendar.csv"

ACTION_COLORS = {
    "ACCUMULATE": "#16a34a",
    "HOLD": "#2563eb",
    "TRIM": "#a855f7",
    "BOOK PROFIT": "#9333ea",
    "REDUCE": "#ea580c",
    "EXIT": "#dc2626",
}

# -----------------------------------------------------
# Utilities
# -----------------------------------------------------

def _find_col(df, candidates):
    lookup = {str(c).strip().lower(): c for c in df.columns}
    for name in candidates:
        key = name.strip().lower()
        if key in lookup:
            return lookup[key]
    return None


def _bare_ticker(ticker):
    t = str(ticker).upper().strip()
    # Strip exchange prefixes (Google Sheets / Google Finance format: "NSE:TCS")
    for pre in ("NSE:", "BSE:", "NSEI:", "BSEI:"):
        if t.startswith(pre):
            t = t[len(pre):]
            break
    # Strip exchange suffixes (Yahoo Finance format: "TCS.NS")
    for suf in (".NS", ".BO", ".NSE", ".BSE"):
        if t.endswith(suf):
            return t[:-len(suf)]
    return t


def _yf_symbol(ticker):
    t = _bare_ticker(ticker)
    return t if "." in t else f"{t}.NS"


def _safe_float(v, default=0.0):
    try:
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def _pct_to_number(v):
    """
    yfinance often returns ratios like 0.23 for 23%.
    If the absolute value is small, convert to percent units.
    """
    x = _safe_float(v, None)
    if x is None:
        return None
    if abs(x) <= 1.5:
        return x * 100.0
    return x


# -----------------------------------------------------
# Sector map
# -----------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def _load_sector_map():
    raw = safe_read_csv(SECTOR_MAP_FILE)

    if raw.empty:
        return {}

    tcol = _find_col(raw, ["Ticker", "Yahoo Finance Code", "Symbol"])
    scol = _find_col(raw, ["Sector"])

    if not tcol or not scol:
        return {}

    out = {}
    for _, row in raw.iterrows():
        t = _bare_ticker(row[tcol])
        if not t:
            continue
        out[t] = str(row[scol]).strip()

    return out


# -----------------------------------------------------
# Result watch
# -----------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def _load_result_watch():
    raw = safe_read_csv(RESULT_CALENDAR_FILE)

    if raw.empty:
        return set()

    tcol = _find_col(raw, ["Ticker", "Symbol", "Stock"])
    if not tcol:
        return set()

    dcol = _find_col(raw, ["Date", "Result Date", "Announcement Date", "ResultDate"])

    tickers = raw[tcol].astype(str).map(_bare_ticker)

    if not dcol:
        return set(tickers[tickers.notna()].tolist())

    try:
        dt = pd.to_datetime(raw[dcol], errors="coerce", dayfirst=True)
        today = pd.Timestamp.today().normalize()
        diff = (dt.dt.normalize() - today).abs().dt.days
        mask = diff <= 7
        return set(tickers[mask & tickers.notna()].tolist())
    except Exception:
        return set()


# -----------------------------------------------------
# Latest result proxy
# -----------------------------------------------------

@st.cache_data(ttl=21600, show_spinner=False)
def _latest_result_profile(ticker: str):
    """
    Latest-result proxy using yfinance snapshot fields.
    If the data is missing, the score stays neutral.
    """
    t = _bare_ticker(ticker)
    try:
        info = yf.Ticker(_yf_symbol(t)).info or {}
    except Exception:
        info = {}

    q_growth = _pct_to_number(info.get("earningsQuarterlyGrowth"))
    r_growth = _pct_to_number(info.get("revenueGrowth"))
    e_growth = _pct_to_number(info.get("earningsGrowth"))

    score = 0.0
    notes = []

    if q_growth is not None:
        if q_growth >= 25:
            score += 2.0
            notes.append(f"Quarterly result strong ({q_growth:.0f}%)")
        elif q_growth > 0:
            score += 1.0
            notes.append(f"Quarterly result positive ({q_growth:.0f}%)")
        else:
            score -= 1.5
            notes.append(f"Quarterly result weak ({q_growth:.0f}%)")

    if r_growth is not None:
        if r_growth >= 20:
            score += 1.5
            notes.append(f"Revenue +{r_growth:.0f}%")
        elif r_growth > 0:
            score += 0.75
            notes.append(f"Revenue +{r_growth:.0f}%")
        else:
            score -= 1.0
            notes.append(f"Revenue {r_growth:.0f}%")

    if e_growth is not None:
        if e_growth >= 20:
            score += 1.5
            notes.append(f"Earnings +{e_growth:.0f}%")
        elif e_growth > 0:
            score += 0.75
            notes.append(f"Earnings +{e_growth:.0f}%")
        else:
            score -= 1.0
            notes.append(f"Earnings {e_growth:.0f}%")

    if not notes:
        notes.append("Latest result data unavailable")

    return {
        "score": round(score, 2),
        "notes": notes[:4],
        "q_growth": q_growth,
        "r_growth": r_growth,
        "e_growth": e_growth,
    }


# -----------------------------------------------------
# Fundamentals snapshot  (value + quality + growth)
# -----------------------------------------------------

@st.cache_data(ttl=21600, show_spinner=False)
def _portfolio_fundamentals(tickers_tuple):
    """
    Parallel-fetch fundamentals for the portfolio and derive sector-relative
    valuation medians (PE / PB / EV-EBITDA) from the holdings themselves.
    Sector medians are only computed where a sector has >= 3 valued names, so
    relative comparisons are meaningful. Returns (fund_map, sector_medians).
    """
    from concurrent.futures import ThreadPoolExecutor

    tickers = list(tickers_tuple)
    sector_map = _load_sector_map()

    fund_map = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        for tk, snap in zip(tickers, ex.map(_fundamentals_raw, tickers)):
            fund_map[_bare_ticker(tk)] = snap

    buckets = {}
    for tk, snap in fund_map.items():
        sec = sector_map.get(tk, "Other")
        b = buckets.setdefault(sec, {"pe": [], "pb": [], "ev_ebitda": []})
        for k in ("pe", "pb", "ev_ebitda"):
            v = snap.get(k)
            if v is not None and v > 0:
                b[k].append(v)

    sector_medians = {}
    for sec, b in buckets.items():
        med = {}
        for k in ("pe", "pb", "ev_ebitda"):
            med[k] = float(np.median(b[k])) if len(b[k]) >= 3 else None
        if any(med.values()):
            sector_medians[sec] = med

    return fund_map, sector_medians


def _fundamentals_raw(ticker):
    """Single yfinance fundamentals pull -> normalised raw fields (no cache;
    batched + cached by _portfolio_fundamentals to stay thread-safe)."""
    t = _bare_ticker(ticker)
    try:
        info = yf.Ticker(_yf_symbol(t)).info or {}
    except Exception:
        info = {}
    return {
        "pe":            _safe_float(info.get("trailingPE"), None),
        "forward_pe":    _safe_float(info.get("forwardPE"), None),
        "pb":            _safe_float(info.get("priceToBook"), None),
        "ps":            _safe_float(info.get("priceToSalesTrailing12Months"), None),
        "ev_ebitda":     _safe_float(info.get("enterpriseToEbitda"), None),
        "peg":           _safe_float(info.get("pegRatio"), None),
        "div":           _pct_to_number(info.get("dividendYield")),
        "roe":           _pct_to_number(info.get("returnOnEquity")),
        "roa":           _pct_to_number(info.get("returnOnAssets")),
        "pm":            _pct_to_number(info.get("profitMargins")),
        "om":            _pct_to_number(info.get("operatingMargins")),
        "gm":            _pct_to_number(info.get("grossMargins")),
        "de":            _safe_float(info.get("debtToEquity"), None),
        "current_ratio": _safe_float(info.get("currentRatio"), None),
        "fcf":           _safe_float(info.get("freeCashflow"), None),
        "qg":            _pct_to_number(info.get("earningsQuarterlyGrowth")),
        "rg":            _pct_to_number(info.get("revenueGrowth")),
        "eg":            _pct_to_number(info.get("earningsGrowth")),
        "market_cap":    _safe_float(info.get("marketCap"), None),
    }


def _score_fundamentals(raw, sec_med=None):
    """
    Pure scoring (no network). Raw fundamentals -> three sub-scores in [0,100].
      value_score   - sector-relative PE/PB/EV-EBITDA, PEG, dividend
      quality_score - ROE/ROA/margins/debt/liquidity/FCF
      growth_score  - EPS-Q growth, revenue growth, earnings growth, acceleration
    """
    if not raw:
        return {"value_score": 50.0, "quality_score": 50.0,
                "growth_score": 50.0, "notes": [], "available": False}

    notes = []
    available = False

    pe  = raw.get("pe");  pb = raw.get("pb");  eve = raw.get("ev_ebitda")
    peg = raw.get("peg"); div = raw.get("div")
    roe = raw.get("roe"); roa = raw.get("roa")
    pm  = raw.get("pm");  om = raw.get("om");  gm = raw.get("gm")
    de  = raw.get("de");  cr = raw.get("current_ratio"); fcf = raw.get("fcf")
    qg  = raw.get("qg");  rg = raw.get("rg");  eg = raw.get("eg")

    sec_pe  = sec_med.get("pe")        if sec_med else None
    sec_pb  = sec_med.get("pb")        if sec_med else None
    sec_eve = sec_med.get("ev_ebitda") if sec_med else None

    # ---- VALUE (sector-relative, with gentle absolute fallback) ----
    value_score = 50.0

    def _rel(val, sec_val, label, abs_cheap, abs_rich):
        nonlocal value_score, available
        if val is None or val <= 0:
            return
        available = True
        if sec_val and sec_val > 0:
            rel = val / sec_val
            if rel < 0.70:
                value_score += 13; notes.append(f"{label} 30%+ below sector")
            elif rel < 0.85:
                value_score += 7;  notes.append(f"{label} below sector")
            elif rel <= 1.15:
                value_score += 1
            elif rel <= 1.40:
                value_score -= 4
            elif rel <= 1.80:
                value_score -= 8;  notes.append(f"{label} rich vs sector")
            else:
                value_score -= 12; notes.append(f"{label} expensive vs sector")
        else:
            if val < abs_cheap:
                value_score += 5
            elif val < abs_rich:
                value_score += 1
            elif val < abs_rich * 1.6:
                value_score -= 3
            else:
                value_score -= 6

    _rel(pe,  sec_pe,  "PE",        18, 35)
    _rel(pb,  sec_pb,  "PB",        2,  5)
    _rel(eve, sec_eve, "EV/EBITDA", 10, 18)

    # PEG — growth-adjusted value (the 100x-growth vs 10x-junk discriminator)
    if peg is not None and peg > 0:
        available = True
        if peg < 1.0:
            value_score += 9; notes.append(f"PEG {peg:.2f} (growth at value price)")
        elif peg < 1.5:
            value_score += 4
        elif peg > 3.0:
            value_score -= 5; notes.append(f"PEG {peg:.1f} stretched")

    if div is not None and div > 0:
        if div >= 3:
            value_score += 4; notes.append(f"Dividend {div:.1f}%")
        elif div >= 1.5:
            value_score += 2

    # ---- QUALITY ----
    quality_score = 50.0
    if roe is not None:
        available = True
        if roe >= 25:
            quality_score += 14; notes.append(f"ROE {roe:.0f}% (excellent)")
        elif roe >= 18:
            quality_score += 9;  notes.append(f"ROE {roe:.0f}% (strong)")
        elif roe >= 12:
            quality_score += 4
        elif 0 <= roe < 8:
            quality_score -= 6;  notes.append(f"ROE {roe:.0f}% (weak)")
        elif roe < 0:
            quality_score -= 16; notes.append(f"ROE {roe:.0f}% (negative)")
    if roa is not None:
        if roa >= 12:
            quality_score += 6
        elif roa >= 6:
            quality_score += 2
        elif 0 <= roa < 2:
            quality_score -= 3
        elif roa < 0:
            quality_score -= 6
    if pm is not None:
        if pm >= 20:
            quality_score += 6; notes.append(f"Net margin {pm:.0f}%")
        elif pm >= 12:
            quality_score += 3
        elif pm < 0:
            quality_score -= 12; notes.append(f"Loss-making ({pm:.0f}%)")
    if om is not None:
        if om >= 22:
            quality_score += 4
        elif 0 <= om < 5:
            quality_score -= 2
        elif om < 0:
            quality_score -= 6
    if gm is not None and gm >= 40:
        quality_score += 3; notes.append("High gross margin")
    if de is not None:
        de_n = de if abs(de) < 10 else de / 100.0
        if de_n < 0.3:
            quality_score += 8; notes.append("Low debt")
        elif de_n < 0.6:
            quality_score += 3
        elif de_n > 2.5:
            quality_score -= 14; notes.append("Very high debt")
        elif de_n > 1.5:
            quality_score -= 8;  notes.append("Elevated debt")
    if cr is not None:
        if cr >= 1.5:
            quality_score += 3
        elif cr < 1.0:
            quality_score -= 4
    if fcf is not None:
        if fcf > 0:
            quality_score += 5; notes.append("Positive FCF")
        else:
            quality_score -= 6

    # ---- GROWTH (heavily weighted toward accumulation triggers) ----
    growth_score = 50.0
    if qg is not None:
        available = True
        if qg >= 30:
            growth_score += 16; notes.append(f"EPS-Q +{qg:.0f}% (surging)")
        elif qg >= 15:
            growth_score += 10; notes.append(f"EPS-Q +{qg:.0f}%")
        elif qg >= 5:
            growth_score += 5
        elif qg >= 0:
            growth_score += 1
        elif qg >= -10:
            growth_score -= 6
        else:
            growth_score -= 16; notes.append(f"EPS-Q {qg:.0f}% (falling)")
    if rg is not None:
        if rg >= 20:
            growth_score += 10; notes.append(f"Revenue +{rg:.0f}%")
        elif rg >= 10:
            growth_score += 5
        elif rg >= 3:
            growth_score += 2
        elif rg < 0:
            growth_score -= 8
    if eg is not None:
        if eg >= 25:
            growth_score += 9
        elif eg >= 12:
            growth_score += 4
        elif eg < 0:
            growth_score -= 8
    if qg is not None and eg is not None and qg > eg + 5:
        growth_score += 6; notes.append("Earnings accelerating")

    value_score   = max(0.0, min(100.0, value_score))
    quality_score = max(0.0, min(100.0, quality_score))
    growth_score  = max(0.0, min(100.0, growth_score))

    return {
        "value_score":   round(value_score, 1),
        "quality_score": round(quality_score, 1),
        "growth_score":  round(growth_score, 1),
        "notes": notes[:10],
        "available": available,
    }


# -----------------------------------------------------
# Ticker frame helper
# -----------------------------------------------------

def _extract_ticker_frame(raw, symbol):
    if raw is None or getattr(raw, "empty", True):
        return None

    try:
        if isinstance(raw.columns, pd.MultiIndex):
            if symbol in raw.columns.get_level_values(1):
                return raw.xs(symbol, axis=1, level=1).dropna(how="all")
        else:
            return raw.copy()
    except Exception:
        return None

    return None


# -----------------------------------------------------
# Context builder
# -----------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def _build_action_context():
    sector_map = _load_sector_map()
    if not sector_map:
        return {}, {}, {}

    tickers = list(sector_map.keys())
    yf_symbols = [_yf_symbol(t) for t in tickers]

    try:
        raw = yf.download(
            yf_symbols,
            period="9mo",
            auto_adjust=True,
            progress=False,
            group_by="ticker",
            threads=True,
        )
    except Exception:
        return {}, {}, sector_map

    tech_map = {}
    sector_returns = {}

    for bare, yf_t in zip(tickers, yf_symbols):
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                if yf_t not in raw.columns.get_level_values(0):
                    continue
                df = raw[yf_t].copy()
            else:
                df = raw.copy()

            if df.empty or "Close" not in df:
                continue

            close = pd.to_numeric(df["Close"], errors="coerce").dropna()
            if len(close) < 80:
                continue

            last = float(close.iloc[-1])

            sma20 = close.rolling(20).mean()
            sma50 = close.rolling(50).mean()
            sma200 = close.rolling(200).mean()

            ret20 = ((last / float(close.iloc[-21])) - 1) * 100
            ret60 = ((last / float(close.iloc[-63])) - 1) * 100

            high_3m = float(close.tail(63).max())
            low_3m = float(close.tail(63).min())

            pos_range = 0.5
            if high_3m > low_3m:
                pos_range = (last - low_3m) / (high_3m - low_3m)

            vol_ratio = 1.0
            if "Volume" in df:
                vol = pd.to_numeric(df["Volume"], errors="coerce").dropna()
                if len(vol) >= 20:
                    avg20 = float(vol.tail(20).mean())
                    if avg20 > 0:
                        vol_ratio = float(vol.iloc[-1]) / avg20

            above20 = pd.notna(sma20.iloc[-1]) and last > float(sma20.iloc[-1])
            above50 = pd.notna(sma50.iloc[-1]) and last > float(sma50.iloc[-1])
            above200 = len(sma200.dropna()) > 0 and last > float(sma200.iloc[-1])

            slope50 = 0.0
            if len(sma50.dropna()) >= 10:
                slope50 = ((sma50.iloc[-1] - sma50.iloc[-10]) / sma50.iloc[-10]) * 100

            accumulation = (
                pos_range >= 0.70
                and vol_ratio >= 1.15
                and above20
            )

            distribution = (
                pos_range <= 0.30
                and vol_ratio >= 1.15
                and not above20
            )

            tech_map[bare] = {
                "ret20": ret20,
                "ret60": ret60,
                "above20": above20,
                "above50": above50,
                "above200": above200,
                "slope50": slope50,
                "pos_range": pos_range,
                "vol_ratio": vol_ratio,
                "accumulation": accumulation,
                "distribution": distribution,
            }

            sec = sector_map.get(bare, "Other")
            sector_returns.setdefault(sec, []).append(ret20)

        except Exception:
            continue

    market_vals = []
    for vals in sector_returns.values():
        market_vals.extend(vals)

    market_median = float(pd.Series(market_vals).median()) if market_vals else 0.0

    sector_strength = {}
    for sec, vals in sector_returns.items():
        if len(vals) < 3:
            continue

        vals_s = pd.Series(vals, dtype="float64")
        median_ret = float(vals_s.median())
        breadth_pos = float((vals_s > 0).mean())
        breadth_strong = float((vals_s > 5).mean())

        score = (
            (median_ret - market_median)
            + ((breadth_pos - 0.5) * 10)
            + (breadth_strong * 5)
        )

        sector_strength[sec] = round(score, 2)

    return sector_strength, tech_map, sector_map


# -----------------------------------------------------
# Context builder
# -----------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def _build_action_context():

    sector_map = _load_sector_map()

    tickers = list(
        sector_map.keys()
    )

    if not tickers:
        return {}, {}, {}

    yf_symbols = [
        _yf_symbol(t)
        for t in tickers
    ]

    try:

        raw = yf.download(
            yf_symbols,
            period="9mo",
            auto_adjust=True,
            progress=False,
            group_by="ticker",
            threads=True,
        )

    except Exception:

        return {}, {}, sector_map

    tech_map = {}
    sector_returns = {}

    for bare, yf_t in zip(
        tickers,
        yf_symbols
    ):

        try:

            if isinstance(
                raw.columns,
                pd.MultiIndex
            ):

                if yf_t not in raw.columns.get_level_values(0):
                    continue

                df = raw[yf_t].copy()

            else:

                df = raw.copy()

            if df.empty:
                continue

            if "Close" not in df:
                continue

            close = pd.to_numeric(
                df["Close"],
                errors="coerce"
            ).dropna()

            if len(close) < 80:
                continue

            last = float(
                close.iloc[-1]
            )

            sma20 = close.rolling(20).mean()
            sma50 = close.rolling(50).mean()
            sma200 = close.rolling(200).mean()

            ret20 = (
                (
                    last /
                    float(close.iloc[-21])
                ) - 1
            ) * 100

            ret60 = (
                (
                    last /
                    float(close.iloc[-63])
                ) - 1
            ) * 100

            high_3m = float(
                close.tail(63).max()
            )

            low_3m = float(
                close.tail(63).min()
            )

            pos_range = 0.5

            if high_3m > low_3m:

                pos_range = (
                    (last - low_3m)
                    /
                    (high_3m - low_3m)
                )

            vol_ratio = 1.0

            if "Volume" in df:

                vol = pd.to_numeric(
                    df["Volume"],
                    errors="coerce"
                ).dropna()

                if len(vol) >= 20:

                    avg20 = float(
                        vol.tail(20).mean()
                    )

                    if avg20 > 0:

                        vol_ratio = (
                            float(vol.iloc[-1])
                            / avg20
                        )

            above20 = (
                pd.notna(sma20.iloc[-1])
                and
                last > float(sma20.iloc[-1])
            )

            above50 = (
                pd.notna(sma50.iloc[-1])
                and
                last > float(sma50.iloc[-1])
            )

            above200 = (
                len(sma200.dropna()) > 0
                and
                last > float(sma200.iloc[-1])
            )

            slope50 = 0.0

            if len(sma50.dropna()) >= 10:

                slope50 = (
                    (
                        sma50.iloc[-1]
                        -
                        sma50.iloc[-10]
                    )
                    /
                    sma50.iloc[-10]
                ) * 100

            accumulation = (
                pos_range >= 0.70
                and
                vol_ratio >= 1.15
                and
                above20
            )

            distribution = (
                pos_range <= 0.30
                and vol_ratio >= 1.15
                and not above20
            )

            # --- powerful trend signals: golden/death cross + MACD ---
            golden_align = (
                pd.notna(sma50.iloc[-1]) and pd.notna(sma200.iloc[-1])
                and float(sma50.iloc[-1]) > float(sma200.iloc[-1])
            )

            golden_cross = False
            death_cross = False
            if len(sma50.dropna()) > 60 and len(sma200.dropna()) > 60:
                try:
                    now_above  = float(sma50.iloc[-1])  > float(sma200.iloc[-1])
                    prev_above = float(sma50.iloc[-60]) > float(sma200.iloc[-60])
                    if now_above and not prev_above:
                        golden_cross = True
                    elif (not now_above) and prev_above:
                        death_cross = True
                except (IndexError, ValueError):
                    pass

            macd_bull = False
            macd_bear = False
            if len(close) >= 35:
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                macd_line   = ema12 - ema26
                signal_line = macd_line.ewm(span=9, adjust=False).mean()
                hist = macd_line - signal_line
                if len(hist) >= 6:
                    if hist.iloc[-1] > 0 and hist.iloc[-6] <= 0:
                        macd_bull = True
                    elif hist.iloc[-1] < 0 and hist.iloc[-6] >= 0:
                        macd_bear = True

            tech_map[bare] = {
                "ret20": ret20,
                "ret60": ret60,
                "above20": above20,
                "above50": above50,
                "above200": above200,
                "slope50": slope50,
                "pos_range": pos_range,
                "vol_ratio": vol_ratio,
                "accumulation": accumulation,
                "distribution": distribution,
                "golden_align": golden_align,
                "golden_cross": golden_cross,
                "death_cross": death_cross,
                "macd_bull": macd_bull,
                "macd_bear": macd_bear,
            }

            sec = sector_map.get(
                bare,
                "Other"
            )

            sector_returns.setdefault(
                sec,
                []
            ).append(ret20)

        except Exception:
            continue

    market_vals = []

    for vals in sector_returns.values():
        market_vals.extend(vals)

    market_median = (
        float(np.median(market_vals))
        if market_vals else 0.0
    )

    sector_strength = {}

    for sec, vals in sector_returns.items():

        if len(vals) < 3:
            continue

        vals_arr = np.array(vals)

        median_ret = float(
            np.median(vals_arr)
        )

        breadth_pos = float(
            (vals_arr > 0).mean()
        )

        breadth_strong = float(
            (vals_arr > 5).mean()
        )

        score = (
            (median_ret - market_median)
            +
            ((breadth_pos - 0.5) * 10)
            +
            (breadth_strong * 5)
        )

        sector_strength[sec] = round(
            score,
            2
        )

    return (
        sector_strength,
        tech_map,
        sector_map
    )

# -----------------------------------------------------
# Portfolio advisor
# -----------------------------------------------------

def _assess_action(row, tech, sector_bias, result_risk=False, fund_raw=None, sec_med=None):
    """
    Quality + Value holder's action engine (absolute, NOT percentile-ranked).

    Blend (when fundamentals available):
        30% Quality   - ROE / ROA / margins / debt / FCF
        28% Growth    - EPS-Q, revenue, earnings growth, acceleration
        17% Value     - sector-relative PE / PB / EV-EBITDA, PEG, dividend
        18% Technical - golden cross, MACD, trend, RS
         7% Sector    - tailwind / headwind

    Valuation is judged RELATIVE TO SECTOR, so a high-growth 80x name is not
    auto-penalised and a no-growth 10x name is not auto-rewarded. Growth and
    PEG drive accumulation; golden cross / MACD provide the technical edge.
    """
    pnl   = _safe_float(row.get("Return %", 0))
    notes = []

    # ---- fundamentals (raw pre-fetched; scored sector-relative) ----
    fs = _score_fundamentals(fund_raw, sec_med)
    quality_score  = fs["quality_score"]
    value_score    = fs["value_score"]
    growth_score   = fs["growth_score"]
    fund_available = fs["available"]
    notes.extend(fs["notes"][:5])

    # ---- technical ----
    tech_score = 50.0
    if tech:
        if tech.get("golden_cross"):
            tech_score += 18; notes.append("Golden cross (50/200)")
        elif tech.get("death_cross"):
            tech_score -= 18; notes.append("Death cross (50/200)")
        elif tech.get("golden_align"):
            tech_score += 8

        if tech.get("above200"):
            tech_score += 5
        else:
            tech_score -= 6; notes.append("Below 200DMA")
        if tech.get("above50"):
            tech_score += 3

        slope50 = _safe_float(tech.get("slope50", 0))
        if slope50 > 3:
            tech_score += 5
        elif slope50 < -4:
            tech_score -= 8; notes.append("50DMA falling")

        if tech.get("macd_bull"):
            tech_score += 6; notes.append("MACD bullish")
        elif tech.get("macd_bear"):
            tech_score -= 5

        ret60 = _safe_float(tech.get("ret60", 0))
        if ret60 >= 20:
            tech_score += 6
        elif ret60 <= -25:
            tech_score -= 10; notes.append(f"60D {ret60:.0f}%")

        if tech.get("distribution"):
            tech_score -= 10; notes.append("Distribution")
        elif tech.get("accumulation"):
            tech_score += 5; notes.append("Accumulation")
    tech_score = max(0.0, min(100.0, tech_score))

    # ---- sector ----
    bias_c = max(-15.0, min(15.0, float(sector_bias)))
    sector_score = 50.0 + bias_c * 2.0
    if sector_bias > 8:
        notes.append("Sector leadership")
    elif sector_bias < -8:
        notes.append("Sector under pressure")

    # ---- composite ----
    if fund_available:
        composite = (
            0.30 * quality_score
            + 0.28 * growth_score
            + 0.17 * value_score
            + 0.18 * tech_score
            + 0.07 * sector_score
        )
    else:
        composite = 0.65 * tech_score + 0.35 * sector_score
        notes.append("Fundamentals unavailable")

    if result_risk:
        composite -= 2; notes.append("Result near")
    composite = max(0.0, min(100.0, composite))

    # ---- action mapping (P&L + value + quality + growth aware) ----
    broken = (
        fund_available
        and ((quality_score <= 30 and growth_score <= 35) or quality_score <= 22)
    )
    premium = (
        fund_available and quality_score >= 68 and growth_score >= 58
    )

    if broken:
        action = "EXIT"; notes.append("Fundamentals broken")

    elif premium:
        if pnl < -8:
            action = "AVERAGE DOWN"
        elif pnl < 8:
            action = "STRONG ACCUMULATE"
        elif pnl < 30:
            action = "ACCUMULATE ON DIPS"
        else:
            action = "HOLD COMPOUNDER"

    elif composite >= 66:
        if pnl < -10 and quality_score >= 55:
            action = "AVERAGE DOWN"
        elif pnl < 18:
            action = "ACCUMULATE"
        elif pnl < 45:
            action = "HOLD"
        elif value_score <= 42:
            action = "BOOK PARTIAL PROFIT"
        else:
            action = "HOLD"

    elif composite >= 52:
        if growth_score >= 62 and pnl < 12:
            action = "ACCUMULATE"               # growth-led even at mid composite
        elif pnl > 35 and value_score <= 38:
            action = "BOOK PARTIAL PROFIT"       # expensive winner
        elif pnl < -15 and quality_score >= 58:
            action = "AVERAGE DOWN"              # quality dip
        else:
            action = "HOLD"

    elif composite >= 40:
        if pnl > 30:
            action = "BOOK PROFIT"
        elif quality_score >= 55:
            action = "HOLD"
        else:
            action = "REDUCE"

    elif composite >= 28:
        action = "BOOK PROFIT" if pnl > 0 else "REDUCE"

    else:
        action = "EXIT"

    note = "; ".join(notes[:6]) if notes else "Insufficient data"
    return action, note, round(composite, 1)
# =====================================================
# TAB 7 — PORTFOLIO (Google Sheets)
# =====================================================
with tab7:
    sh1, sh2 = st.columns([6, 1])
    with sh1:
        st.subheader("Medium-Term Portfolio")
        st.caption("Live from Google Sheets · 5min cache · action engine enabled")
    with sh2:
        st.write("")
        if st.button("Sync", key="pf_refresh"):
            _load_portfolio.clear()
            _load_sector_map.clear()
            _load_result_watch.clear()
            _build_action_context.clear()
            st.rerun()

    if not PORTFOLIO_GSHEET_ID:
        st.warning("Add `PORTFOLIO_GSHEET_ID` to config.py and share the sheet as **Anyone with link → Viewer**.")
    else:
        try:
            live_raw, booked_raw = _load_portfolio()
            load_ok = True
        except Exception as e:
            st.error(f"Google Sheet not accessible. Share as **Anyone with link = Viewer**.\n\n`{e}`")
            load_ok = False

        if load_ok:
            live = live_raw.dropna(how="all").copy()

            if live.shape[1] >= 10:
                live = live.iloc[:, :11]
                live.columns = (
                    ["Date","Stock","Ticker","Qty","Buy Price","Invested","CMP","Current Value","P&L","Return %","Remark"]
                    [:live.shape[1]]
                )

            live = live[
                live["Stock"].astype(str).str.strip().ne("") &
                live["Stock"].astype(str).str.strip().ne("nan")
            ].copy()

            for col in ["Qty", "Buy Price", "Invested", "CMP", "Current Value", "P&L", "Return %"]:
                if col in live.columns:
                    live[col] = pd.to_numeric(live[col], errors="coerce")

            live = live.dropna(subset=["CMP", "Qty"]).copy()
            live["Date"] = live["Date"].apply(_parse_date)
            live["Ticker"] = live["Ticker"].astype(str).map(_bare_ticker)

            # --- intelligence context ---
            sector_strength, tech_map, sector_map = _build_action_context()
            result_watch = _load_result_watch()

            live["Sector"] = live["Ticker"].map(sector_map).fillna("Other")

            # if Return % is missing or blank, rebuild it from P&L / Invested
            if "Return %" in live.columns:
                live["Return %"] = pd.to_numeric(live["Return %"], errors="coerce")
                if live["Return %"].isna().all() and "P&L" in live.columns and "Invested" in live.columns:
                    live["Return %"] = (live["P&L"] / live["Invested"]) * 100

            # --- fundamentals batch + sector-relative valuation medians ---
            _pf_tickers = tuple(sorted(set(
                live["Ticker"].astype(str).map(_bare_ticker)
            )))
            fund_raw_map, sector_val_medians = _portfolio_fundamentals(_pf_tickers)

            # Action model — absolute scoring (NO percentile forcing)
            action_list = []
            note_list = []
            score_list = []
            sector_bias_list = []

            for _, r in live.iterrows():
                t = _bare_ticker(r["Ticker"])
                sec = str(r.get("Sector", "Other"))
                bias = float(sector_strength.get(sec, 0.0))
                tech = tech_map.get(t)
                result_risk = t in result_watch
                fund_raw = fund_raw_map.get(t, {})
                sec_med = sector_val_medians.get(sec)

                action, note, score = _assess_action(
                    r, tech, bias, result_risk, fund_raw, sec_med
                )
                action_list.append(action)
                note_list.append(note)
                score_list.append(score)
                sector_bias_list.append(bias)

            live["Suggested Action"] = action_list
            live["Action Note"] = note_list
            live["Action Score"] = score_list
            live["Sector Bias %"] = sector_bias_list

            inv = live["Invested"].sum()
            val = live["Current Value"].sum()
            pnl = live["P&L"].sum()
            ret = (pnl / inv * 100) if inv else 0
            n   = len(live)
            ws  = int((live["P&L"] > 0).sum())
            ls  = int((live["P&L"] < 0).sum())
            pa  = CLR_BULL if pnl >= 0 else CLR_BEAR
            ra  = CLR_BULL if ret >= 0 else CLR_BEAR

            st.markdown(
                '<div class="qc-ribbon" style="grid-template-columns:repeat(5,1fr);">'
                + kpi_card("INVESTED",      fmt_inr(inv, signed=False))
                + kpi_card("CURRENT VALUE", fmt_inr(val, signed=False))
                + kpi_card("OPEN P&L",      fmt_inr(pnl), color=pa)
                + kpi_card("RETURN",        fmt_pct(ret), color=ra)
                + kpi_card("HOLDINGS",      f"{n}", sub=f"▲ {ws} · ▼ {ls}")
                + '</div>',
                unsafe_allow_html=True,
            )

            # action summary
            action_order = ["ACCUMULATE", "HOLD", "TRIM", "BOOK PROFIT", "REDUCE", "EXIT"]
            action_cols = st.columns(6)
            for i, a in enumerate(action_order):
                cnt = int((live["Suggested Action"] == a).sum())
                color = ACTION_COLORS.get(a, TXT_SECOND)
                with action_cols[i]:
                    st.markdown(
                        f'<div style="background:{BG_CARD};border:1px solid {color}40;'
                        f'border-left:3px solid {color};border-radius:8px;padding:10px 14px;">'
                        f'<div style="color:{TXT_MUTED};font-size:10px;letter-spacing:1px;font-weight:700;">{a}</div>'
                        f'<div style="color:{color};font-size:18px;font-weight:700;margin-top:2px;">{cnt}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            if not live.empty:
                best  = live.loc[live["Return %"].idxmax()]
                worst = live.loc[live["Return %"].idxmin()]
                bw1, bw2 = st.columns(2)
                with bw1:
                    st.markdown(
                        f'<div style="background:#10b98112;border:1px solid #10b98130;border-radius:8px;padding:10px 16px;">'
                        f'<span style="color:{CLR_BULL};font-size:11px;font-weight:700;letter-spacing:1px;">BEST</span>'
                        f'&nbsp;&nbsp;<span style="color:{TXT_PRIMARY};font-weight:600;">{best["Stock"]}</span>'
                        f'&nbsp;<span style="color:{CLR_BULL};font-weight:700;">'
                        f'+{best["Return %"]:.2f}% · {fmt_inr(best["P&L"])}</span></div>',
                        unsafe_allow_html=True,
                    )
                with bw2:
                    st.markdown(
                        f'<div style="background:#ef444412;border:1px solid #ef444430;border-radius:8px;padding:10px 16px;">'
                        f'<span style="color:{CLR_BEAR};font-size:11px;font-weight:700;letter-spacing:1px;">WORST</span>'
                        f'&nbsp;&nbsp;<span style="color:{TXT_PRIMARY};font-weight:600;">{worst["Stock"]}</span>'
                        f'&nbsp;<span style="color:{CLR_BEAR};font-weight:700;">'
                        f'{worst["Return %"]:.2f}% · {fmt_inr(worst["P&L"])}</span></div>',
                        unsafe_allow_html=True,
                    )

            st.markdown('<div class="qc-section-title">Holdings</div>', unsafe_allow_html=True)

            sc, _ = st.columns([2, 4])
            with sc:
                sort_by = st.selectbox(
                    "Sort",
                    ["Suggested Action", "Return % ↓", "Return % ↑", "P&L ↓", "P&L ↑", "Stock A–Z"],
                    label_visibility="collapsed",
                    key="pf_sort",
                )

            sm = {
                "Suggested Action": ("Action Score", True),
                "Return % ↓":      ("Return %", False),
                "Return % ↑":      ("Return %", True),
                "P&L ↓":           ("P&L", False),
                "P&L ↑":           ("P&L", True),
                "Stock A–Z":       ("Stock", True),
            }
            scol, sasc = sm[sort_by]
            disp = live.sort_values(scol, ascending=sasc).copy()

            disp = disp[[
                "Date","Stock","Ticker","Sector","Qty","Buy Price","Invested","CMP",
                "Current Value","P&L","Return %","Sector Bias %","Suggested Action","Action Note"
            ]]

            disp.columns = [
                "Date","Stock","Ticker","Sector","Qty","Buy ₹","Invested ₹","CMP ₹",
                "Value ₹","P&L ₹","Return %","Sector Bias %","Suggested Action","Action Note"
            ]

            def _bg(row):
                try:
                    v = float(row["P&L ₹"])
                    c = "#10b98112" if v > 0 else "#ef444412" if v < 0 else ""
                except Exception:
                    c = ""
                return [f"background:{c}"] * len(row)

            def _num(val):
                try:
                    v = float(val)
                    if v > 0: return f"color:{CLR_BULL};font-weight:600"
                    if v < 0: return f"color:{CLR_BEAR};font-weight:600"
                except (TypeError, ValueError):
                    pass
                return ""

            fmt = {
                "Buy ₹": "₹{:,.2f}",
                "Invested ₹": "₹{:,.0f}",
                "CMP ₹": "₹{:,.2f}",
                "Value ₹": "₹{:,.0f}",
                "P&L ₹": "₹{:,.0f}",
                "Return %": "{:+.2f}%",
                "Sector Bias %": "{:+.2f}%",
                "Qty": "{:.0f}",
            }

            try:
                styled = (
                    disp.style
                    .apply(_bg, axis=1)
                    .map(_num, subset=["P&L ₹", "Return %", "Sector Bias %"])
                    .format(fmt, na_rep="—")
                )
            except AttributeError:
                styled = (
                    disp.style
                    .apply(_bg, axis=1)
                    .applymap(_num, subset=["P&L ₹", "Return %", "Sector Bias %"])
                    .format(fmt, na_rep="—")
                )

            st.dataframe(styled, use_container_width=True, hide_index=True)

            # ── Booked profits ──
            booked = booked_raw.dropna(how="all").copy()
            booked = booked[
                booked.iloc[:, 0].astype(str).str.strip().ne("") &
                booked.iloc[:, 0].astype(str).str.strip().ne("nan")
            ]

            if not booked.empty:
                for col in booked.columns[3:]:
                    booked[col] = pd.to_numeric(booked[col], errors="coerce")

                try:
                    bpnl_col = [c for c in booked.columns if "booked" in str(c).lower() or "p&l" in str(c).lower()][0]
                    total_b = booked[bpnl_col].sum()
                except IndexError:
                    total_b = pd.to_numeric(booked.iloc[:, 8], errors="coerce").sum()

                b_acc = CLR_BULL if total_b >= 0 else CLR_BEAR
                st.markdown('<div class="qc-section-title">Booked Profits (Google Sheets)</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div style="background:{BG_CARD};border:1px solid {b_acc}40;'
                    f'border-left:3px solid {b_acc};border-radius:8px;'
                    f'padding:10px 18px;margin-bottom:10px;display:inline-block;">'
                    f'<span style="color:{TXT_MUTED};font-size:11px;letter-spacing:1px;">TOTAL BOOKED P&L &nbsp;</span>'
                    f'<span style="color:{b_acc};font-size:18px;font-weight:700;">{fmt_inr(total_b)}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(booked, use_container_width=True, hide_index=True)

# =====================================================
# TAB 8 — AI INTELLIGENCE  (paste at END of app.py)
# Also: update the tabs line near the top to include "AI Intelligence"
# =====================================================

# --- ADD this import near the top of app.py (with other core imports) ---
# from core.ai_scanner import scan_universe, mark_existing_positions, CAPITAL_PER_PICK, EXIT_THRESHOLD
# from config import UNIVERSE_FILE, RESULT_CALENDAR_FILE



@st.cache_data(ttl=3600, show_spinner=False)
def _cached_scan():
    """Heavy scan, cached 60 minutes. Independent of open positions."""
    universe = safe_read_csv(UNIVERSE_FILE)
    result_cal = safe_read_csv(RESULT_CALENDAR_FILE)
    return scan_universe(
        universe_df=universe,
        result_calendar_df=result_cal if not result_cal.empty else None,
        progress_callback=None,
    )


with tab8:
    sh1, sh2 = st.columns([6, 1])
    with sh1:
        st.subheader("AI Intelligence · Opportunity Scanner")
        st.caption(
            "Multi-factor convergence model · Conservative mode · "
            f"₹{CAPITAL_PER_PICK:,} per pick · Auto-refresh hourly"
        )
    with sh2:
        st.write("")
        if st.button("Rescan", key="ai_rescan"):
            _cached_scan.clear()
            st.rerun()

    # ── Run scan (progress bar on first hit) ─────────────────
    progress_box = st.empty()
    if "_ai_scan_done" not in st.session_state:
        st.session_state._ai_scan_done = False

    try:
        with st.spinner("Scanning universe… cached for 60min after first run"):
            scan = _cached_scan()
    except Exception as e:
        st.error(f"Scan failed: {e}")
        scan = None

    progress_box.empty()

    if not scan or not scan.get("all_results"):
        st.warning(
            "No scan results yet. Check that `sector_map_fixed.csv` has a Ticker column "
            "and that yfinance can reach Yahoo from this machine."
        )
    else:
        # Mark existing positions and re-partition
        scan = mark_existing_positions(scan, open_trades if not open_trades.empty else None)

        strong_buys = scan["strong_buys"]
        exits       = scan["exits"]
        watchlist   = scan["watchlist"]
        all_results = scan["all_results"]
        sec_mom     = scan["sector_momentum"]
        scanned_at  = scan["scanned_at"]

        # ── KPI ribbon ──
        avg_score = float(pd.Series([r.composite_score for r in all_results]).mean()) if all_results else 0

        best_sector = "—"
        best_sector_score = 0.0
        if sec_mom:
            best_sector = max(sec_mom, key=sec_mom.get)
            best_sector_score = sec_mom[best_sector]

        st.markdown(
            '<div class="qc-ribbon" style="grid-template-columns:repeat(5,1fr);">'
            + kpi_card("STRONG BUYS",  str(len(strong_buys)),
                       color=CLR_BULL if strong_buys else TXT_MUTED,
                       sub="composite ≥75, 4+ groups")
            + kpi_card("EXIT FLAGS",   str(len(exits)),
                       color=CLR_BEAR if exits else TXT_MUTED,
                       sub="open positions weakening")
            + kpi_card("WATCHLIST",    str(len(watchlist)),
                       color=CLR_INFO,
                       sub="score 65+, not converged")
            + kpi_card("UNIVERSE",     f"{len(all_results)}",
                       sub="passed liquidity filter")
            + kpi_card("TOP SECTOR",   best_sector[:14],
                       color=CLR_BULL if best_sector_score > 0 else CLR_WARN,
                       sub=f"{best_sector_score:+.1f}% 1M")
            + '</div>',
            unsafe_allow_html=True,
        )

        # ──────────────────────────────────────────────────────
        # EXIT SIGNALS — top of page (highest priority)
        # ──────────────────────────────────────────────────────
        if exits:
            st.markdown(
                f'<div class="qc-section-title" style="color:{CLR_BEAR};">'
                f'⚠ EXIT SIGNALS — Open positions with weakening scores'
                f'</div>',
                unsafe_allow_html=True,
            )
            for r in exits:
                pnl = r.current_pnl_pct
                pnl_str = f"{pnl:+.1f}%" if pnl is not None else "—"
                pnl_color = CLR_BULL if (pnl or 0) >= 0 else CLR_BEAR
                bears_str = " · ".join(r.bear_signals[:3]) if r.bear_signals else "Multiple weak signals"

                st.markdown(
                    f'<div style="background:{CLR_BEAR}10;border:1px solid {CLR_BEAR}40;'
                    f'border-left:3px solid {CLR_BEAR};border-radius:8px;'
                    f'padding:12px 16px;margin-bottom:8px;">'

                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<div>'
                    f'<span style="color:{CLR_BEAR};font-weight:700;letter-spacing:0.5px;font-size:12px;">EXIT</span>'
                    f'&nbsp;&nbsp;<span style="color:{TXT_PRIMARY};font-weight:700;font-size:15px;">{r.ticker}</span>'
                    f'&nbsp;<span style="color:{TXT_MUTED};font-size:12px;">{r.company_name[:36]}</span>'
                    f'</div>'

                    f'<div style="display:flex;gap:18px;align-items:center;">'
                    f'<span style="color:{TXT_MUTED};font-size:11px;">Score '
                    f'<b style="color:{CLR_BEAR};">{r.composite_score:.0f}</b></span>'
                    f'<span style="color:{TXT_MUTED};font-size:11px;">Current P&L '
                    f'<b style="color:{pnl_color};">{pnl_str}</b></span>'
                    f'<span style="color:{TXT_MUTED};font-size:11px;">CMP '
                    f'<b style="color:{TXT_PRIMARY};">₹{r.current_price:,.2f}</b></span>'
                    f'</div>'

                    f'</div>'

                    f'<div style="color:{TXT_DIM};font-size:12px;margin-top:6px;">{bears_str}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ──────────────────────────────────────────────────────
        # TOP OPPORTUNITY CARDS (top 3)
        # ──────────────────────────────────────────────────────
        if strong_buys:
            st.markdown('<div class="qc-section-title">Top Opportunities</div>', unsafe_allow_html=True)

            top3 = strong_buys[:3]
            cols = st.columns(min(len(top3), 3))
            for i, r in enumerate(top3):
                with cols[i]:
                    stars = "★" * r.conviction + "☆" * (5 - r.conviction)
                    bulls_top = " · ".join(r.bull_signals[:3])
                    cat_html = (
                        f'<span style="background:{CLR_CYAN}22;color:{CLR_CYAN};border:1px solid {CLR_CYAN}44;'
                        f'border-radius:5px;padding:1px 8px;font-size:10px;font-weight:600;margin-left:6px;">'
                        f'⚡ {r.next_event_label} {r.next_event_days}d</span>'
                    ) if r.next_event_label else ""

                    st.markdown(
                        f'<div style="background:{BG_PANEL};border:1px solid {BORDER};'
                        f'border-top:3px solid {CLR_BULL};border-radius:10px;padding:16px;height:100%;">'

                        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">'
                        f'<div>'
                        f'<div style="color:{TXT_PRIMARY};font-size:18px;font-weight:700;letter-spacing:0.5px;">'
                        f'{r.ticker}</div>'
                        f'<div style="color:{TXT_MUTED};font-size:14px;margin-top:2px;">{r.company_name[:30]}</div>'
                        f'<div style="color:{TXT_DIM};font-size:12px;margin-top:1px;">{r.sector[:30]}</div>'
                        f'</div>'
                        f'<div style="color:#fbbf24;font-size:14px;letter-spacing:1px;">{stars}</div>'
                        f'</div>'

                        f'<div style="display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap;">'
                        f'<span style="background:{CLR_BULL}22;color:{CLR_BULL};border:1px solid {CLR_BULL}44;'
                        f'border-radius:5px;padding:2px 10px;font-size:10.5px;font-weight:700;letter-spacing:0.4px;">'
                        f'STRONG BUY</span>'
                        f'<span style="background:{BG_HOVER};color:{TXT_SECOND};border-radius:5px;'
                        f'padding:2px 8px;font-size:10.5px;font-weight:600;">Score {r.composite_score:.0f}</span>'
                        f'<span style="background:{BG_HOVER};color:{TXT_SECOND};border-radius:5px;'
                        f'padding:2px 8px;font-size:10.5px;">⚡ {r.groups_fired}/5</span>'
                        f'{cat_html}'
                        f'</div>'

                        # Trade plan box
                        f'<div style="background:{BG_CARD};border:1px solid {BORDER_SOFT};'
                        f'border-radius:6px;padding:10px 12px;margin-bottom:10px;">'
                        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;font-size:11.5px;">'
                        f'<div><span style="color:{TXT_MUTED};">Entry</span> '
                        f'<b style="color:{TXT_PRIMARY};">₹{r.suggested_entry:,.2f}</b></div>'
                        f'<div><span style="color:{TXT_MUTED};">Qty</span> '
                        f'<b style="color:{TXT_PRIMARY};">{r.suggested_qty}</b></div>'
                        f'<div><span style="color:{TXT_MUTED};">SL</span> '
                        f'<b style="color:{CLR_BEAR};">₹{r.suggested_stop:,.2f}</b></div>'
                        f'<div><span style="color:{TXT_MUTED};">Target</span> '
                        f'<b style="color:{CLR_BULL};">₹{r.suggested_target:,.2f}</b></div>'
                        f'<div><span style="color:{TXT_MUTED};">R:R</span> '
                        f'<b style="color:{TXT_PRIMARY};">{r.rr_ratio:.1f}</b></div>'
                        f'<div><span style="color:{TXT_MUTED};">Risk</span> '
                        f'<b style="color:{CLR_WARN};">₹{r.max_risk_inr:,.0f}</b></div>'
                        f'</div>'
                        f'</div>'

                        f'<div style="color:{TXT_MUTED};font-size:11px;line-height:1.5;'
                        f'border-top:1px solid {BORDER_SOFT};padding-top:8px;">{bulls_top}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # ── Full Strong Buys table ──
            if len(strong_buys) > 3:
                st.markdown(
                    '<div class="qc-section-title" style="margin-top:18px;">All Strong Buys</div>',
                    unsafe_allow_html=True,
                )

            rows = []
            for r in strong_buys:
                stars = "★" * r.conviction
                cat = f"{r.next_event_label} {r.next_event_days}d" if r.next_event_label else "—"
                rows.append({
                    "Ticker":    r.ticker,
                    "Company":   r.company_name[:28],
                    "Sector":    (r.sector or "—")[:18],
                    "★":         stars,
                    "Score":     r.composite_score,
                    "Groups":    r.groups_fired,
                    "Entry ₹":   r.suggested_entry,
                    "SL ₹":      r.suggested_stop,
                    "Target ₹":  r.suggested_target,
                    "R:R":       r.rr_ratio,
                    "Qty":       r.suggested_qty,
                    "Risk ₹":    r.max_risk_inr,
                    "Return %":  r.expected_return_pct,
                    "1M %":      r.ret_1m if r.ret_1m is not None else 0,
                    "RSI":       r.rsi if r.rsi else 0,
                    "vs Nifty":  r.rs_vs_nifty_60d if r.rs_vs_nifty_60d is not None else 0,
                    "Catalyst":  cat,
                })

            if rows:
                df_sb = pd.DataFrame(rows)

                def _score_color(v):
                    try:
                        x = float(v)
                        if x >= 80: return f"color:{CLR_BULL};font-weight:700"
                        if x >= 70: return f"color:{CLR_BULL};font-weight:600"
                    except (TypeError, ValueError):
                        pass
                    return ""

                def _pct_color(v):
                    try:
                        x = float(v)
                        if x > 0: return f"color:{CLR_BULL};font-weight:600"
                        if x < 0: return f"color:{CLR_BEAR};font-weight:600"
                    except (TypeError, ValueError):
                        pass
                    return ""

                fmt = {
                    "Score":    "{:.1f}",
                    "Groups":   "{:.0f}/5",
                    "Entry ₹":  "₹{:,.2f}",
                    "SL ₹":     "₹{:,.2f}",
                    "Target ₹": "₹{:,.2f}",
                    "R:R":      "{:.2f}",
                    "Qty":      "{:.0f}",
                    "Risk ₹":   "₹{:,.0f}",
                    "Return %": "+{:.2f}%",
                    "1M %":     "{:+.1f}%",
                    "RSI":      "{:.0f}",
                    "vs Nifty": "{:+.1f}%",
                }

                try:
                    styled = (
                        df_sb.style
                        .map(_score_color, subset=["Score"])
                        .map(_pct_color,   subset=["1M %", "vs Nifty"])
                        .format(fmt, na_rep="—")
                    )
                except AttributeError:
                    styled = (
                        df_sb.style
                        .applymap(_score_color, subset=["Score"])
                        .applymap(_pct_color,   subset=["1M %", "vs Nifty"])
                        .format(fmt, na_rep="—")
                    )

                st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.info(
                "🛡 No STRONG BUY opportunities meeting conservative criteria right now.\n\n"
                "The model requires **composite ≥ 75 AND at least 4 of 5 factor groups** firing "
                "positively (trend, momentum, setup, sector, catalyst). This is by design — "
                "Conservative mode protects against false signals in choppy markets. "
                "Check the **Watchlist** section below for high-scoring picks that haven't fully "
                "converged yet."
            )

        # ──────────────────────────────────────────────────────
        # WATCHLIST (high-score but not fully converged)
        # ──────────────────────────────────────────────────────
        if watchlist:
            st.markdown(
                '<div class="qc-section-title" style="margin-top:20px;">'
                'Watchlist — High score, awaiting convergence</div>',
                unsafe_allow_html=True,
            )

            w_rows = []
            for r in watchlist[:15]:
                w_rows.append({
                    "Ticker":   r.ticker,
                    "Company":  r.company_name[:30],
                    "Sector":   (r.sector or "—")[:18],
                    "Score":    r.composite_score,
                    "Groups":   r.groups_fired,
                    "Action":   r.action,
                    "CMP ₹":    r.current_price,
                    "RSI":      r.rsi if r.rsi else 0,
                    "1M %":     r.ret_1m if r.ret_1m is not None else 0,
                    "vs Nifty": r.rs_vs_nifty_60d if r.rs_vs_nifty_60d is not None else 0,
                    "Key Signal": " · ".join(r.bull_signals[:2]) if r.bull_signals else "—",
                })

            if w_rows:
                df_w = pd.DataFrame(w_rows)

                def _pct_color_w(v):
                    try:
                        x = float(v)
                        if x > 0: return f"color:{CLR_BULL};font-weight:600"
                        if x < 0: return f"color:{CLR_BEAR};font-weight:600"
                    except (TypeError, ValueError):
                        pass
                    return ""

                fmt = {
                    "Score":  "{:.1f}",
                    "Groups": "{:.0f}/5",
                    "CMP ₹":  "₹{:,.2f}",
                    "RSI":    "{:.0f}",
                    "1M %":   "{:+.1f}%",
                    "vs Nifty": "{:+.1f}%",
                }

                try:
                    styled = df_w.style.map(_pct_color_w, subset=["1M %", "vs Nifty"]).format(fmt, na_rep="—")
                except AttributeError:
                    styled = df_w.style.applymap(_pct_color_w, subset=["1M %", "vs Nifty"]).format(fmt, na_rep="—")

                st.dataframe(styled, use_container_width=True, hide_index=True)

        # ──────────────────────────────────────────────────────
        # SECTOR HEATMAP
        # ──────────────────────────────────────────────────────
        if all_results:
            st.markdown('<div class="qc-section-title" style="margin-top:20px;">Sector Strength</div>',
                        unsafe_allow_html=True)

            sec_data: dict = {}
            for r in all_results:
                sec = r.sector or "Unknown"
                sec_data.setdefault(sec, []).append(r.composite_score)

            sec_rows = []
            for sec, scores in sec_data.items():
                if len(scores) < 2:
                    continue
                sec_rows.append({
                    "Sector":           sec[:32],
                    "Stocks":           len(scores),
                    "1M Momentum %":    sec_mom.get(sec, 0.0),
                    "Avg Score":        float(pd.Series(scores).mean()),
                    "Top Stock Score":  max(scores),
                })

            if sec_rows:
                df_sec = pd.DataFrame(sec_rows).sort_values("Avg Score", ascending=False)

                def _sec_color(v):
                    try:
                        x = float(v)
                        if x >= 65: return f"background:{CLR_BULL}30;color:{CLR_BULL};font-weight:700"
                        if x >= 55: return f"background:{CLR_BULL}15;color:{CLR_BULL}"
                        if x >= 45: return f"background:transparent;color:{TXT_SECOND}"
                        if x >= 35: return f"background:{CLR_WARN}15;color:{CLR_WARN}"
                        return f"background:{CLR_BEAR}20;color:{CLR_BEAR};font-weight:700"
                    except (TypeError, ValueError):
                        return ""

                def _mom_color(v):
                    try:
                        x = float(v)
                        if x > 3:  return f"color:{CLR_BULL};font-weight:600"
                        if x < -3: return f"color:{CLR_BEAR};font-weight:600"
                    except (TypeError, ValueError):
                        pass
                    return ""

                fmt = {
                    "1M Momentum %":   "{:+.2f}%",
                    "Avg Score":       "{:.1f}",
                    "Top Stock Score": "{:.1f}",
                    "Stocks":          "{:.0f}",
                }

                try:
                    styled = (
                        df_sec.style
                        .map(_sec_color, subset=["Avg Score", "Top Stock Score"])
                        .map(_mom_color, subset=["1M Momentum %"])
                        .format(fmt, na_rep="—")
                    )
                except AttributeError:
                    styled = (
                        df_sec.style
                        .applymap(_sec_color, subset=["Avg Score", "Top Stock Score"])
                        .applymap(_mom_color, subset=["1M Momentum %"])
                        .format(fmt, na_rep="—")
                    )

                st.dataframe(styled, use_container_width=True, hide_index=True)

        # ── Footer ──
        st.caption(
            f"Last scan: {scanned_at.strftime('%d-%b %H:%M:%S')} · "
            f"Refreshes hourly · Capital per pick: ₹{CAPITAL_PER_PICK:,} · "
            f"Conservative mode (composite ≥ 75, 4+ converging signals) · "
            f"Research aid only, not financial advice"
        )
# =====================================================
# =====================================================
# TAB 9 — TRADE BOOK
# =====================================================
with tab9:

    st.subheader("Trade Book")
    st.caption("Manage live trades directly from dashboard")

    trade_file = Path(TRADES_LOG_FILE)

    def _as_date(v):
        try:
            dt = pd.to_datetime(v, errors="coerce", dayfirst=True)
            if pd.notna(dt):
                return dt.date()
        except Exception:
            pass
        return pd.Timestamp.today().date()

    def _as_float(v, default=0.0):
        try:
            if pd.isna(v):
                return default
            return float(v)
        except Exception:
            return default

    # -------------------------------------------------
    # LOAD TRADE BOOK
    # -------------------------------------------------
    try:
        if trade_file.exists():
            tb = pd.read_csv(trade_file)
        else:
            tb = pd.DataFrame()
    except Exception:
        tb = pd.DataFrame()

    if not tb.empty:
        tb.columns = [str(c).strip() for c in tb.columns]

    # -------------------------------------------------
    # ADD TRADE
    # -------------------------------------------------
    st.markdown("### Add New Trade")

    with st.form("add_trade_form"):

        c1, c2, c3 = st.columns(3)

        with c1:
            trade_date = st.date_input(
                "Trade Date",
                value=pd.Timestamp.today().date()
            )
            engine_name = st.text_input(
                "Engine",
                value="MANUAL"
            )
            side = st.selectbox(
                "Action",
                ["BUY", "SELL"],
                index=0
            )

        with c2:
            ticker = st.text_input(
                "Ticker",
                placeholder="RELIANCE.NS"
            )
            qty = st.number_input(
                "Quantity",
                min_value=1.0,
                step=1.0,
                value=1.0
            )
            entry_price = st.number_input(
                "Entry Price",
                min_value=0.0,
                step=0.05,
                value=0.0
            )

        with c3:
            stop_loss = st.number_input(
                "Stop Loss",
                min_value=0.0,
                step=0.05,
                value=0.0
            )
            target = st.number_input(
                "Target",
                min_value=0.0,
                step=0.05,
                value=0.0
            )
            notes = st.text_input(
                "Notes"
            )

        add_submit = st.form_submit_button("Add Trade")

    if add_submit:
        if not ticker.strip():
            st.error("Ticker required")
        elif entry_price <= 0:
            st.error("Entry price required")
        elif qty <= 0:
            st.error("Quantity required")
        else:
            new_trade = pd.DataFrame([{
                "Date": pd.Timestamp(trade_date).strftime("%d-%m-%Y"),
                "Engine": str(engine_name).strip(),
                "Ticker": ticker.upper().strip(),
                "Action": side,
                "EntryPrice": float(entry_price),
                "Qty": float(qty),
                "StopLoss": float(stop_loss),
                "Target": float(target),
                "CMP": float(entry_price),
                "PnL": 0.0,
                "Status": "OPEN",
                "ExitPrice": np.nan,
                "ExitDate": np.nan,
                "Notes": notes.strip(),
            }])

            try:
                if tb.empty:
                    updated = new_trade.copy()
                else:
                    updated = pd.concat([tb, new_trade], ignore_index=True)

                updated.to_csv(trade_file, index=False)
                st.success(f"Trade added: {ticker.upper().strip()}")
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")

    st.divider()

    # -------------------------------------------------
    # EDIT TRADE
    # -------------------------------------------------
    st.markdown("### Edit Existing Trade")

    if tb.empty:
        st.info("Trade book empty")
    else:
        edit_options = [
            f"{i} | {str(r.get('Ticker', '')).strip()} | {str(r.get('Status', '')).strip()}"
            for i, r in tb.iterrows()
        ]

        selected_edit = st.selectbox(
            "Select Trade to Edit",
            edit_options,
            key="edit_trade_selector"
        )

        edit_row = int(selected_edit.split("|")[0].strip())
        edit_src = tb.loc[edit_row].copy()

        with st.form("edit_trade_form"):

            e1, e2, e3 = st.columns(3)

            with e1:
                edit_trade_date = st.date_input(
                    "Trade Date",
                    value=_as_date(edit_src.get("Date"))
                )
                edit_engine = st.text_input(
                    "Engine",
                    value=str(edit_src.get("Engine", ""))
                )
                edit_action = st.selectbox(
                    "Action",
                    ["BUY", "SELL"],
                    index=0 if str(edit_src.get("Action", "BUY")).upper() == "BUY" else 1
                )

            with e2:
                edit_ticker = st.text_input(
                    "Ticker",
                    value=str(edit_src.get("Ticker", ""))
                )
                edit_qty = st.number_input(
                    "Quantity",
                    min_value=1.0,
                    step=1.0,
                    value=max(_as_float(edit_src.get("Qty", 1), 1.0), 1.0)
                )
                edit_entry = st.number_input(
                    "Entry Price",
                    min_value=0.0,
                    step=0.05,
                    value=_as_float(edit_src.get("EntryPrice", 0.0), 0.0)
                )

            with e3:
                edit_stop = st.number_input(
                    "Stop Loss",
                    min_value=0.0,
                    step=0.05,
                    value=_as_float(edit_src.get("StopLoss", 0.0), 0.0)
                )
                edit_target = st.number_input(
                    "Target",
                    min_value=0.0,
                    step=0.05,
                    value=_as_float(edit_src.get("Target", 0.0), 0.0)
                )
                edit_status = st.selectbox(
                    "Status",
                    ["OPEN", "CLOSED"],
                    index=0 if str(edit_src.get("Status", "OPEN")).upper() == "OPEN" else 1
                )

            edit_notes = st.text_input(
                "Notes",
                value=str(edit_src.get("Notes", ""))
            )

            st.caption("If Status is CLOSED, fill Exit Price and Exit Date. If Status is OPEN, leave them as-is or empty.")
            f1, f2 = st.columns(2)
            with f1:
                exit_price_val = st.number_input(
                    "Exit Price",
                    min_value=0.0,
                    step=0.05,
                    value=_as_float(edit_src.get("ExitPrice", 0.0), 0.0)
                )
            with f2:
                exit_date_val = st.date_input(
                    "Exit Date",
                    value=_as_date(edit_src.get("ExitDate"))
                )

            edit_submit = st.form_submit_button("Save Edits")

        if edit_submit:
            try:
                tb.loc[edit_row, "Date"] = pd.Timestamp(edit_trade_date).strftime("%d-%m-%Y")
                tb.loc[edit_row, "Engine"] = str(edit_engine).strip()
                tb.loc[edit_row, "Ticker"] = str(edit_ticker).upper().strip()
                tb.loc[edit_row, "Action"] = str(edit_action).strip()
                tb.loc[edit_row, "Qty"] = float(edit_qty)
                tb.loc[edit_row, "EntryPrice"] = float(edit_entry)
                tb.loc[edit_row, "StopLoss"] = float(edit_stop)
                tb.loc[edit_row, "Target"] = float(edit_target)
                tb.loc[edit_row, "Notes"] = str(edit_notes).strip()
                tb.loc[edit_row, "Status"] = str(edit_status).strip().upper()
                tb.loc[edit_row, "CMP"] = float(edit_entry)

                if str(edit_status).upper() == "CLOSED":
                    tb.loc[edit_row, "ExitPrice"] = float(exit_price_val)
                    tb.loc[edit_row, "ExitDate"] = pd.Timestamp(exit_date_val).strftime("%d-%m-%Y")
                    tb.loc[edit_row, "PnL"] = (float(exit_price_val) - float(edit_entry)) * float(edit_qty)
                else:
                    tb.loc[edit_row, "ExitPrice"] = np.nan
                    tb.loc[edit_row, "ExitDate"] = np.nan
                    tb.loc[edit_row, "PnL"] = 0.0

                tb.to_csv(trade_file, index=False)
                st.success("Trade updated")
                st.rerun()
            except Exception as e:
                st.error(f"Edit failed: {e}")

    st.divider()

    # -------------------------------------------------
    # CLOSE TRADE
    # -------------------------------------------------
    st.markdown("### Close Existing Trade")

    open_only = pd.DataFrame()
    if not tb.empty and "Status" in tb.columns:
        open_only = tb[
            tb["Status"].astype(str).str.upper() == "OPEN"
        ].copy()

    if open_only.empty:
        st.info("No open trades available")
    else:
        options = [
            f"{i} | {str(r.get('Ticker', '')).strip()} | Qty {r.get('Qty', '')}"
            for i, r in open_only.iterrows()
        ]

        selected = st.selectbox(
            "Select Open Trade",
            options,
            key="close_trade_selector"
        )

        row_id = int(selected.split("|")[0].strip())

        c1, c2 = st.columns(2)
        with c1:
            exit_price = st.number_input(
                "Exit Price",
                min_value=0.0,
                step=0.05,
                key="exit_px"
            )
        with c2:
            exit_date = st.date_input(
                "Exit Date",
                value=pd.Timestamp.today().date(),
                key="exit_dt"
            )

        close_submit = st.button("Close Trade")

        if close_submit:
            try:
                entry = float(tb.loc[row_id, "EntryPrice"])
                qty = float(tb.loc[row_id, "Qty"])
                pnl = (float(exit_price) - entry) * qty

                tb.loc[row_id, "ExitPrice"] = float(exit_price)
                tb.loc[row_id, "ExitDate"] = pd.Timestamp(exit_date).strftime("%d-%m-%Y")
                tb.loc[row_id, "PnL"] = pnl
                tb.loc[row_id, "Status"] = "CLOSED"

                tb.to_csv(trade_file, index=False)

                st.success(f"Trade closed | PnL ₹{pnl:,.0f}")
                st.rerun()
            except Exception as e:
                st.error(f"Close failed: {e}")

    st.divider()

    # -------------------------------------------------
    # DELETE TRADE
    # -------------------------------------------------
    st.markdown("### Delete Trade")

    if tb.empty:
        st.info("Trade book empty")
    else:
        del_options = [
            f"{i} | {str(r.get('Ticker', '')).strip()} | {str(r.get('Status', '')).strip()}"
            for i, r in tb.iterrows()
        ]

        del_selected = st.selectbox(
            "Select Trade To Delete",
            del_options,
            key="delete_trade_selector"
        )

        del_row = int(del_selected.split("|")[0].strip())

        if st.button("Delete Trade"):
            try:
                tb = tb.drop(del_row)
                tb.to_csv(trade_file, index=False)
                st.success("Trade deleted")
                st.rerun()
            except Exception as e:
                st.error(f"Delete failed: {e}")

    st.divider()

    # -------------------------------------------------
    # LIVE TRADE BOOK
    # -------------------------------------------------
    st.markdown("### Current Trade Book")

    if tb.empty:
        st.info("No trades available")
    else:
        st.dataframe(
            tb.sort_index(ascending=False),
            use_container_width=True,
            hide_index=False
        )
 