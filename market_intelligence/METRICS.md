# Market Intelligence Foundation — Output Metrics

All metrics describe the latest observation in the supplied point-in-time
universe. They use current and earlier rows only. They do not contain forecasts,
scores, weights, thresholds, market states, or decision logic.

## Input contract

- Price input is long-form data with `Date`, `Ticker`, and `Close` columns.
- Sector input is optional and maps `Ticker` to `Sector`.
- `as_of` restricts the engine to observations on or before that timestamp.
- Observation windows and column names can be changed through
  `MarketIntelligenceConfig`.
- A metric requiring more history than is available returns `None`.

## Trend Structure

| Output | Description |
|---|---|
| `constituent_count` | Constituents with a close on the calculation date. |
| `universe_level` | Equal-weight universe path formed by compounding the daily arithmetic mean of available constituent returns. |
| `medium_average` | Rolling mean of `universe_level` over the configured medium observation window. |
| `long_average` | Rolling mean of `universe_level` over the configured long observation window. |
| `distance_from_medium` | Current universe level divided by its medium average, minus one. |
| `distance_from_long` | Current universe level divided by its long average, minus one. |

Trend reports universe-level structure only. Stock participation is not included.

## Participation and Breadth

| Output | Description |
|---|---|
| `constituent_count` | Constituents with a close on the calculation date. |
| `medium_coverage` | Constituents with enough history for the medium moving average. |
| `long_coverage` | Constituents with enough history for the long moving average. |
| `above_medium_count` | Covered constituents currently above their own medium moving average. |
| `above_long_count` | Covered constituents currently above their own long moving average. |
| `above_medium_share` | `above_medium_count / medium_coverage`. |
| `above_long_share` | `above_long_count / long_coverage`. |
| `medium_breadth_change` | Change in `above_medium_share` over the configured participation-change window. |
| `change_window` | Observation span used by `medium_breadth_change`. |

Participation reports how many stocks support the environment and whether that
support is changing. It does not measure return concentration.

## Leadership Quality

| Output | Description |
|---|---|
| `lookback` | Historical observation span used for constituent and sector returns. |
| `eligible_constituent_count` | Constituents with valid current and lookback closes. |
| `positive_constituent_count` | Eligible constituents with a positive lookback return. |
| `positive_return_share` | Positive constituents divided by eligible constituents. |
| `leadership_concentration` | Sum of squared positive-return contribution shares. Higher values mean positive strength is concentrated in fewer stocks. |
| `effective_leader_count` | Inverse of `leadership_concentration`; the equivalent number of equally contributing positive leaders. |
| `sector_count` | Sectors represented by constituents with valid lookback returns. |
| `positive_sector_share` | Sectors with a positive equal-weight constituent return divided by represented sectors. |

Leadership reports the distribution of current strength across stocks and
sectors. It does not reuse moving-average participation.

## Market Stress

| Output | Description |
|---|---|
| `constituent_count` | Constituents with a close on the calculation date. |
| `universe_drawdown` | Distance below the highest equal-weight universe level in the configured drawdown window, expressed as a non-negative proportion. |
| `new_low_count` | Covered constituents at their lowest close in the drawdown window. |
| `new_low_coverage` | Constituents with enough history for the new-low calculation. |
| `new_low_share` | `new_low_count / new_low_coverage`. |
| `persistent_breadth_change` | Medium-term participation share now minus the same share one stress window earlier. |
| `breadth_declining_days` | Number of negative daily changes in medium-term participation during the stress window. |
| `breadth_change_observations` | Valid daily breadth changes inspected during the stress window. |
| `downside_deviation` | Annualized square-root mean of squared negative equal-weight universe returns over the stress window. Positive returns contribute zero. |

Stress reports existing damage and downside instability. It is not a composite
Stress Index and does not trigger defensive action.

## Combined result

`MarketIntelligence` contains:

- `as_of`
- `universe_size`
- `trend`
- `participation`
- `leadership`
- `stress`

The engine only assembles these four independent results.

## Independent interpretation

`MarketIntelligenceInterpreter` converts each raw dimension into a qualitative
condition without combining dimensions:

| Dimension | States | Interpretation inputs |
|---|---|---|
| Trend | Strong / Neutral / Weak | Medium- and long-trend distances |
| Participation | Broad / Average / Narrow | Medium- and long-term participation shares |
| Leadership | Broad / Concentrated / Weak | Positive stock share, effective leader share, and positive sector share |
| Stress | Low / Elevated / High | Drawdown, new-low share, persistent breadth decline, declining-day share, and downside deviation |

Any dimension with insufficient inputs returns `Unavailable`. Each condition
preserves its complete raw result and includes a short explanation.

All interpretation boundaries are held in the threshold dataclasses in
`config.py`. Stress uses transparent independent trigger rules: any high
boundary produces `High`; otherwise any elevated boundary produces `Elevated`.
No weighted or composite score is calculated.

## Driving Mode

`DrivingModeEngine` accepts `MarketConditions` only. It never reads raw metric
values.

The deterministic rule priority is:

1. High Stress defensive override.
2. Multiple adverse opportunity dimensions.
3. Unavailable conditions.
4. Elevated Stress.
5. Concentrated Leadership.
6. Any remaining adverse opportunity condition.
7. Fully favorable opportunity with Low Stress.
8. Otherwise Normal.

This produces `Aggressive`, `Normal`, `Cautious`, or `Defensive` with a reason
and the explanation from each interpreted dimension. `DrivingModeRules` in
`config.py` controls trigger behavior and required dimension counts.

Confidence describes agreement among the four qualitative dimensions:

- `High`: all four share the same favorable, neutral, or adverse stance.
- `Medium`: three dimensions share a stance.
- `Low`: agreement is weaker or any condition is unavailable.

Confidence is not a probability and does not predict an outcome.
