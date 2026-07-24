"""T_TOV: 失误链路集成测试（事件记录 → 统计累计 → 评分惩罚）"""
from datetime import date

import pytest
from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PLAYERS_URL = "/api/v1/players"
MATCHES_URL = "/api/v1/matches"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


async def _register(client: AsyncClient, username: str, email: str | None = None) -> None:
    e = email or f"{username}@test.com"
    r = await client.post(REG_URL, json={"username": username, "email": e, "password": "pw123456"})
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, username: str) -> str:
    r = await client.post(LOGIN_URL, data={"username": username, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _approve_player(client: AsyncClient, owner_token: str, username: str) -> int:
    r = await client.get(f"{PLAYERS_URL}?status=pending",
                         headers={"Authorization": f"Bearer {owner_token}"})
    players = [p for p in r.json() if p["username"] == username]
    pid = players[0]["id"]
    await client.patch(f"{PLAYERS_URL}/{pid}/status", json={"status": "active"},
                       headers={"Authorization": f"Bearer {owner_token}"})
    return pid


async def _setup_team(client: AsyncClient):
    """建立包含 3 名 active 成员的队伍，返回 (owner_token, owner_id, p2_id, p3_id)"""
    await _register(client, "tovowner")
    owner_token = await _login(client, "tovowner")
    r = await client.post("/api/v1/team/create", json={"team_name": "TovTeam"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201, r.text
    team_id = r.json()["team_id"]

    await _register(client, "tovplay2")
    p2_token = await _login(client, "tovplay2")
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {p2_token}"})
    p2_id = await _approve_player(client, owner_token, "tovplay2")

    await _register(client, "tovplay3")
    p3_token = await _login(client, "tovplay3")
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {p3_token}"})
    p3_id = await _approve_player(client, owner_token, "tovplay3")

    me_r = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    owner_id = me_r.json()["id"]
    return owner_token, owner_id, p2_id, p3_id


# ---------------------------------------------------------------------------
# T_TOV01: 失误事件随比赛提交
# ---------------------------------------------------------------------------


async def test_turnover_event_type_accepted(client: AsyncClient):
    """events 中包含 event_type=turnover → 201，不报 422"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 15,
        "score_them": 10,
        "data_level": 1,
        "team_a": [{"player_id": owner_id}],
        "team_b": [{"player_id": p2_id}, {"player_id": p3_id}],
        "events": [
            {"event_type": "turnover", "team_side": "A", "player_id": owner_id},
            {"event_type": "turnover", "team_side": "B", "player_id": p2_id},
        ],
    }
    resp = await client.post(MATCHES_URL, json=payload,
                              headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# T_TOV02: 球员条目 turnovers 字段被累计到 total_turnovers
# ---------------------------------------------------------------------------


async def test_turnover_count_accumulated_after_approval(client: AsyncClient):
    """data_level=3 且 turnovers=2 → 审批后 player.total_turnovers 累计为 2"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)

    payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 15,
        "score_them": 10,
        "data_level": 3,
        "team_a": [{"player_id": owner_id, "goals": 5, "assists": 1, "plus_minus": 2, "turnovers": 2}],
        "team_b": [
            {"player_id": p2_id, "goals": 2, "assists": 1, "plus_minus": -1, "turnovers": 0},
            {"player_id": p3_id, "goals": 3, "assists": 0, "plus_minus": -1, "turnovers": 0},
        ],
    }
    resp = await client.post(MATCHES_URL, json=payload,
                              headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 201

    # owner 直接提交 → auto-approved → total_turnovers 应已累计
    me = await client.get(f"{PLAYERS_URL}/me",
                           headers={"Authorization": f"Bearer {owner_token}"})
    assert me.json()["total_turnovers"] == 2


# ---------------------------------------------------------------------------
# T_TOV03: 失误惩罚影响评分（失误球员 mu 低于同阵同场无失误球员）
# ---------------------------------------------------------------------------


async def test_turnover_penalty_applies_to_mu(client: AsyncClient):
    """比赛中有失误的球员，评分应比无失误的同阵队友更低

    场景：data_level=3，team_a 两名球员（owner 有 turnovers=1，p2 无失误），
    两人均为赢家，owner 还多一次失误惩罚，故 owner.mu < p2_after.mu
    注意：需要 p2 也是 team_a 才能处于相同的胜负场景下。
    """
    await _register(client, "penowner")
    owner_token = await _login(client, "penowner")
    r = await client.post("/api/v1/team/create", json={"team_name": "PenTeam"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    team_id = r.json()["team_id"]

    await _register(client, "penplay2")
    p2_token = await _login(client, "penplay2")
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {p2_token}"})
    p2_id = await _approve_player(client, owner_token, "penplay2")

    await _register(client, "penplay3")
    p3_token = await _login(client, "penplay3")
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {p3_token}"})
    p3_id = await _approve_player(client, owner_token, "penplay3")

    me_r = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    owner_id = me_r.json()["id"]

    # team_a: owner (turnovers=1) + p2 (turnovers=0)
    # team_b: p3
    payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 15,
        "score_them": 5,
        "data_level": 3,
        "team_a": [
            {"player_id": owner_id, "goals": 5, "assists": 0, "plus_minus": 2, "turnovers": 1},
            {"player_id": p2_id, "goals": 5, "assists": 0, "plus_minus": 2, "turnovers": 0},
        ],
        "team_b": [
            {"player_id": p3_id, "goals": 3, "assists": 0, "plus_minus": -2, "turnovers": 0},
        ],
    }
    resp = await client.post(MATCHES_URL, json=payload,
                              headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 201

    # 获取双方 mu
    owner_me = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    p2_me = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {p2_token}"})

    owner_mu = owner_me.json()["mu"]
    p2_mu = p2_me.json()["mu"]

    # owner 有失误惩罚，mu 应低于 p2（同阵同场景但无失误）
    assert owner_mu < p2_mu, (
        f"期望 owner(turnovers=1).mu({owner_mu:.4f}) < p2(turnovers=0).mu({p2_mu:.4f})"
    )


async def test_turnover_sigma_factor_applies_to_sigma(client: AsyncClient):
    """配置 turnover_sigma_factor 后，失误球员的 sigma 增量应显著高于无失误队友。"""
    await _register(client, "sigowner")
    owner_token = await _login(client, "sigowner")
    r = await client.post(
        "/api/v1/team/create",
        json={"team_name": "SigTeam"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    team_id = r.json()["team_id"]

    await _register(client, "sigplay2")
    p2_token = await _login(client, "sigplay2")
    await client.post("/api/v1/team/apply", json={"team_id": team_id}, headers={"Authorization": f"Bearer {p2_token}"})
    p2_id = await _approve_player(client, owner_token, "sigplay2")

    await _register(client, "sigplay3")
    p3_token = await _login(client, "sigplay3")
    await client.post("/api/v1/team/apply", json={"team_id": team_id}, headers={"Authorization": f"Bearer {p3_token}"})
    p3_id = await _approve_player(client, owner_token, "sigplay3")

    me_r = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    owner_id = me_r.json()["id"]

    # 放大 sigma 惩罚系数，便于观测
    put_resp = await client.put(
        "/api/v1/team/settings",
        json={"turnover_penalty": 0.4, "turnover_sigma_factor": 1.0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert put_resp.status_code == 200, put_resp.text

    payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 15,
        "score_them": 5,
        "data_level": 3,
        "team_a": [
            {"player_id": owner_id, "goals": 5, "assists": 0, "plus_minus": 2, "turnovers": 1},
            {"player_id": p2_id, "goals": 5, "assists": 0, "plus_minus": 2, "turnovers": 0},
        ],
        "team_b": [{"player_id": p3_id, "goals": 3, "assists": 0, "plus_minus": -2, "turnovers": 0}],
    }
    resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 201

    owner_me = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    p2_me = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {p2_token}"})
    owner_sigma = owner_me.json()["sigma"]
    p2_sigma = p2_me.json()["sigma"]
    owner_mu = owner_me.json()["mu"]
    p2_mu = p2_me.json()["mu"]

    # v2: turnover 仅惩罚 μ，不再膨胀 σ
    assert owner_sigma == pytest.approx(p2_sigma), (
        f"σ 不应受 turnover 影响: owner.sigma={owner_sigma:.4f} vs p2.sigma={p2_sigma:.4f}"
    )
    assert owner_mu < p2_mu, (
        f"owner(turnovers=1).mu({owner_mu:.4f}) 应低于 p2(turnovers=0).mu({p2_mu:.4f})"
    )
