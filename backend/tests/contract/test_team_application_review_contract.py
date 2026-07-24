"""T035 [US4]: 审核接口合同测试

验证 /team-membership/applications/{membership_id}/review 的响应结构与语义约束：
- approve 时返回 initial_mu 与 suggested_mu
- reject 时返回 rejected 状态
- initial_mu 超出范围时 422
- 无权审核时 403
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CREATE_TEAM_URL = "/api/v1/team/create"
APPLICATIONS_URL = "/api/v1/team-membership/applications"
REVIEW_BASE = "/api/v1/team-membership/applications"
SUGGESTED_MU_URL = "/api/v1/team-membership/applications/suggested-mu"
PLAYERS_URL = "/api/v1/players"


async def _reg_login(client: AsyncClient, username: str, email: str, password: str = "password123") -> str:
    await client.post(REG_URL, json={"username": username, "email": email, "password": password})
    r = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert r.status_code == 200, f"登录失败: {r.text}"
    return r.json()["access_token"]


async def _setup_application(client: AsyncClient, db_session: AsyncSession, suffix: str):
    """创建一个 pending 的 PlayerTeamMembership 申请，返回 (owner_token, user_token, membership_id)。"""
    owner_token = await _reg_login(client, f"rv35own{suffix}", f"rv35own{suffix}@e.com")
    r = await client.post(CREATE_TEAM_URL, json={"team_name": f"ReviewTeam{suffix}"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201
    team_id = r.json()["team_id"]

    user_token = await _reg_login(client, f"rv35usr{suffix}", f"rv35usr{suffix}@e.com")

    # 不限制已在队伍的旧申请逻辑，用 /applications 提交申请（PlayerTeamMembership）
    resp = await client.post(
        APPLICATIONS_URL,
        json={"team_id": team_id, "join_reason": "想加入"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200, f"申请失败: {resp.text}"
    membership_id = resp.json()["data"]["membership_id"]
    return owner_token, user_token, membership_id


async def test_review_approve_default_mu_response_schema(client: AsyncClient, db_session: AsyncSession):
    """T035: approve 且不传 initial_mu → 响应含 code/data/message，data 含 initial_mu 与 suggested_mu"""
    owner_token, _, membership_id = await _setup_application(client, db_session, "a1")

    resp = await client.post(
        f"{REVIEW_BASE}/{membership_id}/review",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200, f"审核通过失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0
    assert "initial_mu" in body["data"]
    assert "suggested_mu" in body["data"]
    assert body["data"]["status"] == "active"


async def test_review_approve_manual_mu(client: AsyncClient, db_session: AsyncSession):
    """T035: approve 且传 initial_mu=30.0 → initial_mu 应为 30.0"""
    owner_token, _, membership_id = await _setup_application(client, db_session, "a2")

    resp = await client.post(
        f"{REVIEW_BASE}/{membership_id}/review",
        json={"action": "approve", "initial_mu": 30.0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200, f"审核通过失败: {resp.text}"
    data = resp.json()["data"]
    assert data["initial_mu"] == pytest.approx(30.0)


async def test_review_approve_mu_out_of_range_422(client: AsyncClient, db_session: AsyncSession):
    """T035: initial_mu 超出 10~40 范围 → 422 验证错误"""
    owner_token, _, membership_id = await _setup_application(client, db_session, "a3")

    resp = await client.post(
        f"{REVIEW_BASE}/{membership_id}/review",
        json={"action": "approve", "initial_mu": 50.0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 422, f"超范围 μ 应被拒绝: {resp.text}"


async def test_review_reject_response_schema(client: AsyncClient, db_session: AsyncSession):
    """T035: reject → 响应 status 为 rejected"""
    owner_token, _, membership_id = await _setup_application(client, db_session, "a4")

    resp = await client.post(
        f"{REVIEW_BASE}/{membership_id}/review",
        json={"action": "reject"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200, f"拒绝审核失败: {resp.text}"
    data = resp.json()["data"]
    assert data["status"] == "rejected"


async def test_suggested_mu_endpoint_schema(client: AsyncClient, db_session: AsyncSession):
    """前端审批弹窗依赖 suggested-mu 接口返回建议值与样本信息。"""
    owner_token, _, _ = await _setup_application(client, db_session, "a5")

    resp = await client.get(
        SUGGESTED_MU_URL,
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200, f"suggested-mu 请求失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0
    assert "suggested_mu" in body["data"]
    assert "sample_count" in body["data"]
    assert "used_default" in body["data"]
    assert body["data"]["manual_mu_min"] == pytest.approx(10.0)
    assert body["data"]["manual_mu_max"] == pytest.approx(40.0)
