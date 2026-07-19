"""
Build market_breadth.csv from existing stock_prices_clean.csv (research only).

Run once if input/market_breadth.csv is missing.
Does NOT modify any production files.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "Data" / "stock_prices_clean.csv"
OUT = Path(__file__).resolve().parents[1] / "input" / "market_breadth.csv"
UNIVERSE = ROOT / "Data" / "sector_map_fixed.csv"


def _load_prices() -> pd.DataFrame:
    df = pd.read_csv(PRICES, parse_dates=["Date"])
    df = df.sort_values(["Ticker", "Date"])
    return df


def _index_proxy(close_wide: pd.DataFrame) -> pd.Series:
    """Equal-weight universe index close."""
    return close_wide.mean(axis=1)


def build() -> pd.DataFrame:
    prices = _load_prices()
    close = prices.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    volume = prices.pivot(index="Date", columns="Ticker", values="Volume").sort_index()

    rets_1d = close.pct_change()
    rets_20d = close.pct_change(20)

    # Daily breadth
    advances = (rets_1d > 0).sum(axis=1)
    declines = (rets_1d < 0).sum(axis=1)
    unchanged = (rets_1d == 0).sum(axis=1)
    total = advances + declines + unchanged
    pct_positive = advances / total.replace(0, np.nan)
    ad_ratio = advances / declines.replace(0, np.nan)

    # DMA participation
    sma50 = close.rolling(50).mean()
    pct_above_50dma = (close > sma50).sum(axis=1) / close.notna().sum(axis=1)
    sma200 = close.rolling(200).mean()
    pct_above_200dma = (close > sma200).sum(axis=1) / close.notna().sum(axis=1)

    # New highs / lows (20d)
    roll_high = close.rolling(20).max()
    roll_low = close.rolling(20).min()
    new_highs_20d = (close >= roll_high).sum(axis=1)
    new_lows_20d = (close <= roll_low).sum(axis=1)

    # Quintile leadership (cross-sectional 20d return)
    def _quintile_spread(row: pd.Series) -> float:
        valid = row.dropna()
        if len(valid) < 20:
            return np.nan
        q80 = valid.quantile(0.8)
        q20 = valid.quantile(0.2)
        return float(q80 - q20)

    quintile_spread_20d = rets_20d.apply(_quintile_spread, axis=1)
    pct_return_above_5pct_20d = (rets_20d > 0.05).sum(axis=1) / rets_20d.notna().sum(axis=1)

    # Volume participation
    up_vol = volume.where(rets_1d > 0, 0).sum(axis=1)
    down_vol = volume.where(rets_1d < 0, 0).sum(axis=1)
    vol_total = up_vol + down_vol
    up_volume_share = up_vol / vol_total.replace(0, np.nan)

    index_close = _index_proxy(close)
    index_sma_50 = index_close.rolling(50).mean()
    index_sma_200 = index_close.rolling(200).mean()
    index_return_20d = index_close.pct_change(20)

    out = pd.DataFrame({
        "date": close.index,
        "index_close": index_close.values,
        "index_sma_50": index_sma_50.values,
        "index_sma_200": index_sma_200.values,
        "index_return_20d": index_return_20d.values,
        "advances": advances.values,
        "declines": declines.values,
        "unchanged": unchanged.values,
        "pct_positive": pct_positive.values,
        "ad_ratio": ad_ratio.values,
        "pct_above_50dma": pct_above_50dma.values,
        "pct_above_200dma": pct_above_200dma.values,
        "new_highs_20d": new_highs_20d.values,
        "new_lows_20d": new_lows_20d.values,
        "top_quintile_return_20d": rets_20d.apply(lambda r: r.quantile(0.8), axis=1).values,
        "bottom_quintile_return_20d": rets_20d.apply(lambda r: r.quantile(0.2), axis=1).values,
        "quintile_spread_20d": quintile_spread_20d.values,
        "pct_return_above_5pct_20d": pct_return_above_5pct_20d.values,
        "up_volume_share": up_volume_share.values,
    })
    out = out.dropna(subset=["index_close"]).reset_index(drop=True)
    return out


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        print(f"Already exists (not overwriting): {OUT}")
        return
    df = build()
    df.to_csv(OUT, index=False)
    print(f"Wrote {len(df)} rows -> {OUT}")


if __name__ == "__main__":
    main()
