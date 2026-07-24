"""fix external_team unique constraint and add season_id to api_key

修复 external_team 表 name 单列唯一约束 → (name, season_id) 复合唯一约束，
解决多赛季场景下同队名不同赛季上传时的 500 错误。
同时为 ranking_api_key 添加 season_id 列。

Revision ID: 20260415_fix_team_unique_apikey_season
Revises: 20260416_add_ranking_season
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = "20260415_fix_team_unique_apikey_season"
down_revision = "20260416_add_ranking_season"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. 修复 external_team 唯一约束 ──────────────────────
    # SQLite 需要使用 batch_alter 重建表
    with op.batch_alter_table("external_team", schema=None) as batch_op:
        # 删除旧的单列 name unique 索引（SQLite 初始建表时 unique=True 创建了此索引）
        # 索引名称在 SQLite 中为 sqlite_autoindex_external_team_1 或 uq_external_team_name
        # batch_alter 重建表时会自动处理，只需声明新的 table_kwargs
        pass

    # 通过重建表来更改约束（SQLite 不支持 DROP CONSTRAINT）
    # batch_alter_table recreate=True 会重建整个表
    with op.batch_alter_table("external_team", recreate="always", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_external_team_name_season", ["name", "season_id"]
        )

    # ── 2. 为 ranking_api_key 添加 season_id ────────────────
    with op.batch_alter_table("ranking_api_key", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("season_id", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("ranking_api_key", schema=None) as batch_op:
        batch_op.drop_column("season_id")

    with op.batch_alter_table("external_team", recreate="always", schema=None) as batch_op:
        batch_op.drop_constraint("uq_external_team_name_season", type_="unique")
