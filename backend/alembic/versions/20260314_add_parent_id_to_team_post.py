"""add parent_id to team_post for comment replies

Revision ID: 20260314_add_parent_id_to_team_post
Revises: 20260313_expand_team_settings
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = '20260314_add_parent_id_to_team_post'
down_revision = '20260313_expand_team_settings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('team_post', sa.Column('parent_id', sa.Integer(), nullable=True))
    op.create_index('ix_team_post_parent_id', 'team_post', ['parent_id'])


def downgrade() -> None:
    op.drop_index('ix_team_post_parent_id', 'team_post')
    op.drop_column('team_post', 'parent_id')
