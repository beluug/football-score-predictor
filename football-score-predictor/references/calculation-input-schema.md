# Calculation Input Schema

Use this schema with `scripts/calculate_prediction.py` before generating a real HTML report.

For real reports, do not hand-write final probabilities. Collect current data, build this JSON, run the calculation script, then pass the produced report JSON to `scripts/generate_report.py`.

```json
{
  "generated_at": "2026-06-16 20:30 Asia/Hong_Kong",
  "data_status": "real research",
  "match": {
    "competition": "Competition",
    "stage": "Round / leg",
    "home_team": "Home",
    "away_team": "Away",
    "kickoff": "2026-06-20 03:00 Asia/Hong_Kong",
    "venue": "Venue",
    "weather": "Weather",
    "referee": "Referee"
  },
  "league_baseline": {
    "avg_home_goals": 1.45,
    "avg_away_goals": 1.15
  },
  "teams": {
    "home": {
      "elo": 1850,
      "attack_rating": 1.18,
      "defense_weakness": 0.86,
      "xg_for": 1.85,
      "xg_against": 0.95,
      "lineup_strength": 0.96,
      "fatigue": 0.04,
      "motivation": 0.08,
      "recent_matches": [
        { "days_ago": 6, "xg_for": 2.1, "xg_against": 0.9 }
      ]
    },
    "away": {
      "elo": 1815,
      "attack_rating": 1.10,
      "defense_weakness": 0.92,
      "xg_for": 1.55,
      "xg_against": 1.05,
      "lineup_strength": 0.93,
      "fatigue": 0.07,
      "motivation": 0.05,
      "recent_matches": []
    }
  },
  "odds": {
    "opening": { "home": 2.05, "draw": 3.45, "away": 3.65 },
    "current": { "home": 1.95, "draw": 3.50, "away": 3.90 },
    "timestamp": "2026-06-16 20:10 Asia/Hong_Kong"
  },
  "adjustments": {
    "home_advantage_goals": 0.18,
    "weather_goal_multiplier": 0.97,
    "referee_goal_multiplier": 1.02,
    "situation_goal_multiplier": 1.00,
    "home_goal_adjustment": 0.00,
    "away_goal_adjustment": 0.00,
    "correlation_lambda": 0.08,
    "dixon_coles_rho": -0.08,
    "negative_binomial_alpha": 0.18,
    "market_weight": 0.25,
    "temperature": 1.04,
    "max_goals": 8,
    "monte_carlo_runs": 30000,
    "seed": 20260616
  },
  "external_model_outputs": {
    "lightgbm": {
      "wdl": { "home_win": 45.1, "draw": 27.9, "away_win": 27.0 },
      "totals": { "over_2_5": 54.2 },
      "btts": 58.7,
      "artifact": "model name/version or source"
    },
    "xgboost": {
      "wdl": { "home_win": 44.6, "draw": 28.4, "away_win": 27.0 },
      "totals": { "over_2_5": 53.5 },
      "btts": 59.1,
      "artifact": "model name/version or source"
    },
    "probability_calibration": {
      "method": "isotonic/platt/temperature",
      "artifact": "calibration source/version"
    }
  },
  "data_quality": {
    "injuries_confirmed": true,
    "lineups_confirmed": false,
    "odds_available": true,
    "xg_available": true,
    "elo_available": true,
    "weather_available": true,
    "referee_available": true,
    "source_count": 8
  },
  "summary": {
    "injuries": "Short injury/lineup summary",
    "market": "Short odds/market summary"
  },
  "evidence_cards": [
    {
      "title": "Injuries and lineup",
      "summary": "Current verified team news.",
      "impact": "Numerical impact used in lineup_strength and goal adjustment."
    }
  ],
  "sources": [
    {
      "label": "Source name",
      "url": "https://example.com",
      "accessed_at": "2026-06-16 20:15 Asia/Hong_Kong",
      "note": "What this source supports"
    }
  ]
}
```

## Strict Rules

- In real mode, run `scripts/calculate_prediction.py --strict --input calculation.json --output report.json`.
- Do not invent missing inputs. If an input is unavailable, either collect it or mark the report as non-real/partial.
- `external_model_outputs.lightgbm`, `external_model_outputs.xgboost`, and `external_model_outputs.probability_calibration` are required in strict mode because this skill does not bundle trained ML artifacts.
- If those trained-model outputs are unavailable, stop and tell the user that a fully strict all-model report cannot be produced yet.
- For previews only, `--allow-missing-ml` may be used, but the report must say `sample preview` or `partial data`, never `real research`.
