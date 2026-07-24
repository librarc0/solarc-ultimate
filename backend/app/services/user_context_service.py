"""user_context_service.py — US3: 用户上下文与默认队伍回退策略。

提供 resolve_active_player 供登录/切队/context 接口复用，同时提供
get_user_teams 查询用户所有可见队伍（active 成员分身）。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player import Player, PlayerStatus
from app.models.user import User


async def resolve_active_player(db: AsyncSession, user: User) -> Player | None:
    """为指定 user 解析最合适的激活 player（含默认队伍回退策略）。

    优先级：
    1. 默认队伍（user.default_team_id）对应的 active player
    2. 任意有 team_id 的 active player
    3. 任意 active 状态的 player（team_id 可为 None，注册时的初始 player）
    4. None（用户无任何 player，罕见）
    """
    # 1. 默认队伍 active player
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


async def get_user_teams(db: AsyncSession, user: User) -> list[Player]:
    """返回 user 所有 active 队伍成员分身（team_id 不为 None 的 active Player 列表）。"""
    result = await db.execute(
        select(Player).where(
            Player.user_id == user.id,
            Player.team_id.isnot(None),
            Player.status == PlayerStatus.active,
        )
    )
    return list(result.scalars().all())


async def converge_after_leave(db: AsyncSession, user: User, left_team_id: int) -> None:
    """T046 [US5]: 退队/被踢后清理 user 级默认队伍设置。

    若 user.default_team_id 正好是刚离开的队伍，则将其清除为 None，
    使下次 resolve_active_player 能回退到其他可用队伍或无队伍状态。
    """
    if user.default_team_id == left_team_id:
        user.default_team_id = None
