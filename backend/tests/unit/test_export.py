"""T072: CSV 导出单元测试"""
import io
import csv
import pytest
from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
EXPORT_RANKINGS_URL = "/api/v1/exports/rankings"
EXPORT_MATCHES_URL = "/api/v1/exports/matches"
EXPORT_PLAYERS_URL = "/api/v1/exports/players"
EXPORT_PLAYER_STATS_URL = "/api/v1/exports/player-stats"


async def _login(client: AsyncClient, username: str, password: str = "pw123456") -> str:
    resp = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_admin(client: AsyncClient) -> str:
    """创建 owner 并返回 token"""
    r = await client.post(REG_URL, json={"username": "adminuser", "email": "adminuser@test.com", "password": "pw123456"})
    assert r.status_code == 201, f"admin reg failed: {r.text}"
    token = await _login(client, "adminuser")
    r_team = await client.post("/api/v1/team/create", json={"team_name": "Eagles"},
                               headers={"Authorization": f"Bearer {token}"})
    assert r_team.status_code == 201, r_team.text
    return token


async def _create_member(client: AsyncClient) -> str:
    """创建普通成员并返回 token"""
    await client.post(REG_URL, json={"username": "member001", "email": "member001@test.com", "password": "pw123456"})
    admin_token = await _login(client, "adminuser")
    # 获取队伍 id
    team_resp = await client.get("/api/v1/team/my", headers={"Authorization": f"Bearer {admin_token}"})
    team_id = team_resp.json()["id"]
    # 申请加入队伍
    member_pre_token = await _login(client, "member001")
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {member_pre_token}"})
    # 审批
    players_resp = await client.get("/api/v1/players?status=pending", headers={"Authorization": f"Bearer {admin_token}"})
    member_id = next(p["id"] for p in players_resp.json() if p["username"] == "member001")
    await client.patch(f"/api/v1/players/{member_id}/status", json={"status": "active"}, headers={"Authorization": f"Bearer {admin_token}"})
    return await _login(client, "member001")


async def test_export_rankings_requires_admin(client: AsyncClient):
    """非 admin 访问导出接口 → 401（未认证）"""
    resp = await client.get(EXPORT_RANKINGS_URL)
    assert resp.status_code == 401


async def test_export_rankings_member_forbidden(client: AsyncClient):
    """普通成员访问导出 → 403"""
    admin_token = await _create_admin(client)
    member_token = await _create_member(client)
    resp = await client.get(EXPORT_RANKINGS_URL, headers={"Authorization": f"Bearer {member_token}"})
    assert resp.status_code == 403


async def test_export_rankings_csv_headers(client: AsyncClient):
    """admin 导出积分榜 CSV — 含正确表头"""
    token = await _create_admin(client)
    resp = await client.get(EXPORT_RANKINGS_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]

    # 解码（去除 BOM）
    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "排名" in header
    assert "用户名" in header
    assert "μ" in header
    assert "保守评分" in header


async def test_export_matches_csv_headers(client: AsyncClient):
    """admin 导出比赛记录 CSV — 含正确表头"""
    token = await _create_admin(client)
    resp = await client.get(EXPORT_MATCHES_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]

    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "ID" in header
    assert "日期" in header
    assert "我方得分" in header


async def test_export_matches_member_forbidden(client: AsyncClient):
    """普通成员访问比赛导出 → 403"""
    admin_token = await _create_admin(client)
    member_token = await _create_member(client)
    resp = await client.get(EXPORT_MATCHES_URL, headers={"Authorization": f"Bearer {member_token}"})
    assert resp.status_code == 403


@pytest.mark.parametrize("ranking_type", ["conservative", "mu", "sigma", "goals", "assists", "plus_minus", "turnovers"])
async def test_export_rankings_with_ranking_type(client: AsyncClient, ranking_type: str):
    """管理员可导出不同排行榜类型 CSV"""
    token = await _create_admin(client)
    resp = await client.get(
        EXPORT_RANKINGS_URL,
        params={"ranking_type": ranking_type},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert f"rankings_{ranking_type}" in resp.headers.get("content-disposition", "")


async def test_export_players_csv_headers(client: AsyncClient):
    """管理员导出队员名单 CSV — 含正确表头"""
    token = await _create_admin(client)
    resp = await client.get(EXPORT_PLAYERS_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]

    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "用户名" in header
    assert "角色" in header
    assert "状态" in header


async def test_export_player_stats_csv_headers(client: AsyncClient):
    """管理员导出个人数据集合 CSV — 含正确表头"""
    token = await _create_admin(client)
    resp = await client.get(EXPORT_PLAYER_STATS_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]

    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "总场次" in header
    assert "进球" in header
    assert "保守评分" in header


async def test_export_single_player_profile_csv(client: AsyncClient):
    """管理员可按 player_id 导出单个队员完整信息"""
    token = await _create_admin(client)
    players_resp = await client.get("/api/v1/players", headers={"Authorization": f"Bearer {token}"})
    assert players_resp.status_code == 200
    players = players_resp.json()
    assert players, "预期至少存在管理员本人"

    player_id = players[0]["id"]
    resp = await client.get(
        EXPORT_PLAYER_STATS_URL,
        params={"player_id": player_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "player_profile_" in resp.headers.get("content-disposition", "")

    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "邮箱" in header
    assert "头像URL" in header
    assert "是否展示在排行榜" in header
