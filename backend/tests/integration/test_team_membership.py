"""T071 [US3]: 我的页面发起加入队伍申请 — 集成测试

测试 /team-membership/applications 多队申请入口：
- 已有队伍的用户可申请加入另一支队伍
- 新申请记录存入 PlayerTeamMembership 表，原有 player.team_id 不变
- 重复申请被拒绝（已是成员或已有 pending 申请）
"""
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import PlayerTeamMembership
from app.models.player import Player, PlayerStatus


REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CREATE_TEAM_URL = "/api/v1/team/create"
APPLICATIONS_URL = "/api/v1/team-membership/applications"


async def _register_login(client: AsyncClient, username: str, email: str, password: str = "password123") -> str:
    await client.post(REG_URL, json={"username": username, "email": email, "password": password})
    r = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert r.status_code == 200, f"登录失败: {r.text}"
    return r.json()["access_token"]


async def test_already_in_team_user_can_apply_to_another_team(
    client: AsyncClient, db_session: AsyncSession
):
    """T071: 已在队伍中的用户可通过 /applications 申请加入另一支队伍，
    原 player.team_id 不变，PlayerTeamMembership 中出现新的 pending 记录。"""
    token_owner_a = await _register_login(client, "tm71ownA", "tm71ownA@e.com")
    token_owner_b = await _register_login(client, "tm71ownB", "tm71ownB@e.com")
    token_user = await _register_login(client, "tm71user", "tm71user@e.com")

    # owner_a 创建 TeamA，user 申请并加入（通过旧 apply 接口，team_id 写入 player）
    r_a = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "TeamA71"},
        headers={"Authorization": f"Bearer {token_owner_a}"},
    )
    assert r_a.status_code == 201
    team_a_id = r_a.json()["team_id"]

    # user 通过旧 /team/apply 加入 TeamA
    r_apply = await client.post(
        "/api/v1/team/apply",
        json={"team_id": team_a_id},
        headers={"Authorization": f"Bearer {token_user}"},
    )
    assert r_apply.status_code == 200, f"加入 TeamA 失败: {r_apply.text}"

    # owner_b 创建 TeamB
    r_b = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "TeamB71"},
        headers={"Authorization": f"Bearer {token_owner_b}"},
    )
    assert r_b.status_code == 201
    team_b_id = r_b.json()["team_id"]

    # 此时 user 已有 team_id（=team_a_id），通过 /applications 申请加入 TeamB
    resp = await client.post(
        APPLICATIONS_URL,
        json={"team_id": team_b_id},
        headers={"Authorization": f"Bearer {token_user}"},
    )
    assert resp.status_code == 200, f"多队申请失败: {resp.text}"
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["status"] == "pending"

    # 验证 DB 中 PlayerTeamMembership 记录已创建
    user_player = (
        await db_session.execute(
            select(Player).where(Player.username == "tm71user")
        )
    ).scalar_one()
    membership = (
        await db_session.execute(
            select(PlayerTeamMembership).where(
                PlayerTeamMembership.player_id == user_player.id,
                PlayerTeamMembership.team_id == team_b_id,
            )
        )
    ).scalar_one_or_none()
    assert membership is not None, "PlayerTeamMembership 记录应已创建"
    assert membership.status == PlayerStatus.pending

    # 原 player.team_id 应保留为 team_a_id（不被覆盖）
    assert user_player.team_id == team_a_id, (
        f"多队申请不应改变 player.team_id，期望 {team_a_id}，实际 {user_player.team_id}"
    )


async def test_applications_prevents_duplicate_pending(
    client: AsyncClient, db_session: AsyncSession
):
    """T071: 对同一队伍重复申请时，第二次应返回 409 并不创建重复记录"""
    token_owner = await _register_login(client, "tm71dup0", "tm71dup0@e.com")
    token_user = await _register_login(client, "tm71dup1", "tm71dup1@e.com")

    r = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "DupTeam71"},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert r.status_code == 201
    team_id = r.json()["team_id"]

    # 首次申请
    r1 = await client.post(
        APPLICATIONS_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token_user}"},
    )
    assert r1.status_code == 200

    # 重复申请应返回 409
    r2 = await client.post(
        APPLICATIONS_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token_user}"},
    )
    assert r2.status_code == 409, f"重复申请应返回 409: {r2.text}"
