# Model Stack

Use this full model stack for real football prediction reports. Keep the ensemble explainable: each model has a role, and the final answer should describe which signals pushed the prediction.

## Required Models

| Layer | Model / method | Role |
|---|---|---|
| 1 | Elo dynamic strength rating | Baseline team strength, home/away strength gap; calculated by `scripts/calculate_prediction.py` from input Elo |
| 2 | xG / xGA expected goals model | Recent true attacking and defensive quality; calculated from sourced xG inputs and recent-match time decay |
| 3 | Time-decay weighting | Give recent matches more weight than older matches; calculated by exponential decay in the script |
| 4 | Lineup strength model | Adjust for starters, injuries, suspensions, rotation, key absences; input must be sourced and used numerically |
| 5 | Dixon-Coles model | Main score-distribution model; calculated by the script with low-score correction |
| 6 | Poisson goal model | Baseline home/away expected goals and score matrix; calculated by the script |
| 7 | Bivariate Poisson | Correct correlation between both teams' goal counts; calculated by the script |
| 8 | Negative binomial model | Handle overdispersion and high-score tail risk; calculated by the script for total-goals audit |
| 9 | Skellam goal-difference model | Win/draw/loss, handicap direction, goal-difference distribution; derived numerically from the score matrix |
| 10 | Odds de-vig model | Convert market odds to fair implied probabilities; calculated by the script |
| 11 | Odds movement / line movement model | Capture market direction, late information, and heat; input must include opening/current odds when available |
| 12 | Kelly index / market bias analysis | Detect payout risk, market disagreement, abnormal prices; calculated by the script |
| 13 | LightGBM / XGBoost ensemble calibration | Must come from real external trained-model outputs or artifacts; strict mode fails if absent |
| 14 | Logistic regression calibration layer | Stable interpretable baseline and fallback probability model; calculated by the script |
| 15 | Probability calibration | Must come from real calibration artifact/output; script also applies numeric temperature calibration when provided |
| 16 | Monte Carlo simulation | Simulate match paths and generate distributions; calculated by the script |
| 17 | Bayesian uncertainty estimate | Confidence intervals, data-scarcity penalty, model disagreement; calculated as uncertainty/confidence penalties |
| 18 | Situation adjustment model | Schedule density, motivation, cup rules, weather, referee, travel distance; input must be sourced and used numerically |
| 19 | Upset risk model | Identify favorite fragility, abnormal market, lineup weakness, fatigue; calculated by the script |
| 20 | Confidence scoring model | Combine data completeness, model agreement, market disagreement, historical calibration error; calculated by the script |

## Practical Flow

```text
Match input
  -> Elo + xG + time decay + lineup strength
  -> Poisson / Dixon-Coles / Bivariate Poisson / negative binomial score matrix
  -> Skellam goal-difference and handicap direction
  -> Odds de-vig + odds movement + Kelly market calibration
  -> LightGBM/XGBoost + logistic regression probability fusion
  -> Monte Carlo + Bayesian uncertainty
  -> Score ranking, goal totals, W-D-L, confidence, HTML report
```

## Modeling Guidance

- For real reports, use `scripts/calculate_prediction.py --strict`. Do not claim a model was used unless it appears in the calculation audit or was supplied as a real external trained-model output.
- Let Dixon-Coles drive exact low-score ranking unless strong evidence suggests an open/high-scoring match.
- Use negative binomial output to widen high-score probability when teams are volatile, defensive injuries are severe, or match state is likely open.
- Use market odds as calibration, not as the only prediction.
- Compare model probability with de-vig market probability. Large disagreement must be explained as either value, missing data, or model uncertainty.
- Prefer a probability distribution over one hard score. The top score can easily have only 8-15% probability.
- Confidence is not the top-score probability. Confidence reflects data quality, model agreement, market stability, and uncertainty.

## Strict Execution Requirement

All real reports must be reproducible from:

1. sourced web data,
2. a `calculation-input.json` file matching `references/calculation-input-schema.md`,
3. `scripts/calculate_prediction.py --strict`,
4. `scripts/generate_report.py`.

If any required input is unavailable, stop instead of inventing it. If LightGBM, XGBoost, or probability-calibration artifacts are unavailable, a fully strict all-model report cannot be produced.

## Confidence Heuristic

Start from 60, then adjust:

- Add 5-10 for confirmed lineups, stable odds, high-quality xG/Elo data, and agreement across models.
- Subtract 5-15 for unclear injuries, major rotation risk, missing odds, early-season noise, friendlies, or low-data leagues.
- Subtract 5-10 when model and market disagree sharply without a clear explanation.
- Cap at 75 before confirmed lineups unless the market and team news are unusually stable.
- Rarely exceed 82 for football match predictions.
