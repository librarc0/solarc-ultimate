"""T023 + US1: /auth 路由 — 注册/登录/me/context/switch-team"""
import asyncio
from datetime import datetime, timedelta, timezone
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.player import Player, PlayerStatus, UserRole
from app.models.user import User
from app.schemas.auth import RegisterRequest, TokenResponse
from app.api.v1.deps import get_current_active_player, get_current_user
from app.services.audit_service import build_change_detail, mask_email, write_audit

router = APIRouter()


# ──────────────────────────────────────────────────────────────────────────────
# 注册：同时创建 User（认证主体）+ Player（队伍业务分身，team_id=None）
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """创建账号 —— 注册时同时建立 User 与初始 Player 分身。

    User 是全局认证主体；Player 是队伍内业务分身，注册时 team_id=None，
    登录后在首页加入或创建队伍（加入后 team_id 会被设置）。
    """
    # 检查用户名唯一（User 层）
    existing_user = await db.execute(select(User).where(User.username == body.username))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 检查邮箱唯一（User 层）
    if body.email:
        email_check = await db.execute(select(User).where(User.email == str(body.email)))
        if email_check.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该邮箱已被注册")

    # 1. 创建 User（认证主体）
    password_hash = get_password_hash(body.password)
    user = User(
        username=body.username,
        email=str(body.email) if body.email else None,
        password_hash=password_hash,
    )
    db.add(user)
    await db.flush()  # 获取 user.id

    # 2. 创建初始 Player 分身（team_id=None，等待加入队伍）
    player = Player(
        user_id=user.id,
        team_id=None,
        username=body.username,
        email=str(body.email) if body.email else None,
        password_hash=password_hash,  # 与 User 保持同步，兼容旧逻辑
        display_name=body.display_name or body.username,
        role=UserRole.member,
        status=PlayerStatus.active,
    )
    db.add(player)
    await db.flush()

    await write_audit(
        db,
        player,
        "player_registered",
        team_id=None,
        target_type="player",
        target_id=player.id,
        detail=build_change_detail(
            after={
                "username": player.username,
                "display_name": player.display_name,
                "email": mask_email(player.email),
                "status": player.status,
                "role": player.role,
                "user_id": user.id,
            }
        ),
    )
    await db.commit()
    return {"code": 0, "data": {}, "message": "注册成功！请登录后加入或创建队伍"}


# ──────────────────────────────────────────────────────────────────────────────
# 登录：通过 User 认证，token 携带 user_id + active_player_id
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """用户名/邮箱登录，优先走 User 认证路径。

    向下兼容：若数据库中尚无 User 记录（迁移前旧账号），降级到 Player 直接认证。
    新 token 格式：{"sub": user_id, "player_id": active_player_id, "role": ...}
    """
    # ── 新路径：通过 User 认证 ────────────────────────────────────────────
    user_result = await db.execute(
        select(User).where(
            or_(
                User.username == form_data.username,
                User.email == form_data.username,
            )
        )
    )
    user = user_result.scalar_one_or_none()

    if user and verify_password(form_data.password, user.password_hash):
        # 找到该 user 最合适的激活 player
        active_player = await _resolve_active_player(db, user)
        # 若所有 player 均为 rejected（无活跃 player 但有被拒绝的 player），拒绝登录
        if active_player is None:
            any_player_result = await db.execute(
                select(Player).where(Player.user_id == user.id)
            )
            all_players = any_player_result.scalars().all()
            if all_players and all(p.status == PlayerStatus.rejected for p in all_players):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="账户已被拒绝，请联系管理员",
                )
        # 更新最后登录时间
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()

        role = active_player.role.value if active_player else UserRole.member.value
        token = create_access_token(
            subject=user.id,
            role=role,
            player_id=active_player.id if active_player else None,
        )
        return TokenResponse(access_token=token, token_type="bearer", role=role)

    # ── 兼容路径：降级到 Player 直接认证（适用于迁移前旧账号）──────────
    player_result = await db.execute(
        select(Player).where(
            or_(Player.username == form_data.username, Player.email == form_data.username)
        )
    )
    player = player_result.scalar_one_or_none()

    if not player or not verify_password(form_data.password, player.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名/邮箱或密码错误",
        )
    if player.status == PlayerStatus.rejected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被拒绝，请联系管理员",
        )

    # 旧格式 token（sub=player_id），向下兼容
    token = create_access_token(subject=player.id, role=player.role.value)
    return TokenResponse(access_token=token, token_type="bearer", role=player.role.value)


async def _resolve_active_player(db: AsyncSession, user: User) -> Player | None:
    """为登录 user 解析最合适的激活 player。

    优先级：
    1. 默认队伍对应的 active player
    2. 任意 active 状态且有 team_id 的 player
    3. 任意 active 状态的 player（可能 team_id=None）
    4. None（用户无任何 player，罕见）
    """
    # 1. 默认队伍对应的 active player
    if user.default_team_id is not None:
        result = await db.execute(
            select(Player).where(
                Player.user_id == user.id,
                Player.team_id == user.default_team_id,
                Player.status == PlayerStatus.active,
            )
        )
        p = result.scalar_one_or_none()
        if p:
            return p

    # 2. 任意有 team_id 的 active player
    result = await db.execute(
        select(Player).where(
            Player.user_id == user.id,
            Player.team_id.isnot(None),
            Player.status == PlayerStatus.active,
        ).limit(1)
    )
    p = result.scalar_one_or_none()
    if p:
        return p

    # 3. 无队伍的 active player（注册时创建的初始 player）
    result = await db.execute(
        select(Player).where(
            Player.user_id == user.id,
            Player.status == PlayerStatus.active,
        ).limit(1)
    )
    return result.scalar_one_or_none()


# ──────────────────────────────────────────────────────────────────────────────
# /me：向下兼容旧调用（返回当前激活 player 信息）
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/me")
async def get_me(current_player: Player = Depends(get_current_active_player)):
    """返回当前激活 player 信息（兼容旧接口）。"""
    return {
        "id": current_player.id,
        "username": current_player.username,
        "display_name": current_player.display_name,
        "role": current_player.role.value,
        "status": current_player.status.value,
        "mu": current_player.mu,
        "sigma": current_player.sigma,
        "conservative_rating": current_player.conservative_rating,
        "email": current_player.email,
    }


# ──────────────────────────────────────────────────────────────────────────────
# /me/context：US1 — 统一账号登录并加载可用队伍上下文
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/me/context")
async def get_me_context(
    current_user: User = Depends(get_current_user),
    current_player: Player = Depends(get_current_active_player),
    db: AsyncSession = Depends(get_db),
):
    """返回 user 全局身份 + 可进入的队伍列表 + 当前激活 player 上下文。

    US1 验收场景：
    - 无队伍用户 → teams=[], active_player=None
    - 有队伍用户 → teams 含该队伍入口，active_player 含当前队伍上下文
    """
    # 查询该 user 所有可见 player（active 状态，且已绑定队伍），顺带 eager-load team
    teams_result = await db.execute(
        select(Player)
        .options(selectinload(Player.team))
        .where(
            Player.user_id == current_user.id,
            Player.team_id.isnot(None),
            Player.status == PlayerStatus.active,
        )
    )
    team_players = teams_result.scalars().all()

    # 构建队伍列表
    teams_list = []
    for tp in team_players:
        team_name = None
        if tp.team:
            team_name = tp.team.name
        teams_list.append({
            "team_id": tp.team_id,
            "team_name": team_name,
            "player_id": tp.id,
            "role": tp.role.value,
            "status": tp.status.value,
        })

    # 构建当前激活 player 信息
    active_player_info = None
    if current_player.team_id is not None:
        active_player_info = {
            "player_id": current_player.id,
            "team_id": current_player.team_id,
            "role": current_player.role.value,
            "status": current_player.status.value,
            "display_name": current_player.display_name,
            "mu": current_player.mu,
            "conservative_rating": current_player.conservative_rating,
        }

    return {
        "code": 0,
        "data": {
            "user_id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "is_superadmin": current_user.is_superadmin,
            "default_team_id": current_user.default_team_id,
            "teams": teams_list,
            "active_player": active_player_info,
        },
        "message": "",
    }


# ──────────────────────────────────────────────────────────────────────────────
# /switch-team：US2 — 统一切队机制（普通用户与超级管理员同一交互）
# ──────────────────────────────────────────────────────────────────────────────


class SwitchTeamRequest(BaseModel):
    """切换队伍请求体"""
    team_id: int


@router.post("/switch-team")
async def switch_team(
    body: SwitchTeamRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """切换当前激活队伍并颁发新 token（player_id 更新为目标队伍的 player）。

    US2 验收场景：
    - 普通用户：必须是目标队伍的 active 成员
    - 超级管理员：可切换到任意目标队伍（自动使用自身 player 或无限制上下文）
    """
    from app.models.team import Team

    # 查找目标队伍
    team_result = await db.execute(
        select(Team).where(Team.id == body.team_id, Team.is_active.is_(True))
    )
    team = team_result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")

    # 查找该 user 在目标队伍的 active player
    player_result = await db.execute(
        select(Player).where(
            Player.user_id == current_user.id,
            Player.team_id == body.team_id,
            Player.status == PlayerStatus.active,
        )
    )
    player = player_result.scalar_one_or_none()

    if not player:
        if current_user.is_superadmin:
            # 超级管理员：无需成员资格，使用自身任意 player（或 None player 走 query param 路径）
            any_player_result = await db.execute(
                select(Player).where(Player.user_id == current_user.id).limit(1)
            )
            player = any_player_result.scalar_one_or_none()
            if not player:
                raise HTTPException(status_code=400, detail="超级管理员账号无 player 分身，请先注册")
        else:
            raise HTTPException(status_code=403, detail="您不是该队伍的成员，无法切换")

    # 颁发新 token，player_id 更新为目标 player
    role = player.role.value if player else UserRole.member.value
    new_token = create_access_token(
        subject=current_user.id,
        role=role,
        player_id=player.id,
    )

    return {
        "code": 0,
        "data": {
            "access_token": new_token,
            "token_type": "bearer",
            "role": role,
            "team_id": body.team_id,
            "player_id": player.id,
        },
        "message": "切换队伍成功",
    }


# ──────────────────────────────────────────────────────────────────────────────
# /me/default-team：US3 — 设置默认队伍
# ──────────────────────────────────────────────────────────────────────────────


class SetDefaultTeamRequest(BaseModel):
    """设置默认队伍请求体"""
    team_id: int | None = None  # None 表示清除默认队伍


@router.post("/me/default-team")
async def set_default_team(
    body: SetDefaultTeamRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """设置用户默认队伍偏好（US3: 我的页面管理所属队伍与默认队伍）。

    - team_id=None → 清除默认队伍
    - team_id=X → 验证 user 在该队伍为 active 成员，然后保存
    """
    if body.team_id is not None:
        # 校验 user 是该队伍的 active 成员（或为超级管理员）
        if not current_user.is_superadmin:
            member_result = await db.execute(
                select(Player).where(
                    Player.user_id == current_user.id,
                    Player.team_id == body.team_id,
                    Player.status == PlayerStatus.active,
                )
            )
            if not member_result.scalar_one_or_none():
                raise HTTPException(status_code=403, detail="您不是该队伍的 active 成员，无法设置为默认队伍")

    current_user.default_team_id = body.team_id
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "code": 0,
        "data": {"default_team_id": body.team_id},
        "message": "默认队伍已更新",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic request schemas（找回密码流程）
# ──────────────────────────────────────────────────────────────────────────────


class ForgotPasswordRequest(BaseModel):
    username: str
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str


class ResetPasswordRequest(BaseModel):
    confirmed_token: str
    new_password: str
    confirm_password: str


# ——— T080: 步骤一 — 验证用户名+邮箱，发送 6 位验证码 ———

@router.post("/forgot-password", status_code=200)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    步骤一：验证用户名与邮箱匹配，发送 6 位数字验证码到邮箱（15 分钟有效）。
    若 SMTP 未配置返回 403；用户名/邮箱不匹配返回 400。
    """
    if not settings.SMTP_HOST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员未配置邮件服务，请联系管理员直接重置密码。",
        )

    # 优先通过 User 表查找（新账号），降级到 Player 表（旧账号）
    user_result = await db.execute(
        select(User).where(
            User.username == body.username,
            User.email == str(body.email),
        )
    )
    linked_user = user_result.scalar_one_or_none()

    player = None
    if linked_user:
        # 新账号：通过 user_id 找到关联 player
        player_result = await db.execute(
            select(Player).where(Player.user_id == linked_user.id).limit(1)
        )
        player = player_result.scalar_one_or_none()
        # 若 player 没有 email，使用 user 的 email
        reset_email = linked_user.email
    else:
        # 旧账号降级
        result = await db.execute(
            select(Player).where(
                Player.username == body.username,
                Player.email == str(body.email),
            )
        )
        player = result.scalar_one_or_none()
        reset_email = player.email if player else None

    if not player:
        raise HTTPException(status_code=400, detail="用户名与邮箱不匹配，请检查后重试。")

    if not reset_email:
        raise HTTPException(status_code=400, detail="该账号未绑定邮箱，请联系管理员重置。")

    # 生成 6 位验证码，存储为 "C:123456"，15 分钟有效
    code = f"{secrets.randbelow(900000) + 100000}"
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    player.reset_token = f"C:{code}"
    player.reset_token_expires = expires

    await write_audit(
        db,
        player,
        "player_password_reset_requested",
        team_id=player.team_id,
        target_type="player",
        target_id=player.id,
        detail=build_change_detail(
            extra={
                "email": mask_email(player.email),
                "expires_at": expires,
            }
        ),
    )
    await db.commit()

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, _send_code_email, reset_email, player.display_name or player.username, code
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="邮件发送失败，请联系管理员直接重置密码。",
        )
    return {"message": "验证码已发送，请查收邮件。"}


# ——— T080: 步骤二 — 验证 6 位验证码 ———

@router.post("/verify-reset-code", status_code=200)
async def verify_reset_code(body: VerifyCodeRequest, db: AsyncSession = Depends(get_db)):
    """
    步骤二：验证 6 位验证码，通过后颁发一次性 confirmed_token（10 分钟有效）。
    """
    result = await db.execute(
        select(Player).where(Player.email == str(body.email))
    )
    player = result.scalar_one_or_none()

    if not player or not player.reset_token or not player.reset_token.startswith("C:"):
        raise HTTPException(status_code=400, detail="验证码无效，请重新申请。")

    now = datetime.now(timezone.utc)
    expires = player.reset_token_expires
    # SQLite 可能回读为 naive datetime，统一补全 UTC tzinfo 再比较
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires is None or expires < now:
        raise HTTPException(status_code=400, detail="验证码已过期，请重新申请。")

    stored_code = player.reset_token[2:]  # 去掉 "C:" 前缀
    if stored_code != body.code.strip():
        raise HTTPException(status_code=400, detail="验证码错误，请重新输入。")

    # 验证通过，颁发 confirmed_token（K: 前缀区分），10 分钟有效
    confirmed = secrets.token_urlsafe(32)
    player.reset_token = f"K:{confirmed}"
    player.reset_token_expires = now + timedelta(minutes=10)
    await db.commit()

    return {"confirmed_token": confirmed}


# ——— T080: 步骤三 — 设置新密码 ———

@router.post("/reset-password", status_code=200)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """步骤三：验证 confirmed_token，两次密码一致且 ≥8 位，完成重置。"""
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=422, detail="两次输入的密码不一致")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="新密码至少 8 位")

    expected_token = f"K:{body.confirmed_token}"
    result = await db.execute(
        select(Player).where(Player.reset_token == expected_token)
    )
    player = result.scalar_one_or_none()

    if not player or player.reset_token_expires is None:
        raise HTTPException(status_code=400, detail="重置凭证无效，请重新走流程。")

    now = datetime.now(timezone.utc)
    expires_k = player.reset_token_expires
    if expires_k.tzinfo is None:
        expires_k = expires_k.replace(tzinfo=timezone.utc)
    if expires_k < now:
        raise HTTPException(status_code=400, detail="重置凭证已过期，请重新走流程。")

    new_hash = get_password_hash(body.new_password)
    player.password_hash = new_hash
    player.reset_token = None
    player.reset_token_expires = None
    # 同步更新关联 User 的密码（确保新密码通过 User 路径也有效）
    if player.user_id:
        user_result2 = await db.execute(select(User).where(User.id == player.user_id))
        linked_user = user_result2.scalar_one_or_none()
        if linked_user:
            linked_user.password_hash = new_hash
    await write_audit(
        db,
        player,
        "player_password_reset_completed",
        team_id=player.team_id,
        target_type="player",
        target_id=player.id,
        detail=build_change_detail(extra={"email": mask_email(player.email)}),
    )
    await db.commit()
    return {"message": "密码已重置，请重新登录"}


def _send_code_email(to_email: str, username: str, code: str) -> None:
    """发送 HTML 格式的 6 位验证码邮件。"""
    html = f"""
<div style="font-family:'PingFang SC','Microsoft YaHei',sans-serif;max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
  <div style="background:linear-gradient(135deg,#1d4ed8 0%,#2563eb 100%);padding:28px 24px;text-align:center;">
    <h1 style="color:#fff;margin:0;font-size:22px;font-weight:700;">Solarc-Ultimate 密码重置</h1>
  </div>
  <div style="padding:28px 24px;">
    <p style="color:#374151;font-size:15px;margin:0 0 16px;">你好，<strong>{username}</strong>！</p>
    <p style="color:#374151;font-size:15px;margin:0 0 20px;">你正在申请重置密码，验证码为：</p>
    <div style="background:#eff6ff;border:2px dashed #3b82f6;border-radius:10px;padding:20px;text-align:center;margin:0 0 20px;">
      <span style="font-size:42px;font-weight:800;letter-spacing:12px;color:#1d4ed8;">{code}</span>
    </div>
    <p style="color:#6b7280;font-size:13px;margin:0 0 8px;">⏱ 验证码 <strong>15 分钟</strong>内有效，请尽快完成操作。</p>
    <p style="color:#6b7280;font-size:13px;margin:0;">🔒 如非本人操作，请忽略此邮件，账号安全不受影响。</p>
  </div>
  <div style="background:#f9fafb;padding:14px 24px;text-align:center;border-top:1px solid #e5e7eb;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">Solarc-Ultimate · 极限飞盘队伍管理系统</p>
  </div>
</div>
"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【Solarc-Ultimate】密码重置验证码：{code}"
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USERNAME
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    _SMTP_TIMEOUT = 10  # seconds

    def _open_client(client_cls):
        # 兼容测试替身：某些 FakeSMTP 不支持 timeout 参数
        try:
            return client_cls(settings.SMTP_HOST, settings.SMTP_PORT, timeout=_SMTP_TIMEOUT)
        except TypeError:
            return client_cls(settings.SMTP_HOST, settings.SMTP_PORT)

    if settings.SMTP_PORT == 465:
        with _open_client(smtplib.SMTP_SSL) as server:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], [to_email], msg.as_string())
    else:
        with _open_client(smtplib.SMTP) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], [to_email], msg.as_string())
