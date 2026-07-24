"""
外部队伍排行榜集成测试

覆盖：
- 公开 API: /api/v1/public/...
- 管理 API: /api/v1/ranking-admin/...
- 外部推送 API: /api/v1/external/...
- ranking_service.map_score_to_strength 单元测试
"""
import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team_ranking import RankingAdmin
from app.core.security import get_password_hash
from app.services.ranking_service import map_score_to_strength

ADMIN_URL = "/api/v1/ranking-admin"
PUBLIC_URL = "/api/v1/public"
EXTERNAL_URL = "/api/v1/external"

# ──────────────────────────────────────────────────────────────
# 测试数据
# ──────────────────────────────────────────────────────────────

SAMPLE_PAYLOAD = {
    "exportedAt": "2026-04-15T12:00:00Z",
    "version": "1.0",
    "source": "Ultimate-Frisbee-Scorecard",
    "rankings": [
        {
            "name": "北京飞鹰",
            "rank": 1,
            "totalScore": 1456.80,
            "avgScore": 364.20,
            "tournamentCount": 2,
            "wins": 13,
            "losses": 4,
            "draws": 1,
            "forfeits": 0,
            "totalGames": 18,
            "winRate": 0.722,
            "pointsScored": 157,
            "pointsConceded": 115,
            "netPoints": 42,
            "tournaments": [
                {
                    "tournamentName": "全国大学生飞盘联赛",
                    "level": "National",
                    "month": "2025-05",
                    "wins": 7,
                    "losses": 2,
                    "draws": 1,
                    "forfeits": 0,
                    "totalGames": 10,
                    "winRate": 0.7,
                    "pointsScored": 85,
                    "pointsConceded": 60,
                    "pool": "A",
                    "rank": 2,
                    "score": 498.50,
                },
                {
                    "tournamentName": "省级邀请赛",
                    "level": "Provincial",
                    "month": "2025-08",
                    "wins": 6,
                    "losses": 2,
                    "draws": 0,
                    "forfeits": 0,
                    "totalGames": 8,
                    "winRate": 0.75,
                    "pointsScored": 72,
                    "pointsConceded": 55,
                    "pool": "B",
                    "rank": 1,
                    "score": 327.60,
                },
            ],
        },
        {
            "name": "上海雄鹰",
            "rank": 2,
            "totalScore": 980.30,
            "avgScore": 490.15,
            "tournamentCount": 1,
            "wins": 8,
            "losses": 3,
            "draws": 0,
            "forfeits": 0,
            "totalGames": 11,
            "winRate": 0.727,
            "pointsScored": 95,
            "pointsConceded": 70,
            "netPoints": 25,
            "tournaments": [
                {
                    "tournamentName": "全国大学生飞盘联赛",
                    "level": "National",
                    "month": "2025-05",
                    "wins": 8,
                    "losses": 3,
                    "draws": 0,
                    "forfeits": 0,
                    "totalGames": 11,
                    "winRate": 0.727,
                    "pointsScored": 95,
                    "pointsConceded": 70,
                    "pool": "A",
                    "rank": 3,
                    "score": 980.30,
                }
            ],
        },
    ],
}


# ──────────────────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────────────────

async def _seed_admin(db_session: AsyncSession) -> RankingAdmin:
    admin = RankingAdmin(
        username="testadmin",
        password_hash=get_password_hash("testpass123"),
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


async def _login_admin(client: AsyncClient) -> str:
    r = await client.post(
        f"{ADMIN_URL}/login",
        data={"username": "testadmin", "password": "testpass123"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _create_season(
    client: AsyncClient, token: str, name: str = "2025春季赛", year: int = 2025
) -> int:
    r = await client.post(
        f"{ADMIN_URL}/seasons",
        json={"name": name, "year": year},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _upload(
    client: AsyncClient,
    token: str,
    season_id: int,
    payload: dict = SAMPLE_PAYLOAD,
    notes: str = "",
) -> dict:
    content = json.dumps(payload).encode()
    data = {"season_id": str(season_id)}
    if notes:
        data["notes"] = notes
    r = await client.post(
        f"{ADMIN_URL}/upload",
        files={"file": ("rankings.json", content, "application/json")},
        data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ──────────────────────────────────────────────────────────────
# 单元测试：map_score_to_strength
# ──────────────────────────────────────────────────────────────


class TestMapScoreToStrength:
    def test_max_score_returns_10(self):
        assert map_score_to_strength(100.0, 0.0, 100.0) == 10.0

    def test_min_score_returns_1(self):
        assert map_score_to_strength(0.0, 0.0, 100.0) == 1.0

    def test_midpoint_returns_5_5(self):
        result = map_score_to_strength(50.0, 0.0, 100.0)
        assert result == 5.5

    def test_equal_min_max_returns_5(self):
        assert map_score_to_strength(50.0, 50.0, 50.0) == 5.0

    def test_clamps_below_min(self):
        result = map_score_to_strength(-10.0, 0.0, 100.0)
        assert result == 1.0

    def test_clamps_above_max(self):
        result = map_score_to_strength(150.0, 0.0, 100.0)
        assert result == 10.0

    def test_result_rounded_to_1_decimal(self):
        result = map_score_to_strength(33.33, 0.0, 100.0)
        # Should have at most 1 decimal place
        assert result == round(result, 1)


# ──────────────────────────────────────────────────────────────
# 公开接口：赛季列表
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_public_seasons_empty(client: AsyncClient, db_session: AsyncSession):
    r = await client.get(f"{PUBLIC_URL}/seasons")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.anyio
async def test_public_seasons_populated(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    await _create_season(client, token, name="2025春季赛", year=2025)
    await _create_season(client, token, name="2024秋季赛", year=2024)

    r = await client.get(f"{PUBLIC_URL}/seasons")
    assert r.status_code == 200
    seasons = r.json()
    assert len(seasons) == 2
    # 应按年份降序排列
    assert seasons[0]["year"] >= seasons[1]["year"]
    assert "name" in seasons[0]
    assert "id" in seasons[0]


# ──────────────────────────────────────────────────────────────
# 公开接口：队伍排行榜列表
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_public_team_rankings_no_data(client: AsyncClient, db_session: AsyncSession):
    r = await client.get(f"{PUBLIC_URL}/team-rankings")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.anyio
async def test_public_team_rankings_with_data(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(f"{PUBLIC_URL}/team-rankings", params={"season_id": season_id})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert data["season_id"] == season_id
    items = data["items"]
    assert items[0]["rank"] == 1
    assert items[0]["name"] == "北京飞鹰"
    assert items[1]["rank"] == 2
    assert items[1]["name"] == "上海雄鹰"


@pytest.mark.anyio
async def test_public_team_rankings_pagination(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings",
        params={"season_id": season_id, "page": 1, "page_size": 1},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["page"] == 1
    assert data["page_size"] == 1


@pytest.mark.anyio
async def test_public_team_rankings_search(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings",
        params={"season_id": season_id, "search": "北京"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "北京飞鹰"


@pytest.mark.anyio
async def test_public_team_rankings_sort_by_win_rate(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings",
        params={"season_id": season_id, "sort_by": "win_rate"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    # 上海 winRate=0.727 > 北京 winRate=0.722 → 应排第一
    assert items[0]["name"] == "上海雄鹰"


@pytest.mark.anyio
async def test_public_team_rankings_defaults_to_latest_season(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    s1 = await _create_season(client, token, name="2024赛季", year=2024)
    s2 = await _create_season(client, token, name="2025赛季", year=2025)
    await _upload(client, token, s1)
    await _upload(client, token, s2)

    r = await client.get(f"{PUBLIC_URL}/team-rankings")
    assert r.status_code == 200
    # 无 season_id 时默认返回数据，不应为空
    data = r.json()
    assert data["total"] > 0


# ──────────────────────────────────────────────────────────────
# 公开接口：for-match
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_public_teams_for_match(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings/for-match",
        params={"season_id": season_id},
    )
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    # 每条应有 name, total_score, rank 字段
    for item in items:
        assert "name" in item
        assert "total_score" in item
        assert "rank" in item


@pytest.mark.anyio
async def test_public_teams_for_match_search(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings/for-match",
        params={"season_id": season_id, "search": "上海"},
    )
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["name"] == "上海雄鹰"


# ──────────────────────────────────────────────────────────────
# 公开接口：队伍详情
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_public_team_detail_found(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings/北京飞鹰",
        params={"season_id": season_id},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "北京飞鹰"
    assert data["rank"] == 1
    assert data["season_id"] == season_id
    # 赛事历史按月份降序
    records = data["tournament_records"]
    assert len(records) == 2
    assert records[0]["month"] >= records[1]["month"]


@pytest.mark.anyio
async def test_public_team_detail_not_found(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings/不存在的队伍",
        params={"season_id": season_id},
    )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_public_team_detail_tournament_records_fields(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings/北京飞鹰",
        params={"season_id": season_id},
    )
    assert r.status_code == 200
    record = r.json()["tournament_records"][0]
    for field in ["tournament_name", "level", "month", "wins", "losses", "computed_score", "pool", "final_rank"]:
        assert field in record, f"缺少字段: {field}"


# ──────────────────────────────────────────────────────────────
# 公开接口：队伍对比
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_public_team_compare_same_season(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings/compare",
        params={"teams": "北京飞鹰,上海雄鹰", "season_ids": f"{season_id},{season_id}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    names = {item["name"] for item in data}
    assert "北京飞鹰" in names
    assert "上海雄鹰" in names


@pytest.mark.anyio
async def test_public_team_compare_cross_season(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    s1 = await _create_season(client, token, name="2024赛季", year=2024)
    s2 = await _create_season(client, token, name="2025赛季", year=2025)

    # 两个赛季各自上传数据
    await _upload(client, token, s1)
    await _upload(client, token, s2)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings/compare",
        params={"teams": "北京飞鹰,上海雄鹰", "season_ids": f"{s1},{s2}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    # 两支队伍来自各自的赛季
    season_ids_returned = {item["season_id"] for item in data}
    assert s1 in season_ids_returned
    assert s2 in season_ids_returned


@pytest.mark.anyio
async def test_public_team_compare_missing_team(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings/compare",
        params={"teams": "北京飞鹰,不存在队伍", "season_ids": f"{season_id},{season_id}"},
    )
    assert r.status_code == 200
    data = r.json()
    # 只返回找到的队伍
    assert len(data) == 1
    assert data[0]["name"] == "北京飞鹰"


# ──────────────────────────────────────────────────────────────
# 公开接口：队伍强度
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_public_team_strength_rank1_is_10(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings-strength/北京飞鹰",
        params={"season_id": season_id},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "北京飞鹰"
    # 最高分队伍强度应为 10.0
    assert data["strength"] == 10.0
    assert data["rank"] == 1
    assert data["season_id"] == season_id


@pytest.mark.anyio
async def test_public_team_strength_rank2_less_than_10(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings-strength/上海雄鹰",
        params={"season_id": season_id},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["strength"] < 10.0
    assert data["strength"] >= 1.0


@pytest.mark.anyio
async def test_public_team_strength_not_found(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings-strength/不存在队伍",
        params={"season_id": season_id},
    )
    assert r.status_code == 404


# ──────────────────────────────────────────────────────────────
# 管理接口：登录
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_admin_login_success(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    r = await client.post(
        f"{ADMIN_URL}/login",
        data={"username": "testadmin", "password": "testpass123"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.anyio
async def test_admin_login_wrong_password(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    r = await client.post(
        f"{ADMIN_URL}/login",
        data={"username": "testadmin", "password": "wrongpass"},
    )
    assert r.status_code == 401


@pytest.mark.anyio
async def test_admin_login_no_user(client: AsyncClient, db_session: AsyncSession):
    r = await client.post(
        f"{ADMIN_URL}/login",
        data={"username": "nobody", "password": "test"},
    )
    assert r.status_code == 401


@pytest.mark.anyio
async def test_admin_protected_without_token(client: AsyncClient, db_session: AsyncSession):
    r = await client.get(f"{ADMIN_URL}/seasons")
    assert r.status_code == 401


# ──────────────────────────────────────────────────────────────
# 管理接口：赛季 CRUD
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_admin_create_season(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)

    r = await client.post(
        f"{ADMIN_URL}/seasons",
        json={"name": "2025春季赛", "year": 2025, "description": "测试赛季"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "2025春季赛"
    assert data["year"] == 2025
    assert "id" in data


@pytest.mark.anyio
async def test_admin_list_seasons(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    await _create_season(client, token, name="A赛季", year=2025)
    await _create_season(client, token, name="B赛季", year=2024)

    r = await client.get(
        f"{ADMIN_URL}/seasons",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.anyio
async def test_admin_update_season(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)

    r = await client.patch(
        f"{ADMIN_URL}/seasons/{season_id}",
        json={"name": "已更新赛季名", "is_active": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "已更新赛季名"
    assert r.json()["is_active"] is True


@pytest.mark.anyio
async def test_admin_delete_season_cascades(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id)

    # 确认有数据
    r = await client.get(
        f"{PUBLIC_URL}/team-rankings",
        params={"season_id": season_id},
    )
    assert r.json()["total"] == 2

    # 删除赛季
    r = await client.delete(
        f"{ADMIN_URL}/seasons/{season_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204

    # 确认赛季在管理端已不存在
    r = await client.get(
        f"{ADMIN_URL}/seasons",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    season_ids = [s["id"] for s in r.json()]
    assert season_id not in season_ids


# ──────────────────────────────────────────────────────────────
# 管理接口：上传
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_admin_upload_success(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)

    result = await _upload(client, token, season_id)
    assert result["teams_processed"] == 2
    assert "batch_id" in result


@pytest.mark.anyio
async def test_admin_upload_invalid_json(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)

    r = await client.post(
        f"{ADMIN_URL}/upload",
        files={"file": ("bad.json", b"not valid json", "application/json")},
        data={"season_id": str(season_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.anyio
async def test_admin_upload_no_season(client: AsyncClient, db_session: AsyncSession):
    """上传时指定不存在的赛季 ID 应返回 404"""
    await _seed_admin(db_session)
    token = await _login_admin(client)

    content = json.dumps(SAMPLE_PAYLOAD).encode()
    r = await client.post(
        f"{ADMIN_URL}/upload",
        files={"file": ("rankings.json", content, "application/json")},
        data={"season_id": "9999"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_admin_upload_second_time_updates_rank_change(
    client: AsyncClient, db_session: AsyncSession
):
    """第二次上传时，rank_change 应反映排名变化"""
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)

    # 第一次上传：北京#1，上海#2
    await _upload(client, token, season_id)

    # 第二次上传：上海#1，北京#2（排名互换）
    swapped = {**SAMPLE_PAYLOAD, "rankings": [
        {**SAMPLE_PAYLOAD["rankings"][1], "rank": 1},
        {**SAMPLE_PAYLOAD["rankings"][0], "rank": 2},
    ]}
    await _upload(client, token, season_id, payload=swapped)

    # 北京应该 rank_change < 0（从1下滑到2）
    r = await client.get(
        f"{PUBLIC_URL}/team-rankings/北京飞鹰",
        params={"season_id": season_id},
    )
    assert r.status_code == 200
    assert r.json()["rank_change"] < 0


# ──────────────────────────────────────────────────────────────
# 管理接口：批次管理
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_admin_list_batches(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    await _upload(client, token, season_id, notes="第一批")
    await _upload(client, token, season_id, notes="第二批")

    r = await client.get(
        f"{ADMIN_URL}/batches",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    batches = r.json()
    assert len(batches) == 2


@pytest.mark.anyio
async def test_admin_list_batches_filter_by_season(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    s1 = await _create_season(client, token, name="赛季1", year=2024)
    s2 = await _create_season(client, token, name="赛季2", year=2025)
    await _upload(client, token, s1)
    await _upload(client, token, s2)
    await _upload(client, token, s2)

    r = await client.get(
        f"{ADMIN_URL}/batches",
        params={"season_id": s2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    batches = r.json()
    assert len(batches) == 2
    for b in batches:
        assert b["season_id"] == s2


@pytest.mark.anyio
async def test_admin_restore_batch(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    first = await _upload(client, token, season_id, notes="原始批次")
    batch_id = first["batch_id"]

    # 上传新数据（会覆盖）
    swapped = {**SAMPLE_PAYLOAD, "rankings": [
        {**SAMPLE_PAYLOAD["rankings"][1], "rank": 1},
        {**SAMPLE_PAYLOAD["rankings"][0], "rank": 2},
    ]}
    await _upload(client, token, season_id, payload=swapped)

    # 恢复原始批次
    r = await client.post(
        f"{ADMIN_URL}/batches/{batch_id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200

    # 确认数据已恢复（北京应该回到#1）
    r = await client.get(
        f"{PUBLIC_URL}/team-rankings/北京飞鹰",
        params={"season_id": season_id},
    )
    assert r.json()["rank"] == 1


@pytest.mark.anyio
async def test_admin_delete_batch(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)
    result = await _upload(client, token, season_id)
    batch_id = result["batch_id"]

    r = await client.delete(
        f"{ADMIN_URL}/batches/{batch_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204

    r = await client.get(
        f"{ADMIN_URL}/batches",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.json() == []


# ──────────────────────────────────────────────────────────────
# 管理接口：API Key 管理
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_admin_create_api_key(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)

    r = await client.post(
        f"{ADMIN_URL}/api-keys",
        data={"name": "测试Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (200, 201)
    data = r.json()
    assert "full_key" in data
    assert data["full_key"].startswith("ep_")
    assert "key_prefix" in data
    assert data["name"] == "测试Key"


@pytest.mark.anyio
async def test_admin_list_api_keys(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)

    await client.post(
        f"{ADMIN_URL}/api-keys",
        data={"name": "Key1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"{ADMIN_URL}/api-keys",
        data={"name": "Key2"},
        headers={"Authorization": f"Bearer {token}"},
    )

    r = await client.get(
        f"{ADMIN_URL}/api-keys",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    keys = r.json()
    assert len(keys) == 2
    # full_key 不应出现在列表中（安全）
    for k in keys:
        assert "full_key" not in k


@pytest.mark.anyio
async def test_admin_revoke_api_key(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)

    r = await client.post(
        f"{ADMIN_URL}/api-keys",
        data={"name": "撤销测试"},
        headers={"Authorization": f"Bearer {token}"},
    )
    key_id = r.json()["id"]
    full_key = r.json()["full_key"]

    r = await client.delete(
        f"{ADMIN_URL}/api-keys/{key_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204

    # 撤销后的 key 不能用于外部推送
    season_id = await _create_season(client, token)
    r = await client.post(
        f"{EXTERNAL_URL}/rankings/push",
        json=SAMPLE_PAYLOAD,
        params={"season_id": season_id},
        headers={"X-API-Key": full_key},
    )
    assert r.status_code == 401


# ──────────────────────────────────────────────────────────────
# 外部推送接口
# ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_external_push_valid_key(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)

    # 创建 API Key
    r = await client.post(
        f"{ADMIN_URL}/api-keys",
        data={"name": "推送测试Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    full_key = r.json()["full_key"]

    r = await client.post(
        f"{EXTERNAL_URL}/rankings/push",
        json=SAMPLE_PAYLOAD,
        params={"season_id": season_id},
        headers={"X-API-Key": full_key},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["teams_processed"] == 2
    assert "batch_id" in data


@pytest.mark.anyio
async def test_external_push_invalid_key(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)

    r = await client.post(
        f"{EXTERNAL_URL}/rankings/push",
        json=SAMPLE_PAYLOAD,
        params={"season_id": season_id},
        headers={"X-API-Key": "ep_invalidkey123456"},
    )
    assert r.status_code == 401


@pytest.mark.anyio
async def test_external_push_no_season(client: AsyncClient, db_session: AsyncSession):
    """无赛季时推送（不传 season_id）应返回 400"""
    await _seed_admin(db_session)
    token = await _login_admin(client)

    r = await client.post(
        f"{ADMIN_URL}/api-keys",
        data={"name": "无赛季推送Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    full_key = r.json()["full_key"]

    r = await client.post(
        f"{EXTERNAL_URL}/rankings/push",
        json=SAMPLE_PAYLOAD,
        # 不传 season_id，且 DB 里没有任何赛季
        headers={"X-API-Key": full_key},
    )
    assert r.status_code == 400


@pytest.mark.anyio
async def test_external_push_updates_public_data(client: AsyncClient, db_session: AsyncSession):
    """推送成功后公开接口应能看到上传的数据"""
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)

    r = await client.post(
        f"{ADMIN_URL}/api-keys",
        data={"name": "验证Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    full_key = r.json()["full_key"]

    await client.post(
        f"{EXTERNAL_URL}/rankings/push",
        json=SAMPLE_PAYLOAD,
        params={"season_id": season_id},
        headers={"X-API-Key": full_key},
    )

    r = await client.get(
        f"{PUBLIC_URL}/team-rankings",
        params={"season_id": season_id},
    )
    assert r.status_code == 200
    assert r.json()["total"] == 2


@pytest.mark.anyio
async def test_external_push_uses_latest_season_when_no_season_id(
    client: AsyncClient, db_session: AsyncSession
):
    """有赛季时不传 season_id，自动用最新赛季"""
    await _seed_admin(db_session)
    token = await _login_admin(client)
    season_id = await _create_season(client, token)

    r = await client.post(
        f"{ADMIN_URL}/api-keys",
        data={"name": "自动赛季Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    full_key = r.json()["full_key"]

    r = await client.post(
        f"{EXTERNAL_URL}/rankings/push",
        json=SAMPLE_PAYLOAD,
        headers={"X-API-Key": full_key},
        # 不传 season_id
    )
    assert r.status_code == 200
    assert r.json()["teams_processed"] == 2
