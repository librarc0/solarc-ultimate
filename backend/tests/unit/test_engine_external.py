"""T017: 外战评分引擎单元测试"""
import pytest

from app.rating_engine.engine import (
    EngineSettings,
    MatchData,
    PlayerRatingInput,
    RatingEngine,
)


def make_player(pid: int, mu: float = 25.0, sigma: float = 8.333) -> PlayerRatingInput:
    return PlayerRatingInput(player_id=pid, mu=mu, sigma=sigma)


def make_team(pids: list[int], mu: float = 25.0, sigma: float = 8.333):
    return [make_player(pid, mu, sigma) for pid in pids]


ENGINE = RatingEngine()


# ---------------------------------------------------------------------------
# 外战：强度边界
# ---------------------------------------------------------------------------


def test_external_strength_boundary_low():
    """强度=1（最弱对手）不报错，本队赢 μ 应增加"""
    match = MatchData(
        team_a=make_team([1, 2, 3]),
        team_b=[],  # 外战，对手字段无意义
        team_a_score=7,
        team_b_score=3,
        data_level=1,
    )
    results = ENGINE.calculate_external(match, opponent_strength=1)
    assert len(results) == 3
    for r in results:
        assert r.delta_mu > 0


def test_external_strength_boundary_high():
    """强度=10（顶级对手）不报错，输了 μ 减少"""
    match = MatchData(
        team_a=make_team([1, 2, 3]),
        team_b=[],
        team_a_score=3,
        team_b_score=10,
        data_level=1,
    )
    results = ENGINE.calculate_external(match, opponent_strength=10)
    assert len(results) == 3
    for r in results:
        assert r.delta_mu < 0


# ---------------------------------------------------------------------------
# 赢强队涨幅 > 赢弱队涨幅
# ---------------------------------------------------------------------------


def test_external_win_vs_strong_gains_more_than_win_vs_weak():
    """赢强队（强度=9）μ 增幅 > 赢弱队（强度=2）μ 增幅"""
    base_team = make_team([1, 2, 3])

    match_vs_strong = MatchData(
        team_a=base_team,
        team_b=[],
        team_a_score=7,
        team_b_score=5,
        data_level=1,
    )
    match_vs_weak = MatchData(
        team_a=base_team,
        team_b=[],
        team_a_score=7,
        team_b_score=5,
        data_level=1,
    )

    results_strong = ENGINE.calculate_external(match_vs_strong, opponent_strength=9)
    results_weak = ENGINE.calculate_external(match_vs_weak, opponent_strength=2)

    avg_delta_strong = sum(r.delta_mu for r in results_strong) / len(results_strong)
    avg_delta_weak = sum(r.delta_mu for r in results_weak) / len(results_weak)

    assert avg_delta_strong > avg_delta_weak, (
        f"Win vs strong (Δμ={avg_delta_strong:.3f}) should give more than "
        f"win vs weak (Δμ={avg_delta_weak:.3f})"
    )


# ---------------------------------------------------------------------------
# 输强队下降幅度 < 输弱队下降幅度
# ---------------------------------------------------------------------------


def test_external_lose_vs_strong_drops_less_than_lose_vs_weak():
    """输强队 μ 下降幅度 < 输弱队 μ 下降幅度（更符合直觉）"""
    base_team = make_team([1, 2, 3])

    match_lose_strong = MatchData(
        team_a=base_team,
        team_b=[],
        team_a_score=3,
        team_b_score=7,
        data_level=1,
    )
    match_lose_weak = MatchData(
        team_a=base_team,
        team_b=[],
        team_a_score=3,
        team_b_score=7,
        data_level=1,
    )

    results_strong = ENGINE.calculate_external(match_lose_strong, opponent_strength=9)
    results_weak = ENGINE.calculate_external(match_lose_weak, opponent_strength=2)

    # delta_mu < 0 for losers; |drop| when losing to strong < |drop| when losing to weak
    avg_drop_strong = abs(sum(r.delta_mu for r in results_strong) / len(results_strong))
    avg_drop_weak = abs(sum(r.delta_mu for r in results_weak) / len(results_weak))

    assert avg_drop_strong < avg_drop_weak, (
        f"Losing to strong (drop={avg_drop_strong:.3f}) should be less than "
        f"losing to weak (drop={avg_drop_weak:.3f})"
    )


# ---------------------------------------------------------------------------
# Level 0 外战 → 空
# ---------------------------------------------------------------------------


def test_external_level0_returns_empty():
    """Level 0 外战也应该返回空列表"""
    match = MatchData(
        team_a=make_team([1, 2, 3]),
        team_b=[],
        team_a_score=7,
        team_b_score=5,
        data_level=0,
    )
    assert ENGINE.calculate_external(match, opponent_strength=5) == []


# ---------------------------------------------------------------------------
# 外战只返回本队结果
# ---------------------------------------------------------------------------


def test_external_only_returns_home_team():
    """外战只更新本队队员（不含虚拟对手）"""
    home = make_team([1, 2, 3, 4, 5])
    match = MatchData(
        team_a=home,
        team_b=[],
        team_a_score=7,
        team_b_score=4,
        data_level=1,
    )
    results = ENGINE.calculate_external(match, opponent_strength=5)
    assert len(results) == 5
    result_ids = {r.player_id for r in results}
    assert result_ids == {1, 2, 3, 4, 5}


def test_external_impact_multiplier_scales_delta_mu():
    """external_impact_multiplier 应按比例缩放外战 Δμ。"""
    match = MatchData(
        team_a=make_team([1, 2, 3]),
        team_b=[],
        team_a_score=7,
        team_b_score=5,
        data_level=1,
    )
    base = RatingEngine(EngineSettings(external_impact_multiplier=1.0)).calculate_external(match, opponent_strength=6)
    scaled = RatingEngine(EngineSettings(external_impact_multiplier=0.5)).calculate_external(match, opponent_strength=6)

    base_avg = sum(r.delta_mu for r in base) / len(base)
    scaled_avg = sum(r.delta_mu for r in scaled) / len(scaled)
    assert scaled_avg == pytest.approx(base_avg * 0.5, rel=0.15)
