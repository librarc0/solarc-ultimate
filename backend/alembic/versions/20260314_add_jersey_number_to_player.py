"""add jersey_number to player

Revision ID: 20260314_jersey
Revises: 20260314_add_parent_id_to_team_post
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = "20260314_jersey"
down_revision = "20260314_add_parent_id_to_team_post"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("player", sa.Column("jersey_number", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("player", "jersey_number")
