import pandas as pd
import yfinance as yf
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# =====================
# LOAD YOUR STOCK LIST
# =====================
universe = pd.read_csv(BASE_DIR / "sector_map_fixed.csv")
tickers = universe['Ticker'].astype(str).str.strip()

all_data = []

# =====================
# DOWNLOAD USING Ticker (STABLE)
# =====================
for ticker in tickers:
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(start="2018-01-01")

        if df.empty:
            print("No data:", ticker)
            continue

        df = df.reset_index()
        df['Ticker'] = ticker

        df = df[['Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Volume']]

        # clean numbers
        for col in ['Open', 'High', 'Low', 'Close']:
            df[col] = pd.to_numeric(df[col], errors='coerce').round(2)

        all_data.append(df)

        print("Done:", ticker)

    except Exception as e:
        print("Error:", ticker, e)

# =====================
# SAFETY
# =====================
if len(all_data) == 0:
    print("No data downloaded. Check setup.")
    exit()

# =====================
# COMBINE
# =====================
final_df = pd.concat(all_data)
final_df = final_df.sort_values(['Ticker', 'Date'])

# =====================
# SAVE
# =====================
final_df.to_csv(BASE_DIR / "stock_prices_clean.csv", index=False)

print("\nFINAL SUMMARY")
print("Stocks:", final_df['Ticker'].nunique())
print("Last date:", final_df['Date'].max())
