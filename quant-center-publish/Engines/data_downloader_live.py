"""
data_downloader_live.py
-----------------------
Downloads fresh OHLCV data for all stocks.
Uses start/end date approach to force latest data from yfinance.
During live market hours, also fetches current live price for today's row.
"""

import os
import time
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
from sector_map import load_universe

DATA_DIR  = "data"
PAUSE_SEC = 0.5

os.makedirs(DATA_DIR, exist_ok=True)

def get_live_price(ticker):
    try:
        info = yf.Ticker(ticker).fast_info
        return float(info['last_price'])
    except:
        return None

def download_all():
    universe = load_universe()
    tickers  = universe["Ticker"].tolist()
    total    = len(tickers)
    end_date   = date.today() + timedelta(days=1)
    start_date = date.today() - timedelta(days=365*5)

    passed, failed = [], []

    for i, ticker in enumerate(tickers, 1):
        save_path = os.path.join(DATA_DIR, f"{ticker}.csv")
        print(f"[{i:>3}/{total}] {ticker:<25}", end=" ")

        try:
            df = yf.download(
                ticker,
                start=start_date.isoformat(),
                end=end_date.isoformat(),
                interval="1d",
                auto_adjust=True,
                progress=False
            )

            # Flatten multi-level columns from new yfinance
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index.name = 'Date'

            if df.empty or len(df) < 20:
                print("SKIP — insufficient data")
                failed.append(ticker)
                continue

            # Drop rows where Close is NaN
            df = df.dropna(subset=["Close"])

            if df.empty:
                print("SKIP — all rows NaN")
                failed.append(ticker)
                continue

            # Fetch live price and update today's row
            live_price = get_live_price(ticker)
            today = pd.Timestamp(date.today())
            if live_price:
                if today in df.index:
                    df.loc[today, "Close"] = live_price
                else:
                    new_row = {col: None for col in df.columns}
                    new_row["Close"] = live_price
                    df.loc[today] = new_row

            last_date  = df.index[-1].date()
            last_close = df["Close"].iloc[-1]
            df.to_csv(save_path)
            print(f"OK — {len(df)} rows — last date: {last_date} — close: {last_close:.2f}")
            passed.append(ticker)

        except Exception as e:
            print(f"ERROR — {e}")
            failed.append(ticker)

        time.sleep(PAUSE_SEC)

    print(f"\n{'─'*45}")
    print(f"✓ Downloaded : {len(passed)} stocks")
    print(f"✗ Failed     : {len(failed)} stocks")
    if failed:
        print("Failed:", failed)

if __name__ == "__main__":
    download_all()
