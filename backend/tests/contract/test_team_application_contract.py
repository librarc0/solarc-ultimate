"""
T070: /team-membership/applications 合同测试
验证多队申请入队接口响应格式与冲突检测行为
"""
from httpx import AsyncClient


REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
APPLICATIONS_URL = "/api/v1/team-membership/applications"
CREATE_TEAM_URL = "/api/v1/team/create"


async def _register_and_login(client: AsyncClient, username: str, email: str, password: str = "password123") -> str:
    await client.post(REG_URL, json={"username": username, "email": email, "password": password})
    resp = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    return resp.json()["access_token"]


async def test_applications_response_envelope(client: AsyncClient):
    """apply-membership 成功响应必须使用统一格式 code/data/message"""
    token_owner = await _register_and_login(client, "tmowner1", "tmowner1@example.com")
    token_applicant = await _register_and_login(client, "tmapply1", "tmapply1@example.com")

    # owner 创建队伍
    r = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "AppTeam1"},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert r.status_code == 201, f"创建队伍失败: {r.text}"
    team_id = r.json().get("data", {}).get("team_id") or r.json().get("team_id")

    # applicant 申请加入
    resp = await client.post(
        APPLICATIONS_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token_applicant}"},
    )
    assert resp.status_code == 200, f"申请入队失败: {resp.text}"
    body = resp.json()
    assert "code" in body, f"缺少 code: {body}"
    assert "data" in body, f"缺少 data: {body}"
    assert "message" in body, f"缺少 message: {body}"
    assert body["code"] == 0
    assert body["data"]["team_id"] == team_id
    assert body["data"]["status"] == "pending"


async def test_applications_duplicate_returns_409(client: AsyncClient):
    """同一用户对同一队伍重复申请应返回 409"""
    token_owner = await _register_and_login(client, "tmowner2", "tmowner2@example.com")
    token_applicant = await _register_and_login(client, "tmapply2", "tmapply2@example.com")

    r = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "AppTeam2"},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert r.status_code == 201
    team_id = r.json().get("data", {}).get("team_id") or r.json().get("team_id")

    # 第一次申请
    resp1 = await client.post(
        APPLICATIONS_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token_applicant}"},
    )
    assert resp1.status_code == 200

    # 重复申请应被拒绝
    resp2 = await client.post(
        APPLICATIONS_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token_applicant}"},
    )
    assert resp2.status_code == 409, f"重复申请应返回 409: {resp2.text}"


async def test_applications_nonexistent_team_returns_404(client: AsyncClient):
    """申请不存在队伍应返回 404"""
    token = await _register_and_login(client, "tmapply3", "tmapply3@example.com")
    resp = await client.post(
        APPLICATIONS_URL,
        json={"team_id": 99999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404, f"不存在队伍应返回 404: {resp.text}"


async def test_applications_requires_auth(client: AsyncClient):
    """未认证请求应返回 401"""
    resp = await client.post(APPLICATIONS_URL, json={"team_id": 1})
    assert resp.status_code == 401, f"未认证应返回 401: {resp.text}"
