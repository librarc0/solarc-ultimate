"""T0xx: 超级管理员在未选择 viewing team 时的首页请求链路应无报错"""
from httpx import AsyncClient


REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


async def _register(client: AsyncClient, username: str, password: str = "pw123456", email: str | None = None):
    e = email or f"{username}@test.com"
    r = await client.post(REG_URL, json={"username": username, "email": e, "password": password})
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, username: str, password: str = "pw123456") -> str:
    r = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_superadmin_home_requests_without_viewing_team(client: AsyncClient, db_session):
    """
    前端 HomeView（超管未选队伍）会发起一串请求。
    期望：这些请求都应返回 200（或空数据），不应出现 4xx/5xx “大量报错”。
    """
    from sqlalchemy import select as sa_select
    from app.models.player import Player

    # 先创建一个普通队伍（让 /team/available 有数据更贴近真实）
    await _register(client, "ownerx1")
    owner_token = await _login(client, "ownerx1")
    r = await client.post("/api/v1/team/create", json={"team_name": "Eagles"}, headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201, r.text

    # 创建超管账号并标记 is_superadmin=True
    await _register(client, "superx1", email="superx1@test.com")
    sa_token = await _login(client, "superx1")
    result = await db_session.execute(sa_select(Player).where(Player.username == "superx1"))
    sa_player = result.scalar_one()
    sa_player.is_superadmin = True
    await db_session.commit()

    headers = {"Authorization": f"Bearer {sa_token}"}

    # 模拟 HomeView.loadData() 的请求组合（未传 team_id）
    r1 = await client.get("/api/v1/players/me", headers=headers)
    assert r1.status_code == 200, r1.text

    r2 = await client.get("/api/v1/team/my", headers=headers)
    assert r2.status_code == 200, r2.text
    # 未选队伍时允许为 None
    assert r2.json() is None

    r3 = await client.get("/api/v1/players/me/rating_history", headers=headers)
    assert r3.status_code == 200, r3.text

    r4 = await client.get("/api/v1/players/me/match_stats", headers=headers)
    assert r4.status_code == 200, r4.text

    r5 = await client.get("/api/v1/players?page_size=100", headers=headers)
    assert r5.status_code == 200, r5.text
    assert r5.json() == []

    # 留言板 + 通知（HomeView.onMounted 会调用）
    r6 = await client.get("/api/v1/team/posts?page_size=10", headers=headers)
    assert r6.status_code == 200, r6.text

    r7 = await client.get("/api/v1/team/notifications/count", headers=headers)
    assert r7.status_code == 200, r7.text

    r8 = await client.get("/api/v1/team/notifications", headers=headers)
    assert r8.status_code == 200, r8.text

