"""
T028: /auth/me/default-team 合同测试
验证默认队伍设置接口响应格式与成员资格校验行为
"""
from httpx import AsyncClient


REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
DEFAULT_TEAM_URL = "/api/v1/auth/me/default-team"
CREATE_TEAM_URL = "/api/v1/team/create"


async def _register_and_login(client: AsyncClient, username: str, email: str, password: str = "password123") -> str:
    await client.post(REG_URL, json={"username": username, "email": email, "password": password})
    resp = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    return resp.json()["access_token"]


async def test_set_default_team_response_envelope(client: AsyncClient):
    """set-default-team 成功响应必须使用统一格式 code/data/message"""
    token = await _register_and_login(client, "dtuser1", "dt1@example.com")
    # 先创建一支队伍
    resp = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "DefaultTeam1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"创建队伍失败: {resp.text}"
    team_id = resp.json().get("data", {}).get("team_id") or resp.json().get("team_id")
    # 设置为默认队伍
    resp = await client.post(
        DEFAULT_TEAM_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"设置默认队伍失败: {resp.text}"
    body = resp.json()
    assert "code" in body, f"缺少 code: {body}"
    assert "data" in body, f"缺少 data: {body}"
    assert "message" in body, f"缺少 message: {body}"
    assert body["code"] == 0
    assert body["data"]["default_team_id"] == team_id


async def test_set_default_team_non_member_gets_403(client: AsyncClient):
    """非队伍成员试图设置该队伍为默认队伍应收到 403"""
    token_a = await _register_and_login(client, "dtuser2a", "dt2a@example.com")
    token_b = await _register_and_login(client, "dtuser2b", "dt2b@example.com")
    # user_a 创建队伍
    resp = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "DefaultTeam2"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 201
    team_id = resp.json().get("data", {}).get("team_id") or resp.json().get("team_id")
    # user_b 试图将 user_a 的队伍设为自己的默认队伍
    resp = await client.post(
        DEFAULT_TEAM_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403, f"非成员应被拒绝: {resp.text}"


async def test_clear_default_team_with_null(client: AsyncClient):
    """team_id=null 应清除默认队伍并返回 default_team_id=None"""
    token = await _register_and_login(client, "dtuser3", "dt3@example.com")
    # 先创建并设置默认队伍
    resp = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "DefaultTeam3"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    team_id = resp.json().get("data", {}).get("team_id") or resp.json().get("team_id")
    await client.post(
        DEFAULT_TEAM_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    # 清除默认队伍
    resp = await client.post(
        DEFAULT_TEAM_URL,
        json={"team_id": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"清除默认队伍失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["default_team_id"] is None


async def test_set_default_team_requires_auth(client: AsyncClient):
    """未认证请求设置默认队伍应收到 401"""
    resp = await client.post(
        DEFAULT_TEAM_URL,
        json={"team_id": 1},
    )
    assert resp.status_code == 401, f"未认证应返回 401: {resp.text}"
