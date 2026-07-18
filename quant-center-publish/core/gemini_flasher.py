"""
Gemini Independent Opportunity Flasher Page — IMPROVED VERSION
Adds four quality filters on top of the original logic:
  1. ADX >= 22 (trend strength must be real, not just direction)
  2. Volume on signal day >= 1.2 × 20-day average (participation check)
  3. Tightened proximity — only actual breakouts (CMP at or above pivot, not below)
  4. SL floor — never risk more than 5% of entry, regardless of Supertrend

Plus a market-mood indicator: Advance/Decline ratio of the Nifty 500 universe
computed from the same bulk download (no extra network calls). Shown as a
banner at the top of every scan to provide live breadth context — not a
hard gate, you decide whether to act based on the breadth reading.

UI, file paths, tracking ledger, and the interface function name are unchanged
so app_ai_2.py and any other caller continue to work without modification.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
from datetime import datetime
from pathlib import Path

import config
_BASE             = Path(getattr(config, "BASE_DIR", Path(__file__).resolve().parent.parent))
_n500_primary     = Path(getattr(config, "NIFTY500_UNIVERSE_FILE",
                          _BASE / "data" / "nifty500_universe.csv"))
_fallback         = Path(getattr(config, "UNIVERSE_FILE",
                          _BASE / "data" / "sector_map_fixed.csv"))
NIFTY500_PATH     = _n500_primary if _n500_primary.exists() else _fallback
TRACKED_PATH      = Path(getattr(config, "FLASHER_TRACKED_FILE",
                          _BASE / "data" / "flasher_tracked_trades.csv"))
CAPITAL_PER_TRADE = 15000.0

# ── Filter thresholds (the four fixes) ─────────────────────────────────
MIN_ADX             = 22.0      # Fix 1: trend-strength gate
MIN_VOL_MULTIPLIER  = 1.2       # Fix 2: today's volume vs 20-day avg
PROXIMITY_UPPER     = 1.02      # Fix 3: 0% below to +2% above pivot (was -1.5% to +1.5%)
MAX_RISK_PCT        = 0.05      # Fix 4: cap SL distance at 5% of entry (choppy/high-IV markets)


def calculate_technical_dna(df: pd.DataFrame, period: int = 14, multiplier: float = 3.0) -> pd.DataFrame:
    """High-performance ATR, ADX, and Supertrend calculation."""
    df = df.copy().sort_values("Date").reset_index(drop=True)
    high, low, close = df["High"], df["Low"], df["Close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(window=period).mean()

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr_smooth = tr.rolling(window=period).sum()
    pos_di = 100 * (pd.Series(pos_dm).rolling(window=period).sum() / (tr_smooth + 1e-9))
    neg_di = 100 * (pd.Series(neg_dm).rolling(window=period).sum() / (tr_smooth + 1e-9))
    dx = 100 * (pos_di - neg_di).abs() / (pos_di + neg_di + 1e-9)
    df["ADX"] = dx.rolling(window=period).mean()

    hl2 = (high + low) / 2
    basic_ub = hl2 + (multiplier * df["ATR"])
    basic_lb = hl2 - (multiplier * df["ATR"])

    final_ub, final_lb = np.zeros(len(df)), np.zeros(len(df))
    supertrend, direction = np.zeros(len(df)), np.ones(len(df))

    for i in range(1, len(df)):
        final_ub[i] = basic_ub[i] if basic_ub[i] < final_ub[i-1] or close[i-1] > final_ub[i-1] else final_ub[i-1]
        final_lb[i] = basic_lb[i] if basic_lb[i] > final_lb[i-1] or close[i-1] < final_lb[i-1] else final_lb[i-1]
        if direction[i-1] == 1:
            if close[i] < final_lb[i]:
                direction[i], supertrend[i] = -1, final_ub[i]
            else:
                direction[i], supertrend[i] = 1, final_lb[i]
        else:
            if close[i] > final_ub[i]:
                direction[i], supertrend[i] = 1, final_lb[i]
            else:
                direction[i], supertrend[i] = -1, final_ub[i]

    df["Supertrend"] = supertrend
    df["ST_Direction"] = direction
    return df


# ── Market mood gauge — Advance/Decline ratio of the scanned universe ─
def compute_advance_decline(bulk_data, tickers) -> dict:
    """
    Compute today's A/D breadth from the bulk-downloaded universe data.
    No extra network calls — reuses the data already pulled for the scan.
    Returns dict with advances, declines, unchanged, ratio, advance_pct.
    """
    advances = declines = unchanged = 0
    for ticker in tickers:
        try:
            if ticker not in bulk_data.columns.levels[0]:
                continue
            closes = bulk_data[ticker]["Close"].dropna()
            if len(closes) < 2:
                continue
            today, yesterday = float(closes.iloc[-1]), float(closes.iloc[-2])
            if   today > yesterday: advances += 1
            elif today < yesterday: declines += 1
            else:                   unchanged += 1
        except Exception:
            continue
    total       = advances + declines + unchanged
    ratio       = advances / declines if declines > 0 else float("inf")
    advance_pct = advances / total * 100 if total > 0 else 0.0
    return {
        "advances":    advances,
        "declines":    declines,
        "unchanged":   unchanged,
        "total":       total,
        "ratio":       ratio,
        "advance_pct": advance_pct,
    }


def render_breadth_banner(breadth: dict) -> None:
    """Show A/D breadth as a colour-coded banner — informational, not a gate."""
    adv, dec, unc = breadth["advances"], breadth["declines"], breadth["unchanged"]
    ratio, pct = breadth["ratio"], breadth["advance_pct"]
    ratio_str = f"{ratio:.2f}" if ratio != float("inf") else "∞"

    if ratio >= 1.5:
        st.success(
            f"🟢 **Strong positive breadth** — A/D: {adv} : {dec}  (ratio {ratio_str})  ·  "
            f"{pct:.0f}% of universe advancing  ·  conducive for breakouts"
        )
    elif ratio >= 1.0:
        st.success(
            f"🟢 **Positive breadth** — A/D: {adv} : {dec}  (ratio {ratio_str})  ·  "
            f"{pct:.0f}% advancing  ·  market mood supportive"
        )
    elif ratio >= 0.7:
        st.warning(
            f"🟡 **Mixed breadth** — A/D: {adv} : {dec}  (ratio {ratio_str})  ·  "
            f"{pct:.0f}% advancing  ·  selective day, expect fewer follow-throughs"
        )
    else:
        st.error(
            f"🔴 **Weak breadth** — A/D: {adv} : {dec}  (ratio {ratio_str})  ·  "
            f"only {pct:.0f}% advancing  ·  breakouts likely to fail today, consider waiting"
        )


def scan_nifty500_universe() -> pd.DataFrame:
    """Four-filter scan. Returns only high-conviction immediate breakouts."""
    if not os.path.exists(NIFTY500_PATH):
        st.error(f"Universe file missing at: {NIFTY500_PATH}")
        return pd.DataFrame()

    try:
        universe_df = pd.read_csv(NIFTY500_PATH)
    except Exception as e:
        st.error(f"Error parsing universe CSV: {e}")
        return pd.DataFrame()

    ticker_col = "Ticker" if "Ticker" in universe_df.columns else universe_df.columns[0]
    raw_tickers = [str(s).strip() for s in universe_df[ticker_col]]
    raw_tickers = [t for t in raw_tickers if "DUMMY" not in t.upper()]
    formatted_tickers = [t if "." in t else f"{t}.NS" for t in raw_tickers]
    ticker_mapping = dict(zip(formatted_tickers, raw_tickers))

    matched_setups = []
    st.info(f"⚡ Scanning {len(formatted_tickers)} tickers with 4-filter quality gates...")

    try:
        bulk_data = yf.download(formatted_tickers, period="150d",
                                group_by="ticker", progress=False, auto_adjust=True)
    except Exception as e:
        st.error(f"Bulk download failed: {e}")
        return pd.DataFrame()

    # ── Market mood: A/D breadth from the same bulk data (zero extra calls) ──
    breadth = compute_advance_decline(bulk_data, formatted_tickers)
    # Store breadth in session state so it persists across rerenders
    st.session_state["gemini_breadth_cache"] = breadth

    progress_bar = st.progress(0)
    total = len(formatted_tickers)
    rejected_counts = {"st_dir": 0, "ema50": 0, "proximity": 0,
                       "adx": 0, "volume": 0, "sl_invalid": 0}

    for idx, f_ticker in enumerate(formatted_tickers):
        progress_bar.progress((idx + 1) / total)
        raw_ticker = ticker_mapping[f_ticker]

        try:
            if f_ticker not in bulk_data.columns.levels[0]:
                continue
            df_hist = bulk_data[f_ticker].copy().dropna(subset=["Close"])
            if len(df_hist) < 90:
                continue
            df_hist = df_hist.reset_index()
            if "Date" not in df_hist.columns and "index" in df_hist.columns:
                df_hist = df_hist.rename(columns={"index": "Date"})

            df = calculate_technical_dna(df_hist)
            close, highs, lows = df["Close"].values, df["High"].values, df["Low"].values
            volumes = df["Volume"].values if "Volume" in df.columns else None

            # ── Original filter 1: Supertrend bullish ────────────────
            if df["ST_Direction"].iloc[-1] != 1:
                rejected_counts["st_dir"] += 1
                continue

            # ── Original filter 2: above EMA50 ───────────────────────
            ema_50 = df["Close"].ewm(span=50, adjust=False).mean().values
            if close[-1] < ema_50[-1]:
                rejected_counts["ema50"] += 1
                continue

            pivot_entry = float(np.max(highs[-15:]))

            # ── Fix 4: tightened proximity — only above the pivot ────
            if not (pivot_entry <= close[-1] <= pivot_entry * PROXIMITY_UPPER):
                rejected_counts["proximity"] += 1
                continue

            # ── Fix 1: ADX trend-strength gate ───────────────────────
            current_adx = float(df["ADX"].iloc[-1])
            if pd.isna(current_adx) or current_adx < MIN_ADX:
                rejected_counts["adx"] += 1
                continue

            # ── Fix 2: volume participation check ────────────────────
            if volumes is not None and len(volumes) >= 20:
                vol_today = float(volumes[-1])
                vol_avg20 = float(np.nanmean(volumes[-21:-1]))
                if vol_avg20 <= 0 or vol_today < vol_avg20 * MIN_VOL_MULTIPLIER:
                    rejected_counts["volume"] += 1
                    continue
                vol_ratio = vol_today / vol_avg20
            else:
                vol_ratio = np.nan

            # ── Stop-loss: original logic + Fix 5 floor ──────────────
            sl_from_indicators = float(max(np.min(lows[-10:]),
                                           df["Supertrend"].iloc[-1]))
            sl_floor = pivot_entry * (1 - MAX_RISK_PCT)
            stop_loss = max(sl_from_indicators, sl_floor)
            risk_spread = pivot_entry - stop_loss
            if risk_spread <= 0:
                rejected_counts["sl_invalid"] += 1
                continue

            # Target: maintain 1:3 R:R (now with capped, sensible risk)
            target_profit = pivot_entry + (risk_spread * 3.0)

            qty = int(CAPITAL_PER_TRADE // close[-1])
            actual_capital = qty * close[-1]

            matched_setups.append({
                "Ticker": raw_ticker.replace(".NS", ""),
                "CMP": round(close[-1], 2),
                "Entry_Trigger": round(pivot_entry, 2),
                "Stop_Loss": round(stop_loss, 2),
                "Target_Profit": round(target_profit, 2),
                "Qty": qty,
                "Capital_Req": round(actual_capital, 2),
                "ADX": round(current_adx, 2),
                "Vol_x_Avg": round(vol_ratio, 2) if not pd.isna(vol_ratio) else "—",
                "Risk_%": round(risk_spread / pivot_entry * 100, 2),
            })
        except Exception:
            continue

    progress_bar.empty()

    # Show why setups were rejected — helps user understand filter strictness
    st.caption(
        f"Filter rejection counts — "
        f"Supertrend not bullish: {rejected_counts['st_dir']}  ·  "
        f"Below EMA50: {rejected_counts['ema50']}  ·  "
        f"Not at breakout: {rejected_counts['proximity']}  ·  "
        f"ADX<{MIN_ADX}: {rejected_counts['adx']}  ·  "
        f"Low volume: {rejected_counts['volume']}  ·  "
        f"Invalid SL: {rejected_counts['sl_invalid']}"
    )
    return pd.DataFrame(matched_setups)


def render_gemini_flasher_interface():
    st.markdown(
        "<h3 style='margin:0; padding:0; font-size:22px; font-weight:600;'>⚡ Gemini Opportunity Flasher "
        "<span style='font-size:14px; font-weight:400; color:#888; margin-left:15px;'>"
        "4-Filter Quality Gates • ₹15k Allocation • Real-Time Tracking</span></h3>",
        unsafe_allow_html=True
    )
    st.markdown("<hr style='margin:8px 0 15px 0; border:0; border-top:1px solid #444;'>", unsafe_allow_html=True)

    # ── Methodology note for the user ─────────────────────────────────
    with st.expander("ℹ️ What this scanner now checks (4 filters + breadth context)"):
        st.markdown(
            f"""
            **Per-stock quality filters:**
            1. **Supertrend bullish** — direction = +1 on (14, 3) Supertrend
            2. **Above EMA(50)** — price in established uptrend
            3. **At breakout** — CMP within 0% to +{(PROXIMITY_UPPER-1)*100:.0f}% above 15-day high (no premature setups)
            4. **ADX ≥ {MIN_ADX}** — trend strength is real, not noise
            5. **Volume ≥ {MIN_VOL_MULTIPLIER}× 20-day avg** — breakout has participation
            6. **Max risk per trade ≤ {MAX_RISK_PCT*100:.0f}%** — SL floored so R:R stays sensible in choppy markets

            **Market mood gauge (shown as banner, informational only):**
            - **A/D ratio** of the Nifty 500 universe — today's advancers vs decliners
            - 🟢 Ratio ≥ 1.0 = supportive · 🟡 0.7-1.0 = mixed · 🔴 < 0.7 = avoid
            - Computed from the same bulk download — zero extra API calls
            - Not a hard gate — you decide whether to act on signals based on the reading

            Each filter's rejection count is shown below the scan results.
            """
        )

    if "gemini_scan_cache" not in st.session_state:
        st.session_state["gemini_scan_cache"] = pd.DataFrame()
    if "gemini_breadth_cache" not in st.session_state:
        st.session_state["gemini_breadth_cache"] = None

    if st.button("🚀 Run Quality-Filtered Nifty 500 Scan", key="gemini_scan_trigger"):
        with st.spinner("Applying 4-filter quality gates..."):
            results = scan_nifty500_universe()
            st.session_state["gemini_scan_cache"] = results
            if results.empty:
                st.info("No tickers passed all 4 filters today. Patience is the edge here.")

    # Breadth banner — rendered from session state so it survives every rerender
    if st.session_state.get("gemini_breadth_cache") is not None:
        render_breadth_banner(st.session_state["gemini_breadth_cache"])

    cached_df = st.session_state["gemini_scan_cache"]

    if not cached_df.empty:
        st.markdown(f"### 🎯 Quality-Filtered Setups ({len(cached_df)})")

        for _, row in cached_df.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 3, 3])

                with col1:
                    st.subheader(row["Ticker"])
                    st.metric("Live Market Price", f"₹{row['CMP']:,}")
                    st.caption(f"ADX: {row['ADX']}  ·  Vol×Avg: {row['Vol_x_Avg']}  ·  Risk: {row['Risk_%']}%")

                with col2:
                    st.markdown("**📐 Trade Plan**")
                    st.write(f"🔹 **Entry Pivot:** ₹{row['Entry_Trigger']:,}")
                    st.write(f"🛑 **Stop Loss:** ₹{row['Stop_Loss']:,}")
                    st.write(f"🎯 **Target (3:1):** ₹{row['Target_Profit']:,}")

                with col3:
                    st.markdown("**💰 Capital**")
                    st.write(f"⚖️ **Qty:** {row['Qty']} shares")
                    st.write(f"💵 **Deployed:** ₹{row['Capital_Req']:,}")

                    if st.button("📌 Record & Monitor", key=f"gemini_track_{row['Ticker']}"):
                        Path(TRACKED_PATH).parent.mkdir(parents=True, exist_ok=True)
                        new_log = pd.DataFrame([{
                            "Date_Added": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Ticker": row["Ticker"],
                            "Qty": row["Qty"],
                            "Entry": row["Entry_Trigger"],
                            "SL": row["Stop_Loss"],
                            "Target": row["Target_Profit"],
                            "Live_CMP": row["CMP"],
                            "Status": "OBSERVING"
                        }])
                        file_headers = not os.path.exists(TRACKED_PATH)
                        new_log.to_csv(TRACKED_PATH, mode='a', index=False, header=file_headers)
                        st.toast(f"✓ {row['Ticker']} added — live monitoring on")

    st.markdown("---")
    st.subheader("📡 Live Position Monitor (Flasher Ledger)")

    if os.path.exists(TRACKED_PATH):
        try:
            tracked_df = pd.read_csv(TRACKED_PATH)
            if not tracked_df.empty:
                with st.spinner("Pinging NSE for live prices..."):
                    for idx, r in tracked_df.iterrows():
                        if r["Status"] not in ["🎯 TARGET HIT", "🛑 SL HIT"]:
                            try:
                                live_price = yf.Ticker(f"{r['Ticker']}.NS").history(period="1d")["Close"].iloc[-1]
                                tracked_df.at[idx, "Live_CMP"] = round(live_price, 2)
                                if live_price >= r["Target"]:
                                    tracked_df.at[idx, "Status"] = "🎯 TARGET HIT"
                                elif live_price <= r["SL"]:
                                    tracked_df.at[idx, "Status"] = "🛑 SL HIT"
                                elif live_price >= r["Entry"]:
                                    tracked_df.at[idx, "Status"] = "⚡ ACTIVE"
                            except Exception:
                                pass

                tracked_df.to_csv(TRACKED_PATH, index=False)

                def highlight_status(val):
                    if val == "🎯 TARGET HIT": return 'background-color: #004d00; color: white'
                    if val == "🛑 SL HIT":     return 'background-color: #4d0000; color: white'
                    if val == "⚡ ACTIVE":      return 'background-color: #003366; color: white'
                    return ''

                # Format numeric columns — prevents raw float display (1757.900000)
                for _fc in ["Entry", "SL", "Target", "Live_CMP", "Qty"]:
                    if _fc in tracked_df.columns:
                        tracked_df[_fc] = pd.to_numeric(tracked_df[_fc], errors="coerce")

                _tcol_cfg = {}
                for _c, _fmt, _w in [
                    ("Date_Added", None,    140),
                    ("Ticker",     None,     90),
                    ("Qty",        "%d",     55),
                    ("Entry",      "₹%.2f", 100),
                    ("SL",         "₹%.2f", 100),
                    ("Target",     "₹%.2f", 100),
                    ("Live_CMP",   "₹%.2f", 100),
                    ("Status",     None,    110),
                ]:
                    if _c not in tracked_df.columns:
                        continue
                    if _fmt:
                        _tcol_cfg[_c] = st.column_config.NumberColumn(_c, format=_fmt, width=_w)
                    else:
                        _tcol_cfg[_c] = st.column_config.TextColumn(_c, width=_w)

                try:
                    st.dataframe(
                        tracked_df.style.map(highlight_status, subset=["Status"]),
                        use_container_width=True, hide_index=True,
                        column_config=_tcol_cfg,
                    )
                except Exception:
                    st.dataframe(tracked_df, use_container_width=True, hide_index=True,
                                 column_config=_tcol_cfg)

                if st.button("🗑️ Clear Tracking Ledger", key="clear_gemini_ledger"):
                    os.remove(TRACKED_PATH)
                    st.rerun()
            else:
                st.info("No active operations recorded.")
        except Exception as e:
            st.error(f"Error accessing ledger: {e}")
    else:
        st.caption("Tracking file does not exist yet. Record a setup above to start live monitoring.")