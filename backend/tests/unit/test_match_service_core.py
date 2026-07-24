"""match_service 核心分支单测：create/approve/revert/edit"""

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.match import Match, MatchEvent, MatchPlayer, MatchStatus, MatchType, RatingHistory, TeamSide
from app.models.player import Player, PlayerStatus, UserRole
from app.models.team import Team
from app.schemas.match import EventCreate, MatchCreate, MatchPlayerEntry, MatchUpdate
from app.services import match_service
from app.services.match_service import approve_match, create_match, edit_approved_match, revert_ratings


@pytest.mark.anyio
async def test_create_match_downgrades_level_and_ignores_invalid_event_type(db_session):
    team = Team(name="ms-team-1", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    owner = Player(username="msowner1", password_hash="x", role=UserRole.owner, status=PlayerStatus.active, team_id=team.id)
    p2 = Player(username="msplyr11", password_hash="x", role=UserRole.member, status=PlayerStatus.active, team_id=team.id)
    db_session.add_all([owner, p2])
    await db_session.flush()

    body = MatchCreate(
        match_date=date.today(),
        match_type="internal",
        score_us=10,
        score_them=8,
        data_level=3,
        team_a=[MatchPlayerEntry(player_id=owner.id, goals=3, assists=1)],
        team_b=[MatchPlayerEntry(player_id=p2.id, goals=2, assists=1)],
        events=[EventCreate(event_type="not_real_event", team_side="A", player_id=owner.id)],
    )

    m = await create_match(
        db=db_session,
        body=body,
        created_by_id=owner.id,
        team_id=team.id,
        auto_approve=False,
    )

    assert m.status == MatchStatus.pending_approval
    assert m.data_level == 2  # 缺 plus_minus，请求 3 自动降级为 2

    # 非法 event_type 应被忽略
    ev = list((await db_session.execute(select(MatchEvent))).scalars())
    assert len(ev) == 0


@pytest.mark.anyio
async def test_approve_match_validation_errors(db_session):
    with pytest.raises(ValueError, match="比赛不存在"):
        await approve_match(db_session, match_id=99999, approver_id=1)

    team = Team(name="ms-team-2", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    owner = Player(username="msowner2", password_hash="x", role=UserRole.owner, status=PlayerStatus.active, team_id=team.id)
    db_session.add(owner)
    await db_session.flush()

    m = Match(
        team_id=team.id,
        match_type=MatchType.internal,
        data_level=1,
        team_a_score=5,
        team_b_score=3,
        match_date=datetime.now(timezone.utc),
        status=MatchStatus.approved,
        created_by=owner.id,
        approved_by=owner.id,
        approved_at=datetime.now(timezone.utc),
    )
    db_session.add(m)
    await db_session.commit()

    with pytest.raises(ValueError, match="只能审批 pending_approval"):
        await approve_match(db_session, match_id=m.id, approver_id=owner.id)


@pytest.mark.anyio
async def test_revert_ratings_no_history_noop(db_session):
    team = Team(name="ms-team-3", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    owner = Player(
        username="msowner3",
        password_hash="x",
        role=UserRole.owner,
        status=PlayerStatus.active,
        team_id=team.id,
        mu=26.0,
        sigma=8.1,
        conservative_rating=51.7,
        total_matches=3,
        total_wins=2,
    )
    db_session.add(owner)
    await db_session.flush()

    m = Match(
        team_id=team.id,
        match_type=MatchType.internal,
        data_level=1,
        team_a_score=5,
        team_b_score=3,
        match_date=datetime.now(timezone.utc),
        status=MatchStatus.approved,
        created_by=owner.id,
    )
    db_session.add(m)
    await db_session.flush()

    mp = MatchPlayer(
        match_id=m.id,
        player_id=owner.id,
        team_side=TeamSide.A,
        goals=1,
        assists=0,
        turnovers=0,
        mu_before=owner.mu,
        sigma_before=owner.sigma,
        is_winner=True,
    )
    db_session.add(mp)
    await db_session.commit()

    before = (owner.mu, owner.sigma, owner.conservative_rating, owner.total_matches, owner.total_wins)
    await revert_ratings(db_session, m, participants=None)
    after = (owner.mu, owner.sigma, owner.conservative_rating, owner.total_matches, owner.total_wins)

    assert after == before


@pytest.mark.anyio
async def test_create_match_auto_approve_calls_apply_ratings_and_persists_valid_event(db_session, monkeypatch):
    team = Team(name="ms-team-4", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    owner = Player(username="msowner4", password_hash="x", role=UserRole.owner, status=PlayerStatus.active, team_id=team.id)
    p2 = Player(username="msplyr41", password_hash="x", role=UserRole.member, status=PlayerStatus.active, team_id=team.id)
    db_session.add_all([owner, p2])
    await db_session.flush()

    calls = []

    async def fake_apply_ratings(db, match, operated_by, participants, reason="match_result"):
        calls.append((match.id, operated_by, len(participants), reason))

    monkeypatch.setattr(match_service, "apply_ratings", fake_apply_ratings)

    body = MatchCreate(
        match_date=date.today(),
        match_type="internal",
        score_us=11,
        score_them=9,
        data_level=1,
        team_a=[MatchPlayerEntry(player_id=owner.id)],
        team_b=[MatchPlayerEntry(player_id=p2.id)],
        events=[EventCreate(event_type="goal", team_side="A", player_id=owner.id, elapsed_seconds=60)],
    )

    match = await create_match(db_session, body, created_by_id=owner.id, team_id=team.id, auto_approve=True)

    assert match.status == MatchStatus.approved
    assert calls == [(match.id, owner.id, 2, "match_result")]
    events = list((await db_session.execute(select(MatchEvent).where(MatchEvent.match_id == match.id))).scalars())
    assert len(events) == 1
    assert events[0].event_type.value == "goal"


@pytest.mark.anyio
async def test_approve_match_success_calls_apply_ratings(db_session, monkeypatch):
    team = Team(name="ms-team-5", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    owner = Player(username="msowner5", password_hash="x", role=UserRole.owner, status=PlayerStatus.active, team_id=team.id)
    p2 = Player(username="msplyr51", password_hash="x", role=UserRole.member, status=PlayerStatus.active, team_id=team.id)
    db_session.add_all([owner, p2])
    await db_session.flush()

    match = Match(
        team_id=team.id,
        match_type=MatchType.internal,
        data_level=1,
        team_a_score=7,
        team_b_score=5,
        match_date=datetime.now(timezone.utc),
        status=MatchStatus.pending_approval,
        created_by=owner.id,
    )
    db_session.add(match)
    await db_session.flush()

    participant = MatchPlayer(match_id=match.id, player_id=p2.id, team_side=TeamSide.B, mu_before=p2.mu, sigma_before=p2.sigma)
    db_session.add(participant)
    await db_session.commit()

    calls = []

    async def fake_apply_ratings(db, match, operated_by, participants, reason="match_result"):
        calls.append((match.id, operated_by, len(participants), reason))

    monkeypatch.setattr(match_service, "apply_ratings", fake_apply_ratings)

    approved = await approve_match(db_session, match.id, owner.id)

    assert approved.status == MatchStatus.approved
    assert calls == [(match.id, owner.id, 1, "match_result")]


@pytest.mark.anyio
async def test_revert_ratings_uses_latest_history_and_rolls_back_stats(db_session):
    team = Team(name="ms-team-6", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    player = Player(
        username="msowner6",
        password_hash="x",
        role=UserRole.owner,
        status=PlayerStatus.active,
        team_id=team.id,
        mu=30.0,
        sigma=7.0,
        conservative_rating=59.0,
        total_matches=6,
        total_wins=4,
        total_goals=10,
        total_assists=5,
        total_plus_minus=8,
        total_turnovers=3,
    )
    db_session.add(player)
    await db_session.flush()

    match = Match(
        team_id=team.id,
        match_type=MatchType.internal,
        data_level=3,
        team_a_score=15,
        team_b_score=10,
        match_date=datetime.now(timezone.utc),
        status=MatchStatus.approved,
        created_by=player.id,
    )
    db_session.add(match)
    await db_session.flush()

    participant = MatchPlayer(
        match_id=match.id,
        player_id=player.id,
        team_side=TeamSide.A,
        goals=2,
        assists=1,
        plus_minus=3,
        turnovers=1,
        is_winner=True,
        mu_before=27.0,
        sigma_before=8.0,
    )
    db_session.add(participant)
    await db_session.flush()

    older = RatingHistory(
        player_id=player.id,
        match_id=match.id,
        mu_before=26.0,
        sigma_before=8.2,
        mu_after=28.0,
        sigma_after=7.8,
        conservative_before=51.4,
        conservative_after=54.6,
        delta_mu=2.0,
        reason="match_result",
        operated_by=player.id,
        created_at=datetime(2026, 3, 18, tzinfo=timezone.utc),
    )
    latest = RatingHistory(
        player_id=player.id,
        match_id=match.id,
        mu_before=27.5,
        sigma_before=7.9,
        mu_after=30.0,
        sigma_after=7.0,
        conservative_before=53.8,
        conservative_after=59.0,
        delta_mu=2.5,
        reason="admin_correction",
        operated_by=player.id,
        created_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
    )
    db_session.add_all([older, latest])
    await db_session.commit()

    await revert_ratings(db_session, match, participants=[participant])

    assert player.mu == pytest.approx(27.5)
    assert player.sigma == pytest.approx(7.9)
    assert player.conservative_rating == pytest.approx(53.8)
    assert player.total_matches == 5
    assert player.total_wins == 3
    assert player.total_goals == 8
    assert player.total_assists == 4
    assert player.total_plus_minus == 5
    assert player.total_turnovers == 2


@pytest.mark.anyio
async def test_edit_approved_match_validation_and_score_only_reuse_participants(db_session, monkeypatch):
    team = Team(name="ms-team-7", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    owner = Player(username="msowner7", password_hash="x", role=UserRole.owner, status=PlayerStatus.active, team_id=team.id, mu=26.0, sigma=8.1)
    mate = Player(username="msplyr71", password_hash="x", role=UserRole.member, status=PlayerStatus.active, team_id=team.id, mu=24.5, sigma=8.4)
    db_session.add_all([owner, mate])
    await db_session.flush()

    with pytest.raises(ValueError, match="比赛不存在"):
        await edit_approved_match(db_session, 99999, MatchUpdate(action="edit", score_us=1), owner.id, team.id)

    pending_match = Match(
        team_id=team.id,
        match_type=MatchType.internal,
        data_level=1,
        team_a_score=8,
        team_b_score=6,
        match_date=datetime.now(timezone.utc),
        status=MatchStatus.pending_approval,
        created_by=owner.id,
    )
    db_session.add(pending_match)
    await db_session.commit()

    with pytest.raises(ValueError, match="只能编辑已审批"):
        await edit_approved_match(db_session, pending_match.id, MatchUpdate(action="edit", score_us=1), owner.id, team.id)

    approved_match = Match(
        team_id=team.id,
        match_type=MatchType.internal,
        data_level=1,
        team_a_score=10,
        team_b_score=9,
        match_date=datetime.now(timezone.utc),
        status=MatchStatus.approved,
        created_by=owner.id,
        approved_by=owner.id,
        approved_at=datetime.now(timezone.utc),
    )
    db_session.add(approved_match)
    await db_session.flush()

    mp_owner = MatchPlayer(match_id=approved_match.id, player_id=owner.id, team_side=TeamSide.A, mu_before=25.0, sigma_before=8.3)
    mp_mate = MatchPlayer(match_id=approved_match.id, player_id=mate.id, team_side=TeamSide.B, mu_before=25.0, sigma_before=8.3)
    db_session.add_all([mp_owner, mp_mate])
    await db_session.commit()

    async def fake_revert(db, match, participants=None):
        owner.mu = 25.2
        owner.sigma = 8.25
        mate.mu = 24.8
        mate.sigma = 8.35

    calls = []

    async def fake_apply_ratings(db, match, operated_by, participants, reason="match_result"):
        calls.append(SimpleNamespace(match_id=match.id, operated_by=operated_by, participants=participants, reason=reason))

    monkeypatch.setattr(match_service, "revert_ratings", fake_revert)
    monkeypatch.setattr(match_service, "apply_ratings", fake_apply_ratings)

    edited = await edit_approved_match(
        db_session,
        approved_match.id,
        MatchUpdate(action="edit", score_us=12, score_them=7),
        owner.id,
        team.id,
    )

    assert edited.team_a_score == 12
    assert edited.team_b_score == 7
    assert len(calls) == 1
    assert calls[0].reason == "admin_correction"
    assert calls[0].participants[0].mu_before == pytest.approx(25.2)
    assert calls[0].participants[0].sigma_before == pytest.approx(8.25)
    assert calls[0].participants[1].mu_before == pytest.approx(24.8)
    assert calls[0].participants[1].sigma_before == pytest.approx(8.35)


@pytest.mark.anyio
async def test_edit_approved_match_new_roster_missing_player_raises(db_session, monkeypatch):
    team = Team(name="ms-team-8", is_active=True, is_approved=True)
    db_session.add(team)
    await db_session.flush()

    owner = Player(username="msowner8", password_hash="x", role=UserRole.owner, status=PlayerStatus.active, team_id=team.id)
    mate = Player(username="msplyr81", password_hash="x", role=UserRole.member, status=PlayerStatus.active, team_id=team.id)
    db_session.add_all([owner, mate])
    await db_session.flush()

    approved_match = Match(
        team_id=team.id,
        match_type=MatchType.internal,
        data_level=1,
        team_a_score=10,
        team_b_score=9,
        match_date=datetime.now(timezone.utc),
        status=MatchStatus.approved,
        created_by=owner.id,
        approved_by=owner.id,
        approved_at=datetime.now(timezone.utc),
    )
    db_session.add(approved_match)
    await db_session.flush()

    old_participant = MatchPlayer(match_id=approved_match.id, player_id=owner.id, team_side=TeamSide.A, mu_before=owner.mu, sigma_before=owner.sigma)
    db_session.add(old_participant)
    await db_session.commit()

    async def fake_revert(db, match, participants=None):
        return None

    monkeypatch.setattr(match_service, "revert_ratings", fake_revert)

    body = MatchUpdate(
        action="edit",
        score_us=15,
        score_them=10,
        team_a=[MatchPlayerEntry(player_id=owner.id)],
        team_b=[MatchPlayerEntry(player_id=999999)],
    )

    with pytest.raises(ValueError, match="球员 ID 不存在"):
        await edit_approved_match(db_session, approved_match.id, body, owner.id, team.id)
