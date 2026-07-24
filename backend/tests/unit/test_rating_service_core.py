"""rating_service 关键分支单测：settings 映射 + apply_ratings 分支"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.match import (
    EventType,
    Match,
    MatchEvent,
    MatchPlayer,
    MatchStatus,
    MatchType,
    RatingHistory,
    TeamSettings,
    TeamSide,
)
from app.models.player import Player, PlayerStatus, UserRole
from app.models.team import Team
from app.services.rating_service import _build_settings, apply_ratings


def test_build_settings_with_none_returns_defaults():
    s = _build_settings(None)
    assert s.alpha == pytest.approx(0.3)
    assert s.beta == pytest.approx(0.6)
    assert s.gamma == pytest.approx(0.4)
    assert s.external_impact_multiplier == pytest.approx(1.0)


def test_build_settings_maps_team_settings_fields():
    ts = TeamSettings(
        team_id=1,
        updated_by=1,
        alpha=1.1,
        beta=0.9,
        gamma=0.2,
        defense_weight=0.7,
        composite_ts_weight=0.8,
        composite_perf_weight=0.2,
        winner_floor_factor=0.4,
        external_opp_mu_min=10.0,
        external_opp_mu_max=60.0,
        external_opp_sigma=7.0,
        external_impact_multiplier=0.6,
        openskill_mu=26.0,
        openskill_sigma=9.0,
        openskill_beta=4.0,
        openskill_tau=0.2,
        openskill_kappa=0.001,
        openskill_margin=1.5,
        openskill_limit_sigma=True,
        openskill_balance=True,
    )
    s = _build_settings(ts)
    assert s.alpha == pytest.approx(1.1)
    assert s.beta == pytest.approx(0.9)
    assert s.gamma == pytest.approx(0.2)
    assert s.defense_weight == pytest.approx(0.7)
    assert s.composite_ts_weight == pytest.approx(0.8)
    assert s.composite_perf_weight == pytest.approx(0.2)
    assert s.winner_floor_factor == pytest.approx(0.4)
    assert s.external_opp_mu_min == pytest.approx(10.0)
    assert s.external_opp_mu_max == pytest.approx(60.0)
    assert s.external_opp_sigma == pytest.approx(7.0)
    assert s.external_impact_multiplier == pytest.approx(0.6)
    assert s.openskill_mu == pytest.approx(26.0)
    assert s.openskill_sigma == pytest.approx(9.0)
    assert s.openskill_beta == pytest.approx(4.0)
    assert s.openskill_tau == pytest.approx(0.2)
    assert s.openskill_kappa == pytest.approx(0.001)
    assert s.openskill_margin == pytest.approx(1.5)
    assert s.openskill_limit_sigma is True
    assert s.openskill_balance is True


@pytest.mark.anyio
async def test_apply_ratings_level0_returns_without_history(db_session):
    team = Team(name="svc-team", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    p1 = Player(username="svcuser1", password_hash="x", role=UserRole.owner, status=PlayerStatus.active, team_id=team.id)
    p2 = Player(username="svcuser2", password_hash="x", role=UserRole.member, status=PlayerStatus.active, team_id=team.id)
    db_session.add_all([p1, p2])
    await db_session.flush()

    match = Match(
        team_id=team.id,
        match_type=MatchType.internal,
        data_level=0,
        team_a_score=1,
        team_b_score=0,
        match_date=datetime.now(timezone.utc),
        status=MatchStatus.approved,
        created_by=p1.id,
    )
    db_session.add(match)
    await db_session.flush()

    mp1 = MatchPlayer(match_id=match.id, player_id=p1.id, team_side=TeamSide.A, mu_before=p1.mu, sigma_before=p1.sigma)
    mp2 = MatchPlayer(match_id=match.id, player_id=p2.id, team_side=TeamSide.B, mu_before=p2.mu, sigma_before=p2.sigma)
    db_session.add_all([mp1, mp2])
    await db_session.flush()

    before_mu = p1.mu
    await apply_ratings(db_session, match, operated_by=p1.id, participants=[mp1, mp2])

    assert p1.mu == pytest.approx(before_mu)
    rh = list((await db_session.execute(select(RatingHistory))).scalars())
    assert len(rh) == 0


@pytest.mark.anyio
async def test_apply_ratings_prefers_turnover_events_over_entry_turnovers(db_session):
    team = Team(name="svc-team-ev", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    owner = Player(username="evowner1", password_hash="x", role=UserRole.owner, status=PlayerStatus.active, team_id=team.id)
    mate = Player(username="evmate11", password_hash="x", role=UserRole.member, status=PlayerStatus.active, team_id=team.id)
    opp = Player(username="evopp111", password_hash="x", role=UserRole.member, status=PlayerStatus.active, team_id=team.id)
    db_session.add_all([owner, mate, opp])
    await db_session.flush()

    ts = TeamSettings(team_id=team.id, updated_by=owner.id, turnover_penalty=0.4, turnover_sigma_factor=1.0)
    db_session.add(ts)

    match = Match(
        team_id=team.id,
        match_type=MatchType.internal,
        data_level=3,
        team_a_score=15,
        team_b_score=5,
        match_date=datetime.now(timezone.utc),
        status=MatchStatus.approved,
        created_by=owner.id,
    )
    db_session.add(match)
    await db_session.flush()

    mp_owner = MatchPlayer(
        match_id=match.id,
        player_id=owner.id,
        team_side=TeamSide.A,
        goals=5,
        assists=0,
        plus_minus=2,
        turnovers=0,
        mu_before=owner.mu,
        sigma_before=owner.sigma,
    )
    mp_mate = MatchPlayer(
        match_id=match.id,
        player_id=mate.id,
        team_side=TeamSide.A,
        goals=5,
        assists=0,
        plus_minus=2,
        turnovers=0,
        mu_before=mate.mu,
        sigma_before=mate.sigma,
    )
    mp_opp = MatchPlayer(
        match_id=match.id,
        player_id=opp.id,
        team_side=TeamSide.B,
        goals=2,
        assists=0,
        plus_minus=-2,
        turnovers=0,
        mu_before=opp.mu,
        sigma_before=opp.sigma,
    )
    db_session.add_all([mp_owner, mp_mate, mp_opp])
    await db_session.flush()

    # owner 有 1 次 turnover 事件，虽然 MatchPlayer.turnovers=0，仍应触发惩罚
    ev = MatchEvent(
        match_id=match.id,
        event_type=EventType.turnover,
        team_side=TeamSide.A,
        player_id=owner.id,
    )
    db_session.add(ev)
    await db_session.flush()

    await apply_ratings(db_session, match, operated_by=owner.id, participants=[mp_owner, mp_mate, mp_opp])

    # v2: turnover 仅惩罚 μ，不再膨胀 σ（σ 由 OpenSkill tau 统一管理）
    assert owner.mu < mate.mu  # owner 有 turnover 惩罚，mu 更低
    assert owner.sigma == mate.sigma  # σ 不受 turnover 影响


# ──────────────────────────────────────────────────────────────────────────────
# T037 [US4]: 建议 μ 计算函数单元测试
# ──────────────────────────────────────────────────────────────────────────────

async def test_get_suggested_mu_falls_back_to_default_when_fewer_than_3_samples(db_session):
    """T037 [US4]: 有效样本 < 3 人时，建议 μ 回退为该队 openskill_mu（默认 25.0）。"""
    from app.services.rating_settings import get_suggested_mu

    team = Team(name="SugMuTeam37a", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    # 只添加 2 名 active 非 guest 成员
    for i, mu_val in enumerate([28.0, 30.0]):
        p = Player(
            username=f"sugmu37a_{i}",
            password_hash="x",
            team_id=team.id,
            status=PlayerStatus.active,
            is_guest=False,
            mu=mu_val,
            sigma=8.333,
            conservative_rating=mu_val - 3 * 8.333,
        )
        db_session.add(p)
    await db_session.flush()

    suggested = await get_suggested_mu(db_session, team.id)
    # 样本 < 3，回退到默认 25.0（无 TeamSettings 时）
    assert suggested == pytest.approx(25.0)


async def test_get_suggested_mu_uses_arithmetic_mean_when_3_or_more_samples(db_session):
    """T037 [US4]: 有效样本 >= 3 人时，建议 μ = 算术平均值。"""
    from app.services.rating_settings import get_suggested_mu

    team = Team(name="SugMuTeam37b", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    for i, mu_val in enumerate([20.0, 25.0, 30.0]):
        p = Player(
            username=f"sugmu37b_{i}",
            password_hash="x",
            team_id=team.id,
            status=PlayerStatus.active,
            is_guest=False,
            mu=mu_val,
            sigma=8.333,
            conservative_rating=mu_val - 3 * 8.333,
        )
        db_session.add(p)
    await db_session.flush()

    suggested = await get_suggested_mu(db_session, team.id)
    assert suggested == pytest.approx(25.0)  # (20+25+30)/3 = 25


async def test_get_suggested_mu_ignores_guests(db_session):
    """T037 [US4]: is_guest=True 的成员不计入建议 μ 计算（仍 < 3 非 guest → 回退默认值）。"""
    from app.services.rating_settings import get_suggested_mu

    team = Team(name="SugMuTeam37c", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    # 2 名 guest + 1 名非 guest → 非 guest 样本 = 1 < 3 → 回退默认
    for i, (mu_val, is_guest) in enumerate([(10.0, True), (12.0, True), (40.0, False)]):
        p = Player(
            username=f"sugmu37c_{i}",
            password_hash="x",
            team_id=team.id,
            status=PlayerStatus.active,
            is_guest=is_guest,
            mu=mu_val,
            sigma=8.333,
            conservative_rating=mu_val - 3 * 8.333,
        )
        db_session.add(p)
    await db_session.flush()

    suggested = await get_suggested_mu(db_session, team.id)
    # 只有 1 个非 guest 样本，< 3 → 回退默认 25.0
    assert suggested == pytest.approx(25.0)
