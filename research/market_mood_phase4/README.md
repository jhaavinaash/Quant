# Market Mood Phase 4 — Stress Layer Research

Research only. This module does not modify production code or source datasets.

## Input

- `Data/stock_prices_clean.csv` (read-only)
- Phase 2 research breadth history (read-only)

No external data is used.

## Run

```bash
python research/market_mood_phase4/scripts/run_phase4_stress_layer.py
```

## Outputs

- `output/PHASE4_STRESS_FACTOR_REPORT.md`
- `output/stress_factor_metrics.csv`
- `output/stress_factor_quintiles.csv`
- `output/recommended_stress_weights.csv`
- `output/stress_index_metrics.csv`
- `output/stress_index_quintiles.csv`
- `output/daily_stress_factors.csv`
- `output/daily_stress_index.csv`

