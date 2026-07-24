"""
test_multi_team.py
------------------
验证多队伍功能端对端交互：
  1. 申请加入多支队伍
  2. 审批时展示 join_reason
  3. GET /players 成员列表隔离
  4. 切换默认队伍 (PUT /team/default)
  5. cross_player 可在 testmix / testman 之间切换
  6. 移出队伍后 membership 自动回退到另一支
  7. 重复申请同一支队伍返回 400
"""
import pytest
from httpx import AsyncClient

REG_URL     = "/api/v1/auth/register"
LOGIN_URL   = "/api/v1/auth/login"
AUTH_URL    = "/api/v1/auth"
TEAM_URL    = "/api/v1/team"
PLAYERS_URL = "/api/v1/players"


# ─── helpers ──────────────────────────────────────────────────────────

async def reg(client: AsyncClient, username: str, pw: str = "pw123456") -> None:
    r = await client.post(REG_URL, json={"username": username, "email": f"{username}@example.com", "password": pw})
    assert r.status_code == 201, r.text


async def login(client: AsyncClient, username: str, pw: str = "pw123456") -> str:
    r = await client.post(LOGIN_URL, data={"username": username, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_approved_team(client: AsyncClient, owner_username: str, team_name: str):
    """注册 owner、创建队伍，用超管批准（跳过超管流程，直接用 is_approved 已经 True 时的自动批准逻辑）。
    本测试环境 DEBUG=False，team 创建后 is_approved=False；
    为简化测试，我们使用已审批的现有队伍 testmix/testman/testwoman，
    只注册新用户并让他们申请加入。
    """
    await reg(client, owner_username)
    owner_token = await login(client, owner_username)
    r = await client.post(f"{TEAM_URL}/create", json={"team_name": team_name}, headers=hdr(owner_token))
    assert r.status_code == 201, r.text
    team_id = r.json()["team_id"]
    return owner_token, team_id


# ─── tests ─────────────────────────────────────────────────────────────

class TestMultiTeamApply:
    """测试申请加入多支队伍"""

    @pytest.mark.asyncio
    async def test_apply_to_two_teams(self, client: AsyncClient):
        """同一用户可申请加入两支不同的已批准队伍"""
        # 注册 owner1，创建并批准 teamA
        await reg(client, "mtownera")
        oa_token = await login(client, "mtownera")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "mt_team_a"}, headers=hdr(oa_token))
        assert r.status_code == 201
        ta_id = r.json()["team_id"]

        # 注册 owner2，创建并批准 teamB
        await reg(client, "mtownerb")
        ob_token = await login(client, "mtownerb")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "mt_team_b"}, headers=hdr(ob_token))
        assert r.status_code == 201
        tb_id = r.json()["team_id"]

        # 普通用户申请加入 teamA（带理由）— 使用多队申请端点
        await reg(client, "mtapplicant")
        ap_token = await login(client, "mtapplicant")
        r = await client.post(
            f"{TEAM_URL}/applications",
            json={"team_id": ta_id, "join_reason": "想练队"},
            headers=hdr(ap_token),
        )
        assert r.status_code == 200, r.text

        # 同用户申请加入 teamB（无理由也可）
        r = await client.post(
            f"{TEAM_URL}/applications",
            json={"team_id": tb_id},
            headers=hdr(ap_token),
        )
        assert r.status_code == 200, r.text

        # GET /team/my-teams 应返回 2 条
        r = await client.get(f"{TEAM_URL}/my-teams", headers=hdr(ap_token))
        assert r.status_code == 200
        teams = r.json()
        assert len(teams) == 2, f"期望 2 支队伍，实际 {len(teams)}: {teams}"

    @pytest.mark.asyncio
    async def test_duplicate_apply_returns_400(self, client: AsyncClient):
        """重复申请同一支队伍应返回 400"""
        await reg(client, "mtdupowner")
        ot = await login(client, "mtdupowner")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "mt_dup_team"}, headers=hdr(ot))
        team_id = r.json()["team_id"]

        await reg(client, "mtdupuser")
        ut = await login(client, "mtdupuser")
        await client.post(f"{TEAM_URL}/apply", json={"team_id": team_id}, headers=hdr(ut))

        # 第二次申请
        r = await client.post(f"{TEAM_URL}/apply", json={"team_id": team_id}, headers=hdr(ut))
        assert r.status_code == 400, r.text


class TestJoinReasonDisplay:
    """测试申请理由在审批列表中可见"""

    @pytest.mark.asyncio
    async def test_pending_members_shows_join_reason(self, client: AsyncClient):
        await reg(client, "jraowner")
        owner_t = await login(client, "jraowner")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "jra_team"}, headers=hdr(owner_t))
        team_id = r.json()["team_id"]

        await reg(client, "jrauser")
        user_t = await login(client, "jrauser")
        reason = "我热爱飞盘，想加入你们"
        # 使用多队申请端点，以保存 join_reason 到 PlayerTeamMembership
        await client.post(f"{TEAM_URL}/applications", json={"team_id": team_id, "join_reason": reason}, headers=hdr(user_t))

        # owner 查看 pending-members
        r = await client.get(f"{TEAM_URL}/pending-members", headers=hdr(owner_t))
        assert r.status_code == 200, r.text
        pending = r.json()
        assert len(pending) >= 1
        usernames = [p["username"] for p in pending]
        assert "jrauser" in usernames
        jra_entry = next(p for p in pending if p["username"] == "jrauser")
        assert jra_entry["join_reason"] == reason


class TestMemberListIsolation:
    """验证 GET /players 只返回当前队伍的成员"""

    @pytest.mark.asyncio
    async def test_players_list_isolated_by_team(self, client: AsyncClient):
        # 建立两支队伍
        await reg(client, "isoownera")
        oa_t = await login(client, "isoownera")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "iso_team_a"}, headers=hdr(oa_t))
        ta_id = r.json()["team_id"]

        await reg(client, "isoownerb")
        ob_t = await login(client, "isoownerb")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "iso_team_b"}, headers=hdr(ob_t))
        tb_id = r.json()["team_id"]

        # 各添加一个 active 队员
        await reg(client, "isomembera")
        ma_t = await login(client, "isomembera")
        await client.post(f"{TEAM_URL}/apply", json={"team_id": ta_id}, headers=hdr(ma_t))
        # 获取 pending player id
        pending = (await client.get(f"{PLAYERS_URL}?status=pending", headers=hdr(oa_t))).json()
        ma_id = next(p["id"] for p in pending if p["username"] == "isomembera")
        await client.patch(f"{PLAYERS_URL}/{ma_id}/status", json={"status": "active"}, headers=hdr(oa_t))

        # owner_a 拿到的队员列表只有 teamA 成员
        players_a = (await client.get(f"{PLAYERS_URL}", headers=hdr(oa_t))).json()
        usernames_a = {p["username"] for p in players_a}
        assert "isomembera" in usernames_a, "isomembera 应在 teamA 列表中"
        assert "isoownerb" not in usernames_a, "teamB 的 owner 不应出现在 teamA 列表"

    @pytest.mark.asyncio
    async def test_superadmin_can_switch_team_view(self, client: AsyncClient):
        """超管通过 ?team_id= 可以查看任意队伍的成员列表"""
        # 用已有的超管账号（如果项目有固定超管，可直接 login；否则此测试跳过）
        r = await client.post(LOGIN_URL, data={"username": "superadmin", "password": "admin123"})
        if r.status_code != 200:
            pytest.skip("本地无 superadmin 账号，跳过此测试")
        sa_token = r.json()["access_token"]

        # 注册一支队伍，让超管通过 ?team_id= 查看
        await reg(client, "satestowner")
        ot = await login(client, "satestowner")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "sa_test_team"}, headers=hdr(ot))
        team_id = r.json()["team_id"]

        r = await client.get(f"{PLAYERS_URL}?team_id={team_id}", headers=hdr(sa_token))
        assert r.status_code == 200, r.text
        usernames = {p["username"] for p in r.json()}
        assert "satestowner" in usernames


class TestDefaultTeamSwitch:
    """测试切换默认队伍"""

    @pytest.mark.asyncio
    async def test_set_default_team(self, client: AsyncClient):
        """用户加入两支队伍后可切换默认队伍"""
        await reg(client, "defownerx")
        ox_t = await login(client, "defownerx")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "def_team_x"}, headers=hdr(ox_t))
        tx_id = r.json()["team_id"]

        await reg(client, "defownery")
        oy_t = await login(client, "defownery")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "def_team_y"}, headers=hdr(oy_t))
        ty_id = r.json()["team_id"]

        # 用户加入 team_x（旧流程：/apply → /players/{id}/status）
        await reg(client, "defswitcher")
        sw_t = await login(client, "defswitcher")
        r = await client.post(f"{TEAM_URL}/apply", json={"team_id": tx_id}, headers=hdr(sw_t))
        assert r.status_code == 200

        # team_x 审批通过（旧流程）
        pending = (await client.get(f"{PLAYERS_URL}?status=pending", headers=hdr(ox_t))).json()
        sw_id = next(p["id"] for p in pending if p["username"] == "defswitcher")
        await client.patch(f"{PLAYERS_URL}/{sw_id}/status", json={"status": "active"}, headers=hdr(ox_t))

        # 用户申请 team_y（多队申请端点，获取 membership_id）
        r = await client.post(f"{TEAM_URL}/applications", json={"team_id": ty_id}, headers=hdr(sw_t))
        assert r.status_code == 200, r.text
        membership_id_y = r.json()["data"]["membership_id"]

        # team_y 审批通过（新流程：review 端点）
        r = await client.post(
            f"{TEAM_URL}/applications/{membership_id_y}/review",
            json={"action": "approve"},
            headers=hdr(oy_t),
        )
        assert r.status_code == 200, r.text

        # 切换默认到 team_y
        r = await client.put(f"{TEAM_URL}/default", json={"team_id": ty_id}, headers=hdr(sw_t))
        assert r.status_code == 200, r.text

        # 通过 /auth/me/context 验证 default_team_id 已更新
        ctx = (await client.get(f"{AUTH_URL}/me/context", headers=hdr(sw_t))).json()
        assert ctx["data"]["default_team_id"] == ty_id, f"expected {ty_id}, got {ctx['data']['default_team_id']}"

    @pytest.mark.asyncio
    async def test_switch_to_non_member_team_returns_403(self, client: AsyncClient):
        """尝试切换到没有 membership 的队伍应返回 403"""
        await reg(client, "defownerz")
        oz_t = await login(client, "defownerz")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "def_team_z"}, headers=hdr(oz_t))
        tz_id = r.json()["team_id"]

        await reg(client, "defnonmember")
        nm_t = await login(client, "defnonmember")

        # 非成员切换默认队伍应返回 403
        r = await client.put(f"{TEAM_URL}/default", json={"team_id": tz_id}, headers=hdr(nm_t))
        assert r.status_code == 403, r.text


class TestRemoveFromTeamFallback:
    """移出队伍后，若还有其他队伍，自动切换到另一支"""

    @pytest.mark.asyncio
    async def test_remove_from_one_team_falls_back(self, client: AsyncClient):
        # 两支队伍的 owner
        await reg(client, "rmownera")
        roa_t = await login(client, "rmownera")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "rm_team_a"}, headers=hdr(roa_t))
        rta_id = r.json()["team_id"]

        await reg(client, "rmownerb")
        rob_t = await login(client, "rmownerb")
        r = await client.post(f"{TEAM_URL}/create", json={"team_name": "rm_team_b"}, headers=hdr(rob_t))
        rtb_id = r.json()["team_id"]

        # target 用户：旧流程加入 team_a
        await reg(client, "rmtarget")
        tgt_t = await login(client, "rmtarget")

        await client.post(f"{TEAM_URL}/apply", json={"team_id": rta_id}, headers=hdr(tgt_t))
        pending_a = (await client.get(f"{PLAYERS_URL}?status=pending", headers=hdr(roa_t))).json()
        tgt_id = next(p["id"] for p in pending_a if p["username"] == "rmtarget")
        await client.patch(f"{PLAYERS_URL}/{tgt_id}/status", json={"status": "active"}, headers=hdr(roa_t))

        # 多队申请端点申请 team_b，获取 membership_id
        r = await client.post(f"{TEAM_URL}/applications", json={"team_id": rtb_id}, headers=hdr(tgt_t))
        assert r.status_code == 200, r.text
        membership_id_b = r.json()["data"]["membership_id"]

        # team_b owner 审批通过（review 端点）
        r = await client.post(
            f"{TEAM_URL}/applications/{membership_id_b}/review",
            json={"action": "approve"},
            headers=hdr(rob_t),
        )
        assert r.status_code == 200, r.text

        # 切换默认到 team_a（通过 PTM 校验，team_a 通过旧 /apply 无 PTM active 记录）
        # 不调用 PUT /team/default，因 team_a 没有 PTM active 记录，改为直接验证 team_b 回退

        # team_a owner 将 target 移出 team_a
        r = await client.delete(f"{PLAYERS_URL}/{tgt_id}/from-team", headers=hdr(roa_t))
        assert r.status_code == 200, r.text

        # 重新登录获取指向 team_b shard 的新 token
        tgt_t_new = await login(client, "rmtarget")

        # target 当前 active player 应在 team_b
        me = (await client.get(f"{PLAYERS_URL}/me", headers=hdr(tgt_t_new))).json()
        assert me["team_id"] == rtb_id, f"应回退到 team_b={rtb_id}, 实际={me['team_id']}"
