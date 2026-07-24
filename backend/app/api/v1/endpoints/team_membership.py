"""/team membership and approval endpoints."""

import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_player, get_current_user, get_effective_team_id, require_admin, require_owner, require_superadmin
from app.core.database import get_db
from app.core.paths import get_uploads_dir
from app.models.match import TeamSettings
from app.models.membership import PlayerTeamMembership
from app.models.player import Player, PlayerStatus, UserRole
from app.models.user import User
from app.models.team import Team
from app.services.audit_service import build_change_detail, snapshot_fields, write_audit

router = APIRouter()

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}
UPLOAD_DIR = get_uploads_dir()


class CreateTeamRequest(BaseModel):
    team_name: str = Field(..., min_length=2, max_length=50)


class UpdateTeamInfoRequest(BaseModel):
    team_name: str | None = Field(default=None, min_length=2, max_length=50)


class JoinTeamRequest(BaseModel):
    team_id: int


class TeamInfoResponse(BaseModel):
    id: int
    name: str
    logo_url: str | None = None
    member_count: int
    my_status: str


class PendingTeamResponse(BaseModel):
    id: int
    name: str
    created_at: str
    owner_username: str
    owner_display_name: str | None


@router.post("/logo")
async def upload_team_logo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(require_owner),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="只支持 JPG/PNG/GIF/WEBP 格式图片")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 5MB")

    team = (await db.execute(select(Team).where(Team.id == current_player.team_id))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")

    ext = ALLOWED_IMAGE_TYPES[file.content_type]
    filename = f"logo_{current_player.team_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    old_logo_url = team.logo_url

    if team.logo_url:
        old_path = os.path.join(UPLOAD_DIR, os.path.basename(team.logo_url))
        try:
            os.remove(old_path)
        except FileNotFoundError:
            pass

    with open(filepath, "wb") as f:
        f.write(content)

    team.logo_url = f"/uploads/{filename}"
    await write_audit(
        db,
        current_player,
        "team_logo_updated",
        team_id=team.id,
        target_type="team",
        target_id=team.id,
        detail=build_change_detail(before={"logo_url": old_logo_url}, after={"logo_url": team.logo_url}),
    )
    await db.commit()
    return {"logo_url": team.logo_url}


@router.get("/my", response_model=TeamInfoResponse | None)
async def get_my_team(
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
    viewing_team_id: int | None = Query(None, alias="team_id"),
):
    if current_player.is_superadmin and viewing_team_id is not None:
        effective_id = viewing_team_id
    elif current_player.team_id:
        effective_id = current_player.team_id
    else:
        return None

    team = (await db.execute(select(Team).where(Team.id == effective_id))).scalar_one_or_none()
    if not team:
        return None

    count_result = await db.execute(
        select(func.count()).select_from(Player).where(
            Player.team_id == effective_id,
            Player.status == PlayerStatus.active,
        )
    )
    return TeamInfoResponse(
        id=team.id,
        name=team.name,
        logo_url=team.logo_url,
        member_count=count_result.scalar() or 0,
        my_status=current_player.status.value,
    )


@router.put("/info", status_code=200)
async def update_team_info(
    body: UpdateTeamInfoRequest,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(require_owner),
    effective_team_id: int = Depends(get_effective_team_id),
):
    team = (await db.execute(select(Team).where(Team.id == effective_team_id))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")

    before_info = snapshot_fields(team, ["name"])
    if body.team_name:
        existing = (
            await db.execute(select(Team).where(Team.name == body.team_name, Team.id != team.id))
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="队伍名称已存在")
        team.name = body.team_name

    await write_audit(
        db,
        current_player,
        "team_info_updated",
        team_id=team.id,
        target_type="team",
        target_id=team.id,
        detail=build_change_detail(before=before_info, after=snapshot_fields(team, ["name"])),
    )
    await db.commit()
    return {"message": "队伍信息已更新", "name": team.name}


@router.get("/available")
async def list_available_teams(
    db: AsyncSession = Depends(get_db),
    _: Player = Depends(get_current_active_player),
):
    q = (
        select(Team.id, Team.name, func.count(Player.id).label("member_count"))
        .where(Team.is_active.is_(True), Team.is_approved.is_(True))
        .outerjoin(Player, (Player.team_id == Team.id) & (Player.status == PlayerStatus.active))
        .group_by(Team.id, Team.name)
        .order_by(Team.name.asc())
    )
    rows = (await db.execute(q)).all()
    return [{"id": tid, "name": name, "member_count": int(cnt or 0)} for tid, name, cnt in rows]


@router.post("/create", status_code=201)
async def create_team(
    body: CreateTeamRequest,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    if current_player.team_id is not None:
        raise HTTPException(status_code=400, detail="请先退出当前队伍再创建新队伍")

    existing = (await db.execute(select(Team).where(Team.name == body.team_name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="队伍名称已存在")

    team = Team(name=body.team_name, is_approved=False)
    db.add(team)
    await db.flush()

    db.add(TeamSettings(team_id=team.id, updated_by=current_player.id))

    current_player.team_id = team.id
    current_player.role = UserRole.owner
    current_player.status = PlayerStatus.active
    await write_audit(
        db,
        current_player,
        "team_created",
        team_id=team.id,
        target_type="team",
        target_id=team.id,
        detail=build_change_detail(
            after={
                "team_name": team.name,
                "is_approved": team.is_approved,
                "owner_username": current_player.username,
            }
        ),
    )
    await db.commit()
    return {
        "message": f"队伍 '{body.team_name}' 申请已提交，等待超级管理员审批",
        "team_id": team.id,
        "pending": True,
    }


@router.post("/apply", status_code=200)
async def apply_join_team(
    body: JoinTeamRequest,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    if current_player.team_id is not None:
        raise HTTPException(status_code=400, detail="你已经在一个队伍中，请先退出")

    team = (
        await db.execute(select(Team).where(Team.id == body.team_id, Team.is_active.is_(True)))
    ).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")

    before_membership = snapshot_fields(current_player, ["team_id", "role", "status"])
    current_player.team_id = team.id
    current_player.role = UserRole.member
    current_player.status = PlayerStatus.pending

    # 同步写入 PlayerTeamMembership，确保团队管理页面（TeamMembershipView）能看到申请
    ptm_exists = (
        await db.execute(
            select(PlayerTeamMembership).where(
                PlayerTeamMembership.player_id == current_player.id,
                PlayerTeamMembership.team_id == team.id,
            )
        )
    ).scalar_one_or_none()
    if ptm_exists is None:
        db.add(PlayerTeamMembership(
            player_id=current_player.id,
            team_id=team.id,
            role=UserRole.member,
            status=PlayerStatus.pending,
        ))
    elif ptm_exists.status != PlayerStatus.active:
        ptm_exists.status = PlayerStatus.pending

    await write_audit(
        db,
        current_player,
        "team_join_applied",
        team_id=team.id,
        target_type="team",
        target_id=team.id,
        detail=build_change_detail(
            before=before_membership,
            after=snapshot_fields(current_player, ["team_id", "role", "status"]),
            extra={"team_name": team.name},
        ),
    )
    await db.commit()
    return {"message": f"已申请加入 '{team.name}'，等待管理员审核"}


@router.delete("/leave", status_code=200)
async def leave_team(
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
    current_user: User = Depends(get_current_user),
):
    if current_player.team_id is None:
        raise HTTPException(status_code=400, detail="你当前不在任何队伍中")

    if current_player.role == UserRole.owner:
        other_count = (
            await db.execute(
                select(func.count()).select_from(Player).where(
                    Player.team_id == current_player.team_id,
                    Player.id != current_player.id,
                )
            )
        ).scalar() or 0
        if other_count > 0:
            raise HTTPException(status_code=400, detail="作为主理人，请先转让主理人权限或移除所有成员再退出")

    before_membership = snapshot_fields(current_player, ["team_id", "role", "status"])
    former_team_id = current_player.team_id
    current_player.team_id = None
    current_player.role = UserRole.member
    current_player.status = PlayerStatus.active

    # T046 [US5]: 退队后清理 user 级默认队伍（若默认队伍正是刚退出的队伍）
    from app.services.user_context_service import converge_after_leave
    await converge_after_leave(db, current_user, former_team_id)

    await write_audit(
        db,
        current_player,
        "team_left",
        team_id=former_team_id,
        target_type="team",
        target_id=former_team_id,
        detail=build_change_detail(
            before=before_membership,
            after=snapshot_fields(current_player, ["team_id", "role", "status"]),
        ),
    )
    await db.commit()
    return {"message": "已退出队伍"}


@router.get("/pending-teams", status_code=200)
async def list_pending_teams(
    db: AsyncSession = Depends(get_db),
    _: Player = Depends(require_superadmin),
):
    q = (
        select(Team.id, Team.name, Team.created_at, Player.username, Player.display_name)
        .select_from(Team)
        .outerjoin(Player, (Player.team_id == Team.id) & (Player.role == UserRole.owner))
        .where(Team.is_approved.is_(False), Team.is_active.is_(True))
        .order_by(Team.created_at.desc())
    )
    rows = (await db.execute(q)).all()
    return [
        {
            "id": team_id,
            "name": name,
            "created_at": created_at.isoformat() if created_at else "",
            "owner_username": owner_username or "",
            "owner_display_name": owner_display_name,
        }
        for team_id, name, created_at, owner_username, owner_display_name in rows
    ]


@router.post("/{team_id}/approve", status_code=200)
async def approve_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(require_superadmin),
):
    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")
    if team.is_approved:
        raise HTTPException(status_code=400, detail="该队伍已经通过审批")

    team.is_approved = True
    await db.execute(
        update(Player)
        .where(
            Player.team_id == team_id,
            Player.role == UserRole.owner,
            Player.status == PlayerStatus.pending,
        )
        .values(status=PlayerStatus.active)
    )
    await write_audit(
        db,
        current_player,
        "team_approved",
        team_id=team_id,
        target_type="team",
        target_id=team_id,
        detail={"team_name": team.name},
    )
    await db.commit()
    return {"message": f"队伍 '{team.name}' 已通过审批"}


@router.post("/{team_id}/reject", status_code=200)
async def reject_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(require_superadmin),
):
    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")
    if team.is_approved:
        raise HTTPException(status_code=400, detail="该队伍已通过审批，无法拒绝")

    await db.execute(
        update(Player)
        .where(Player.team_id == team_id)
        .values(team_id=None, role=UserRole.member, status=PlayerStatus.rejected)
    )
    team.is_active = False
    await write_audit(
        db,
        current_player,
        "team_rejected",
        team_id=team_id,
        target_type="team",
        target_id=team_id,
        detail={"team_name": team.name},
    )
    await db.commit()
    return {"message": f"队伍 '{team.name}' 申请已拒绝"}


# ──────────────────────────────────────────────────────────────────────────────
# T072 [US3]: /team-membership/applications — 多队申请入口
# ──────────────────────────────────────────────────────────────────────────────


class TeamApplicationRequest(BaseModel):
    """多队申请入队请求体"""
    team_id: int | None = None
    team_name: str | None = Field(default=None, max_length=100)
    join_reason: str | None = Field(default=None, max_length=300)


@router.post("/applications", status_code=200)
async def apply_team_membership(
    body: TeamApplicationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """多队申请入队（US3）。

    支持通过 team_id 或 team_name 指定目标队伍。
    与旧版 /apply 的区别：不限制用户是否已在某队伍中，
    通过 PlayerTeamMembership 为用户在目标队伍创建独立的 pending 申请记录。
    同一用户对同一队伍只能有一条有效申请。
    """
    # 查找目标队伍（优先 team_name，其次 team_id）
    if body.team_name:
        team = (
            await db.execute(
                select(Team).where(
                    Team.name == body.team_name,
                    Team.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not team:
            raise HTTPException(status_code=404, detail="没有该队伍")
    elif body.team_id is not None:
        team = (
            await db.execute(select(Team).where(Team.id == body.team_id, Team.is_active.is_(True)))
        ).scalar_one_or_none()
        if not team:
            raise HTTPException(status_code=404, detail="队伍不存在")
    else:
        raise HTTPException(status_code=400, detail="请提供 team_name 或 team_id")

    # 查找该 user 对应的 Player（全局身份）
    player_result = await db.execute(
        select(Player).where(Player.user_id == current_user.id).limit(1)
    )
    current_player = player_result.scalar_one_or_none()
    if not current_player:
        raise HTTPException(status_code=400, detail="用户账号异常，找不到对应 player 记录")

    # 检查是否已有该队伍的 membership 记录
    existing = (
        await db.execute(
            select(PlayerTeamMembership).where(
                PlayerTeamMembership.player_id == current_player.id,
                PlayerTeamMembership.team_id == team.id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        if existing.status == PlayerStatus.active:
            raise HTTPException(status_code=409, detail="您已经是该队伍的成员")
        if existing.status == PlayerStatus.pending:
            raise HTTPException(status_code=409, detail="您已提交过该队伍的加入申请，请等待审核")
        # 被拒绝后允许重新申请：重置已有记录为 pending
        existing.status = PlayerStatus.pending
        existing.join_reason = body.join_reason
        existing.approved_by = None
        existing.approved_at = None
        await write_audit(
            db,
            current_player,
            "team_membership_applied",
            team_id=team.id,
            target_type="team",
            target_id=team.id,
            detail={"team_name": team.name, "join_reason": body.join_reason, "re_apply": True},
        )
        await db.commit()
        await db.refresh(existing)
        return {
            "code": 0,
            "data": {
                "membership_id": existing.id,
                "team_id": existing.team_id,
                "status": existing.status.value,
            },
            "message": f"已重新申请加入 '{team.name}'，等待管理员审核",
        }

    # 创建 PlayerTeamMembership 申请记录
    new_membership = PlayerTeamMembership(
        player_id=current_player.id,
        team_id=team.id,
        role=UserRole.member,
        status=PlayerStatus.pending,
        join_reason=body.join_reason,
    )
    db.add(new_membership)
    await write_audit(
        db,
        current_player,
        "team_membership_applied",
        team_id=team.id,
        target_type="team",
        target_id=team.id,
        detail={"team_name": team.name, "join_reason": body.join_reason},
    )
    await db.commit()
    await db.refresh(new_membership)
    return {
        "code": 0,
        "data": {
            "membership_id": new_membership.id,
            "team_id": new_membership.team_id,
            "status": new_membership.status.value,
        },
        "message": f"已申请加入 '{team.name}'，等待管理员审核",
    }


# ──────────────────────────────────────────────────────────────────────────────
# T041 [US4]: GET /applications/pending — 查询队伍待审核申请列表（管理员）
# NOTE: 必须在 /{membership_id}/review 之前注册，以免路由匹配冲突

@router.get("/applications/pending", status_code=200)
async def list_pending_applications(
    team_id: int | None = Query(default=None),
    admin: Player = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """列出指定队伍的全部 pending PlayerTeamMembership 申请（管理员）。"""
    effective_team_id = team_id or admin.team_id
    if not effective_team_id:
        raise HTTPException(status_code=400, detail="无法确定队伍")

    rows = (
        await db.execute(
            select(PlayerTeamMembership, Player, User)
            .join(Player, PlayerTeamMembership.player_id == Player.id)
            .join(User, Player.user_id == User.id)
            .where(
                PlayerTeamMembership.team_id == effective_team_id,
                PlayerTeamMembership.status == PlayerStatus.pending,
            )
            .order_by(PlayerTeamMembership.created_at.asc())
        )
    ).all()

    items = []
    for membership, player, user in rows:
        items.append({
            "id": membership.id,
            "player_id": player.id,
            "player_username": user.username,
            "team_id": membership.team_id,
            "join_reason": membership.join_reason,
            "status": membership.status.value,
            "created_at": membership.created_at.isoformat() if membership.created_at else None,
        })

    return {"code": 0, "data": items, "message": "ok"}


@router.get("/applications/suggested-mu", status_code=200)
async def get_pending_review_suggested_mu(
    team_id: int | None = Query(default=None),
    admin: Player = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """为入队审核提供建议初始 μ 参考信息。"""
    from app.services.rating_settings import get_suggested_mu

    effective_team_id = team_id or admin.team_id
    if not effective_team_id:
        raise HTTPException(status_code=400, detail="无法确定队伍")

    if not admin.is_superadmin and admin.team_id != effective_team_id:
        raise HTTPException(status_code=403, detail="无权查看其他队伍建议值")

    sample_count = (
        await db.execute(
            select(func.count()).select_from(Player).where(
                Player.team_id == effective_team_id,
                Player.status == PlayerStatus.active,
                Player.is_guest.is_(False),
            )
        )
    ).scalar() or 0

    suggested_mu = await get_suggested_mu(db, effective_team_id)
    ts = (
        await db.execute(select(TeamSettings).where(TeamSettings.team_id == effective_team_id))
    ).scalar_one_or_none()
    fallback_mu = ts.openskill_mu if ts else 25.0

    return {
        "code": 0,
        "data": {
            "team_id": effective_team_id,
            "suggested_mu": float(suggested_mu),
            "sample_count": int(sample_count),
            "used_default": sample_count < 3,
            "fallback_mu": float(fallback_mu),
            "manual_mu_min": 10.0,
            "manual_mu_max": 40.0,
        },
        "message": "ok",
    }


# ──────────────────────────────────────────────────────────────────────────────
# T038 [US4]: /team-membership/applications/{membership_id}/review — 审核申请
# ──────────────────────────────────────────────────────────────────────────────


class ApplicationReviewRequest(BaseModel):
    """审核 PlayerTeamMembership 申请请求体（US4）"""
    action: str = Field(..., pattern="^(approve|reject)$", description="approve 或 reject")
    initial_mu: float | None = Field(
        default=None,
        ge=10.0, le=40.0,
        description="管理员手动设置的初始 μ（10.0~40.0），不填则使用建议值",
    )


@router.post("/applications/{membership_id}/review", status_code=200)
async def review_team_membership(
    membership_id: int,
    body: ApplicationReviewRequest,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
):
    """审核 PlayerTeamMembership 申请（US4: 入队申请审核与初始 μ 设定）。

    - approve：将申请置为 active，并为对应 player 在目标队伍创建/更新 player 分身
    - reject：将申请置为 active（清除 team 绑定），使用户可重新申请
    - initial_mu：管理员手动设置，不填则用队伍平均 μ 建议值
    """
    from app.services.rating_settings import get_suggested_mu
    from datetime import datetime, timezone

    # 查询申请记录
    membership = (
        await db.execute(
            select(PlayerTeamMembership).where(PlayerTeamMembership.id == membership_id)
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="申请记录不存在")
    if membership.status != PlayerStatus.pending:
        raise HTTPException(status_code=400, detail="该申请已处理，无法重复审核")

    # 校验管理员有权审核（同队伍 admin/owner 或超管）
    if not admin.is_superadmin and admin.team_id != membership.team_id:
        raise HTTPException(status_code=403, detail="无权审核其他队伍的申请")

    player = (
        await db.execute(select(Player).where(Player.id == membership.player_id))
    ).scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="申请者 player 记录不存在")

    if body.action == "approve":
        # 计算建议 μ 并记录快照
        suggested = await get_suggested_mu(db, membership.team_id)
        membership.suggested_mu_snapshot = suggested
        final_mu = body.initial_mu if body.initial_mu is not None else suggested

        # 更新申请记录
        membership.status = PlayerStatus.active
        membership.approved_by = admin.id
        membership.approved_at = datetime.now(timezone.utc)
        membership.mu = final_mu

        # 将 player 绑定到目标队伍：
        # - 若 player 尚无 team_id，直接更新 player 记录
        # - 若 player.team_id 已等于申请队伍（旧 /team/apply 路径），仅激活状态
        # - 若 player 已属于其他队伍，创建新的 player 分身（多队支持）
        if player.team_id is None:
            player.team_id = membership.team_id
            player.status = PlayerStatus.active
            player.role = UserRole.member
            player.mu = final_mu
        elif player.team_id == membership.team_id:
            # 旧 /team/apply 已经设置了 team_id，只需要激活 player
            player.status = PlayerStatus.active
            player.mu = final_mu
        else:
            # 检查该 user 在目标队伍是否已有 player 分身
            existing_shard = (
                await db.execute(
                    select(Player).where(
                        Player.user_id == player.user_id,
                        Player.team_id == membership.team_id,
                    )
                )
            ).scalar_one_or_none()
            if existing_shard is None:
                cr = final_mu - 3 * 8.333
                # 多队分身：username 和 email 须全局唯一，使用合成标识符避免冲突
                shard_username = f"_s{player.user_id}t{membership.team_id}"
                new_shard = Player(
                    user_id=player.user_id,
                    username=shard_username,
                    password_hash=player.password_hash,
                    display_name=player.display_name,
                    gender=player.gender,
                    jersey_number=player.jersey_number,
                    avatar_url=player.avatar_url,
                    team_id=membership.team_id,
                    role=UserRole.member,
                    status=PlayerStatus.active,
                    mu=final_mu,
                    sigma=8.333,
                    conservative_rating=cr,
                )
                db.add(new_shard)
            else:
                # 分身已存在，确保激活
                existing_shard.status = PlayerStatus.active
                existing_shard.mu = final_mu

        await write_audit(
            db, admin, "membership_approved",
            team_id=membership.team_id, target_type="player", target_id=player.id,
            detail={
                "initial_mu": final_mu,
                "suggested_mu": suggested,
                "manual_mu": body.initial_mu is not None,
                "player_username": player.username,
            },
        )
        await db.commit()
        return {
            "code": 0,
            "data": {
                "membership_id": membership.id,
                "status": "active",
                "initial_mu": final_mu,
                "suggested_mu": suggested,
            },
            "message": "申请已通过",
        }

    else:  # reject
        # 拒绝：将申请状态置为 rejected，player 保持原状（不影响其他队伍归属）
        membership.status = PlayerStatus.rejected
        membership.approved_by = admin.id
        membership.approved_at = datetime.now(timezone.utc)

        await write_audit(
            db, admin, "membership_rejected",
            team_id=membership.team_id, target_type="player", target_id=player.id,
            detail={"player_username": player.username},
        )
        await db.commit()
        return {
            "code": 0,
            "data": {"membership_id": membership.id, "status": "rejected"},
            "message": "申请已拒绝",
        }


# ──────────────────────────────────────────────────────────────────────────────
# GET /team/my-teams — 当前用户的所有队伍 membership 列表
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/my-teams", status_code=200)
async def get_my_teams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回当前用户在所有队伍的 membership 记录（pending + active）。"""
    # 找到该 user 的 player
    player_result = await db.execute(
        select(Player).where(Player.user_id == current_user.id).limit(1)
    )
    current_player = player_result.scalar_one_or_none()
    if not current_player:
        return []

    rows = (
        await db.execute(
            select(PlayerTeamMembership, Team)
            .join(Team, PlayerTeamMembership.team_id == Team.id)
            .where(
                PlayerTeamMembership.player_id == current_player.id,
                PlayerTeamMembership.status.in_([PlayerStatus.pending, PlayerStatus.active]),
            )
            .order_by(PlayerTeamMembership.created_at.asc())
        )
    ).all()

    return [
        {
            "membership_id": membership.id,
            "team_id": team.id,
            "team_name": team.name,
            "status": membership.status.value,
            "role": membership.role.value,
            "join_reason": membership.join_reason,
        }
        for membership, team in rows
    ]


# ──────────────────────────────────────────────────────────────────────────────
# GET /team/pending-members — 管理员查看本队待审核的成员申请
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/pending-members", status_code=200)
async def get_pending_members(
    admin: Player = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """列出当前管理员所在队伍的所有 pending 成员申请（PlayerTeamMembership）。

    响应字段：id, username, join_reason（供审批列表展示）。
    """
    effective_team_id = admin.team_id
    if not effective_team_id:
        raise HTTPException(status_code=400, detail="无法确定队伍")

    rows = (
        await db.execute(
            select(PlayerTeamMembership, Player, User)
            .join(Player, PlayerTeamMembership.player_id == Player.id)
            .join(User, Player.user_id == User.id)
            .where(
                PlayerTeamMembership.team_id == effective_team_id,
                PlayerTeamMembership.status == PlayerStatus.pending,
            )
            .order_by(PlayerTeamMembership.created_at.asc())
        )
    ).all()

    return [
        {
            "id": membership.id,
            "player_id": player.id,
            "username": user.username,
            "display_name": player.display_name,
            "team_id": membership.team_id,
            "join_reason": membership.join_reason,
            "status": membership.status.value,
            "created_at": membership.created_at.isoformat() if membership.created_at else None,
        }
        for membership, player, user in rows
    ]


# ──────────────────────────────────────────────────────────────────────────────
# PUT /team/default — 设置当前用户的默认队伍（US3 别名端点）
# ──────────────────────────────────────────────────────────────────────────────


class SetDefaultTeamRequest(BaseModel):
    team_id: int


@router.put("/default", status_code=200)
async def set_default_team(
    body: SetDefaultTeamRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """设置用户默认队伍（须为该队伍的 active 成员）。

    非成员返回 403；成功更新 user.default_team_id 并返回 200。
    """
    from datetime import datetime, timezone

    # 校验：user 须是目标队伍的 active 成员
    if not current_user.is_superadmin:
        # 通过 PlayerTeamMembership 校验（多队架构）
        ptm = (
            await db.execute(
                select(PlayerTeamMembership)
                .join(Player, PlayerTeamMembership.player_id == Player.id)
                .where(
                    Player.user_id == current_user.id,
                    PlayerTeamMembership.team_id == body.team_id,
                    PlayerTeamMembership.status == PlayerStatus.active,
                )
            )
        ).scalar_one_or_none()
        # 也兼容旧版 player.team_id 机制
        if ptm is None:
            legacy = (
                await db.execute(
                    select(Player).where(
                        Player.user_id == current_user.id,
                        Player.team_id == body.team_id,
                        Player.status == PlayerStatus.active,
                    )
                )
            ).scalar_one_or_none()
            if legacy is None:
                raise HTTPException(status_code=403, detail="您不是该队伍的 active 成员，无法设置为默认队伍")

    current_user.default_team_id = body.team_id
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "code": 0,
        "data": {"default_team_id": body.team_id},
        "message": "默认队伍已更新",
    }

