# Market Mood Phase 3 — Market State Engine Research

**Research only.** No production changes.

## Prerequisite

Phase 2 outputs must exist:

```
research/market_mood_phase2/output/daily_factors_and_returns.csv
```

## Run

```bash
python research/market_mood_phase3/scripts/run_phase3_market_states.py
```

## Outputs

| File | Content |
|------|---------|
| `MARKET_MOOD_PHASE3_REPORT.md` | Full research report |
| `factor_boundaries.json` | LOW/MEDIUM/HIGH cut points per factor |
| `combination_statistics.csv` | All 27 factor combinations |
| `market_state_statistics.csv` | Per-state forward return stats |
| `transition_matrix.csv` | State-to-state transition probabilities |
| `state_durations.csv` | Time spent in each state |
| `risk_o_meter_recommendations.csv` | Suggested Risk-O-Meter actions |
| `daily_market_states.csv` | Daily state assignments |
