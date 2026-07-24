"""T015: 内战评分引擎单元测试 — 无需数据库，纯算法层"""
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
# Level 0: no update
# ---------------------------------------------------------------------------


def test_level0_returns_empty():
    """Level 0 — 只有名单，不更新评分"""
    match = MatchData(
        team_a=make_team([1, 2, 3]),
        team_b=make_team([4, 5, 6]),
        team_a_score=7,
        team_b_score=5,
        data_level=0,
    )
    assert ENGINE.calculate_internal(match) == []


# ---------------------------------------------------------------------------
# Level 1: pure OpenSkill, no individual stats
# ---------------------------------------------------------------------------


def test_level1_winner_mu_increases_loser_mu_decreases():
    """Level 1 — 胜队 μ 应增加，败队 μ 应减少"""
    match = MatchData(
        team_a=make_team([1, 2, 3]),
        team_b=make_team([4, 5, 6]),
        team_a_score=7,
        team_b_score=5,
        data_level=1,
    )
    results = ENGINE.calculate_internal(match)
    assert len(results) == 6

    a_ids = {1, 2, 3}
    b_ids = {4, 5, 6}
    for r in results:
        if r.player_id in a_ids:
            assert r.delta_mu > 0, f"Winner player {r.player_id} should gain mu"
        else:
            assert r.delta_mu < 0, f"Loser player {r.player_id} should lose mu"


def test_level1_sigma_decreases_for_all():
    """Level 1 — 所有人 σ 都应收窄"""
    match = MatchData(
        team_a=make_team([1, 2, 3]),
        team_b=make_team([4, 5, 6]),
        team_a_score=7,
        team_b_score=4,
        data_level=1,
    )
    results = ENGINE.calculate_internal(match)
    for r in results:
        assert r.sigma_after < r.sigma_before, f"Sigma should shrink for player {r.player_id}"


def test_level1_draw_small_delta():
    """平局 — μ 变化极小，σ 收窄"""
    match = MatchData(
        team_a=make_team([1, 2, 3]),
        team_b=make_team([4, 5, 6]),
        team_a_score=7,
        team_b_score=7,
        data_level=1,
    )
    results = ENGINE.calculate_internal(match)
    for r in results:
        assert abs(r.delta_mu) < 1.0, "Draw should produce tiny mu changes"
        assert r.sigma_after < r.sigma_before


def test_level1_asymmetric_teams():
    """7v6 不等人数 — 正常执行不报错"""
    match = MatchData(
        team_a=make_team([1, 2, 3, 4, 5, 6, 7]),
        team_b=make_team([8, 9, 10, 11, 12, 13]),
        team_a_score=10,
        team_b_score=8,
        data_level=1,
    )
    results = ENGINE.calculate_internal(match)
    assert len(results) == 13


# ---------------------------------------------------------------------------
# Level 2: goals contribution weighting
# ---------------------------------------------------------------------------


def test_level2_top_scorer_gains_more():
    """Level 2 — 进球最多的队员 μ 涨幅最大"""
    team_a = [
        PlayerRatingInput(player_id=1, mu=25.0, sigma=8.333, goals=5, assists=0),
        PlayerRatingInput(player_id=2, mu=25.0, sigma=8.333, goals=3, assists=0),
        PlayerRatingInput(player_id=3, mu=25.0, sigma=8.333, goals=0, assists=0),
    ]
    match = MatchData(
        team_a=team_a,
        team_b=make_team([4, 5, 6]),
        team_a_score=8,
        team_b_score=3,
        data_level=2,
    )
    results = ENGINE.calculate_internal(match)
    by_id = {r.player_id: r for r in results}

    # 进5球 > 进3球 > 进0球（涨幅依次递减）
    assert by_id[1].delta_mu > by_id[2].delta_mu > by_id[3].delta_mu


def test_level2_all_winners_gain_positive():
    """Level 2 胜者保护 — 所有胜队成员 delta_mu 应为正"""
    team_a = [
        PlayerRatingInput(player_id=i, mu=25.0, sigma=8.333, goals=0, assists=0)
        for i in range(1, 4)
    ]
    match = MatchData(
        team_a=team_a,
        team_b=make_team([4, 5, 6]),
        team_a_score=7,
        team_b_score=3,
        data_level=2,
    )
    results = ENGINE.calculate_internal(match)
    for r in results:
        if r.player_id in {1, 2, 3}:
            assert r.delta_mu > 0, f"Winner {r.player_id} floor should keep delta_mu positive"


def test_level2_alpha_zero_equals_pure_os():
    """alpha=0 时，Level 2 结果应退化为纯 OpenSkill（无个人加权）"""
    settings_no_alpha = EngineSettings(alpha=0.0, beta=0.6, gamma=0.4)
    engine_no_alpha = RatingEngine(settings_no_alpha)
    engine_pure = RatingEngine(EngineSettings(alpha=0.0))

    team_a = [
        PlayerRatingInput(player_id=1, mu=25.0, sigma=8.333, goals=5, assists=3),
        PlayerRatingInput(player_id=2, mu=25.0, sigma=8.333, goals=0, assists=0),
    ]
    match = MatchData(
        team_a=team_a,
        team_b=make_team([3, 4]),
        team_a_score=5,
        team_b_score=3,
        data_level=2,
    )

    results_alpha0 = engine_no_alpha.calculate_internal(match)
    results_pure = engine_pure.calculate_internal(match)

    # All players should get the same delta_mu when alpha=0 (no individual weighting)
    by_id_alpha0 = {r.player_id: r for r in results_alpha0}
    by_id_pure = {r.player_id: r for r in results_pure}
    for pid in [1, 2]:
        assert abs(by_id_alpha0[pid].delta_mu - by_id_pure[pid].delta_mu) < 0.01, (
            f"alpha=0 should give same result as pure OS for player {pid}"
        )


# ---------------------------------------------------------------------------
# Level 3: full stats (goals + assists + plus_minus)
# ---------------------------------------------------------------------------


def test_level3_plus_minus_affects_contribution():
    """Level 3 — defenses 应参与贡献分计算"""
    # 两名队员进球相同，但 defenses 不同
    team_a = [
        PlayerRatingInput(player_id=1, mu=25.0, sigma=8.333, goals=2, assists=1, defenses=5),
        PlayerRatingInput(player_id=2, mu=25.0, sigma=8.333, goals=2, assists=1, defenses=0),
    ]
    match = MatchData(
        team_a=team_a,
        team_b=make_team([3, 4]),
        team_a_score=4,
        team_b_score=2,
        data_level=3,
    )
    results = ENGINE.calculate_internal(match)
    by_id = {r.player_id: r for r in results}
    # defenses=5 的队员应涨更多
    assert by_id[1].delta_mu > by_id[2].delta_mu


def test_level3_conservative_rating_updates():
    """Level 3 — conservative_after = BASELINE(50) + mu_after - 3 * sigma_after"""
    team_a = [
        PlayerRatingInput(player_id=1, mu=25.0, sigma=8.333, goals=3, assists=1, defenses=2),
    ]
    match = MatchData(
        team_a=team_a,
        team_b=make_team([2]),
        team_a_score=3,
        team_b_score=1,
        data_level=3,
    )
    results = ENGINE.calculate_internal(match)
    r = results[0]
    # conservative_score = max(0, 50 + mu - 3*sigma)，含 50 分基准偏移
    BASELINE = 50.0
    expected_cr = max(0.0, BASELINE + r.mu_after - 3 * r.sigma_after)
    assert abs(r.conservative_after - expected_cr) < 1e-6


def test_gamma_higher_rewards_assists_more():
    """gamma 越高，助攻型球员相对进球型球员的涨分应更大（Level 3）。"""
    team_a = [
        PlayerRatingInput(player_id=1, mu=25.0, sigma=8.333, goals=2, assists=0, defenses=0),
        PlayerRatingInput(player_id=2, mu=25.0, sigma=8.333, goals=0, assists=2, defenses=0),
    ]
    match = MatchData(
        team_a=team_a,
        team_b=make_team([3, 4]),
        team_a_score=4,
        team_b_score=2,
        data_level=3,
    )

    low = RatingEngine(EngineSettings(alpha=1.0, gamma=0.1)).calculate_internal(match)
    high = RatingEngine(EngineSettings(alpha=1.0, gamma=1.2)).calculate_internal(match)
    low_map = {r.player_id: r for r in low}
    high_map = {r.player_id: r for r in high}
    low_diff = low_map[2].delta_mu - low_map[1].delta_mu
    high_diff = high_map[2].delta_mu - high_map[1].delta_mu
    assert high_diff > low_diff


def test_defense_weight_increases_plus_minus_impact():
    """defense_weight 越大，defenses 更高的球员优势应更明显。"""
    team_a = [
        PlayerRatingInput(player_id=1, mu=25.0, sigma=8.333, goals=1, assists=0, defenses=6),
        PlayerRatingInput(player_id=2, mu=25.0, sigma=8.333, goals=1, assists=0, defenses=0),
    ]
    match = MatchData(
        team_a=team_a,
        team_b=make_team([3, 4]),
        team_a_score=4,
        team_b_score=2,
        data_level=3,
    )

    low = RatingEngine(EngineSettings(alpha=1.0, defense_weight=0.0)).calculate_internal(match)
    high = RatingEngine(EngineSettings(alpha=1.0, defense_weight=0.8)).calculate_internal(match)
    low_map = {r.player_id: r for r in low}
    high_map = {r.player_id: r for r in high}

    low_spread = low_map[1].delta_mu - low_map[2].delta_mu
    high_spread = high_map[1].delta_mu - high_map[2].delta_mu
    assert high_spread > low_spread


def test_winner_floor_factor_lifts_low_contrib_winner():
    """winner_floor_factor 提高后，低贡献胜者应获得更高保底涨分。"""
    team_a = [
        PlayerRatingInput(player_id=1, mu=25.0, sigma=8.333, goals=5, assists=0, defenses=0),
        PlayerRatingInput(player_id=2, mu=25.0, sigma=8.333, goals=0, assists=0, defenses=0),
    ]
    match = MatchData(
        team_a=team_a,
        team_b=make_team([3, 4]),
        team_a_score=5,
        team_b_score=3,
        data_level=2,
    )

    low = RatingEngine(EngineSettings(alpha=1.2, winner_floor_factor=0.0)).calculate_internal(match)
    high = RatingEngine(EngineSettings(alpha=1.2, winner_floor_factor=0.5)).calculate_internal(match)
    low_map = {r.player_id: r for r in low}
    high_map = {r.player_id: r for r in high}
    assert high_map[2].delta_mu >= low_map[2].delta_mu


def test_rating_engine_applies_openskill_model_params():
    """EngineSettings 中 OpenSkill 参数应传入底层 PlackettLuce 模型。"""
    s = EngineSettings(
        openskill_mu=30.0,
        openskill_sigma=9.0,
        openskill_beta=5.2,
        openskill_tau=0.12,
        openskill_kappa=0.002,
        openskill_margin=1.0,
        openskill_limit_sigma=True,
        openskill_balance=True,
    )
    engine = RatingEngine(s)

    assert engine._model.mu == pytest.approx(30.0)
    assert engine._model.sigma == pytest.approx(9.0)
    assert engine._model.beta == pytest.approx(5.2)
    assert engine._model.tau == pytest.approx(0.12)
    assert engine._model.kappa == pytest.approx(0.002)
    assert engine._model.margin == pytest.approx(1.0)
    assert engine._model.limit_sigma is True
    assert engine._model.balance is True
