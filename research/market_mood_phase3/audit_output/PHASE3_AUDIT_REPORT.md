# Phase 3 Market State Research — Audit Report

**Research only. No production code or datasets modified.**

## 1. Small-Sample Ranking Audit

The original ranking used raw mean return. The two apparent leaders each had only 7 observations; their estimates have wide confidence intervals and are not reliable enough to outrank combinations with 100+ observations.

### Raw-return leaders (now uncertainty-qualified)

| Combination | N | Avg 10d | SE | 95% CI | Reliability |
|---|---:|---:|---:|---:|---:|
| HIGH Trend + LOW Leadership + LOW Participation | 7 | 3.80% | 0.77% | [1.91%, 5.68%] | 58.2/100 |
| MEDIUM Trend + LOW Leadership + HIGH Participation | 7 | 3.39% | 0.73% | [1.59%, 5.19%] | 57.9/100 |
| MEDIUM Trend + HIGH Leadership + HIGH Participation | 44 | 1.80% | 0.44% | [0.91%, 2.70%] | 77.2/100 |

### Reliability-adjusted leaders

| Combination | N | Avg 10d | 95% CI lower | Reliability |
|---|---:|---:|---:|---:|
| HIGH Trend + HIGH Leadership + HIGH Participation | 102 | 1.55% | 1.18% | 96.7/100 |
| HIGH Trend + LOW Leadership + LOW Participation | 7 | 3.80% | 1.91% | 58.2/100 |
| MEDIUM Trend + LOW Leadership + HIGH Participation | 7 | 3.39% | 1.59% | 57.9/100 |
| HIGH Trend + MEDIUM Leadership + MEDIUM Participation | 128 | 1.20% | 0.87% | 96.3/100 |
| MEDIUM Trend + HIGH Leadership + HIGH Participation | 44 | 1.80% | 0.91% | 77.2/100 |

Full metrics for all combinations: `combination_reliability.csv`.

## 2. Why No Bearish State Was Found

The three V2 factors mainly describe trend direction, breadth leadership, and participation change. They do not directly encode drawdown depth, realized downside volatility, or crash/tail behavior. Participation impulse can also turn positive during a bear-market relief rally. Therefore the three factors are insufficient by themselves for robust bear-state identification.

| Diagnostic condition | N | Avg 10d | Win 10d | Vol 1d |
|---|---:|---:|---:|---:|
| All three factors LOW | 106 | 0.05% | 55.7% | 1.58% |
| Trend LOW | 613 | 0.61% | 58.1% | 1.30% |
| Severe index drawdown (proxy) | 94 | 2.77% | 71.3% | 2.07% |
| High realized volatility (top decile) | 184 | 2.20% | 67.9% | 1.69% |

### Recommended additional market-state variables

- **Index drawdown from 252-day high** — distinguishes sustained bear markets from weak trend.
- **20-day realized volatility and downside volatility** — separates orderly weakness from stress.
- **5% lower-tail forward-independent proxy:** historical downside semivariance or rolling VaR.
- **New-low / new-high balance** — captures downside breadth, not only relative leadership.
- **Breadth deterioration persistence** — consecutive days below breadth thresholds.

These can be derived from existing breadth/index history; no external source is required.

## 3. Outcome-Similarity Clustering

Combinations were clustered using forward returns (1/5/10/20d), win rates, volatility, downside volatility, drawdown, 5% tail loss, and persistence. Factor values were not used to create these outcome clusters.

| State | Mean 10d | Win 10d | Vol 1d | Drawdown 20d | Persistence |
|---|---:|---:|---:|---:|---:|
| Capital Protection | 0.34% | 58.8% | 1.75% | -5.13% | 15.2% |
| Caution | 0.42% | 55.7% | 0.90% | -4.13% | 32.7% |
| Constructive | 1.24% | 72.8% | 0.77% | -2.89% | 31.1% |

## 4. State-Count Selection

| States | Silhouette | Bootstrap stability (ARI) | Smallest cluster | Selection score |
|---:|---:|---:|---:|---:|
| 3 | 0.295 | 0.690 | 2 | 0.473 |
| 4 | 0.240 | 0.598 | 2 | 0.401 |
| 5 | 0.246 | 0.635 | 2 | 0.421 |

**Recommendation: 3 states.** This count provides the best supported balance of outcome separation, bootstrap stability, and minimum cluster size among the tested 3/4/5-state solutions.

## 5. Final Production Recommendation

**Do not implement the original Phase 3 states. Modify the architecture first.**

1. Use reliability-adjusted combination estimates; impose a minimum sample threshold (recommended N ≥ 30) and shrink smaller groups toward the global mean.
2. Add drawdown, downside volatility, downside breadth, and persistence variables.
3. Use the statistically supported **3-state outcome architecture** as the research target, then map observable current-day inputs to those outcome states.
4. Re-run out-of-sample and walk-forward validation before production.