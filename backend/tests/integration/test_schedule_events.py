"""日程事件 CRUD 集成测试"""
from datetime import date, timedelta
from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
EVENTS_URL = "/api/v1/schedule-events"


async def _register(client: AsyncClient, username: str) -> None:
    r = await client.post(REG_URL, json={"username": username, "email": f"{username}@t.com", "password": "pw123456"})
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, username: str) -> str:
    r = await client.post(LOGIN_URL, data={"username": username, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _setup_team(client: AsyncClient):
    await _register(client, "schedowner")
    owner_token = await _login(client, "schedowner")
    r = await client.post("/api/v1/team/create", json={"team_name": "TestTeam"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201, r.text
    team_id = r.json()["team_id"]

    await _register(client, "schedmember")
    member_token = await _login(client, "schedmember")
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {member_token}"})

    r_pending = await client.get("/api/v1/players?status=pending",
                                 headers={"Authorization": f"Bearer {owner_token}"})
    pid = next(p["id"] for p in r_pending.json() if p["username"] == "schedmember")
    await client.patch(f"/api/v1/players/{pid}/status", json={"status": "active"},
                       headers={"Authorization": f"Bearer {owner_token}"})

    return owner_token, member_token


def _event_body(offset: int = 0):
    today = date.today() + timedelta(days=offset)
    return {
        "title": f"测试活动 {offset}",
        "event_type": "game",
        "start_date": today.isoformat(),
        "end_date": today.isoformat(),
    }


# ─── 认证 / 权限 ──────────────────────────────────────────────────────────────

async def test_create_event_unauthenticated(client: AsyncClient):
    r = await client.post(EVENTS_URL, json=_event_body())
    assert r.status_code == 401


async def test_create_event_requires_admin(client: AsyncClient):
    _, member_token = await _setup_team(client)
    r = await client.post(EVENTS_URL, json=_event_body(),
                          headers={"Authorization": f"Bearer {member_token}"})
    assert r.status_code == 403


# ─── 创建 / 读取 ──────────────────────────────────────────────────────────────

async def test_create_event_happy_path(client: AsyncClient):
    owner_token, _ = await _setup_team(client)
    body = _event_body(1)
    r = await client.post(EVENTS_URL, json=body,
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == body["title"]
    assert data["status"] == "draft"
    assert data["event_type"] == "game"


async def test_publish_event(client: AsyncClient):
    owner_token, _ = await _setup_team(client)
    r = await client.post(EVENTS_URL, json=_event_body(2),
                          headers={"Authorization": f"Bearer {owner_token}"})
    ev_id = r.json()["id"]

    pub = await client.post(f"{EVENTS_URL}/{ev_id}/publish",
                             headers={"Authorization": f"Bearer {owner_token}"})
    assert pub.status_code == 200, pub.text
    assert pub.json()["status"] == "published"


async def test_remind_draft_event_rejected(client: AsyncClient):
    owner_token, _ = await _setup_team(client)
    created = await client.post(
        EVENTS_URL,
        json=_event_body(2),
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 201, created.text

    remind = await client.post(
        f"{EVENTS_URL}/{created.json()['id']}/remind",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert remind.status_code == 400


async def test_list_events_date_filter(client: AsyncClient):
    owner_token, _ = await _setup_team(client)
    today = date.today()
    # 创建两个不同日期的活动
    for offset in [0, 30]:
        await client.post(EVENTS_URL, json=_event_body(offset),
                          headers={"Authorization": f"Bearer {owner_token}"})

    r = await client.get(EVENTS_URL,
                         params={"start_date": today.isoformat(), "end_date": today.isoformat()},
                         headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 200, r.text
    events = r.json()
    assert all(
        e["start_date"] <= today.isoformat() <= e["end_date"]
        for e in events
    )


async def test_draft_hidden_from_members(client: AsyncClient):
    owner_token, member_token = await _setup_team(client)
    r = await client.post(EVENTS_URL, json=_event_body(3),
                          headers={"Authorization": f"Bearer {owner_token}"})
    ev_id = r.json()["id"]

    # 非管理员无法查看草稿
    r_member = await client.get(f"{EVENTS_URL}/{ev_id}",
                                headers={"Authorization": f"Bearer {member_token}"})
    assert r_member.status_code == 404


async def test_delete_event(client: AsyncClient):
    owner_token, _ = await _setup_team(client)
    r = await client.post(EVENTS_URL, json=_event_body(4),
                          headers={"Authorization": f"Bearer {owner_token}"})
    ev_id = r.json()["id"]
    del_r = await client.delete(f"{EVENTS_URL}/{ev_id}",
                                headers={"Authorization": f"Bearer {owner_token}"})
    assert del_r.status_code == 204

    get_r = await client.get(f"{EVENTS_URL}/{ev_id}",
                             headers={"Authorization": f"Bearer {owner_token}"})
    assert get_r.status_code == 404


async def test_list_events_includes_attendance_breakdown(client: AsyncClient):
    owner_token, member_token = await _setup_team(client)
    body = _event_body(5)
    created = await client.post(EVENTS_URL, json=body, headers={"Authorization": f"Bearer {owner_token}"})
    assert created.status_code == 201, created.text
    ev_id = created.json()["id"]

    published = await client.post(f"{EVENTS_URL}/{ev_id}/publish", headers={"Authorization": f"Bearer {owner_token}"})
    assert published.status_code == 200, published.text

    yes_r = await client.put(
        f"/api/v1/schedule-attendance/{ev_id}/me",
        json={"status": "yes"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert yes_r.status_code == 200, yes_r.text

    sdl_r = await client.put(
        f"/api/v1/schedule-attendance/{ev_id}/me",
        json={"status": "sdl"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert sdl_r.status_code == 200, sdl_r.text

    listed = await client.get(
        EVENTS_URL,
        params={"start_date": body["start_date"], "end_date": body["end_date"]},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert listed.status_code == 200, listed.text
    item = next(e for e in listed.json() if e["id"] == ev_id)
    assert item["attendance_count"] == 2
    assert item["yes_count"] == 1
    assert item["sdl_count"] == 1
    assert item["not_submitted_count"] == 0


async def test_remind_ended_event_rejected(client: AsyncClient):
    owner_token, _ = await _setup_team(client)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    created = await client.post(
        EVENTS_URL,
        json={"title": "已结束活动", "event_type": "training", "start_date": yesterday, "end_date": yesterday},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 201, created.text
    event_id = created.json()["id"]
    await client.post(f"{EVENTS_URL}/{event_id}/publish", headers={"Authorization": f"Bearer {owner_token}"})

    remind = await client.post(f"{EVENTS_URL}/{event_id}/remind", headers={"Authorization": f"Bearer {owner_token}"})
    assert remind.status_code == 400


async def test_bulk_remind_only_shows_in_notifications(client: AsyncClient):
    owner_token, member_token = await _setup_team(client)
    first = _event_body(6)
    second = _event_body(7)

    first_r = await client.post(EVENTS_URL, json=first, headers={"Authorization": f"Bearer {owner_token}"})
    second_r = await client.post(EVENTS_URL, json=second, headers={"Authorization": f"Bearer {owner_token}"})
    assert first_r.status_code == 201, first_r.text
    assert second_r.status_code == 201, second_r.text

    first_id = first_r.json()["id"]
    second_id = second_r.json()["id"]
    await client.post(f"{EVENTS_URL}/{first_id}/publish", headers={"Authorization": f"Bearer {owner_token}"})
    await client.post(f"{EVENTS_URL}/{second_id}/publish", headers={"Authorization": f"Bearer {owner_token}"})

    remind_r = await client.post(f"{EVENTS_URL}/remind/pending", headers={"Authorization": f"Bearer {owner_token}"})
    assert remind_r.status_code == 200, remind_r.text
    remind_data = remind_r.json()
    assert remind_data["events"] == 2
    assert remind_data["reminded"] >= 1

    posts_r = await client.get("/api/v1/team/posts?page_size=20", headers={"Authorization": f"Bearer {member_token}"})
    assert posts_r.status_code == 200, posts_r.text
    assert all("出勤提醒" not in (post.get("content") or "") for post in posts_r.json())

    notif_r = await client.get("/api/v1/team/notifications", headers={"Authorization": f"Bearer {member_token}"})
    assert notif_r.status_code == 200, notif_r.text
    schedule_items = [item for item in notif_r.json()["items"] if item.get("type") == "schedule"]
    assert len(schedule_items) == 1
    assert first["title"] in schedule_items[0]["body"]
    assert second["title"] in schedule_items[0]["body"]
