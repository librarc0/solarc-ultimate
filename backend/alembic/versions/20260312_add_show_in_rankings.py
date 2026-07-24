"""add show_in_rankings to player

Revision ID: 20260312_add_show_in_rankings
Revises: 20260312_add_gender_superadmin
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = '20260312_add_show_in_rankings'
down_revision = '20260312_add_gender_superadmin'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('player', sa.Column('show_in_rankings', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('player', 'show_in_rankings')
