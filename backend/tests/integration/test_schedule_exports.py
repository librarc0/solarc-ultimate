"""日程导出集成测试（CSV 导出 + 权限/异常分支）"""
from datetime import date

from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
EVENTS_URL = "/api/v1/schedule-events"
EXPORT_URL = "/api/v1/exports/schedule"


async def _register(client: AsyncClient, username: str) -> None:
    r = await client.post(REG_URL, json={"username": username, "email": f"{username}@t.com", "password": "pw123456"})
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, username: str) -> str:
    r = await client.post(LOGIN_URL, data={"username": username, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _setup_team(client: AsyncClient):
    await _register(client, "exportowner")
    owner_token = await _login(client, "exportowner")
    created = await client.post(
        "/api/v1/team/create",
        json={"team_name": "ExportTeam"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 201, created.text
    team_id = created.json()["team_id"]

    await _register(client, "exportmember")
    member_token = await _login(client, "exportmember")
    await client.post(
        "/api/v1/team/apply",
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {member_token}"},
    )

    pending = await client.get(
        "/api/v1/players?status=pending",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert pending.status_code == 200, pending.text
    player_id = next(p["id"] for p in pending.json() if p["username"] == "exportmember")
    approved = await client.patch(
        f"/api/v1/players/{player_id}/status",
        json={"status": "active"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert approved.status_code == 200, approved.text
    return owner_token, member_token


async def test_export_schedule_csv_happy_path(client: AsyncClient):
    owner_token, member_token = await _setup_team(client)
    today = date.today().isoformat()

    created = await client.post(
        EVENTS_URL,
        json={"title": "导出测试活动", "event_type": "training", "start_date": today, "end_date": today},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 201, created.text
    event_id = created.json()["id"]

    published = await client.post(
        f"{EVENTS_URL}/{event_id}/publish",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert published.status_code == 200, published.text

    submitted = await client.put(
        f"/api/v1/schedule-attendance/{event_id}/me",
        json={"status": "leave"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert submitted.status_code == 200, submitted.text

    exported = await client.get(
        EXPORT_URL,
        params={"start_date": today, "end_date": today},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers["content-type"]
    assert "==== 活动 1 ====" in exported.text
    assert "导出测试活动" in exported.text
    assert "球员名称" in exported.text
    assert "请假" in exported.text


async def test_export_schedule_requires_admin(client: AsyncClient):
    _, member_token = await _setup_team(client)
    today = date.today().isoformat()

    exported = await client.get(
        EXPORT_URL,
        params={"start_date": today, "end_date": today},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert exported.status_code == 403


async def test_export_schedule_rejects_invalid_dates(client: AsyncClient):
    owner_token, _ = await _setup_team(client)

    exported = await client.get(
        EXPORT_URL,
        params={"start_date": "2025/01/01", "end_date": "2025-01-31"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert exported.status_code == 400
