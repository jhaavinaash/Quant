"""Audit Phase 3 market-state research using Phase 2 outputs only."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

BASE = Path(__file__).resolve().parents[1]
P2 = BASE.parent / "market_mood_phase2" / "output" / "daily_factors_and_returns.csv"
P3 = BASE / "output"
OUT = BASE / "audit_output"
FACTORS = ["trend_regime", "relative_leadership", "participation_impulse"]
HORIZONS = [1, 5, 10, 20]


def load() -> pd.DataFrame:
    d = pd.read_csv(P2, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    return d.dropna(subset=FACTORS).reset_index(drop=True)


def boundaries() -> dict:
    import json
    return json.loads((P3 / "factor_boundaries.json").read_text())


def level(v: float, b: dict) -> str:
    if v <= b["low_boundary"]:
        return "LOW"
    if v <= b["high_boundary"]:
        return "MEDIUM"
    return "HIGH"


def label_combinations(d: pd.DataFrame) -> pd.DataFrame:
    b = boundaries()
    x = d.copy()
    for f in FACTORS:
        x[f"{f}_level"] = x[f].map(lambda v: level(v, b[f]))
    x["combination"] = (
        x["trend_regime_level"] + " Trend + "
        + x["relative_leadership_level"] + " Leadership + "
        + x["participation_impulse_level"] + " Participation"
    )
    return x


def forward_drawdown(close: pd.Series, pos: int, horizon: int = 20) -> float:
    path = close.iloc[pos: pos + horizon + 1]
    if len(path) < 2:
        return np.nan
    peak = path.cummax()
    return float((path / peak - 1).min())


def reliability_score(n: int, se: float, ci_low: float, mean: float) -> float:
    """0–100 score combining sample adequacy, precision, and sign confidence."""
    sample = min(1.0, np.sqrt(n / 100))
    precision = 1.0 / (1.0 + (se / max(abs(mean), 0.002)))
    sign_confidence = 1.0 if ci_low > 0 else (0.5 if mean > 0 else 0.2)
    return float(100 * (0.50 * sample + 0.30 * precision + 0.20 * sign_confidence))


def combination_reliability(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for combo, g in d.groupby("combination"):
        row = {"combination": combo, "sample_count": len(g)}
        for h in HORIZONS:
            s = g[f"fwd_return_{h}d"].dropna()
            n = len(s)
            mean = s.mean()
            se = s.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
            tcrit = stats.t.ppf(0.975, n - 1) if n > 1 else np.nan
            low, high = mean - tcrit * se, mean + tcrit * se
            row.update({
                f"avg_return_{h}d": mean,
                f"standard_error_{h}d": se,
                f"ci95_low_{h}d": low,
                f"ci95_high_{h}d": high,
                f"win_rate_{h}d": (s > 0).mean(),
            })
        row["reliability_score"] = reliability_score(
            len(g), row["standard_error_10d"], row["ci95_low_10d"], row["avg_return_10d"]
        )
        # Conservative ranking: lower confidence bound, moderated by reliability.
        row["reliability_adjusted_rank_score"] = (
            row["ci95_low_10d"] * row["reliability_score"] / 100
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["reliability_adjusted_rank_score", "sample_count"], ascending=False
    )


def outcome_profiles(d: pd.DataFrame) -> pd.DataFrame:
    close = d["index_close"].reset_index(drop=True)
    dd = pd.Series(
        [forward_drawdown(close, i, 20) for i in range(len(d))], index=d.index
    )
    x = d.assign(forward_drawdown_20d=dd)
    rows = []
    for combo, g in x.groupby("combination"):
        idx = g.index.to_numpy()
        persistence = np.mean([
            i + 1 < len(x) and x.at[i + 1, "combination"] == combo for i in idx
        ])
        rows.append({
            "combination": combo,
            "sample_count": len(g),
            **{f"return_{h}d": g[f"fwd_return_{h}d"].mean() for h in HORIZONS},
            **{f"win_rate_{h}d": (g[f"fwd_return_{h}d"] > 0).mean() for h in HORIZONS},
            "volatility_1d": g["fwd_return_1d"].std(),
            "downside_volatility_1d": g.loc[
                g["fwd_return_1d"] < 0, "fwd_return_1d"
            ].std(),
            "avg_drawdown_20d": g["forward_drawdown_20d"].mean(),
            "tail_loss_5pct_10d": g["fwd_return_10d"].quantile(0.05),
            "persistence": persistence,
        })
    return pd.DataFrame(rows)


OUTCOME_COLS = [
    "return_1d", "return_5d", "return_10d", "return_20d",
    "win_rate_5d", "win_rate_10d", "win_rate_20d",
    "volatility_1d", "downside_volatility_1d", "avg_drawdown_20d",
    "tail_loss_5pct_10d", "persistence",
]


def cluster_diagnostics(profiles: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    reliable = profiles[profiles["sample_count"] >= 20].copy()
    X = reliable[OUTCOME_COLS].replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())
    scaler = StandardScaler()
    Z = scaler.fit_transform(X)
    rng = np.random.default_rng(42)
    diagnostics, fitted = [], {}
    for k in [3, 4, 5]:
        model = KMeans(n_clusters=k, random_state=42, n_init=50)
        labels = model.fit_predict(Z)
        sil = silhouette_score(Z, labels)
        aris = []
        for seed in range(30):
            sample = rng.choice(len(Z), len(Z), replace=True)
            boot = KMeans(n_clusters=k, random_state=seed, n_init=20).fit(Z[sample])
            boot_labels = boot.predict(Z)
            aris.append(adjusted_rand_score(labels, boot_labels))
        sizes = pd.Series(labels).value_counts()
        diagnostics.append({
            "states": k,
            "silhouette": sil,
            "bootstrap_stability_ari": np.mean(aris),
            "smallest_cluster_combinations": sizes.min(),
            "selection_score": 0.55 * sil + 0.45 * np.mean(aris),
        })
        fitted[k] = (model, labels, scaler, reliable)
    diag = pd.DataFrame(diagnostics)
    # Require no singleton outcome cluster; maximize combined separation/stability.
    eligible = diag[diag["smallest_cluster_combinations"] >= 2]
    chosen = int(eligible.loc[eligible["selection_score"].idxmax(), "states"])
    return diag, {"chosen": chosen, "fit": fitted[chosen]}


def name_outcome_states(cluster_summary: pd.DataFrame) -> dict:
    ranked = cluster_summary.sort_values("return_10d")
    names = {}
    n = len(ranked)
    labels = (
        ["Capital Protection", "Caution", "Constructive"]
        if n == 3 else
        ["Capital Protection", "Caution", "Constructive", "Risk-On"]
        if n == 4 else
        ["Capital Protection", "Defensive", "Caution", "Constructive", "Risk-On"]
    )
    for cluster, name in zip(ranked.index, labels):
        names[int(cluster)] = name
    return names


def outcome_states(profiles: pd.DataFrame, selected: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    model, labels, scaler, reliable = selected["fit"]
    reliable = reliable.copy()
    reliable["cluster"] = labels
    rows = []
    for cluster, group in reliable.groupby("cluster"):
        weights = group["sample_count"].to_numpy()
        row = {"cluster": cluster, "sample_count": int(weights.sum())}
        for col in OUTCOME_COLS:
            row[col] = float(np.average(group[col], weights=weights))
        row["combination_count"] = len(group)
        rows.append(row)
    summary = pd.DataFrame(rows).set_index("cluster")
    names = name_outcome_states(summary)
    reliable["outcome_state"] = reliable["cluster"].map(names)
    summary["outcome_state"] = summary.index.map(names)
    return reliable, summary.reset_index()


def bear_audit(d: pd.DataFrame, profiles: pd.DataFrame) -> pd.DataFrame:
    b = boundaries()
    checks = {
        "All three factors LOW": (
            (d.trend_regime <= b["trend_regime"]["low_boundary"])
            & (d.relative_leadership <= b["relative_leadership"]["low_boundary"])
            & (d.participation_impulse <= b["participation_impulse"]["low_boundary"])
        ),
        "Trend LOW": d.trend_regime <= b["trend_regime"]["low_boundary"],
        "Severe index drawdown (proxy)": d.index_close / d.index_close.rolling(252).max() - 1 <= -0.15,
        "High realized volatility (top decile)": (
            d.index_close.pct_change().rolling(20).std()
            >= d.index_close.pct_change().rolling(20).std().quantile(0.90)
        ),
    }
    rows = []
    for label, mask in checks.items():
        g = d[mask]
        rows.append({
            "condition": label,
            "sample_count": len(g),
            "avg_return_10d": g.fwd_return_10d.mean(),
            "win_rate_10d": (g.fwd_return_10d > 0).mean(),
            "avg_return_20d": g.fwd_return_20d.mean(),
            "win_rate_20d": (g.fwd_return_20d > 0).mean(),
            "volatility_1d": g.fwd_return_1d.std(),
        })
    return pd.DataFrame(rows)


def report(reliability, diagnostics, states, state_summary, bear) -> str:
    top_raw = reliability.sort_values("avg_return_10d", ascending=False).head(3)
    top_reliable = reliability.head(5)
    chosen = int(diagnostics.loc[diagnostics.selection_score.idxmax(), "states"])
    # Use actual constrained selection from state count.
    chosen = state_summary.outcome_state.nunique()
    lines = [
        "# Phase 3 Market State Research — Audit Report", "",
        "**Research only. No production code or datasets modified.**", "",
        "## 1. Small-Sample Ranking Audit", "",
        "The original ranking used raw mean return. The two apparent leaders each had "
        "only 7 observations; their estimates have wide confidence intervals and are not "
        "reliable enough to outrank combinations with 100+ observations.", "",
        "### Raw-return leaders (now uncertainty-qualified)", "",
        "| Combination | N | Avg 10d | SE | 95% CI | Reliability |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in top_raw.iterrows():
        lines.append(
            f"| {r.combination} | {int(r.sample_count)} | {r.avg_return_10d:.2%} | "
            f"{r.standard_error_10d:.2%} | [{r.ci95_low_10d:.2%}, {r.ci95_high_10d:.2%}] | "
            f"{r.reliability_score:.1f}/100 |"
        )
    lines += ["", "### Reliability-adjusted leaders", "",
              "| Combination | N | Avg 10d | 95% CI lower | Reliability |",
              "|---|---:|---:|---:|---:|"]
    for _, r in top_reliable.iterrows():
        lines.append(
            f"| {r.combination} | {int(r.sample_count)} | {r.avg_return_10d:.2%} | "
            f"{r.ci95_low_10d:.2%} | {r.reliability_score:.1f}/100 |"
        )
    lines += [
        "", "Full metrics for all combinations: `combination_reliability.csv`.", "",
        "## 2. Why No Bearish State Was Found", "",
        "The three V2 factors mainly describe trend direction, breadth leadership, and "
        "participation change. They do not directly encode drawdown depth, realized downside "
        "volatility, or crash/tail behavior. Participation impulse can also turn positive during "
        "a bear-market relief rally. Therefore the three factors are insufficient by themselves "
        "for robust bear-state identification.", "",
        "| Diagnostic condition | N | Avg 10d | Win 10d | Vol 1d |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, r in bear.iterrows():
        lines.append(
            f"| {r.condition} | {int(r.sample_count)} | {r.avg_return_10d:.2%} | "
            f"{r.win_rate_10d:.1%} | {r.volatility_1d:.2%} |"
        )
    lines += [
        "", "### Recommended additional market-state variables", "",
        "- **Index drawdown from 252-day high** — distinguishes sustained bear markets from weak trend.",
        "- **20-day realized volatility and downside volatility** — separates orderly weakness from stress.",
        "- **5% lower-tail forward-independent proxy:** historical downside semivariance or rolling VaR.",
        "- **New-low / new-high balance** — captures downside breadth, not only relative leadership.",
        "- **Breadth deterioration persistence** — consecutive days below breadth thresholds.",
        "",
        "These can be derived from existing breadth/index history; no external source is required.",
        "",
        "## 3. Outcome-Similarity Clustering", "",
        "Combinations were clustered using forward returns (1/5/10/20d), win rates, volatility, "
        "downside volatility, drawdown, 5% tail loss, and persistence. Factor values were not "
        "used to create these outcome clusters.", "",
        "| State | Mean 10d | Win 10d | Vol 1d | Drawdown 20d | Persistence |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in state_summary.sort_values("return_10d").iterrows():
        lines.append(
            f"| {r.outcome_state} | {r.return_10d:.2%} | {r.win_rate_10d:.1%} | "
            f"{r.volatility_1d:.2%} | {r.avg_drawdown_20d:.2%} | {r.persistence:.1%} |"
        )
    lines += ["", "## 4. State-Count Selection", "",
              "| States | Silhouette | Bootstrap stability (ARI) | Smallest cluster | Selection score |",
              "|---:|---:|---:|---:|---:|"]
    for _, r in diagnostics.iterrows():
        lines.append(
            f"| {int(r.states)} | {r.silhouette:.3f} | {r.bootstrap_stability_ari:.3f} | "
            f"{int(r.smallest_cluster_combinations)} | {r.selection_score:.3f} |"
        )
    lines += [
        "", f"**Recommendation: {chosen} states.** This count provides the best supported "
        "balance of outcome separation, bootstrap stability, and minimum cluster size among "
        "the tested 3/4/5-state solutions.", "",
        "## 5. Final Production Recommendation", "",
        "**Do not implement the original Phase 3 states. Modify the architecture first.**",
        "",
        "1. Use reliability-adjusted combination estimates; impose a minimum sample threshold "
        "(recommended N ≥ 30) and shrink smaller groups toward the global mean.",
        "2. Add drawdown, downside volatility, downside breadth, and persistence variables.",
        f"3. Use the statistically supported **{chosen}-state outcome architecture** as the "
        "research target, then map observable current-day inputs to those outcome states.",
        "4. Re-run out-of-sample and walk-forward validation before production.",
    ]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    d = label_combinations(load())
    rel = combination_reliability(d)
    rel.to_csv(OUT / "combination_reliability.csv", index=False)
    profiles = outcome_profiles(d)
    profiles.to_csv(OUT / "combination_outcome_profiles.csv", index=False)
    diag, selected = cluster_diagnostics(profiles)
    diag.to_csv(OUT / "state_count_diagnostics.csv", index=False)
    states, summary = outcome_states(profiles, selected)
    states.to_csv(OUT / "outcome_state_assignments.csv", index=False)
    summary.to_csv(OUT / "outcome_state_statistics.csv", index=False)
    bear = bear_audit(d, profiles)
    bear.to_csv(OUT / "bear_market_diagnostics.csv", index=False)
    text = report(rel, diag, states, summary, bear)
    (OUT / "PHASE3_AUDIT_REPORT.md").write_text(text, encoding="utf-8")
    print(f"Audit report: {OUT / 'PHASE3_AUDIT_REPORT.md'}")


if __name__ == "__main__":
    main()
