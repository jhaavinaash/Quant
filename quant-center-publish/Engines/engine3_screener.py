import pandas as pd
import yfinance as yf
from pathlib import Path

signals_list = []

BASE_DIR = Path(__file__).resolve().parent

PORTFOLIO_FILE = BASE_DIR.parent / "portfolio" / "trades_log.csv"
DATA_FILE = BASE_DIR.parent / "data" / "sector_map_fixed.csv"

# ---------------- PARAMETERS ----------------
CAPITAL = 200000
ENGINE_CAPITAL = 100000
MAX_POSITIONS = 3
HOLD_DAYS = 5

TP = 0.06
SL = -0.03
COST = 0.003

# ---------------- HELPERS ----------------
def get_used_capital():
    try:
        if not PORTFOLIO_FILE.exists():
            return 0.0

        df = pd.read_csv(PORTFOLIO_FILE)

        if df.empty:
            return 0.0

        df["Engine"] = df["Engine"].astype(str).str.upper().str.strip()
        df["Status"] = df["Status"].astype(str).str.upper().str.strip()
        df["EntryPrice"] = pd.to_numeric(df["EntryPrice"], errors="coerce")
        df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce")

        open_e3 = df[(df["Engine"] == "E3") & (df["Status"] == "OPEN")].copy()
        if open_e3.empty:
            return 0.0

        return float((open_e3["EntryPrice"] * open_e3["Qty"]).fillna(0).sum())

    except:
        return 0.0


# ---------------- CORE ----------------
def run():
    global signals_list
    signals_list = []

    stocks = pd.read_csv(DATA_FILE)["Ticker"].drop_duplicates().tolist()

    print("Downloading data...")

    data = yf.download(
        stocks,
        period="6mo",
        auto_adjust=True,
        group_by="ticker",
        progress=False
    )

    rows = []

    for s in stocks:
        try:
            df = data[s].copy()

            df["ret3"] = df["Close"].pct_change(3)
            df["ret120"] = df["Close"].pct_change(120)
            df["vol5"] = df["Close"].pct_change().rolling(5).std()
            df["sma100"] = df["Close"].rolling(100).mean()

            last = df.iloc[-1]

            rows.append({
                "Ticker": s,
                "ret3": last["ret3"],
                "ret120": last["ret120"],
                "vol5": last["vol5"],
                "sma100": last["sma100"],
                "CMP": last["Close"]
            })

        except:
            pass

    df_all = pd.DataFrame(rows)

    if df_all.empty:
        print("No data.")
        return []

    df_all["rs_rank"] = df_all["ret120"].rank(pct=True)

    signals_df = df_all[
        (df_all["rs_rank"] >= 0.85) &
        (df_all["CMP"] > df_all["sma100"]) &
        (df_all["ret3"] < -0.01) &
        (df_all["ret3"] > -0.04) &
        (df_all["vol5"] < 0.08)
    ].sort_values("ret120", ascending=False).reset_index(drop=True)

    print("\nENGINE-3 TRADE CANDIDATES\n")

    if signals_df.empty:
        print("No signals")
        return []

    print(signals_df[["Ticker", "CMP"]])

    # ----- CAPITAL -----
    used_capital = get_used_capital()
    remaining_capital = ENGINE_CAPITAL - used_capital

    print(f"\nUsed Capital (E3): ₹{round(used_capital, 1)}")
    print(f"Remaining Capital (E3): ₹{round(remaining_capital, 1)}")

    # ----- SLOT CHECK (ONLY WARNING) -----
    open_positions = 0
    try:
        if PORTFOLIO_FILE.exists():
            pf = pd.read_csv(PORTFOLIO_FILE)
            pf["Engine"] = pf["Engine"].astype(str).str.upper().str.strip()
            pf["Status"] = pf["Status"].astype(str).str.upper().str.strip()

            open_positions = len(
                pf[(pf["Engine"] == "E3") & (pf["Status"] == "OPEN")]
            )
    except:
        pass

    if open_positions >= MAX_POSITIONS:
        pass

    # ----- RETURN FORMAT FOR CM -----
    signals = []

    for _, row in signals_df.iterrows():
        entry = float(row["CMP"])
        sl = entry * (1 - 0.03)

        signals.append({
            "Ticker": row["Ticker"],
            "Entry": round(entry, 2),
            "SL": round(sl, 2)
        })
    
    print("E3 final signals:", signals)
    return signals


# ---------------- CM ENTRY ----------------
def get_signals():
    return run()


# ---------------- MANUAL RUN ----------------
if __name__ == "__main__":
    run()