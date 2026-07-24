from app.api.v1.endpoints.schedule_lines import (
    _assign_roles,
    _build_gender_targets,
    _build_line_specs,
    _distribute_players_to_lines,
    _serialize_smart_line,
)


def _fake_scored_player(player_id: int, gender: str | None, total_score: float, role_hint: float = 0.0):
    return {
        "player_id": player_id,
        "player_name": f"player_{player_id}",
        "display_name": None,
        "gender": gender,
        "ability_score": total_score,
        "chemistry_score": 5.0,
        "offense_score": total_score * 0.8,
        "defense_score": total_score * 0.75,
        "scoring_score": total_score * 0.7,
        "recent_form_score": total_score * 0.6,
        "turnover_control_score": total_score * 0.5,
        "playmaking_score": total_score * 0.65,
        "stability_score": total_score * 0.68,
        "total_score": total_score,
        "o_line_score": total_score + 1.5,
        "d_line_score": total_score + 1.0,
        "role_hint": role_hint,
    }


def test_gender_targets_preserve_totals():
    scored = [
        _fake_scored_player(i + 1, "M" if i < 7 else "F", 80 - i)
        for i in range(14)
    ]
    specs = _build_line_specs(scored, max_line_size=7, d_line_count=1)
    _build_gender_targets(scored, specs)

    total_m = sum(spec.get("gender_targets", {}).get("M", 0) for spec in specs)
    total_f = sum(spec.get("gender_targets", {}).get("F", 0) for spec in specs)

    assert total_m == 7
    assert total_f == 7
    assert all(spec.get("gender_targets", {}).get("M", 0) <= spec["size"] for spec in specs)
    assert all(spec.get("gender_targets", {}).get("F", 0) <= spec["size"] for spec in specs)


def test_distribute_players_to_lines_considers_gender_balance():
    scored = [
        _fake_scored_player(i + 1, "M" if i % 2 == 0 else "F", 100 - i, role_hint=(3 - (i % 4)))
        for i in range(14)
    ]

    specs = _distribute_players_to_lines(scored, {}, max_line_size=7, d_line_count=1)

    male_counts = [sum(1 for row in spec["players"] if row["gender"] == "M") for spec in specs]
    female_counts = [sum(1 for row in spec["players"] if row["gender"] == "F") for spec in specs]

    assert len(specs) == 2
    assert max(male_counts) - min(male_counts) <= 1
    assert max(female_counts) - min(female_counts) <= 1


def test_build_line_specs_supports_two_d_lines():
    scored = [_fake_scored_player(i + 1, "M" if i < 6 else "F", 90 - i) for i in range(12)]
    specs = _build_line_specs(scored, max_line_size=5, d_line_count=2)

    assert len(specs) == 3
    assert specs[0]["line_type"] == "o_line"
    assert specs[1]["line_name"] == "D Line 1"
    assert specs[2]["line_name"] == "D Line 2"
    assert all(spec["size"] <= 5 for spec in specs)


def test_serialize_smart_line_includes_pair_chemistry_details():
    rows = _assign_roles(
        [
            _fake_scored_player(1, "M", 95, role_hint=2.0),
            _fake_scored_player(2, "F", 90, role_hint=-1.0),
        ],
        handler_ratio=1,
        cutter_ratio=1,
        line_type="o_line",
    )
    pair_map = {
        (1, 2): {
            "player_a_id": 1,
            "player_b_id": 2,
            "player_a_name": "player_1",
            "player_b_name": "player_2",
            "chemistry_score": 0.82,
            "combo_count": 6,
            "co_matches": 10,
        }
    }

    line = _serialize_smart_line("O Line", "o_line", rows, pair_map)

    assert line["chemistry_average"] == 0.82
    assert len(line["chemistry_pairs"]) == 1
    assert "默契 0.82" in line["chemistry_pairs"][0]["summary"]