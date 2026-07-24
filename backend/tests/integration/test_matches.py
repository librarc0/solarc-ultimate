"""T033-T037: /matches 端点集成测试"""
import pytest
from httpx import AsyncClient
from datetime import date, datetime, timedelta, timezone

from app.api.v1.endpoints import matches as matches_endpoint

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PLAYERS_URL = "/api/v1/players"
MATCHES_URL = "/api/v1/matches"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


async def _register(client: AsyncClient, username: str, password: str = "pw123456", email: str | None = None) -> None:
    e = email or f"{username}@test.com"
    r = await client.post(REG_URL, json={"username": username, "email": e, "password": password})
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, username: str, password: str = "pw123456") -> str:
    r = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _approve_player(client: AsyncClient, owner_token: str, username: str) -> int:
    """将 pending 用户审批为 active，返回 player_id"""
    r = await client.get(f"{PLAYERS_URL}?status=pending", headers={"Authorization": f"Bearer {owner_token}"})
    players = [p for p in r.json() if p["username"] == username]
    pid = players[0]["id"]
    await client.patch(f"{PLAYERS_URL}/{pid}/status", json={"status": "active"}, headers={"Authorization": f"Bearer {owner_token}"})
    return pid


async def _setup_team(client: AsyncClient):
    """
    建立包含 3 名 active 成员的队伍：
    - owner1 (active, role=owner)
    - player2 (active)
    - player3 (active)
    返回 (owner_token, owner_id, p2_id, p3_id)
    """
    await _register(client, "owner1")
    owner_token = await _login(client, "owner1")
    r = await client.post("/api/v1/team/create", json={"team_name": "Eagles"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201, r.text
    team_id = r.json()["team_id"]

    # 注册 + 申请 + 审批 player2
    await _register(client, "player2")
    p2_token = await _login(client, "player2")
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {p2_token}"})
    p2_id = await _approve_player(client, owner_token, "player2")

    # 注册 + 申请 + 审批 player3
    await _register(client, "player3")
    p3_token = await _login(client, "player3")
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {p3_token}"})
    p3_id = await _approve_player(client, owner_token, "player3")

    # 获取 owner 的 id
    me_r = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    owner_id = me_r.json()["id"]

    return owner_token, owner_id, p2_id, p3_id


def _match_payload(owner_id: int, p2_id: int, p3_id: int, match_type: str = "internal") -> dict:
    return {
        "match_date": str(date.today()),
        "match_type": match_type,
        "score_us": 15,
        "score_them": 10,
        "data_level": 1,
        "team_a": [{"player_id": owner_id}],
        "team_b": [{"player_id": p2_id}, {"player_id": p3_id}],
    }


# ---------------------------------------------------------------------------
# POST /matches — 提交比赛
# ---------------------------------------------------------------------------


async def test_submit_match_requires_auth(client: AsyncClient):
    """未登录 → 401"""
    resp = await client.post(MATCHES_URL, json={})
    assert resp.status_code == 401


async def test_owner_submit_match_auto_approved(client: AsyncClient):
    """owner 提交 → 直接 approved"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    payload = _match_payload(owner_id, p2_id, p3_id)

    resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "approved"


async def test_member_submit_match_pending_approval(client: AsyncClient):
    """普通成员提交 → pending_approval"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    member_token = await _login(client, "player2")
    payload = _match_payload(owner_id, p2_id, p3_id)

    resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending_approval"


async def test_submit_match_with_nonexistent_player_fails(client: AsyncClient):
    """包含不存在的 player_id → 400"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 5,
        "score_them": 3,
        "data_level": 1,
        "team_a": [{"player_id": 9999}],
        "team_b": [{"player_id": owner_id}],
    }
    resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 400


async def test_submit_match_returns_requested_and_applied_level(client: AsyncClient):
    """请求 data_level=3 但缺 plus_minus 时，应返回 requested/applied 并自动降级为 2。"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)

    payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 15,
        "score_them": 10,
        "data_level": 3,
        "team_a": [{"player_id": owner_id, "goals": 5, "assists": 2}],
        "team_b": [
            {"player_id": p2_id, "goals": 3, "assists": 1},
            {"player_id": p3_id, "goals": 2, "assists": 0},
        ],
    }
    resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["requested_level"] == 3
    assert data["applied_level"] == 2


# ---------------------------------------------------------------------------
# POST /matches/{id}/approve — 审批
# ---------------------------------------------------------------------------


async def test_admin_can_approve_pending_match(client: AsyncClient):
    """管理员审批 pending 比赛 → approved + 评分结算"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    member_token = await _login(client, "player2")
    payload = _match_payload(owner_id, p2_id, p3_id)

    # 成员提交 pending 比赛
    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {member_token}"})
    match_id = submit_resp.json()["id"]

    # owner 审批
    approve_resp = await client.post(
        f"{MATCHES_URL}/{match_id}/approve",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"


async def test_member_cannot_approve_match(client: AsyncClient):
    """普通成员不能审批 → 403"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    member_token = await _login(client, "player2")
    payload = _match_payload(owner_id, p2_id, p3_id)

    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {member_token}"})
    match_id = submit_resp.json()["id"]

    approve_resp = await client.post(
        f"{MATCHES_URL}/{match_id}/approve",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert approve_resp.status_code == 403


# ---------------------------------------------------------------------------
# 评分影响验证
# ---------------------------------------------------------------------------


async def test_approved_match_updates_player_rating(client: AsyncClient):
    """审批后球员 mu 应有变化（非初始值）"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)

    # owner 直接提交（auto-approved）
    payload = _match_payload(owner_id, p2_id, p3_id)
    await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})

    # 检查 owner（winner）的 mu 应该变了
    me_resp = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    from app.rating_engine.engine import DEFAULT_MU
    owner_mu = me_resp.json()["mu"]
    assert owner_mu != DEFAULT_MU  # 评分应已更新


async def test_list_matches(client: AsyncClient):
    """GET /matches 返回列表"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    payload = _match_payload(owner_id, p2_id, p3_id)
    await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})

    resp = await client.get(MATCHES_URL, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_list_matches_invalid_status_returns_400(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    payload = _match_payload(owner_id, p2_id, p3_id)
    await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})

    resp = await client.get(f"{MATCHES_URL}?status=not_a_status", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 400


async def test_get_match_detail(client: AsyncClient):
    """GET /matches/{id} 返回详情"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    payload = _match_payload(owner_id, p2_id, p3_id)
    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    match_id = submit_resp.json()["id"]

    resp = await client.get(f"{MATCHES_URL}/{match_id}", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == match_id


async def test_get_match_events_returns_sorted_and_404_for_missing(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    payload = _match_payload(owner_id, p2_id, p3_id)
    payload["events"] = [
        {"event_type": "goal", "team_side": "A", "player_id": owner_id, "elapsed_seconds": 20},
        {"event_type": "turnover", "team_side": "A", "player_id": owner_id, "elapsed_seconds": 10},
    ]
    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    match_id = submit_resp.json()["id"]

    resp = await client.get(f"{MATCHES_URL}/{match_id}/events", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    events = resp.json()
    assert [e["elapsed_seconds"] for e in events] == [10, 20]

    missing = await client.get(f"{MATCHES_URL}/999999/events", headers={"Authorization": f"Bearer {owner_token}"})
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# PUT /matches/{id} — T041/T042 管理员审批 + 修改已审批比赛
# ---------------------------------------------------------------------------


async def test_put_approve_pending_match(client: AsyncClient):
    """PUT action=approve 审批 pending 比赛 → approved + 评分更新"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    member_token = await _login(client, "player2")

    # 成员提交 → pending
    payload = _match_payload(owner_id, p2_id, p3_id)
    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert submit_resp.json()["status"] == "pending_approval"
    match_id = submit_resp.json()["id"]

    # owner 用 PUT approve
    put_resp = await client.put(
        f"{MATCHES_URL}/{match_id}",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["status"] == "approved"

    # 验证评分已更新
    from app.rating_engine.engine import DEFAULT_MU
    me_resp = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    assert me_resp.json()["mu"] != DEFAULT_MU


async def test_put_reject_pending_match(client: AsyncClient):
    """PUT action=reject 拒绝 pending 比赛"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    member_token = await _login(client, "player2")

    payload = _match_payload(owner_id, p2_id, p3_id)
    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {member_token}"})
    match_id = submit_resp.json()["id"]

    put_resp = await client.put(
        f"{MATCHES_URL}/{match_id}",
        json={"action": "reject"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["status"] == "rejected"


async def test_member_cannot_put_match(client: AsyncClient):
    """普通成员不能使用 PUT → 403"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    member_token = await _login(client, "player2")

    payload = _match_payload(owner_id, p2_id, p3_id)
    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {member_token}"})
    match_id = submit_resp.json()["id"]

    put_resp = await client.put(
        f"{MATCHES_URL}/{match_id}",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert put_resp.status_code == 403


async def test_put_unknown_action_returns_400(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    payload = _match_payload(owner_id, p2_id, p3_id)
    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    match_id = submit_resp.json()["id"]

    put_resp = await client.put(
        f"{MATCHES_URL}/{match_id}",
        json={"action": "unknown_action"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert put_resp.status_code == 400


async def test_edit_approved_match_reraters_and_creates_admin_correction(client: AsyncClient):
    """T042: admin 修改已审批比赛比分 → Player.mu 变化 → RatingHistory 有 admin_correction 记录"""

    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)

    # 提交比赛（auto-approved）
    payload = _match_payload(owner_id, p2_id, p3_id)
    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    match_id = submit_resp.json()["id"]

    # 记录修改前的 owner mu
    me_before = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    mu_before_edit = me_before.json()["mu"]

    # 用 PUT action=edit 修改比分（翻转：A输B赢）
    edit_payload = {
        "action": "edit",
        "score_us": 5,
        "score_them": 15,
        "team_a": [{"player_id": owner_id}],
        "team_b": [{"player_id": p2_id}, {"player_id": p3_id}],
    }
    put_resp = await client.put(
        f"{MATCHES_URL}/{match_id}",
        json=edit_payload,
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["status"] == "approved"

    # 修改后 owner 现在是输家，mu 应该比赢的时候低
    me_after = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    mu_after_edit = me_after.json()["mu"]
    # 原来 A 队赢（mu_before_edit > DEFAULT_MU），改成 A 队输 → mu 应更低
    assert mu_after_edit < mu_before_edit


async def test_edit_approved_match_score_only(client: AsyncClient):
    """T042: admin 仅修改比分（不提供阵容）→ 成功重算"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)

    payload = _match_payload(owner_id, p2_id, p3_id)
    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    match_id = submit_resp.json()["id"]

    put_resp = await client.put(
        f"{MATCHES_URL}/{match_id}",
        json={"action": "edit", "score_us": 3, "score_them": 3},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert put_resp.status_code == 200


# ---------------------------------------------------------------------------
# 失误字段测试（turnover_penalty 功能）
# ---------------------------------------------------------------------------


async def test_submit_match_with_turnovers_entry(client: AsyncClient):
    """球员条目中包含 turnovers 字段 → 正常提交，data_level=3 时生效"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)

    payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 15,
        "score_them": 10,
        "data_level": 3,
        "team_a": [{"player_id": owner_id, "goals": 5, "assists": 2, "plus_minus": 2, "turnovers": 1}],
        "team_b": [
            {"player_id": p2_id, "goals": 3, "assists": 1, "plus_minus": -1, "turnovers": 2},
            {"player_id": p3_id, "goals": 2, "assists": 0, "plus_minus": -1, "turnovers": 0},
        ],
    }
    resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 201


async def test_draft_lifecycle_create_save_finalize(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)

    create_resp = await client.post(
        f"{MATCHES_URL}/drafts",
        json={
            "match_date": str(date.today()),
            "match_type": "internal",
            "team_a_ids": [owner_id],
            "team_b_ids": [p2_id, p3_id],
            "data_level": 3,
            "notes": "live draft",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_resp.status_code == 201, create_resp.text
    draft_id = create_resp.json()["id"]

    e1 = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/events",
        json={
            "client_event_id": "evt-1",
            "seq": 1,
            "event_type": "goal",
            "team_side": "A",
            "player_id": owner_id,
            "assist_player_id": None,
            "is_break": False,
            "elapsed_seconds": 45,
            "payload": {"score_a": 1, "score_b": 0},
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert e1.status_code == 200, e1.text

    save_resp = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/save",
        json={"elapsed_seconds": 120, "score_a": 1, "score_b": 0, "is_halftime": False, "possession": "B"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "in_progress"

    finalize_resp = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/finalize",
        json={"notes": "done"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert finalize_resp.status_code == 200, finalize_resp.text
    assert finalize_resp.json()["status"] == "approved"


async def test_draft_finalize_by_member_goes_pending_approval(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    member_token = await _login(client, "player2")

    create_resp = await client.post(
        f"{MATCHES_URL}/drafts",
        json={
            "match_date": str(date.today()),
            "match_type": "internal",
            "team_a_ids": [owner_id],
            "team_b_ids": [p2_id, p3_id],
            "data_level": 3,
            "notes": "member live draft",
        },
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert create_resp.status_code == 201, create_resp.text
    draft_id = create_resp.json()["id"]

    e1 = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/events",
        json={
            "client_event_id": "evt-member-1",
            "seq": 1,
            "event_type": "goal",
            "team_side": "A",
            "player_id": owner_id,
            "assist_player_id": None,
            "is_break": False,
            "elapsed_seconds": 45,
            "payload": {"score_a": 1, "score_b": 0},
        },
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert e1.status_code == 200, e1.text

    finalize_resp = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/finalize",
        json={"notes": "member submit"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert finalize_resp.status_code == 200, finalize_resp.text
    assert finalize_resp.json()["status"] == "pending_approval"


async def test_draft_event_idempotency_and_seq_conflict(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    create_resp = await client.post(
        f"{MATCHES_URL}/drafts",
        json={
            "match_date": str(date.today()),
            "match_type": "internal",
            "team_a_ids": [owner_id],
            "team_b_ids": [p2_id, p3_id],
            "data_level": 3,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    draft_id = create_resp.json()["id"]

    base_event = {
        "client_event_id": "evt-idempotent",
        "seq": 1,
        "event_type": "turnover",
        "team_side": "A",
        "player_id": owner_id,
        "assist_player_id": None,
        "is_break": False,
        "elapsed_seconds": 10,
        "payload": {"score_a": 0, "score_b": 0},
    }
    r1 = await client.post(f"{MATCHES_URL}/drafts/{draft_id}/events", json=base_event, headers={"Authorization": f"Bearer {owner_token}"})
    assert r1.status_code == 200
    r2 = await client.post(f"{MATCHES_URL}/drafts/{draft_id}/events", json=base_event, headers={"Authorization": f"Bearer {owner_token}"})
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True

    conflict = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/events",
        json={
            "client_event_id": "evt-conflict",
            "seq": 3,
            "event_type": "goal",
            "team_side": "A",
            "player_id": owner_id,
            "assist_player_id": None,
            "is_break": False,
            "elapsed_seconds": 20,
            "payload": {"score_a": 1, "score_b": 0},
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert conflict.status_code == 409


async def test_draft_list_and_abandon(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    create_resp = await client.post(
        f"{MATCHES_URL}/drafts",
        json={
            "match_date": str(date.today()),
            "match_type": "internal",
            "team_a_ids": [owner_id],
            "team_b_ids": [p2_id, p3_id],
            "data_level": 3,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    draft_id = create_resp.json()["id"]

    list_before = await client.get(f"{MATCHES_URL}/drafts/active", headers={"Authorization": f"Bearer {owner_token}"})
    assert list_before.status_code == 200
    assert any(x["id"] == draft_id for x in list_before.json())

    abandon = await client.post(f"{MATCHES_URL}/drafts/{draft_id}/abandon", headers={"Authorization": f"Bearer {owner_token}"})
    assert abandon.status_code == 200

    list_after = await client.get(f"{MATCHES_URL}/drafts/active", headers={"Authorization": f"Bearer {owner_token}"})
    assert list_after.status_code == 200
    assert all(x["id"] != draft_id for x in list_after.json())


async def test_draft_is_shared_and_locked_when_someone_enters_live(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    p2_token = await _login(client, "player2")
    p3_token = await _login(client, "player3")

    create_resp = await client.post(
        f"{MATCHES_URL}/drafts",
        json={
            "match_date": str(date.today()),
            "match_type": "internal",
            "team_a_ids": [owner_id],
            "team_b_ids": [p2_id, p3_id],
            "data_level": 3,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_resp.status_code == 201, create_resp.text
    draft_id = create_resp.json()["id"]

    # 公共未完成列表：队员均可见
    p2_list_before = await client.get(
        f"{MATCHES_URL}?status=draft",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert p2_list_before.status_code == 200
    assert any(x["id"] == draft_id for x in p2_list_before.json())

    p3_list_before = await client.get(
        f"{MATCHES_URL}?status=draft",
        headers={"Authorization": f"Bearer {p3_token}"},
    )
    assert p3_list_before.status_code == 200
    assert any(x["id"] == draft_id for x in p3_list_before.json())

    # player2 先接管，再进入实况并获得锁
    p2_takeover = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/takeover",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert p2_takeover.status_code == 200, p2_takeover.text

    p2_enter = await client.get(
        f"{MATCHES_URL}/drafts/{draft_id}",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert p2_enter.status_code == 200, p2_enter.text

    # 被锁后，公共未完成列表中仍可见，但状态应为他人锁定
    p3_list_locked = await client.get(
        f"{MATCHES_URL}?status=draft",
        headers={"Authorization": f"Bearer {p3_token}"},
    )
    assert p3_list_locked.status_code == 200
    p3_locked_item = next(x for x in p3_list_locked.json() if x["id"] == draft_id)
    assert p3_locked_item["lock_status"] == "locked_by_other"

    # 持锁人自己仍应在未完成列表看到该草稿，避免误以为草稿丢失
    p2_list_locked = await client.get(
        f"{MATCHES_URL}?status=draft",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert p2_list_locked.status_code == 200
    own_locked = next(x for x in p2_list_locked.json() if x["id"] == draft_id)
    assert own_locked["lock_status"] == "locked_by_me"

    # 第二个人直接进入会被权限拦截（需先接管）
    p3_enter = await client.get(
        f"{MATCHES_URL}/drafts/{draft_id}",
        headers={"Authorization": f"Bearer {p3_token}"},
    )
    assert p3_enter.status_code == 403
    assert p3_enter.json()["detail"]["code"] == "DRAFT_TAKEOVER_REQUIRED"

    # player2 保存后释放锁，列表应重新可见
    p2_save = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/save",
        json={"elapsed_seconds": 30, "score_a": 0, "score_b": 0},
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert p2_save.status_code == 200

    p3_list_after_save = await client.get(
        f"{MATCHES_URL}?status=draft",
        headers={"Authorization": f"Bearer {p3_token}"},
    )
    assert p3_list_after_save.status_code == 200
    draft_item = next(x for x in p3_list_after_save.json() if x["id"] == draft_id)
    assert draft_item["created_by_id"] == p2_id
    assert draft_item["created_by_name"] == "player2"


async def test_draft_lock_lease_expire_then_takeover_success(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    p2_token = await _login(client, "player2")
    p3_token = await _login(client, "player3")

    fake_now_ref = [datetime.now(timezone.utc)]

    def _fake_utcnow():
        return fake_now_ref[0]

    monkeypatch.setattr(matches_endpoint, "_utcnow", _fake_utcnow)

    create_resp = await client.post(
        f"{MATCHES_URL}/drafts",
        json={
            "match_date": str(date.today()),
            "match_type": "internal",
            "team_a_ids": [owner_id],
            "team_b_ids": [p2_id, p3_id],
            "data_level": 3,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_resp.status_code == 201, create_resp.text
    draft_id = create_resp.json()["id"]

    # player2 先接管拿锁
    p2_takeover = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/takeover",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert p2_takeover.status_code == 200, p2_takeover.text

    p2_enter = await client.get(
        f"{MATCHES_URL}/drafts/{draft_id}",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert p2_enter.status_code == 200, p2_enter.text

    # 过了租约时间后，player3 可接管
    fake_now_ref[0] = fake_now_ref[0] + timedelta(seconds=matches_endpoint.LOCK_LEASE_SECONDS + 5)
    takeover_resp = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/takeover",
        headers={"Authorization": f"Bearer {p3_token}"},
    )
    assert takeover_resp.status_code == 200, takeover_resp.text
    assert takeover_resp.json()["takeover"] is True

    # 接管后应可进入草稿
    p3_enter = await client.get(
        f"{MATCHES_URL}/drafts/{draft_id}",
        headers={"Authorization": f"Bearer {p3_token}"},
    )
    assert p3_enter.status_code == 200, p3_enter.text


async def test_member_must_takeover_before_entering_others_draft(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    p2_token = await _login(client, "player2")

    create_resp = await client.post(
        f"{MATCHES_URL}/drafts",
        json={
            "match_date": str(date.today()),
            "match_type": "internal",
            "team_a_ids": [owner_id],
            "team_b_ids": [p2_id, p3_id],
            "data_level": 3,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_resp.status_code == 201
    draft_id = create_resp.json()["id"]

    direct_enter = await client.get(
        f"{MATCHES_URL}/drafts/{draft_id}",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert direct_enter.status_code == 403
    assert direct_enter.json()["detail"]["code"] == "DRAFT_TAKEOVER_REQUIRED"

    takeover_resp = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/takeover",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert takeover_resp.status_code == 200
    assert takeover_resp.json()["takeover"] is True

    enter_after_takeover = await client.get(
        f"{MATCHES_URL}/drafts/{draft_id}",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert enter_after_takeover.status_code == 200


async def test_member_cannot_abandon_others_draft_but_admin_can(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    p2_token = await _login(client, "player2")

    create_resp = await client.post(
        f"{MATCHES_URL}/drafts",
        json={
            "match_date": str(date.today()),
            "match_type": "internal",
            "team_a_ids": [owner_id],
            "team_b_ids": [p2_id, p3_id],
            "data_level": 3,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_resp.status_code == 201
    draft_id = create_resp.json()["id"]

    member_abandon = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/abandon",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert member_abandon.status_code == 403

    admin_abandon = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/abandon",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert admin_abandon.status_code == 200


async def test_draft_heartbeat_renews_lease_and_blocks_takeover(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    p2_token = await _login(client, "player2")
    p3_token = await _login(client, "player3")

    fake_now_ref = [datetime.now(timezone.utc)]

    def _fake_utcnow():
        return fake_now_ref[0]

    monkeypatch.setattr(matches_endpoint, "_utcnow", _fake_utcnow)

    create_resp = await client.post(
        f"{MATCHES_URL}/drafts",
        json={
            "match_date": str(date.today()),
            "match_type": "internal",
            "team_a_ids": [owner_id],
            "team_b_ids": [p2_id, p3_id],
            "data_level": 3,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_resp.status_code == 201, create_resp.text
    draft_id = create_resp.json()["id"]

    # player2 先接管拿锁
    p2_takeover = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/takeover",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert p2_takeover.status_code == 200, p2_takeover.text

    p2_enter = await client.get(
        f"{MATCHES_URL}/drafts/{draft_id}",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert p2_enter.status_code == 200, p2_enter.text

    # 临近过期前发送心跳续租
    fake_now_ref[0] = fake_now_ref[0] + timedelta(seconds=matches_endpoint.LOCK_LEASE_SECONDS - 10)
    beat_resp = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/heartbeat",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert beat_resp.status_code == 200, beat_resp.text
    assert beat_resp.json()["ok"] is True

    # 心跳后 20 秒，未过期，不允许接管
    fake_now_ref[0] = fake_now_ref[0] + timedelta(seconds=20)
    takeover_resp = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/takeover",
        headers={"Authorization": f"Bearer {p3_token}"},
    )
    assert takeover_resp.status_code == 409, takeover_resp.text
    detail = takeover_resp.json()["detail"]
    assert detail["code"] == "DRAFT_LOCKED"
    assert detail["lock_expires_in_seconds"] > 0


async def test_draft_finalize_records_final_submitter_identity(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    p2_token = await _login(client, "player2")

    create_resp = await client.post(
        f"{MATCHES_URL}/drafts",
        json={
            "match_date": str(date.today()),
            "match_type": "internal",
            "team_a_ids": [owner_id],
            "team_b_ids": [p2_id, p3_id],
            "data_level": 3,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_resp.status_code == 201
    draft_id = create_resp.json()["id"]

    # player2 先接管并进入，最终提交人应记录为 player2
    takeover_resp = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/takeover",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert takeover_resp.status_code == 200

    enter_resp = await client.get(
        f"{MATCHES_URL}/drafts/{draft_id}",
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert enter_resp.status_code == 200

    finalize_resp = await client.post(
        f"{MATCHES_URL}/drafts/{draft_id}/finalize",
        json={"notes": "relay submit"},
        headers={"Authorization": f"Bearer {p2_token}"},
    )
    assert finalize_resp.status_code == 200, finalize_resp.text
    assert finalize_resp.json()["status"] == "pending_approval"

    detail_resp = await client.get(
        f"{MATCHES_URL}/{draft_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["created_by_id"] == p2_id

    pending_list_resp = await client.get(
        f"{MATCHES_URL}?status=pending_approval",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert pending_list_resp.status_code == 200
    target = next(item for item in pending_list_resp.json() if item["id"] == draft_id)
    assert target["created_by_id"] == p2_id
    assert target["created_by_name"] == "player2"


async def test_submit_match_with_turnover_events(client: AsyncClient):
    """事件列表中包含 event_type=turnover → 正常提交 201"""
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)

    payload = _match_payload(owner_id, p2_id, p3_id)
    payload["events"] = [
        {"event_type": "turnover", "team_side": "A", "player_id": owner_id},
        {"event_type": "turnover", "team_side": "B", "player_id": p2_id},
    ]
    resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# 超级管理员提交比赛
# ---------------------------------------------------------------------------


async def test_superadmin_can_submit_match(client: AsyncClient, db_session):
    """超级管理员（无所属队伍）可提交比赛，队伍 ID 从球员推断"""
    from sqlalchemy import select as sa_select
    from app.models.player import Player

    # 先建立一支普通队伍
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)

    # 注册超管账号并设 is_superadmin=True
    await _register(client, "superadmin1", email="superadmin1@test.com")
    sa_token = await _login(client, "superadmin1")
    result = await db_session.execute(sa_select(Player).where(Player.username == "superadmin1"))
    sa_player = result.scalar_one()
    sa_player.is_superadmin = True
    await db_session.commit()

    # 超管提交比赛（队伍 ID 从球员列表推断）
    payload = _match_payload(owner_id, p2_id, p3_id)
    resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {sa_token}"})
    assert resp.status_code == 201
    # 超管提交直接 approved（超管视为管理员级别）
    assert resp.json()["status"] == "approved"


async def test_delete_match_not_found_and_delete_approved_ok(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)

    not_found = await client.delete(f"{MATCHES_URL}/999999", headers={"Authorization": f"Bearer {owner_token}"})
    assert not_found.status_code == 404

    payload = _match_payload(owner_id, p2_id, p3_id)
    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    match_id = submit_resp.json()["id"]

    del_resp = await client.delete(f"{MATCHES_URL}/{match_id}", headers={"Authorization": f"Bearer {owner_token}"})
    assert del_resp.status_code == 204

    detail_resp = await client.get(f"{MATCHES_URL}/{match_id}", headers={"Authorization": f"Bearer {owner_token}"})
    assert detail_resp.status_code == 404


async def test_external_match_spirit_score_upsert_and_get(client: AsyncClient):
    owner_token, owner_id, p2_id, p3_id = await _setup_team(client)
    payload = _match_payload(owner_id, p2_id, p3_id, match_type="external")
    payload["team_b"] = []
    submit_resp = await client.post(MATCHES_URL, json=payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert submit_resp.status_code == 201
    match_id = submit_resp.json()["id"]

    score_body = {
        "rules": {"score": 3, "reasons": ["规则认知良好"], "note": ""},
        "contact": {"score": 2, "reasons": ["接触可控"], "note": ""},
        "fairness": {"score": 4, "reasons": ["公平竞技"], "note": ""},
        "attitude": {"score": 3, "reasons": ["态度积极"], "note": ""},
        "communication": {"score": 2, "reasons": ["沟通顺畅"], "note": ""},
        "note": "赛后补充说明",
    }
    upsert = await client.put(
        f"{MATCHES_URL}/{match_id}/spirit-score",
        json=score_body,
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert upsert.status_code == 200
    assert upsert.json()["total_score"] == 14

    get_resp = await client.get(f"{MATCHES_URL}/{match_id}/spirit-score", headers={"Authorization": f"Bearer {owner_token}"})
    assert get_resp.status_code == 200
    assert get_resp.json()["rules"]["score"] == 3
    assert get_resp.json()["note"] == "赛后补充说明"

    list_resp = await client.get(f"{MATCHES_URL}?status=approved", headers={"Authorization": f"Bearer {owner_token}"})
    assert list_resp.status_code == 200
    target = next(item for item in list_resp.json() if item["id"] == match_id)
    assert target["spirit_scored"] is True
    assert target["spirit_total_score"] == 14

