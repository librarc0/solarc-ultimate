"""multi_team_membership

Revision ID: c3f7a2d81e09
Revises: b2d84eb45fa8
Create Date: 2026-05-09 00:00:00.000000

新增:
- player_team_membership 表（用户-队伍多对多，含独立评分/角色/状态/申请理由）
- player.default_team_id 列

数据迁移:
- 将现有 player 表中 team_id IS NOT NULL 的记录同步到 membership 表
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3f7a2d81e09"
down_revision = "b2d84eb45fa8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. 新建 player_team_membership 表 ───────────────────────────────────
    op.create_table(
        "player_team_membership",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("player.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("team.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("join_reason", sa.String(300), nullable=True),
        sa.Column("mu", sa.Float, nullable=False, server_default="25.0"),
        sa.Column("sigma", sa.Float, nullable=False, server_default="8.333"),
        sa.Column("conservative_rating", sa.Float, nullable=False, server_default="50.0"),
        sa.Column("approved_by", sa.Integer, sa.ForeignKey("player.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("player_id", "team_id", name="uq_player_team"),
    )
    op.create_index("ix_ptm_player_id", "player_team_membership", ["player_id"])
    op.create_index("ix_ptm_team_id", "player_team_membership", ["team_id"])

    # ── 2. player 表增加 default_team_id 列 ─────────────────────────────────
    with op.batch_alter_table("player") as batch_op:
        batch_op.add_column(
            sa.Column("default_team_id", sa.Integer, nullable=True)
        )

    # ── 3. 数据迁移：将现有 player 表的关联关系同步到 membership 表 ───────────
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT id, team_id, role, status, mu, sigma, conservative_rating, approved_by, approved_at
            FROM player
            WHERE team_id IS NOT NULL
            """
        )
    ).fetchall()

    if rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO player_team_membership
                    (player_id, team_id, role, status, mu, sigma, conservative_rating, approved_by, approved_at)
                VALUES
                    (:player_id, :team_id, :role, :status, :mu, :sigma, :conservative_rating, :approved_by, :approved_at)
                """
            ),
            [
                {
                    "player_id": r[0],
                    "team_id": r[1],
                    "role": r[2],
                    "status": r[3],
                    "mu": r[4],
                    "sigma": r[5],
                    "conservative_rating": r[6],
                    "approved_by": r[7],
                    "approved_at": r[8],
                }
                for r in rows
            ],
        )

    # ── 4. 将 default_team_id 设置为现有 team_id ────────────────────────────
    conn.execute(
        sa.text("UPDATE player SET default_team_id = team_id WHERE team_id IS NOT NULL")
    )


def downgrade() -> None:
    with op.batch_alter_table("player") as batch_op:
        batch_op.drop_column("default_team_id")

    op.drop_index("ix_ptm_team_id", table_name="player_team_membership")
    op.drop_index("ix_ptm_player_id", table_name="player_team_membership")
    op.drop_table("player_team_membership")
