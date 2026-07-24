"""add turnover_sigma_factor to team_settings

Revision ID: 20260319_turnover_sigma
Revises: add_team_is_approved
Create Date: 2026-03-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260319_turnover_sigma"
down_revision = "add_team_is_approved"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("team_settings") as batch_op:
        batch_op.add_column(
            sa.Column("turnover_sigma_factor", sa.Float(), nullable=False, server_default="0.3")
        )


def downgrade() -> None:
    with op.batch_alter_table("team_settings") as batch_op:
        batch_op.drop_column("turnover_sigma_factor")
