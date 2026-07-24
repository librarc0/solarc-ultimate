"""
T003: test_user_team_context 集成测试骨架
US1 多队伍账号登录后上下文加载验证
"""
from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CONTEXT_URL = "/api/v1/auth/me/context"
CREATE_TEAM_URL = "/api/v1/team/create"


async def _register_and_login(client: AsyncClient, username: str, email: str, password: str = "password123") -> str:
    await client.post(REG_URL, json={"username": username, "email": email, "password": password})
    resp = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_new_user_gets_empty_team_context(client: AsyncClient):
    """新注册用户登录后 me/context 返回空 teams 列表（US1 验收场景-2）"""
    token = await _register_and_login(client, "utcusr1", "utc1@example.com")
    resp = await client.get(CONTEXT_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["teams"] == []
    assert data.get("active_player") is None


async def test_team_owner_sees_team_in_context(client: AsyncClient):
    """创建队伍后 me/context 的 teams 列表应包含该队伍"""
    token = await _register_and_login(client, "utcusr2", "utc2@example.com")
    # 创建队伍（创建者自动成为 owner + active）
    resp = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "ContextTestTeam"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    resp = await client.get(CONTEXT_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["teams"]) >= 1, f"创建队伍后 teams 应非空: {data}"
