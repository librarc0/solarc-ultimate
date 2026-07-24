"""微信小程序认证接口 — wx-login / wx-bind / wx-bind-confirm"""
import secrets
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_player
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.player import Player, PlayerStatus, UserRole

router = APIRouter()

# ─────────────────────────── Schemas ────────────────────────────


class WxLoginRequest(BaseModel):
    code: str


class WxLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    # 引导前端进入哪个后续流程
    # "ok"            → 已有完整账号，直接进入应用
    # "need_bind"     → 新微信用户，需选择"绑定已有账号"或"完善新账号信息"
    next_step: Literal["ok", "need_bind"]
    # 新用户时返回一次性 bind_token，用于后续 wx-bind-new 流程创建账号
    bind_token: str | None = None
    display_name: str | None = None


class WxBindExistingRequest(BaseModel):
    """已有密码账号的用户，用微信绑定它"""
    bind_token: str          # wx-login 返回的 bind_token
    username: str
    password: str


class WxBindNewRequest(BaseModel):
    """新用户用微信注册时补充的信息"""
    bind_token: str
    display_name: str


class WxBindCurrentRequest(BaseModel):
    """已登录的密码账号用户，主动绑定微信（从 Web 端扫码流程等）"""
    code: str


# ──────────────────────── 内部帮助函数 ──────────────────────────


async def _code_to_openid(code: str) -> str:
    """向微信服务器换取 openid；未配置 app_id 时走测试模式返回 code 自身。"""
    if not settings.WX_APP_ID or not settings.WX_APP_SECRET:
        # 本地开发 / 测试：直接把 code 当成 openid
        return f"fake_openid_{code}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": settings.WX_APP_ID,
                "secret": settings.WX_APP_SECRET,
                "js_code": code,
                "grant_type": "authorization_code",
            },
        )
    wx_data: dict = r.json()
    if "errcode" in wx_data and wx_data["errcode"] != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"微信授权失败: {wx_data.get('errmsg', wx_data['errcode'])}",
        )
    openid = wx_data.get("openid")
    if not openid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="微信返回数据异常")
    return openid


# ─── bind_token 简易存储（内存，单进程够用）────────────────────
# 结构：{ bind_token: openid }
_pending_binds: dict[str, str] = {}


def _alloc_bind_token(openid: str) -> str:
    token = secrets.token_urlsafe(32)
    _pending_binds[token] = openid
    return token


def _consume_bind_token(bind_token: str) -> str:
    """取出并删除 bind_token，不存在则抛 400"""
    openid = _pending_binds.pop(bind_token, None)
    if not openid:
        raise HTTPException(status_code=400, detail="bind_token 无效或已过期")
    return openid


# ─────────────────────────── 路由 ────────────────────────────


@router.post("/wx-login", response_model=WxLoginResponse)
async def wx_login(body: WxLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    微信小程序登录入口。

    场景：
    - 已绑定账号 → next_step="ok"，直接颁发 JWT
    - 未绑定   → next_step="need_bind"，返回 bind_token，
                  前端引导用户选择 wx-bind-existing 或 wx-bind-new
    """
    openid = await _code_to_openid(body.code)

    result = await db.execute(select(Player).where(Player.wx_openid == openid))
    player = result.scalar_one_or_none()

    if player:
        # 已有绑定账号 → 直接登录
        if player.status == PlayerStatus.rejected:
            raise HTTPException(status_code=403, detail="账户已被封禁，请联系管理员")
        token = create_access_token(subject=player.id, role=player.role.value)
        return WxLoginResponse(
            access_token=token,
            role=player.role.value,
            next_step="ok",
            display_name=player.display_name,
        )

    # 未绑定 → 生成 bind_token 暂存 openid，让前端引导绑定
    bind_token = _alloc_bind_token(openid)
    return WxLoginResponse(
        access_token="",
        role="",
        next_step="need_bind",
        bind_token=bind_token,
    )


@router.post("/wx-bind-existing")
async def wx_bind_existing(body: WxBindExistingRequest, db: AsyncSession = Depends(get_db)):
    """
    微信新用户绑定已有密码账号。

    流程：wx-login 返回 need_bind → 用户选择"绑定已有账号"
    → 输入已有用户名+密码 → 本接口验证后绑定并颁发 JWT
    """
    openid = _consume_bind_token(body.bind_token)

    # 验证用户名+密码
    from sqlalchemy import or_
    result = await db.execute(
        select(Player).where(
            or_(Player.username == body.username, Player.email == body.username)
        )
    )
    player = result.scalar_one_or_none()
    if not player or not verify_password(body.password, player.password_hash):
        # 失败时把 bind_token 放回去，让用户可以重试
        _pending_binds[body.bind_token] = openid
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if player.status == PlayerStatus.rejected:
        raise HTTPException(status_code=403, detail="账户已被封禁")

    # 检查 openid 未被其他账号占用
    dup = await db.execute(select(Player).where(Player.wx_openid == openid))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该微信已绑定其他账号")

    player.wx_openid = openid
    await db.commit()

    token = create_access_token(subject=player.id, role=player.role.value)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": player.role.value,
        "display_name": player.display_name,
    }


@router.post("/wx-bind-new")
async def wx_bind_new(body: WxBindNewRequest, db: AsyncSession = Depends(get_db)):
    """
    微信新用户注册新账号（无需手动输入用户名密码）。

    流程：wx-login 返回 need_bind → 用户选择"直接注册新账号"
    → 仅提供昵称 → 本接口创建账号并绑定 openid
    """
    openid = _consume_bind_token(body.bind_token)

    # 生成唯一临时用户名
    base = f"wx{openid[-8:]}"
    suffix = 0
    while True:
        candidate = base if suffix == 0 else f"{base}{suffix}"
        existing = await db.execute(select(Player).where(Player.username == candidate))
        if not existing.scalar_one_or_none():
            break
        suffix += 1

    player = Player(
        wx_openid=openid,
        username=candidate,
        # 微信注册账号无密码（无法用密码登录，只能微信登录）
        password_hash=get_password_hash(secrets.token_urlsafe(32)),
        display_name=body.display_name or candidate,
        role=UserRole.member,
        status=PlayerStatus.active,
    )
    db.add(player)
    await db.commit()
    await db.refresh(player)

    token = create_access_token(subject=player.id, role=player.role.value)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": player.role.value,
        "display_name": player.display_name,
    }


@router.post("/wx-bind")
async def wx_bind_current(
    body: WxBindCurrentRequest,
    current_player: Player = Depends(get_current_active_player),
    db: AsyncSession = Depends(get_db),
):
    """
    已登录的密码账号用户，主动绑定自己的微信。
    （在 Web 版个人资料页面或小程序设置页面触发）
    """
    if current_player.wx_openid:
        raise HTTPException(status_code=409, detail="当前账号已绑定微信，如需更换请先解绑")

    openid = await _code_to_openid(body.code)

    dup = await db.execute(select(Player).where(Player.wx_openid == openid))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该微信已绑定其他账号，如需换绑请先解绑")

    current_player.wx_openid = openid
    await db.commit()
    return {"message": "微信绑定成功"}


@router.delete("/wx-unbind")
async def wx_unbind(
    current_player: Player = Depends(get_current_active_player),
    db: AsyncSession = Depends(get_db),
):
    """解绑微信（需要账号有密码才能解绑，否则会失去登录方式）"""
    if not current_player.wx_openid:
        raise HTTPException(status_code=400, detail="当前账号未绑定微信")

    # 纯微信账号（no email/password_hash set via normal register）没有其他登录方式，禁止解绑
    # 判断方式：email 为空且 password_hash 是随机串（wx-bind-new 生成的）
    # 实际上用 email 是否存在来判断更可靠
    if not current_player.email:
        raise HTTPException(
            status_code=400,
            detail="纯微信账号无法解绑（解绑后将无法登录），请先在个人资料中设置邮箱和密码",
        )

    current_player.wx_openid = None
    await db.commit()
    return {"message": "微信解绑成功"}
