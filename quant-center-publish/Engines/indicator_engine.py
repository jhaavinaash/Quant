"""
indicator_engine.py
-------------------
Calculates all strategy indicators for each stock and saves
enriched CSVs back into the data/ folder.

Indicators calculated:
  EMA10, EMA21, EMA50, EMA200   — trend filters
  ATR14                          — volatility / position sizing
  ADX14                          — trend strength
  ROC63                          — 3-month price momentum (skips last 5 days)
  RS_score                       — stock return vs Nifty 50 (20-day)
  Volume_ratio                   — today vol / 20-day avg vol
"""

import os
import pandas as pd
import yfinance as yf
from sector_map import load_universe

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR   = "data"
NIFTY_FILE = os.path.join(DATA_DIR, "NIFTY50.csv")
NIFTY_TKR  = "^NSEI"

# ── CSV loader (handles yfinance 2-row junk header) ───────────────────────────

def load_stock_csv(fpath):
    df = pd.read_csv(fpath, skiprows=2, header=0)
    df.columns = ["Date", "Close", "High", "Low", "Open", "Volume"]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).set_index("Date")
    for col in ["Close", "High", "Low", "Open", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Close"])
    return df

# ── Indicator functions ───────────────────────────────────────────────────────

def compute_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def compute_atr(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def compute_adx(df, period=14):
    high, low = df["High"], df["Low"]
    close     = df["Close"]
    plus_dm   = high.diff()
    minus_dm  = -low.diff()
    plus_dm[plus_dm   < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm[plus_dm   < minus_dm] = 0
    minus_dm[minus_dm < plus_dm]  = 0
    atr      = compute_atr(df, period)
    plus_di  = 100 * plus_dm.ewm(span=period, adjust=False).mean()  / atr
    minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).fillna(0)
    return dx.ewm(span=period, adjust=False).mean()

def compute_roc(series, period=63, skip=5):
    return (series.shift(skip) / series.shift(period + skip) - 1) * 100

def compute_rs(stock_close, nifty_close, period=20):
    stock_ret  = stock_close / stock_close.shift(period)
    nifty_ret  = nifty_close / nifty_close.shift(period)
    nifty_ret  = nifty_ret.reindex(stock_ret.index, method="ffill")
    return stock_ret / nifty_ret

# ── Load Nifty 50 benchmark ───────────────────────────────────────────────────

def load_nifty():
    if not os.path.exists(NIFTY_FILE):
        print("Downloading Nifty 50 benchmark...")
        nifty = yf.download(NIFTY_TKR, period="3y", interval="1d",
                            auto_adjust=True, progress=False)
        nifty.to_csv(NIFTY_FILE)
        print(f"  Saved to {NIFTY_FILE}")

    nifty = load_stock_csv(NIFTY_FILE)
    return nifty["Close"]

# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    universe = load_universe()
    tickers  = universe["Ticker"].tolist()
    nifty    = load_nifty()
    passed, failed = [], []

    for i, ticker in enumerate(tickers, 1):
        fpath = os.path.join(DATA_DIR, f"{ticker}.csv")
        print(f"[{i:>3}/{len(tickers)}] {ticker:<25}", end=" ")

        if not os.path.exists(fpath):
            print("SKIP — file not found")
            failed.append(ticker)
            continue

        try:
            df    = load_stock_csv(fpath)
            close = df["Close"]

            df["EMA10"]        = compute_ema(close, 10)
            df["EMA21"]        = compute_ema(close, 21)
            df["EMA50"]        = compute_ema(close, 50)
            df["EMA200"]       = compute_ema(close, 200)
            df["ATR14"]        = compute_atr(df, 14)
            df["ADX14"]        = compute_adx(df, 14)
            df["ROC63"]        = compute_roc(close, 63, 5)
            df["RS_score"]     = compute_rs(close, nifty, 20)
            df["Volume_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()

            df.to_csv(fpath)
            passed.append(ticker)
            print(f"OK — {len(df)} rows")

        except Exception as e:
            print(f"ERROR — {e}")
            failed.append(ticker)

    print(f"\n{'─'*45}")
    print(f"✓ Processed : {len(passed)} stocks")
    print(f"✗ Failed    : {len(failed)} stocks")
    if failed:
        print("Failed:", failed)

if __name__ == "__main__":
    run()