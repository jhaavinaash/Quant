from pathlib import Path
"""
screener.py
-----------
Daily signal generator based on winning parameters:
  ROC10 skip1 | SL1.5 | Chan3.5 | ADX25 | Hold40 | Partial2.0

Replaces daily_signal.py in Claude_System1.py pipeline.
daily_signal.py kept as backup — do not delete.

Run via Claude_System1.py or standalone:
  python screener.py
"""

import os
import numpy as np
import pandas as pd
from datetime import date
from sector_map import load_universe
from notifier import send_signal_email

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR       = str(Path(__file__).resolve().parent / "data")
RESULTS_DIR    = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CAPITAL        = 100000
RISK_PCT       = 0.015
MAX_POS_PCT    = 0.20
HARD_SL_ATR    = 1.5
PARTIAL_ATR    = 2.0
CHANDELIER_ATR = 3.5
ADX_MIN        = 25
MAX_HOLD_DAYS  = 40
TOP_SECTORS_N  = 10
TOP_STOCKS     = 3
VOLUME_MIN     = 1.0
ROC_PERIOD     = 10
ROC_SKIP       = 1

# ── Loader ────────────────────────────────────────────────────────────────────

def load_enriched(ticker):
    fpath = os.path.join(DATA_DIR, f"{ticker}.csv")
    if not os.path.exists(fpath):
        return None
    df = pd.read_csv(fpath, index_col=0)
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[df.index.notna()]
    df = df.dropna(subset=["Close"])
    # Drop rows where key indicators are all NaN (live price rows)
    df = df.dropna(subset=["Volume_ratio", "RS_score"], how="any")
    return df

# ── ROC10 — computed fresh from Close prices ──────────────────────────────────

def compute_roc10(df):
    """
    ROC10 with skip1 — computed fresh from Close.
    Not from pre-saved ROC63 in CSV.
    Returns latest ROC value or NaN.
    """
    close = df["Close"]
    if len(close) < ROC_PERIOD + ROC_SKIP + 1:
        return np.nan
    shifted_now  = close.shift(ROC_SKIP)
    shifted_base = close.shift(ROC_PERIOD + ROC_SKIP)
    roc_series   = (shifted_now / shifted_base - 1) * 100
    val = roc_series.dropna()
    return val.iloc[-1] if not val.empty else np.nan

# ── Step 1: Sector ranking ────────────────────────────────────────────────────

def get_top_sectors(universe):
    records = []
    for _, row in universe.iterrows():
        df = load_enriched(row["Ticker"])
        if df is None or "RS_score" not in df.columns:
            continue
        rs = df["RS_score"].dropna()
        if rs.empty:
            continue
        records.append({"Sector": row["Sector"], "RS": rs.iloc[-1]})
    if not records:
        return []
    df_sec = pd.DataFrame(records)
    return (df_sec.groupby("Sector")["RS"]
                  .mean()
                  .sort_values(ascending=False)
                  .head(TOP_SECTORS_N)
                  .index.tolist())

# ── Step 2: Score stocks in top sectors ──────────────────────────────────────

def score_stocks(universe, top_sectors):
    filtered = universe[universe["Sector"].isin(top_sectors)]
    records  = []

    for _, row in filtered.iterrows():
        ticker = row["Ticker"]
        df     = load_enriched(ticker)
        if df is None or len(df) < ROC_PERIOD + ROC_SKIP + 5:
            continue
        last   = df.iloc[-1]
        prev   = df.iloc[-2]
        needed = ["RS_score", "Volume_ratio",
                  "EMA10", "EMA21", "EMA50", "ADX14", "ATR14"]
        if any(pd.isna(last.get(c, np.nan)) for c in needed):
            continue

        roc_val = compute_roc10(df)
        if pd.isna(roc_val):
            continue

        records.append({
            "Ticker":       ticker,
            "Sector":       row["Sector"],
            "Close":        last["Close"],
            "PrevClose":    prev["Close"],
            "ROC10":        roc_val,
            "RS_score":     last["RS_score"],
            "Volume_ratio": last["Volume_ratio"],
            "EMA10":        last["EMA10"],
            "EMA21":        last["EMA21"],
            "EMA50":        last["EMA50"],
            "ADX14":        last["ADX14"],
            "ATR14":        last["ATR14"],
        })

    if not records:
        return pd.DataFrame()

    df_all = pd.DataFrame(records)
    for col in ["ROC10", "RS_score", "Volume_ratio"]:
        std = df_all[col].std()
        df_all[f"z_{col}"] = (df_all[col] - df_all[col].mean()) / (std if std else 1)
    df_all["Score"] = (df_all["z_ROC10"]        * 0.40 +
                       df_all["z_RS_score"]      * 0.35 +
                       df_all["z_Volume_ratio"]  * 0.25)
    return df_all.sort_values("Score", ascending=False).reset_index(drop=True)

# ── Step 3: Entry filter ──────────────────────────────────────────────────────

def passes_entry(row):
    return (row["Close"]        > row["EMA50"]     and
            row["EMA10"]        > row["EMA21"]     and
            row["ADX14"]        > ADX_MIN          and
            row["Close"]        > row["PrevClose"] and
            row["Volume_ratio"] > VOLUME_MIN)

# ── Step 4: Position sizing ───────────────────────────────────────────────────

def calc_position(close, atr):
    risk_rs        = CAPITAL * RISK_PCT
    risk_per_share = HARD_SL_ATR * atr
    if risk_per_share <= 0:
        return None
    shares    = int(risk_rs / risk_per_share)
    pos_value = shares * close
    if pos_value > CAPITAL * MAX_POS_PCT:
        shares    = int((CAPITAL * MAX_POS_PCT) / close)
        pos_value = shares * close
    if shares < 1:
        return None
    actual_risk = shares * risk_per_share
    return {
        "shares":      shares,
        "pos_value":   round(pos_value, 2),
        "actual_risk": round(actual_risk, 2),
        "risk_pct":    round(actual_risk / CAPITAL * 100, 2),
    }

# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    universe    = load_universe()
    top_sectors = get_top_sectors(universe)
    scored      = score_stocks(universe, top_sectors)
    candidates  = []

    if scored.empty:
        print("No scored stocks. Run indicator_engine.py first.")
        send_signal_email(candidates, top_sectors)
        return

    print(f"\n{'═'*65}")
    print(f"  SCREENER — ROC10 | ADX25 | SL1.5x | Hold40 | Partial2.0x")
    print(f"  Date          : {date.today().strftime('%d %b %Y')}")
    print(f"  Active sectors: {len(top_sectors)}")
    print(f"  Top sectors   : {', '.join(top_sectors[:5])}...")
    print(f"{'═'*65}")

    checked = 0
    for _, row in scored.iterrows():
        if len(candidates) >= TOP_STOCKS:
            break
        if checked >= TOP_STOCKS * 4:
            break
        checked += 1

        if not passes_entry(row):
            continue

        pos = calc_position(row["Close"], row["ATR14"])
        if pos is None:
            continue

        close          = row["Close"]
        atr            = row["ATR14"]
        entry          = round(close, 2)
        sl             = round(close - HARD_SL_ATR    * atr, 2)
        partial_target = round(close + PARTIAL_ATR    * atr, 2)
        full_target    = round(close + CHANDELIER_ATR * atr, 2)
        sl_pct         = round((entry - sl)             / entry * 100, 2)
        partial_pct    = round((partial_target - entry) / entry * 100, 2)
        full_pct       = round((full_target - entry)    / entry * 100, 2)

        candidates.append({
            "Ticker":         row["Ticker"],
            "Sector":         row["Sector"],
            "Score":          round(row["Score"], 3),
            "Entry":          entry,
            "SL":             sl,
            "SL_pct":         f"-{sl_pct}%",
            "Partial_Target": partial_target,
            "Partial_pct":    f"+{partial_pct}%",
            "Full_Target":    full_target,
            "Full_pct":       f"+{full_pct}%",
            "Shares":         pos["shares"],
            "Capital_Used":   f"Rs.{pos['pos_value']:,.0f}",
            "Risk_Rs":        f"Rs.{pos['actual_risk']:,.0f}",
            "Risk_Pct":       f"{pos['risk_pct']}%",
            "ADX":            round(row["ADX14"], 1),
            "Vol_Ratio":      round(row["Volume_ratio"], 2),
            "ROC10":          round(row["ROC10"], 2),
        })

    if not candidates:
        print("\n  No buy signals today — no stocks passed all conditions.")
        print(f"{'═'*65}\n")
    else:
        for c in candidates:
            print(f"\n  {'─'*60}")
            print(f"  STOCK    : {c['Ticker']}  ({c['Sector']})")
            print(f"  Score    : {c['Score']}  |  ADX: {c['ADX']}  |  "
                  f"Vol: {c['Vol_Ratio']}x  |  ROC10: {c['ROC10']}%")
            print(f"  {'─'*60}")
            print(f"  Entry    : Rs.{c['Entry']}  (buy at market open tomorrow)")
            print(f"  SL       : Rs.{c['SL']}  ({c['SL_pct']} from entry)")
            print(f"  Target 1 : Rs.{c['Partial_Target']}  ({c['Partial_pct']})  "
                  f"<-- book 50% here")
            print(f"  Target 2 : Rs.{c['Full_Target']}  ({c['Full_pct']})  "
                  f"<-- trail rest")
            print(f"  {'─'*60}")
            print(f"  Shares   : {c['Shares']} shares")
            print(f"  Capital  : {c['Capital_Used']}")
            print(f"  Risk     : {c['Risk_Rs']}  ({c['Risk_Pct']} of capital)")
            print(f"  {'─'*60}")

        pd.DataFrame(candidates).to_csv(RESULTS_DIR / "screener_signal.csv", index=False)
        print(f"\n  Saved -> results/screener_signal.csv")

    print(f"{'═'*65}\n")
    send_signal_email(candidates, top_sectors)


if __name__ == "__main__":
    run()