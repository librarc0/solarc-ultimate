"""T048 [US6]: 双层资料更新合同测试

验证 PATCH /players/me/profile/dual 接口的响应结构与语义约束：
- 修改 user.username 全局生效且唯一性校验有效
- 修改 player.display_name 只影响当前队伍
- username 格式不合法时返回 400
- 重复 username 返回 400
"""
import pytest
from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CREATE_TEAM_URL = "/api/v1/team/create"
DUAL_PROFILE_URL = "/api/v1/players/me/profile/dual"
ME_URL = "/api/v1/auth/me"


async def _reg_login(client: AsyncClient, username: str, email: str, password: str = "password123") -> str:
    await client.post(REG_URL, json={"username": username, "email": email, "password": password})
    r = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert r.status_code == 200, f"登录失败 {username}: {r.text}"
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_dual_profile_update_username_response_schema(client: AsyncClient):
    """[合同] approve: 修改 user.username 响应符合 DualLayerProfileUpdateResponse 结构"""
    token = await _reg_login(client, "dupSchu1", "dupSchu1@e.com")
    r = await client.patch(
        DUAL_PROFILE_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"user": {"username": "dupSchnew1"}},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user_username"] == "dupSchnew1"
    assert "display_name" in data
    assert "show_in_rankings" in data


@pytest.mark.asyncio
async def test_dual_profile_update_display_name_only(client: AsyncClient):
    """[合同] 只修改 player.display_name，不影响 user_username"""
    token = await _reg_login(client, "dupSchu2", "dupSchu2@e.com")
    # 先加入队伍
    r = await client.post(CREATE_TEAM_URL,
                                 headers={"Authorization": f"Bearer {token}"},
                                 json={"team_name": "DupSchTeam2"})
    assert r.status_code == 201

    r = await client.patch(
        DUAL_PROFILE_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"player": {"display_name": "飞鹰小张"}},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user_username"] == "dupSchu2"  # 不变
    assert data["display_name"] == "飞鹰小张"


@pytest.mark.asyncio
async def test_dual_profile_update_invalid_username_format(client: AsyncClient):
    """[合同] username 含非法字符时返回 400"""
    token = await _reg_login(client, "dupSchu3", "dupSchu3@e.com")
    r = await client.patch(
        DUAL_PROFILE_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"user": {"username": "bad username!"}},
    )
    assert r.status_code == 400
    assert "用户名" in r.json()["detail"]


@pytest.mark.asyncio
async def test_dual_profile_update_duplicate_username(client: AsyncClient):
    """[合同] username 已被他人使用时返回 400"""
    await _reg_login(client, "duptakenu", "duptakenu@e.com")  # 占用此名
    token2 = await _reg_login(client, "dupotheru", "dupotheru@e.com")
    r = await client.patch(
        DUAL_PROFILE_URL,
        headers={"Authorization": f"Bearer {token2}"},
        json={"user": {"username": "duptakenu"}},  # 尝试使用已被占用的名
    )
    assert r.status_code == 400
    assert "已被使用" in r.json()["detail"]


@pytest.mark.asyncio
async def test_dual_profile_update_can_clear_email_with_null(client: AsyncClient):
    """[合同] 显式传 player.email = null 时应清空邮箱。"""
    token = await _reg_login(client, "dupSchu4", "dupSchu4@e.com")

    r = await client.patch(
        DUAL_PROFILE_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"player": {"email": None}},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"] is None

    me = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] is None
