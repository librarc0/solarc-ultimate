"""add avatar_url to player and logo_url to team

Revision ID: 20260312_add_avatar_logo_url
Revises: 3a754045f56a
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = '20260312_add_avatar_logo_url'
down_revision = '68bc6d76ddec'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('player', sa.Column('avatar_url', sa.String(500), nullable=True))
    op.add_column('team', sa.Column('logo_url', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('player', 'avatar_url')
    op.drop_column('team', 'logo_url')
