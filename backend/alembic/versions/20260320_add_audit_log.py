"""20260320 — 添加 audit_log 表"""
from alembic import op
import sqlalchemy as sa


revision = "20260320_audit_log"
down_revision = "20260319_dynamic_k_frisbee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("team_id", sa.Integer, nullable=True, index=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("player.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_username", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", sa.Integer, nullable=True),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
