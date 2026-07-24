"""分 line 管理集成测试（含内战同轮唯一性校验）"""
from datetime import date
from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
EVENTS_URL = "/api/v1/schedule-events"
LINES_URL = "/api/v1/schedule-lines"


async def _register(client: AsyncClient, username: str) -> None:
    r = await client.post(REG_URL, json={"username": username, "email": f"{username}@t.com", "password": "pw123456"})
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, username: str) -> str:
    r = await client.post(LOGIN_URL, data={"username": username, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _setup_team(client: AsyncClient):
    await _register(client, "lineowner")
    owner_token = await _login(client, "lineowner")
    r = await client.post("/api/v1/team/create", json={"team_name": "LineTeam"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    team_id = r.json()["team_id"]

    # 注册两名成员
    pids = []
    for i in range(1, 3):
        await _register(client, f"lineplayer{i}")
        tok = await _login(client, f"lineplayer{i}")
        await client.post("/api/v1/team/apply", json={"team_id": team_id},
                          headers={"Authorization": f"Bearer {tok}"})
        r_pend = await client.get("/api/v1/players?status=pending",
                                  headers={"Authorization": f"Bearer {owner_token}"})
        pid = next(p["id"] for p in r_pend.json() if p["username"] == f"lineplayer{i}")
        await client.patch(f"/api/v1/players/{pid}/status", json={"status": "active"},
                           headers={"Authorization": f"Bearer {owner_token}"})
        pids.append(pid)

    return owner_token, pids[0], pids[1]


async def _setup_team_with_players(client: AsyncClient, prefix: str, player_count: int):
    await _register(client, f"{prefix}owner")
    owner_token = await _login(client, f"{prefix}owner")
    r = await client.post(
        "/api/v1/team/create",
        json={"team_name": f"{prefix}Team"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    team_id = r.json()["team_id"]

    player_ids: list[int] = []
    for i in range(1, player_count + 1):
        username = f"{prefix}player{i}"
        await _register(client, username)
        tok = await _login(client, username)
        await client.post(
            "/api/v1/team/apply",
            json={"team_id": team_id},
            headers={"Authorization": f"Bearer {tok}"},
        )
        r_pend = await client.get(
            "/api/v1/players?status=pending",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        pid = next(p["id"] for p in r_pend.json() if p["username"] == username)
        await client.patch(
            f"/api/v1/players/{pid}/status",
            json={"status": "active"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        player_ids.append(pid)

    return owner_token, player_ids


async def _make_event(client: AsyncClient, owner_token: str, event_type: str = "game") -> int:
    today = date.today().isoformat()
    r = await client.post(EVENTS_URL,
                          json={"title": "分line测试", "event_type": event_type,
                                "start_date": today, "end_date": today},
                          headers={"Authorization": f"Bearer {owner_token}"})
    return r.json()["id"]


# ─── 认证 / 权限 ──────────────────────────────────────────────────────────────

async def test_create_division_requires_admin(client: AsyncClient):
    await _register(client, "lineanon")
    anon_token = await _login(client, "lineanon")
    r = await client.post(f"{LINES_URL}/1/division",
                          json={"division_method": "manual", "total_rounds": 1},
                          headers={"Authorization": f"Bearer {anon_token}"})
    assert r.status_code in (403, 404)


# ─── 分 line 方案 CRUD ───────────────────────────────────────────────────────

async def test_get_division_without_plan_returns_404(client: AsyncClient):
    owner_token, _, _ = await _setup_team(client)
    ev_id = await _make_event(client, owner_token)

    r = await client.get(f"{LINES_URL}/{ev_id}/division", headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 404


async def test_create_division_and_add_line(client: AsyncClient):
    owner_token, p1_id, p2_id = await _setup_team(client)
    ev_id = await _make_event(client, owner_token)

    # 初始化方案
    r = await client.post(f"{LINES_URL}/{ev_id}/division",
                          json={"division_method": "manual", "total_rounds": 1},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201, r.text
    div = r.json()
    assert div["total_rounds"] == 1

    # 添加 line
    r_line = await client.post(f"{LINES_URL}/{ev_id}/division/lines",
                               json={"line_name": "O Line", "line_type": "o_line",
                                     "round_number": 1, "order_index": 0},
                               headers={"Authorization": f"Bearer {owner_token}"})
    assert r_line.status_code == 201, r_line.text
    line = r_line.json()
    assert line["line_name"] == "O Line"


async def test_add_player_to_line(client: AsyncClient):
    owner_token, p1_id, _ = await _setup_team(client)
    ev_id = await _make_event(client, owner_token)

    await client.post(f"{LINES_URL}/{ev_id}/division",
                      json={"division_method": "manual", "total_rounds": 1},
                      headers={"Authorization": f"Bearer {owner_token}"})
    r_line = await client.post(f"{LINES_URL}/{ev_id}/division/lines",
                               json={"line_name": "Line A", "line_type": "line",
                                     "round_number": 1, "order_index": 0},
                               headers={"Authorization": f"Bearer {owner_token}"})
    line_id = r_line.json()["id"]

    r = await client.post(f"{LINES_URL}/{ev_id}/division/lines/{line_id}/players",
                          json={"player_id": p1_id},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201, r.text
    assert any(p["player_id"] == p1_id for p in r.json()["players"])


async def test_internal_same_round_duplicate_player(client: AsyncClient):
    """内战：同轮同一球员不能分配到两条 line → 400"""
    owner_token, p1_id, _ = await _setup_team(client)
    ev_id = await _make_event(client, owner_token, event_type="internal")

    await client.post(f"{LINES_URL}/{ev_id}/division",
                      json={"division_method": "manual", "total_rounds": 2},
                      headers={"Authorization": f"Bearer {owner_token}"})

    # 创建两条同轮 line
    r_line_a = await client.post(f"{LINES_URL}/{ev_id}/division/lines",
                                 json={"line_name": "Line A", "line_type": "line",
                                       "round_number": 1, "order_index": 0},
                                 headers={"Authorization": f"Bearer {owner_token}"})
    r_line_b = await client.post(f"{LINES_URL}/{ev_id}/division/lines",
                                 json={"line_name": "Line B", "line_type": "line",
                                       "round_number": 1, "order_index": 1},
                                 headers={"Authorization": f"Bearer {owner_token}"})
    line_a_id = r_line_a.json()["id"]
    line_b_id = r_line_b.json()["id"]

    await client.post(f"{LINES_URL}/{ev_id}/division/lines/{line_a_id}/players",
                      json={"player_id": p1_id},
                      headers={"Authorization": f"Bearer {owner_token}"})

    r_dup = await client.post(f"{LINES_URL}/{ev_id}/division/lines/{line_b_id}/players",
                              json={"player_id": p1_id},
                              headers={"Authorization": f"Bearer {owner_token}"})
    assert r_dup.status_code == 400, r_dup.text


async def test_game_same_round_duplicate_player_blocked(client: AsyncClient):
    """外战/训练：当前轮同一球员也只能出现在一条 line 中 → 400"""
    owner_token, p1_id, _ = await _setup_team(client)
    ev_id = await _make_event(client, owner_token, event_type="game")

    await client.post(f"{LINES_URL}/{ev_id}/division",
                      json={"division_method": "manual", "total_rounds": 1},
                      headers={"Authorization": f"Bearer {owner_token}"})

    r_line_a = await client.post(f"{LINES_URL}/{ev_id}/division/lines",
                                 json={"line_name": "O Line", "line_type": "o_line",
                                       "round_number": 1, "order_index": 0},
                                 headers={"Authorization": f"Bearer {owner_token}"})
    r_line_b = await client.post(f"{LINES_URL}/{ev_id}/division/lines",
                                 json={"line_name": "D Line", "line_type": "d_line",
                                       "round_number": 1, "order_index": 1},
                                 headers={"Authorization": f"Bearer {owner_token}"})
    line_a_id = r_line_a.json()["id"]
    line_b_id = r_line_b.json()["id"]

    first_add = await client.post(f"{LINES_URL}/{ev_id}/division/lines/{line_a_id}/players",
                                  json={"player_id": p1_id},
                                  headers={"Authorization": f"Bearer {owner_token}"})
    assert first_add.status_code == 201, first_add.text

    second_add = await client.post(f"{LINES_URL}/{ev_id}/division/lines/{line_b_id}/players",
                                   json={"player_id": p1_id},
                                   headers={"Authorization": f"Bearer {owner_token}"})
    assert second_add.status_code == 400, second_add.text


async def test_update_internal_division_rounds(client: AsyncClient):
    """内战分 line 轮数可以增加到 10 轮以内，供后续比赛录入选择具体轮次。"""
    owner_token, _, _ = await _setup_team(client)
    ev_id = await _make_event(client, owner_token, event_type="internal")

    created = await client.post(
        f"{LINES_URL}/{ev_id}/division",
        json={"division_method": "manual", "total_rounds": 2},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["total_rounds"] == 2

    updated = await client.put(
        f"{LINES_URL}/{ev_id}/division",
        json={"total_rounds": 5},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["total_rounds"] == 5


async def test_update_internal_division_rounds_cannot_reduce(client: AsyncClient):
    owner_token, _, _ = await _setup_team(client)
    ev_id = await _make_event(client, owner_token, event_type="internal")

    await client.post(
        f"{LINES_URL}/{ev_id}/division",
        json={"division_method": "manual", "total_rounds": 3},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    reduced = await client.put(
        f"{LINES_URL}/{ev_id}/division",
        json={"total_rounds": 2},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert reduced.status_code == 400


async def test_delete_internal_round_reorders_following_rounds(client: AsyncClient):
    owner_token, _, _ = await _setup_team(client)
    ev_id = await _make_event(client, owner_token, event_type="internal")

    created = await client.post(
        f"{LINES_URL}/{ev_id}/division",
        json={"division_method": "manual", "total_rounds": 3},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 201, created.text

    round2 = await client.post(
        f"{LINES_URL}/{ev_id}/division/lines",
        json={"line_name": "Round2 Line", "line_type": "line", "round_number": 2, "order_index": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    round3 = await client.post(
        f"{LINES_URL}/{ev_id}/division/lines",
        json={"line_name": "Round3 Line", "line_type": "line", "round_number": 3, "order_index": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert round2.status_code == 201, round2.text
    assert round3.status_code == 201, round3.text

    deleted = await client.delete(
        f"{LINES_URL}/{ev_id}/division/rounds/2",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["total_rounds"] == 2
    assert any(line["line_name"] == "Round3 Line" and line["round_number"] == 2 for line in deleted.json()["lines"])


async def test_save_and_apply_game_template(client: AsyncClient):
    """外战分 line 可保存为模板，并在后续重新套用。"""
    owner_token, p1_id, p2_id = await _setup_team(client)
    ev_id = await _make_event(client, owner_token, event_type="game")

    created = await client.post(
        f"{LINES_URL}/{ev_id}/division",
        json={"division_method": "manual", "total_rounds": 1},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 201, created.text

    o_line = await client.post(
        f"{LINES_URL}/{ev_id}/division/lines",
        json={"line_name": "主力 O", "line_type": "o_line", "round_number": 1, "order_index": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    d_line = await client.post(
        f"{LINES_URL}/{ev_id}/division/lines",
        json={"line_name": "主力 D", "line_type": "d_line", "round_number": 1, "order_index": 1},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert o_line.status_code == 201, o_line.text
    assert d_line.status_code == 201, d_line.text

    await client.post(
        f"{LINES_URL}/{ev_id}/division/lines/{o_line.json()['id']}/players",
        json={"player_id": p1_id},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    await client.post(
        f"{LINES_URL}/{ev_id}/division/lines/{d_line.json()['id']}/players",
        json={"player_id": p2_id},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    saved = await client.post(
        f"{LINES_URL}/{ev_id}/division/templates",
        json={"template_name": "外战主力版"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert saved.status_code == 201, saved.text
    template_id = saved.json()["id"]

    reset = await client.post(
        f"{LINES_URL}/{ev_id}/division",
        json={"division_method": "manual", "total_rounds": 1},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert reset.status_code == 201, reset.text
    temp_line = await client.post(
        f"{LINES_URL}/{ev_id}/division/lines",
        json={"line_name": "临时 Line", "line_type": "line", "round_number": 1, "order_index": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert temp_line.status_code == 201, temp_line.text
    await client.post(
        f"{LINES_URL}/{ev_id}/division/lines/{temp_line.json()['id']}/players",
        json={"player_id": p1_id},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    await client.post(
        f"{LINES_URL}/{ev_id}/division/lines/{temp_line.json()['id']}/players",
        json={"player_id": p2_id},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    applied = await client.post(
        f"{LINES_URL}/{ev_id}/division/templates/{template_id}/apply",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert applied.status_code == 200, applied.text
    div = applied.json()
    names = [line["line_name"] for line in div["lines"]]
    assert "主力 O" in names
    assert "主力 D" in names
    assert any(line["line_name"] == "主力 O" and any(p["player_id"] == p1_id for p in line["players"]) for line in div["lines"])
    assert any(line["line_name"] == "主力 D" and any(p["player_id"] == p2_id for p in line["players"]) for line in div["lines"])


async def test_template_limit_max_three(client: AsyncClient):
    """同一队伍同一类型最多保存 3 个模板。"""
    owner_token, _, _ = await _setup_team(client)
    ev_id = await _make_event(client, owner_token, event_type="training")

    await client.post(
        f"{LINES_URL}/{ev_id}/division",
        json={"division_method": "manual", "total_rounds": 1},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    base_line = await client.post(
        f"{LINES_URL}/{ev_id}/division/lines",
        json={"line_name": "训练一组", "line_type": "line", "round_number": 1, "order_index": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert base_line.status_code == 201, base_line.text

    for name in ["模板A", "模板B", "模板C"]:
        saved = await client.post(
            f"{LINES_URL}/{ev_id}/division/templates",
            json={"template_name": name},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert saved.status_code == 201, saved.text

    limited = await client.post(
        f"{LINES_URL}/{ev_id}/division/templates",
        json={"template_name": "模板D"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert limited.status_code == 400, limited.text


async def test_auto_assign_without_confirmed_players_rejected(client: AsyncClient):
    owner_token, _, _ = await _setup_team(client)
    ev_id = await _make_event(client, owner_token)

    await client.post(
        f"{LINES_URL}/{ev_id}/division",
        json={"division_method": "manual", "total_rounds": 1},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    auto_assign = await client.post(
        f"{LINES_URL}/{ev_id}/division/auto-assign",
        json={"method": "auto_balanced", "num_lines": 2, "round_number": 1},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert auto_assign.status_code == 400


async def test_auto_assign_balanced(client: AsyncClient):
    """自动均衡分配：2 条 line，球员分配到其中"""
    owner_token, p1_id, p2_id = await _setup_team(client)
    ev_id = await _make_event(client, owner_token)

    await client.post(f"{LINES_URL}/{ev_id}/division",
                      json={"division_method": "manual", "total_rounds": 1},
                      headers={"Authorization": f"Bearer {owner_token}"})

    # 设置出勤
    await client.put(f"/api/v1/schedule-attendance/{ev_id}/me",
                     json={"status": "yes"},
                     headers={"Authorization": f"Bearer {owner_token}"})

    r = await client.post(f"{LINES_URL}/{ev_id}/division/auto-assign",
                          json={"method": "auto_balanced", "num_lines": 2, "round_number": 1},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 200, r.text
    div = r.json()
    total_assigned = sum(len(l["players"]) for l in div["lines"] if l["round_number"] == 1)
    assert total_assigned >= 1  # 至少 owner 被分配


async def test_smart_external_lines_without_linked_event(client: AsyncClient):
    owner_token, player_ids = await _setup_team_with_players(client, prefix="smartline", player_count=8)

    r = await client.post(
        f"{LINES_URL}/smart-external-lines",
        json={"player_ids": player_ids, "recent_matches": 6},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["event_id"] is None
    assert payload["o_line"]["line_type"] == "o_line"
    assert payload["lines"][0]["line_type"] == "o_line"
    assert any(line["line_type"] == "d_line" for line in payload["lines"])
    assert all("chemistry_pairs" in line for line in payload["lines"])
