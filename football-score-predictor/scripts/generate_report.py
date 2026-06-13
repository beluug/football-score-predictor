#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "report-template.html"


REQUIRED_TOP_LEVEL = [
    "generated_at",
    "data_status",
    "match",
    "prediction",
    "wdl",
    "score_ranking",
    "goal_distribution",
    "trend",
]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def validate_report(data: dict) -> None:
    missing = [key for key in REQUIRED_TOP_LEVEL if key not in data]
    if missing:
        raise ValueError(f"Missing required top-level fields: {', '.join(missing)}")

    match = data.get("match") or {}
    prediction = data.get("prediction") or {}
    for key in ["home_team", "away_team"]:
        if not match.get(key):
            raise ValueError(f"Missing match.{key}")

    for key in ["recommended_score", "confidence", "expected_goals"]:
        if key not in prediction:
            raise ValueError(f"Missing prediction.{key}")

    if not isinstance(data.get("score_ranking"), list) or not data["score_ranking"]:
        raise ValueError("score_ranking must be a non-empty list")

    if not isinstance(data.get("goal_distribution"), list) or not data["goal_distribution"]:
        raise ValueError("goal_distribution must be a non-empty list")


def html_safe_json(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return (
        payload
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_report(data: dict) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    return template.replace("__REPORT_DATA__", html_safe_json(data))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a static football score prediction HTML report.")
    parser.add_argument("--input", required=True, help="Path to report JSON")
    parser.add_argument("--output", required=True, help="Path to output HTML")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    data = load_json(input_path)
    validate_report(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(data), encoding="utf-8")
    print(f"Generated report: {output_path}")


if __name__ == "__main__":
    main()
