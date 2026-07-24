"""Core /matches endpoints for submit, list, detail, moderation, and events."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_player, get_optional_player, require_admin
from app.core.database import get_db
from app.models.match import Match, MatchEvent, MatchPlayer, MatchSpiritScore, MatchStatus, MatchType
from app.models.player import Player, UserRole
from app.schemas.match import (
    MatchCreate,
    MatchDetailResponse,
    MatchEventItem,
    MatchListItem,
    MatchParticipant,
    MatchResponse,
    MatchUpdate,
    SpiritScoreRead,
    SpiritScoreUpsert,
)
from app.services.audit_service import build_change_detail, snapshot_fields, write_audit
from app.services.match_service import approve_match, create_match, edit_approved_match
from app.api.v1.endpoints.matches_drafts import (
    LOCK_LEASE_SECONDS,
    _cleanup_expired_drafts,
    _is_lock_expired,
    _lock_remaining_seconds,
    _seconds_until,
    _utcnow,
)

router = APIRouter()


@router.post("", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
async def submit_match(
    body: MatchCreate,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    """
    提交比赛记录。
    - admin/owner/superadmin 提交 -> 直接 approved，立即结算评分
    - 普通成员提交 -> pending_approval，等待管理员审批
    """
    is_admin = current_player.is_superadmin or current_player.role in (UserRole.admin, UserRole.owner)

    team_id = current_player.team_id
    if team_id is None:
        all_entries = body.team_a + body.team_b
        if not all_entries:
            raise HTTPException(status_code=400, detail="比赛数据为空")
        first_pid = all_entries[0].player_id
        p_result = await db.execute(select(Player).where(Player.id == first_pid))
        first_player = p_result.scalar_one_or_none()
        if not first_player or not first_player.team_id:
            raise HTTPException(status_code=400, detail="无法确定比赛所属队伍，请确保球员已加入队伍")
        team_id = first_player.team_id

    try:
        match = await create_match(
            db=db,
            body=body,
            created_by_id=current_player.id,
            team_id=team_id,
            auto_approve=is_admin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 关联日程活动
    if body.schedule_event_id is not None:
        from app.models.schedule import ScheduleEvent
        sev_res = await db.execute(
            select(ScheduleEvent).where(
                ScheduleEvent.id == body.schedule_event_id,
                ScheduleEvent.team_id == match.team_id,
            )
        )
        sev = sev_res.scalar_one_or_none()
        if sev:
            sev.linked_match_id = match.id
            if sev.title and not (match.notes and sev.title in match.notes):
                match.notes = f"[{sev.title}] {match.notes or ''}".strip()

    await write_audit(
        db,
        current_player,
        "match_created" if is_admin else "match_submitted",
        team_id=match.team_id,
        target_type="match",
        target_id=match.id,
        detail={
            "match_type": match.match_type.value,
            "data_level": match.data_level,
            "status": match.status.value,
            "score": f"{match.team_a_score}-{match.team_b_score}",
            "notes": match.notes or "",
        },
    )
    await db.commit()

    msg = "比赛已提交并结算评分" if is_admin else "比赛已提交，等待管理员审批"
    return MatchResponse(
        id=match.id,
        status=match.status.value,
        message=msg,
        requested_level=body.data_level,
        applied_level=match.data_level,
    )


@router.post("/{match_id}/approve", response_model=MatchResponse)
async def approve_match_endpoint(
    match_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
):
    """管理员审批并结算比赛评分"""
    try:
        match = await approve_match(db, match_id, admin.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await write_audit(
        db,
        admin,
        "match_approved",
        team_id=match.team_id,
        target_type="match",
        target_id=match.id,
        detail={"score": f"{match.team_a_score}-{match.team_b_score}"},
    )
    await db.commit()
    return MatchResponse(id=match.id, status=match.status.value, message="比赛审批通过，评分已结算")


@router.get("", response_model=list[MatchListItem])
async def list_matches(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    viewing_team_id: int | None = Query(None, alias="team_id"),
    db: AsyncSession = Depends(get_db),
    current_player: Player | None = Depends(get_optional_player),
):
    """
    列出比赛记录（T070）。
    - 已登录用户：可见详细信息
    - 未登录用户：返回空（保护数据隔离）
    """
    if current_player is None:
        return []

    if current_player.is_superadmin and viewing_team_id is not None:
        team_id_for_query = viewing_team_id
    else:
        team_id_for_query = current_player.team_id
    if team_id_for_query is None:
        return []

    await _cleanup_expired_drafts(db, team_id_for_query)
    q = select(Match).where(Match.team_id == team_id_for_query, Match.deleted_at.is_(None)).order_by(Match.match_date.desc())
    if status_filter:
        try:
            ms = MatchStatus(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"无效状态值: {status_filter}") from exc
        q = q.where(Match.status == ms)
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    matches = result.scalars().all()
    spirit_map: dict[int, MatchSpiritScore] = {}
    if matches:
        spirit_result = await db.execute(
            select(MatchSpiritScore).where(MatchSpiritScore.match_id.in_([m.id for m in matches]))
        )
        spirit_map = {row.match_id: row for row in spirit_result.scalars().all()}

    creator_ids = {m.created_by for m in matches if m.created_by} | {m.draft_owner_id for m in matches if m.draft_owner_id}
    creator_map: dict[int, Player] = {}
    if creator_ids:
        creator_result = await db.execute(select(Player).where(Player.id.in_(creator_ids)))
        creator_map = {player.id: player for player in creator_result.scalars().all()}

    now = _utcnow()
    return [
        ({
            "id": m.id,
            "match_type": m.match_type.value,
            "match_date": m.match_date.isoformat(),
            "team_a_score": m.team_a_score,
            "team_b_score": m.team_b_score,
            "status": m.status.value,
            "data_level": m.data_level,
            "notes": m.notes,
            "created_by_id": m.created_by,
            "created_by_name": (creator_map[m.created_by].display_name or creator_map[m.created_by].username)
            if m.created_by in creator_map
            else None,
            "duration_seconds": m.duration_seconds,
            "expires_at": m.expires_at.isoformat() if m.expires_at else None,
            "countdown_seconds": _seconds_until(m.expires_at, now),
            "lock_status": (
                "unlocked"
                if m.draft_owner_id is None
                else (
                    "lock_expired"
                    if _is_lock_expired(m, now)
                    else ("locked_by_me" if m.draft_owner_id == current_player.id else "locked_by_other")
                )
            ),
            "lock_owner_id": m.draft_owner_id,
            "lock_owner_name": None,
            "lock_expires_in_seconds": _lock_remaining_seconds(m.last_synced_at, now) if m.draft_owner_id else 0,
            "lock_lease_seconds": LOCK_LEASE_SECONDS,
            "spirit_scored": m.id in spirit_map,
            "spirit_total_score": spirit_map[m.id].total_score if m.id in spirit_map else None,
        } | ({
            "lock_owner_name": (creator_map[m.draft_owner_id].display_name or creator_map[m.draft_owner_id].username)
            if m.draft_owner_id in creator_map
            else None
        }))
        for m in matches
    ]


@router.get("/{match_id}", response_model=MatchDetailResponse)
async def get_match_detail(
    match_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    """获取比赛详情，含球员参与者列表（T069）"""
    q = select(Match).where(Match.id == match_id, Match.deleted_at.is_(None))
    if not current_player.is_superadmin:
        q = q.where(Match.team_id == current_player.team_id)
    result = await db.execute(q)
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    mp_result = await db.execute(select(MatchPlayer).where(MatchPlayer.match_id == match_id))
    participants = mp_result.scalars().all()
    spirit_record = (await db.execute(select(MatchSpiritScore).where(MatchSpiritScore.match_id == match_id))).scalar_one_or_none()

    player_ids = {mp.player_id for mp in participants}
    player_ids.add(match.created_by)
    players_result = await db.execute(select(Player).where(Player.id.in_(player_ids)))
    player_map: dict[int, Player] = {p.id: p for p in players_result.scalars().all()}

    def player_label(pid: int) -> str:
        p = player_map.get(pid)
        if not p:
            return f"#{pid}"
        return p.display_name or p.username

    is_admin = current_player.role in (UserRole.admin, UserRole.owner) or current_player.is_superadmin

    def serialize_mp(mp: MatchPlayer) -> MatchParticipant:
        d = {
            "player_id": mp.player_id,
            "player_name": player_label(mp.player_id),
            "team_side": mp.team_side.value,
            "goals": mp.goals,
            "assists": mp.assists,
            "defenses": mp.defenses,
            "turnovers": mp.turnovers,
            "plus_minus": mp.plus_minus,
            "is_mvp": mp.is_mvp,
        }
        if is_admin:
            d["mu_before"] = mp.mu_before
            d["sigma_before"] = mp.sigma_before
            d["mu_after"] = mp.mu_after
            d["sigma_after"] = mp.sigma_after
        return MatchParticipant(**d)

    return {
        "id": match.id,
        "match_type": match.match_type.value,
        "match_date": match.match_date.isoformat(),
        "team_a_score": match.team_a_score,
        "team_b_score": match.team_b_score,
        "status": match.status.value,
        "data_level": match.data_level,
        "notes": match.notes,
        "created_by_id": match.created_by,
        "created_by_name": player_label(match.created_by),
        "participants": [serialize_mp(mp) for mp in participants],
        "spirit_score": _serialize_spirit_score(spirit_record),
    }


@router.put("/{match_id}", response_model=MatchResponse)
async def update_match(
    match_id: int,
    body: MatchUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
):
    """
    管理员操作比赛：
    - action=approve：审批 pending_approval -> approved，触发评分结算
    - action=reject：将比赛置为 rejected
    - action=edit：修改已审批比赛数据，回退旧评分并重算
    """
    if body.action == "approve":
        try:
            match = await approve_match(db, match_id, admin.id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await write_audit(
            db,
            admin,
            "match_approved",
            team_id=match.team_id,
            target_type="match",
            target_id=match.id,
            detail=build_change_detail(extra={"score": f"{match.team_a_score}-{match.team_b_score}"}),
        )
        await db.commit()
        return MatchResponse(id=match.id, status=match.status.value, message="比赛审批通过，评分已结算")

    if body.action == "reject":
        q = select(Match).where(Match.id == match_id)
        if not admin.is_superadmin:
            q = q.where(Match.team_id == admin.team_id)
        result = await db.execute(q)
        match = result.scalar_one_or_none()
        if not match:
            raise HTTPException(status_code=404, detail="比赛不存在")
        if match.status != MatchStatus.pending_approval:
            raise HTTPException(status_code=400, detail="只能拒绝 pending_approval 状态的比赛")
        before_status = match.status.value
        match.status = MatchStatus.rejected
        await write_audit(
            db,
            admin,
            "match_rejected",
            team_id=match.team_id,
            target_type="match",
            target_id=match.id,
            detail=build_change_detail(
                before={"status": before_status},
                after={"status": match.status.value},
                extra={"score": f"{match.team_a_score}-{match.team_b_score}"},
            ),
        )
        await db.commit()
        await db.refresh(match, attribute_names=["id", "status"])
        return MatchResponse(id=match.id, status=match.status.value, message="比赛已拒绝")

    if body.action == "edit":
        pre_match = (await db.execute(select(Match).where(Match.id == match_id))).scalar_one_or_none()
        before_detail = None
        if pre_match and (admin.is_superadmin or pre_match.team_id == admin.team_id):
            before_detail = snapshot_fields(
                pre_match,
                ["team_a_score", "team_b_score", "data_level", "notes", "opponent_strength", "status"],
            )
        edit_team_id = admin.team_id
        if edit_team_id is None and pre_match is not None:
            edit_team_id = pre_match.team_id
        if edit_team_id is None:
            raise HTTPException(status_code=400, detail="无法确定比赛所属队伍")
        try:
            match = await edit_approved_match(db, match_id, body, admin.id, edit_team_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await write_audit(
            db,
            admin,
            "match_edited",
            team_id=match.team_id,
            target_type="match",
            target_id=match.id,
            detail=build_change_detail(
                before=before_detail,
                after=snapshot_fields(match, ["team_a_score", "team_b_score", "data_level", "notes", "opponent_strength", "status"]),
                extra={"recalculated": True},
            ),
        )
        await db.commit()
        return MatchResponse(id=match.id, status=match.status.value, message="比赛已更新，评分已重新结算")

    raise HTTPException(status_code=400, detail=f"未知 action: {body.action}")


@router.get("/{match_id}/spirit-score", response_model=SpiritScoreRead | None)
async def get_spirit_score(
    match_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    match = await _require_visible_match(db, match_id, current_player)
    if match.match_type != MatchType.external:
        raise HTTPException(status_code=400, detail="仅外战支持精神评分")
    record = (await db.execute(select(MatchSpiritScore).where(MatchSpiritScore.match_id == match_id))).scalar_one_or_none()
    return _serialize_spirit_score(record)


@router.put("/{match_id}/spirit-score", response_model=SpiritScoreRead)
async def upsert_spirit_score(
    match_id: int,
    body: SpiritScoreUpsert,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    match = await _require_visible_match(db, match_id, current_player)
    if match.match_type != MatchType.external:
        raise HTTPException(status_code=400, detail="仅外战支持精神评分")

    payload = body.model_dump()
    total_score = sum(payload[item]["score"] for item in ("rules", "contact", "fairness", "attitude", "communication"))
    record = (await db.execute(select(MatchSpiritScore).where(MatchSpiritScore.match_id == match_id))).scalar_one_or_none()
    if record is None:
        record = MatchSpiritScore(
            match_id=match_id,
            rules=payload["rules"]["score"],
            contact=payload["contact"]["score"],
            fairness=payload["fairness"]["score"],
            attitude=payload["attitude"]["score"],
            communication=payload["communication"]["score"],
            total_score=total_score,
            details_json=json.dumps(payload, ensure_ascii=False),
            created_by=current_player.id,
            updated_by=current_player.id,
        )
        db.add(record)
    else:
        record.rules = payload["rules"]["score"]
        record.contact = payload["contact"]["score"]
        record.fairness = payload["fairness"]["score"]
        record.attitude = payload["attitude"]["score"]
        record.communication = payload["communication"]["score"]
        record.total_score = total_score
        record.details_json = json.dumps(payload, ensure_ascii=False)
        record.updated_by = current_player.id
    await db.commit()
    await db.refresh(record)
    return _serialize_spirit_score(record)


@router.delete("/{match_id}", status_code=204)
async def delete_match(
    match_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
):
    """
    管理员删除比赛记录。
    - 若比赛已审批（approved），先回退评分再删除。
    - 删除操作同时清除相关 MatchPlayer、MatchEvent、RatingHistory 记录。
    """
    from sqlalchemy import delete as sa_delete

    from app.models.match import RatingHistory
    from app.services.match_service import revert_ratings

    q = select(Match).where(Match.id == match_id, Match.deleted_at.is_(None))
    if not admin.is_superadmin:
        q = q.where(Match.team_id == admin.team_id)
    result = await db.execute(q)
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    if match.status == MatchStatus.approved:
        await revert_ratings(db, match)

    await db.execute(sa_delete(RatingHistory).where(RatingHistory.match_id == match_id))
    await db.execute(sa_delete(MatchEvent).where(MatchEvent.match_id == match_id))
    await db.execute(sa_delete(MatchPlayer).where(MatchPlayer.match_id == match_id))
    await db.execute(sa_delete(MatchSpiritScore).where(MatchSpiritScore.match_id == match_id))
    await write_audit(
        db,
        admin,
        "match_deleted",
        team_id=match.team_id,
        target_type="match",
        target_id=match_id,
        detail={
            "status": match.status.value,
            "score": f"{match.team_a_score}-{match.team_b_score}",
            "notes": match.notes or "",
        },
    )
    await db.delete(match)
    await db.commit()


@router.get("/{match_id}/events", response_model=list[MatchEventItem])
async def get_match_events(
    match_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    """获取比赛时间轴事件流（T066）"""
    q = select(Match).where(Match.id == match_id)
    if not current_player.is_superadmin:
        q = q.where(Match.team_id == current_player.team_id)
    if not (await db.execute(q)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="比赛不存在")

    ev_result = await db.execute(
        select(MatchEvent)
        .where(MatchEvent.match_id == match_id, MatchEvent.deleted_at.is_(None))
        .order_by(MatchEvent.seq.asc(), MatchEvent.elapsed_seconds.asc())
    )
    events = ev_result.scalars().all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type.value,
            "team_side": e.team_side.value if e.team_side else None,
            "player_id": e.player_id,
            "assist_player_id": e.assist_player_id,
            "is_break": e.is_break,
            "elapsed_seconds": e.elapsed_seconds,
        }
        for e in events
    ]


async def _require_visible_match(db: AsyncSession, match_id: int, current_player: Player) -> Match:
    q = select(Match).where(Match.id == match_id, Match.deleted_at.is_(None))
    if not current_player.is_superadmin:
        q = q.where(Match.team_id == current_player.team_id)
    match = (await db.execute(q)).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return match


def _serialize_spirit_score(record: MatchSpiritScore | None) -> SpiritScoreRead | None:
    if record is None:
        return None
    raw = {}
    if record.details_json:
        try:
            raw = json.loads(record.details_json)
        except json.JSONDecodeError:
            raw = {}

    def dim(name: str, fallback_score: int) -> dict:
        part = raw.get(name) if isinstance(raw, dict) else None
        if not isinstance(part, dict):
            return {"score": fallback_score, "reasons": [], "note": None}
        return {
            "score": int(part.get("score", fallback_score)),
            "reasons": part.get("reasons", []) if isinstance(part.get("reasons", []), list) else [],
            "note": part.get("note"),
        }

    return SpiritScoreRead(
        rules=dim("rules", record.rules),
        contact=dim("contact", record.contact),
        fairness=dim("fairness", record.fairness),
        attitude=dim("attitude", record.attitude),
        communication=dim("communication", record.communication),
        total_score=record.total_score,
        note=(raw.get("note") if isinstance(raw, dict) else None),
        updated_by=record.updated_by,
        updated_at=record.updated_at.isoformat(),
    )
