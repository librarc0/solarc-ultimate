"""Draft-related /matches endpoints and lock utilities."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy import delete as sa_delete
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_player, get_effective_team_id
from app.core.database import get_db
from app.models.match import Match, MatchEvent, MatchPlayer, MatchStatus, MatchType, TeamSide, EventType
from app.models.player import Player, UserRole
from app.schemas.match import (
    DraftCreate,
    DraftDetailResponse,
    DraftEventResponse,
    DraftEventCreate,
    DraftHeartbeatResponse,
    DraftLockResponse,
    DraftFinalizeRequest,
    DraftMatchItem,
    DraftSaveRequest,
    DraftTakeoverResponse,
    MatchResponse,
)
from app.services.audit_service import write_audit
from app.services.rating_service import apply_ratings

router = APIRouter()
LOCK_LEASE_SECONDS = 90


def _utcnow() -> datetime:
    # Keep compatibility with tests that monkeypatch app.api.v1.endpoints.matches._utcnow.
    from app.api.v1.endpoints import matches as matches_entry

    return matches_entry._utcnow()


def _to_json_text(data: dict | None) -> str | None:
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=False)


def _parse_json_text(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _seconds_until(target: datetime | None, now: datetime) -> int | None:
    if target is None:
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return int((target - now).total_seconds())


def _lock_deadline(last_synced_at: datetime | None) -> datetime | None:
    if last_synced_at is None:
        return None
    if last_synced_at.tzinfo is None:
        last_synced_at = last_synced_at.replace(tzinfo=timezone.utc)
    return last_synced_at + timedelta(seconds=LOCK_LEASE_SECONDS)


def _lock_remaining_seconds(last_synced_at: datetime | None, now: datetime) -> int:
    deadline = _lock_deadline(last_synced_at)
    if deadline is None:
        return 0
    return max(0, int((deadline - now).total_seconds()))


def _is_lock_expired(match: Match, now: datetime) -> bool:
    if match.draft_owner_id is None:
        return True
    return _lock_remaining_seconds(match.last_synced_at, now) <= 0


async def _cleanup_expired_drafts(db: AsyncSession, team_id: int | None = None) -> int:
    now = _utcnow()
    q = select(Match).where(
        Match.status == MatchStatus.draft,
        Match.deleted_at.is_(None),
        Match.expires_at.is_not(None),
        Match.expires_at < now,
    )
    if team_id is not None:
        q = q.where(Match.team_id == team_id)
    result = await db.execute(q)
    expired = result.scalars().all()
    for m in expired:
        m.deleted_at = now
    if expired:
        await db.flush()
    return len(expired)


async def _get_visible_match_or_404(db: AsyncSession, match_id: int, current_player: Player) -> Match:
    q = select(Match).where(Match.id == match_id, Match.deleted_at.is_(None))
    if not current_player.is_superadmin:
        q = q.where(Match.team_id == current_player.team_id)
    match = (await db.execute(q)).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return match


async def _player_display_name(db: AsyncSession, player_id: int | None) -> str:
    if not player_id:
        return "其他队员"
    player = (await db.execute(select(Player).where(Player.id == player_id))).scalar_one_or_none()
    if not player:
        return "其他队员"
    return player.display_name or player.username


async def _acquire_draft_lock_or_409(db: AsyncSession, match: Match, current_player: Player) -> Match:
    if match.status != MatchStatus.draft or match.deleted_at is not None:
        raise HTTPException(status_code=400, detail="该草稿已终结")

    now = _utcnow()
    lease_expire_before = now - timedelta(seconds=LOCK_LEASE_SECONDS)

    if match.draft_owner_id == current_player.id:
        match.last_synced_at = now
        match.expires_at = now + timedelta(hours=48)
        await db.commit()
        return match

    if match.draft_owner_id is None or _is_lock_expired(match, now):
        lock_result = await db.execute(
            sa_update(Match)
            .where(
                Match.id == match.id,
                Match.status == MatchStatus.draft,
                Match.deleted_at.is_(None),
                or_(
                    Match.draft_owner_id.is_(None),
                    Match.last_synced_at.is_(None),
                    Match.last_synced_at < lease_expire_before,
                ),
            )
            .values(
                draft_owner_id=current_player.id,
                last_synced_at=now,
                expires_at=now + timedelta(hours=48),
            )
        )
        if (getattr(lock_result, "rowcount", 0) or 0) > 0:
            await db.commit()
            refreshed = await _get_visible_match_or_404(db, match.id, current_player)
            return refreshed

    latest = await _get_visible_match_or_404(db, match.id, current_player)
    if latest.draft_owner_id != current_player.id:
        locker_name = await _player_display_name(db, latest.draft_owner_id)
        remaining = _lock_remaining_seconds(latest.last_synced_at, now)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DRAFT_LOCKED",
                "message": "正在有人录入该比赛",
                "locked_by": locker_name,
                "lock_expires_in_seconds": remaining,
            },
        )
    return latest


@router.post("/drafts", response_model=DraftMatchItem, status_code=status.HTTP_201_CREATED)
async def create_match_draft(
    body: DraftCreate,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    if not body.team_a_ids:
        raise HTTPException(status_code=400, detail="队A至少需要1名球员")
    if body.match_type == "internal" and not body.team_b_ids:
        raise HTTPException(status_code=400, detail="内战需要队B球员")

    all_ids = list(dict.fromkeys(body.team_a_ids + body.team_b_ids))
    players = (await db.execute(select(Player).where(Player.id.in_(all_ids)))).scalars().all()
    player_map = {p.id: p for p in players}
    missing = set(all_ids) - set(player_map.keys())
    if missing:
        raise HTTPException(status_code=400, detail=f"球员不存在: {sorted(missing)}")

    team_id = current_player.team_id
    if current_player.is_superadmin:
        first = player_map.get(body.team_a_ids[0])
        if not first or not first.team_id:
            raise HTTPException(status_code=400, detail="无法确定队伍")
        team_id = first.team_id
    if team_id is None:
        raise HTTPException(status_code=400, detail="无法确定队伍")

    now = _utcnow()
    match = Match(
        team_id=team_id,
        match_type=MatchType(body.match_type),
        data_level=body.data_level,
        team_a_score=0,
        team_b_score=0,
        opponent_strength=body.opponent_strength,
        match_date=now.replace(year=body.match_date.year, month=body.match_date.month, day=body.match_date.day),
        status=MatchStatus.draft,
        created_by=current_player.id,
        draft_owner_id=None,
        notes=body.notes,
        duration_seconds=0,
        last_event_seq=0,
        last_synced_at=now,
        saved_at=now,
        expires_at=now + timedelta(hours=48),
        draft_snapshot_json=_to_json_text({"score_a": 0, "score_b": 0, "is_halftime": False}),
    )
    db.add(match)
    await db.flush()

    for pid in body.team_a_ids:
        p = player_map[pid]
        db.add(
            MatchPlayer(
                match_id=match.id,
                player_id=pid,
                team_side=TeamSide.A,
                goals=0,
                assists=0,
                defenses=0,
                turnovers=0,
                is_mvp=False,
                mu_before=p.mu,
                sigma_before=p.sigma,
            )
        )
    for pid in body.team_b_ids:
        p = player_map[pid]
        db.add(
            MatchPlayer(
                match_id=match.id,
                player_id=pid,
                team_side=TeamSide.B,
                goals=0,
                assists=0,
                defenses=0,
                turnovers=0,
                is_mvp=False,
                mu_before=p.mu,
                sigma_before=p.sigma,
            )
        )

    await write_audit(
        db,
        current_player,
        "match_draft_created",
        team_id=team_id,
        target_type="match",
        target_id=match.id,
        detail={"team_a_count": len(body.team_a_ids), "team_b_count": len(body.team_b_ids), "match_type": body.match_type},
    )
    await db.commit()
    return DraftMatchItem(
        id=match.id,
        match_type=match.match_type.value,
        match_date=match.match_date.isoformat(),
        team_a_score=match.team_a_score,
        team_b_score=match.team_b_score,
        status=match.status.value,
        data_level=match.data_level,
        notes=match.notes,
        duration_seconds=match.duration_seconds,
        expires_at=match.expires_at.isoformat() if match.expires_at else None,
        countdown_seconds=_seconds_until(match.expires_at, now),
    )


@router.get("/drafts/active", response_model=list[DraftMatchItem])
async def list_active_drafts(
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
    effective_team_id: int = Depends(get_effective_team_id),
):
    await _cleanup_expired_drafts(db, effective_team_id)
    q = select(Match).where(
        Match.status == MatchStatus.draft,
        Match.deleted_at.is_(None),
        Match.team_id == effective_team_id,
    )

    result = await db.execute(q.order_by(Match.updated_at.desc()))
    now = _utcnow()
    return [
        DraftMatchItem(
            id=m.id,
            match_type=m.match_type.value,
            match_date=m.match_date.isoformat(),
            team_a_score=m.team_a_score,
            team_b_score=m.team_b_score,
            status=m.status.value,
            data_level=m.data_level,
            notes=m.notes,
            duration_seconds=m.duration_seconds,
            expires_at=m.expires_at.isoformat() if m.expires_at else None,
            countdown_seconds=_seconds_until(m.expires_at, now),
        )
        for m in result.scalars().all()
    ]


@router.get("/drafts/{match_id}", response_model=DraftDetailResponse)
async def get_draft_detail(
    match_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    await _cleanup_expired_drafts(db, current_player.team_id)
    match = await _get_visible_match_or_404(db, match_id, current_player)

    is_admin = current_player.is_superadmin or current_player.role in (UserRole.admin, UserRole.owner)
    if not is_admin and match.created_by != current_player.id and match.draft_owner_id != current_player.id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "DRAFT_TAKEOVER_REQUIRED",
                "message": "该未完成比赛由其他队员创建，请先接管后再继续录入",
            },
        )

    match = await _acquire_draft_lock_or_409(db, match, current_player)

    players = (await db.execute(select(MatchPlayer).where(MatchPlayer.match_id == match.id))).scalars().all()
    team_a_ids = [p.player_id for p in players if p.team_side == TeamSide.A]
    team_b_ids = [p.player_id for p in players if p.team_side == TeamSide.B]

    events = (
        await db.execute(
            select(MatchEvent)
            .where(MatchEvent.match_id == match.id, MatchEvent.deleted_at.is_(None))
            .order_by(MatchEvent.seq.asc(), MatchEvent.elapsed_seconds.asc())
        )
    ).scalars().all()

    return DraftDetailResponse(
        id=match.id,
        match_type=match.match_type.value,
        match_date=match.match_date.isoformat(),
        team_a_ids=team_a_ids,
        team_b_ids=team_b_ids,
        team_a_score=match.team_a_score,
        team_b_score=match.team_b_score,
        status=match.status.value,
        data_level=match.data_level,
        notes=match.notes,
        duration_seconds=match.duration_seconds,
        last_event_seq=match.last_event_seq,
        expires_at=match.expires_at.isoformat() if match.expires_at else None,
        snapshot=_parse_json_text(match.draft_snapshot_json),
        events=[
            DraftEventResponse(
                id=e.id,
                seq=e.seq or 0,
                event_type=e.event_type.value,
                team_side=e.team_side.value if e.team_side else None,
                player_id=e.player_id,
                assist_player_id=e.assist_player_id,
                is_break=e.is_break,
                elapsed_seconds=e.elapsed_seconds,
                payload=_parse_json_text(e.payload_json),
            )
            for e in events
        ],
    )


@router.post("/drafts/{match_id}/events")
async def append_draft_event(
    match_id: int,
    body: DraftEventCreate,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    match = await _get_visible_match_or_404(db, match_id, current_player)
    match = await _acquire_draft_lock_or_409(db, match, current_player)

    existing = (
        await db.execute(
            select(MatchEvent).where(
                MatchEvent.match_id == match.id,
                MatchEvent.client_event_id == body.client_event_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return {"accepted": True, "duplicate": True, "last_event_seq": match.last_event_seq}

    expected = match.last_event_seq + 1
    if body.seq != expected:
        raise HTTPException(status_code=409, detail={"message": "seq冲突", "last_event_seq": match.last_event_seq})

    try:
        event_type = EventType(body.event_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="无效 event_type") from exc

    event = MatchEvent(
        match_id=match.id,
        event_type=event_type,
        team_side=TeamSide(body.team_side) if body.team_side else None,
        player_id=body.player_id,
        assist_player_id=body.assist_player_id,
        is_break=body.is_break,
        elapsed_seconds=body.elapsed_seconds,
        seq=body.seq,
        client_event_id=body.client_event_id,
        event_version=1,
        payload_json=_to_json_text(body.payload),
        created_by=current_player.id,
        source="live",
    )
    db.add(event)

    if body.payload:
        score_a = body.payload.get("score_a")
        score_b = body.payload.get("score_b")
        if isinstance(score_a, int):
            match.team_a_score = score_a
        if isinstance(score_b, int):
            match.team_b_score = score_b

    if body.elapsed_seconds is not None:
        match.duration_seconds = max(match.duration_seconds or 0, body.elapsed_seconds)
    match.last_event_seq = body.seq
    now = _utcnow()
    match.last_synced_at = now
    match.expires_at = now + timedelta(hours=48)
    match.draft_snapshot_json = _to_json_text(
        {
            "score_a": match.team_a_score,
            "score_b": match.team_b_score,
            "elapsed_seconds": match.duration_seconds or 0,
            **(body.payload or {}),
        }
    )
    await db.commit()
    return {
        "accepted": True,
        "match_id": match.id,
        "event_id": event.id,
        "last_event_seq": match.last_event_seq,
        "snapshot": _parse_json_text(match.draft_snapshot_json),
    }


@router.post("/drafts/{match_id}/save")
async def save_draft_state(
    match_id: int,
    body: DraftSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    match = await _get_visible_match_or_404(db, match_id, current_player)
    match = await _acquire_draft_lock_or_409(db, match, current_player)

    if body.elapsed_seconds is not None:
        match.duration_seconds = max(match.duration_seconds or 0, body.elapsed_seconds)
    if body.score_a is not None:
        match.team_a_score = body.score_a
    if body.score_b is not None:
        match.team_b_score = body.score_b

    snapshot = _parse_json_text(match.draft_snapshot_json) or {}
    if body.is_halftime is not None:
        snapshot["is_halftime"] = body.is_halftime
    if body.possession is not None:
        snapshot["possession"] = body.possession
    snapshot["score_a"] = match.team_a_score
    snapshot["score_b"] = match.team_b_score
    snapshot["elapsed_seconds"] = match.duration_seconds or 0
    match.draft_snapshot_json = _to_json_text(snapshot)

    now = _utcnow()
    match.created_by = current_player.id
    match.draft_owner_id = None
    match.saved_at = now
    match.last_synced_at = now
    match.expires_at = now + timedelta(hours=48)
    await db.commit()
    saved_at = None
    expires_at = None
    saved_at_obj = match.saved_at
    expires_at_obj = match.expires_at
    if saved_at_obj is not None:
        saved_at = saved_at_obj.isoformat()
    if expires_at_obj is not None:
        expires_at = expires_at_obj.isoformat()
    return {
        "match_id": match.id,
        "status": "in_progress",
        "saved_at": saved_at,
        "elapsed_seconds": match.duration_seconds or 0,
        "expires_at": expires_at,
    }


@router.post("/drafts/{match_id}/finalize", response_model=MatchResponse)
async def finalize_draft_match(
    match_id: int,
    body: DraftFinalizeRequest,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    match = await _get_visible_match_or_404(db, match_id, current_player)
    match = await _acquire_draft_lock_or_409(db, match, current_player)

    participants = list((
        await db.execute(select(MatchPlayer).where(MatchPlayer.match_id == match.id))
    ).scalars().all())
    events = (
        await db.execute(select(MatchEvent).where(MatchEvent.match_id == match.id, MatchEvent.deleted_at.is_(None)))
    ).scalars().all()

    goals: dict[int, int] = {}
    assists: dict[int, int] = {}
    defenses: dict[int, int] = {}
    turnovers: dict[int, int] = {}
    for e in events:
        if e.event_type == EventType.goal and e.player_id is not None:
            goals[e.player_id] = goals.get(e.player_id, 0) + 1
            if e.assist_player_id is not None:
                assists[e.assist_player_id] = assists.get(e.assist_player_id, 0) + 1
        elif e.event_type == EventType.defense and e.player_id is not None:
            defenses[e.player_id] = defenses.get(e.player_id, 0) + 1
        elif e.event_type == EventType.turnover and e.player_id is not None:
            turnovers[e.player_id] = turnovers.get(e.player_id, 0) + 1

    for p in participants:
        p.goals = goals.get(p.player_id, 0)
        p.assists = assists.get(p.player_id, 0)
        p.defenses = defenses.get(p.player_id, 0)
        p.turnovers = turnovers.get(p.player_id, 0)

    is_admin = current_player.is_superadmin or current_player.role in (UserRole.admin, UserRole.owner)
    match.notes = body.notes or match.notes
    match.deleted_at = None
    match.created_by = current_player.id
    match.draft_owner_id = None
    if is_admin:
        match.status = MatchStatus.approved
        match.approved_by = current_player.id
        match.approved_at = _utcnow()
        await apply_ratings(db, match, operated_by=current_player.id, participants=participants)
    else:
        match.status = MatchStatus.pending_approval
        match.approved_by = None
        match.approved_at = None

    await write_audit(
        db,
        current_player,
        "match_draft_finalized" if is_admin else "match_draft_submitted",
        team_id=match.team_id,
        target_type="match",
        target_id=match.id,
        detail={"score": f"{match.team_a_score}-{match.team_b_score}", "events": len(events)},
    )
    await db.commit()
    return MatchResponse(
        id=match.id,
        status=match.status.value,
        message="比赛已结束并结算评分" if is_admin else "比赛已提交，等待管理员审核",
    )


@router.post("/drafts/{match_id}/abandon")
async def abandon_draft_match(
    match_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    match = await _get_visible_match_or_404(db, match_id, current_player)
    if match.status != MatchStatus.draft or match.deleted_at is not None:
        raise HTTPException(status_code=400, detail="该草稿已终结")

    is_admin = current_player.is_superadmin or current_player.role in (UserRole.admin, UserRole.owner)
    if not is_admin and match.created_by != current_player.id:
        raise HTTPException(status_code=403, detail="只能放弃自己创建或已接管的未完成比赛")

    if not is_admin:
        match = await _acquire_draft_lock_or_409(db, match, current_player)

    await write_audit(
        db,
        current_player,
        "match_draft_abandoned",
        team_id=match.team_id,
        target_type="match",
        target_id=match.id,
        detail={"last_event_seq": match.last_event_seq},
    )

    await db.execute(sa_delete(MatchEvent).where(MatchEvent.match_id == match.id))
    await db.execute(sa_delete(MatchPlayer).where(MatchPlayer.match_id == match.id))
    await db.delete(match)
    await db.commit()
    return {"ok": True}


@router.post("/drafts/{match_id}/release", response_model=DraftLockResponse)
async def release_draft_lock(
    match_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    match = await _get_visible_match_or_404(db, match_id, current_player)
    if match.status != MatchStatus.draft:
        return {"ok": True}
    if match.draft_owner_id != current_player.id:
        return {"ok": True}
    match.draft_owner_id = None
    match.saved_at = _utcnow()
    await db.commit()
    return {"ok": True}


@router.post("/drafts/{match_id}/heartbeat", response_model=DraftHeartbeatResponse)
async def renew_draft_lock(
    match_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    match = await _get_visible_match_or_404(db, match_id, current_player)
    match = await _acquire_draft_lock_or_409(db, match, current_player)
    now = _utcnow()
    return {
        "ok": True,
        "lock_expires_in_seconds": _lock_remaining_seconds(match.last_synced_at, now),
        "lock_lease_seconds": LOCK_LEASE_SECONDS,
    }


@router.post("/drafts/{match_id}/takeover", response_model=DraftTakeoverResponse)
async def takeover_draft_lock(
    match_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    match = await _get_visible_match_or_404(db, match_id, current_player)
    if match.status != MatchStatus.draft or match.deleted_at is not None:
        raise HTTPException(status_code=400, detail="该草稿已终结")

    now = _utcnow()
    if match.draft_owner_id == current_player.id:
        match.created_by = current_player.id
        match.last_synced_at = now
        match.expires_at = now + timedelta(hours=48)
        await db.commit()
        return {"ok": True, "takeover": False, "message": "已是当前录入者"}

    if match.draft_owner_id and not _is_lock_expired(match, now):
        locker_name = await _player_display_name(db, match.draft_owner_id)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DRAFT_LOCKED",
                "message": "正在有人录入该比赛",
                "locked_by": locker_name,
                "lock_expires_in_seconds": _lock_remaining_seconds(match.last_synced_at, now),
            },
        )

    prev_owner = match.draft_owner_id
    prev_creator = match.created_by
    match.draft_owner_id = current_player.id
    match.created_by = current_player.id
    match.last_synced_at = now
    match.expires_at = now + timedelta(hours=48)
    await write_audit(
        db,
        current_player,
        "match_draft_lock_takeover",
        team_id=match.team_id,
        target_type="match",
        target_id=match.id,
        detail={"previous_owner_id": prev_owner, "previous_creator_id": prev_creator},
    )
    await db.commit()
    return {"ok": True, "takeover": True}
