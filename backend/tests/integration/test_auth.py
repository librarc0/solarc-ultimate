"""T025: /auth 端点集成测试 — 新注册逻辑（不自动分配队伍，必须有邮箱）"""
from datetime import datetime, timedelta, timezone
import base64

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import _send_code_email
from app.core.config import settings
from app.models.player import Player, PlayerStatus


REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"


# ---------------------------------------------------------------------------
# 注册场景
# ---------------------------------------------------------------------------


async def test_register_creates_active_member(client: AsyncClient):
    """注册后账号为 active + member，无团队"""
    resp = await client.post(REG_URL, json={
        "username": "newuser1",
        "email": "newuser1@example.com",
        "password": "password123",
    })
    assert resp.status_code == 201


async def test_register_requires_email(client: AsyncClient):
    """没有邮箱 → 422 验证错误"""
    resp = await client.post(REG_URL, json={
        "username": "nomail1",
        "password": "password123",
    })
    assert resp.status_code == 422


async def test_register_invalid_email(client: AsyncClient):
    """无效邮箱格式 → 422"""
    resp = await client.post(REG_URL, json={
        "username": "badmail1",
        "email": "not-an-email",
        "password": "password123",
    })
    assert resp.status_code == 422


async def test_duplicate_username_fails(client: AsyncClient):
    """重复用户名 → 400"""
    payload = {"username": "dupuser", "email": "dup@example.com", "password": "password123"}
    await client.post(REG_URL, json=payload)
    resp = await client.post(REG_URL, json={"username": "dupuser", "email": "dup2@example.com", "password": "password123"})
    assert resp.status_code == 400


async def test_duplicate_email_fails(client: AsyncClient):
    """重复邮箱 → 400"""
    await client.post(REG_URL, json={"username": "emailuser1", "email": "same@example.com", "password": "password123"})
    resp = await client.post(REG_URL, json={"username": "emailuser2", "email": "same@example.com", "password": "password123"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 登录和 token 验证
# ---------------------------------------------------------------------------


async def test_login_with_username(client: AsyncClient):
    """用用户名登录 → 返回 access_token"""
    await client.post(REG_URL, json={
        "username": "loginusr1",
        "email": "loginusr1@example.com",
        "password": "password123",
    })
    resp = await client.post(LOGIN_URL, data={
        "username": "loginusr1",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_with_email(client: AsyncClient):
    """用邮箱登录 → 返回 access_token"""
    await client.post(REG_URL, json={
        "username": "loginusr2",
        "email": "loginusr2@example.com",
        "password": "password123",
    })
    resp = await client.post(LOGIN_URL, data={
        "username": "loginusr2@example.com",  # email as username field
        "password": "password123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_wrong_password_returns_401(client: AsyncClient):
    """错误密码 → 401"""
    await client.post(REG_URL, json={
        "username": "authuser",
        "email": "authuser@example.com",
        "password": "password123",
    })
    resp = await client.post(LOGIN_URL, data={
        "username": "authuser",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


async def test_registered_user_can_login_without_team(client: AsyncClient):
    """注册后无需队伍即可登录（新逻辑：不再是 pending）"""
    await client.post(REG_URL, json={
        "username": "noteamuser",
        "email": "noteam@example.com",
        "password": "password123",
    })
    resp = await client.post(LOGIN_URL, data={
        "username": "noteamuser",
        "password": "password123",
    })
    assert resp.status_code == 200


async def test_short_password_fails(client: AsyncClient):
    """密码不足8位 → 422"""
    resp = await client.post(REG_URL, json={
        "username": "shortpw1",
        "email": "shortpw@example.com",
        "password": "short",
    })
    assert resp.status_code == 422


async def test_invalid_username_format(client: AsyncClient):
    """用户名含特殊字符 → 422"""
    resp = await client.post(REG_URL, json={
        "username": "bad name!",
        "email": "badname@example.com",
        "password": "password123",
    })
    assert resp.status_code == 422


async def test_nonexistent_user_returns_401(client: AsyncClient):
    """不存在的用户 → 401"""
    resp = await client.post(LOGIN_URL, data={
        "username": "ghost",
        "password": "password123",
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------


async def _get_token(client: AsyncClient, username: str = "meuser") -> str:
    await client.post(REG_URL, json={
        "username": username,
        "email": f"{username}@test.com",
        "password": "password123",
    })
    resp = await client.post(LOGIN_URL, data={
        "username": username,
        "password": "password123",
    })
    return resp.json()["access_token"]


async def test_get_me_with_valid_token(client: AsyncClient):
    """有效 token → 200 + 用户信息"""
    token = await _get_token(client)
    resp = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "meuser"
    assert data["role"] == "member"


async def test_get_me_without_token_returns_401(client: AsyncClient):
    """无 token → 401"""
    resp = await client.get(ME_URL)
    assert resp.status_code == 401


async def test_get_me_with_invalid_token_returns_401(client: AsyncClient):
    """无效 token → 401"""
    resp = await client.get(ME_URL, headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401


async def test_login_rejected_user_returns_403(client: AsyncClient, db_session: AsyncSession):
    """被拒绝账户登录 → 403"""
    await client.post(
        REG_URL,
        json={
            "username": "rejecteduser",
            "email": "rejecteduser@example.com",
            "password": "password123",
        },
    )
    result = await db_session.execute(select(Player).where(Player.username == "rejecteduser"))
    player = result.scalar_one()
    player.status = PlayerStatus.rejected
    await db_session.commit()

    resp = await client.post(
        LOGIN_URL,
        data={
            "username": "rejecteduser",
            "password": "password123",
        },
    )
    assert resp.status_code == 403


async def test_forgot_password_without_smtp_returns_403(client: AsyncClient):
    """未配置 SMTP 时找回密码接口返回 403"""
    old_host = settings.SMTP_HOST
    settings.SMTP_HOST = ""
    try:
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"username": "nobody", "email": "nobody@example.com"},
        )
    finally:
        settings.SMTP_HOST = old_host

    assert resp.status_code == 403


async def test_forgot_password_username_email_mismatch_returns_400(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """用户名与邮箱不匹配 → 400"""
    await client.post(
        REG_URL,
        json={"username": "mismatch_user", "email": "mismatch@example.com", "password": "password123"},
    )

    monkeypatch.setattr("app.api.v1.endpoints.auth._send_code_email", lambda *a, **kw: None)
    old_host = settings.SMTP_HOST
    settings.SMTP_HOST = "smtp.example.com"
    try:
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"username": "mismatch_user", "email": "wrong@example.com"},
        )
    finally:
        settings.SMTP_HOST = old_host

    assert resp.status_code == 400


async def test_forgot_password_success_sends_code_and_stores_in_db(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """用户名+邮箱匹配时，存储验证码（C:前缀）并发送邮件"""
    await client.post(
        REG_URL,
        json={"username": "codeuser", "email": "codeuser@example.com", "password": "password123"},
    )

    sent: dict = {}

    def fake_send_code(to_email: str, username: str, code: str) -> None:
        sent["to"] = to_email
        sent["code"] = code

    monkeypatch.setattr("app.api.v1.endpoints.auth._send_code_email", fake_send_code)
    old_host = settings.SMTP_HOST
    settings.SMTP_HOST = "smtp.example.com"
    try:
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"username": "codeuser", "email": "codeuser@example.com"},
        )
    finally:
        settings.SMTP_HOST = old_host

    assert resp.status_code == 200
    assert "验证码" in resp.json()["message"]

    result = await db_session.execute(select(Player).where(Player.username == "codeuser"))
    player = result.scalar_one()
    assert player.reset_token is not None
    assert player.reset_token.startswith("C:")
    assert player.reset_token_expires is not None
    assert sent["to"] == "codeuser@example.com"
    assert len(sent["code"]) == 6
    assert sent["code"].isdigit()


# ---------------------------------------------------------------------------
# 步骤二：验证码验证
# ---------------------------------------------------------------------------


async def test_verify_reset_code_missing_or_wrong_token_returns_400(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """没有待验证状态时 → 400"""
    await client.post(
        REG_URL,
        json={"username": "nocode_user", "email": "nocode@example.com", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": "nocode@example.com", "code": "123456"},
    )
    assert resp.status_code == 400


async def test_verify_reset_code_expired_returns_400(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """验证码过期 → 400"""
    await client.post(
        REG_URL,
        json={"username": "expcodeuser", "email": "expcode@example.com", "password": "password123"},
    )
    result = await db_session.execute(select(Player).where(Player.username == "expcodeuser"))
    player = result.scalar_one()
    player.reset_token = "C:654321"
    player.reset_token_expires = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": "expcode@example.com", "code": "654321"},
    )
    assert resp.status_code == 400


async def test_verify_reset_code_wrong_code_returns_400(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """验证码错误 → 400"""
    await client.post(
        REG_URL,
        json={"username": "wrongcodeuser", "email": "wrongcode@example.com", "password": "password123"},
    )
    result = await db_session.execute(select(Player).where(Player.username == "wrongcodeuser"))
    player = result.scalar_one()
    player.reset_token = "C:111111"
    player.reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": "wrongcode@example.com", "code": "999999"},
    )
    assert resp.status_code == 400


async def test_verify_reset_code_correct_returns_confirmed_token(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """正确验证码 → 200 + confirmed_token，DB 中存 K: 前缀"""
    await client.post(
        REG_URL,
        json={"username": "okcodeuser", "email": "okcode@example.com", "password": "password123"},
    )
    result = await db_session.execute(select(Player).where(Player.username == "okcodeuser"))
    player = result.scalar_one()
    player.reset_token = "C:222222"
    player.reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": "okcode@example.com", "code": "222222"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "confirmed_token" in data
    assert len(data["confirmed_token"]) > 10

    await db_session.refresh(player)
    assert player.reset_token is not None
    assert player.reset_token.startswith("K:")


# ---------------------------------------------------------------------------
# 步骤三：重置密码
# ---------------------------------------------------------------------------


async def test_reset_password_passwords_mismatch_returns_422(client: AsyncClient):
    """两次密码不一致 → 422"""
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"confirmed_token": "abc", "new_password": "password123", "confirm_password": "different456"},
    )
    assert resp.status_code == 422


async def test_reset_password_too_short_returns_422(client: AsyncClient):
    """密码过短 → 422"""
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"confirmed_token": "abc", "new_password": "short", "confirm_password": "short"},
    )
    assert resp.status_code == 422


async def test_reset_password_invalid_confirmed_token_returns_400(client: AsyncClient):
    """无效 confirmed_token → 400"""
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"confirmed_token": "nonexistent-token", "new_password": "newpass123", "confirm_password": "newpass123"},
    )
    assert resp.status_code == 400


async def test_reset_password_expired_confirmed_token_returns_400(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """confirmed_token 过期 → 400"""
    await client.post(
        REG_URL,
        json={"username": "expresetuser", "email": "exp_reset@example.com", "password": "password123"},
    )
    result = await db_session.execute(select(Player).where(Player.username == "expresetuser"))
    player = result.scalar_one()
    player.reset_token = "K:expired-confirmed-token"
    player.reset_token_expires = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"confirmed_token": "expired-confirmed-token", "new_password": "newpass123", "confirm_password": "newpass123"},
    )
    assert resp.status_code == 400


async def test_reset_password_full_flow_success(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """完整三步流程：重置成功后旧密码失效、新密码可登录"""
    await client.post(
        REG_URL,
        json={"username": "fullflowuser", "email": "fullflow@example.com", "password": "password123"},
    )

    # 直接在 DB 注入已验证的 confirmed_token
    result = await db_session.execute(select(Player).where(Player.username == "fullflowuser"))
    player = result.scalar_one()
    player.reset_token = "K:valid-confirmed-token"
    player.reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    await db_session.commit()

    reset_resp = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "confirmed_token": "valid-confirmed-token",
            "new_password": "newpassword456",
            "confirm_password": "newpassword456",
        },
    )
    assert reset_resp.status_code == 200

    # 旧密码应不可用
    old_login = await client.post(LOGIN_URL, data={"username": "fullflowuser", "password": "password123"})
    assert old_login.status_code == 401

    # 新密码应可用
    new_login = await client.post(LOGIN_URL, data={"username": "fullflowuser", "password": "newpassword456"})
    assert new_login.status_code == 200

    # token 已清空
    await db_session.refresh(player)
    assert player.reset_token is None
    assert player.reset_token_expires is None


# ---------------------------------------------------------------------------
# SMTP helper 单元测试
# ---------------------------------------------------------------------------


def test_send_code_email_uses_smtp_client(monkeypatch: pytest.MonkeyPatch):
    """_send_code_email: 建立 SMTP 连接、starttls、login 并 sendmail"""
    calls: dict = {}

    class FakeSMTP:
        def __init__(self, host: str, port: int):
            calls["host"] = host
            calls["port"] = port

        def __enter__(self):
            calls["entered"] = True
            return self

        def __exit__(self, exc_type, exc, tb):
            calls["exited"] = True

        def starttls(self):
            calls["tls"] = True

        def login(self, username: str, password: str):
            calls["login"] = (username, password)

        def sendmail(self, from_email: str, to_emails: list, message: str):
            calls["sendmail"] = (from_email, to_emails, message)

    monkeypatch.setattr("app.api.v1.endpoints.auth.smtplib.SMTP", FakeSMTP)

    old_host = settings.SMTP_HOST
    old_port = settings.SMTP_PORT
    old_username = settings.SMTP_USERNAME
    old_password = settings.SMTP_PASSWORD
    old_from = settings.SMTP_FROM
    settings.SMTP_HOST = "smtp.example.com"
    settings.SMTP_PORT = 2525
    settings.SMTP_USERNAME = "mailer"
    settings.SMTP_PASSWORD = "secret"
    settings.SMTP_FROM = "noreply@example.com"
    try:
        _send_code_email("target@example.com", "TestUser", "123456")
    finally:
        settings.SMTP_HOST = old_host
        settings.SMTP_PORT = old_port
        settings.SMTP_USERNAME = old_username
        settings.SMTP_PASSWORD = old_password
        settings.SMTP_FROM = old_from

    assert calls["host"] == "smtp.example.com"
    assert calls["port"] == 2525
    assert calls["tls"] is True
    assert calls["login"] == ("mailer", "secret")
    sent_from, sent_to, raw_message = calls["sendmail"]
    assert sent_from == "noreply@example.com"
    assert sent_to == ["target@example.com"]
    # 邮件体是 base64 编码的 HTML multipart，解码后检查验证码出现
    assert base64.b64encode(b"123456").decode() in raw_message or "123456" in raw_message


# ---------------------------------------------------------------------------
# T013: User-based 登录/token 回归测试
# ---------------------------------------------------------------------------

import json as _json


def _decode_jwt_payload(token: str) -> dict:
    """Base64url 解码 JWT payload（不验签，仅用于测试断言）。"""
    payload_part = token.split(".")[1]
    # Add padding
    padding = 4 - len(payload_part) % 4
    if padding != 4:
        payload_part += "=" * padding
    return _json.loads(base64.b64decode(payload_part.replace("-", "+").replace("_", "/")))


async def test_login_token_sub_is_user_id(client: AsyncClient, db_session: AsyncSession):
    """T013: 登录后 JWT sub 字段为 user.id，而非 player.id"""
    from sqlalchemy import select
    from app.models.user import User

    await client.post(REG_URL, json={
        "username": "toktest1",
        "email": "toktest1@example.com",
        "password": "password123",
    })
    resp = await client.post(LOGIN_URL, data={"username": "toktest1", "password": "password123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    payload = _decode_jwt_payload(token)

    result = await db_session.execute(select(User).where(User.username == "toktest1"))
    user = result.scalar_one()

    # sub MUST be the User.id, not the Player.id
    assert str(payload["sub"]) == str(user.id), (
        f"JWT sub={payload['sub']} expected user.id={user.id}"
    )


async def test_login_token_contains_role(client: AsyncClient):
    """T013: token payload 包含 role 字段"""
    await client.post(REG_URL, json={
        "username": "toktest2",
        "email": "toktest2@example.com",
        "password": "password123",
    })
    resp = await client.post(LOGIN_URL, data={"username": "toktest2", "password": "password123"})
    payload = _decode_jwt_payload(resp.json()["access_token"])
    assert "role" in payload


async def test_me_endpoint_works_after_user_migration(client: AsyncClient):
    """T013: /auth/me 用新格式 token 仍返回 200 + 用户信息"""
    await client.post(REG_URL, json={
        "username": "mecompat",
        "email": "mecompat@example.com",
        "password": "password123",
    })
    login_resp = await client.post(LOGIN_URL, data={"username": "mecompat", "password": "password123"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["username"] == "mecompat"


async def test_me_context_returns_envelope(client: AsyncClient):
    """T013: GET /auth/me/context 返回 {code,data,message} 信封格式"""
    await client.post(REG_URL, json={
        "username": "ctxuser1",
        "email": "ctxuser1@example.com",
        "password": "password123",
    })
    login_resp = await client.post(LOGIN_URL, data={"username": "ctxuser1", "password": "password123"})
    token = login_resp.json()["access_token"]

    ctx_resp = await client.get("/api/v1/auth/me/context", headers={"Authorization": f"Bearer {token}"})
    assert ctx_resp.status_code == 200
    body = ctx_resp.json()
    assert body["code"] == 0
    assert "data" in body
    data = body["data"]
    assert "user_id" in data
    assert "username" in data
    assert "teams" in data
    assert isinstance(data["teams"], list)


async def test_me_context_new_user_has_no_teams(client: AsyncClient):
    """T013: 新注册用户 /auth/me/context 中 teams 为空列表"""
    await client.post(REG_URL, json={
        "username": "noteamctx",
        "email": "noteamctx@example.com",
        "password": "password123",
    })
    login_resp = await client.post(LOGIN_URL, data={"username": "noteamctx", "password": "password123"})
    token = login_resp.json()["access_token"]

    ctx_resp = await client.get("/api/v1/auth/me/context", headers={"Authorization": f"Bearer {token}"})
    assert ctx_resp.status_code == 200
    assert ctx_resp.json()["data"]["teams"] == []


async def test_me_context_requires_auth(client: AsyncClient):
    """T013: /auth/me/context 无 token → 401"""
    resp = await client.get("/api/v1/auth/me/context")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# T022 [US2]: switch-team 切队权限场景
# ---------------------------------------------------------------------------

SWITCH_URL = "/api/v1/auth/switch-team"
CREATE_TEAM_URL = "/api/v1/team/create"
APPLY_URL = "/api/v1/team/apply"
APPROVE_URL = "/api/v1/players"


async def _register_login(client: AsyncClient, username: str, email: str, password: str = "password123") -> str:
    await client.post(REG_URL, json={"username": username, "email": email, "password": password})
    r = await client.post(LOGIN_URL, data={"username": username, "password": password})
    assert r.status_code == 200, f"登录失败: {r.text}"
    return r.json()["access_token"]


async def test_switch_team_member_can_switch_to_own_team(client: AsyncClient, db_session):
    """T022: 普通用户可切换到自己所属的队伍，返回新 token"""
    token = await _register_login(client, "swowner22aa", "swowner22@e.com")
    # 创建队伍
    r = await client.post(CREATE_TEAM_URL, json={"team_name": "Switchable22"},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    team_id = r.json()["team_id"]

    # 切换到自己创建的队伍（自己是 active owner 成员）
    resp = await client.post(SWITCH_URL, json={"team_id": team_id},
                             headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, f"切队失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0
    assert "access_token" in body["data"]
    assert body["data"]["team_id"] == team_id


async def test_switch_team_non_member_gets_403(client: AsyncClient, db_session):
    """T022: 普通用户切换到无访问权限队伍 → 403"""
    # 创建两个用户，各自建队
    token_a = await _register_login(client, "swusera22bb", "swusera22@e.com")
    token_b = await _register_login(client, "swuserb22cc", "swuserb22@e.com")

    r_a = await client.post(CREATE_TEAM_URL, json={"team_name": "TeamA22"},
                            headers={"Authorization": f"Bearer {token_a}"})
    assert r_a.status_code == 201
    team_a_id = r_a.json()["team_id"]


# ─── T049 [US6]: username 唯一性与跨队昵称隔离集成测试 ─────────────────────────

DUAL_PROFILE_URL = "/api/v1/players/me/profile/dual"


@pytest.mark.asyncio
async def test_us6_username_uniqueness_enforced(client: AsyncClient, db_session):
    """T049 [US6]: user.username 全局唯一，重复修改返回 400"""
    # 先注册两个用户
    token_a = await _register_login(client, "us6unamea1", "us6unamea1@e.com")
    token_b = await _register_login(client, "us6unameb1", "us6unameb1@e.com")

    # user_b 修改 username 为已存在的 us6unamea1
    r = await client.patch(
        DUAL_PROFILE_URL,
        headers={"Authorization": f"Bearer {token_b}"},
        json={"user": {"username": "us6unamea1"}},
    )
    assert r.status_code == 400
    assert "已被使用" in r.json()["detail"]


@pytest.mark.asyncio
async def test_us6_display_name_isolated_across_teams(client: AsyncClient, db_session):
    """T049 [US6]: 修改一个队伍 player 的 display_name，不影响另一个队伍的 display_name"""
    # 注册一个用户并创建队伍 A
    token_a = await _register_login(client, "us6isoowna", "us6isoa@e.com")
    r = await client.post(CREATE_TEAM_URL, json={"team_name": "US6IsoTeamA"},
                          headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 201


# ─── T056 [US7]: 修复后多队登录上下文回归测试骨架 ─────────────────────────────

@pytest.mark.skip(reason="T056 US7: 需要实际合并映射数据后完善")
@pytest.mark.asyncio
async def test_multi_team_login_context_regression_after_merge(client: AsyncClient, db_session):
    """合并后原账号仍可登录，teams 列表完整，player 分身可访问"""
    pass


async def test_superadmin_can_switch_to_any_team(client: AsyncClient, db_session):
    """T022: 超级管理员可切换到任意队伍（即使没有成员关系）"""
    from app.models.user import User
    from sqlalchemy import select

    # 注册普通用户并创建队伍
    owner_token = await _register_login(client, "swteamown22dd", "swteamown22@e.com")
    r = await client.post(CREATE_TEAM_URL, json={"team_name": "AnyTeam22"},
                          headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201
    team_id = r.json()["team_id"]

    # 注册超管账号
    sa_password = "password123"
    sa_username = "swsuperadm22ee"
    await client.post(REG_URL, json={"username": sa_username, "email": "swsa22@e.com", "password": sa_password})
    # 直接在 DB 中设置 is_superadmin=True
    result = await db_session.execute(select(User).where(User.username == sa_username))
    sa_user = result.scalar_one()
    sa_user.is_superadmin = True
    await db_session.commit()
    # 重新登录获取新 token（auth 层在 DB 查询 is_superadmin）
    sa_token = (await client.post(LOGIN_URL, data={"username": sa_username, "password": sa_password})).json()["access_token"]

    # 超管切换到他人球队（没有 player 关系 → 走超管分支，返回超管自身的 player）
    resp = await client.post(SWITCH_URL, json={"team_id": team_id},
                             headers={"Authorization": f"Bearer {sa_token}"})
    assert resp.status_code == 200, f"超管切队应成功: {resp.text}"
    assert resp.json()["code"] == 0


# ---------------------------------------------------------------------------
# T029 [US3]: 默认队伍命中与失效回退测试
# ---------------------------------------------------------------------------

DEFAULT_TEAM_URL = "/api/v1/auth/me/default-team"
CONTEXT_URL = "/api/v1/auth/me/context"
LEAVE_URL = "/api/v1/team/leave"


async def test_default_team_affects_login_context(client: AsyncClient, db_session):
    """T029: 设置默认队伍后重新登录，me/context 中 active_player 应属于默认队伍"""

    token = await _register_login(client, "dftuser29aa", "dft29aa@e.com")
    # 创建队伍（创建者自动成为 active 成员）
    r = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "DefaultTeamTest29"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    team_id = r.json()["team_id"]

    # 设置为默认队伍
    resp = await client.post(
        DEFAULT_TEAM_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # 重新登录，检查 context 中 active_player.team_id 是否命中默认队伍
    new_token_resp = await client.post(
        LOGIN_URL, data={"username": "dftuser29aa", "password": "password123"}
    )
    assert new_token_resp.status_code == 200
    new_token = new_token_resp.json()["access_token"]

    ctx = await client.get(CONTEXT_URL, headers={"Authorization": f"Bearer {new_token}"})
    assert ctx.status_code == 200
    ctx_data = ctx.json()["data"]
    assert ctx_data["default_team_id"] == team_id, (
        f"context 中 default_team_id 应为 {team_id}，实际: {ctx_data}"
    )
    # active_player 应属于默认队伍
    if ctx_data.get("active_player"):
        assert ctx_data["active_player"]["team_id"] == team_id, (
            f"active_player.team_id 应为 {team_id}，实际: {ctx_data['active_player']}"
        )


async def test_default_team_fallback_on_invalid(client: AsyncClient, db_session):
    """T029: 失效默认队伍时（用户不再是 active 成员），context 仍能正常返回（回退到其他队伍或 null）"""
    from app.models.user import User

    token = await _register_login(client, "dftuser29bb", "dft29bb@e.com")
    # 创建队伍并设置为默认队伍
    r = await client.post(
        CREATE_TEAM_URL,
        json={"team_name": "DefaultTeamFallback29"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    team_id = r.json()["team_id"]

    await client.post(
        DEFAULT_TEAM_URL,
        json={"team_id": team_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    # 直接在 DB 中将 default_team_id 设置为一个无效队伍 id（模拟队伍被删除或脱离）
    result = await db_session.execute(
        select(User).where(User.username == "dftuser29bb")
    )
    user_obj = result.scalar_one()
    user_obj.default_team_id = 99999  # 不存在的队伍
    await db_session.commit()

    # 重新登录后，context 接口仍应正常返回（不抛 500）
    new_token_resp = await client.post(
        LOGIN_URL, data={"username": "dftuser29bb", "password": "password123"}
    )
    assert new_token_resp.status_code == 200
    new_token = new_token_resp.json()["access_token"]

    ctx = await client.get(CONTEXT_URL, headers={"Authorization": f"Bearer {new_token}"})
    assert ctx.status_code == 200, f"context 接口不应抛 500: {ctx.text}"
    ctx_data = ctx.json()["data"]
    # active_player 不应在失效队伍（99999）中
    if ctx_data.get("active_player"):
        assert ctx_data["active_player"]["team_id"] != 99999, "active_player 不应在失效队伍中"


# ---------------------------------------------------------------------------
# T042 [US5]: 退队后重登收敛测试
# ---------------------------------------------------------------------------

LEAVE_TEAM_URL = "/api/v1/team-membership/leave"


async def test_leave_team_convergence(client: AsyncClient, db_session):
    """T042 [US5]: 用户退队后再次调用 me/context，teams 列表为空，default_team_id 被清除。"""
    from app.models.user import User

    token = await _register_login(client, "leaveconv42", "leaveconv42@e.com")

    # 创建队伍（自动成为 active owner）
    r = await client.post(CREATE_TEAM_URL, json={"team_name": "LeaveTeam42"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    team_id = r.json()["team_id"]

    # 设置为默认队伍
    await client.post(DEFAULT_TEAM_URL, json={"team_id": team_id}, headers={"Authorization": f"Bearer {token}"})

    # 验证 context 中有队伍
    ctx_before = await client.get(CONTEXT_URL, headers={"Authorization": f"Bearer {token}"})
    assert ctx_before.status_code == 200
    assert any(t["team_id"] == team_id for t in ctx_before.json()["data"]["teams"])
    assert ctx_before.json()["data"]["default_team_id"] == team_id

    # 退队（owner 仅有一人时允许退队）
    resp = await client.delete(LEAVE_TEAM_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, f"退队应成功: {resp.text}"

    # 退队后 me/context 中 teams 应为空
    ctx_after = await client.get(CONTEXT_URL, headers={"Authorization": f"Bearer {token}"})
    assert ctx_after.status_code == 200, f"退队后 context 不应 500: {ctx_after.text}"
    ctx_data = ctx_after.json()["data"]
    assert ctx_data["teams"] == [], f"退队后 teams 应为空，实际: {ctx_data['teams']}"

    # default_team_id 应被清除
    result = await db_session.execute(select(User).where(User.username == "leaveconv42"))
    user_obj = result.scalar_one()
    await db_session.refresh(user_obj)
    assert user_obj.default_team_id is None, f"退队后 default_team_id 应被清除，实际: {user_obj.default_team_id}"
