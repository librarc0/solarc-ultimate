"""T027: /players 端点集成测试"""
from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PLAYERS_URL = "/api/v1/players"
CREATE_TEAM_URL = "/api/v1/team/create"
APPLY_TEAM_URL = "/api/v1/team/apply"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


async def _register(client: AsyncClient, username: str, password: str = "password123", email: str | None = None) -> None:
    e = email or f"{username}@test.com"
    resp = await client.post(REG_URL, json={"username": username, "email": e, "password": password})
    assert resp.status_code == 201, resp.text


async def _get_token(client: AsyncClient, username: str, password: str = "password123") -> str:
    resp = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _setup_owner(client: AsyncClient, username: str = "owneruser") -> tuple[str, int]:
    """注册、创建队伍成为 owner，返回 (token, team_id)"""
    await _register(client, username)
    token = await _get_token(client, username)
    r = await client.post(CREATE_TEAM_URL, json={"team_name": "Eagles"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    return token, r.json()["team_id"]


async def _make_pending(client: AsyncClient, username: str, team_id: int, password: str = "password123") -> str:
    """注册 → 登录 → 申请加入队伍（status=pending），返回 token"""
    await _register(client, username, password)
    token = await _get_token(client, username, password)
    r = await client.post(APPLY_TEAM_URL, json={"team_id": team_id}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return token


# ---------------------------------------------------------------------------
# GET /players
# ---------------------------------------------------------------------------


async def test_list_players_requires_auth(client: AsyncClient):
    """未登录访问列表 → 401"""
    resp = await client.get(PLAYERS_URL)
    assert resp.status_code == 401


async def test_list_players_returns_active_members(client: AsyncClient):
    """列表包含 active 成员"""
    token, _ = await _setup_owner(client)
    resp = await client.get(PLAYERS_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["username"] == "owneruser"
    assert data[0]["status"] == "active"


async def test_list_players_filter_by_status(client: AsyncClient):
    """按 status=pending 筛选"""
    owner_token, team_id = await _setup_owner(client)
    await _make_pending(client, "pendinguser", team_id)

    resp = await client.get(
        f"{PLAYERS_URL}?status=pending",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["username"] == "pendinguser"


# ---------------------------------------------------------------------------
# GET /players/me
# ---------------------------------------------------------------------------


async def test_get_me_returns_current_player(client: AsyncClient):
    """GET /players/me 返回当前用户"""
    token, _ = await _setup_owner(client)
    resp = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "owneruser"


# ---------------------------------------------------------------------------
# GET /players/{id}
# ---------------------------------------------------------------------------


async def test_get_player_by_id_owner_can_view_any(client: AsyncClient):
    """owner 可以查看任意成员"""
    owner_token, team_id = await _setup_owner(client)
    await _make_pending(client, "member1", team_id)

    # 获取 member1 的 id
    list_resp = await client.get(
        f"{PLAYERS_URL}?status=pending",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    member_id = list_resp.json()[0]["id"]

    resp = await client.get(
        f"{PLAYERS_URL}/{member_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200


async def test_get_nonexistent_player_returns_404(client: AsyncClient):
    """查询不存在的 id → 404"""
    token, _ = await _setup_owner(client)
    resp = await client.get(f"{PLAYERS_URL}/9999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /players/{id}/status
# ---------------------------------------------------------------------------


async def test_admin_can_approve_pending_player(client: AsyncClient):
    """管理员可以审批 pending 用户"""
    owner_token, team_id = await _setup_owner(client)
    await _make_pending(client, "pendinguser2", team_id)

    list_resp = await client.get(
        f"{PLAYERS_URL}?status=pending",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    member_id = list_resp.json()[0]["id"]

    resp = await client.patch(
        f"{PLAYERS_URL}/{member_id}/status",
        json={"status": "active"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


async def test_non_admin_cannot_change_status(client: AsyncClient):
    """普通成员不能修改他人状态"""
    owner_token, team_id = await _setup_owner(client, "ownerA")
    memberB_token = await _make_pending(client, "memberB", team_id)

    # owner 审批 memberB → active
    list_resp = await client.get(
        f"{PLAYERS_URL}?status=pending",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    member_id = list_resp.json()[0]["id"]
    await client.patch(
        f"{PLAYERS_URL}/{member_id}/status",
        json={"status": "active"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    # memberC 申请加入队伍 → pending
    await _make_pending(client, "memberC", team_id)
    list_resp2 = await client.get(
        f"{PLAYERS_URL}?status=pending",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    member_c_id = list_resp2.json()[0]["id"]

    # memberB（普通成员）尝试审批他人 → 403
    resp = await client.patch(
        f"{PLAYERS_URL}/{member_c_id}/status",
        json={"status": "active"},
        headers={"Authorization": f"Bearer {memberB_token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /players/{id}/role
# ---------------------------------------------------------------------------


async def test_owner_can_promote_to_admin(client: AsyncClient):
    """主理人可以将成员提升为 admin"""
    owner_token, team_id = await _setup_owner(client)
    await _make_pending(client, "futureAdmin", team_id)

    # 先审批
    list_resp = await client.get(
        f"{PLAYERS_URL}?status=pending",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    member_id = list_resp.json()[0]["id"]
    await client.patch(
        f"{PLAYERS_URL}/{member_id}/status",
        json={"status": "active"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    # 提升角色
    resp = await client.patch(
        f"{PLAYERS_URL}/{member_id}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


async def test_cannot_promote_to_owner(client: AsyncClient):
    """不能将他人设为 owner → 400"""
    owner_token, team_id = await _setup_owner(client)
    await _make_pending(client, "cantBeOwner", team_id)

    list_resp = await client.get(
        f"{PLAYERS_URL}?status=pending",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    member_id = list_resp.json()[0]["id"]

    resp = await client.patch(
        f"{PLAYERS_URL}/{member_id}/role",
        json={"role": "owner"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 400
