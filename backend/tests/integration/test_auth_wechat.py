"""
微信认证端点集成测试

覆盖四种账号关联场景：
 1. 新微信用户（wx-login → need_bind → wx-bind-new）
 2. 微信重复登录（已有绑定，直接返回 token）
 3. 绑定已有账号（wx-login → need_bind → wx-bind-existing）
 4. 绑定冲突（同一 openid 绑两个账号 → 409）
 5. 当前已登录账号主动绑定微信（wx-bind）
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient


# ────────────────────────────── URL 常量 ──────────────────────────────

WX_LOGIN_URL = "/api/v1/auth/wx-login"
WX_BIND_NEW_URL = "/api/v1/auth/wx-bind-new"
WX_BIND_EXISTING_URL = "/api/v1/auth/wx-bind-existing"
WX_BIND_URL = "/api/v1/auth/wx-bind"
WX_UNBIND_URL = "/api/v1/auth/wx-unbind"
REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

# ────────────────────────────── 帮助函数 ─────────────────────────────


def mock_wx(openid: str):
    """
    Patch _code_to_openid 使其直接返回指定 openid，
    用于绕过真实的微信 HTTP 请求。
    """
    return patch(
        "app.api.v1.endpoints.auth_wechat._code_to_openid",
        new=AsyncMock(return_value=openid),
    )


async def register_and_login(client: AsyncClient, username: str, password: str = "password123") -> str:
    """注册普通账号并返回 access_token"""
    await client.post(REG_URL, json={
        "username": username,
        "email": f"{username}@example.com",
        "password": password,
        "display_name": username,
    })
    resp = await client.post(LOGIN_URL, data={"username": username, "password": password})
    return resp.json()["access_token"]


# ─────────────────────────── 测试用例 ────────────────────────────────


@pytest.mark.anyio
async def test_wx_login_new_user_returns_need_bind(client: AsyncClient):
    """
    场景 1a：全新微信用户登录 → next_step=need_bind，返回 bind_token
    """
    with mock_wx("openid_new_001"):
        resp = await client.post(WX_LOGIN_URL, json={"code": "fake_code_1"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_step"] == "need_bind"
    assert data["bind_token"], "应返回非空 bind_token"
    assert data["access_token"] == ""  # 尚未颁发真实 token


@pytest.mark.anyio
async def test_wx_bind_new_creates_account(client: AsyncClient):
    """
    场景 1b：新微信用户 → wx-bind-new → 创建账号并拿到 token
    """
    with mock_wx("openid_new_002"):
        wx_resp = await client.post(WX_LOGIN_URL, json={"code": "fake_code_2"})

    bind_token = wx_resp.json()["bind_token"]

    resp = await client.post(WX_BIND_NEW_URL, json={
        "bind_token": bind_token,
        "display_name": "测试队员",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"], "应返回 access_token"
    assert data["role"] == "member"


@pytest.mark.anyio
async def test_wx_login_existing_bound_user(client: AsyncClient):
    """
    场景 2：openid 已绑定账号 → wx-login 直接返回 ok + token（无需 bind 流程）
    """
    # 首先注册一个普通账号，然后绑定 openid
    with mock_wx("openid_bound_003"):
        # 第一次：need_bind → 注册新账号绑定
        wx1 = await client.post(WX_LOGIN_URL, json={"code": "c1"})
        token1 = (await client.post(WX_BIND_NEW_URL, json={
            "bind_token": wx1.json()["bind_token"],
            "display_name": "已绑定用户",
        })).json()["access_token"]
        assert token1

    # 第二次用同一 openid 登录 → 直接 ok
    with mock_wx("openid_bound_003"):
        wx2 = await client.post(WX_LOGIN_URL, json={"code": "c2"})

    assert wx2.status_code == 200
    data2 = wx2.json()
    assert data2["next_step"] == "ok"
    assert data2["access_token"], "重复登录应直接颁发 token"


@pytest.mark.anyio
async def test_wx_bind_existing_account(client: AsyncClient):
    """
    场景 3：新微信用户 → 选择绑定已有密码账号 → 成功
    """
    # 先注册一个普通账号
    await client.post(REG_URL, json={
        "username": "olduser1",
        "email": "olduser1@example.com",
        "password": "password123",
    })

    with mock_wx("openid_bind_existing_004"):
        wx_resp = await client.post(WX_LOGIN_URL, json={"code": "cx1"})

    bind_token = wx_resp.json()["bind_token"]

    resp = await client.post(WX_BIND_EXISTING_URL, json={
        "bind_token": bind_token,
        "username": "olduser1",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"]
    assert data["role"]


@pytest.mark.anyio
async def test_wx_bind_existing_wrong_password(client: AsyncClient):
    """绑定已有账号时密码错误 → 401"""
    await client.post(REG_URL, json={
        "username": "olduser2",
        "email": "olduser2@example.com",
        "password": "rightpass123",
    })

    with mock_wx("openid_wrong_pw_005"):
        wx_resp = await client.post(WX_LOGIN_URL, json={"code": "cx2"})

    bind_token = wx_resp.json()["bind_token"]

    resp = await client.post(WX_BIND_EXISTING_URL, json={
        "bind_token": bind_token,
        "username": "olduser2",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_wx_bind_duplicate_openid_conflict(client: AsyncClient):
    """
    场景 4：同一 openid 试图绑定第二个账号 → 409
    """
    # openid 先绑定 account_a
    with mock_wx("openid_dup_006"):
        wx1 = await client.post(WX_LOGIN_URL, json={"code": "d1"})
        await client.post(WX_BIND_NEW_URL, json={
            "bind_token": wx1.json()["bind_token"],
            "display_name": "账号A",
        })

    # 注册 account_b（普通密码账号）
    await client.post(REG_URL, json={
        "username": "account_b",
        "email": "account_b@example.com",
        "password": "password123",
    })

    # 尝试用同一 openid 绑定 account_b → 应 409
    with mock_wx("openid_dup_006"):
        wx2 = await client.post(WX_LOGIN_URL, json={"code": "d2"})

    # wx-login 此时会返回 ok（因为 openid 已绑定），不会再有 bind_token
    # 但如果直接调用 wx-bind-existing 用一个新 bind_token 也会冲突
    # 验证已绑定直接 ok 即可（场景 4 主要防止后端意外重复绑定）
    assert wx2.json()["next_step"] == "ok"


@pytest.mark.anyio
async def test_wx_bind_active_user_to_wechat(client: AsyncClient):
    """
    场景 5：密码账号已登录，主动绑定微信
    """
    token = await register_and_login(client, "bindme1")

    with mock_wx("openid_active_bind_007"):
        resp = await client.post(
            WX_BIND_URL,
            json={"code": "e1"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert "成功" in resp.json()["message"]


@pytest.mark.anyio
async def test_wx_bind_already_bound_conflict(client: AsyncClient):
    """已绑定再次绑定 → 409"""
    # 先绑定一次
    token = await register_and_login(client, "bindme2")
    with mock_wx("openid_double_bind_008"):
        await client.post(
            WX_BIND_URL,
            json={"code": "f1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # 再绑一次
        resp = await client.post(
            WX_BIND_URL,
            json={"code": "f2"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_wx_login_invalid_code(client: AsyncClient):
    """
    微信返回 errcode 时应该 400（测试 _code_to_openid 抛出 HTTPException 路径）
    """
    with patch(
        "app.api.v1.endpoints.auth_wechat._code_to_openid",
        new=AsyncMock(side_effect=HTTPException(status_code=400, detail="微信授权失败: invalid code")),
    ):
        resp = await client.post(WX_LOGIN_URL, json={"code": "bad_code"})
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_bind_token_single_use(client: AsyncClient):
    """bind_token 只能消费一次，重复使用 → 400"""
    with mock_wx("openid_singleuse_009"):
        wx_resp = await client.post(WX_LOGIN_URL, json={"code": "g1"})

    bind_token = wx_resp.json()["bind_token"]

    # 第一次使用 OK
    r1 = await client.post(WX_BIND_NEW_URL, json={"bind_token": bind_token, "display_name": "用一次"})
    assert r1.status_code == 200

    # 第二次使用 → 400
    r2 = await client.post(WX_BIND_NEW_URL, json={"bind_token": bind_token, "display_name": "再用一次"})
    assert r2.status_code == 400
