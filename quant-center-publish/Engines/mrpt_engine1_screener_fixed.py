import pandas as pd
import yfinance as yf
from pathlib import Path

signals_list = []

# ===== PATH TO PORTFOLIO FILE =====
BASE_DIR = Path(__file__).resolve().parent
PORTFOLIO_FILE = BASE_DIR.parent / "portfolio" / "trades_log.csv"

def get_used_capital():
    try:
        df = pd.read_csv(PORTFOLIO_FILE)
        df = df[df["Status"] == "OPEN"]
        df = df[df["Engine"] == "E1"]

        used = (df["EntryPrice"] * df["Qty"]).sum()
        return used
    except:
        return 0


def run():
    global signals_list
    signals_list = []

    DATA_FILE = BASE_DIR.parent / "data" / "sector_map_fixed.csv"

    stocks = pd.read_csv(DATA_FILE)["Ticker"].drop_duplicates().tolist()

    DROP_DAYS = 2

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

            df["drop"] = df["Close"].pct_change(DROP_DAYS)
            df["ret60"] = df["Close"].pct_change(60)
            df["vol5"] = df["Close"].pct_change().rolling(5).std()

            last = df.iloc[-1]

            rows.append({
                "Ticker": s,
                "drop": last["drop"],
                "ret60": last["ret60"],
                "vol5": last["vol5"],
                "CMP": last["Close"]
            })

        except:
            pass

    df = pd.DataFrame(rows)

    if df.empty:
        print("No data.")
        return

    threshold = df["drop"].quantile(0.10)

    signals = df[
        (df["drop"] <= threshold) &
        (df["ret60"] > 0) &
        (df["vol5"] < 0.08)
    ]

    signals = signals.sort_values("ret60", ascending=False).head(7)

    signals["Target"] = signals["CMP"] * 1.053
    signals["StopLoss"] = signals["CMP"] * 0.97

    print("\nTODAY SIGNALS\n")

    if signals.empty:
        print("No signals today.")
        return

    print(signals[["Ticker","CMP","Target","StopLoss"]])

    # ===== REAL CAPITAL LOGIC =====
    TOTAL_CAPITAL = 175000
    MAX_POSITIONS = 3

    used_capital = get_used_capital()
    remaining_capital = TOTAL_CAPITAL - used_capital

    print(f"\nUsed Capital (E1): ₹{round(used_capital,0)}")
    print(f"Remaining Capital (E1): ₹{round(remaining_capital,0)}")

    if remaining_capital <= 0:
        print("\nNo capital left for E1 trades")
        return

    capital_per_trade = remaining_capital / MAX_POSITIONS

    
    for _, row in signals.iterrows():

        entry = round(row["CMP"], 2)
        qty = int(capital_per_trade // entry)
        capital_used = qty * entry

        if qty <= 0:
            continue

        signals_list.append({
            "Ticker": row["Ticker"],
            "Sector": "E1",
            "Score": 0,
            "Entry": entry,
            "SL": round(row["StopLoss"], 2),
            "SL_pct": "",
            "Partial_Target": round(row["Target"], 2),
            "Partial_pct": "",
            "Full_Target": "",
            "Full_pct": "",
            "Shares": qty,
            "Capital_Used": round(capital_used, 0),
            "Risk_Rs": "",
            "Risk_Pct": "",
            "ADX": "",
            "Vol_Ratio": ""
        })

        
def get_signals():
    run()
    return signals_list


if __name__ == "__main__":
    run()