from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.main import app


@pytest_asyncio.fixture(scope="function")
async def migrated_client(tmp_path, monkeypatch):
    backend_dir = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "migration_backed_integration.db"
    sqlite_async_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", sqlite_async_url)

    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(alembic_cfg, "head")

    engine = create_async_engine(sqlite_async_url, connect_args={"check_same_thread": False})
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


async def test_migration_backed_schema_supports_core_api_flow(migrated_client: AsyncClient):
    register_resp = await migrated_client.post(
        "/api/v1/auth/register",
        json={"username": "migowner", "email": "migowner@test.com", "password": "pw123456"},
    )
    assert register_resp.status_code == 201, register_resp.text

    login_resp = await migrated_client.post(
        "/api/v1/auth/login",
        data={"username": "migowner", "password": "pw123456"},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_team_resp = await migrated_client.post(
        "/api/v1/team/create",
        json={"team_name": "Migration Integration Team"},
        headers=headers,
    )
    assert create_team_resp.status_code == 201, create_team_resp.text

    me_resp = await migrated_client.get("/api/v1/players/me", headers=headers)
    assert me_resp.status_code == 200, me_resp.text


# ─── T055 [US7]: 修复脚本端到端测试骨架 ──────────────────────────────────────


@pytest.mark.skip(reason="T055 US7: 需要 MERGE_MAPPING 实际数据后完善")
@pytest.mark.asyncio
async def test_merge_script_e2e_dry_run(migrated_client):
    """干运行合并脚本，验证输出摘要正确（无数据变化）"""
    pass


@pytest.mark.skip(reason="T055 US7: 需要 MERGE_MAPPING 实际数据后完善")
@pytest.mark.asyncio
async def test_merge_script_e2e_execute_and_rollback(migrated_client):
    """执行合并后验证 player.user_id 更新，回滚后恢复原值"""
    pass
