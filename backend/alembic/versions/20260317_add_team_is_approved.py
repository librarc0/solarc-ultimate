"""add team is_approved

Revision ID: add_team_is_approved
Revises: 20260314_jersey
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_team_is_approved'
down_revision = '20260314_jersey'  # latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("team") as batch_op:
        batch_op.add_column(
            sa.Column("is_approved", sa.Boolean(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("team") as batch_op:
        batch_op.drop_column("is_approved")
