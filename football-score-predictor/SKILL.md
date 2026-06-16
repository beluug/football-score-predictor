---
name: football-score-predictor
description: Generate evidence-backed football match prediction reports as static HTML with strict numeric calculation. Use when the user asks for football/soccer score prediction, 比分竞猜, 胜平负, 进球数, 大小球, BTTS, 让球倾向, cold upset risk, or asks to analyze a specific football match and produce an HTML report. The skill requires current web research for injuries, lineups, odds, market movement, schedule context, weather, referee/news signals, then requires scripts/calculate_prediction.py for real model calculation before HTML generation.
---

# Football Score Predictor

## Core Rule

Treat football prediction as a research-and-modeling task, not a quick guess. Spend enough analysis time to collect current evidence, compare sources, resolve contradictions, and explain uncertainty. Do not produce a final report from memory alone when the match is upcoming or recent.

Always browse/search the web for current match context before prediction unless the user explicitly provides a complete, current dataset and asks not to browse. Current context includes injuries, suspensions, expected lineups, odds, line movement, recent form, xG/form metrics, schedule density, weather, venue, referee, motivation, and relevant team news.

For real reports, all probabilities must come from actual numeric calculation. Do not manually invent score probabilities, W-D-L probabilities, goal distributions, confidence, or model outputs. Build a calculation input JSON from researched data, run `scripts/calculate_prediction.py --strict`, then render the HTML from the calculated report JSON.

## Workflow

1. **Parse the match**
   - Identify teams, competition, date/time, venue, home/away status, leg/stage rules, and user target markets.
   - If teams or date are ambiguous, ask one concise clarification before analysis.

2. **Research current evidence**
   - Search official club/league sources, reputable sports news, injury/lineup aggregators, odds comparison pages, and recent form/stat sources.
   - Prefer primary or near-primary sources for injuries and lineups.
   - For odds, collect opening and current prices when available; record timestamp and market.
   - Cross-check important claims with at least two sources when possible.
   - Note unavailable or low-confidence inputs explicitly instead of inventing them.

3. **Build the model inputs**
   - Convert research into structured estimates: team strength, attack/defense level, recent xG trend, lineup impact, market implied probabilities, schedule fatigue, motivation, weather/referee effects, and data quality.
   - Read `references/model-stack.md` for the exact model list and role of each model.
   - Read `references/report-schema.md` before preparing JSON for the report generator.
   - Read `references/calculation-input-schema.md` before creating the calculation input file.
   - Every numeric input must be sourced, derived from sourced data, or explicitly marked unavailable. Do not fill unknowns with convenient guesses in real mode.

4. **Run strict numeric calculation**
   - Use the full model stack from `references/model-stack.md`.
   - Run `scripts/calculate_prediction.py --strict --input <calculation-input.json> --output <report.json>`.
   - The script calculates Poisson, Dixon-Coles, Bivariate Poisson, negative binomial totals, Skellam-derived W-D-L, odds de-vig, Kelly index, logistic calibration, Monte Carlo, uncertainty, upset risk, and confidence.
   - Strict mode requires external trained-model outputs for LightGBM, XGBoost, and probability calibration because this skill does not bundle trained model artifacts. If those outputs are unavailable, stop and tell the user a fully strict all-model report cannot be produced yet.
   - Do not override script-calculated probabilities by hand. If a result looks wrong, fix the input data or calculation script and rerun.

5. **Generate the HTML report**
   - Use the report JSON produced by `scripts/calculate_prediction.py`.
   - Run `scripts/generate_report.py --input <report.json> --output <report.html>`.
   - If the user did not specify an output path, create the file in the current workspace with a clear name such as `football-prediction-<home>-vs-<away>.html`.
   - Do not hand-code a new page design. The visual design must come from `assets/report-template.html`; only the report data may change.

6. **Final response**
   - Link to the generated HTML file.
   - Summarize the recommended score, win/draw/loss probabilities, expected goals, confidence, and the biggest uncertainty.
   - Include a brief source note: source count, odds timestamp if available, and missing data warnings.

## Required Outputs

The HTML report must include:

- Match information: competition, kickoff, venue, weather, source timestamp.
- Predicted result: recommended score, backup scores, confidence.
- Score probability ranking.
- Total-goals distribution.
- Win/draw/loss probabilities.
- Model analysis line chart.
- Key evidence cards: injuries/lineups, odds movement, xG/form, schedule/motivation.
- Model stack summary and uncertainty/risk notes.
- Sources list with URLs and access timestamps.
- Calculation audit showing the script-calculated inputs/outputs and any missing trained model artifacts.

## Evidence Quality Rules

- Do not cite or rely on a source that is only a user forum rumor unless it is labeled as rumor.
- Do not treat betting odds as guaranteed truth; use them as a calibrated market signal.
- Reduce confidence when injuries, confirmed lineups, or current odds are unavailable.
- Reduce confidence for friendlies, early-season matches, small leagues with poor data, major rotation risk, neutral venues, and unclear motivation.
- If sources disagree on a key player or odds movement, show the disagreement and lower confidence.
- If strict calculation fails because a required data point or model artifact is missing, do not downgrade silently into a guessed report. Stop and explain exactly what is missing.

## Report Generation Notes

Use `scripts/generate_report.py` for deterministic HTML rendering. The script expects a JSON file and embeds it into `assets/report-template.html`. Keep the HTML static and self-contained so the user can open it directly in a browser.

The report template is the canonical visual design. Do not rebuild, restyle, reorder, or simplify the HTML/CSS during normal report generation. If the user asks for a visual change, edit `assets/report-template.html` first, then generate from that template.

When the user asks for only a preview/design, use plausible sample data but label it clearly as sample data and run `scripts/calculate_prediction.py --allow-missing-ml` if a calculated preview is needed. When the user asks for a real prediction, browse first, include sources, run strict calculation, and only then generate the HTML.
