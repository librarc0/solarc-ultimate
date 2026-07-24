"""日程出勤 CRUD 集成测试"""
from datetime import date
from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
EVENTS_URL = "/api/v1/schedule-events"
ATT_URL = "/api/v1/schedule-attendance"


async def _register(client: AsyncClient, username: str) -> None:
    r = await client.post(REG_URL, json={"username": username, "email": f"{username}@t.com", "password": "pw123456"})
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, username: str) -> str:
    r = await client.post(LOGIN_URL, data={"username": username, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _setup_team(client: AsyncClient):
    await _register(client, "attowner")
    owner_token = await _login(client, "attowner")
    r = await client.post("/api/v1/team/create", json={"team_name": "AttTeam"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    team_id = r.json()["team_id"]

    await _register(client, "attmember")
    member_token = await _login(client, "attmember")
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {member_token}"})

    r_pend = await client.get("/api/v1/players?status=pending",
                              headers={"Authorization": f"Bearer {owner_token}"})
    pid = next(p["id"] for p in r_pend.json() if p["username"] == "attmember")
    await client.patch(f"/api/v1/players/{pid}/status", json={"status": "active"},
                       headers={"Authorization": f"Bearer {owner_token}"})

    return owner_token, member_token


async def _create_published_event(client: AsyncClient, owner_token: str) -> int:
    today = date.today().isoformat()
    r = await client.post(EVENTS_URL, json={"title": "出勤测试活动", "event_type": "game",
                                              "start_date": today, "end_date": today},
                          headers={"Authorization": f"Bearer {owner_token}"})
    ev_id = r.json()["id"]
    await client.post(f"{EVENTS_URL}/{ev_id}/publish",
                      headers={"Authorization": f"Bearer {owner_token}"})
    return ev_id


# ─── 认证 / 权限 ──────────────────────────────────────────────────────────────

async def test_submit_attendance_unauthenticated(client: AsyncClient):
    r = await client.put(f"{ATT_URL}/1/me", json={"status": "yes"})
    assert r.status_code == 401


async def test_attendance_summary_requires_admin(client: AsyncClient):
    _, member_token = await _setup_team(client)
    r = await client.get(f"{ATT_URL}/1/summary",
                         headers={"Authorization": f"Bearer {member_token}"})
    assert r.status_code == 403


async def test_member_cannot_submit_attendance_for_draft_event(client: AsyncClient):
    owner_token, member_token = await _setup_team(client)
    today = date.today().isoformat()
    created = await client.post(
        EVENTS_URL,
        json={"title": "草稿活动", "event_type": "training", "start_date": today, "end_date": today},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 201, created.text

    r = await client.put(
        f"{ATT_URL}/{created.json()['id']}/me",
        json={"status": "yes"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r.status_code == 404


# ─── 正常出勤流程 ──────────────────────────────────────────────────────────────

async def test_submit_attendance_happy_path(client: AsyncClient):
    owner_token, member_token = await _setup_team(client)
    ev_id = await _create_published_event(client, owner_token)

    r = await client.put(f"{ATT_URL}/{ev_id}/me", json={"status": "yes"},
                         headers={"Authorization": f"Bearer {member_token}"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "yes"


async def test_submit_attendance_idempotent(client: AsyncClient):
    """重复提交更新状态而非报错"""
    owner_token, member_token = await _setup_team(client)
    ev_id = await _create_published_event(client, owner_token)

    await client.put(f"{ATT_URL}/{ev_id}/me", json={"status": "yes"},
                     headers={"Authorization": f"Bearer {member_token}"})
    r = await client.put(f"{ATT_URL}/{ev_id}/me", json={"status": "leave"},
                         headers={"Authorization": f"Bearer {member_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "leave"


async def test_submit_removed_no_status_rejected(client: AsyncClient):
    owner_token, member_token = await _setup_team(client)
    ev_id = await _create_published_event(client, owner_token)

    r = await client.put(
        f"{ATT_URL}/{ev_id}/me",
        json={"status": "no"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r.status_code == 422


async def test_attendance_summary_shows_not_submitted(client: AsyncClient):
    """出勤汇总中 not_submitted 包含尚未填写的成员"""
    owner_token, member_token = await _setup_team(client)
    ev_id = await _create_published_event(client, owner_token)

    # member 提交，owner 不提交
    await client.put(f"{ATT_URL}/{ev_id}/me", json={"status": "yes"},
                     headers={"Authorization": f"Bearer {member_token}"})

    r = await client.get(f"{ATT_URL}/{ev_id}/summary",
                         headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 200, r.text
    summary = r.json()
    assert len(summary["yes"]) >= 1
    assert len(summary["not_submitted"]) >= 1  # owner 未提交


async def test_get_my_attendance(client: AsyncClient):
    owner_token, member_token = await _setup_team(client)
    ev_id = await _create_published_event(client, owner_token)

    await client.put(f"{ATT_URL}/{ev_id}/me", json={"status": "leave"},
                     headers={"Authorization": f"Bearer {member_token}"})

    r = await client.get(f"{ATT_URL}/{ev_id}/me",
                         headers={"Authorization": f"Bearer {member_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "leave"
