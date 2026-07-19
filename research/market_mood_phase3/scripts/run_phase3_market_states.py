"""
Market Mood Phase 3 — Market State Engine research (standalone).

Inputs:  Phase 2 daily factor outputs only
Outputs: research/market_mood_phase3/output/

Does NOT modify production code or data files.
"""
from __future__ import annotations

import json
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parents[1]
PHASE2 = Path(__file__).resolve().parents[2] / "market_mood_phase2" / "output" / "daily_factors_and_returns.csv"
OUTPUT = BASE / "output"

FACTORS = ["trend_regime", "relative_leadership", "participation_impulse"]
FACTOR_LABELS = {
    "trend_regime": "Trend Regime",
    "relative_leadership": "Relative Leadership",
    "participation_impulse": "Participation Impulse",
}
HORIZONS = [1, 5, 10, 20]
LEVELS = ["LOW", "MEDIUM", "HIGH"]


def load_phase2() -> pd.DataFrame:
    df = pd.read_csv(PHASE2, parse_dates=["date"])
    cols = ["date", "index_close"] + FACTORS + [f"fwd_return_{h}d" for h in HORIZONS]
    df = df[cols].dropna(subset=FACTORS).copy()
    return df.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Task 1 — Natural boundaries
# ---------------------------------------------------------------------------

def distribution_summary(series: pd.Series) -> dict:
    return {
        "mean": float(series.mean()),
        "std": float(series.std()),
        "p10": float(series.quantile(0.10)),
        "p25": float(series.quantile(0.25)),
        "p33": float(series.quantile(0.33)),
        "p50": float(series.quantile(0.50)),
        "p67": float(series.quantile(0.67)),
        "p75": float(series.quantile(0.75)),
        "p90": float(series.quantile(0.90)),
        "skew": float(series.skew()),
        "kurtosis": float(series.kurtosis()),
    }


def evaluate_boundary_separation(df: pd.DataFrame, factor: str, low_cut: float, high_cut: float) -> float:
    """Score boundary quality: spread in 10d forward return between HIGH and LOW buckets."""
    bucket = pd.cut(
        df[factor],
        bins=[-np.inf, low_cut, high_cut, np.inf],
        labels=["LOW", "MEDIUM", "HIGH"],
    )
    tmp = df.assign(bucket=bucket).dropna(subset=["bucket", "fwd_return_10d"])
    if tmp["bucket"].nunique() < 2:
        return 0.0
    grp = tmp.groupby("bucket", observed=True)["fwd_return_10d"].mean()
    if "HIGH" in grp.index and "LOW" in grp.index:
        return float(grp["HIGH"] - grp["LOW"])
    return 0.0


def recommend_boundaries(df: pd.DataFrame) -> dict:
    """Percentile-based boundaries with separation check vs tertile alternative."""
    results = {}
    for f in FACTORS:
        dist = distribution_summary(df[f])
        # Primary: tertile cuts (33/67) — natural LOW/MED/HIGH
        p33, p67 = dist["p33"], dist["p67"]
        # Alternative: quartile-style inner band (25/75) for wider MEDIUM
        p25, p75 = dist["p25"], dist["p75"]

        sep_tertile = evaluate_boundary_separation(df, f, p33, p67)
        sep_quartile = evaluate_boundary_separation(df, f, p25, p75)

        if sep_quartile > sep_tertile * 1.05:
            low_cut, high_cut = p25, p75
            method = "33/67 rejected; 25/75 percentile cuts maximize 10d return separation"
        else:
            low_cut, high_cut = p33, p67
            method = "33/67 percentile tertiles (data-driven natural thirds)"

        results[f] = {
            "distribution": dist,
            "low_boundary": low_cut,
            "high_boundary": high_cut,
            "method": method,
            "rules": {
                "LOW": f"value <= {low_cut:.6f}",
                "MEDIUM": f"{low_cut:.6f} < value <= {high_cut:.6f}",
                "HIGH": f"value > {high_cut:.6f}",
            },
        }
    return results


def assign_level(value: float, low: float, high: float) -> str:
    if value <= low:
        return "LOW"
    if value <= high:
        return "MEDIUM"
    return "HIGH"


def label_factors(df: pd.DataFrame, boundaries: dict) -> pd.DataFrame:
    d = df.copy()
    for f in FACTORS:
        low = boundaries[f]["low_boundary"]
        high = boundaries[f]["high_boundary"]
        d[f"{f}_level"] = d[f].apply(lambda v: assign_level(v, low, high))
    d["combo_label"] = (
        d["trend_regime_level"] + " Trend + "
        + d["relative_leadership_level"] + " Leadership + "
        + d["participation_impulse_level"] + " Participation"
    )
    return d


# ---------------------------------------------------------------------------
# Task 2 — Combination statistics
# ---------------------------------------------------------------------------

def max_forward_drawdown(index: pd.Series, start_idx: int, window: int = 20) -> float:
    """Max peak-to-trough decline over next `window` days from start_idx."""
    segment = index.iloc[start_idx : start_idx + window + 1]
    if len(segment) < 2:
        return np.nan
    peak = segment.iloc[0]
    max_dd = 0.0
    for price in segment.iloc[1:]:
        peak = max(peak, price)
        dd = (price / peak) - 1
        max_dd = min(max_dd, dd)
    return float(max_dd)


def combination_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    index = df["index_close"].reset_index(drop=True)
    for combo, grp in df.groupby("combo_label"):
        idx_positions = grp.index.tolist()
        dds = []
        for i in idx_positions:
            pos = df.index.get_loc(i)
            if pos + 1 < len(df):
                dds.append(max_forward_drawdown(index, pos, window=20))
        row = {
            "combination": combo,
            "sample_count": len(grp),
            "frequency_pct": len(grp) / len(df) * 100,
            "win_rate_1d": (grp["fwd_return_1d"] > 0).mean(),
            "win_rate_5d": (grp["fwd_return_5d"] > 0).mean(),
            "win_rate_10d": (grp["fwd_return_10d"] > 0).mean(),
            "win_rate_20d": (grp["fwd_return_20d"] > 0).mean(),
            "avg_return_1d": grp["fwd_return_1d"].mean(),
            "avg_return_5d": grp["fwd_return_5d"].mean(),
            "avg_return_10d": grp["fwd_return_10d"].mean(),
            "avg_return_20d": grp["fwd_return_20d"].mean(),
            "median_return_1d": grp["fwd_return_1d"].median(),
            "median_return_5d": grp["fwd_return_5d"].median(),
            "median_return_10d": grp["fwd_return_10d"].median(),
            "median_return_20d": grp["fwd_return_20d"].median(),
            "avg_max_drawdown_20d": np.nanmean(dds) if dds else np.nan,
        }
        # Parse levels for filtering
        parts = combo.split(" + ")
        row["trend_level"] = parts[0].replace(" Trend", "")
        row["leadership_level"] = parts[1].replace(" Leadership", "")
        row["participation_level"] = parts[2].replace(" Participation", "")
        rows.append(row)
    return pd.DataFrame(rows).sort_values("avg_return_10d", ascending=False)


# ---------------------------------------------------------------------------
# Task 3 — Discover market states via clustering
# ---------------------------------------------------------------------------

def score_k_range(matrix: np.ndarray, k_min: int = 3, k_max: int = 8) -> pd.DataFrame:
    rows = []
    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=20)
        labels = km.fit_predict(matrix)
        sil = silhouette_score(matrix, labels) if k > 1 else np.nan
        rows.append({"k": k, "silhouette": sil, "inertia": km.inertia_})
    return pd.DataFrame(rows)


def choose_k(scores: pd.DataFrame) -> int:
    best = scores.loc[scores["silhouette"].idxmax(), "k"]
    return int(best)


def name_state(row: pd.Series) -> str:
    """Data-driven naming from average factor levels in cluster."""
    t = row["trend_regime"]
    l = row["relative_leadership"]
    p = row["participation_impulse"]
    score = t + l + p
    if score >= 0.75 and t > 0.25 and p > 0:
        return "Highway"
    if score >= 0.35 and l > 0:
        return "City"
    if t < -0.1 and p < 0:
        return "Bad Roads"
    if abs(t) < 0.15 and p < -0.05:
        return "Fog"
    if score < -0.2:
        return "Bad Roads"
    if t > 0.15 and p < 0:
        return "Caution Zone"
    return "Mixed Terrain"


def discover_states(df: pd.DataFrame, combo_stats: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Cluster combination profiles (avg factor z-scores + forward return profile)."""
    combo_factors = df.groupby("combo_label")[FACTORS].mean().reset_index()
    combo_factors = combo_factors.rename(columns={"combo_label": "combination"})
    usable = combo_stats.merge(combo_factors, on="combination", how="left")
    usable = usable[usable["sample_count"] >= 5].copy()
    if len(usable) < 6:
        usable = combo_stats.merge(combo_factors, on="combination", how="left")

    feat_cols = FACTORS + ["avg_return_5d", "avg_return_10d", "win_rate_10d"]

    X = usable[feat_cols].fillna(0).values
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    k_scores = score_k_range(Xs, 3, min(8, len(usable) - 1))
    k = choose_k(k_scores)
    k = max(3, min(k, 6))  # practical range for driving metaphor

    km = KMeans(n_clusters=k, random_state=42, n_init=30)
    usable["cluster"] = km.fit_predict(Xs)

    # Centroids in original combo feature space
    centroids = usable.groupby("cluster")[FACTORS].mean()
    centroids["state_name"] = centroids.apply(name_state, axis=1)

    # Resolve duplicate names
    name_counts: dict[str, int] = {}
    final_names = []
    for _, r in centroids.iterrows():
        base = r["state_name"]
        name_counts[base] = name_counts.get(base, 0) + 1
        final_names.append(base if name_counts[base] == 1 else f"{base} {name_counts[base]}")
    centroids["state_name"] = final_names

    usable = usable.merge(
        centroids[["state_name"]].reset_index(),
        on="cluster",
        how="left",
    )
    return usable, k, k_scores, centroids


def map_daily_states(df: pd.DataFrame, combo_to_state: dict, centroids: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["market_state"] = d["combo_label"].map(combo_to_state)

    # Assign rare combinations to nearest cluster centroid
    centroid_factors = centroids[FACTORS].values
    state_names = centroids["state_name"].tolist()
    missing = d["market_state"].isna()
    if missing.any():
        for idx in d.index[missing]:
            row = d.loc[idx, FACTORS].values.astype(float)
            dists = np.linalg.norm(centroid_factors - row, axis=1)
            d.at[idx, "market_state"] = state_names[int(np.argmin(dists))]

    return d


# ---------------------------------------------------------------------------
# Task 4 — State statistics, transitions, duration
# ---------------------------------------------------------------------------

def state_statistics(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for state, grp in daily.groupby("market_state"):
        rets_1d = grp["fwd_return_1d"].dropna()
        rets_5d = grp["fwd_return_5d"].dropna()
        rets_10d = grp["fwd_return_10d"].dropna()
        rets_20d = grp["fwd_return_20d"].dropna()
        vol = rets_1d.std() * np.sqrt(252) if len(rets_1d) > 1 else np.nan
        # Confidence: function of sample size and IC stability
        n = len(grp)
        ic = stats.spearmanr(grp[FACTORS].mean(axis=1), grp["fwd_return_10d"])[0] if n > 20 else np.nan
        confidence = min(0.95, 0.5 + np.log1p(n) / 20 + (abs(ic) if pd.notna(ic) else 0) * 0.3)

        rows.append({
            "market_state": state,
            "sample_count": n,
            "frequency_pct": n / len(daily) * 100,
            "expected_return_1d": rets_1d.mean(),
            "expected_return_5d": rets_5d.mean(),
            "expected_return_10d": rets_10d.mean(),
            "expected_return_20d": rets_20d.mean(),
            "expected_win_rate_1d": (rets_1d > 0).mean(),
            "expected_win_rate_5d": (rets_5d > 0).mean(),
            "expected_win_rate_10d": (rets_10d > 0).mean(),
            "expected_win_rate_20d": (rets_20d > 0).mean(),
            "expected_volatility_ann": vol,
            "confidence": confidence,
        })
    return pd.DataFrame(rows).sort_values("expected_return_10d", ascending=False)


def transition_matrix(daily: pd.DataFrame) -> pd.DataFrame:
    states = sorted(daily["market_state"].unique())
    idx = {s: i for i, s in enumerate(states)}
    mat = np.zeros((len(states), len(states)))
    s = daily["market_state"].values
    for i in range(len(s) - 1):
        mat[idx[s[i]], idx[s[i + 1]]] += 1
    # Normalize rows
    row_sums = mat.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    prob = mat / row_sums
    out = pd.DataFrame(prob, index=states, columns=states)
    out.index.name = "from_state"
    return out


def state_durations(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for state in daily["market_state"].unique():
        runs = []
        current = None
        length = 0
        for s in daily["market_state"]:
            if s == current:
                length += 1
            else:
                if current == state and length > 0:
                    runs.append(length)
                current = s
                length = 1 if s == state else 0
        if current == state and length > 0:
            runs.append(length)
        rows.append({
            "market_state": state,
            "avg_duration_days": np.mean(runs) if runs else np.nan,
            "median_duration_days": np.median(runs) if runs else np.nan,
            "max_duration_days": max(runs) if runs else np.nan,
            "episodes": len(runs),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Task 5 — Risk-O-Meter recommendations
# ---------------------------------------------------------------------------

def risk_o_meter_recommendations(state_stats: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in state_stats.iterrows():
        ret10 = r["expected_return_10d"]
        wr10 = r["expected_win_rate_10d"]
        vol = r["expected_volatility_ann"]
        conf = r["confidence"]

        if ret10 >= 0.008 and wr10 >= 0.65 and vol < 0.25:
            action = "Increase allocation"
            detail = "Favorable expected return and win rate with contained volatility."
        elif ret10 >= 0.004 and wr10 >= 0.58:
            action = "Normal allocation"
            detail = "Constructive environment; standard risk budget appropriate."
        elif ret10 >= 0.0 and wr10 >= 0.52:
            action = "Reduced allocation"
            detail = "Marginal edge; tighten position sizing and raise selectivity."
        else:
            action = "Capital protection"
            detail = "Weak or negative expectancy; prioritize defense and cash."

        rows.append({
            "market_state": r["market_state"],
            "risk_o_meter_action": action,
            "rationale": detail,
            "confidence": conf,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def generate_report(
    boundaries: dict,
    combo_stats: pd.DataFrame,
    state_stats: pd.DataFrame,
    transitions: pd.DataFrame,
    durations: pd.DataFrame,
    risk_rec: pd.DataFrame,
    k_chosen: int,
    k_scores: pd.DataFrame,
    centroids: pd.DataFrame,
) -> str:
    lines = [
        "# Market Mood Phase 3 — Market State Engine Research Report",
        "",
        "**Status:** Research only. No production implementation.",
        "",
        "---",
        "",
        "## 1. Recommended Factor Boundaries (LOW / MEDIUM / HIGH)",
        "",
        "Boundaries derived from historical distributions (percentile analysis) ",
        "and validated by 10-day forward-return separation between HIGH and LOW buckets.",
        "",
    ]
    for f in FACTORS:
        b = boundaries[f]
        lines += [
            f"### {FACTOR_LABELS[f]}",
            "",
            f"- **Method:** {b['method']}",
            f"- **LOW:** {b['rules']['LOW']}",
            f"- **MEDIUM:** {b['rules']['MEDIUM']}",
            f"- **HIGH:** {b['rules']['HIGH']}",
            f"- Distribution: mean={b['distribution']['mean']:.4f}, "
            f"std={b['distribution']['std']:.4f}, "
            f"median={b['distribution']['p50']:.4f}",
            "",
        ]

    lines += ["---", "", "## 2. Market State Definitions", ""]
    lines.append(f"**Clusters discovered:** {k_chosen} (silhouette-optimal in range 3–8)")
    lines.append("")
    for _, c in centroids.reset_index().iterrows():
        lines.append(
            f"- **{c['state_name']}** (cluster {int(c['cluster'])}): "
            f"avg Trend={c['trend_regime']:.3f}, "
            f"Leadership={c['relative_leadership']:.3f}, "
            f"Participation={c['participation_impulse']:.3f}"
        )
    lines.append("")

    lines += ["---", "", "## 3. Historical Statistics by Market State", ""]
    lines.append("| State | Days | Freq% | E[R 10d] | Win% 10d | Vol (ann) | Confidence |")
    lines.append("|-------|------|-------|----------|----------|-----------|------------|")
    for _, r in state_stats.iterrows():
        lines.append(
            f"| {r['market_state']} | {int(r['sample_count'])} | {r['frequency_pct']:.1f}% | "
            f"{r['expected_return_10d']:.3%} | {r['expected_win_rate_10d']:.1%} | "
            f"{r['expected_volatility_ann']:.2%} | {r['confidence']:.2f} |"
        )
    lines.append("")

    lines += ["---", "", "## 4. Top Factor Combinations (by 10d return)", ""]
    top = combo_stats.head(8)
    lines.append("| Combination | N | Avg 10d | Win% 10d | Avg MDD 20d |")
    lines.append("|-------------|---|---------|----------|-------------|")
    for _, r in top.iterrows():
        lines.append(
            f"| {r['combination']} | {int(r['sample_count'])} | "
            f"{r['avg_return_10d']:.3%} | {r['win_rate_10d']:.1%} | "
            f"{r['avg_max_drawdown_20d']:.2%} |"
        )
    lines.append("")

    lines += ["---", "", "## 5. Transition Frequencies (daily)", ""]
    lines.append("| From → To | " + " | ".join(transitions.columns) + " |")
    lines.append("|" + "---|" * (len(transitions.columns) + 1))
    for from_state, row in transitions.iterrows():
        cells = " | ".join(f"{v:.2f}" for v in row.values)
        lines.append(f"| {from_state} | {cells} |")
    lines.append("")
    lines += ["---", "", "## 6. Average Duration in Each State", ""]
    lines.append("| State | Avg days | Median days | Max days | Episodes |")
    lines.append("|-------|----------|-------------|----------|----------|")
    for _, r in durations.iterrows():
        lines.append(
            f"| {r['market_state']} | {r['avg_duration_days']:.1f} | "
            f"{r['median_duration_days']:.1f} | {int(r['max_duration_days'])} | "
            f"{int(r['episodes'])} |"
        )
    lines.append("")

    lines += ["---", "", "## 7. Risk-O-Meter Response (recommendation only)", ""]
    for _, r in risk_rec.iterrows():
        lines.append(f"- **{r['market_state']}** → **{r['risk_o_meter_action']}**: {r['rationale']}")
    lines.append("")

    lines += ["---", "", "## 8. Production Implementation Recommendation", ""]
    best = state_stats.iloc[0]
    worst = state_stats.iloc[-1]
    spread = best["expected_return_10d"] - worst["expected_return_10d"]
    if spread > 0.005 and k_chosen >= 3:
        lines.append(
            "**Proceed to implementation** with data-derived percentile boundaries and "
            f"{k_chosen} learned market states. Replace manual Driving Mode thresholds with "
            "the boundaries in Section 1. Map daily factor levels → combination → market state. "
            "Apply Risk-O-Meter actions from Section 7. Paper-trade state transitions for 4–6 weeks."
        )
    else:
        lines.append(
            "**Modify architecture** — state separation insufficient. "
            "Consider fewer states or refined factor definitions before production."
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Generated by `scripts/run_phase3_market_states.py`*")
    return "\n".join(lines)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    df = load_phase2()
    print(f"Loaded {len(df)} days from Phase 2 outputs")

    boundaries = recommend_boundaries(df)
    with open(OUTPUT / "factor_boundaries.json", "w") as f:
        json.dump(boundaries, f, indent=2)

    labeled = label_factors(df, boundaries)
    combos = combination_stats(labeled)
    combos.to_csv(OUTPUT / "combination_statistics.csv", index=False)

    clustered, k, k_scores, centroids = discover_states(labeled, combos)
    clustered.to_csv(OUTPUT / "combination_clusters.csv", index=False)
    k_scores.to_csv(OUTPUT / "cluster_selection_scores.csv", index=False)
    centroids.reset_index().to_csv(OUTPUT / "state_centroids.csv", index=False)

    combo_to_state = dict(zip(clustered["combination"], clustered["state_name"]))
    daily = map_daily_states(labeled, combo_to_state, centroids)
    daily.to_csv(OUTPUT / "daily_market_states.csv", index=False)

    state_stats = state_statistics(daily)
    state_stats.to_csv(OUTPUT / "market_state_statistics.csv", index=False)

    transitions = transition_matrix(daily)
    transitions.to_csv(OUTPUT / "transition_matrix.csv")

    durations = state_durations(daily)
    durations.to_csv(OUTPUT / "state_durations.csv", index=False)

    risk_rec = risk_o_meter_recommendations(state_stats)
    risk_rec.to_csv(OUTPUT / "risk_o_meter_recommendations.csv", index=False)

    report = generate_report(
        boundaries, combos, state_stats, transitions, durations,
        risk_rec, k, k_scores, centroids,
    )
    (OUTPUT / "MARKET_MOOD_PHASE3_REPORT.md").write_text(report, encoding="utf-8")
    print(f"Report: {OUTPUT / 'MARKET_MOOD_PHASE3_REPORT.md'}")
    print(f"States discovered: {k}")


if __name__ == "__main__":
    main()
