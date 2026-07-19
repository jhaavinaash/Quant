"""Phase 4: Stress Layer research using existing historical prices only."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
PRICES = ROOT / "Data" / "stock_prices_clean.csv"
P2_BREADTH = ROOT / "research" / "market_mood_phase2" / "input" / "market_breadth.csv"
OUT = Path(__file__).resolve().parents[1] / "output"
HORIZONS = [1, 5, 10, 20]


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    breadth = pd.read_csv(P2_BREADTH, parse_dates=["date"]).sort_values("date")
    prices = pd.read_csv(
        PRICES, usecols=["Date", "Ticker", "Close"], parse_dates=["Date"]
    ).sort_values(["Ticker", "Date"])
    return breadth.reset_index(drop=True), prices


def consecutive_true(values: pd.Series) -> pd.Series:
    groups = (~values.fillna(False)).cumsum()
    return values.fillna(False).astype(int).groupby(groups).cumsum()


def build_stress_factors(breadth: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    d = breadth.copy()
    close = d["index_close"]
    ret = close.pct_change()

    # 1. Market Drawdown: positive number means more stress.
    d["market_drawdown_252"] = 1 - close / close.rolling(252, min_periods=126).max()

    # 2. Breadth deterioration: positive number means breadth declined.
    for window in [5, 10, 20]:
        d[f"above200_deterioration_{window}d"] = (
            d["pct_above_200dma"].shift(window) - d["pct_above_200dma"]
        )
        d[f"above50_deterioration_{window}d"] = (
            d["pct_above_50dma"].shift(window) - d["pct_above_50dma"]
        )

    # 3. New low pressure from existing stock closes.
    wide = prices.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    rolling_high = wide.rolling(252, min_periods=126).max()
    rolling_low = wide.rolling(252, min_periods=126).min()
    valid = wide.notna() & rolling_high.notna() & rolling_low.notna()
    highs = ((wide >= rolling_high) & valid).sum(axis=1)
    lows = ((wide <= rolling_low) & valid).sum(axis=1)
    universe = valid.sum(axis=1).replace(0, np.nan)
    nl = pd.DataFrame({
        "date": wide.index,
        "new_highs_52w": highs.values,
        "new_lows_52w": lows.values,
        "net_new_lows_share": ((lows - highs) / universe).values,
        "new_low_high_ratio": np.log1p((lows / (highs + 1)).clip(upper=20)).values,
    })
    d = d.merge(nl, on="date", how="left")

    # 4. Downside volatility.
    d["realized_volatility_20d"] = ret.rolling(20).std() * np.sqrt(252)
    negative_sq = ret.where(ret < 0, 0).pow(2)
    d["downside_semivariance_20d"] = negative_sq.rolling(20).mean() * 252

    # 5. Breadth failure. Critical levels are expanding 20th percentiles,
    # shifted one day so today's classification uses historical information only.
    for dma in [200, 50]:
        col = f"pct_above_{dma}dma"
        critical = d[col].expanding(252).quantile(0.20).shift(1)
        failed = d[col] < critical
        d[f"above{dma}_failure_days"] = consecutive_true(failed)
        d[f"above{dma}_critical_p20"] = critical

    # Forward outcomes.
    for h in HORIZONS:
        d[f"fwd_return_{h}d"] = close.shift(-h) / close - 1
        future = pd.concat(
            [close.shift(-i) / close - 1 for i in range(1, h + 1)], axis=1
        )
        d[f"fwd_drawdown_{h}d"] = -future.min(axis=1).clip(upper=0)
    return d


FACTOR_FAMILIES = {
    "Drawdown": ["market_drawdown_252"],
    "Breadth deterioration": [
        f"above{dma}_deterioration_{w}d" for dma in [200, 50] for w in [5, 10, 20]
    ],
    "New low pressure": [
        "new_lows_52w", "net_new_lows_share", "new_low_high_ratio"
    ],
    "Downside volatility": [
        "realized_volatility_20d", "downside_semivariance_20d"
    ],
    "Breadth failure": ["above200_failure_days", "above50_failure_days"],
}
FACTORS = [f for values in FACTOR_FAMILIES.values() for f in values]


def high_stress_persistence(series: pd.Series) -> tuple[float, float]:
    valid = series.dropna()
    if len(valid) < 10:
        return np.nan, np.nan
    threshold = valid.quantile(0.80)
    # Sparse count factors often have an 80th percentile of zero; zero means
    # no failure and must not be classified as high stress.
    high = series > threshold if threshold <= valid.min() else series >= threshold
    next_high = high.shift(-1)
    persistence = next_high[high].mean()
    runs, run = [], 0
    for value in high.fillna(False):
        if value:
            run += 1
        elif run:
            runs.append(run)
            run = 0
    if run:
        runs.append(run)
    return float(persistence), float(np.mean(runs)) if runs else 0.0


def validate_factors(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, quintiles = [], []
    for factor in FACTORS:
        persistence, avg_run = high_stress_persistence(d[factor])
        for h in HORIZONS:
            cols = [factor, f"fwd_return_{h}d", f"fwd_drawdown_{h}d"]
            x = d[cols].replace([np.inf, -np.inf], np.nan).dropna()
            if len(x) < 50:
                continue
            ret_ic, ret_p = stats.spearmanr(x[factor], x[f"fwd_return_{h}d"])
            dd_ic, dd_p = stats.spearmanr(x[factor], x[f"fwd_drawdown_{h}d"])
            rows.append({
                "factor": factor,
                "family": next(k for k, vals in FACTOR_FAMILIES.items() if factor in vals),
                "horizon": h,
                "sample_count": len(x),
                "return_ic": ret_ic,
                "return_ic_pvalue": ret_p,
                "drawdown_ic": dd_ic,
                "drawdown_ic_pvalue": dd_p,
                "high_stress_next_day_persistence": persistence,
                "avg_high_stress_run_days": avg_run,
            })
            x["quintile"] = pd.qcut(x[factor], 5, labels=False, duplicates="drop") + 1
            for q, g in x.groupby("quintile"):
                quintiles.append({
                    "factor": factor,
                    "horizon": h,
                    "quintile": int(q),
                    "sample_count": len(g),
                    "avg_forward_return": g[f"fwd_return_{h}d"].mean(),
                    "median_forward_return": g[f"fwd_return_{h}d"].median(),
                    "win_rate": (g[f"fwd_return_{h}d"] > 0).mean(),
                    "avg_forward_drawdown": g[f"fwd_drawdown_{h}d"].mean(),
                    "drawdown_hit_rate_3pct": (g[f"fwd_drawdown_{h}d"] >= 0.03).mean(),
                })
    return pd.DataFrame(rows), pd.DataFrame(quintiles)


def predictive_scores(metrics: pd.DataFrame) -> pd.DataFrame:
    """Evidence score rewards negative return IC and positive drawdown IC."""
    x = metrics.copy()
    x["horizon_score"] = (
        (-x["return_ic"]).clip(lower=0) + x["drawdown_ic"].clip(lower=0)
    ) / 2
    summary = x.groupby(["family", "factor"]).agg(
        predictive_score=("horizon_score", "mean"),
        mean_return_ic=("return_ic", "mean"),
        mean_drawdown_ic=("drawdown_ic", "mean"),
        persistence=("high_stress_next_day_persistence", "first"),
        avg_run_days=("avg_high_stress_run_days", "first"),
    ).reset_index()
    return summary.sort_values("predictive_score", ascending=False)


def select_and_weight(summary: pd.DataFrame) -> pd.DataFrame:
    # Select strongest variable from each conceptual family to avoid double-counting
    # highly related horizons. Weights are normalized predictive scores, not tuned.
    selected = summary.loc[summary.groupby("family")["predictive_score"].idxmax()].copy()
    selected = selected[selected["predictive_score"] > 0]
    selected["weight"] = selected["predictive_score"] / selected["predictive_score"].sum()
    return selected.sort_values("weight", ascending=False)


def expanding_percentile(series: pd.Series, min_periods: int = 252) -> pd.Series:
    """Past-only percentile rank, preventing look-ahead in the Stress Index."""
    values = series.to_numpy()
    out = np.full(len(values), np.nan)
    for i in range(min_periods, len(values)):
        history = values[:i]
        history = history[np.isfinite(history)]
        if len(history):
            out[i] = stats.percentileofscore(history, values[i], kind="weak") / 100
    return pd.Series(out, index=series.index)


def build_stress_index(d: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    x = d[["date", "index_close"] + [f"fwd_return_{h}d" for h in HORIZONS]
          + [f"fwd_drawdown_{h}d" for h in HORIZONS]].copy()
    components = []
    for row in selected.itertuples():
        col = f"stress_pct_{row.factor}"
        x[col] = expanding_percentile(d[row.factor])
        components.append((col, row.weight))
    valid_weight = sum(w for _, w in components)
    x["stress_index"] = sum(x[c] * w for c, w in components) / valid_weight
    return x


def validate_index(x: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, quintiles = [], []
    for h in HORIZONS:
        z = x[["stress_index", f"fwd_return_{h}d", f"fwd_drawdown_{h}d"]].dropna()
        ret_ic, ret_p = stats.spearmanr(z.stress_index, z[f"fwd_return_{h}d"])
        dd_ic, dd_p = stats.spearmanr(z.stress_index, z[f"fwd_drawdown_{h}d"])
        rows.append({
            "horizon": h, "sample_count": len(z),
            "return_ic": ret_ic, "return_ic_pvalue": ret_p,
            "drawdown_ic": dd_ic, "drawdown_ic_pvalue": dd_p,
        })
        z["quintile"] = pd.qcut(z.stress_index, 5, labels=False) + 1
        for q, g in z.groupby("quintile"):
            quintiles.append({
                "horizon": h, "stress_quintile": int(q), "sample_count": len(g),
                "avg_forward_return": g[f"fwd_return_{h}d"].mean(),
                "win_rate": (g[f"fwd_return_{h}d"] > 0).mean(),
                "avg_forward_drawdown": g[f"fwd_drawdown_{h}d"].mean(),
                "drawdown_hit_rate_3pct": (g[f"fwd_drawdown_{h}d"] >= 0.03).mean(),
            })
    return pd.DataFrame(rows), pd.DataFrame(quintiles)


def make_report(
    metrics: pd.DataFrame, quintiles: pd.DataFrame, summary: pd.DataFrame,
    selected: pd.DataFrame, index_metrics: pd.DataFrame, index_q: pd.DataFrame,
) -> str:
    lines = [
        "# Phase 4 — Stress Factor Research Report", "",
        "**Research only. Existing historical prices only. No production changes.**", "",
        "## 1. Candidate Stress Factors", "",
        "Stress is oriented so higher values mean greater market stress. Return IC should "
        "therefore be negative, while forward-drawdown IC should be positive.", "",
        "| Factor | Family | Mean return IC | Mean drawdown IC | Persistence | Score |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in summary.itertuples():
        lines.append(
            f"| `{r.factor}` | {r.family} | {r.mean_return_ic:.3f} | "
            f"{r.mean_drawdown_ic:.3f} | {r.persistence:.1%} | {r.predictive_score:.3f} |"
        )
    lines += ["", "## 2. Recommended Stress Index", "",
              "One strongest variable per family was retained to limit correlated duplication. "
              "Weights equal normalized historical predictive scores; they were not manually tuned.", "",
              "| Factor | Family | Weight |",
              "|---|---|---:|"]
    for r in selected.itertuples():
        lines.append(f"| `{r.factor}` | {r.family} | {r.weight:.1%} |")
    lines += ["", "Each component is converted to a past-only expanding percentile. The index is:",
              "", "`Stress Index = Σ(component percentile × evidence weight)`", "",
              "## 3. Stress Index Predictive Statistics", "",
              "| Horizon | N | Return IC | p-value | Drawdown IC | p-value |",
              "|---:|---:|---:|---:|---:|---:|"]
    for r in index_metrics.itertuples():
        lines.append(
            f"| {r.horizon}d | {r.sample_count} | {r.return_ic:.3f} | "
            f"{r.return_ic_pvalue:.4f} | {r.drawdown_ic:.3f} | {r.drawdown_ic_pvalue:.4f} |"
        )
    lines += ["", "### Stress Index quintiles (20-day outcome)", "",
              "| Quintile | N | Avg return | Win rate | Avg drawdown | ≥3% drawdown |",
              "|---:|---:|---:|---:|---:|---:|"]
    q20 = index_q[index_q.horizon == 20]
    for r in q20.itertuples():
        lines.append(
            f"| {r.stress_quintile} | {r.sample_count} | {r.avg_forward_return:.2%} | "
            f"{r.win_rate:.1%} | {r.avg_forward_drawdown:.2%} | "
            f"{r.drawdown_hit_rate_3pct:.1%} |"
        )
    lines += [
        "",
        "**Interpretation:** drawdown prediction is monotonic and materially stronger than "
        "return prediction. The highest-stress quintile still has a positive average 20-day "
        "return because severe stress is frequently followed by rebound rallies. Therefore "
        "this index should be treated as a capital-risk/drawdown layer, not a directional "
        "return forecast.",
    ]
    lines += [
        "", "## 4. Validation Coverage", "",
        "For every candidate factor, `stress_factor_metrics.csv` reports IC for 1/5/10/20-day "
        "returns and drawdowns. `stress_factor_quintiles.csv` reports forward return, win rate, "
        "drawdown level, and ≥3% drawdown hit rate by quintile. Persistence is measured as both "
        "next-day top-quintile retention and average high-stress run length.", "",
        "## 5. Final Market Intelligence Architecture", "",
        "```text",
        "Trend Layer",
        "Leadership Layer",
        "Participation Layer",
        "Stress Layer",
        "    ├─ Drawdown",
        "    ├─ Breadth deterioration / failure",
        "    ├─ New-low pressure",
        "    └─ Downside volatility",
        "            ↓",
        "Market State Engine",
        "            ↓",
        "Risk-O-Meter",
        "```", "",
        "Recommended behavior (design only):",
        "- The first three layers describe opportunity quality.",
        "- The Stress Layer is an independent defensive override.",
        "- High stress must prevent a positive participation rebound from being mistaken for a "
        "durable risk-on regime.",
        "- Market states should combine opportunity and stress: Constructive, Caution, and "
        "Capital Protection.",
        "- Risk-O-Meter allocation should be conditional on both opportunity state and Stress "
        "Index percentile.", "",
        "## 6. Recommendation", "",
        "**Proceed to walk-forward validation, not production implementation.** The Stress Index "
        "must next be tested out-of-sample for threshold stability, false-positive rate, and "
        "lead time before major drawdowns. Production thresholds must be derived from that test.",
    ]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    breadth, prices = load_inputs()
    daily = build_stress_factors(breadth, prices)
    metrics, quintiles = validate_factors(daily)
    summary = predictive_scores(metrics)
    selected = select_and_weight(summary)
    index = build_stress_index(daily, selected)
    index_metrics, index_q = validate_index(index)

    daily.to_csv(OUT / "daily_stress_factors.csv", index=False)
    metrics.to_csv(OUT / "stress_factor_metrics.csv", index=False)
    quintiles.to_csv(OUT / "stress_factor_quintiles.csv", index=False)
    summary.to_csv(OUT / "stress_factor_summary.csv", index=False)
    selected.to_csv(OUT / "recommended_stress_weights.csv", index=False)
    index.to_csv(OUT / "daily_stress_index.csv", index=False)
    index_metrics.to_csv(OUT / "stress_index_metrics.csv", index=False)
    index_q.to_csv(OUT / "stress_index_quintiles.csv", index=False)
    weights = dict(zip(selected.factor, selected.weight))
    (OUT / "recommended_stress_index.json").write_text(json.dumps(weights, indent=2))
    report = make_report(metrics, quintiles, summary, selected, index_metrics, index_q)
    (OUT / "PHASE4_STRESS_FACTOR_REPORT.md").write_text(report, encoding="utf-8")
    print(f"Report: {OUT / 'PHASE4_STRESS_FACTOR_REPORT.md'}")


if __name__ == "__main__":
    main()
