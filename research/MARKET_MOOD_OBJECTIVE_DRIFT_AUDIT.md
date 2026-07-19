# Market Mood Research — Independent Objective-Drift Audit and Course Correction

## Executive conclusion

The permanent project objective reconstructed from the Quant Center codebase is:

> Build a Market Intelligence Engine that improves decisions across the Quant Center stock universe—including stock selection, portfolio construction, Risk-O-Meter, and F1. It is not an index prediction model.

Production evidence supports this objective:

- `core/orchestrator.py` runs stock-selection engines and writes ticker-level signals.
- `Engines/` contains per-stock screening, ranking, sizing, stop, and target logic.
- `core/ai_scanner.py` produces per-stock BUY/WATCH/EXIT decisions.
- Quant Center's F1 services consume ranked per-stock decisions and construct portfolios.
- Index and breadth measures appear primarily as context or entry gates, not as the product being forecast.

The research objective drift began in Phase 2 when the equal-weight mean price of the available stock universe was named `index_close` and made the primary target for forward-return prediction. Phase 3 then converted those index-return relationships into market states and allocation recommendations. That conversion was not justified for stock selection, F1, or portfolio construction.

The Phase 3 audit corrected statistical reliability problems but retained index outcomes as the regime target. Phase 4 moved closer to the correct objective by treating stress as a drawdown-risk layer, but its validation and weights still use an equal-weight index proxy rather than actual Quant Center portfolio and stock-universe decision outcomes.

Therefore:

- Keep the descriptive breadth/factor constructions.
- Keep the statistical reliability standards.
- Keep the Stress Layer concept as a defensive risk feature.
- Discard the original Phase 3 states and allocation recommendations.
- Revalidate all weights, boundaries, states, and Risk-O-Meter mappings against stock-universe, F1, and portfolio outcomes.

---

## 1. Reconstructed project objective

### What the project actually does

| Project function | Evidence | Correct Market Intelligence role |
|---|---|---|
| Stock screening | `Engines/`, `core/orchestrator.py` | Improve candidate quality and timing |
| Stock ranking | `core/ai_scanner.py`, F1 decision feed | Improve cross-sectional selection |
| Portfolio construction | `config.py`, F1/F1 Basket services | Control deployment, sizing, concentration, and turnover |
| Risk control | Breadth gates, earnings blocks, stops, Phase 4 stress design | Throttle exposure and protect capital |
| F1 | Ranked BUY/ROTATE/BLOCK/WATCH decisions | Improve deployment and portfolio rotation |

### What the project is not

It is not designed to:

- Forecast Nifty direction as its primary output.
- Maximize correlation with index forward returns.
- Treat a positive index return as sufficient evidence that stock-selection decisions improved.
- Derive portfolio allocation solely from expected index returns.

### Correct research question

The correct question is not:

> Does this factor predict the market index return?

It is:

> Does this information improve the quality, risk, selectivity, sizing, and deployment decisions of Quant Center's stock universe and portfolios?

---

## 2. Where objective drift occurred

### Initial methodological drift

`research/market_mood_phase2/scripts/build_market_breadth.py` creates:

```text
index_close = equal-weight mean of constituent closing prices
```

That synthetic series is useful as a broad universe condition indicator. The drift occurred when it became the optimization target rather than a contextual variable.

### Consequences of the drift

1. Factor predictive power became synonymous with index-return IC.
2. Factor weights were chosen from index-return correlations.
3. LOW/MEDIUM/HIGH boundaries were selected to separate 10-day index returns.
4. Market states were named and ranked from index outcomes.
5. Risk-O-Meter actions were inferred from index expectancy.
6. No analysis tested whether the factors improved:
   - stock-selection hit rate,
   - cross-sectional alpha,
   - F1 ranking quality,
   - basket return or drawdown,
   - portfolio concentration,
   - turnover,
   - deployment timing,
   - or capital efficiency.

---

## 3. Phase-by-phase classification

## Phase 1

No Phase 1 research artifacts or `market_mood.csv` are present in this repository.

| Conclusion or artifact | Classification | Reason |
|---|---|---|
| Any Phase 1 thresholds, weights, or Driving Modes | **Needs revalidation** | Source evidence is unavailable; they cannot be independently audited |
| General idea of market context influencing stock decisions | **Still valid** | Consistent with production breadth gates and stock-selection architecture |

Phase 1 must be supplied or reconstructed before any claim that the entire historical chain has been validated.

---

## Phase 2 — Factor predictive validation

### Still valid

| Conclusion | Reason |
|---|---|
| Trend Regime, Relative Leadership, and Participation Impulse are coherent condition descriptors | They are computed from contemporaneous price/breadth information and describe the stock universe |
| Breadth, leadership, participation, and trend should remain independent during research | Prevents a final score from hiding weak components |
| Quintile, monotonicity, IC, and interaction analysis are useful statistical tools | The tools remain valid when applied to the correct outcomes |
| Large-sample interaction analysis is preferable to anecdotal thresholds | Methodologically sound |

### Needs reinterpretation

| Conclusion | Required reinterpretation |
|---|---|
| Relative Leadership was the strongest factor | It was strongest for the synthetic equal-weight index return, not necessarily for stock ranking or F1 |
| Participation Impulse had useful short-term predictive value | Treat as a possible deployment/selectivity indicator, not an index forecast |
| Trend Regime was more useful at longer horizons | This may describe holding-environment quality, but does not prove better portfolio outcomes |
| High Trend + High Participation was favorable | A supportive universe condition hypothesis, not evidence to increase allocation |

### Needs revalidation

| Conclusion | Correct revalidation target |
|---|---|
| Weights: Trend 23%, Leadership 41%, Participation 36% | Conditional stock returns, F1 rank spread, basket P&L, portfolio drawdown |
| No factor should be removed | Incremental decision value after controlling for overlap |
| IC magnitudes and quintile spreads | Stock-level and portfolio-level outcomes |
| Factor interactions | Engine/F1 hit rate, payoff ratio, drawdown, turnover, breadth of usable opportunities |

### Must be discarded

| Conclusion | Reason |
|---|---|
| “Proceed to implementation” based on Phase 2 | The implementation gate was tied to index-return IC and combination return spread |
| Index predictive power as proof of Quant Center decision value | Wrong objective |

---

## Phase 3 — Market states and Driving Mode thresholds

### Still valid

| Conclusion | Reason |
|---|---|
| Factor distributions can supply natural boundaries | Distributional analysis is appropriate, but target-assisted selection must be removed |
| Combination cells require sample-count reporting | Essential governance |
| State persistence and transition frequency matter | Relevant to preventing excessive portfolio churn |

### Needs reinterpretation

| Conclusion | Required reinterpretation |
|---|---|
| LOW/MEDIUM/HIGH categories are useful | They should describe universe conditions, not index-return bands |
| Market states can simplify decision policy | States should map to selection breadth, portfolio risk, and deployment conditions |

### Needs revalidation

| Conclusion | Correct revalidation |
|---|---|
| Numeric factor boundaries | Derive using rolling distributions and validate against decision outcomes |
| Number of states | Select using stability plus separation in portfolio/F1 outcomes |
| Transition and duration properties | Recompute after states are rebuilt on correct outcomes |

### Must be discarded

| Conclusion | Reason |
|---|---|
| Fog, City, and Mixed Terrain states | Built partly from index-return profiles; City had only 14 days |
| City/Fog → increase allocation | No evidence from Quant Center portfolios or F1 |
| Raw combination rankings led by cells with seven observations | Statistically unreliable |
| “Proceed to implementation” | Superseded by the audit and invalid under the correct objective |

---

## Phase 3 reliability audit

### Still valid

| Conclusion | Reason |
|---|---|
| Seven-observation combinations must not outrank well-supported combinations without uncertainty adjustment | Universal statistical principle |
| Report standard error, confidence intervals, and reliability | Required for any decision rule |
| Recommended minimum cell size of approximately 30 | Reasonable research governance floor |
| Original Phase 3 states must not be implemented | Correct |
| Opportunity factors alone do not reliably identify stress/bear conditions | Supported by the failure of all-three-LOW to isolate adverse outcomes |
| Drawdown, downside volatility, new-low pressure, and persistence should be added | Directly relevant to capital protection |

### Needs reinterpretation

| Conclusion | Required reinterpretation |
|---|---|
| HIGH Trend + HIGH Leadership + HIGH Participation was the reliable leader | Reliable only for index-return evidence; treat as a hypothesis for broad stock opportunity |
| Constructive/Caution/Capital Protection are appropriate names | Useful policy labels, not validated state definitions |

### Needs revalidation

| Conclusion | Correct revalidation |
|---|---|
| Three states are statistically optimal | Re-run clustering on stock/basket/portfolio behavior |
| Outcome clusters | Use Quant Center outcomes, not index outcomes |
| State allocation mappings | Test gross exposure, position count, and F1 deployment policies |

### Must be discarded

| Conclusion | Reason |
|---|---|
| Index-outcome clusters as final production states | They cluster the wrong outcomes |

---

## Phase 4 — Stress Layer

### Still valid

| Conclusion | Reason |
|---|---|
| Stress must be separate from opportunity | Prevents relief rallies from being mistaken for durable risk-on conditions |
| New-low pressure and breadth deterioration are strong stress candidates | They directly describe deterioration across the stock universe |
| Drawdown, downside volatility, and breadth-failure persistence are relevant | Directly related to capital-protection decisions |
| Stress predicts drawdown risk better than directional return | Correct conceptual use |
| High stress can coexist with positive subsequent returns | Critical evidence against using stress as a short/index forecast |
| Stress should act as an independent defensive override | Aligned with Risk-O-Meter purpose |
| Walk-forward testing is required before implementation | Correct |

### Needs reinterpretation

| Conclusion | Required reinterpretation |
|---|---|
| Stress Index predicts “market drawdown” | It predicts drawdown of the equal-weight universe proxy; interpret as a candidate portfolio-risk feature |
| Highest stress means Capital Protection | It may justify a risk review or throttle, but the action must depend on actual portfolio/F1 outcomes |

### Needs revalidation

| Conclusion | Correct revalidation |
|---|---|
| Stress Index weights | Walk-forward portfolio drawdown, basket tail loss, and F1 adverse-selection outcomes |
| 20-day drawdown IC of 0.214 | Recalculate for Quant Center baskets and strategy books |
| Stress quintile thresholds | Evaluate false positives, lead time, opportunity cost, and recovery behavior |
| Combined opportunity-state × stress policy | Simulate actual deployment and sizing decisions |

### Must be discarded

No Phase 4 factor family needs to be discarded solely because of objective drift. However, none of its exact weights or thresholds is production-valid yet.

---

## 4. Master conclusion register

| Research conclusion | Classification |
|---|---|
| Breadth history is useful for universe-condition analysis | **Still valid** |
| Trend/Leadership/Participation factor definitions | **Still valid** as descriptors |
| Independent factor analysis | **Still valid** |
| Statistical reliability metrics and minimum sample rules | **Still valid** |
| Opportunity factors alone miss stress regimes | **Still valid** |
| Add Stress Layer | **Still valid** |
| Stress is a drawdown-risk layer, not directional forecast | **Still valid** |
| Phase 2 factor ranking | **Needs reinterpretation** |
| Phase 2 combination results | **Needs reinterpretation** |
| Phase 3 state concept | **Needs reinterpretation** |
| Three policy labels: Constructive/Caution/Capital Protection | **Needs reinterpretation** |
| Phase 2 weights | **Needs revalidation** |
| Phase 3 boundaries | **Needs revalidation** |
| Phase 3 state count | **Needs revalidation** |
| Phase 3 audit outcome clusters | **Needs revalidation** |
| Phase 4 Stress Index weights and thresholds | **Needs revalidation** |
| Any F1 integration claim | **Needs revalidation from scratch** |
| Phase 2 “Proceed to implementation” | **Must be discarded** |
| Phase 3 Fog/City/Mixed Terrain states | **Must be discarded** |
| Phase 3 allocation recommendations | **Must be discarded** |
| Phase 3 “Proceed to implementation” | **Must be discarded** |

---

## 5. Correct outcome framework

Future Market Intelligence research must evaluate whether information available on day *t* improves decisions made after day *t*.

### Stock-selection outcomes

- Forward return of selected stocks.
- Return relative to the eligible universe.
- Rank IC across stocks, not time-series IC against an index.
- Top-minus-bottom rank spread.
- Hit rate, payoff ratio, and downside tail.
- Number and quality of actionable candidates.
- Performance separately for each engine and F1.

### Portfolio-construction outcomes

- Basket return and drawdown.
- Volatility and downside semivariance.
- Concentration and sector exposure.
- Turnover and transaction-cost-adjusted performance.
- Position overlap across engines.
- Capital utilization and idle cash.
- Tail loss and recovery time.

### Risk-O-Meter outcomes

- Reduction in portfolio maximum drawdown.
- Reduction in ≥3%, ≥5%, and ≥10% loss-event frequency.
- False defensive signals and missed upside.
- Warning lead time before adverse portfolio events.
- Improvement in risk-adjusted return after throttling.
- Stability and turnover of allocation states.

### F1 outcomes

- PortfolioRank monotonicity.
- BUY versus WATCH/BLOCK forward spread.
- Deployment success by market state.
- ROTATE decision quality.
- Basket return, drawdown, and recovery.
- Effect of state-conditioned position count and capital per pick.

The broad-market or equal-weight universe return may remain:

- a benchmark,
- a control variable,
- a regime descriptor,
- or a relative-return denominator.

It must not remain the sole optimization target.

---

## 6. Course-corrected research architecture

```text
Contemporaneous universe information
    ├── Trend Layer
    ├── Leadership Layer
    ├── Participation Layer
    └── Stress Layer
            ↓
Decision-context model
            ↓
    ┌──────────────────────────────────────┐
    │ Stock selection / rank thresholds    │
    │ Portfolio sizing / concentration     │
    │ Risk-O-Meter exposure throttle       │
    │ F1 deployment / rotation policy      │
    └──────────────────────────────────────┘
            ↓
Evaluation on stock, F1, and portfolio outcomes
```

Market Intelligence should estimate the quality and risk of the opportunity set—not predict a single index path.

---

## 7. Required course correction

### Step 1 — Freeze invalid production conclusions

Do not use:

- Phase 2 weights,
- Phase 3 boundaries,
- Phase 3 state labels,
- Phase 3 allocation rules,
- or current Stress Index thresholds

in production.

### Step 2 — Rebuild the research panel

Create a point-in-time daily panel containing:

- eligible universe constituents,
- factor values,
- engine signals,
- F1 decisions and ranks,
- holdings and portfolio state,
- forward stock outcomes,
- and forward portfolio outcomes.

Universe membership must be point-in-time to reduce survivorship bias.

### Step 3 — Revalidate factor usefulness

For each factor, test:

- cross-sectional stock rank IC,
- conditional signal hit rate,
- selected-versus-universe excess return,
- and incremental value after controlling for the other factors.

### Step 4 — Revalidate Stress Layer

Test whether stress:

- predicts portfolio drawdown and tail loss,
- improves sizing decisions,
- reduces loss-event frequency,
- and provides useful warning lead time without excessive opportunity cost.

### Step 5 — Joint policy simulation

Evaluate:

```text
Opportunity condition × Stress condition
    → entry threshold
    → number of positions
    → capital per position
    → gross exposure
    → F1 deployment/rotation policy
```

Compare each policy with unchanged Quant Center behavior.

### Step 6 — Walk-forward governance

All thresholds and weights must be estimated on historical training windows and evaluated on later unseen periods. Report:

- parameter stability,
- state frequency,
- transition stability,
- confidence intervals,
- turnover,
- false positives,
- and out-of-sample portfolio impact.

### Step 7 — Expand to the future Nifty 750 universe

Repeat validation when the point-in-time Nifty 750 universe is available. Current results use a substantially smaller stock history and cannot automatically generalize.

---

## Final independent recommendation

The Market Mood research contains useful raw ingredients but does not yet validate a production Market Intelligence Engine for Quant Center.

The correct disposition is:

- **Retain:** factor constructions, breadth methodology, reliability governance, Stress Layer concept, and drawdown-not-direction interpretation.
- **Reinterpret:** index-based evidence as preliminary universe-context evidence.
- **Revalidate:** all weights, thresholds, interactions, states, and Risk-O-Meter/F1 mappings using stock and portfolio outcomes.
- **Discard:** Phase 2 and original Phase 3 implementation recommendations, original Phase 3 states, and index-return-derived allocation actions.

The next phase should not ask whether Market Mood predicts an index. It should ask whether Market Intelligence measurably improves Quant Center's stock selection, portfolio construction, capital protection, and F1 decisions out of sample.
