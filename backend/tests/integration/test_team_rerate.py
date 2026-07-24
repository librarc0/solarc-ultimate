"""T0xx: 超级管理员按当前系数重算某队历史比赛"""

import pytest
from httpx import AsyncClient


REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PLAYERS_URL = "/api/v1/players"


async def _register(client: AsyncClient, username: str, password: str = "pw123456", email: str | None = None):
    e = email or f"{username}@test.com"
    r = await client.post(REG_URL, json={"username": username, "email": e, "password": password})
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, username: str, password: str = "pw123456") -> str:
    r = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _apply_and_approve(client: AsyncClient, username: str, team_id: int, owner_token: str) -> int:
    """注册 → 登录 → 申请加入队伍 → owner 审批，返回 player_id"""
    await _register(client, username)
    token = await _login(client, username)
    await client.post("/api/v1/team/apply", json={"team_id": team_id}, headers={"Authorization": f"Bearer {token}"})
    r = await client.get(f"{PLAYERS_URL}?status=pending", headers={"Authorization": f"Bearer {owner_token}"})
    pid = next(p["id"] for p in r.json() if p["username"] == username)
    await client.patch(f"{PLAYERS_URL}/{pid}/status", json={"status": "active"}, headers={"Authorization": f"Bearer {owner_token}"})
    return int(pid)


async def test_superadmin_rerate_team_history_changes_ratings(client: AsyncClient, db_session):
    from datetime import date
    from sqlalchemy import select as sa_select
    from app.models.player import Player

    # 1) 创建一支队伍 + 2 个成员，提交 2 场比赛（auto-approved）
    await _register(client, "ownerra")
    owner_token = await _login(client, "ownerra")
    c = await client.post("/api/v1/team/create", json={"team_name": "RerateTeam"}, headers={"Authorization": f"Bearer {owner_token}"})
    assert c.status_code == 201, c.text
    team_id = c.json()["team_id"]

    p2_id = await _apply_and_approve(client, "playrb", team_id, owner_token)
    p3_id = await _apply_and_approve(client, "playrc", team_id, owner_token)

    owner_id = (await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})).json()["id"]

    base_payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 15,
        "score_them": 5,
        "data_level": 2,
        "team_a": [
            {"player_id": owner_id, "goals": 5, "assists": 0},
            {"player_id": p2_id, "goals": 0, "assists": 0},
        ],
        "team_b": [{"player_id": p3_id, "goals": 0, "assists": 0}],
    }
    r1 = await client.post("/api/v1/matches", json=base_payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert r1.status_code == 201, r1.text
    r2 = await client.post("/api/v1/matches", json=base_payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert r2.status_code == 201, r2.text

    owner_mu_before = (await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})).json()["mu"]

    # 2) 创建超管并设置 is_superadmin=True
    await _register(client, "superra", email="superra@test.com")
    sa_token = await _login(client, "superra")
    result = await db_session.execute(sa_select(Player).where(Player.username == "superra"))
    sa_player = result.scalar_one()
    sa_player.is_superadmin = True
    await db_session.commit()

    # 3) 修改该队 tau（影响 sigma 动态因子 → 直接改变 mu 收敛行为）并触发重算
    # 超管通过 ?team_id= 指定要操作的队伍
    put = await client.put(
        "/api/v1/team/settings?team_id=" + str(team_id),
        json={"openskill_tau": 2.5},
        headers={"Authorization": f"Bearer {sa_token}"},
    )
    assert put.status_code == 200, put.text
    assert put.json()["openskill_tau"] == pytest.approx(2.5)

    rr = await client.post(
        f"/api/v1/team/{team_id}/rerate",
        headers={"Authorization": f"Bearer {sa_token}"},
    )
    assert rr.status_code == 200, rr.text
    assert rr.json()["matches_replayed"] >= 2

    # 4) 重算后，owner 的 mu 应发生变化（tau 改变影响 sigma 收敛行为，从而改变 mu）
    owner_mu_after = (await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})).json()["mu"]
    assert owner_mu_after != owner_mu_before

