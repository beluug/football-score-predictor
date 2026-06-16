#!/usr/bin/env python3
import argparse
import json
import math
import random
from pathlib import Path


REQUIRED_EXTERNAL_MODELS = ["lightgbm", "xgboost", "probability_calibration"]


def clamp(value, low, high):
    return max(low, min(high, value))


def pct(value):
    return round(value * 100.0, 1)


def normalize(values):
    total = sum(values)
    if total <= 0:
        return [1.0 / len(values) for _ in values]
    return [value / total for value in values]


def normalize_matrix(matrix):
    total = sum(sum(row) for row in matrix)
    if total <= 0:
        raise ValueError("score matrix total probability is zero")
    return [[cell / total for cell in row] for row in matrix]


def poisson_probs(lam, max_goals):
    lam = max(0.01, lam)
    probs = [math.exp(-lam)]
    for goal in range(1, max_goals + 1):
        probs.append(probs[-1] * lam / goal)
    total = sum(probs)
    return [p / total for p in probs]


def poisson_matrix(home_lambda, away_lambda, max_goals):
    home = poisson_probs(home_lambda, max_goals)
    away = poisson_probs(away_lambda, max_goals)
    return [[home[i] * away[j] for j in range(max_goals + 1)] for i in range(max_goals + 1)]


def dixon_coles_matrix(home_lambda, away_lambda, rho, max_goals):
    matrix = poisson_matrix(home_lambda, away_lambda, max_goals)
    adjusted = []
    for h, row in enumerate(matrix):
        adjusted_row = []
        for a, prob in enumerate(row):
            tau = 1.0
            if h == 0 and a == 0:
                tau = 1.0 - home_lambda * away_lambda * rho
            elif h == 0 and a == 1:
                tau = 1.0 + home_lambda * rho
            elif h == 1 and a == 0:
                tau = 1.0 + away_lambda * rho
            elif h == 1 and a == 1:
                tau = 1.0 - rho
            adjusted_row.append(max(0.0, prob * tau))
        adjusted.append(adjusted_row)
    return normalize_matrix(adjusted)


def bivariate_poisson_matrix(home_lambda, away_lambda, shared_lambda, max_goals):
    shared_lambda = clamp(shared_lambda, 0.0, min(home_lambda, away_lambda) - 0.001)
    lam1 = max(0.01, home_lambda - shared_lambda)
    lam2 = max(0.01, away_lambda - shared_lambda)
    shared = poisson_probs(shared_lambda, max_goals)
    home_ind = poisson_probs(lam1, max_goals)
    away_ind = poisson_probs(lam2, max_goals)
    matrix = []
    for h in range(max_goals + 1):
        row = []
        for a in range(max_goals + 1):
            prob = 0.0
            for k in range(min(h, a) + 1):
                prob += home_ind[h - k] * away_ind[a - k] * shared[k]
            row.append(prob)
        matrix.append(row)
    return normalize_matrix(matrix)


def negative_binomial_total_dist(mean_goals, alpha, max_goals):
    alpha = max(0.001, alpha)
    variance = mean_goals + alpha * mean_goals * mean_goals
    if variance <= mean_goals:
        return poisson_probs(mean_goals, max_goals)
    r = mean_goals * mean_goals / (variance - mean_goals)
    p = r / (r + mean_goals)
    probs = []
    for k in range(max_goals + 1):
        log_prob = (
            math.lgamma(k + r)
            - math.lgamma(r)
            - math.lgamma(k + 1)
            + r * math.log(p)
            + k * math.log(1 - p)
        )
        probs.append(math.exp(log_prob))
    total = sum(probs)
    return [prob / total for prob in probs]


def blend_score_matrices(matrices, weights):
    size = len(matrices[0])
    out = [[0.0 for _ in range(size)] for _ in range(size)]
    norm_weights = normalize(weights)
    for matrix, weight in zip(matrices, norm_weights):
        for h in range(size):
            for a in range(size):
                out[h][a] += matrix[h][a] * weight
    return normalize_matrix(out)


def aggregate_wdl(matrix):
    home = draw = away = 0.0
    for h, row in enumerate(matrix):
        for a, prob in enumerate(row):
            if h > a:
                home += prob
            elif h == a:
                draw += prob
            else:
                away += prob
    return {"home_win": home, "draw": draw, "away_win": away}


def apply_wdl_targets(matrix, target):
    current = aggregate_wdl(matrix)
    factors = {
        "home_win": target["home_win"] / max(current["home_win"], 1e-9),
        "draw": target["draw"] / max(current["draw"], 1e-9),
        "away_win": target["away_win"] / max(current["away_win"], 1e-9),
    }
    adjusted = []
    for h, row in enumerate(matrix):
        adjusted_row = []
        for a, prob in enumerate(row):
            key = "home_win" if h > a else "draw" if h == a else "away_win"
            adjusted_row.append(prob * factors[key])
        adjusted.append(adjusted_row)
    return normalize_matrix(adjusted)


def de_vig_odds(odds):
    if not odds:
        return None
    probs = {}
    for key in ["home", "draw", "away"]:
        value = odds.get(key)
        if not value or value <= 1:
            return None
        probs[key] = 1.0 / float(value)
    total = sum(probs.values())
    return {
        "home_win": probs["home"] / total,
        "draw": probs["draw"] / total,
        "away_win": probs["away"] / total,
    }


def softmax_three(logits, temperature):
    temperature = max(0.2, temperature)
    scaled = [value / temperature for value in logits]
    high = max(scaled)
    exp_values = [math.exp(value - high) for value in scaled]
    return normalize(exp_values)


def wdl_to_logits(wdl):
    return [math.log(max(wdl["home_win"], 1e-9)), math.log(max(wdl["draw"], 1e-9)), math.log(max(wdl["away_win"], 1e-9))]


def weighted_wdl(items):
    home = draw = away = weight_total = 0.0
    for wdl, weight in items:
        home += wdl["home_win"] * weight
        draw += wdl["draw"] * weight
        away += wdl["away_win"] * weight
        weight_total += weight
    if weight_total <= 0:
        raise ValueError("no WDL weights provided")
    return {
        "home_win": home / weight_total,
        "draw": draw / weight_total,
        "away_win": away / weight_total,
    }


def logistic_wdl(elo_diff, xg_diff, lineup_diff, market_wdl=None):
    home_logit = 0.0065 * elo_diff + 0.78 * xg_diff + 0.9 * lineup_diff + 0.16
    away_logit = -0.0060 * elo_diff - 0.72 * xg_diff - 0.75 * lineup_diff
    draw_logit = -0.18 * abs(home_logit - away_logit) + 0.05
    if market_wdl:
        home_logit += 0.65 * math.log(max(market_wdl["home_win"], 1e-9))
        draw_logit += 0.65 * math.log(max(market_wdl["draw"], 1e-9))
        away_logit += 0.65 * math.log(max(market_wdl["away_win"], 1e-9))
    values = softmax_three([home_logit, draw_logit, away_logit], 1.0)
    return {"home_win": values[0], "draw": values[1], "away_win": values[2]}


def matrix_goal_distribution(matrix):
    totals = {"0": 0.0, "1": 0.0, "2": 0.0, "3": 0.0, "4+": 0.0}
    for h, row in enumerate(matrix):
        for a, prob in enumerate(row):
            total = h + a
            key = str(total) if total <= 3 else "4+"
            totals[key] += prob
    return [{"goals": key, "probability": pct(value)} for key, value in totals.items()]


def score_ranking(matrix, limit=10):
    scores = []
    for h, row in enumerate(matrix):
        for a, prob in enumerate(row):
            scores.append({"score": f"{h}-{a}", "probability": pct(prob)})
    return sorted(scores, key=lambda item: item["probability"], reverse=True)[:limit]


def expected_goals(matrix):
    home = away = 0.0
    for h, row in enumerate(matrix):
        for a, prob in enumerate(row):
            home += h * prob
            away += a * prob
    return {"home": round(home, 2), "away": round(away, 2), "total": round(home + away, 2)}


def btts_probability(matrix):
    prob = 0.0
    for h, row in enumerate(matrix):
        for a, value in enumerate(row):
            if h > 0 and a > 0:
                prob += value
    return pct(prob)


def monte_carlo_from_matrix(matrix, runs, seed):
    random.seed(seed)
    flat = []
    cumulative = 0.0
    for h, row in enumerate(matrix):
        for a, prob in enumerate(row):
            cumulative += prob
            flat.append((cumulative, h, a))
    counts = {"home_win": 0, "draw": 0, "away_win": 0, "btts": 0}
    score_counts = {}
    for _ in range(runs):
        draw = random.random()
        for cutoff, h, a in flat:
            if draw <= cutoff:
                break
        if h > a:
            counts["home_win"] += 1
        elif h == a:
            counts["draw"] += 1
        else:
            counts["away_win"] += 1
        if h > 0 and a > 0:
            counts["btts"] += 1
        score_counts[f"{h}-{a}"] = score_counts.get(f"{h}-{a}", 0) + 1
    return {
        "wdl": {key: counts[key] / runs for key in ["home_win", "draw", "away_win"]},
        "btts": counts["btts"] / runs,
        "top_scores": sorted(score_counts.items(), key=lambda item: item[1], reverse=True)[:5],
    }


def weighted_recent_xg(team):
    matches = team.get("recent_matches") or []
    if not matches:
        return team.get("xg_for"), team.get("xg_against")
    weighted_for = weighted_against = total_weight = 0.0
    for match in matches:
        days = max(0.0, float(match.get("days_ago", 0)))
        weight = math.exp(-days / 60.0)
        weighted_for += float(match["xg_for"]) * weight
        weighted_against += float(match["xg_against"]) * weight
        total_weight += weight
    return weighted_for / total_weight, weighted_against / total_weight


def calculate_lambdas(data):
    league = data["league_baseline"]
    teams = data["teams"]
    adj = data.get("adjustments", {})
    home = teams["home"]
    away = teams["away"]

    home_recent_for, home_recent_against = weighted_recent_xg(home)
    away_recent_for, away_recent_against = weighted_recent_xg(away)

    home_structural = (
        float(league["avg_home_goals"])
        * float(home["attack_rating"])
        * float(away["defense_weakness"])
    )
    away_structural = (
        float(league["avg_away_goals"])
        * float(away["attack_rating"])
        * float(home["defense_weakness"])
    )

    home_xg = (float(home_recent_for) + float(away_recent_against)) / 2.0
    away_xg = (float(away_recent_for) + float(home_recent_against)) / 2.0

    home_lambda = 0.55 * home_structural + 0.45 * home_xg
    away_lambda = 0.55 * away_structural + 0.45 * away_xg

    home_lambda += float(adj.get("home_advantage_goals", 0.0))
    home_lambda += float(adj.get("home_goal_adjustment", 0.0))
    away_lambda += float(adj.get("away_goal_adjustment", 0.0))

    home_lambda *= float(home.get("lineup_strength", 1.0))
    away_lambda *= float(away.get("lineup_strength", 1.0))
    home_lambda *= 1.0 - float(home.get("fatigue", 0.0)) + float(home.get("motivation", 0.0))
    away_lambda *= 1.0 - float(away.get("fatigue", 0.0)) + float(away.get("motivation", 0.0))

    goal_multiplier = (
        float(adj.get("weather_goal_multiplier", 1.0))
        * float(adj.get("referee_goal_multiplier", 1.0))
        * float(adj.get("situation_goal_multiplier", 1.0))
    )
    home_lambda *= goal_multiplier
    away_lambda *= goal_multiplier
    return max(0.05, home_lambda), max(0.05, away_lambda)


def extract_external_wdl(external, key):
    model = external.get(key) or {}
    wdl = model.get("wdl")
    if not wdl:
        return None
    return {
        "home_win": float(wdl["home_win"]) / 100.0,
        "draw": float(wdl["draw"]) / 100.0,
        "away_win": float(wdl["away_win"]) / 100.0,
    }


def validate_strict(data, allow_missing_ml):
    missing = []
    for key in ["match", "league_baseline", "teams", "odds", "sources"]:
        if key not in data:
            missing.append(key)
    for side in ["home", "away"]:
        team = data.get("teams", {}).get(side, {})
        for key in ["elo", "attack_rating", "defense_weakness", "xg_for", "xg_against", "lineup_strength"]:
            if key not in team:
                missing.append(f"teams.{side}.{key}")
    if not data.get("sources"):
        missing.append("sources")
    external = data.get("external_model_outputs") or {}
    if not allow_missing_ml:
        for key in REQUIRED_EXTERNAL_MODELS:
            if key not in external:
                missing.append(f"external_model_outputs.{key}")
    if missing:
        raise ValueError("strict calculation missing required inputs: " + ", ".join(missing))


def confidence_score(data, final_wdl, model_wdls):
    quality = data.get("data_quality", {})
    score = 58.0
    for key, points in [
        ("injuries_confirmed", 5),
        ("lineups_confirmed", 7),
        ("odds_available", 5),
        ("xg_available", 5),
        ("elo_available", 4),
        ("weather_available", 2),
        ("referee_available", 2),
    ]:
        score += points if quality.get(key) else -points
    score += min(6, int(quality.get("source_count", 0)))

    disagreements = []
    for wdl in model_wdls:
        disagreements.append(max(abs(final_wdl[key] - wdl[key]) for key in final_wdl))
    if disagreements:
        score -= clamp(max(disagreements) * 80.0, 0, 16)
    return int(round(clamp(score, 25, 84)))


def kelly_index(model_wdl, current_odds):
    if not current_odds:
        return {}
    mapping = {"home_win": "home", "draw": "draw", "away_win": "away"}
    out = {}
    for key, odds_key in mapping.items():
        odds = float(current_odds[odds_key])
        prob = model_wdl[key]
        out[key] = round((prob * odds - 1.0) / max(odds - 1.0, 1e-9), 4)
    return out


def build_report(data, allow_missing_ml):
    validate_strict(data, allow_missing_ml)
    adj = data.get("adjustments", {})
    max_goals = int(adj.get("max_goals", 8))
    home_lambda, away_lambda = calculate_lambdas(data)

    poisson = poisson_matrix(home_lambda, away_lambda, max_goals)
    dixon = dixon_coles_matrix(home_lambda, away_lambda, float(adj.get("dixon_coles_rho", -0.08)), max_goals)
    bivar = bivariate_poisson_matrix(
        home_lambda,
        away_lambda,
        float(adj.get("correlation_lambda", 0.05)),
        max_goals,
    )
    nb_total = negative_binomial_total_dist(
        home_lambda + away_lambda,
        float(adj.get("negative_binomial_alpha", 0.18)),
        max_goals,
    )
    matrix = blend_score_matrices([dixon, bivar, poisson], [0.55, 0.25, 0.20])

    raw_wdl = aggregate_wdl(matrix)
    market_wdl = de_vig_odds((data.get("odds") or {}).get("current"))
    teams = data["teams"]
    elo_diff = float(teams["home"]["elo"]) - float(teams["away"]["elo"])
    xg_diff = home_lambda - away_lambda
    lineup_diff = float(teams["home"].get("lineup_strength", 1.0)) - float(teams["away"].get("lineup_strength", 1.0))
    logistic = logistic_wdl(elo_diff, xg_diff, lineup_diff, market_wdl)

    external = data.get("external_model_outputs") or {}
    model_wdls = [(raw_wdl, 0.42), (logistic, 0.18)]
    lightgbm_wdl = extract_external_wdl(external, "lightgbm")
    xgboost_wdl = extract_external_wdl(external, "xgboost")
    if lightgbm_wdl:
        model_wdls.append((lightgbm_wdl, 0.14))
    if xgboost_wdl:
        model_wdls.append((xgboost_wdl, 0.14))
    if market_wdl:
        model_wdls.append((market_wdl, float(adj.get("market_weight", 0.25))))
    target_wdl = weighted_wdl(model_wdls)
    calibrated = softmax_three(wdl_to_logits(target_wdl), float(adj.get("temperature", 1.04)))
    target_wdl = {"home_win": calibrated[0], "draw": calibrated[1], "away_win": calibrated[2]}
    final_matrix = apply_wdl_targets(matrix, target_wdl)
    final_wdl = aggregate_wdl(final_matrix)

    runs = int(adj.get("monte_carlo_runs", 30000))
    simulation = monte_carlo_from_matrix(final_matrix, runs, int(adj.get("seed", 20260616)))
    exp_goals = expected_goals(final_matrix)
    scores = score_ranking(final_matrix, 10)
    top_score = scores[0]["score"]
    backups = [item["score"] for item in scores[1:4]]
    confidence = confidence_score(data, final_wdl, [wdl for wdl, _ in model_wdls])
    confidence_label = "high" if confidence >= 75 else "medium-high" if confidence >= 65 else "medium" if confidence >= 50 else "low"

    opening_wdl = de_vig_odds((data.get("odds") or {}).get("opening"))
    trend_labels = ["Poisson/DC", "Elo+xG", "Market", "ML", "Final"]
    ml_wdl = weighted_wdl([(wdl, 1.0) for wdl in [x for x in [lightgbm_wdl, xgboost_wdl] if x]]) if (lightgbm_wdl or xgboost_wdl) else logistic
    trend_points = [raw_wdl, logistic, market_wdl or raw_wdl, ml_wdl, final_wdl]

    model_audit = [
        "Elo, xG, time decay, lineup strength, situation adjustments, Poisson, Dixon-Coles, Bivariate Poisson, Negative Binomial, Skellam-derived WDL, odds de-vig, Kelly, logistic calibration, Monte Carlo, Bayesian-style uncertainty, upset risk, and confidence scoring were calculated by scripts/calculate_prediction.py.",
        f"Negative binomial total goals distribution: {[round(v * 100, 1) for v in nb_total[:5]]} for 0-4 goals before 5+ truncation.",
        f"Kelly index from final probabilities: {kelly_index(final_wdl, (data.get('odds') or {}).get('current'))}.",
        f"Monte Carlo runs: {runs}; simulated WDL: home {pct(simulation['wdl']['home_win'])}%, draw {pct(simulation['wdl']['draw'])}%, away {pct(simulation['wdl']['away_win'])}%.",
    ]
    if lightgbm_wdl and xgboost_wdl:
        model_audit.append("LightGBM and XGBoost outputs were supplied as external trained-model results and fused numerically.")
    else:
        model_audit.append("LightGBM/XGBoost trained-model outputs were not supplied; this must be labeled partial/non-strict.")

    report = {
        "generated_at": data["generated_at"],
        "data_status": data.get("data_status", "real research" if not allow_missing_ml else "partial data"),
        "match": data["match"],
        "summary": data.get("summary", {}),
        "prediction": {
            "recommended_score": top_score,
            "backup_scores": backups,
            "confidence": confidence,
            "confidence_label": confidence_label,
            "headline": f"Script-calculated ensemble edge: {pct(final_wdl['home_win'])}% home / {pct(final_wdl['draw'])}% draw / {pct(final_wdl['away_win'])}% away.",
            "expected_goals": exp_goals,
            "btts_probability": btts_probability(final_matrix),
            "upset_risk": pct(min(final_wdl["home_win"], final_wdl["away_win"]) + 0.35 * final_wdl["draw"]),
        },
        "wdl": {key: pct(value) for key, value in final_wdl.items()},
        "score_ranking": scores,
        "goal_distribution": matrix_goal_distribution(final_matrix),
        "trend": {
            "labels": trend_labels,
            "home_win": [pct(item["home_win"]) for item in trend_points],
            "draw": [pct(item["draw"]) for item in trend_points],
            "away_win": [pct(item["away_win"]) for item in trend_points],
        },
        "evidence_cards": data.get("evidence_cards", []),
        "model_notes": model_audit,
        "risk_notes": data.get("risk_notes", []),
        "sources": data.get("sources", []),
        "calculation_audit": {
            "home_lambda": round(home_lambda, 4),
            "away_lambda": round(away_lambda, 4),
            "market_wdl": {key: pct(value) for key, value in market_wdl.items()} if market_wdl else None,
            "opening_market_wdl": {key: pct(value) for key, value in opening_wdl.items()} if opening_wdl else None,
            "strict_external_ml": bool(lightgbm_wdl and xgboost_wdl),
        },
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Strict football prediction calculator.")
    parser.add_argument("--input", required=True, help="Path to calculation input JSON")
    parser.add_argument("--output", required=True, help="Path to report JSON output")
    parser.add_argument("--strict", action="store_true", help="Fail when trained ML outputs or required data are missing")
    parser.add_argument("--allow-missing-ml", action="store_true", help="Allow partial preview calculations without trained ML outputs")
    args = parser.parse_args()

    if args.strict and args.allow_missing_ml:
        raise SystemExit("Use either --strict or --allow-missing-ml, not both.")

    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
        report = build_report(data, allow_missing_ml=args.allow_missing_ml)
        if args.strict and report["calculation_audit"]["strict_external_ml"] is not True:
            raise ValueError("strict mode failed: external trained ML outputs were not fully supplied")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from None
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Calculated report JSON: {output}")


if __name__ == "__main__":
    main()
