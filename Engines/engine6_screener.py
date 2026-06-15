from E6_rotation_100 import load_universe, fetch_data, align_data
import pandas as pd
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent

TOP_N = 5

def get_signals():
    end = pd.Timestamp.today()
    start = end - pd.DateOffset(months=6)

    symbols = load_universe(
        str(BASE_DIR.parent / "data" / "sector_map_fixed.csv")
    )
    symbols = symbols[:100]   # enforce top 100 (align with backtest)
    raw_data = fetch_data(symbols, start, end)
    price_df = align_data(raw_data)

    ret60 = price_df / price_df.shift(60) - 1
    print("Price DF shape:", price_df.shape)
    print("Last date:", price_df.index[-1])
    
    latest = price_df.index[-1]
    scores = ret60.loc[latest].dropna()
    scores = scores.dropna()
    print("Scores count:", len(scores))
    print(scores.sort_values(ascending=False).head(10))
    print("Price DF shape:", price_df.shape)
    top = scores.sort_values(ascending=False).head(TOP_N).index

    signals = []

    for sym in top:
        price = float(price_df.loc[latest, sym])

        signals.append({
            "Ticker": sym,
            "Entry": round(price, 2),
            "SL": round(price * 0.97, 2)   # 3% SL (align with your style)
        })

    return signals

if __name__ == "__main__":
    signals = get_signals()

    print("\n===== E6 SIGNALS =====")

    for s in signals:
        print(s)