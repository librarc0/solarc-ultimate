"""/team 核心端点集成测试：创建/加入/退出/审批与异常分支"""

from httpx import AsyncClient
from sqlalchemy import select

from app.models.player import Player, PlayerStatus
from app.models.team import Team

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


async def _make_superadmin(client: AsyncClient, db_session, username: str = "supteam1") -> str:
    await _register(client, username, email=f"{username}@test.com")
    token = await _login(client, username)
    player = (await db_session.execute(select(Player).where(Player.username == username))).scalar_one()
    player.is_superadmin = True
    await db_session.commit()
    return token


async def test_available_teams_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/team/available")
    assert resp.status_code == 401


async def test_create_team_and_get_my_team(client: AsyncClient):
    await _register(client, "teamow01")
    owner_token = await _login(client, "teamow01")

    c = await client.post(
        "/api/v1/team/create",
        json={"team_name": "CoreTeamA"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert c.status_code == 201, c.text
    assert c.json()["pending"] is True

    me = await client.get("/api/v1/team/my", headers={"Authorization": f"Bearer {owner_token}"})
    assert me.status_code == 200
    assert me.json()["name"] == "CoreTeamA"


async def test_create_team_duplicate_name_fails(client: AsyncClient):
    await _register(client, "teamow11")
    token1 = await _login(client, "teamow11")
    c1 = await client.post(
        "/api/v1/team/create",
        json={"team_name": "DupTeamX"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert c1.status_code == 201

    await _register(client, "teamow12")
    token2 = await _login(client, "teamow12")
    c2 = await client.post(
        "/api/v1/team/create",
        json={"team_name": "DupTeamX"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert c2.status_code == 400


async def test_apply_join_team_not_found_and_already_in_team(client: AsyncClient):
    await _register(client, "teamow21")
    owner_token = await _login(client, "teamow21")
    c = await client.post(
        "/api/v1/team/create",
        json={"team_name": "ApplyTeamA"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert c.status_code == 201

    # 已在队伍中的 owner 再申请加入其他队伍
    again = await client.post(
        "/api/v1/team/apply",
        json={"team_id": 999999},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert again.status_code == 400

    await _register(client, "teammb21")
    member_token = await _login(client, "teammb21")
    missing = await client.post(
        "/api/v1/team/apply",
        json={"team_id": 999999},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert missing.status_code == 404


async def test_leave_team_owner_with_members_forbidden_then_member_can_leave(client: AsyncClient):
    await _register(client, "teamow31")
    owner_token = await _login(client, "teamow31")
    c = await client.post(
        "/api/v1/team/create",
        json={"team_name": "LeaveTeamA"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    team_id = c.json()["team_id"]

    # 增加一名成员（pending 即可触发 owner 不能离队）
    await _register(client, "teammb31")
    member_token = await _login(client, "teammb31")
    await client.post(
        "/api/v1/team/apply",
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {member_token}"},
    )

    owner_leave = await client.delete("/api/v1/team/leave", headers={"Authorization": f"Bearer {owner_token}"})
    assert owner_leave.status_code == 400

    member_leave = await client.delete("/api/v1/team/leave", headers={"Authorization": f"Bearer {member_token}"})
    assert member_leave.status_code == 200


async def test_update_team_info_success_and_duplicate_name(client: AsyncClient):
    await _register(client, "teamow41")
    token1 = await _login(client, "teamow41")
    c1 = await client.post(
        "/api/v1/team/create",
        json={"team_name": "InfoTeamA"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert c1.status_code == 201

    await _register(client, "teamow42")
    token2 = await _login(client, "teamow42")
    c2 = await client.post(
        "/api/v1/team/create",
        json={"team_name": "InfoTeamB"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert c2.status_code == 201

    ok = await client.put(
        "/api/v1/team/info",
        json={"team_name": "InfoTeamA2"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert ok.status_code == 200

    dup = await client.put(
        "/api/v1/team/info",
        json={"team_name": "InfoTeamB"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert dup.status_code == 400


async def test_pending_teams_requires_superadmin_and_approve_workflow(client: AsyncClient, db_session):
    await _register(client, "teamow51")
    owner_token = await _login(client, "teamow51")
    c = await client.post(
        "/api/v1/team/create",
        json={"team_name": "PendingTeamA"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    team_id = c.json()["team_id"]

    forbidden = await client.get("/api/v1/team/pending-teams", headers={"Authorization": f"Bearer {owner_token}"})
    assert forbidden.status_code == 403

    sa_token = await _make_superadmin(client, db_session, "supteam5")

    pending = await client.get("/api/v1/team/pending-teams", headers={"Authorization": f"Bearer {sa_token}"})
    assert pending.status_code == 200
    assert any(t["id"] == team_id for t in pending.json())

    approve = await client.post(f"/api/v1/team/{team_id}/approve", headers={"Authorization": f"Bearer {sa_token}"})
    assert approve.status_code == 200

    again = await client.post(f"/api/v1/team/{team_id}/approve", headers={"Authorization": f"Bearer {sa_token}"})
    assert again.status_code == 400


async def test_reject_team_not_found_and_reject_pending_deactivates_team(client: AsyncClient, db_session):
    sa_token = await _make_superadmin(client, db_session, "supteam6")

    not_found = await client.post("/api/v1/team/999999/reject", headers={"Authorization": f"Bearer {sa_token}"})
    assert not_found.status_code == 404

    await _register(client, "teamow61")
    owner_token = await _login(client, "teamow61")
    c = await client.post(
        "/api/v1/team/create",
        json={"team_name": "RejectTeamA"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    team_id = c.json()["team_id"]

    # 增加一个成员，拒绝后应被踢出并标记 rejected
    await _register(client, "teammb61")
    member_token = await _login(client, "teammb61")
    await client.post(
        "/api/v1/team/apply",
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {member_token}"},
    )

    reject = await client.post(f"/api/v1/team/{team_id}/reject", headers={"Authorization": f"Bearer {sa_token}"})
    assert reject.status_code == 200

    team = (await db_session.execute(select(Team).where(Team.id == team_id))).scalar_one()
    assert team.is_active is False

    players = list((await db_session.execute(select(Player).where(Player.username.in_(["teamow61", "teammb61"])))).scalars())
    assert all(p.team_id is None for p in players)
    assert all(p.status == PlayerStatus.rejected for p in players)
