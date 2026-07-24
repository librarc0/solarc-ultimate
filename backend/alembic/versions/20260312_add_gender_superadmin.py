"""add gender to player and is_superadmin flag

Revision ID: 20260312_add_gender_superadmin
Revises: 20260312_add_avatar_logo_url
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = '20260312_add_gender_superadmin'
down_revision = '20260312_add_avatar_logo_url'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('player', sa.Column('gender', sa.String(1), nullable=True))
    op.add_column('player', sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('player', 'is_superadmin')
    op.drop_column('player', 'gender')
