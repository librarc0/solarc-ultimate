from httpx import AsyncClient


REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


async def _register(
    client: AsyncClient,
    username: str,
    password: str = "pw123456",
    email: str | None = None,
):
    user_email = email or f"{username}@test.com"
    response = await client.post(
        REG_URL,
        json={"username": username, "email": user_email, "password": password},
    )
    assert response.status_code == 201, response.text


async def _login(client: AsyncClient, username: str, password: str = "pw123456") -> str:
    response = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def test_superadmin_audit_logs_cover_team_player_and_match_changes(client: AsyncClient, db_session):
    from sqlalchemy import select as sa_select

    from app.models.player import Player

    await _register(client, "auditowner")
    owner_token = await _login(client, "auditowner")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    create_team_resp = await client.post(
        "/api/v1/team/create",
        json={"team_name": "Audit Eagles"},
        headers=owner_headers,
    )
    assert create_team_resp.status_code == 201, create_team_resp.text
    team_id = create_team_resp.json()["team_id"]

    owner_result = await db_session.execute(sa_select(Player).where(Player.username == "auditowner"))
    owner = owner_result.scalar_one()

    update_team_resp = await client.put(
        "/api/v1/team/info",
        json={"team_name": "Audit Eagles Pro"},
        headers=owner_headers,
    )
    assert update_team_resp.status_code == 200, update_team_resp.text

    update_profile_resp = await client.put(
        "/api/v1/players/me/profile",
        json={"display_name": "审计队长", "gender": "M", "jersey_number": 9},
        headers=owner_headers,
    )
    assert update_profile_resp.status_code == 200, update_profile_resp.text

    create_player_resp = await client.post(
        "/api/v1/players/admin-create",
        json={
            "username": "auditplayer1",
            "display_name": "队员一号",
            "email": "auditplayer1@test.com",
            "password": "pw123456",
            "gender": "F",
            "jersey_number": 18,
        },
        headers=owner_headers,
    )
    assert create_player_resp.status_code == 201, create_player_resp.text
    created_player_id = create_player_resp.json()["id"]

    create_match_resp = await client.post(
        "/api/v1/matches",
        json={
            "match_date": "2026-03-20",
            "match_type": "internal",
            "score_us": 5,
            "score_them": 3,
            "data_level": 1,
            "team_a": [{"player_id": owner.id}],
            "team_b": [{"player_id": created_player_id}],
            "notes": "审计日志测试比赛",
        },
        headers=owner_headers,
    )
    assert create_match_resp.status_code == 201, create_match_resp.text

    await _register(client, "auditsa", email="auditsa@test.com")
    sa_token = await _login(client, "auditsa")
    result = await db_session.execute(sa_select(Player).where(Player.username == "auditsa"))
    superadmin = result.scalar_one()
    superadmin.is_superadmin = True
    await db_session.commit()

    sa_headers = {"Authorization": f"Bearer {sa_token}"}
    logs_resp = await client.get(
        "/api/v1/audit-logs",
        params={"team_id": team_id, "page_size": 100},
        headers=sa_headers,
    )
    assert logs_resp.status_code == 200, logs_resp.text
    payload = logs_resp.json()
    actions = {item["action"] for item in payload["items"]}

    assert "team_created" in actions
    assert "team_info_updated" in actions
    assert "player_profile_updated" in actions
    assert "player_created" in actions
    assert "match_created" in actions

    team_update_log = next(item for item in payload["items"] if item["action"] == "team_info_updated")
    assert team_update_log["detail"]["before"]["name"] == "Audit Eagles"
    assert team_update_log["detail"]["after"]["name"] == "Audit Eagles Pro"

    filtered_resp = await client.get(
        "/api/v1/audit-logs",
        params={"team_id": team_id, "action": "player_profile_updated", "page_size": 20},
        headers=sa_headers,
    )
    assert filtered_resp.status_code == 200, filtered_resp.text
    filtered_payload = filtered_resp.json()
    assert filtered_payload["total"] >= 1
    assert all(item["action"] == "player_profile_updated" for item in filtered_payload["items"])


async def test_audit_logs_cover_draft_submit_and_admin_approve(client: AsyncClient, db_session):
    from sqlalchemy import select as sa_select

    from app.models.player import Player

    await _register(client, "auditowner2")
    owner_token = await _login(client, "auditowner2")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    create_team_resp = await client.post(
        "/api/v1/team/create",
        json={"team_name": "Audit Relay Team"},
        headers=owner_headers,
    )
    assert create_team_resp.status_code == 201, create_team_resp.text
    team_id = create_team_resp.json()["team_id"]

    await _register(client, "relaymember")
    member_token = await _login(client, "relaymember")
    member_headers = {"Authorization": f"Bearer {member_token}"}

    apply_resp = await client.post(
        "/api/v1/team/apply",
        json={"team_id": team_id},
        headers=member_headers,
    )
    assert apply_resp.status_code == 200, apply_resp.text

    pending_resp = await client.get("/api/v1/players?status=pending", headers=owner_headers)
    assert pending_resp.status_code == 200, pending_resp.text
    pending_member_id = pending_resp.json()[0]["id"]

    approve_member_resp = await client.patch(
        f"/api/v1/players/{pending_member_id}/status",
        json={"status": "active"},
        headers=owner_headers,
    )
    assert approve_member_resp.status_code == 200, approve_member_resp.text

    owner_result = await db_session.execute(sa_select(Player).where(Player.username == "auditowner2"))
    owner = owner_result.scalar_one()

    create_draft_resp = await client.post(
        "/api/v1/matches/drafts",
        json={
            "match_date": "2026-03-20",
            "match_type": "internal",
            "team_a_ids": [owner.id],
            "team_b_ids": [pending_member_id],
            "data_level": 3,
            "notes": "audit relay",
        },
        headers=member_headers,
    )
    assert create_draft_resp.status_code == 201, create_draft_resp.text
    draft_id = create_draft_resp.json()["id"]

    lock_resp = await client.get(f"/api/v1/matches/drafts/{draft_id}", headers=member_headers)
    assert lock_resp.status_code == 200, lock_resp.text

    submit_resp = await client.post(
        f"/api/v1/matches/drafts/{draft_id}/finalize",
        json={"notes": "submitted for approval"},
        headers=member_headers,
    )
    assert submit_resp.status_code == 200, submit_resp.text
    assert submit_resp.json()["status"] == "pending_approval"

    owner_approve_resp = await client.put(
        f"/api/v1/matches/{draft_id}",
        json={"action": "approve"},
        headers=owner_headers,
    )
    assert owner_approve_resp.status_code == 200, owner_approve_resp.text

    await _register(client, "auditsa2", email="auditsa2@test.com")
    sa_token = await _login(client, "auditsa2")
    sa_headers = {"Authorization": f"Bearer {sa_token}"}
    result = await db_session.execute(sa_select(Player).where(Player.username == "auditsa2"))
    superadmin = result.scalar_one()
    superadmin.is_superadmin = True
    await db_session.commit()

    logs_resp = await client.get(
        "/api/v1/audit-logs",
        params={"team_id": team_id, "page_size": 200},
        headers=sa_headers,
    )
    assert logs_resp.status_code == 200, logs_resp.text
    items = logs_resp.json()["items"]

    submit_logs = [item for item in items if item["action"] == "match_draft_submitted" and item["target_id"] == draft_id]
    approve_logs = [item for item in items if item["action"] == "match_approved" and item["target_id"] == draft_id]

    assert len(submit_logs) >= 1
    assert len(approve_logs) >= 1