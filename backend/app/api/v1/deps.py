from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.player import Player, PlayerStatus, UserRole
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ──────────────────────────────────────────────────────────────────────────────
# 新架构：User 级别鉴权依赖
# ──────────────────────────────────────────────────────────────────────────────


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从新格式 JWT（sub=user_id）解析全局 User 身份。

    新格式 token 结构：{"sub": "<user_id>", "player_id": "<active_player_id>", "role": "..."}
    """
    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")
    try:
        uid = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


# ──────────────────────────────────────────────────────────────────────────────
# 兼容层：Player 级别鉴权依赖（同时支持新/旧 token 格式）
# ──────────────────────────────────────────────────────────────────────────────


async def get_current_active_player(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Player:
    """解析当前激活 Player。

    优先使用新格式 token（player_id 字段），降级兼容旧格式（sub=player_id）。
    - 新格式：{"sub": "<user_id>", "player_id": "<player_id>"}  → 通过 player_id 查 player
    - 旧格式：{"sub": "<player_id>"}（无 player_id 字段）→ 通过 sub 直接查 player
    """
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")

    # 判断 token 格式：新格式含 player_id 字段
    player_id_str = payload.get("player_id")
    sub_str = payload.get("sub")

    if not sub_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")

    try:
        if player_id_str:
            # 新格式：通过 player_id 解析激活 player
            pid = int(player_id_str)
        else:
            # 旧格式兼容：sub 直接是 player_id
            pid = int(sub_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")

    result = await db.execute(select(Player).where(Player.id == pid))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if player.status == PlayerStatus.rejected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账户已被拒绝，请联系管理员")
    return player


async def require_admin(
    current_player: Player = Depends(get_current_active_player),
) -> Player:
    if current_player.is_superadmin:
        return current_player
    if current_player.role not in (UserRole.admin, UserRole.owner):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_player


async def require_owner(
    current_player: Player = Depends(get_current_active_player),
) -> Player:
    if current_player.is_superadmin:
        return current_player
    if current_player.role != UserRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要主理人权限")
    return current_player


async def require_team_member(
    current_player: Player = Depends(get_current_active_player),
) -> Player:
    """require 已加入队伍且 status=active"""
    if current_player.team_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请先加入队伍")
    if current_player.status != PlayerStatus.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您的队伍申请正在审核中")
    return current_player


async def get_optional_player(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[Player]:
    """可选认证：有 token 时返回用户，无 token/token 无效时返回 None。

    同样支持新/旧 token 格式。
    """
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None

    player_id_str = payload.get("player_id")
    sub_str = payload.get("sub")
    if not sub_str:
        return None

    try:
        pid = int(player_id_str) if player_id_str else int(sub_str)
    except (ValueError, TypeError):
        return None

    result = await db.execute(select(Player).where(Player.id == pid))
    player = result.scalar_one_or_none()
    if not player or player.status != PlayerStatus.active:
        return None
    return player


async def get_effective_team_id(
    current_player: Player = Depends(get_current_active_player),
    viewing_team_id: int | None = Query(None, alias="team_id"),
    db: AsyncSession = Depends(get_db),
) -> int:
    """超级管理员可通过 ?team_id=X 切换查看的队伍；普通用户返回自己的 team_id。

    T025 [US2]: 优先使用 User.is_superadmin 作为权威来源（兼容 Player.is_superadmin）。
    """
    # 判断超管：Player 层或 User 层任一为 True 都视为超管
    is_sa = current_player.is_superadmin
    if not is_sa and current_player.user_id is not None:
        result = await db.execute(select(User).where(User.id == current_player.user_id))
        user = result.scalar_one_or_none()
        if user and user.is_superadmin:
            is_sa = True

    if is_sa and viewing_team_id is not None:
        return viewing_team_id
    if not current_player.team_id:
        raise HTTPException(status_code=403, detail="请先加入队伍")
    return current_player.team_id


async def require_superadmin(
    current_player: Player = Depends(get_current_active_player),
) -> Player:
    if not current_player.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要超级管理员权限")
    return current_player
