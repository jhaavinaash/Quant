import pandas as pd
import yfinance as yf

# =========================
# CONFIG
# =========================

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR.parent / "data" / "sector_map_fixed.csv"
LOOKBACK_DAYS = 60

TOP_SECTORS = 2
TOP_STOCKS = 2
BREADTH_THRESHOLD = 0.10
MIN_STOCKS = 2

STOP_LOSS_PCT = 0.12

# =========================
# CORE FUNCTION
# =========================
def get_signals():

    # =========================
    # LOAD UNIVERSE
    # =========================
    df = pd.read_csv(CSV_PATH)

    if "Yahoo Finance Code" in df.columns:
        ticker_col = "Yahoo Finance Code"
    elif "Ticker" in df.columns:
        ticker_col = "Ticker"
    else:
        raise ValueError("Ticker column not found")

    df["Ticker"] = df[ticker_col].astype(str).str.strip().str.upper()
    df["Sector"] = df["Sector"].replace({"Realty": "Real Estate"})

    tickers = df["Ticker"].dropna().unique().tolist()

    # =========================
    # DOWNLOAD DATA
    # =========================
    data = yf.download(
        tickers,
        period=f"{LOOKBACK_DAYS}d",
        auto_adjust=True,
        progress=False
    )

    if "Close" not in data:
        return []

    close_prices = data["Close"].dropna(axis=1)

    if close_prices.shape[0] < 20:
        return []

    # =========================
    # CALCULATE RETURNS
    # =========================
    ret_20 = close_prices.iloc[-1] / close_prices.iloc[-20] - 1

    temp = pd.DataFrame({
        "Ticker": ret_20.index,
        "20D": ret_20.values
    })

    temp = temp.merge(df[["Ticker", "Sector"]], on="Ticker", how="left")
    temp = temp.dropna(subset=["Sector"])

    # =========================
    # SECTOR STRENGTH
    # =========================
    market_ret = temp["20D"].mean()
    sector_strength = {}

    for sector, group in temp.groupby("Sector"):

        if (group["20D"] > BREADTH_THRESHOLD).sum() < MIN_STOCKS:
            continue

        top_3 = group.sort_values("20D", ascending=False).head(3)
        if len(top_3) < 3:
            continue

        strength = top_3["20D"].mean() - market_ret
        if strength > 0:
            sector_strength[sector] = strength

    # =========================
    # SELECT PICKS
    # =========================
    picks = []

    if sector_strength:

        top_sectors = (
            pd.Series(sector_strength)
            .sort_values(ascending=False)
            .head(TOP_SECTORS)
            .index
        )

        for sector in top_sectors:
            g = temp[temp["Sector"] == sector]
            g = g[g["20D"] > 0].sort_values("20D", ascending=False).head(TOP_STOCKS)
            picks.extend(g["Ticker"].tolist())

    # =========================
    # FORMAT FOR CM
    # =========================
    signals = []

    latest_close = close_prices.iloc[-1]

    for ticker in picks:
        if ticker not in latest_close:
            continue

        entry = float(latest_close[ticker])
        sl = float(entry * (1 - STOP_LOSS_PCT))

        signals.append({
            "Ticker": ticker,
            "Entry": round(entry, 2),
            "SL": round(sl, 2)
        })

    return signals


# =========================
# OPTIONAL MANUAL RUN
# =========================
if __name__ == "__main__":

    signals = get_signals()

    print("\n===== E5 SIGNAL =====")

    if signals:
        for s in signals:
            print(f"{s['Ticker']} | CMP: {s['Entry']} | SL: {s['SL']}")
    else:
        print("No valid signals today")