"""/team posts and notifications endpoints."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_player, require_superadmin
from app.core.database import get_db
from app.models.match import TeamPost
from app.models.membership import PlayerTeamMembership
from app.models.player import Player, PlayerStatus, UserRole
from app.models.team import Team
from app.services.audit_service import build_change_detail, write_audit

router = APIRouter()

HIDDEN_REMINDER_PREFIXES = ("[出勤提醒]", "[系统催填]")


def _exclude_hidden_reminders(stmt):
    for prefix in HIDDEN_REMINDER_PREFIXES:
        stmt = stmt.where(~TeamPost.content.like(f"{prefix}%"))
    return stmt


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class PostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: int | None = None


class BroadcastNoticeRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    team_ids: list[int] = Field(default_factory=list)


class BroadcastNoticeResponse(BaseModel):
    team_count: int
    target_team_ids: list[int]


class PostRead(BaseModel):
    id: int
    author_id: int
    author_name: str
    content: str
    parent_id: int | None = None
    created_at: datetime
    replies: list["PostRead"] = []


PostRead.model_rebuild()


@router.post("/superadmin/broadcast", response_model=BroadcastNoticeResponse)
async def broadcast_notice(
    body: BroadcastNoticeRequest,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(require_superadmin),
):
    team_ids = list(dict.fromkeys(body.team_ids))
    q = select(Team.id).where(Team.is_active.is_(True), Team.is_approved.is_(True))
    if team_ids:
        q = q.where(Team.id.in_(team_ids))

    rows = (await db.execute(q.order_by(Team.id.asc()))).all()
    target_team_ids = [int(tid) for (tid,) in rows]
    if not target_team_ids:
        raise HTTPException(status_code=400, detail="目标队伍不存在或不可用")

    for team_id in target_team_ids:
        db.add(TeamPost(team_id=team_id, author_id=current_player.id, content=body.content.strip(), parent_id=None))

    await write_audit(
        db,
        current_player,
        "superadmin_notice_published",
        team_id=None,
        target_type="team_post",
        target_id=None,
        detail=build_change_detail(
            after={
                "team_count": len(target_team_ids),
                "target_team_ids": target_team_ids,
                "content_preview": body.content.strip()[:80],
            }
        ),
    )
    await db.commit()
    return BroadcastNoticeResponse(team_count=len(target_team_ids), target_team_ids=target_team_ids)


@router.get("/posts", response_model=list[PostRead])
async def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    from app.models.player import Player as PlayerModel

    posts_query = _exclude_hidden_reminders(
        select(TeamPost)
        .where(
            TeamPost.team_id == current_player.team_id,
            TeamPost.is_deleted.is_(False),
            TeamPost.parent_id.is_(None),
        )
    )
    result = await db.execute(
        posts_query
        .order_by(TeamPost.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    top_posts = result.scalars().all()
    if not top_posts:
        return []

    top_post_ids = [p.id for p in top_posts]
    replies_result = await db.execute(
        select(TeamPost)
        .where(TeamPost.parent_id.in_(top_post_ids), TeamPost.is_deleted.is_(False))
        .order_by(TeamPost.created_at.asc())
    )
    all_replies = replies_result.scalars().all()

    all_posts = list(top_posts) + list(all_replies)
    author_ids = list({p.author_id for p in all_posts})
    aresult = await db.execute(select(PlayerModel).where(PlayerModel.id.in_(author_ids)))
    author_map = {a.id: a.username for a in aresult.scalars()}

    replies_map: dict[int, list[PostRead]] = {pid: [] for pid in top_post_ids}
    for r in all_replies:
        if r.parent_id in replies_map:
            replies_map[r.parent_id].append(
                PostRead(
                    id=r.id,
                    author_id=r.author_id,
                    author_name=author_map.get(r.author_id, str(r.author_id)),
                    content=r.content,
                    parent_id=r.parent_id,
                    created_at=r.created_at,
                    replies=[],
                )
            )

    return [
        PostRead(
            id=p.id,
            author_id=p.author_id,
            author_name=author_map.get(p.author_id, str(p.author_id)),
            content=p.content,
            parent_id=None,
            created_at=p.created_at,
            replies=replies_map.get(p.id, []),
        )
        for p in top_posts
    ]


@router.post("/posts", response_model=PostRead, status_code=201)
async def create_post(
    body: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    if body.parent_id is not None:
        parent = (
            await db.execute(
                select(TeamPost).where(
                    TeamPost.id == body.parent_id,
                    TeamPost.team_id == current_player.team_id,
                    TeamPost.is_deleted.is_(False),
                    TeamPost.parent_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="父帖不存在或不可回复")

    post = TeamPost(
        team_id=current_player.team_id,
        author_id=current_player.id,
        content=body.content,
        parent_id=body.parent_id,
    )
    db.add(post)
    await db.flush()
    await write_audit(
        db,
        current_player,
        "team_post_created",
        team_id=current_player.team_id,
        target_type="team_post",
        target_id=post.id,
        detail=build_change_detail(after={"parent_id": post.parent_id, "content_preview": body.content[:80]}),
    )
    await db.commit()
    await db.refresh(post)
    return PostRead(
        id=post.id,
        author_id=post.author_id,
        author_name=current_player.username,
        content=post.content,
        parent_id=post.parent_id,
        created_at=post.created_at,
        replies=[],
    )


@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    post = (
        await db.execute(select(TeamPost).where(TeamPost.id == post_id, TeamPost.team_id == current_player.team_id))
    ).scalar_one_or_none()
    if not post or post.is_deleted:
        raise HTTPException(status_code=404, detail="公告不存在")

    is_admin = current_player.role in (UserRole.admin, UserRole.owner)
    if post.author_id != current_player.id and not is_admin:
        raise HTTPException(status_code=403, detail="无权删除此公告")

    post.is_deleted = True
    post.updated_at = datetime.now(timezone.utc)
    await write_audit(
        db,
        current_player,
        "team_post_deleted",
        team_id=current_player.team_id,
        target_type="team_post",
        target_id=post.id,
        detail=build_change_detail(
            before={"is_deleted": False, "content_preview": post.content[:80]},
            after={"is_deleted": True},
        ),
    )
    await db.commit()


@router.get("/notifications/count")
async def get_notification_count(
    since: str | None = Query(None, description="ISO datetime 上次已读时间戳"),
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    from app.models.match import Match, MatchStatus

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            since_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)
    else:
        since_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)

    count = 0
    my_post_ids_q = await db.execute(
        select(TeamPost.id).where(
            TeamPost.author_id == current_player.id,
            TeamPost.parent_id.is_(None),
            TeamPost.is_deleted.is_(False),
        )
    )
    my_post_ids = [r for (r,) in my_post_ids_q]
    if my_post_ids:
        res = await db.execute(
            select(func.count()).select_from(TeamPost).where(
                TeamPost.parent_id.in_(my_post_ids),
                TeamPost.author_id != current_player.id,
                TeamPost.is_deleted.is_(False),
                TeamPost.created_at > since_dt,
            )
        )
        count += res.scalar_one()

    sa_notice = await db.execute(
        select(func.count()).select_from(TeamPost).join(Player, TeamPost.author_id == Player.id).where(
            TeamPost.team_id == current_player.team_id,
            TeamPost.parent_id.is_(None),
            TeamPost.is_deleted.is_(False),
            TeamPost.created_at > since_dt,
            Player.is_superadmin.is_(True),
            TeamPost.author_id != current_player.id,
        )
    )
    count += sa_notice.scalar_one()

    if current_player.role in (UserRole.admin, UserRole.owner):
        res = await db.execute(
            select(func.count()).select_from(Match).where(
                Match.team_id == current_player.team_id,
                Match.status == MatchStatus.pending_approval,
            )
        )
        count += res.scalar_one()

        # 待审核的入队申请（PlayerTeamMembership）
        membership_res = await db.execute(
            select(func.count()).select_from(PlayerTeamMembership).where(
                PlayerTeamMembership.team_id == current_player.team_id,
                PlayerTeamMembership.status == PlayerStatus.pending,
            )
        )
        count += membership_res.scalar_one()

    # 已发布且尚未结束、当前玩家仍未填写出勤的日程提醒：聚合为 1 条通知
    from app.models.schedule import ScheduleEvent, ScheduleAttendance, ScheduleEventStatus
    submitted_event_ids = select(ScheduleAttendance.event_id).where(
        ScheduleAttendance.player_id == current_player.id
    )
    sched_res = await db.execute(
        select(func.count()).select_from(ScheduleEvent).where(
            ScheduleEvent.team_id == current_player.team_id,
            ScheduleEvent.status == ScheduleEventStatus.published,
            ScheduleEvent.end_date >= date.today(),
            ScheduleEvent.id.not_in(submitted_event_ids),
        )
    )
    if int(sched_res.scalar_one() or 0) > 0:
        count += 1

    return {"count": min(int(count), 99)}


@router.get("/notifications")
async def get_notifications(
    since: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    from app.models.match import Match, MatchStatus
    from app.models.player import Player as PlayerModel

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            since_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)
    else:
        since_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)

    items = []

    my_post_ids_q = await db.execute(
        select(TeamPost.id, TeamPost.content).where(
            TeamPost.author_id == current_player.id,
            TeamPost.parent_id.is_(None),
            TeamPost.is_deleted.is_(False),
        )
    )
    my_posts = {pid: content for pid, content in my_post_ids_q}
    if my_posts:
        replies_q = await db.execute(
            select(TeamPost)
            .where(
                TeamPost.parent_id.in_(list(my_posts.keys())),
                TeamPost.author_id != current_player.id,
                TeamPost.is_deleted.is_(False),
                TeamPost.created_at > since_dt,
            )
            .order_by(TeamPost.created_at.desc())
            .limit(20)
        )
        reply_posts = replies_q.scalars().all()
        replier_ids = {r.author_id for r in reply_posts}
        if replier_ids:
            names_q = await db.execute(
                select(PlayerModel.id, PlayerModel.display_name, PlayerModel.username).where(
                    PlayerModel.id.in_(replier_ids)
                )
            )
            names_map = {pid: (dn or un) for pid, dn, un in names_q}
        else:
            names_map = {}

        for r in reply_posts:
            parent_snippet = (my_posts.get(r.parent_id) or "")[:20]
            items.append(
                {
                    "type": "reply",
                    "title": f"{names_map.get(r.author_id, '队友')} 回复了你",
                    "body": r.content[:60],
                    "hint": f"原帖：{parent_snippet}…" if parent_snippet else "",
                    "created_at": r.created_at.isoformat(),
                }
            )

    notice_query = _exclude_hidden_reminders(
        select(TeamPost)
        .join(PlayerModel, TeamPost.author_id == PlayerModel.id)
        .where(
            TeamPost.team_id == current_player.team_id,
            TeamPost.parent_id.is_(None),
            TeamPost.is_deleted.is_(False),
            TeamPost.created_at > since_dt,
            PlayerModel.is_superadmin.is_(True),
            TeamPost.author_id != current_player.id,
        )
    )
    notice_q = await db.execute(
        notice_query.order_by(TeamPost.created_at.desc()).limit(20)
    )
    notices = notice_q.scalars().all()
    for n in notices:
        items.append(
            {
                "type": "announcement",
                "title": "超管公告",
                "body": n.content[:100],
                "hint": "来自平台管理公告",
                "created_at": n.created_at.isoformat(),
            }
        )

    if current_player.role in (UserRole.admin, UserRole.owner):
        pending_q = await db.execute(
            select(Match.id, Match.match_date)
            .where(
                Match.team_id == current_player.team_id,
                Match.status == MatchStatus.pending_approval,
            )
            .order_by(Match.match_date.desc())
            .limit(10)
        )
        for match_id, match_date in pending_q:
            items.append(
                {
                    "type": "approval",
                    "title": "待审批比赛",
                    "body": f"比赛 #{match_id}（{match_date.strftime('%m-%d')}）等待审批",
                    "hint": "",
                    "created_at": match_date.isoformat(),
                }
            )

    # 已发布且尚未结束、当前玩家还未提交出勤的日程提醒：聚合为单条通知
    from app.models.schedule import ScheduleAttendance, ScheduleEvent, ScheduleEventStatus

    if current_player.team_id is not None:
        submitted_event_ids = select(ScheduleAttendance.event_id).where(
            ScheduleAttendance.player_id == current_player.id
        )
        event_type_text = {
            "game": "外战",
            "internal": "内战",
            "training": "训练",
            "other": "其他",
        }
        sched_q = await db.execute(
            select(ScheduleEvent)
            .where(
                ScheduleEvent.team_id == current_player.team_id,
                ScheduleEvent.status == ScheduleEventStatus.published,
                ScheduleEvent.end_date >= date.today(),
                ScheduleEvent.id.not_in(submitted_event_ids),
            )
            .order_by(ScheduleEvent.start_date.asc(), ScheduleEvent.id.desc())
            .limit(20)
        )
        pending_events = sched_q.scalars().all()
        if pending_events:
            trigger_q = await db.execute(
                select(func.max(TeamPost.created_at)).where(
                    TeamPost.team_id == current_player.team_id,
                    TeamPost.parent_id.is_(None),
                    TeamPost.is_deleted.is_(False),
                    TeamPost.content.like("[系统催填]%"),
                )
            )
            reminder_trigger_at = _ensure_aware(trigger_q.scalar_one_or_none())

            event_lines = []
            for ev in pending_events[:4]:
                date_text = ev.start_date.isoformat()
                if ev.end_date != ev.start_date:
                    date_text = f"{ev.start_date.isoformat()} ~ {ev.end_date.isoformat()}"
                event_type_key = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
                event_lines.append(f"{date_text}「{ev.title}」({event_type_text.get(event_type_key, event_type_key)})")

            body = "；".join(event_lines)
            if len(pending_events) > 4:
                body += f"；等 {len(pending_events)} 个活动"

            created_candidates = [aware_dt for ev in pending_events if (aware_dt := _ensure_aware(ev.created_at)) is not None]
            if reminder_trigger_at is not None:
                created_candidates.append(reminder_trigger_at)
            created_at = max(created_candidates).isoformat() if created_candidates else datetime.now(timezone.utc).isoformat()

            if reminder_trigger_at is not None and reminder_trigger_at > since_dt:
                title = f"管理员提醒：请填写 {len(pending_events)} 个活动出勤"
            elif len(pending_events) == 1:
                title = f"待填写出勤：{pending_events[0].title}"
            else:
                title = f"待填写出勤：{len(pending_events)} 个活动"

            items.append(
                {
                    "type": "schedule",
                    "title": title,
                    "body": body,
                    "hint": "在主页日历点开对应日期后，提交一次会同步当天全部活动的状态",
                    "created_at": created_at,
                }
            )

    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {"items": items}
