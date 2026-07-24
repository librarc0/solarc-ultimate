"""
T021: /auth/switch-team 合同测试
验证切队接口响应格式与可访问性校验行为
"""
from httpx import AsyncClient


REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
SWITCH_URL = "/api/v1/auth/switch-team"
CREATE_TEAM_URL = "/api/v1/team/create"
CONTEXT_URL = "/api/v1/auth/me/context"


async def _register_and_login(client: AsyncClient, username: str, email: str, password: str = "password123") -> str:
    await client.post(REG_URL, json={"username": username, "email": email, "password": password})
    resp = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    return resp.json()["access_token"]


async def test_switch_team_response_envelope(client: AsyncClient):
    """switch-team 成功响应必须使用统一格式 code/data/message"""
    token = await _register_and_login(client, "swuser1", "sw1@example.com")
    # 先创建一支队伍
    resp = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "SwitchTeam1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"创建队伍失败: {resp.text}"
    team_id = resp.json()["data"]["team_id"] if "data" in resp.json() else resp.json().get("team_id")
    # 切换到该队伍
    resp = await client.post(
        SWITCH_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"switch-team 失败: {resp.text}"
    body = resp.json()
    assert "code" in body, f"缺少 code: {body}"
    assert "data" in body, f"缺少 data: {body}"
    assert "message" in body, f"缺少 message: {body}"
    assert body["code"] == 0


async def test_switch_team_returns_new_token(client: AsyncClient):
    """switch-team 成功后 data 包含新 access_token"""
    token = await _register_and_login(client, "swuser2", "sw2@example.com")
    resp = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "SwitchTeam2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    team_id = resp.json().get("data", {}).get("team_id") or resp.json().get("team_id")
    resp = await client.post(
        SWITCH_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data, f"data 应包含 access_token: {data}"


async def test_switch_team_inaccessible_fails(client: AsyncClient):
    """切换到无访问权限的队伍应返回 403"""
    token = await _register_and_login(client, "swuser3", "sw3@example.com")
    resp = await client.post(
        SWITCH_URL,
        json={"team_id": 99999},  # 不存在的队伍
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (403, 404), f"非成员切到陌生队伍应被拒绝: {resp.text}"
