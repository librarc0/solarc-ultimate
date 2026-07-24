"""add_user_model

Revision ID: a1f2e3d4c5b6
Revises: 02b7f39776e1
Create Date: 2026-05-11 00:00:00.000000

功能：
- T008: 新增 user 表（全局登录身份主体）
- T008: 为 player 表添加 user_id 外键 (FK -> user.id)
- T008: 为 player 添加 unique(user_id, team_id) 约束
- T009: 数据迁移 — 为所有现有 player 创建对应 user 记录（1:1 兼容迁移）
         保留原登录凭证、原队伍关联与默认队伍行为不变

说明：
- user_id 在迁移过程中先为 nullable，数据补全后可视业务需要再加 NOT NULL 约束
- 旧 token（sub=player_id）在此迁移后仍可兼容解析（见 deps.py 注释）
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision = "a1f2e3d4c5b6"
down_revision = "02b7f39776e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. 新建 user 表 ────────────────────────────────────────────────────────
    op.create_table(
        "user",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(20), nullable=False),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("wx_openid", sa.String(128), nullable=True),
        sa.Column("is_superadmin", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("default_team_id", sa.Integer, sa.ForeignKey("team.id", name="fk_user_default_team_id"), nullable=True),
        sa.Column("reset_token", sa.String(64), nullable=True),
        sa.Column("reset_token_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_id", "user", ["id"], unique=False)
    op.create_index("ix_user_username", "user", ["username"], unique=True)
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_index("ix_user_wx_openid", "user", ["wx_openid"], unique=True)
    op.create_index("ix_user_reset_token", "user", ["reset_token"], unique=False)

    # ── 2. player 表增加 user_id 列（nullable，过渡期兼容）─────────────────────
    with op.batch_alter_table("player") as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id", name="fk_player_user_id"), nullable=True)
        )

    op.create_index("ix_player_user_id", "player", ["user_id"], unique=False)

    # ── 3. 数据迁移：为每个 player 创建对应 user 记录（1:1 兼容迁移）──────────
    # 保留原登录凭证（username/email/password_hash/wx_openid）
    # 保留 is_superadmin 标志位
    # default_team_id 来自 player.team_id（单队用户的唯一队伍即为默认队伍）
    conn = op.get_bind()
    players = conn.execute(
        sa.text(
            """
            SELECT id, username, email, password_hash, wx_openid,
                   is_superadmin, team_id, reset_token, reset_token_expires
            FROM player
            """
        )
    ).fetchall()

    for p in players:
        # 插入 user 记录（保留原始凭证）
        result = conn.execute(
            sa.text(
                """
                INSERT INTO user
                    (username, email, password_hash, wx_openid, is_superadmin,
                     default_team_id, reset_token, reset_token_expires, created_at)
                VALUES
                    (:username, :email, :password_hash, :wx_openid, :is_superadmin,
                     :default_team_id, :reset_token, :reset_token_expires, :created_at)
                """
            ),
            {
                "username": p.username,
                "email": p.email,
                "password_hash": p.password_hash,
                "wx_openid": p.wx_openid,
                "is_superadmin": p.is_superadmin if hasattr(p, "is_superadmin") else False,
                # 默认队伍：单队用户的唯一队伍即为默认
                "default_team_id": p.team_id,
                "reset_token": p.reset_token if hasattr(p, "reset_token") else None,
                "reset_token_expires": p.reset_token_expires if hasattr(p, "reset_token_expires") else None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        # 获取新建 user.id，回填到 player.user_id
        user_id = conn.execute(
            sa.text("SELECT id FROM user WHERE username = :username"),
            {"username": p.username},
        ).scalar_one()
        conn.execute(
            sa.text("UPDATE player SET user_id = :user_id WHERE id = :player_id"),
            {"user_id": user_id, "player_id": p.id},
        )

    # ── 4. 为 player 添加 unique(user_id, team_id) 约束 ──────────────────────
    # 注意：SQLite 对 NULL 的唯一约束行为是 NULL != NULL，迁移期 nullable user_id 安全
    with op.batch_alter_table("player") as batch_op:
        batch_op.create_unique_constraint(
            "uq_player_user_team", ["user_id", "team_id"]
        )


def downgrade() -> None:
    # ── 回滚顺序：先移除约束和列，再删表 ────────────────────────────────────
    with op.batch_alter_table("player") as batch_op:
        batch_op.drop_constraint("uq_player_user_team", type_="unique")
        batch_op.drop_column("user_id")

    try:
        op.drop_index("ix_player_user_id", "player")
    except Exception:
        pass

    op.drop_index("ix_user_reset_token", "user")
    op.drop_index("ix_user_wx_openid", "user")
    op.drop_index("ix_user_email", "user")
    op.drop_index("ix_user_username", "user")
    op.drop_index("ix_user_id", "user")
    op.drop_table("user")
