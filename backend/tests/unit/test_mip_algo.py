"""MIP 四维进步评分算法单元测试

测试目标：
  1. _weighted_slope — 指数衰减加权斜率
  2. _compute_mip_score_map — 四维复合分：门槛、归一化、抗末场拉高
"""
import pytest

from app.api.v1.endpoints.rankings import _weighted_slope, _compute_mip_score_map


# ── _weighted_slope ──────────────────────────────────────────────────────────

class TestWeightedSlope:
    def test_ascending_returns_positive(self):
        """单调递增序列 → 正斜率"""
        values = [10.0, 11.0, 12.0, 13.0, 14.0]
        assert _weighted_slope(values) > 0

    def test_descending_returns_negative(self):
        """单调递减序列 → 负斜率"""
        values = [14.0, 13.0, 12.0, 11.0, 10.0]
        assert _weighted_slope(values) < 0

    def test_flat_returns_zero(self):
        """完全平坦序列 → 0"""
        values = [5.0, 5.0, 5.0, 5.0]
        assert _weighted_slope(values) == pytest.approx(0.0, abs=1e-9)

    def test_single_point_returns_zero(self):
        """单点无法计算斜率 → 0"""
        assert _weighted_slope([25.0]) == 0.0

    def test_empty_returns_zero(self):
        assert _weighted_slope([]) == 0.0

    def test_recency_bias_with_late_spike(self):
        """末场单次高分：加权斜率仍然为正（近期权重高，末场有最大影响力）。
        但多维 MIP 综合分会通过 half_diff、sigma 等维度来平衡，
        真正的抗暴涨验证见 test_mip_steady_beats_spike。
        """
        flat_then_spike = [25.0] * 10 + [45.0]
        weighted_sl = _weighted_slope(flat_then_spike, lam=0.15)
        assert weighted_sl > 0  # 末场高分必然拉正

    def test_lambda_higher_emphasizes_recent_more(self):
        """λ 越大，近期权重占比越高：两组数据，λ=0.5 与 λ=0.05 的斜率比较方向一致但幅度扩大。
        使用一个末场大跌序列：λ 越大，跌幅展现越明显（负斜率更大）。
        """
        late_drop = [30.0] * 8 + [10.0]
        sl_high_lambda = _weighted_slope(late_drop, lam=0.5)
        sl_low_lambda  = _weighted_slope(late_drop, lam=0.05)
        # 两者都是负斜率（末场暴跌）
        assert sl_high_lambda < 0
        assert sl_low_lambda  < 0
        # 高 λ 对末场跌幅更敏感 → 负斜率绝对值更大
        assert abs(sl_high_lambda) > abs(sl_low_lambda)


# ── _compute_mip_score_map ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_mip_empty_player_list(db_session):
    """空 player_ids → 空 dict"""
    result = await _compute_mip_score_map(db_session, [], ts=None)
    assert result == {}


@pytest.mark.anyio
async def test_mip_below_min_matches_returns_zero(db_session):
    """历史不足 min_matches（默认 8）的球员 → 全部 0.0"""
    from app.models.team import Team
    from app.models.player import Player, PlayerStatus, UserRole
    from app.models.match import RatingHistory

    team = Team(name="mip-test-team", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    p = Player(username="mip_p1", password_hash="x", role=UserRole.member,
               status=PlayerStatus.active, team_id=team.id)
    db_session.add(p)
    await db_session.flush()

    # 只给 3 条历史（< 默认 8）
    from datetime import datetime, timezone
    for i in range(3):
        rh = RatingHistory(
            player_id=p.id,
            match_id=1,
            mu_before=25.0,
            mu_after=25.0 + i,
            sigma_before=8.0,
            sigma_after=7.8,
            conservative_before=1.0,
            conservative_after=1.5,
            delta_mu=float(i),
            reason="match_result",
            operated_by=p.id,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(rh)
    await db_session.flush()

    result = await _compute_mip_score_map(db_session, [p.id], ts=None)
    assert result[p.id] == 0.0


@pytest.mark.anyio
async def test_mip_steady_beats_spike(db_session):
    """稳步提升球员的 MIP 分 > 整赛季垃圾+末场爆发球员。"""
    from app.models.team import Team
    from app.models.player import Player, PlayerStatus, UserRole
    from app.models.match import RatingHistory
    from datetime import datetime, timezone

    team = Team(name="mip-cmp-team", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    p_steady = Player(username="mip_steady", password_hash="x", role=UserRole.member,
                      status=PlayerStatus.active, team_id=team.id)
    p_spike  = Player(username="mip_spike",  password_hash="x", role=UserRole.member,
                      status=PlayerStatus.active, team_id=team.id)
    db_session.add_all([p_steady, p_spike])
    await db_session.flush()

    n = 10  # 超过 min_matches=8

    # p_steady：每场 µ+1，sigma 稳步降
    for i in range(n):
        rh = RatingHistory(
            player_id=p_steady.id,
            match_id=1,
            mu_before=20.0 + i,
            mu_after=21.0 + i,
            sigma_before=8.0 - i * 0.1,
            sigma_after=7.9 - i * 0.1,
            conservative_before=1.0,
            conservative_after=1.5,
            delta_mu=1.0,
            reason="match_result",
            operated_by=p_steady.id,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(rh)

    # p_spike：前 9 场µ跌，最后 1 场暴涨
    for i in range(n - 1):
        rh = RatingHistory(
            player_id=p_spike.id,
            match_id=1,
            mu_before=25.0 - i * 0.5,
            mu_after=24.5 - i * 0.5,
            sigma_before=8.0,
            sigma_after=8.1,
            conservative_before=1.0,
            conservative_after=1.0,
            delta_mu=-0.5,
            reason="match_result",
            operated_by=p_spike.id,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(rh)
    # 最后一场暴涨
    rh_last = RatingHistory(
        player_id=p_spike.id,
        match_id=1,
        mu_before=20.5,
        mu_after=35.0,
        sigma_before=8.0,
        sigma_after=8.5,
        conservative_before=1.0,
        conservative_after=5.0,
        delta_mu=14.5,
        reason="match_result",
        operated_by=p_spike.id,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(rh_last)
    await db_session.flush()

    result = await _compute_mip_score_map(db_session, [p_steady.id, p_spike.id], ts=None)

    assert result[p_steady.id] > result[p_spike.id], (
        f"稳步提升({result[p_steady.id]:.4f}) 应 > 末场暴涨({result[p_spike.id]:.4f})"
    )
