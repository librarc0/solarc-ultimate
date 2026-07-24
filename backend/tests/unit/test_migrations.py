from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings
from app.core.database import Base


def test_alembic_upgrade_head_on_empty_sqlite_db(tmp_path, monkeypatch):
    backend_dir = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "migration_smoke.db"
    sqlite_async_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    sqlite_sync_url = f"sqlite:///{db_path.as_posix()}"

    import app.models  # noqa: F401

    monkeypatch.setattr(settings, "DATABASE_URL", sqlite_async_url)

    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    command.upgrade(alembic_cfg, "head")

    script_dir = ScriptDirectory.from_config(alembic_cfg)
    engine = create_engine(sqlite_sync_url)
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            inspector = inspect(conn)
            migrated_tables = set(inspector.get_table_names())
            match_columns = {column["name"] for column in inspector.get_columns("match")}
            event_columns = {column["name"] for column in inspector.get_columns("match_event")}
            match_event_uniques = {
                tuple(sorted((item.get("column_names") or [])))
                for item in inspector.get_unique_constraints("match_event")
            }
            match_player_uniques = {
                tuple(sorted((item.get("column_names") or [])))
                for item in inspector.get_unique_constraints("match_player")
            }
            match_event_unique_indexes = {
                tuple(sorted((item.get("column_names") or [])))
                for item in inspector.get_indexes("match_event")
                if item.get("unique")
            }
            match_player_unique_indexes = {
                tuple(sorted((item.get("column_names") or [])))
                for item in inspector.get_indexes("match_player")
                if item.get("unique")
            }
            match_event_fks = {
                tuple(item.get("constrained_columns") or [])
                for item in inspector.get_foreign_keys("match_event")
            }
            match_player_fks = {
                tuple(item.get("constrained_columns") or [])
                for item in inspector.get_foreign_keys("match_player")
            }
            match_index_columns = {
                tuple(item.get("column_names") or [])
                for item in inspector.get_indexes("match")
            }
            match_event_index_columns = {
                tuple(item.get("column_names") or [])
                for item in inspector.get_indexes("match_event")
            }

            expected_tables = set(Base.metadata.tables.keys())
            assert expected_tables <= migrated_tables

            missing_columns_by_table: dict[str, list[str]] = {}
            for table_name, table in Base.metadata.tables.items():
                migrated_columns = {column["name"] for column in inspector.get_columns(table_name)}
                expected_columns = {column.name for column in table.columns}
                missing_columns = sorted(expected_columns - migrated_columns)
                if missing_columns:
                    missing_columns_by_table[table_name] = missing_columns

            # T012: compute these INSIDE the with-block while connection is alive
            t012_user_columns = {c["name"] for c in inspector.get_columns("user")}
            t012_player_columns = {c["name"] for c in inspector.get_columns("player")}
            t012_rh_columns = {c["name"] for c in inspector.get_columns("rating_history")}
            t012_ptm_indexes = {i["name"] for i in inspector.get_indexes("player_team_membership")}

        assert version == script_dir.get_current_head()
        assert not missing_columns_by_table, missing_columns_by_table
        assert {"draft_owner_id", "last_event_seq", "saved_at", "expires_at", "deleted_at"} <= match_columns
        assert {"seq", "client_event_id", "event_version", "payload_json", "created_by", "source", "deleted_at"} <= event_columns
        assert ("client_event_id", "match_id") in (match_event_uniques | match_event_unique_indexes)
        assert ("match_id", "seq") in (match_event_uniques | match_event_unique_indexes)
        assert ("match_id", "player_id") in (match_player_uniques | match_player_unique_indexes)
        assert ("match_id",) in match_event_fks
        assert ("player_id",) in match_event_fks
        assert ("assist_player_id",) in match_event_fks
        assert ("match_id",) in match_player_fks
        assert ("player_id",) in match_player_fks
        assert ("team_id",) in match_index_columns
        assert ("match_date",) in match_index_columns
        assert ("expires_at",) in match_index_columns
        assert ("deleted_at",) in match_index_columns
        assert ("match_id",) in match_event_index_columns

        # T012: User model and user_id FK assertions
        assert "user" in migrated_tables, "user table must exist after migration"
        assert {"id", "username", "password_hash", "is_superadmin", "created_at"} <= t012_user_columns
        assert "user_id" in t012_player_columns, "player.user_id FK column must exist"
        assert "team_id" in t012_rh_columns, "rating_history.team_id must be added by migration"
        assert "ix_player_team_membership_player_id" in t012_ptm_indexes
        assert "ix_player_team_membership_team_id" in t012_ptm_indexes
    finally:
        engine.dispose()


# ─── T054 [US7]: 重复人员合并映射与回滚测试骨架 ──────────────────────────────


@pytest.mark.skip(reason="T054 US7: 需要实际映射数据后完善")
def test_merge_task_record_model_schema():
    """验证 MergeTaskRecord 迁移后表结构正确（字段/索引存在）"""
    pass


@pytest.mark.skip(reason="T054 US7: 需要实际映射数据后完善")
def test_merge_rollback_restores_player_user_id():
    """回滚合并操作后，player.user_id 恢复原始值"""
    pass