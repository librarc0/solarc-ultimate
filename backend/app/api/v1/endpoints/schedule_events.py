"""日程事件 CRUD 端点"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import (
    get_current_active_player,
    get_effective_team_id,
    require_admin,
)
from app.core.database import get_db
from app.models.match import TeamPost
from app.models.player import Player, UserRole
from app.models.schedule import ScheduleEvent, ScheduleAttendance, ScheduleEventStatus, ScheduleEventType
from app.schemas.schedule import (
    ScheduleEventCreate,
    ScheduleEventListItem,
    ScheduleEventRead,
    ScheduleEventUpdate,
)
from app.services.audit_service import write_audit

router = APIRouter()

REMINDER_POST_PREFIX = "[系统催填]"


# ─── 查询日程列表（按日期范围，供日历渲染） ────────────────────────────────────────

@router.get("", response_model=list[ScheduleEventListItem])
async def list_events(
    start_date: date = Query(..., description="日期范围起始（含）"),
    end_date: date = Query(..., description="日期范围结束（含）"),
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
    team_id: int = Depends(get_effective_team_id),
):
    """获取指定日期范围内的所有日程（已登录成员可见，draft 仅管理员见）"""
    q = select(ScheduleEvent).where(
        ScheduleEvent.team_id == team_id,
        ScheduleEvent.start_date <= end_date,
        ScheduleEvent.end_date >= start_date,
    )
    is_admin = current_player.is_superadmin or current_player.role in (UserRole.admin, UserRole.owner)
    if not is_admin:
        q = q.where(ScheduleEvent.status == ScheduleEventStatus.published)

    result = await db.execute(q.order_by(ScheduleEvent.start_date, ScheduleEvent.id.desc()))
    events = result.scalars().all()

    player_count_res = await db.execute(
        select(func.count()).select_from(Player).where(
            Player.team_id == team_id,
            Player.status == "active",
        )
    )
    total_players = int(player_count_res.scalar_one())

    event_ids = [ev.id for ev in events]
    stats_by_event: dict[int, dict[str, int]] = {
        event_id: {"attendance_count": 0, "yes": 0, "sdl": 0, "leave": 0}
        for event_id in event_ids
    }
    if event_ids:
        att_stats_res = await db.execute(
            select(ScheduleAttendance.event_id, ScheduleAttendance.status, func.count())
            .where(ScheduleAttendance.event_id.in_(event_ids))
            .group_by(ScheduleAttendance.event_id, ScheduleAttendance.status)
        )
        for event_id, att_status, count in att_stats_res.all():
            status_key = att_status.value if hasattr(att_status, "value") else str(att_status)
            bucket = stats_by_event.setdefault(
                event_id,
                {"attendance_count": 0, "yes": 0, "sdl": 0, "leave": 0},
            )
            bucket["attendance_count"] += int(count)
            if status_key == "no":
                bucket["leave"] += int(count)
            elif status_key in bucket:
                bucket[status_key] = int(count)

    items = []
    for ev in events:
        stats = stats_by_event.get(ev.id, {"attendance_count": 0, "yes": 0, "sdl": 0, "leave": 0})
        attendance_count = int(stats.get("attendance_count", 0))
        items.append(
            ScheduleEventListItem(
                id=ev.id,
                title=ev.title,
                event_type=ev.event_type.value if hasattr(ev.event_type, 'value') else ev.event_type,
                start_date=ev.start_date,
                end_date=ev.end_date,
                status=ev.status.value if hasattr(ev.status, 'value') else ev.status,
                linked_match_id=ev.linked_match_id,
                attendance_count=attendance_count,
                total_players=total_players,
                yes_count=int(stats.get("yes", 0)),
                sdl_count=int(stats.get("sdl", 0)),
                leave_count=int(stats.get("leave", 0)),
                no_count=0,
                not_submitted_count=max(total_players - attendance_count, 0),
            )
        )
    return items


# ─── 创建日程（管理员） ─────────────────────────────────────────────────────────

@router.post("", response_model=ScheduleEventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: ScheduleEventCreate,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    ev = ScheduleEvent(
        team_id=team_id,
        title=body.title,
        event_type=ScheduleEventType(body.event_type),
        start_date=body.start_date,
        end_date=body.end_date,
        description=body.description,
        status=ScheduleEventStatus.draft,
        created_by=admin.id,
    )
    db.add(ev)
    await db.flush()
    await write_audit(
        db, admin, "schedule_event_created",
        team_id=team_id, target_type="schedule_event", target_id=ev.id,
        detail={"title": ev.title, "event_type": ev.event_type.value if hasattr(ev.event_type, 'value') else ev.event_type,
                "start_date": str(ev.start_date), "end_date": str(ev.end_date)},
    )
    await db.commit()
    await db.refresh(ev)
    return _to_read(ev)


# ─── 获取单个日程详情 ────────────────────────────────────────────────────────────

@router.get("/{event_id}", response_model=ScheduleEventRead)
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
    team_id: int = Depends(get_effective_team_id),
):
    ev = await _get_event_or_404(db, event_id, team_id)
    is_admin = current_player.is_superadmin or current_player.role in (UserRole.admin, UserRole.owner)
    if ev.status == ScheduleEventStatus.draft and not is_admin:
        raise HTTPException(status_code=404, detail="日程不存在")
    return _to_read(ev)


# ─── 更新日程（管理员，仅 draft 状态可全量编辑，published 只改描述） ──────────────────

@router.put("/{event_id}", response_model=ScheduleEventRead)
async def update_event(
    event_id: int,
    body: ScheduleEventUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    ev = await _get_event_or_404(db, event_id, team_id)
    if body.title is not None:
        ev.title = body.title
    if body.event_type is not None:
        ev.event_type = ScheduleEventType(body.event_type)
    if body.start_date is not None:
        ev.start_date = body.start_date
    if body.end_date is not None:
        ev.end_date = body.end_date
    if body.description is not None:
        ev.description = body.description
    ev.updated_at = datetime.now(timezone.utc)
    await write_audit(
        db, admin, "schedule_event_updated",
        team_id=team_id, target_type="schedule_event", target_id=ev.id,
        detail={"title": ev.title},
    )
    await db.commit()
    await db.refresh(ev)
    return _to_read(ev)


# ─── 发布 / 取消发布（管理员） ────────────────────────────────────────────────────

@router.post("/{event_id}/publish", response_model=ScheduleEventRead)
async def publish_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    ev = await _get_event_or_404(db, event_id, team_id)
    ev.status = ScheduleEventStatus.published
    ev.updated_at = datetime.now(timezone.utc)
    await write_audit(
        db, admin, "schedule_event_published",
        team_id=team_id, target_type="schedule_event", target_id=ev.id,
        detail={"title": ev.title},
    )
    await db.commit()
    await db.refresh(ev)
    return _to_read(ev)


@router.post("/{event_id}/unpublish", response_model=ScheduleEventRead)
async def unpublish_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    ev = await _get_event_or_404(db, event_id, team_id)
    ev.status = ScheduleEventStatus.draft
    ev.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ev)
    return _to_read(ev)


# ─── 删除日程（管理员） ─────────────────────────────────────────────────────────

@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    ev = await _get_event_or_404(db, event_id, team_id)
    await write_audit(
        db, admin, "schedule_event_deleted",
        team_id=team_id, target_type="schedule_event", target_id=ev.id,
        detail={"title": ev.title},
    )
    await db.delete(ev)
    await db.commit()


# ─── 催促未填写的队员（管理员，发 TeamPost 通知） ────────────────────────────────────

@router.post("/{event_id}/remind", status_code=status.HTTP_200_OK)
async def remind_attendance(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    """向本队所有『尚未提交出勤』的队员发送 TeamPost 提醒（出现在通知角标中）"""
    ev = await _get_event_or_404(db, event_id, team_id)
    if ev.status != ScheduleEventStatus.published:
        raise HTTPException(status_code=400, detail="仅已发布的日程可以推送催促通知")
    if ev.end_date < date.today():
        raise HTTPException(status_code=400, detail="活动已结束，无需再催填")

    submitted = await db.execute(
        select(ScheduleAttendance.player_id).where(ScheduleAttendance.event_id == event_id)
    )
    submitted_ids = {r for (r,) in submitted}

    active_p = await db.execute(
        select(Player).where(Player.team_id == team_id, Player.status == "active")
    )
    active_players = active_p.scalars().all()

    not_submitted = [p for p in active_players if p.id not in submitted_ids]
    if not not_submitted:
        return {"message": "所有队员均已提交出勤，无需催促", "reminded": 0}

    content = f"{REMINDER_POST_PREFIX} 请填写「{ev.title}」（{ev.start_date}）的出勤状态"
    db.add(TeamPost(team_id=team_id, author_id=admin.id, content=content, parent_id=None))
    await write_audit(
        db, admin, "schedule_event_reminded",
        team_id=team_id, target_type="schedule_event", target_id=ev.id,
        detail={"title": ev.title, "reminded": len(not_submitted)},
    )
    await db.commit()
    return {"message": "催填通知已发送", "reminded": len(not_submitted)}


@router.post("/remind/pending", status_code=status.HTTP_200_OK)
async def remind_pending_attendance(
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    """一键催填全部未来未结束且已发布的活动，只在通知中生成一条聚合提醒。"""
    today = date.today()
    events_res = await db.execute(
        select(ScheduleEvent)
        .where(
            ScheduleEvent.team_id == team_id,
            ScheduleEvent.status == ScheduleEventStatus.published,
            ScheduleEvent.end_date >= today,
        )
        .order_by(ScheduleEvent.start_date.asc(), ScheduleEvent.id.asc())
    )
    upcoming_events = events_res.scalars().all()
    if not upcoming_events:
        return {"message": "没有未来已发布活动需要催填", "reminded": 0, "events": 0}

    event_ids = [ev.id for ev in upcoming_events]
    submitted_res = await db.execute(
        select(ScheduleAttendance.event_id, ScheduleAttendance.player_id)
        .where(ScheduleAttendance.event_id.in_(event_ids))
    )
    submitted_by_event: dict[int, set[int]] = {event_id: set() for event_id in event_ids}
    for submitted_event_id, player_id in submitted_res.all():
        submitted_by_event.setdefault(submitted_event_id, set()).add(player_id)

    active_players_res = await db.execute(
        select(Player).where(Player.team_id == team_id, Player.status == "active")
    )
    active_players = active_players_res.scalars().all()

    pending_events = []
    reminded_player_ids: set[int] = set()
    for ev in upcoming_events:
        submitted_ids = submitted_by_event.get(ev.id, set())
        missing_players = [player for player in active_players if player.id not in submitted_ids]
        if missing_players:
            pending_events.append(ev)
            reminded_player_ids.update(player.id for player in missing_players)

    if not pending_events:
        return {"message": "所有未来活动都已完成填报，无需催填", "reminded": 0, "events": 0}

    preview = "；".join(f"{ev.start_date.isoformat()} {ev.title}" for ev in pending_events[:4])
    if len(pending_events) > 4:
        preview += f"；等 {len(pending_events)} 个活动"

    db.add(
        TeamPost(
            team_id=team_id,
            author_id=admin.id,
            content=f"{REMINDER_POST_PREFIX} 请尽快填写以下活动出勤：{preview}",
            parent_id=None,
        )
    )
    await write_audit(
        db, admin, "schedule_pending_reminded",
        team_id=team_id, target_type="schedule_event", target_id=None,
        detail={
            "event_ids": [ev.id for ev in pending_events],
            "events": len(pending_events),
            "reminded": len(reminded_player_ids),
        },
    )
    await db.commit()
    return {
        "message": f"已向 {len(reminded_player_ids)} 名未填队员发送未来活动催填提醒",
        "reminded": len(reminded_player_ids),
        "events": len(pending_events),
    }


# ─── 获取可关联日程（新建比赛时用 ）────────────────────────────────────────────────

@router.get("/for-match/linkable", response_model=list[dict])
@router.get("/linkable/for-match", response_model=list[dict], include_in_schema=False)
async def list_linkable_events(
    match_type: str | None = Query(default=None, pattern="^(internal|external)$"),
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    """获取可关联到比赛的已发布日程（外战→game，内战→internal；不传则返回全部可关联赛事）"""
    q = select(ScheduleEvent).where(
        ScheduleEvent.team_id == team_id,
        ScheduleEvent.status == ScheduleEventStatus.published,
    )

    if match_type is not None:
        event_type_map = {"external": "game", "internal": "internal"}
        q = q.where(ScheduleEvent.event_type == event_type_map[match_type])
    else:
        q = q.where(ScheduleEvent.event_type.in_(["game", "internal"]))

    result = await db.execute(q.order_by(ScheduleEvent.start_date.desc()))
    events = result.scalars().all()
    return [
        {
            "id": ev.id,
            "title": ev.title,
            "event_type": ev.event_type.value if hasattr(ev.event_type, 'value') else ev.event_type,
            "start_date": str(ev.start_date),
            "end_date": str(ev.end_date),
            "linked_match_id": ev.linked_match_id,
        }
        for ev in events
    ]


# ─── 内部工具函数 ────────────────────────────────────────────────────────────────

async def _get_event_or_404(db: AsyncSession, event_id: int, team_id: int) -> ScheduleEvent:
    result = await db.execute(
        select(ScheduleEvent).where(
            ScheduleEvent.id == event_id,
            ScheduleEvent.team_id == team_id,
        )
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="日程不存在")
    return ev


def _to_read(ev: ScheduleEvent) -> ScheduleEventRead:
    et = ev.event_type
    st = ev.status
    return ScheduleEventRead(
        id=ev.id,
        team_id=ev.team_id,
        title=ev.title,
        event_type=et.value if hasattr(et, 'value') else et,
        start_date=ev.start_date,
        end_date=ev.end_date,
        description=ev.description,
        status=st.value if hasattr(st, 'value') else st,
        created_by=ev.created_by,
        linked_match_id=ev.linked_match_id,
        created_at=ev.created_at,
        updated_at=ev.updated_at,
    )
