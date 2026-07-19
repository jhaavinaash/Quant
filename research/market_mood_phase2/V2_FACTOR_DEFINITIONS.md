# Market Mood V2 — Proposed Factor Definitions (Research Only)

These definitions are used **only** for Phase 2 validation.  
They are **not** implemented in production.

All inputs come from columns in `market_breadth.csv`.

---

## 1. Trend Regime

**Intent:** Is the market in a supportive trend environment?

| Component | Formula |
|-----------|---------|
| Index vs 50 DMA | `(index_close / index_sma_50) - 1` |
| Index vs 200 DMA | `(index_close / index_sma_200) - 1` |
| 20-day index momentum | `index_return_20d` |
| Breadth trend | `pct_above_50dma - 0.5` (centered participation level) |

**Trend Regime score** (raw, not normalized to Mood):

```
trend_regime = 0.35 * index_vs_50dma
             + 0.25 * index_vs_200dma
             + 0.25 * index_return_20d
             + 0.15 * (pct_above_50dma - 0.5)
```

Higher = stronger bullish trend regime.

---

## 2. Relative Leadership

**Intent:** Is leadership broad and strong, not narrow or weak?

| Component | Formula |
|-----------|---------|
| Quintile spread | `top_quintile_return_20d - bottom_quintile_return_20d` |
| New high leadership | `new_highs_20d / (new_highs_20d + new_lows_20d + 1)` |
| Strong stock share | `pct_return_above_5pct_20d` (% of universe with 20d return > 5%) |

**Relative Leadership score:**

```
relative_leadership = 0.45 * quintile_spread
                    + 0.35 * nh_nl_ratio
                    + 0.20 * (pct_return_above_5pct_20d - 0.5)
```

Higher = stronger, healthier leadership.

---

## 3. Participation Impulse

**Intent:** Is participation improving (impulse), not just high?

| Component | Formula |
|-----------|---------|
| 5-day Δ in breadth | `pct_above_50dma - pct_above_50dma_lag5` |
| 3-day Δ in A/D ratio | `ad_ratio - ad_ratio_lag3` |
| Daily participation | `pct_positive - 0.5` (centered % advancing) |
| Volume impulse | `up_volume_share - 0.5` (centered) |

**Participation Impulse score:**

```
participation_impulse = 0.40 * delta_pct_above_50dma_5d
                      + 0.30 * delta_ad_ratio_3d
                      + 0.20 * (pct_positive - 0.5)
                      + 0.10 * (up_volume_share - 0.5)
```

Higher = improving participation impulse.

---

## Interaction buckets (for combination analysis)

Each factor split at **median** into High / Low:

| Combination | Condition |
|-------------|-----------|
| High Trend + High Participation | trend ≥ median AND participation ≥ median |
| High Trend + Weak Participation | trend ≥ median AND participation < median |
| Weak Trend + Strong Participation | trend < median AND participation ≥ median |
| Strong Leadership + Weak Trend | leadership ≥ median AND trend < median |

---

## Forward returns (market index)

Computed on `index_close` from `market_breadth.csv`:

- `fwd_return_1d`, `fwd_return_3d`, `fwd_return_5d`, `fwd_return_10d`, `fwd_return_20d`

---

## Notes

- Factors are kept **independent** — no final Mood score in this phase.
- Quintile analysis uses **daily cross-sectional** quintiles of each factor score.
- IC = Spearman correlation of factor score with forward return (standard quant definition).
