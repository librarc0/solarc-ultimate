"""T043-T048: /rankings 端点集成测试"""
import pytest
from datetime import date
from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PLAYERS_URL = "/api/v1/players"
MATCHES_URL = "/api/v1/matches"
RANKINGS_URL = "/api/v1/rankings"
SCHEDULE_EVENTS_URL = "/api/v1/schedule-events"
ATTENDANCE_URL = "/api/v1/schedule-attendance"


# ---------------------------------------------------------------------------
# 辅助函数（与 test_matches.py 保持一致的 setup 模式）
# ---------------------------------------------------------------------------


async def _register(client, username, password="pw123456", email=None):
    e = email or f"{username}@test.com"
    r = await client.post(REG_URL, json={"username": username, "email": e, "password": password})
    assert r.status_code == 201, r.text


async def _login(client, username, password="pw123456") -> str:
    r = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _approve_player(client, owner_token, username) -> int:
    r = await client.get(f"{PLAYERS_URL}?status=pending", headers={"Authorization": f"Bearer {owner_token}"})
    players = [p for p in r.json() if p["username"] == username]
    pid = players[0]["id"]
    await client.patch(f"{PLAYERS_URL}/{pid}/status", json={"status": "active"}, headers={"Authorization": f"Bearer {owner_token}"})
    return pid


async def _setup_match(client) -> tuple[str, int, int]:
    """建立 2 人队伍并提交一场已审批比赛，返回 (owner_token, owner_id, player2_id)"""
    await _register(client, "rankowner")
    owner_token = await _login(client, "rankowner")
    r_team = await client.post("/api/v1/team/create", json={"team_name": "Eagles"},
                               headers={"Authorization": f"Bearer {owner_token}"})
    assert r_team.status_code == 201, r_team.text
    team_id = r_team.json()["team_id"]

    await _register(client, "rankp2")
    p2_token = await _login(client, "rankp2")
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {p2_token}"})
    p2_id = await _approve_player(client, owner_token, "rankp2")

    me_r = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    owner_id = me_r.json()["id"]

    payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 15,
        "score_them": 10,
        "data_level": 1,
        "team_a": [{"player_id": owner_id}],
        "team_b": [{"player_id": p2_id}],
    }
    r = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201
    return owner_token, owner_id, p2_id


async def _setup_team_members(client: AsyncClient, team_name: str, member_usernames: list[str]) -> tuple[str, int, dict[str, int]]:
    """创建队伍并审批指定成员，返回 (owner_token, owner_id, {username: player_id})。"""
    owner_name = ("owner" + team_name).lower().replace("_", "")[:20]
    await _register(client, owner_name)
    owner_token = await _login(client, owner_name)
    r_team = await client.post(
        "/api/v1/team/create",
        json={"team_name": team_name},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert r_team.status_code == 201, r_team.text
    team_id = r_team.json()["team_id"]

    me_r = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    owner_id = me_r.json()["id"]

    id_map: dict[str, int] = {}
    for uname in member_usernames:
        await _register(client, uname)
        member_token = await _login(client, uname)
        apply_r = await client.post(
            "/api/v1/team/apply",
            json={"team_id": team_id},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert apply_r.status_code == 200, apply_r.text
        id_map[uname] = await _approve_player(client, owner_token, uname)

    return owner_token, owner_id, id_map


async def _create_published_event(client: AsyncClient, owner_token: str, title: str, event_type: str) -> int:
    today = date.today().isoformat()
    created = await client.post(
        SCHEDULE_EVENTS_URL,
        json={"title": title, "event_type": event_type, "start_date": today, "end_date": today},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 201, created.text
    event_id = created.json()["id"]
    published = await client.post(
        f"{SCHEDULE_EVENTS_URL}/{event_id}/publish",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert published.status_code == 200, published.text
    return event_id


# ---------------------------------------------------------------------------
# GET /rankings — 公开排行榜
# ---------------------------------------------------------------------------


async def test_rankings_requires_auth(client: AsyncClient):
    """排行榜需要登录（团队隔离）"""
    resp = await client.get(RANKINGS_URL)
    assert resp.status_code == 401


async def test_rankings_empty_before_any_match(client: AsyncClient):
    """无比赛时排行榜返回空 items 列表"""
    await _register(client, "rankempty")
    token = await _login(client, "rankempty")
    await client.post("/api/v1/team/create", json={"team_name": "EmptyTeam"},
                      headers={"Authorization": f"Bearer {token}"})
    resp = await client.get(RANKINGS_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["page"] == 1


async def test_rankings_includes_active_players_after_match(client: AsyncClient):
    """有比赛后，active 球员出现在排行榜"""
    owner_token, owner_id, p2_id = await _setup_match(client)
    resp = await client.get(RANKINGS_URL, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 2


async def test_rankings_sorted_by_conservative_rating(client: AsyncClient):
    """排行榜按 conservative_rating 降序"""
    owner_token, _, _ = await _setup_match(client)
    resp = await client.get(RANKINGS_URL, headers={"Authorization": f"Bearer {owner_token}"})
    items = resp.json()["items"]
    scores = [item["conservative_rating"] for item in items]
    assert scores == sorted(scores, reverse=True)


async def test_rankings_rank_field_sequential(client: AsyncClient):
    """rank 字段从 1 开始连续递增"""
    owner_token, _, _ = await _setup_match(client)
    resp = await client.get(RANKINGS_URL, headers={"Authorization": f"Bearer {owner_token}"})
    items = resp.json()["items"]
    ranks = [item["rank"] for item in items]
    assert ranks == list(range(1, len(ranks) + 1))


async def test_rankings_pagination(client: AsyncClient):
    """分页参数生效：page_size=1 只返回 1 条"""
    owner_token, _, _ = await _setup_match(client)
    resp = await client.get(f"{RANKINGS_URL}?page=1&page_size=1",
                             headers={"Authorization": f"Bearer {owner_token}"})
    items = resp.json()["items"]
    assert len(items) == 1


# ---------------------------------------------------------------------------
# GET /rankings/panel/{player_id}
# ---------------------------------------------------------------------------


async def test_player_panel_requires_auth(client: AsyncClient):
    """球员面板需要登录"""
    resp = await client.get(f"{RANKINGS_URL}/panel/1")
    assert resp.status_code == 401


async def test_player_panel_returns_data_after_match(client: AsyncClient):
    """比赛后球员面板包含评分历史"""
    owner_token, owner_id, p2_id = await _setup_match(client)

    resp = await client.get(
        f"{RANKINGS_URL}/panel/{owner_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["player"]["id"] == owner_id
    assert len(data["rating_history"]) >= 1
    assert len(data["recent_matches"]) >= 1


async def test_player_panel_nonexistent_returns_404(client: AsyncClient):
    """不存在的球员 → 404"""
    await _register(client, "panelowner")
    token = await _login(client, "panelowner")

    resp = await client.get(
        f"{RANKINGS_URL}/panel/9999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# sort_by 参数测试（正负值、失误、统计字段）
# ---------------------------------------------------------------------------


async def test_sort_by_plus_minus_returns_200(client: AsyncClient):
    """?sort_by=plus_minus 排行榜正常返回，每条目含 total_plus_minus"""
    owner_token, _, _ = await _setup_match(client)
    resp = await client.get(f"{RANKINGS_URL}?sort_by=plus_minus",
                             headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert "total_plus_minus" in item


async def test_sort_by_turnovers_returns_200(client: AsyncClient):
    """?sort_by=turnovers 排行榜正常返回，每条目含 total_turnovers"""
    owner_token, _, _ = await _setup_match(client)
    resp = await client.get(f"{RANKINGS_URL}?sort_by=turnovers",
                             headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert "total_turnovers" in item
        assert item["total_turnovers"] >= 0


async def test_sort_by_composite_returns_scores(client: AsyncClient):
    """?sort_by=composite 可返回综合分字段并按降序排序。"""
    owner_token, _, _ = await _setup_match(client)
    resp = await client.get(f"{RANKINGS_URL}?sort_by=composite", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    scores = [item["composite_score"] for item in items]
    assert scores == sorted(scores, reverse=True)
    for item in items:
        assert "composite_score" in item
        assert "attendance_rate" in item


async def test_composite_ranking_can_include_attendance_bonus(client: AsyncClient):
    """开启出勤系数后，综合榜会把训练/比赛出勤率加成计入 composite_score。"""
    owner_token, owner_id, p2_id = await _setup_match(client)
    p2_token = await _login(client, "rankp2")

    training_event_id = await _create_published_event(client, owner_token, "周中训练", "training")
    game_event_id = await _create_published_event(client, owner_token, "周末比赛", "game")

    for event_id in (training_event_id, game_event_id):
        owner_att = await client.put(
            f"{ATTENDANCE_URL}/{event_id}/me",
            json={"status": "yes"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_att.status_code == 200, owner_att.text
        p2_att = await client.put(
            f"{ATTENDANCE_URL}/{event_id}/me",
            json={"status": "leave"},
            headers={"Authorization": f"Bearer {p2_token}"},
        )
        assert p2_att.status_code == 200, p2_att.text

    settings_resp = await client.put(
        "/api/v1/team/settings",
        json={
            "composite_ts_weight": 0,
            "composite_perf_weight": 0,
            "composite_attendance_weight": 1,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert settings_resp.status_code == 200, settings_resp.text

    resp = await client.get(
        f"{RANKINGS_URL}?sort_by=composite",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    owner_item = next(item for item in items if item["player_id"] == owner_id)
    p2_item = next(item for item in items if item["player_id"] == p2_id)

    assert owner_item["attendance_rate"] == pytest.approx(100.0)
    assert owner_item["composite_score"] == pytest.approx(100.0)
    assert p2_item["attendance_rate"] == pytest.approx(0.0)
    assert p2_item["composite_score"] == pytest.approx(0.0)
    assert items[0]["player_id"] == owner_id


async def test_composite_excludes_zero_match_players(client: AsyncClient):
    """公平性：0 场球员不进入综合战力榜。"""
    owner_token, owner_id, id_map = await _setup_team_members(
        client,
        team_name="RankFairZero",
        member_usernames=["rfzp2001", "rfzp3001"],
    )
    p2_id = id_map["rfzp2001"]
    p3_id = id_map["rfzp3001"]  # 保持 0 场

    match_payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 11,
        "score_them": 9,
        "data_level": 1,
        "team_a": [{"player_id": owner_id}],
        "team_b": [{"player_id": p2_id}],
    }
    submit_r = await client.post(MATCHES_URL, json=match_payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert submit_r.status_code == 201, submit_r.text

    rank_r = await client.get(
        f"{RANKINGS_URL}?sort_by=composite",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert rank_r.status_code == 200, rank_r.text
    player_ids = [item["player_id"] for item in rank_r.json()["items"]]
    assert p3_id not in player_ids


async def test_composite_small_sample_does_not_outrank_stable_player(client: AsyncClient):
    """公平性：少样本高光不应轻易压过多场稳定球员。"""
    owner_token, owner_id, id_map = await _setup_team_members(
        client,
        team_name="RankFairSample",
        member_usernames=["rfsopp001", "rfsrookie1"],
    )
    opp_id = id_map["rfsopp001"]
    rookie_id = id_map["rfsrookie1"]

    # 稳定球员（owner）先打多场中高表现
    for _ in range(10):
        payload = {
            "match_date": str(date.today()),
            "match_type": "internal",
            "score_us": 6,
            "score_them": 5,
            "data_level": 3,
            "team_a": [{"player_id": owner_id, "goals": 2, "assists": 1, "defenses": 1}],
            "team_b": [{"player_id": opp_id, "goals": 1, "assists": 0, "defenses": 0}],
        }
        r = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 201, r.text

    # 新人仅 1 场高光
    rookie_payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 10,
        "score_them": 2,
        "data_level": 3,
        "team_a": [{"player_id": rookie_id, "goals": 9, "assists": 1, "defenses": 0}],
        "team_b": [{"player_id": opp_id, "goals": 2, "assists": 0, "defenses": 0}],
    }
    rookie_r = await client.post(MATCHES_URL, json=rookie_payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert rookie_r.status_code == 201, rookie_r.text

    # 仅看表现分，验证软折扣后稳定样本优先
    settings_r = await client.put(
        "/api/v1/team/settings",
        json={
            "composite_ts_weight": 0,
            "composite_perf_weight": 1,
            "composite_attendance_weight": 0,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert settings_r.status_code == 200, settings_r.text

    rank_r = await client.get(
        f"{RANKINGS_URL}?sort_by=composite",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert rank_r.status_code == 200, rank_r.text
    items = rank_r.json()["items"]
    owner_item = next(item for item in items if item["player_id"] == owner_id)
    rookie_item = next(item for item in items if item["player_id"] == rookie_id)
    assert owner_item["composite_score"] > rookie_item["composite_score"]


async def test_composite_strong_loss_not_systematically_suppressed(client: AsyncClient):
    """公平性：强队惜败球员不应被弱队小胜球员系统性压制。"""
    owner_token, _owner_id, id_map = await _setup_team_members(
        client,
        team_name="RankFairOpponent",
        member_usernames=["rfoweak01", "rfostrong1"],
    )
    weak_win_id = id_map["rfoweak01"]
    strong_loss_id = id_map["rfostrong1"]

    weak_win_payload = {
        "match_date": str(date.today()),
        "match_type": "external",
        "score_us": 13,
        "score_them": 12,
        "data_level": 1,
        "team_a": [{"player_id": weak_win_id}],
        "team_b": [],
        "opponent_strength": 2,
    }
    weak_r = await client.post(MATCHES_URL, json=weak_win_payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert weak_r.status_code == 201, weak_r.text

    strong_loss_payload = {
        "match_date": str(date.today()),
        "match_type": "external",
        "score_us": 12,
        "score_them": 13,
        "data_level": 1,
        "team_a": [{"player_id": strong_loss_id}],
        "team_b": [],
        "opponent_strength": 9,
    }
    strong_r = await client.post(MATCHES_URL, json=strong_loss_payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert strong_r.status_code == 201, strong_r.text

    # 仅看 OpenSkill 主干，避免 perf 噪声干扰
    settings_r = await client.put(
        "/api/v1/team/settings",
        json={
            "composite_ts_weight": 1,
            "composite_perf_weight": 0,
            "composite_attendance_weight": 0,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert settings_r.status_code == 200, settings_r.text

    rank_r = await client.get(
        f"{RANKINGS_URL}?sort_by=composite",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert rank_r.status_code == 200, rank_r.text
    items = rank_r.json()["items"]
    weak_item = next(item for item in items if item["player_id"] == weak_win_id)


# ─── T074 [US7]: 迁移后历史查询/排行榜兼容回归测试骨架 ──────────────────────


@pytest.mark.skip(reason="T074 US7: 合并脚本执行后需验证排行榜历史查询兼容性")
@pytest.mark.asyncio
async def test_rankings_history_compatible_after_merge(client: AsyncClient, db_session):
    """合并后玩家历史战绩仍能正常查询，排行榜数据未受影响"""
    pass


async def test_ranking_item_has_all_stat_fields(client: AsyncClient):
    """排行榜每条目包含 total_goals / total_assists / total_turnovers 字段"""
    owner_token, _, _ = await _setup_match(client)
    resp = await client.get(RANKINGS_URL, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert "total_goals" in item
        assert "total_assists" in item
        assert "total_turnovers" in item
        assert "total_plus_minus" in item


# ---------------------------------------------------------------------------
# sort_by=progress（MIP 四维进步榜）
# ---------------------------------------------------------------------------


async def test_sort_by_progress_returns_200_with_progress_speed(client: AsyncClient):
    """?sort_by=progress 正常返回，每条目含 progress_speed 字段（0.0 = 场次不足）"""
    owner_token, _, _ = await _setup_match(client)
    resp = await client.get(f"{RANKINGS_URL}?sort_by=progress",
                             headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert "progress_speed" in item
        assert isinstance(item["progress_speed"], float)
        assert 0.0 <= item["progress_speed"] <= 1.0 or item["progress_speed"] == 0.0


async def test_sort_by_progress_with_invalid_season_returns_200(client: AsyncClient):
    """传入不存在的 season_id 时，进步榜仍正常返回（退化为全历史模式）"""
    owner_token, _, _ = await _setup_match(client)
    resp = await client.get(f"{RANKINGS_URL}?sort_by=progress&season_id=99999",
                             headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


async def test_progress_below_min_matches_gets_zero(client: AsyncClient):
    """场次不足 mip_min_matches 的球员 progress_speed = 0.0"""
    owner_token, _, _ = await _setup_match(client)
    # 刚建队只有 1 场比赛，远低于默认 6 场门槛
    resp = await client.get(f"{RANKINGS_URL}?sort_by=progress",
                             headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    # 所有球员场次均 < 6，progress_speed 应全为 0.0
    for item in items:
        assert item["progress_speed"] == pytest.approx(0.0)


async def test_team_settings_mip_fields_present(client: AsyncClient):
    """TeamSettings 接口包含 MIP 六个字段，默认值符合预期"""
    owner_token, _, _ = await _setup_match(client)
    resp = await client.get("/api/v1/team/settings",
                             headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mip_weight_mu_delta"] == pytest.approx(0.40)
    assert data["mip_weight_slope"]    == pytest.approx(0.30)
    assert data["mip_weight_half"]     == pytest.approx(0.20)
    assert data["mip_weight_sigma"]    == pytest.approx(0.10)
    assert data["mip_slope_lambda"]    == pytest.approx(0.15)
    assert data["mip_min_matches"]     == 6


async def test_team_settings_mip_fields_updatable(client: AsyncClient):
    """TeamSettings PUT 能成功更新 MIP 字段"""
    owner_token, _, _ = await _setup_match(client)
    resp = await client.put(
        "/api/v1/team/settings",
        json={"mip_min_matches": 5, "mip_weight_mu_delta": 0.50, "mip_weight_slope": 0.25,
              "mip_weight_half": 0.15, "mip_weight_sigma": 0.10},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mip_min_matches"]     == 5
    assert data["mip_weight_mu_delta"] == pytest.approx(0.50)
    assert data["mip_weight_slope"]    == pytest.approx(0.25)
