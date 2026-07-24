"""T026: /players 端点 — 成员列表、个人详情、状态与角色管理"""
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

import re
from pydantic import field_validator
from app.api.v1.deps import get_current_active_player, get_current_user, get_effective_team_id, require_admin, require_owner
from app.core.paths import get_uploads_dir
from app.core.security import verify_password, get_password_hash
from app.core.database import get_db
from app.models.player import Player, PlayerStatus, UserRole
from app.models.user import User
from app.models.match import RatingHistory, MatchPlayer, Match, MatchStatus
from app.schemas.player import PlayerPublic, PlayerStatusUpdate, PlayerRoleUpdate, PlayerProfileUpdate, PasswordChange, DualLayerProfileUpdateRequest, DualLayerProfileUpdateResponse
from app.services.audit_service import build_change_detail, mask_email, snapshot_fields, write_audit

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}
UPLOAD_DIR = get_uploads_dir()


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    """上传个人头像"""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="只支持 JPG/PNG/GIF/WEBP 格式图片")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="图片大小不能超过 5MB")
    ext = ALLOWED_IMAGE_TYPES[file.content_type]
    filename = f"avatar_{current_player.id}_{uuid.uuid4().hex[:8]}.{ext}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    old_avatar_url = current_player.avatar_url
    # 删除旧头像文件
    if current_player.avatar_url:
        old_path = os.path.join(UPLOAD_DIR, os.path.basename(current_player.avatar_url))
        try:
            os.remove(old_path)
        except FileNotFoundError:
            pass
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    current_player.avatar_url = f"/uploads/{filename}"
    await write_audit(
        db,
        current_player,
        "player_avatar_updated",
        team_id=current_player.team_id,
        target_type="player",
        target_id=current_player.id,
        detail=build_change_detail(
            before={"avatar_url": old_avatar_url},
            after={"avatar_url": current_player.avatar_url},
        ),
    )
    await db.commit()
    return {"avatar_url": current_player.avatar_url}


@router.get("", response_model=list[PlayerPublic])
async def list_players(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    viewing_team_id: int | None = Query(None, alias="team_id"),
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    """列出队员（可按状态筛选，且仅返回同队伍成员），超级管理员可通过 ?team_id= 切换队伍"""
    if current_player.is_superadmin:
        if viewing_team_id is None:
            return []  # 超管未选择队伍时返回空列表
        effective_team_id = viewing_team_id
    elif current_player.team_id:
        effective_team_id = current_player.team_id
    else:
        raise HTTPException(status_code=403, detail="请先加入队伍")
    q = select(Player).where(Player.team_id == effective_team_id).order_by(Player.conservative_rating.desc())
    if status_filter:
        try:
            ps = PlayerStatus(status_filter)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效状态值: {status_filter}")
        q = q.where(Player.status == ps)
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/me", response_model=PlayerPublic)
async def get_my_profile(current_player: Player = Depends(get_current_active_player)):
    """获取当前登录用户的完整档案"""
    return current_player


@router.get("/{player_id}", response_model=PlayerPublic)
async def get_player(
    player_id: int,
    db: AsyncSession = Depends(get_db),
    current_player: Player = Depends(get_current_active_player),
):
    """获取指定队员档案（成员只能查自己，管理员可查本队任意人）"""
    if current_player.role not in (UserRole.admin, UserRole.owner) and current_player.id != player_id:
        if not current_player.is_superadmin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问")

    q = select(Player).where(Player.id == player_id)
    if not current_player.is_superadmin:
        q = q.where(Player.team_id == current_player.team_id)
    result = await db.execute(q)
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="队员不存在")
    return player


@router.patch("/{player_id}/status", response_model=PlayerPublic)
async def update_player_status(
    player_id: int,
    body: PlayerStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
):
    """管理员审批成员申请（active/rejected）"""
    q = select(Player).where(Player.id == player_id)
    if not admin.is_superadmin:
        q = q.where(Player.team_id == admin.team_id)
    result = await db.execute(q)
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="队员不存在")
    if player.id == admin.id:
        raise HTTPException(status_code=400, detail="不能修改自己的状态")

    old_status = player.status.value
    player.status = body.status
    player.approved_by = admin.id
    player.approved_at = datetime.now(timezone.utc)

    # T045 [US5]: 申请被拒时将 player 恢复到无队伍状态，使用户仍可登录并重新申请
    if body.status == PlayerStatus.rejected and player.team_id is not None:
        former_team_id = player.team_id
        player.team_id = None
        player.role = UserRole.member
        player.status = PlayerStatus.active  # 恢复为 active(无队伍)，而非 rejected
        # 同步清理 user 的默认队伍设置
        if player.user_id is not None:
            from sqlalchemy import select as sa_select
            from app.models.user import User as UserModel
            user_result = await db.execute(sa_select(UserModel).where(UserModel.id == player.user_id))
            user_obj = user_result.scalar_one_or_none()
            if user_obj:
                from app.services.user_context_service import converge_after_leave
                await converge_after_leave(db, user_obj, former_team_id)

    await write_audit(db, admin, "player_status_updated",
                      team_id=player.team_id, target_type="player", target_id=player.id,
                      detail={"from": old_status, "to": body.status.value,
                              "player_username": player.username})
    await db.commit()
    await db.refresh(player)
    return player


@router.patch("/{player_id}/role", response_model=PlayerPublic)
async def update_player_role(
    player_id: int,
    body: PlayerRoleUpdate,
    db: AsyncSession = Depends(get_db),
    owner: Player = Depends(require_owner),
):
    """主理人变更队员角色（不能修改自己）"""
    q = select(Player).where(Player.id == player_id)
    if not owner.is_superadmin:
        q = q.where(Player.team_id == owner.team_id)
    result = await db.execute(q)
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="队员不存在")
    if player.id == owner.id:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")
    if body.role == UserRole.owner:
        raise HTTPException(status_code=400, detail="不能将他人设为主理人")

    old_role = player.role.value
    player.role = body.role
    await write_audit(db, owner, "player_role_changed",
                      team_id=player.team_id, target_type="player", target_id=player.id,
                      detail=build_change_detail(
                          before={"role": old_role},
                          after={"role": body.role.value},
                          extra={"player_username": player.username},
                      ))
    await db.commit()
    await db.refresh(player)
    return player


# ——— T079: 绑定邮箱 ———

class EmailUpdate(BaseModel):
    email: EmailStr


@router.put("/me/email", status_code=200)
async def update_my_email(
    body: EmailUpdate,
    current_player: Player = Depends(get_current_active_player),
    db: AsyncSession = Depends(get_db),
):
    """绑定或变更自己的邮箱（用于找回密码）。"""
    # 检查邮箱是否被其他人占用
    existing = await db.execute(
        select(Player).where(Player.email == str(body.email), Player.id != current_player.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该邮箱已被其他账号绑定")

    old_email = current_player.email
    current_player.email = str(body.email)
    await write_audit(
        db,
        current_player,
        "player_email_updated",
        team_id=current_player.team_id,
        target_type="player",
        target_id=current_player.id,
        detail=build_change_detail(
            before={"email": mask_email(old_email)},
            after={"email": mask_email(current_player.email)},
        ),
    )
    await db.commit()
    return {"message": "邮箱绑定成功", "email": str(body.email)}


# ——— 修改密码 ———

@router.put("/me/password", status_code=200)
async def change_my_password(
    body: PasswordChange,
    current_player: Player = Depends(get_current_active_player),
    db: AsyncSession = Depends(get_db),
):
    """修改自己的密码（需要验证旧密码）"""
    if not verify_password(body.old_password, current_player.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    new_hash = get_password_hash(body.new_password)
    current_player.password_hash = new_hash
    # 同步更新关联 User 的密码，确保用户通过 User 路径登录也有效
    if current_player.user_id:
        user_result = await db.execute(select(User).where(User.id == current_player.user_id))
        linked_user = user_result.scalar_one_or_none()
        if linked_user:
            linked_user.password_hash = new_hash
    await write_audit(
        db,
        current_player,
        "player_password_changed",
        team_id=current_player.team_id,
        target_type="player",
        target_id=current_player.id,
        detail=build_change_detail(extra={"email": mask_email(current_player.email)}),
    )
    await db.commit()
    return {"message": "密码修改成功"}


# ——— 个人资料编辑 ———

@router.put("/me/profile", response_model=PlayerPublic)
async def update_my_profile(
    body: PlayerProfileUpdate,
    current_player: Player = Depends(get_current_active_player),
    db: AsyncSession = Depends(get_db),
):
    """修改自己的账户名、显示名称、邮箱和性别（均保证唯一性）"""
    before_profile = snapshot_fields(
        current_player,
        ["username", "display_name", "email", "gender", "show_in_rankings", "jersey_number"],
    )
    if body.username is not None:
        if not re.match(r'^[a-zA-Z0-9_]{3,30}$', body.username):
            raise HTTPException(status_code=400, detail="账户名只能包含英文字母、数字和下划线，长度 3-30 位")
        # 同时检查 Player 和 User 表的唯一性
        conflict = await db.execute(
            select(Player).where(
                Player.username == body.username,
                Player.id != current_player.id,
            )
        )
        if conflict.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该账户名已被使用")
        user_conflict = await db.execute(
            select(User).where(
                User.username == body.username,
                User.id != current_player.user_id,
            )
        )
        if user_conflict.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该账户名已被使用")
        current_player.username = body.username
        # 同步更新关联 User 的 username
        if current_player.user_id:
            user_result = await db.execute(select(User).where(User.id == current_player.user_id))
            if u := user_result.scalar_one_or_none():
                u.username = body.username

    if body.display_name is not None:
        conflict = await db.execute(
            select(Player).where(
                Player.display_name == body.display_name,
                Player.id != current_player.id,
                Player.team_id == current_player.team_id,
            )
        )
        if conflict.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该显示名称已被他人使用")
        current_player.display_name = body.display_name

    if body.email is not None:
        if body.email == "":
            current_player.email = None
        else:
            # 同时检查 Player 和 User 表的邮箱唯一性
            conflict = await db.execute(
                select(Player).where(
                    Player.email == body.email,
                    Player.id != current_player.id,
                )
            )
            if conflict.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="该邮箱已被其他账号绑定")
            user_email_conflict = await db.execute(
                select(User).where(
                    User.email == body.email,
                    User.id != current_player.user_id,
                )
            )
            if user_email_conflict.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="该邮箱已被其他账号绑定")
            current_player.email = body.email

    if body.gender is not None:
        if body.gender == "":
            current_player.gender = None
        elif body.gender not in ("M", "F"):
            raise HTTPException(status_code=400, detail="gender 只能是 M 或 F")
        else:
            current_player.gender = body.gender

    if body.show_in_rankings is not None:
        current_player.show_in_rankings = body.show_in_rankings

    if body.jersey_number is not None:
        if body.jersey_number < 0 or body.jersey_number > 999:
            raise HTTPException(status_code=400, detail="球衣号码必须在0-999之间")
        current_player.jersey_number = body.jersey_number
    elif hasattr(body, 'jersey_number') and 'jersey_number' in (body.model_fields_set or set()):
        current_player.jersey_number = None

    after_profile = snapshot_fields(
        current_player,
        ["username", "display_name", "email", "gender", "show_in_rankings", "jersey_number"],
    )
    if before_profile["email"]:
        before_profile["email"] = mask_email(before_profile["email"])
    if after_profile["email"]:
        after_profile["email"] = mask_email(after_profile["email"])
    await write_audit(
        db,
        current_player,
        "player_profile_updated",
        team_id=current_player.team_id,
        target_type="player",
        target_id=current_player.id,
        detail=build_change_detail(before=before_profile, after=after_profile),
    )
    await db.commit()
    await db.refresh(current_player)
    return current_player


# ——— T051 [US6]: 双层资料更新 ———

@router.patch("/me/profile/dual", status_code=200)
async def update_dual_layer_profile(
    body: DualLayerProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    current_player: Player = Depends(get_current_active_player),
    db: AsyncSession = Depends(get_db),
):
    """双层资料更新：user.username（全局唯一）与当前队伍 player 字段（昵称等）分别更新。"""
    # ── user 层：修改全局用户名 ──
    if body.user and body.user.username is not None:
        new_uname = body.user.username
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', new_uname):
            raise HTTPException(status_code=400, detail="用户名只能包含英文字母、数字和下划线，长度 3-20 位")
        conflict_user = (
            await db.execute(
                select(User).where(User.username == new_uname, User.id != current_user.id)
            )
        ).scalar_one_or_none()
        if conflict_user:
            raise HTTPException(status_code=400, detail="该用户名已被使用")
        current_user.username = new_uname
        # 同步到 player.username（保持一致）
        current_player.username = new_uname

    # ── player 层：修改当前队伍昵称等字段 ──
    if body.player:
        pl = body.player
        if pl.display_name is not None:
            current_player.display_name = pl.display_name or None
        if "email" in (pl.model_fields_set or set()):
            if pl.email in (None, ""):
                current_player.email = None
            else:
                conflict_email = (
                    await db.execute(
                        select(Player).where(
                            Player.email == pl.email,
                            Player.id != current_player.id,
                        )
                    )
                ).scalar_one_or_none()
                if conflict_email:
                    raise HTTPException(status_code=400, detail="该邮箱已被其他账号绑定")
                current_player.email = pl.email
        if pl.gender is not None:
            if pl.gender == "":
                current_player.gender = None
            elif pl.gender not in ("M", "F"):
                raise HTTPException(status_code=400, detail="gender 只能是 M 或 F")
            else:
                current_player.gender = pl.gender
        if pl.jersey_number is not None:
            current_player.jersey_number = pl.jersey_number
        if pl.show_in_rankings is not None:
            current_player.show_in_rankings = pl.show_in_rankings

    await db.commit()
    await db.refresh(current_player)
    await db.refresh(current_user)
    await write_audit(
        db, current_player, "profile_dual_updated",
        team_id=current_player.team_id,
        target_type="player",
        target_id=current_player.id,
        detail=build_change_detail(
            after={
                "user_username": current_user.username,
                "display_name": current_player.display_name,
            }
        ),
    )
    await db.commit()
    return DualLayerProfileUpdateResponse(
        user_username=current_user.username,
        display_name=current_player.display_name,
        email=current_player.email,
        gender=current_player.gender,
        jersey_number=current_player.jersey_number,
        show_in_rankings=current_player.show_in_rankings,
    )


# ——— 战力历史 ———

class RatingHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_id: int
    mu_before: float
    mu_after: float
    sigma_before: float
    sigma_after: float
    conservative_before: float
    conservative_after: float
    delta_mu: float
    created_at: str


@router.get("/me/rating_history", response_model=list[RatingHistoryItem])
async def get_my_rating_history(
    limit: int = Query(20, ge=1, le=100),
    current_player: Player = Depends(get_current_active_player),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户最近的战力变化历史（默认最新 20 条）"""
    result = await db.execute(
        select(RatingHistory)
        .where(RatingHistory.player_id == current_player.id)
        .order_by(desc(RatingHistory.created_at))
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        RatingHistoryItem(
            match_id=r.match_id,
            mu_before=round(r.mu_before, 3),
            mu_after=round(r.mu_after, 3),
            sigma_before=round(r.sigma_before, 3),
            sigma_after=round(r.sigma_after, 3),
            conservative_before=round(r.conservative_before, 2),
            conservative_after=round(r.conservative_after, 2),
            delta_mu=round(r.delta_mu, 3),
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


# ——— 每场比赛个人数据统计 ———

class MatchStatItem(BaseModel):
    match_id: int
    match_date: str
    goals: int
    assists: int
    defenses: int
    plus_minus: int
    is_winner: bool


@router.get("/me/match_stats", response_model=list[MatchStatItem])
async def get_my_match_stats(
    limit: int = Query(20, ge=1, le=50),
    current_player: Player = Depends(get_current_active_player),
    db: AsyncSession = Depends(get_db),
):
    """获取最近 N 场已审批比赛的个人数据统计（得分/助攻/防守/胜负）"""
    result = await db.execute(
        select(MatchPlayer, Match.match_date)
        .join(Match, MatchPlayer.match_id == Match.id)
        .where(
            MatchPlayer.player_id == current_player.id,
            Match.status == MatchStatus.approved,
        )
        .order_by(Match.match_date.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        MatchStatItem(
            match_id=mp.match_id,
            match_date=match_date.isoformat(),
            goals=mp.goals or 0,
            assists=mp.assists or 0,
            defenses=mp.defenses or 0,
            plus_minus=mp.plus_minus or 0,
            is_winner=bool(mp.is_winner),
        )
        for mp, match_date in rows
    ]


# ─── 管理员专用：新建 / 编辑 / 移出 ─────────────────────────────────────────


class AdminCreatePlayerRequest(BaseModel):
    username: str
    display_name: str | None = None
    email: str | None = None
    password: str
    gender: str | None = None
    jersey_number: int | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_]{3,30}$', v):
            raise ValueError("账户名只能包含英文字母、数字和下划线，长度 3-30 位")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码最少 6 位")
        return v


class AdminEditPlayerRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None
    gender: str | None = None
    jersey_number: int | None = None


@router.post("/admin-create", status_code=201, response_model=PlayerPublic)
async def admin_create_player(
    body: AdminCreatePlayerRequest,
    admin: Player = Depends(require_admin),
    effective_team_id: int = Depends(get_effective_team_id),
    db: AsyncSession = Depends(get_db),
):
    """管理员直接新建队员（创建 User 级别账号 + Player 队伍分身，状态直接为 active）
    
    关键：此流程与全局 /register 一致，在 User 层验证唯一性
    """
    # ── 1. User 层唯一性检查（与 /register 保持一致） ──────────────────────
    existing_user = await db.execute(select(User).where(User.username == body.username))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该用户名已注册过账号，请通知该用户登录后申请加入队伍")
    
    if body.email:
        email_check = await db.execute(select(User).where(User.email == str(body.email)))
        if email_check.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="该邮箱已注册过账号，请通知该用户登录后申请加入队伍")

    # ── 2. 创建 User 记录（全局认证主体） ────────────────────────────────
    password_hash = get_password_hash(body.password)
    user = User(
        username=body.username,
        email=str(body.email) if body.email else None,
        password_hash=password_hash,
    )
    db.add(user)
    await db.flush()  # 获取 user.id
    
    # ── 3. 创建 Player 队伍分身（绑定到 User） ─────────────────────────────
    player = Player(
        user_id=user.id,  # ← 关键：绑定到新建的 User
        team_id=effective_team_id,
        username=body.username,
        email=body.email or None,
        password_hash=password_hash,  # 与 User 保持同步（向下兼容）
        display_name=body.display_name or body.username,
        gender=body.gender or None,
        jersey_number=body.jersey_number,
        role=UserRole.member,
        status=PlayerStatus.active,
        approved_by=admin.id,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(player)
    await db.flush()
    
    # ── 4. 写审计日志 ──────────────────────────────────────────────────────
    await write_audit(
        db,
        admin,
        "player_created",
        team_id=effective_team_id,
        target_type="player",
        target_id=player.id,
        detail=build_change_detail(
            after={
                "user_id": user.id,
                "username": player.username,
                "display_name": player.display_name,
                "email": mask_email(player.email),
                "gender": player.gender,
                "jersey_number": player.jersey_number,
                "status": player.status,
                "role": player.role,
            }
        ),
    )
    await db.commit()
    await db.refresh(player)
    return player


class GuestPlayerCreateRequest(BaseModel):
    display_name: str
    gender: str | None = None


@router.post("/guest", status_code=201, response_model=PlayerPublic)
async def create_guest_player(
    body: GuestPlayerCreateRequest,
    admin: Player = Depends(require_admin),
    effective_team_id: int = Depends(get_effective_team_id),
    db: AsyncSession = Depends(get_db),
):
    """管理员为本场外战添加外援（不进入正式榜单，无法登录）"""
    username = f"guest_{uuid.uuid4().hex[:8]}"
    player = Player(
        team_id=effective_team_id,
        username=username,
        password_hash="!",
        display_name=body.display_name,
        gender=body.gender or None,
        role=UserRole.member,
        status=PlayerStatus.active,
        is_guest=True,
        show_in_rankings=False,
        approved_by=admin.id,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(player)
    await db.flush()
    await write_audit(
        db,
        admin,
        "guest_player_created",
        team_id=effective_team_id,
        target_type="player",
        target_id=player.id,
        detail=build_change_detail(
            after={
                "display_name": player.display_name,
                "gender": player.gender,
                "is_guest": True,
            }
        ),
    )
    await db.commit()
    await db.refresh(player)
    return player


@router.put("/{player_id}/admin-edit", response_model=PlayerPublic)
async def admin_edit_player(
    player_id: int,
    body: AdminEditPlayerRequest,
    admin: Player = Depends(require_admin),
    effective_team_id: int = Depends(get_effective_team_id),
    db: AsyncSession = Depends(get_db),
):
    """管理员编辑队员个人信息（同队伍内）"""
    result = await db.execute(
        select(Player).where(Player.id == player_id, Player.team_id == effective_team_id)
    )
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="队员不存在或不属于本队")

    before_profile = snapshot_fields(
        player,
        ["display_name", "email", "gender", "jersey_number"],
    )

    if body.display_name is not None:
        conflict = await db.execute(
            select(Player).where(
                Player.display_name == body.display_name,
                Player.id != player_id,
                Player.team_id == effective_team_id,
            )
        )
        if conflict.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该显示名称已被他人使用")
        player.display_name = body.display_name

    if body.email is not None:
        if body.email:
            conflict = await db.execute(
                select(Player).where(Player.email == body.email, Player.id != player_id)
            )
            if conflict.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="该邮箱已被其他账号绑定")
        player.email = body.email or None

    if body.gender is not None:
        if body.gender == "":
            player.gender = None
        elif body.gender not in ("M", "F"):
            raise HTTPException(status_code=400, detail="gender 只能是 M 或 F")
        else:
            player.gender = body.gender

    if body.jersey_number is not None:
        player.jersey_number = body.jersey_number
    elif 'jersey_number' in (body.model_fields_set or set()):
        player.jersey_number = None

    after_profile = snapshot_fields(
        player,
        ["display_name", "email", "gender", "jersey_number"],
    )
    if before_profile["email"]:
        before_profile["email"] = mask_email(before_profile["email"])
    if after_profile["email"]:
        after_profile["email"] = mask_email(after_profile["email"])
    await write_audit(
        db,
        admin,
        "player_profile_admin_updated",
        team_id=effective_team_id,
        target_type="player",
        target_id=player.id,
        detail=build_change_detail(
            before=before_profile,
            after=after_profile,
            extra={"player_username": player.username},
        ),
    )
    await db.commit()
    await db.refresh(player)
    return player


@router.delete("/{player_id}/from-team", status_code=200)
async def remove_player_from_team(
    player_id: int,
    admin: Player = Depends(require_admin),
    effective_team_id: int = Depends(get_effective_team_id),
    db: AsyncSession = Depends(get_db),
):
    """管理员将队员移出队伍（仅清除队伍归属，保留账号及历史数据）"""
    result = await db.execute(
        select(Player).where(Player.id == player_id, Player.team_id == effective_team_id)
    )
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="队员不存在或不属于本队")
    if player.id == admin.id and not admin.is_superadmin:
        raise HTTPException(status_code=400, detail="不能将自己移出队伍")
    if player.role == UserRole.owner:
        raise HTTPException(status_code=400, detail="不能移出队伍主理人")

    before_membership = snapshot_fields(player, ["team_id", "role", "status"])
    player.team_id = None
    player.role = UserRole.member
    player.status = PlayerStatus.active
    await write_audit(
        db,
        admin,
        "player_removed_from_team",
        team_id=effective_team_id,
        target_type="player",
        target_id=player.id,
        detail=build_change_detail(
            before=before_membership,
            after=snapshot_fields(player, ["team_id", "role", "status"]),
            extra={"player_username": player.username},
        ),
    )
    await db.commit()
    return {"message": f"已将 {player.display_name or player.username} 移出队伍"}


# ─── 批量查询两两默契值 ────────────────────────────────────────────────────────

class ChemistryPairRequest(BaseModel):
    player_ids: list[int]


class ChemistryPairItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    player_a_id: int
    player_b_id: int
    chemistry_score: float
    co_matches: int


@router.post("/chemistry-pairs", response_model=list[ChemistryPairItem])
async def get_chemistry_pairs(
    body: ChemistryPairRequest,
    current_player: Player = Depends(get_current_active_player),
    effective_team_id: int = Depends(get_effective_team_id),
    db: AsyncSession = Depends(get_db),
):
    """给定一组 player_ids，返回其中所有存在历史记录的两两默契值（仅本队数据）。
    默契值来自 PlayerChemistry 表的真实算法结果（胜率×0.7 + 配合率×0.3）× 置信因子。
    """
    from app.models.match import PlayerChemistry
    if len(body.player_ids) < 2:
        return []
    result = await db.execute(
        select(PlayerChemistry).where(
            PlayerChemistry.team_id == effective_team_id,
            PlayerChemistry.player_a_id.in_(body.player_ids),
            PlayerChemistry.player_b_id.in_(body.player_ids),
        )
    )
    return [
        ChemistryPairItem(
            player_a_id=row.player_a_id,
            player_b_id=row.player_b_id,
            chemistry_score=round(float(row.chemistry_score or 0.0), 4),
            co_matches=int(row.co_matches or 0),
        )
        for row in result.scalars().all()
    ]
