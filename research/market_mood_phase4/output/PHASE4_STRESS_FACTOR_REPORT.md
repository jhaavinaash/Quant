# Phase 4 — Stress Factor Research Report

**Research only. Existing historical prices only. No production changes.**

## 1. Candidate Stress Factors

Stress is oriented so higher values mean greater market stress. Return IC should therefore be negative, while forward-drawdown IC should be positive.

| Factor | Family | Mean return IC | Mean drawdown IC | Persistence | Score |
|---|---|---:|---:|---:|---:|
| `net_new_lows_share` | New low pressure | -0.048 | 0.143 | 75.6% | 0.095 |
| `new_lows_52w` | New low pressure | -0.053 | 0.124 | 78.4% | 0.089 |
| `above200_deterioration_20d` | Breadth deterioration | -0.045 | 0.129 | 84.3% | 0.087 |
| `new_low_high_ratio` | New low pressure | -0.043 | 0.124 | 78.2% | 0.084 |
| `above50_deterioration_20d` | Breadth deterioration | -0.044 | 0.117 | 83.1% | 0.081 |
| `above200_deterioration_10d` | Breadth deterioration | -0.033 | 0.120 | 82.2% | 0.076 |
| `above200_deterioration_5d` | Breadth deterioration | -0.030 | 0.110 | 71.7% | 0.070 |
| `above50_deterioration_5d` | Breadth deterioration | -0.027 | 0.091 | 71.0% | 0.059 |
| `above50_deterioration_10d` | Breadth deterioration | -0.027 | 0.090 | 78.1% | 0.059 |
| `market_drawdown_252` | Drawdown | 0.008 | 0.087 | 92.9% | 0.045 |
| `downside_semivariance_20d` | Downside volatility | 0.043 | 0.072 | 94.2% | 0.036 |
| `above50_failure_days` | Breadth failure | 0.061 | 0.069 | 83.8% | 0.035 |
| `above200_failure_days` | Breadth failure | 0.053 | 0.065 | 91.5% | 0.033 |
| `realized_volatility_20d` | Downside volatility | 0.073 | 0.039 | 94.2% | 0.020 |

## 2. Recommended Stress Index

One strongest variable per family was retained to limit correlated duplication. Weights equal normalized historical predictive scores; they were not manually tuned.

| Factor | Family | Weight |
|---|---|---:|
| `net_new_lows_share` | New low pressure | 32.0% |
| `above200_deterioration_20d` | Breadth deterioration | 29.2% |
| `market_drawdown_252` | Drawdown | 15.1% |
| `downside_semivariance_20d` | Downside volatility | 12.1% |
| `above50_failure_days` | Breadth failure | 11.6% |

Each component is converted to a past-only expanding percentile. The index is:

`Stress Index = Σ(component percentile × evidence weight)`

## 3. Stress Index Predictive Statistics

| Horizon | N | Return IC | p-value | Drawdown IC | p-value |
|---:|---:|---:|---:|---:|---:|
| 1d | 1835 | -0.030 | 0.2055 | 0.116 | 0.0000 |
| 5d | 1831 | -0.017 | 0.4545 | 0.148 | 0.0000 |
| 10d | 1826 | -0.051 | 0.0301 | 0.176 | 0.0000 |
| 20d | 1816 | -0.071 | 0.0026 | 0.214 | 0.0000 |

### Stress Index quintiles (20-day outcome)

| Quintile | N | Avg return | Win rate | Avg drawdown | ≥3% drawdown |
|---:|---:|---:|---:|---:|---:|
| 1 | 364 | 2.42% | 76.1% | 1.46% | 17.9% |
| 2 | 363 | 1.39% | 71.9% | 2.15% | 26.4% |
| 3 | 363 | 1.36% | 64.5% | 2.25% | 33.9% |
| 4 | 363 | 0.83% | 55.6% | 2.91% | 36.6% |
| 5 | 363 | 1.76% | 65.0% | 3.75% | 43.8% |

**Interpretation:** drawdown prediction is monotonic and materially stronger than return prediction. The highest-stress quintile still has a positive average 20-day return because severe stress is frequently followed by rebound rallies. Therefore this index should be treated as a capital-risk/drawdown layer, not a directional return forecast.

## 4. Validation Coverage

For every candidate factor, `stress_factor_metrics.csv` reports IC for 1/5/10/20-day returns and drawdowns. `stress_factor_quintiles.csv` reports forward return, win rate, drawdown level, and ≥3% drawdown hit rate by quintile. Persistence is measured as both next-day top-quintile retention and average high-stress run length.

## 5. Final Market Intelligence Architecture

```text
Trend Layer
Leadership Layer
Participation Layer
Stress Layer
    ├─ Drawdown
    ├─ Breadth deterioration / failure
    ├─ New-low pressure
    └─ Downside volatility
            ↓
Market State Engine
            ↓
Risk-O-Meter
```

Recommended behavior (design only):
- The first three layers describe opportunity quality.
- The Stress Layer is an independent defensive override.
- High stress must prevent a positive participation rebound from being mistaken for a durable risk-on regime.
- Market states should combine opportunity and stress: Constructive, Caution, and Capital Protection.
- Risk-O-Meter allocation should be conditional on both opportunity state and Stress Index percentile.

## 6. Recommendation

**Proceed to walk-forward validation, not production implementation.** The Stress Index must next be tested out-of-sample for threshold stability, false-positive rate, and lead time before major drawdowns. Production thresholds must be derived from that test.