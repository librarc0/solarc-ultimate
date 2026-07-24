"""add turnover fields

Revision ID: 20260312_add_turnover_fields
Revises: 20260312_add_show_in_rankings
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = '20260312_add_turnover_fields'
down_revision = '20260312_add_show_in_rankings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 球员累计失误数
    op.add_column('player', sa.Column('total_turnovers', sa.Integer(), nullable=False, server_default='0'))
    # 单场失误记录（nullable，旧数据不受影响）
    op.add_column('match_player', sa.Column('turnovers', sa.Integer(), nullable=True))
    # 队伍设置：失误惩罚系数
    op.add_column('team_settings', sa.Column('turnover_penalty', sa.Float(), nullable=False, server_default='0.2'))


def downgrade() -> None:
    op.drop_column('team_settings', 'turnover_penalty')
    op.drop_column('match_player', 'turnovers')
    op.drop_column('player', 'total_turnovers')
