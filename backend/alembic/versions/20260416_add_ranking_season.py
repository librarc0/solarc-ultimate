"""add ranking_season table and season_id to teams/batches

Revision ID: 20260416_add_ranking_season
Revises: 20260416_add_raw_payload
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = "20260416_add_ranking_season"
down_revision = "20260416_add_raw_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 新建赛季表
    op.create_table(
        "ranking_season",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.String(20), nullable=True),
        sa.Column("end_date", sa.String(20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ranking_season_year", "ranking_season", ["year"])

    # 2. 插入默认赛季（用于迁移历史数据）
    now = datetime.now(timezone.utc).isoformat()
    op.execute(
        f"INSERT INTO ranking_season (name, year, start_date, end_date, description, is_active, created_at) "
        f"VALUES ('初始赛季', 2025, '2025-01-01', '2025-12-31', '系统自动创建的默认赛季', 1, '{now}')"
    )

    # 3. 为 ranking_upload_batch 添加 season_id（SQLite 批量模式）
    with op.batch_alter_table("ranking_upload_batch", schema=None) as batch_op:
        batch_op.add_column(sa.Column("season_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_rup_batch_season_id", ["season_id"])

    # 4. 将现有 batch 记录绑到默认赛季
    op.execute(
        "UPDATE ranking_upload_batch SET season_id = (SELECT id FROM ranking_season LIMIT 1)"
    )

    # 5. 为 external_team 通过 batch 模式重建表（同时去掉 name 单列 unique，加入 season_id）
    with op.batch_alter_table("external_team", schema=None) as batch_op:
        batch_op.add_column(sa.Column("season_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_external_team_season_id", ["season_id"])

    # 6. 将现有 team 记录绑到默认赛季
    op.execute(
        "UPDATE external_team SET season_id = (SELECT id FROM ranking_season LIMIT 1)"
    )


def downgrade() -> None:
    with op.batch_alter_table("external_team", schema=None) as batch_op:
        batch_op.drop_index("ix_external_team_season_id")
        batch_op.drop_column("season_id")

    with op.batch_alter_table("ranking_upload_batch", schema=None) as batch_op:
        batch_op.drop_index("ix_rup_batch_season_id")
        batch_op.drop_column("season_id")

    op.drop_index("ix_ranking_season_year", table_name="ranking_season")
    op.drop_table("ranking_season")
