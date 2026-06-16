import pandas as pd
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

DATA_FILE = DATA_DIR / "stock_prices_clean.csv"
SECTOR_FILE = DATA_DIR / "sector_map_fixed.csv"

# =========================
# PARAMETERS (LOCKED)
# =========================
THREE_DAY_DIP_MIN = -0.08
THREE_DAY_DIP_MAX = -0.04

RET_60_MIN = 0.25

TP_PCT = 0.057
SL_PCT = 0.04
MAX_HOLD_DAYS = 7

TOP_N = 6

# =========================
# CORE FUNCTION
# =========================
def run(print_output=True):

    signals_list = []

    # ---- SAFE DATA UPDATE (NO HANG) ----
    try:
        subprocess.run(
            ["py", str(DATA_DIR / "download_prices.py")],
            timeout=45
        )
    except:
        if print_output:
            print("Warning: Data update skipped")

    # ---- LOAD DATA ----
    df = pd.read_csv(DATA_FILE)
    df["Date"] = pd.to_datetime(df["Date"])

    df = df.sort_values(["Ticker", "Date"]).reset_index(drop=True)

    # ---- FEATURES ----
    df["ret3"] = df.groupby("Ticker")["Close"].pct_change(3)
    df["ret60"] = df.groupby("Ticker")["Close"].pct_change(60)

    df["sma100"] = df.groupby("Ticker")["Close"].transform(
        lambda x: x.rolling(100).mean()
    )

    df["sma100_slope"] = df.groupby("Ticker")["sma100"].transform(
        lambda x: x.diff(5)
    )

    df["vol5"] = (
        df.groupby("Ticker")["Close"]
        .pct_change()
        .rolling(5)
        .std()
    )

    # =========================
    # INDUSTRY RS21
    # =========================
    sector_map = pd.read_csv(SECTOR_FILE)

    df = df.merge(
        sector_map[["Ticker", "Sector"]],
        on="Ticker",
        how="left"
    )

    df["ret21"] = df.groupby("Ticker")["Close"].pct_change(21)

    sector_ret21 = (
        df.groupby(["Date", "Sector"])["ret21"]
        .mean()
        .reset_index(name="sector_ret21")
    )

    universe_ret21 = (
        df.groupby("Date")["ret21"]
        .mean()
        .reset_index(name="universe_ret21")
    )

    sector_ret21 = sector_ret21.merge(
        universe_ret21,
        on="Date",
        how="left"
    )

    sector_ret21["industry_rs21"] = (
        sector_ret21["sector_ret21"]
        - sector_ret21["universe_ret21"]
    )

    df = df.merge(
        sector_ret21[["Date", "Sector", "industry_rs21"]],
        on=["Date", "Sector"],
        how="left"
    )

    # ---- LATEST DATE ----
    latest_date = df["Date"].max()
    today_df = df[df["Date"] == latest_date].copy()
    
    # ---- SIGNALS ----
    signals = today_df[
        (today_df["ret3"] >= THREE_DAY_DIP_MIN) &
        (today_df["ret3"] <= THREE_DAY_DIP_MAX) &
        (today_df["ret60"] > RET_60_MIN) &
        (today_df["Close"] > today_df["sma100"]) &
        (today_df["sma100_slope"] > 0) &
        (today_df["vol5"] < 0.03) &
        (today_df["industry_rs21"] > 0.02)
    ].sort_values("ret3")

    # ---- PRINT ----
    if print_output:
        print("\n===== ENGINE-4 SIGNALS =====")
        print("Date:", latest_date.date())

        if len(signals) == 0:
            print("No trades today.")
        else:
            print(
                signals[
                    [
                        "Ticker",
                        "Close",
                        "ret3",
                        "ret60",
                        "industry_rs21"
                    ]
                ].head(TOP_N)
            )

    # ---- BUILD SIGNAL LIST ----
    for _, row in signals.head(TOP_N).iterrows():

        price = row["Close"]

        target = price * (1 + TP_PCT)
        stop = price * (1 - SL_PCT)

        signals_list.append({
            "Ticker": row["Ticker"],
            "Sector": "E4",
            "Score": 0,
            "Entry": round(price, 2),
            "SL": round(stop, 2),
            "SL_pct": "",
            "Partial_Target": round(target, 2),
            "Partial_pct": "",
            "Full_Target": "",
            "Full_pct": "",
            "Shares": "",
            "Capital_Used": "",
            "Risk_Rs": "",
            "Risk_Pct": "",
            "ADX": "",
            "Vol_Ratio": ""
        })

    return signals_list


# =========================
# INTERFACE
# =========================
def get_signals():
    return run(print_output=False)


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    run(print_output=True)