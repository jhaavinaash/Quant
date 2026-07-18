import pandas as pd
import yfinance as yf
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ================= CONFIG =================
PRICE_FILE = BASE_DIR.parent / "data" / "stock_prices_clean.csv"
UNIVERSE_FILE = BASE_DIR.parent / "data" / "sector_map_fixed.csv"

signals_list = []

# ================= DATA UPDATER =================
def update_prices():
    u = pd.read_csv(UNIVERSE_FILE, encoding="utf-8-sig")
    u.columns = u.columns.str.strip().str.lower()
    tickers = (
        u["ticker"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .tolist()
    )

    try:
        old = pd.read_csv(PRICE_FILE)
        old["Date"] = pd.to_datetime(old["Date"]).dt.tz_localize(None)  # FIX 1: Force tz-naive
        last_date = old["Date"].max()
        start_date = last_date.strftime("%Y-%m-%d")
    except Exception:
        old = pd.DataFrame(columns=["Ticker","Date","Open","High","Low","Close"])
        start_date = "2022-01-01"

    print(f"Updating incremental data from {start_date}...")

    # Download all tickers at once for speed
    data = yf.download(tickers, start=start_date, group_by='ticker', progress=False, auto_adjust=True)

    # FIX 1 (continued): Normalize the downloaded index to tz-naive
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    # FIX 3: Pre-compute the last known date per ticker (avoids O(n²) inner loop)
    if not old.empty:
        last_dates = old.groupby("Ticker")["Date"].max().to_dict()
    else:
        last_dates = {}

    new_rows = []
    for t in tickers:
        try:
            # Handle both single ticker and multi-ticker returns
            if len(tickers) > 1:
                df_t = data[t].dropna()
            else:
                df_t = data.dropna()

            # FIX 1 (continued): Normalize per-ticker index too (belt-and-suspenders)
            if df_t.index.tz is not None:
                df_t.index = df_t.index.tz_localize(None)

            # FIX 3: Use pre-computed last date instead of filtering inside the loop
            ticker_last_date = last_dates.get(t, None)

            for date, row in df_t.iterrows():
                if ticker_last_date is not None and date <= ticker_last_date:
                    continue

                new_rows.append({
                    "Ticker": t,
                    "Date": date,
                    "Open": row["Open"],
                    "High": row["High"],
                    "Low": row["Low"],
                    "Close": row["Close"]
                })
        except Exception as e:
            # FIX 2: Log the error so you can diagnose problems
            print(f"  Warning: Could not process {t}: {e}")
            continue

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        final_df = pd.concat([old, new_df], ignore_index=True)
        final_df["Date"] = pd.to_datetime(final_df["Date"]).dt.tz_localize(None)  # Ensure consistency
        final_df = final_df.drop_duplicates(subset=["Ticker", "Date"], keep="last")
        final_df = final_df.sort_values(["Ticker", "Date"])
        final_df.to_csv(PRICE_FILE, index=False)
        print(f"Data update complete. Added {len(new_rows)} new rows.")
    else:
        print("No new data found.")

# ================= CORE =================
def run():
    global signals_list
    signals_list = []

    # ===== STEP 1: UPDATE DATA =====
    update_prices()

    # ===== STEP 2: LOAD DATA =====
    df = pd.read_csv(PRICE_FILE)
    df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)

    df = df[df["Date"] >= "2022-01-01"].copy()
    df = df.sort_values(["Ticker", "Date"]).drop_duplicates(["Ticker", "Date"], keep="last")
    df = df.sort_values(["Ticker", "Date"]).reset_index(drop=True)

    # ===== FEATURES =====
    df["ret60"] = df.groupby("Ticker")["Close"].pct_change(60)
    df["sma50"] = df.groupby("Ticker")["Close"].transform(lambda x: x.rolling(50).mean())
    df["sma50_slope"] = df.groupby("Ticker")["sma50"].transform(lambda x: x.diff(5))
    df["hh20"] = df.groupby("Ticker")["High"].transform(lambda x: x.rolling(20).max().shift(1))
    df["high5"] = df.groupby("Ticker")["High"].transform(lambda x: x.rolling(5).max())
    df["low5"]  = df.groupby("Ticker")["Low"].transform(lambda x: x.rolling(5).min())
    df["range5"] = (df["high5"] - df["low5"]) / df["Close"]

    # ===== SAFE DATE SELECTION =====
    unique_dates = sorted(df["Date"].unique())

    if len(unique_dates) < 1:
        print("Not enough data")
        return

    today = unique_dates[-1]

    day_df = df[df["Date"] == today]

    print("\n===== DEBUG SAMPLE =====")
    print("Signal Date:", today.date())
    print(f"Total tickers in DB: {df['Ticker'].nunique()}")
    print(f"Tickers available today: {len(day_df)}")

    # ===== SIGNALS (VCP / Momentum Logic) =====
    signals = day_df[
        (day_df["Close"] > day_df["sma50"]) &
        (day_df["sma50_slope"] > 0) &
        (day_df["ret60"] > 0.10) &
        (day_df["range5"] < 0.05) &
        (day_df["Close"] > day_df["hh20"])
    ].sort_values("ret60", ascending=False)

    if signals.empty:
        print("No signals found for the selected criteria.")
    else:
        print(f"\n===== ENGINE 2 SIGNALS ({today.date()}) =====")

    for _, row in signals.head(10).iterrows():
        print(f"{row['Ticker']} | Close: {round(row['Close'],2)} | RS (60d): {round(row['ret60']*100,2)}%")

        signals_list.append({
            "Ticker": row["Ticker"],
            "Sector": "Momentum",
            "Score": round(row["ret60"], 3),
            "Entry": round(row["Close"], 2),
            "SL": 0.0
        })

# ================= MAIN =================
def get_signals():
    run()
    return signals_list


if __name__ == "__main__":
    run()