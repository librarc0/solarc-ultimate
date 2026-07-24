"""Run the standalone rating engine against a JSON match file.

Example:
    uv run python scripts/rating_cli.py examples/rating_match.json
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.rating_engine.engine import EngineSettings, MatchData, PlayerRatingInput, RatingEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate SolArc rating deltas from JSON.")
    parser.add_argument("input", type=Path, help="JSON file containing one match.")
    return parser.parse_args()


def load_player(raw: dict) -> PlayerRatingInput:
    return PlayerRatingInput(
        player_id=int(raw["player_id"]),
        mu=float(raw.get("mu", 25.0)),
        sigma=float(raw.get("sigma", 8.333)),
        goals=raw.get("goals"),
        assists=raw.get("assists"),
        defenses=raw.get("defenses"),
    )


def main() -> None:
    args = parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    settings = EngineSettings(**data.get("settings", {}))
    engine = RatingEngine(settings)
    match = MatchData(
        team_a=[load_player(p) for p in data["team_a"]],
        team_b=[load_player(p) for p in data.get("team_b", [])],
        team_a_score=int(data["team_a_score"]),
        team_b_score=int(data["team_b_score"]),
        data_level=int(data.get("data_level", 1)),
    )

    if data.get("match_type", "internal") == "external":
        outputs = engine.calculate_external(match, opponent_strength=int(data.get("opponent_strength", 5)))
    else:
        outputs = engine.calculate_internal(match)

    print(json.dumps([asdict(item) for item in outputs], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
