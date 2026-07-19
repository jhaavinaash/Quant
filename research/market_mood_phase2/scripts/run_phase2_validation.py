"""
Market Mood Phase 2 — Factor validation research (standalone).

Reads:  research/market_mood_phase2/input/market_breadth.csv
Writes: research/market_mood_phase2/output/

Does NOT modify production code or CSVs.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

BASE = Path(__file__).resolve().parents[1]
INPUT = BASE / "input" / "market_breadth.csv"
OUTPUT = BASE / "output"
HORIZONS = [1, 3, 5, 10, 20]

FACTORS = {
    "trend_regime": "Trend Regime",
    "relative_leadership": "Relative Leadership",
    "participation_impulse": "Participation Impulse",
}


def load_breadth() -> pd.DataFrame:
    if not INPUT.exists():
        raise FileNotFoundError(
            f"{INPUT} not found. Place market_breadth.csv there or run "
            "scripts/build_market_breadth.py (research only)."
        )
    df = pd.read_csv(INPUT, parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


def compute_v2_factors(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["index_vs_50dma"] = d["index_close"] / d["index_sma_50"] - 1
    d["index_vs_200dma"] = d["index_close"] / d["index_sma_200"] - 1
    d["nh_nl_ratio"] = d["new_highs_20d"] / (d["new_highs_20d"] + d["new_lows_20d"] + 1)

    d["delta_pct_above_50dma_5d"] = d["pct_above_50dma"] - d["pct_above_50dma"].shift(5)
    d["delta_ad_ratio_3d"] = d["ad_ratio"] - d["ad_ratio"].shift(3)

    d["trend_regime"] = (
        0.35 * d["index_vs_50dma"]
        + 0.25 * d["index_vs_200dma"]
        + 0.25 * d["index_return_20d"]
        + 0.15 * (d["pct_above_50dma"] - 0.5)
    )
    d["relative_leadership"] = (
        0.45 * d["quintile_spread_20d"]
        + 0.35 * d["nh_nl_ratio"]
        + 0.20 * (d["pct_return_above_5pct_20d"] - 0.5)
    )
    d["participation_impulse"] = (
        0.40 * d["delta_pct_above_50dma_5d"]
        + 0.30 * d["delta_ad_ratio_3d"]
        + 0.20 * (d["pct_positive"] - 0.5)
        + 0.10 * (d["up_volume_share"] - 0.5)
    )
    return d


def compute_forward_returns(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for h in HORIZONS:
        d[f"fwd_return_{h}d"] = d["index_close"].shift(-h) / d["index_close"] - 1
    return d


def quintile_analysis(series: pd.Series, forward: pd.Series) -> pd.DataFrame:
    valid = pd.DataFrame({"factor": series, "fwd": forward}).dropna()
    if valid.empty:
        return pd.DataFrame()
    valid["quintile"] = pd.qcut(valid["factor"], 5, labels=False, duplicates="drop") + 1
    rows = []
    for q, grp in valid.groupby("quintile"):
        rows.append({
            "quintile": int(q),
            "count": len(grp),
            "avg_forward_return": grp["fwd"].mean(),
            "median_forward_return": grp["fwd"].median(),
            "win_rate": (grp["fwd"] > 0).mean(),
        })
    out = pd.DataFrame(rows).sort_values("quintile")
    if len(out) >= 2:
        out["monotonicity"] = out["avg_forward_return"].diff().dropna().ge(0).mean()
    return out


def monotonicity_score(quint_df: pd.DataFrame) -> float:
    if quint_df.empty or len(quint_df) < 2:
        return float("nan")
    rets = quint_df.sort_values("quintile")["avg_forward_return"].values
    diffs = np.diff(rets)
    return float(np.mean(diffs >= 0))


def factor_metrics(df: pd.DataFrame, factor_col: str, horizon: int) -> dict:
    fwd = f"fwd_return_{horizon}d"
    valid = df[[factor_col, fwd]].dropna()
    if len(valid) < 30:
        return {"n": len(valid), "note": "insufficient data"}

    pearson_r, pearson_p = stats.pearsonr(valid[factor_col], valid[fwd])
    spearman_r, spearman_p = stats.spearmanr(valid[factor_col], valid[fwd])
    quint = quintile_analysis(valid[factor_col], valid[fwd])

    return {
        "n": len(valid),
        "pearson_r": pearson_r,
        "pearson_p": pearson_p,
        "spearman_r": spearman_r,
        "spearman_p": spearman_p,
        "ic": spearman_r,
        "quintile_spread_q5_q1": (
            quint.loc[quint["quintile"] == quint["quintile"].max(), "avg_forward_return"].iloc[0]
            - quint.loc[quint["quintile"] == quint["quintile"].min(), "avg_forward_return"].iloc[0]
        ) if not quint.empty else np.nan,
        "monotonicity": monotonicity_score(quint),
        "quintiles": quint.to_dict(orient="records"),
    }


def interaction_analysis(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    fwd = f"fwd_return_{horizon}d"
    d = df.dropna(subset=["trend_regime", "relative_leadership", "participation_impulse", fwd]).copy()
    t_med = d["trend_regime"].median()
    p_med = d["participation_impulse"].median()
    l_med = d["relative_leadership"].median()

    def _bucket(row) -> str:
        high_t = row["trend_regime"] >= t_med
        high_p = row["participation_impulse"] >= p_med
        high_l = row["relative_leadership"] >= l_med
        if high_t and high_p:
            return "High Trend + High Participation"
        if high_t and not high_p:
            return "High Trend + Weak Participation"
        if not high_t and high_p:
            return "Weak Trend + Strong Participation"
        if high_l and not high_t:
            return "Strong Leadership + Weak Trend"
        if high_t:
            return "High Trend (other)"
        if high_p:
            return "High Participation (other)"
        return "Low Trend + Low Participation"

    d["combo"] = d.apply(_bucket, axis=1)
    rows = []
    for combo, grp in d.groupby("combo"):
        rows.append({
            "combination": combo,
            "horizon_days": horizon,
            "count": len(grp),
            "avg_forward_return": grp[fwd].mean(),
            "median_forward_return": grp[fwd].median(),
            "win_rate": (grp[fwd] > 0).mean(),
            "spearman_ic_vs_fwd": stats.spearmanr(grp["participation_impulse"], grp[fwd])[0]
            if len(grp) > 10 else np.nan,
        })
    return pd.DataFrame(rows).sort_values("avg_forward_return", ascending=False)


def recommend_weights(summary: pd.DataFrame) -> dict:
    """Evidence-based weight suggestion from mean |IC| across horizons."""
    weights = {}
    for factor in FACTORS:
        sub = summary[summary["factor"] == factor]
        weights[factor] = sub["ic"].abs().mean()
    total = sum(weights.values()) or 1
    norm = {k: round(v / total, 3) for k, v in weights.items()}
    return norm


def generate_report(
    df: pd.DataFrame,
    factor_results: list[dict],
    interactions: pd.DataFrame,
    weights: dict,
) -> str:
    summary = pd.DataFrame(factor_results)
    lines = [
        "# Market Mood Phase 2 — Research Report",
        "",
        "**Status:** Research only. No production changes.",
        "",
        f"**Sample:** {len(df)} trading days",
        f"**Date range:** {df['date'].min().date()} → {df['date'].max().date()}",
        "",
        "---",
        "",
        "## 1. Predictive Power by Factor",
        "",
    ]

    for factor, label in FACTORS.items():
        lines.append(f"### {label} (`{factor}`)")
        lines.append("")
        lines.append("| Horizon | Pearson r | Spearman r | IC | Monotonicity | Q5−Q1 spread |")
        lines.append("|---------|-----------|------------|-----|--------------|--------------|")
        sub = summary[summary["factor"] == factor]
        for _, r in sub.iterrows():
            lines.append(
                f"| {int(r['horizon'])}d | {r['pearson_r']:.4f} | {r['spearman_r']:.4f} | "
                f"{r['ic']:.4f} | {r['monotonicity']:.2f} | {r['quintile_spread_q5_q1']:.4%} |"
            )
        lines.append("")

    lines += ["---", "", "## 2. Factor Combinations (10-day horizon)", ""]
    i10 = interactions[interactions["horizon_days"] == 10]
    lines.append("| Combination | Days | Avg Fwd Return | Win Rate |")
    lines.append("|-------------|------|----------------|----------|")
    for _, r in i10.iterrows():
        lines.append(
            f"| {r['combination']} | {int(r['count'])} | {r['avg_forward_return']:.4%} | {r['win_rate']:.1%} |"
        )

    lines += ["", "---", "", "## 3. Recommended Factor Weights (evidence-based)", ""]
    for k, w in weights.items():
        lines.append(f"- **{FACTORS[k]}:** {w:.1%}")
    lines.append("")

    # Remove / increase recommendations
    avg_ic = summary.groupby("factor")["ic"].mean()
    lines += ["---", "", "## 4. Factors to Remove", ""]
    weak = avg_ic[avg_ic.abs() < 0.02].index.tolist()
    if weak:
        for f in weak:
            lines.append(f"- **{FACTORS[f]}** — mean IC {avg_ic[f]:.4f} (weak)")
    else:
        lines.append("- None meet removal threshold (|mean IC| < 0.02).")

    lines += ["", "## 5. Factors Deserving Higher Weight", ""]
    strong = avg_ic.abs().sort_values(ascending=False)
    for f in strong.index[:2]:
        lines.append(f"- **{FACTORS[f]}** — strongest mean IC ({avg_ic[f]:.4f})")

    lines += ["", "---", "", "## 6. Final Recommendation", ""]
    best_ic = avg_ic.abs().max()
    best_combo = i10.iloc[0]["combination"] if not i10.empty else "N/A"
    combo_edge = (
        i10.iloc[0]["avg_forward_return"] - i10.iloc[-1]["avg_forward_return"]
        if len(i10) >= 2 else 0
    )

    if best_ic >= 0.05 and combo_edge > 0.002:
        rec = "**Proceed to implementation** with modified weights (see Section 3). "
        rec += "Validate combinations in paper trading before production."
    elif best_ic >= 0.02:
        rec = "**Modify architecture** — factors show marginal signal; "
        rec += "refine Participation Impulse and interaction rules before full implementation."
    else:
        rec = "**Reject architecture** — insufficient predictive power at proposed V2 definitions."

    lines.append(rec)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Generated by `scripts/run_phase2_validation.py`*")
    return "\n".join(lines)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    df = load_breadth()
    df = compute_v2_factors(df)
    df = compute_forward_returns(df)

    df.to_csv(OUTPUT / "daily_factors_and_returns.csv", index=False)

    factor_results = []
    quintile_tables = []
    for factor_col, label in FACTORS.items():
        for h in HORIZONS:
            m = factor_metrics(df, factor_col, h)
            m.update({"factor": factor_col, "factor_label": label, "horizon": h})
            factor_results.append({k: v for k, v in m.items() if k != "quintiles"})
            if "quintiles" in m:
                for q in m["quintiles"]:
                    quintile_tables.append({
                        "factor": factor_col,
                        "horizon": h,
                        **q,
                    })

    summary_df = pd.DataFrame(factor_results)
    summary_df.to_csv(OUTPUT / "factor_correlations.csv", index=False)
    pd.DataFrame(quintile_tables).to_csv(OUTPUT / "quintile_analysis.csv", index=False)

    all_interactions = []
    for h in HORIZONS:
        all_interactions.append(interaction_analysis(df, h))
    interactions_df = pd.concat(all_interactions, ignore_index=True)
    interactions_df.to_csv(OUTPUT / "interaction_analysis.csv", index=False)

    weights = recommend_weights(summary_df)
    with open(OUTPUT / "recommended_weights.json", "w") as f:
        json.dump(weights, f, indent=2)

    report = generate_report(df, factor_results, interactions_df, weights)
    (OUTPUT / "MARKET_MOOD_PHASE2_REPORT.md").write_text(report, encoding="utf-8")

    print(f"Report: {OUTPUT / 'MARKET_MOOD_PHASE2_REPORT.md'}")
    print(f"Rows analyzed: {len(df.dropna(subset=['fwd_return_5d']))}")


if __name__ == "__main__":
    main()
