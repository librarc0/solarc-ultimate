"""T075: team posts 公告板集成测试"""
from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
POSTS_URL = "/api/v1/team/posts"


async def _login(client: AsyncClient, username: str, password: str = "pw123456") -> str:
    resp = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _setup(client: AsyncClient):
    """创建 owner 和成员，返回 (admin_token, member_token)"""
    r1 = await client.post(REG_URL, json={"username": "adminuser", "email": "adminuser@test.com", "password": "pw123456"})
    assert r1.status_code == 201, f"admin reg failed: {r1.text}"
    admin_token = await _login(client, "adminuser")
    r_team = await client.post("/api/v1/team/create", json={"team_name": "Eagles"},
                               headers={"Authorization": f"Bearer {admin_token}"})
    assert r_team.status_code == 201, r_team.text
    team_id = r_team.json()["team_id"]

    await client.post(REG_URL, json={"username": "member001", "email": "member001@test.com", "password": "pw123456"})
    member_pre_token = await _login(client, "member001")
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {member_pre_token}"})
    # admin 审批 member001
    players_resp = await client.get("/api/v1/players?status=pending", headers={"Authorization": f"Bearer {admin_token}"})
    member_id = next(p["id"] for p in players_resp.json() if p["username"] == "member001")
    await client.patch(f"/api/v1/players/{member_id}/status", json={"status": "active"}, headers={"Authorization": f"Bearer {admin_token}"})

    member_token = await _login(client, "member001")
    return admin_token, member_token


async def test_get_posts_requires_auth(client: AsyncClient):
    """未登录访问 GET /team/posts → 401"""
    resp = await client.get(POSTS_URL)
    assert resp.status_code == 401


async def test_member_can_post_and_others_see_it(client: AsyncClient):
    """发帖后其他用户可见"""
    admin_token, member_token = await _setup(client)

    # member 发帖
    post_resp = await client.post(
        POSTS_URL,
        json={"content": "Hello from member!"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert post_resp.status_code == 201
    post_id = post_resp.json()["id"]

    # admin 也能看到
    list_resp = await client.get(POSTS_URL, headers={"Authorization": f"Bearer {admin_token}"})
    assert list_resp.status_code == 200
    ids = [p["id"] for p in list_resp.json()]
    assert post_id in ids


async def test_author_can_soft_delete_own_post(client: AsyncClient):
    """发帖人可以软删除自己的帖子"""
    admin_token, member_token = await _setup(client)

    post_resp = await client.post(
        POSTS_URL,
        json={"content": "Delete me"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    post_id = post_resp.json()["id"]

    # member 删除自己的帖子
    del_resp = await client.delete(
        f"{POSTS_URL}/{post_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert del_resp.status_code == 204

    # 删除后列表中不可见
    list_resp = await client.get(POSTS_URL, headers={"Authorization": f"Bearer {admin_token}"})
    ids = [p["id"] for p in list_resp.json()]
    assert post_id not in ids


async def test_admin_can_delete_others_post(client: AsyncClient):
    """admin 可以软删除他人帖子"""
    admin_token, member_token = await _setup(client)

    post_resp = await client.post(
        POSTS_URL,
        json={"content": "Admin will delete this"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    post_id = post_resp.json()["id"]

    del_resp = await client.delete(
        f"{POSTS_URL}/{post_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_resp.status_code == 204


async def test_member_cannot_delete_others_post(client: AsyncClient):
    """非发帖人且非 admin 不能删除他人帖子"""
    admin_token, member_token = await _setup(client)

    # admin 发一帖
    post_resp = await client.post(
        POSTS_URL,
        json={"content": "Admin's post"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    post_id = post_resp.json()["id"]

    # member 尝试删除 → 403
    del_resp = await client.delete(
        f"{POSTS_URL}/{post_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert del_resp.status_code == 403
