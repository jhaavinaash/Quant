# Market Mood — Phase 2 Research

**Research only.** Does not modify production code, dashboards, APIs, or `market_mood.csv`.

## Objective

Validate proposed V2 factor architecture using forward market returns.

## Input

Place your historical file at:

```
research/market_mood_phase2/input/market_breadth.csv
```

If missing, a one-time research build can be generated from existing `Data/stock_prices_clean.csv`:

```bash
python research/market_mood_phase2/scripts/build_market_breadth.py
```

## Run validation

```bash
python research/market_mood_phase2/scripts/run_phase2_validation.py
```

## Output

| File | Description |
|------|-------------|
| `output/MARKET_MOOD_PHASE2_REPORT.md` | Full research report |
| `output/factor_correlations.csv` | Pearson, Spearman, IC by factor/horizon |
| `output/quintile_analysis.csv` | Quintile returns and win rates |
| `output/interaction_analysis.csv` | Factor combination analysis |
| `output/daily_factors_and_returns.csv` | Daily factor scores + forward returns |
| `output/recommended_weights.json` | Evidence-based weight suggestion |

## V2 factor definitions

See `V2_FACTOR_DEFINITIONS.md`.

## Horizons

1, 3, 5, 10, 20 trading days forward returns on market index.
