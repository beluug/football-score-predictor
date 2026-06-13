---
name: football-score-predictor
description: Generate evidence-backed football match prediction reports as static HTML. Use when the user asks for football/soccer score prediction, 比分竞猜, 胜平负, 进球数, 大小球, BTTS, 让球倾向, cold upset risk, or asks to analyze a specific football match and produce an HTML report. The skill requires current web research for injuries, lineups, odds, market movement, schedule context, weather, referee/news signals, and then uses an ensemble model stack to output score probabilities, goal totals, W-D-L probabilities, confidence, and model explanation charts.
---

# Football Score Predictor

## Core Rule

Treat football prediction as a research-and-modeling task, not a quick guess. Spend enough analysis time to collect current evidence, compare sources, resolve contradictions, and explain uncertainty. Do not produce a final report from memory alone when the match is upcoming or recent.

Always browse/search the web for current match context before prediction unless the user explicitly provides a complete, current dataset and asks not to browse. Current context includes injuries, suspensions, expected lineups, odds, line movement, recent form, xG/form metrics, schedule density, weather, venue, referee, motivation, and relevant team news.

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

4. **Run the ensemble reasoning**
   - Use the full model stack from `references/model-stack.md`.
   - Make Dixon-Coles/Poisson the main score-distribution layer.
   - Use Elo, xG, time decay, lineup strength, odds, and situational factors as inputs/corrections.
   - Use Monte Carlo and uncertainty scoring to avoid overconfident single-score picks.

5. **Generate the HTML report**
   - Prepare report JSON matching `references/report-schema.md`.
   - Run `scripts/generate_report.py --input <report.json> --output <report.html>`.
   - If the user did not specify an output path, create the file in the current workspace with a clear name such as `football-prediction-<home>-vs-<away>.html`.

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

## Evidence Quality Rules

- Do not cite or rely on a source that is only a user forum rumor unless it is labeled as rumor.
- Do not treat betting odds as guaranteed truth; use them as a calibrated market signal.
- Reduce confidence when injuries, confirmed lineups, or current odds are unavailable.
- Reduce confidence for friendlies, early-season matches, small leagues with poor data, major rotation risk, neutral venues, and unclear motivation.
- If sources disagree on a key player or odds movement, show the disagreement and lower confidence.

## Report Generation Notes

Use `scripts/generate_report.py` for deterministic HTML rendering. The script expects a JSON file and embeds it into `assets/report-template.html`. Keep the HTML static and self-contained so the user can open it directly in a browser.

When the user asks for only a preview/design, use plausible sample data but label it clearly as sample data. When the user asks for a real prediction, browse first and include sources.
