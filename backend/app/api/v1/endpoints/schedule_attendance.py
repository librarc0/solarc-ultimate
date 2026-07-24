"""出勤记录端点：球员提交/更新出勤，管理员查汇总"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import (
    get_current_active_player,
    get_effective_team_id,
    require_admin,
)
from app.core.database import get_db
from app.models.player import Player, PlayerStatus, UserRole
from app.models.schedule import AttendanceStatus, ScheduleAttendance, ScheduleEvent, ScheduleEventStatus
from app.schemas.schedule import AttendanceRead, AttendanceSummary, AttendanceSubmit

router = APIRouter()


def _enum_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _normalize_attendance_status(value: object) -> str:
    raw = _enum_value(value)
    return "leave" if raw == "no" else raw


# ─── 球员提交 / 更新本人出勤 ────────────────────────────────────────────────────

@router.put("/{event_id}/me", response_model=AttendanceRead, status_code=status.HTTP_200_OK)
async def submit_my_attendance(
    event_id: int,
    body: AttendanceSubmit,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    """球员提交或更新自己对指定日程的出勤状态"""
    if current_player.team_id is None:
        raise HTTPException(status_code=403, detail="请先加入队伍")

    # 普通队员只能对已发布日程提交；管理员可在 draft 阶段提前维护
    ev_res = await db.execute(
        select(ScheduleEvent).where(
            ScheduleEvent.id == event_id,
            ScheduleEvent.team_id == current_player.team_id,
        )
    )
    ev = ev_res.scalar_one_or_none()
    is_admin = current_player.is_superadmin or current_player.role in (UserRole.admin, UserRole.owner)
    if not ev or (ev.status != ScheduleEventStatus.published and not is_admin):
        raise HTTPException(status_code=404, detail="日程不存在或尚未发布")

    # 幂等 upsert：已有则更新，无则创建
    att_res = await db.execute(
        select(ScheduleAttendance).where(
            ScheduleAttendance.event_id == event_id,
            ScheduleAttendance.player_id == current_player.id,
        )
    )
    att = att_res.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    normalized_status = AttendanceStatus.leave if body.status == "no" else AttendanceStatus(body.status)
    if att:
        att.status = normalized_status
        att.updated_at = now
    else:
        att = ScheduleAttendance(
            event_id=event_id,
            player_id=current_player.id,
            status=normalized_status,
            submitted_at=now,
            updated_at=now,
        )
        db.add(att)

    await db.commit()
    await db.refresh(att)
    return AttendanceRead(
        id=att.id,
        event_id=att.event_id,
        player_id=att.player_id,
        player_name=current_player.username,
        player_display_name=current_player.display_name,
        status=_normalize_attendance_status(att.status),
        submitted_at=att.submitted_at,
        updated_at=att.updated_at,
    )


# ─── 球员查看自己的出勤状态 ────────────────────────────────────────────────────────

@router.get("/{event_id}/me", response_model=AttendanceRead | None)
async def get_my_attendance(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    if current_player.team_id is None:
        raise HTTPException(status_code=403, detail="请先加入队伍")

    att_res = await db.execute(
        select(ScheduleAttendance).where(
            ScheduleAttendance.event_id == event_id,
            ScheduleAttendance.player_id == current_player.id,
        )
    )
    att = att_res.scalar_one_or_none()
    if not att:
        return None
    return AttendanceRead(
        id=att.id,
        event_id=att.event_id,
        player_id=att.player_id,
        player_name=current_player.username,
        player_display_name=current_player.display_name,
        status=_normalize_attendance_status(att.status),
        submitted_at=att.submitted_at,
        updated_at=att.updated_at,
    )


# ─── 管理员查看出勤汇总 ────────────────────────────────────────────────────────────

@router.get("/{event_id}/summary", response_model=AttendanceSummary)
async def get_attendance_summary(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    """管理员查看指定日程的所有队员出勤汇总（含未提交人员列表）"""
    ev_res = await db.execute(
        select(ScheduleEvent).where(
            ScheduleEvent.id == event_id,
            ScheduleEvent.team_id == team_id,
        )
    )
    ev = ev_res.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="日程不存在")

    # 全队活跃成员
    players_res = await db.execute(
        select(Player).where(
            Player.team_id == team_id,
            Player.status == PlayerStatus.active,
        )
    )
    all_players = players_res.scalars().all()
    player_map = {p.id: p for p in all_players}

    # 所有出勤记录
    att_res = await db.execute(
        select(ScheduleAttendance).where(ScheduleAttendance.event_id == event_id)
    )
    attendances = att_res.scalars().all()
    submitted_ids = {a.player_id for a in attendances}

    def _to_att_read(att: ScheduleAttendance) -> AttendanceRead:
        p = player_map.get(att.player_id)
        return AttendanceRead(
            id=att.id,
            event_id=att.event_id,
            player_id=att.player_id,
            player_name=p.username if p else str(att.player_id),
            player_display_name=p.display_name if p else None,
            status=_normalize_attendance_status(att.status),
            submitted_at=att.submitted_at,
            updated_at=att.updated_at,
        )

    summary = AttendanceSummary(event_id=event_id)
    for att in attendances:
        att_read = _to_att_read(att)
        att_status = _normalize_attendance_status(att.status)
        if att_status == "yes":
            summary.yes.append(att_read)
        elif att_status == "leave":
            summary.leave.append(att_read)
        elif att_status == "sdl":
            summary.sdl.append(att_read)

    summary.not_submitted = [
        {"player_id": p.id, "player_name": p.username, "display_name": p.display_name}
        for p in all_players
        if p.id not in submitted_ids
    ]
    return summary


# ─── 管理员查看某球员的出勤（供管理员手动添加 line 时参考） ─────────────────────────────

@router.get("/{event_id}/players/{player_id}", response_model=AttendanceRead | None)
async def get_player_attendance(
    event_id: int,
    player_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    # 确认目标球员属于同一队伍
    p_res = await db.execute(select(Player).where(Player.id == player_id, Player.team_id == team_id))
    p = p_res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="球员不存在")

    att_res = await db.execute(
        select(ScheduleAttendance).where(
            ScheduleAttendance.event_id == event_id,
            ScheduleAttendance.player_id == player_id,
        )
    )
    att = att_res.scalar_one_or_none()
    if not att:
        return None
    return AttendanceRead(
        id=att.id,
        event_id=att.event_id,
        player_id=att.player_id,
        player_name=p.username,
        player_display_name=p.display_name,
        status=_normalize_attendance_status(att.status),
        submitted_at=att.submitted_at,
        updated_at=att.updated_at,
    )
