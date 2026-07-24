"""
T014/T068: /auth/me/context 合同测试
验证响应必须使用统一格式 { "code": 0, "data": {...}, "message": "" }
以及字段完整性（user 身份 + teams 列表 + active_player 上下文）
"""
from httpx import AsyncClient


REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CONTEXT_URL = "/api/v1/auth/me/context"


# ──────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────────────────────────────────


async def _register_and_login(client: AsyncClient, username: str, email: str, password: str) -> str:
    """注册并登录，返回 access_token"""
    await client.post(REG_URL, json={
        "username": username,
        "email": email,
        "password": password,
    })
    resp = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    return resp.json()["access_token"]


# ──────────────────────────────────────────────────────────────────────────────
# T068: 统一响应格式 (code/data/message)
# ──────────────────────────────────────────────────────────────────────────────


async def test_context_response_envelope_format(client: AsyncClient):
    """me/context 响应必须包含 code/data/message 字段（章程 API 约束）"""
    token = await _register_and_login(client, "ctxuser1", "ctx1@example.com", "password123")
    resp = await client.get(CONTEXT_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    # 验证三字段均存在
    assert "code" in body, f"响应缺少 code 字段: {body}"
    assert "data" in body, f"响应缺少 data 字段: {body}"
    assert "message" in body, f"响应缺少 message 字段: {body}"
    assert body["code"] == 0, f"成功响应 code 应为 0: {body}"


async def test_context_unauthenticated_returns_401(client: AsyncClient):
    """未携带 token 请求 me/context 应返回 401"""
    resp = await client.get(CONTEXT_URL)
    assert resp.status_code == 401


async def test_context_response_data_structure(client: AsyncClient):
    """me/context data 字段必须包含 user_id / teams / active_player"""
    token = await _register_and_login(client, "ctxuser2", "ctx2@example.com", "password123")
    resp = await client.get(CONTEXT_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "user_id" in data, f"data 缺少 user_id: {data}"
    assert "username" in data, f"data 缺少 username: {data}"
    assert "teams" in data, f"data 缺少 teams 列表: {data}"
    # 无队伍用户 teams 应为空列表
    assert isinstance(data["teams"], list)


async def test_context_no_teams_for_new_user(client: AsyncClient):
    """新注册用户 me/context 返回空 teams 列表"""
    token = await _register_and_login(client, "ctxuser3", "ctx3@example.com", "password123")
    resp = await client.get(CONTEXT_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["teams"] == [], f"新用户 teams 应为空: {data}"
    # active_player 为 None（无队伍）
    assert data.get("active_player") is None, f"无队伍时 active_player 应为 None: {data}"
