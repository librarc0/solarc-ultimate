"""add is_guest to player

Revision ID: 20260413_add_is_guest
Revises: 20260413_match_spirit
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa


revision = "20260413_add_is_guest"
down_revision = "20260413_match_spirit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("player")}
    if "is_guest" not in columns:
        with op.batch_alter_table("player") as batch_op:
            batch_op.add_column(
                sa.Column("is_guest", sa.Boolean(), nullable=False, server_default="0")
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("player")}
    if "is_guest" in columns:
        with op.batch_alter_table("player") as batch_op:
            batch_op.drop_column("is_guest")
