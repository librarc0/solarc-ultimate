"""add match spirit score table

Revision ID: 20260413_match_spirit
Revises: 20260410_sched_tpl
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa


revision = "20260413_match_spirit"
down_revision = "20260410_sched_tpl"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "match_spirit_score" not in existing_tables:
        op.create_table(
            "match_spirit_score",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("match_id", sa.Integer(), sa.ForeignKey("match.id"), nullable=False),
            sa.Column("rules", sa.Integer(), nullable=False),
            sa.Column("contact", sa.Integer(), nullable=False),
            sa.Column("fairness", sa.Integer(), nullable=False),
            sa.Column("attitude", sa.Integer(), nullable=False),
            sa.Column("communication", sa.Integer(), nullable=False),
            sa.Column("total_score", sa.Integer(), nullable=False),
            sa.Column("details_json", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("player.id"), nullable=False),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("player.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("match_id", name="uq_match_spirit_score_match"),
        )
        op.create_index("ix_match_spirit_score_id", "match_spirit_score", ["id"], unique=False)
        op.create_index("ix_match_spirit_score_match_id", "match_spirit_score", ["match_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "match_spirit_score" in existing_tables:
        with op.batch_alter_table("match_spirit_score") as batch_op:
            try:
                batch_op.drop_index("ix_match_spirit_score_match_id")
            except Exception:
                pass
            try:
                batch_op.drop_index("ix_match_spirit_score_id")
            except Exception:
                pass
        op.drop_table("match_spirit_score")
