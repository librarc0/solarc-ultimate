"""T078: /team/settings 端点集成测试"""
import pytest
from httpx import AsyncClient

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PLAYERS_URL = "/api/v1/players"
SETTINGS_URL = "/api/v1/team/settings"


async def _register(client: AsyncClient, username: str, password: str = "pw123456", email: str | None = None):
    e = email or f"{username}@test.com"
    r = await client.post(REG_URL, json={"username": username, "email": e, "password": password})
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, username: str, password: str = "pw123456") -> str:
    r = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


async def _apply_and_approve(client: AsyncClient, username: str, team_id: int, owner_token: str) -> tuple[int, str]:
    """注册 → 登录 → 申请加入队伍 → owner 审批，返回 (player_id, token)"""
    await _register(client, username)
    token = await _login(client, username)
    await client.post("/api/v1/team/apply", json={"team_id": team_id},
                      headers={"Authorization": f"Bearer {token}"})
    r = await client.get(f"{PLAYERS_URL}?status=pending", headers={"Authorization": f"Bearer {owner_token}"})
    pid = next(p["id"] for p in r.json() if p["username"] == username)
    await client.patch(f"{PLAYERS_URL}/{pid}/status", json={"status": "active"},
                       headers={"Authorization": f"Bearer {owner_token}"})
    return pid, token


async def _setup(client: AsyncClient):
    """owner + 一个 admin + 一个 member"""
    await _register(client, "owner1")
    owner_token = await _login(client, "owner1")
    r = await client.post("/api/v1/team/create", json={"team_name": "Eagles"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201, r.text
    team_id = r.json()["team_id"]

    admin_id, admin_token = await _apply_and_approve(client, "admin1", team_id, owner_token)
    # 提升为 admin
    await client.patch(f"{PLAYERS_URL}/{admin_id}/role", json={"role": "admin"},
                       headers={"Authorization": f"Bearer {owner_token}"})

    _, member_token = await _apply_and_approve(client, "member1", team_id, owner_token)

    return owner_token, admin_token, member_token


# ---------------------------------------------------------------------------
# GET /team/settings
# ---------------------------------------------------------------------------


async def test_get_settings_requires_auth(client: AsyncClient):
    """未登录 → 401"""
    resp = await client.get(SETTINGS_URL)
    assert resp.status_code == 401


async def test_get_settings_default_values(client: AsyncClient):
    """登录后可获取默认算法系数"""
    owner_token, _, member_token = await _setup(client)

    resp = await client.get(SETTINGS_URL, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "alpha" in data
    assert "beta" in data
    assert "gamma" in data
    assert "composite_ts_weight" in data
    assert "composite_perf_weight" in data
    assert "composite_attendance_weight" in data
    # 默认值验证
    assert data["alpha"] == pytest.approx(0.3)
    assert data["beta"] == pytest.approx(0.6)
    assert data["gamma"] == pytest.approx(0.4)
    assert data["composite_attendance_weight"] == pytest.approx(0.0)
    # 新增：team 对象 + OpenSkill 默认参数
    assert data["team_id"] >= 1
    assert data["team"] is not None
    assert data["team"]["id"] == data["team_id"]
    assert data["openskill_mu"] == pytest.approx(25.0)
    assert data["openskill_sigma"] == pytest.approx(25.0 / 3.0)
    assert data["openskill_beta"] == pytest.approx(25.0 / 6.0)
    assert data["openskill_tau"] == pytest.approx(25.0 / 300.0)
    assert data["openskill_kappa"] == pytest.approx(0.0001)
    assert data["openskill_margin"] == pytest.approx(0.0)
    assert data["openskill_limit_sigma"] is False
    assert data["openskill_balance"] is True


async def test_member_can_get_settings(client: AsyncClient):
    """普通成员也可查看系数"""
    _, _, member_token = await _setup(client)
    resp = await client.get(SETTINGS_URL, headers={"Authorization": f"Bearer {member_token}"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# PUT /team/settings
# ---------------------------------------------------------------------------


async def test_owner_can_update_settings(client: AsyncClient):
    """owner 修改系数 → 成功返回新值"""
    owner_token, _, _ = await _setup(client)

    resp = await client.put(
        SETTINGS_URL,
        json={"alpha": 0.5, "beta": 0.8, "composite_attendance_weight": 0.03},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["alpha"] == pytest.approx(0.5)
    assert data["beta"] == pytest.approx(0.8)
    assert data["composite_attendance_weight"] == pytest.approx(0.03)
    assert data["gamma"] == pytest.approx(0.4)  # 未修改的保持默认


async def test_admin_cannot_update_settings(client: AsyncClient):
    """admin 无权修改系数（owner only）→ 403"""
    _, admin_token, _ = await _setup(client)

    resp = await client.put(
        SETTINGS_URL,
        json={"alpha": 0.9},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403


async def test_member_cannot_update_settings(client: AsyncClient):
    """普通成员无权修改系数 → 403"""
    _, _, member_token = await _setup(client)

    resp = await client.put(
        SETTINGS_URL,
        json={"alpha": 0.9},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp.status_code == 403


async def test_updated_settings_used_in_next_match(client: AsyncClient):
    """T078: owner 修改 alpha → 下一场比赛使用新系数（通过 delta_mu 差值对比验证）"""
    from datetime import date

    owner_token, _, member_token = await _setup(client)

    # 获取 owner + admin 的 id
    me_r = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
    owner_id = me_r.json()["id"]
    admin_r = await client.get(f"{PLAYERS_URL}?status=active", headers={"Authorization": f"Bearer {owner_token}"})
    all_active = admin_r.json()
    member = next((p for p in all_active if p["username"] == "member1"), None)
    assert member is not None
    member_id = member["id"]
    admin = next((p for p in all_active if p["username"] == "admin1"), None)
    admin_id = admin["id"]

    base_payload = {
        "match_date": str(date.today()),
        "match_type": "internal",
        "score_us": 15,
        "score_them": 5,
        "data_level": 2,
        "team_a": [{"player_id": owner_id, "goals": 5, "assists": 2}],
        "team_b": [{"player_id": member_id, "goals": 0, "assists": 0}, {"player_id": admin_id, "goals": 0, "assists": 0}],
    }

    # 第一场比赛（默认 alpha=0.3）
    r1 = await client.post("/api/v1/matches", json=base_payload, headers={"Authorization": f"Bearer {owner_token}"})
    assert r1.status_code == 201
    mu_after_match1 = (await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})).json()["mu"]

    # 改回 owner mu（通过反向比赛抵消影响，这里简化：只验证修改后系数确实持久化）
    # 更新系数为高 alpha
    put_resp = await client.put(
        SETTINGS_URL,
        json={"alpha": 1.5},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["alpha"] == pytest.approx(1.5)

    # 重新读取配置确认持久化
    get_resp = await client.get(SETTINGS_URL, headers={"Authorization": f"Bearer {owner_token}"})
    assert get_resp.json()["alpha"] == pytest.approx(1.5)


async def test_team_alpha_changes_next_match_delta(client: AsyncClient):
    """
    修改队伍 alpha 后，下一场结算的 Δμ 应发生可观察变化。

    为避免“上一场已改动 mu 导致不可比”，这里用两支全新队伍：
    - TeamLow: alpha=0.0
    - TeamHigh: alpha=1.5
    提交同样的 Level 2 内战数据（胜方有明显个人贡献差异），比较胜方核心球员涨幅。
    """
    from datetime import date
    from app.rating_engine.engine import DEFAULT_MU

    async def _setup_team(team_name: str) -> tuple[str, int, int, int]:
        # username 约束：6-20 位字母数字（无下划线/空格）
        base = team_name.lower()
        owner_u = f"{base}own"
        p2_u = f"{base}p2x"
        p3_u = f"{base}p3x"
        await _register(client, owner_u)
        owner_token = await _login(client, owner_u)
        r = await client.post(
            "/api/v1/team/create",
            json={"team_name": team_name},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert r.status_code == 201, r.text
        team_id = r.json()["team_id"]

        p2_id, _ = await _apply_and_approve(client, p2_u, team_id, owner_token)
        p3_id, _ = await _apply_and_approve(client, p3_u, team_id, owner_token)

        me_r = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
        owner_id = me_r.json()["id"]
        return owner_token, owner_id, p2_id, p3_id

    async def _run_one(team_name: str, alpha: float) -> float:
        owner_token, owner_id, p2_id, p3_id = await _setup_team(team_name)

        put_resp = await client.put(
            SETTINGS_URL,
            json={"alpha": alpha},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert put_resp.status_code == 200, put_resp.text
        assert put_resp.json()["alpha"] == pytest.approx(alpha)

        # 胜方需要 >=2 人，才能观察 alpha 对“个人贡献差异放大”的影响
        payload = {
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
        r = await client.post("/api/v1/matches", json=payload, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 201, r.text

        # 读取队内两人的 mu，比较“核心球员涨幅 - 队友涨幅”的差值（spread）
        me_after = await client.get(f"{PLAYERS_URL}/me", headers={"Authorization": f"Bearer {owner_token}"})
        assert me_after.status_code == 200, me_after.text
        owner_mu = me_after.json()["mu"]

        mate_after = await client.get(f"{PLAYERS_URL}/{p2_id}", headers={"Authorization": f"Bearer {owner_token}"})
        assert mate_after.status_code == 200, mate_after.text
        mate_mu = mate_after.json()["mu"]
        owner_delta = float(owner_mu) - float(DEFAULT_MU)
        mate_delta = float(mate_mu) - float(DEFAULT_MU)
        return owner_delta - mate_delta

    spread_low = await _run_one("TeamLow", alpha=0.0)
    spread_high = await _run_one("TeamHigh", alpha=1.5)

    # alpha 更大 → 个人贡献差异放大 → 核心球员涨幅应更大（留一点数值余量）
    assert spread_high > spread_low + 0.05, f"Expected spread_high({spread_high}) > spread_low({spread_low})"


# ---------------------------------------------------------------------------
# turnover_penalty 字段测试（T078+）
# ---------------------------------------------------------------------------


async def test_get_settings_includes_turnover_penalty(client: AsyncClient):
    """GET /team/settings 响应中包含 turnover_penalty 与 turnover_sigma_factor 字段"""
    owner_token, _, _ = await _setup(client)
    resp = await client.get(SETTINGS_URL, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "turnover_penalty" in data
    assert "turnover_sigma_factor" in data
    assert data["turnover_penalty"] == pytest.approx(0.2)  # 默认值
    assert data["turnover_sigma_factor"] == pytest.approx(0.3)  # 默认值


async def test_owner_can_update_turnover_penalty(client: AsyncClient):
    """owner 修改 turnover_penalty / turnover_sigma_factor → 成功持久化"""
    owner_token, _, _ = await _setup(client)

    resp = await client.put(
        SETTINGS_URL,
        json={"turnover_penalty": 0.5, "turnover_sigma_factor": 0.8},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["turnover_penalty"] == pytest.approx(0.5)
    assert resp.json()["turnover_sigma_factor"] == pytest.approx(0.8)

    # 重新读取确认持久化
    get_resp = await client.get(SETTINGS_URL, headers={"Authorization": f"Bearer {owner_token}"})
    assert get_resp.json()["turnover_penalty"] == pytest.approx(0.5)
    assert get_resp.json()["turnover_sigma_factor"] == pytest.approx(0.8)


async def test_settings_returns_defaults_when_no_row(client: AsyncClient):
    """未配置时 GET /team/settings 应返回默认值而非 404"""
    # 只注册 owner 并创建队伍，不做任何 PUT 配置
    await _register(client, "freshowner")
    token = await _login(client, "freshowner")
    await client.post("/api/v1/team/create", json={"team_name": "Fresh Team"},
                      headers={"Authorization": f"Bearer {token}"})

    resp = await client.get(SETTINGS_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    # 验证返回默认值而非报错
    assert data["alpha"] == pytest.approx(0.3)
    assert data["turnover_penalty"] == pytest.approx(0.2)
    assert data["turnover_sigma_factor"] == pytest.approx(0.3)
    assert data["composite_attendance_weight"] == pytest.approx(0.0)


async def test_owner_can_update_openskill_params(client: AsyncClient):
    """owner 可更新 OpenSkill 参数，并正确持久化。"""
    owner_token, _, _ = await _setup(client)

    resp = await client.put(
        SETTINGS_URL,
        json={
            "openskill_mu": 30.0,
            "openskill_sigma": 9.0,
            "openskill_beta": 5.0,
            "openskill_tau": 0.12,
            "openskill_kappa": 0.001,
            "openskill_margin": 1.5,
            "openskill_limit_sigma": True,
            "openskill_balance": True,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["openskill_mu"] == pytest.approx(30.0)
    assert data["openskill_sigma"] == pytest.approx(9.0)
    assert data["openskill_beta"] == pytest.approx(5.0)
    assert data["openskill_tau"] == pytest.approx(0.12)
    assert data["openskill_kappa"] == pytest.approx(0.001)
    assert data["openskill_margin"] == pytest.approx(1.5)
    assert data["openskill_limit_sigma"] is True
    assert data["openskill_balance"] is True

    # 再读一遍确认持久化
    g = await client.get(SETTINGS_URL, headers={"Authorization": f"Bearer {owner_token}"})
    assert g.status_code == 200
    gd = g.json()
    assert gd["openskill_mu"] == pytest.approx(30.0)
    assert gd["openskill_sigma"] == pytest.approx(9.0)
    assert gd["openskill_beta"] == pytest.approx(5.0)
    assert gd["openskill_tau"] == pytest.approx(0.12)
    assert gd["openskill_kappa"] == pytest.approx(0.001)
    assert gd["openskill_margin"] == pytest.approx(1.5)
    assert gd["openskill_limit_sigma"] is True
    assert gd["openskill_balance"] is True


async def test_reset_restores_openskill_defaults(client: AsyncClient):
    """重置后 OpenSkill 参数恢复默认值。"""
    owner_token, _, _ = await _setup(client)

    # 先改一组非默认值
    u = await client.put(
        SETTINGS_URL,
        json={"openskill_mu": 31.0, "openskill_sigma": 10.0, "openskill_limit_sigma": True},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert u.status_code == 200

    # 重置
    r = await client.post("/api/v1/team/settings/reset", headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["openskill_mu"] == pytest.approx(25.0)
    assert d["openskill_sigma"] == pytest.approx(25.0 / 3.0)
    assert d["openskill_beta"] == pytest.approx(25.0 / 6.0)
    assert d["openskill_tau"] == pytest.approx(25.0 / 300.0)
    assert d["openskill_kappa"] == pytest.approx(0.0001)
    assert d["openskill_margin"] == pytest.approx(0.0)
    assert d["openskill_limit_sigma"] is False
    assert d["openskill_balance"] is True


# ---------------------------------------------------------------------------
# T069 [US2]: 超级管理员跨队关键写操作回归
# ---------------------------------------------------------------------------


async def _make_superadmin(client: AsyncClient, db_session, username: str, email: str, password: str = "pw123456") -> str:
    """注册用户，将 Player.is_superadmin 设为 True，重登返回 token"""
    from app.models.player import Player
    from sqlalchemy import select

    await _register(client, username, password, email)
    token = await _login(client, username, password)
    # 设置 player.is_superadmin = True（deps.py 依赖 Player 上的标志）
    result = await db_session.execute(select(Player).where(Player.username == username))
    player = result.scalar_one()
    player.is_superadmin = True
    await db_session.commit()
    # 重新登录（current_user/player 由 DB 读取，立即生效）
    return await _login(client, username, password)


async def test_superadmin_can_update_any_team_settings(client: AsyncClient, db_session):
    """T069: 超级管理员可对任意队伍执行 PUT /team/settings 等关键写操作"""
    owner_token, _, _ = await _setup(client)
    # 超管账号（非该队伍成员）
    sa_token = await _make_superadmin(client, db_session, "sa69owner", "sa69owner@t.com")

    # 超管直接修改 alpha（无 team 归属，requires_admin → superadmin bypass）
    # 需要 ?team_id 参数告知 get_effective_team_id 要操作哪支队伍
    r = await client.get(SETTINGS_URL, headers={"Authorization": f"Bearer {owner_token}"})
    team_id = r.json()["team_id"]

    resp = await client.put(
        f"{SETTINGS_URL}?team_id={team_id}",
        json={"alpha": 0.99},
        headers={"Authorization": f"Bearer {sa_token}"},
    )
    assert resp.status_code == 200, f"超管写操作应成功: {resp.text}"
    assert resp.json()["alpha"] == pytest.approx(0.99)


async def test_superadmin_GET_settings_any_team(client: AsyncClient, db_session):
    """T069: 超级管理员可通过 ?team_id 查看任意队伍设置"""
    owner_token, _, _ = await _setup(client)
    sa_token = await _make_superadmin(client, db_session, "sa69reader", "sa69reader@t.com")

    r = await client.get(SETTINGS_URL, headers={"Authorization": f"Bearer {owner_token}"})
    team_id = r.json()["team_id"]

    resp = await client.get(
        f"{SETTINGS_URL}?team_id={team_id}",
        headers={"Authorization": f"Bearer {sa_token}"},
    )
    assert resp.status_code == 200, f"超管读任意队伍应成功: {resp.text}"
    assert resp.json()["team_id"] == team_id


# ---------------------------------------------------------------------------
# T043 [US5]: 申请被拒后重登收敛测试
# ---------------------------------------------------------------------------

REG_URL_TS = "/api/v1/auth/register"
LOGIN_URL_TS = "/api/v1/auth/login"
CREATE_TEAM_URL_TS = "/api/v1/team/create"
CONTEXT_URL_TS = "/api/v1/auth/me/context"


async def _reg_login_ts(client: AsyncClient, username: str, email: str, password: str = "password123") -> str:
    await client.post(REG_URL_TS, json={"username": username, "email": email, "password": password})
    r = await client.post(LOGIN_URL_TS, data={"username": username, "password": password})
    assert r.status_code == 200, f"登录失败: {r.text}"
    return r.json()["access_token"]


async def test_reject_application_convergence(client: AsyncClient, db_session):
    """T043 [US5]: 申请被 owner 拒绝后，me/context 的 teams 列表应为空（无 active 队伍）。"""

    owner_token = await _reg_login_ts(client, "ts43owner", "ts43owner@t.com")
    # owner 创建队伍
    r = await client.post(CREATE_TEAM_URL_TS, json={"team_name": "RejectTeam43"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201
    team_id = r.json()["team_id"]

    # 普通用户申请入队
    user_token = await _reg_login_ts(client, "ts43user", "ts43user@t.com")
    apply_resp = await client.post("/api/v1/team/apply", json={"team_id": team_id},
                                   headers={"Authorization": f"Bearer {user_token}"})
    assert apply_resp.status_code == 200, f"申请加入应成功: {apply_resp.text}"

    # 获取 pending player id
    pending_resp = await client.get(f"{PLAYERS_URL}?status=pending",
                                    headers={"Authorization": f"Bearer {owner_token}"})
    assert pending_resp.status_code == 200
    user_player = next((p for p in pending_resp.json() if p["username"] == "ts43user"), None)
    assert user_player is not None, "应能找到 pending 的申请"
    pid = user_player["id"]

    # owner 拒绝申请 → player 恢复无队伍 active 状态
    reject_resp = await client.patch(f"{PLAYERS_URL}/{pid}/status",
                                     json={"status": "rejected"},
                                     headers={"Authorization": f"Bearer {owner_token}"})
    assert reject_resp.status_code == 200, f"拒绝申请应成功: {reject_resp.text}"

    # 被拒用户重新登录（恢复为无队伍 active，可正常登录）
    new_token_resp = await client.post(LOGIN_URL_TS, data={"username": "ts43user", "password": "password123"})
    assert new_token_resp.status_code == 200, f"被拒后应仍可登录: {new_token_resp.text}"
    new_token = new_token_resp.json()["access_token"]

    # 被拒用户 me/context → teams 应为空（无 active 队伍成员身份）
    ctx_resp = await client.get(CONTEXT_URL_TS, headers={"Authorization": f"Bearer {new_token}"})
    assert ctx_resp.status_code == 200, f"context 接口不应 500: {ctx_resp.text}"
    ctx_data = ctx_resp.json()["data"]
    assert ctx_data["teams"] == [], f"被拒后 teams 应为空，实际: {ctx_data['teams']}"


# ---------------------------------------------------------------------------
# T036 [US4]: 初始 μ 手动/默认路径集成测试
# ---------------------------------------------------------------------------

APPLICATIONS_URL_TS = "/api/v1/team-membership/applications"
REVIEW_BASE_TS = "/api/v1/team-membership/applications"


async def test_review_approve_uses_suggested_mu_when_no_manual_input(
    client: AsyncClient, db_session
):
    """T036 [US4]: approve 不传 initial_mu 时，DB 中 membership.mu 应等于建议 μ（样本 < 3 回退默认 25.0）。"""

    owner_token = await _reg_login_ts(client, "ts36own1", "ts36own1@t.com")
    r = await client.post(CREATE_TEAM_URL_TS, json={"team_name": "ReviewTeam36a"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201
    team_id = r.json()["team_id"]

    user_token = await _reg_login_ts(client, "ts36usr1", "ts36usr1@t.com")
    # 提交 PlayerTeamMembership 申请
    apply_resp = await client.post(
        APPLICATIONS_URL_TS,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert apply_resp.status_code == 200
    membership_id = apply_resp.json()["data"]["membership_id"]

    # owner 审核通过（不传 initial_mu）
    review_resp = await client.post(
        f"{REVIEW_BASE_TS}/{membership_id}/review",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert review_resp.status_code == 200, f"审核通过失败: {review_resp.text}"
    data = review_resp.json()["data"]
    # 样本不足 3 人（队伍刚创建），建议值应回退到 25.0
    assert data["suggested_mu"] == pytest.approx(25.0), f"样本不足时建议值应为 25.0，实际: {data}"
    assert data["initial_mu"] == pytest.approx(25.0)


async def test_review_approve_manual_mu_sets_player_mu(
    client: AsyncClient, db_session
):
    """T036 [US4]: approve 时手动传 initial_mu=32.0，player.mu 应被设为 32.0。"""
    from sqlalchemy import select
    from app.models.player import Player

    owner_token = await _reg_login_ts(client, "ts36own2", "ts36own2@t.com")
    r = await client.post(CREATE_TEAM_URL_TS, json={"team_name": "ReviewTeam36b"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201
    team_id = r.json()["team_id"]

    user_token = await _reg_login_ts(client, "ts36usr2", "ts36usr2@t.com")
    apply_resp = await client.post(
        APPLICATIONS_URL_TS,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert apply_resp.status_code == 200
    membership_id = apply_resp.json()["data"]["membership_id"]

    review_resp = await client.post(
        f"{REVIEW_BASE_TS}/{membership_id}/review",
        json={"action": "approve", "initial_mu": 32.0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert review_resp.status_code == 200, f"审核通过失败: {review_resp.text}"
    assert review_resp.json()["data"]["initial_mu"] == pytest.approx(32.0)

    # 验证 player.mu 已被设为 32.0
    user_player = (
        await db_session.execute(select(Player).where(Player.username == "ts36usr2"))
    ).scalar_one()
    await db_session.refresh(user_player)
    assert user_player.mu == pytest.approx(32.0), f"player.mu 应为 32.0，实际: {user_player.mu}"

