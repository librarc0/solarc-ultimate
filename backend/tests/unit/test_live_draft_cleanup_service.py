import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.audit import AuditLog
from app.models.match import Match, MatchStatus, MatchType
from app.models.player import Player, PlayerStatus, UserRole
from app.models.team import Team
from app.services import live_draft_cleanup_service as cleanup_service


def _fixed_now() -> datetime:
    return datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)


async def _build_fixture_data(SessionLocal):
    async with SessionLocal() as session:
        team = Team(name="Cleanup Team", is_active=True, is_approved=True)
        session.add(team)
        await session.flush()

        owner = Player(
            team_id=team.id,
            username="cleanup_owner",
            password_hash="hashed",
            email="cleanup_owner@test.com",
            role=UserRole.owner,
            status=PlayerStatus.active,
            is_superadmin=False,
        )
        session.add(owner)
        await session.flush()

        expired = Match(
            team_id=team.id,
            match_type=MatchType.external,
            data_level=3,
            team_a_score=0,
            team_b_score=0,
            match_date=_fixed_now(),
            status=MatchStatus.draft,
            created_by=owner.id,
            draft_owner_id=None,
            last_event_seq=0,
            expires_at=_fixed_now() - timedelta(minutes=1),
            deleted_at=None,
        )
        active = Match(
            team_id=team.id,
            match_type=MatchType.external,
            data_level=3,
            team_a_score=0,
            team_b_score=0,
            match_date=_fixed_now(),
            status=MatchStatus.draft,
            created_by=owner.id,
            draft_owner_id=None,
            last_event_seq=0,
            expires_at=_fixed_now() + timedelta(minutes=10),
            deleted_at=None,
        )
        session.add_all([expired, active])
        await session.commit()

        return expired.id, active.id


async def test_cleanup_expired_drafts_once_marks_expired_and_writes_audit(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            import app.models  # noqa: F401

            await conn.run_sync(Base.metadata.create_all)

        expired_id, active_id = await _build_fixture_data(SessionLocal)

        monkeypatch.setattr(cleanup_service, "AsyncSessionLocal", SessionLocal)
        monkeypatch.setattr(cleanup_service, "utcnow", _fixed_now)

        cleaned = await cleanup_service.cleanup_expired_drafts_once()
        assert cleaned == 1

        async with SessionLocal() as session:
            expired = (await session.execute(select(Match).where(Match.id == expired_id))).scalar_one()
            active = (await session.execute(select(Match).where(Match.id == active_id))).scalar_one()
            logs = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "match_draft_expired_deleted",
                        AuditLog.target_id == expired_id,
                    )
                )
            ).scalars().all()

        assert expired.deleted_at is not None
        assert expired.deleted_at.replace(tzinfo=timezone.utc) == _fixed_now()
        assert active.deleted_at is None
        assert len(logs) >= 1
    finally:
        await engine.dispose()


async def test_run_live_draft_cleanup_loop_stops_when_event_set(monkeypatch):
    calls = {"count": 0}

    async def fake_cleanup_once():
        calls["count"] += 1
        return 0

    monkeypatch.setattr(cleanup_service, "cleanup_expired_drafts_once", fake_cleanup_once)
    monkeypatch.setattr(cleanup_service, "CLEANUP_INTERVAL_SECONDS", 0.05)

    stop_event = asyncio.Event()
    task = asyncio.create_task(cleanup_service.run_live_draft_cleanup_loop(stop_event))
    await asyncio.sleep(0.12)
    stop_event.set()
    await task

    assert calls["count"] >= 1


async def test_stop_cleanup_task_cancels_task_and_sets_event():
    stop_event = asyncio.Event()
    task = asyncio.create_task(asyncio.sleep(5))

    await cleanup_service.stop_cleanup_task(task, stop_event)

    assert stop_event.is_set()
    assert task.done()
