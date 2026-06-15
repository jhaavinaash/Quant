import pandas as pd
import numpy as np
import yfinance as yf

# ================= CONFIG =================
UNIVERSE_CSV = r"C:/Users/Avinaash/quant_app/sector_map_fixed.csv"

LOOKBACK_YEARS = 3
TOP_N = 5
REBALANCE_DAYS = 14
INITIAL_CAPITAL = 100000
STOP_LOSS = 0.18
COST = 0.003


# ================= LOAD =================
def load_universe(path):
    df = pd.read_csv(path)

    print("Columns in file:", list(df.columns))

    for col in df.columns:
        data = df[col].astype(str)

        if data.str.contains(".NS", regex=False).any():
            print(f"Using column: {col}")
            return data.dropna().tolist()[:100]   # ✅ ONLY CHANGE

    # fallback
    print("Fallback column used:", df.columns[1])
    return df.iloc[:, 1].dropna().astype(str).tolist()[:100]   # ✅ ONLY CHANGE


# ================= FETCH DATA =================
def fetch_data(symbols, start, end):
    data = {}

    for sym in symbols:
        print(sym)
        try:
            df = yf.download(sym, start=start, end=end, progress=False)

            if df.empty:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df[["Open", "High", "Low", "Close"]].copy()
            data[sym] = df

        except:
            continue

    return data


# ================= ALIGN =================
def align_data(data):
    df_list = []

    for sym, df in data.items():
        temp = df[["Close"]].rename(columns={"Close": sym})
        df_list.append(temp)

    combined = pd.concat(df_list, axis=1)
    combined = combined.ffill()

    return combined


# ================= BACKTEST =================
def backtest(price_df, raw_data):

    ret60 = price_df / price_df.shift(60) - 1

    equity = INITIAL_CAPITAL
    equity_curve = []

    dates = price_df.index

    for i in range(60, len(dates) - REBALANCE_DAYS, REBALANCE_DAYS):

        date = dates[i]
        next_date = dates[i + REBALANCE_DAYS]

        scores = ret60.loc[date].dropna()
        scores = scores[scores > 0]   # keep strong stocks

        if len(scores) < TOP_N:
            continue

        top = scores.sort_values(ascending=False).head(TOP_N).index

        returns_list = []

        for sym in top:
            df = raw_data.get(sym)
            if df is None:
                continue

            if date not in df.index or next_date not in df.index:
                continue

            entry_price = df.loc[date]["Close"]
            exit_price = df.loc[next_date]["Close"]

            sl_price = entry_price * (1 - STOP_LOSS)

            window = df.loc[date:next_date]

            if (window["Low"] <= sl_price).any():
                exit_price = sl_price

            ret = (exit_price / entry_price) - 1
            returns_list.append(ret)

        if len(returns_list) == 0:
            continue

        avg_ret = np.mean(returns_list) - COST

        if np.isnan(avg_ret):
            continue

        equity *= (1 + avg_ret)
        equity_curve.append(equity)

    return equity_curve


# ================= MAIN =================
def main():

    end = pd.Timestamp.today()
    start = end - pd.DateOffset(years=LOOKBACK_YEARS)

    symbols = load_universe(UNIVERSE_CSV)
    print("Universe size:", len(symbols))

    raw_data = fetch_data(symbols, start, end)

    print("\nAligning data...")
    price_df = align_data(raw_data)

    print("Running backtest...")
    equity_curve = backtest(price_df, raw_data)

    if len(equity_curve) == 0:
        print("No result")
        return

    final_equity = equity_curve[-1]
    returns = np.diff(equity_curve) / equity_curve[:-1]

    peak = equity_curve[0]
    max_dd = 0

    for eq in equity_curve:
        peak = max(peak, eq)
        dd = (eq - peak) / peak
        max_dd = min(max_dd, dd)

    print("\n===== RESULT =====")
    print("Final Equity:", final_equity)
    print("Avg Period Return:", np.mean(returns))
    print("Win Rate:", np.mean(returns > 0))
    print("Max Drawdown:", max_dd)


if __name__ == "__main__":
    main()