"""expand team_settings with full algorithm coefficients

Revision ID: 20260313_expand_team_settings
Revises: 20260312_add_turnover_fields
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa

revision = '20260313_expand_team_settings'
down_revision = '20260312_add_turnover_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 个人贡献: 防守权重（原写死在 EngineSettings 默认值里）
    op.add_column('team_settings', sa.Column('defense_weight', sa.Float(), nullable=False, server_default='0.1'))
    # 特殊奖惩
    op.add_column('team_settings', sa.Column('break_bonus_per_goal', sa.Float(), nullable=False, server_default='0.1'))
    op.add_column('team_settings', sa.Column('winner_floor_factor', sa.Float(), nullable=False, server_default='0.1'))
    # 外战参数
    op.add_column('team_settings', sa.Column('external_impact_multiplier', sa.Float(), nullable=False, server_default='1.0'))
    op.add_column('team_settings', sa.Column('external_opp_mu_min', sa.Float(), nullable=False, server_default='15.0'))
    op.add_column('team_settings', sa.Column('external_opp_mu_max', sa.Float(), nullable=False, server_default='50.0'))
    op.add_column('team_settings', sa.Column('external_opp_sigma', sa.Float(), nullable=False, server_default='6.0'))
    # 化学值公式权重
    op.add_column('team_settings', sa.Column('chemistry_win_weight', sa.Float(), nullable=False, server_default='0.7'))
    op.add_column('team_settings', sa.Column('chemistry_combo_weight', sa.Float(), nullable=False, server_default='0.3'))


def downgrade() -> None:
    op.drop_column('team_settings', 'chemistry_combo_weight')
    op.drop_column('team_settings', 'chemistry_win_weight')
    op.drop_column('team_settings', 'external_opp_sigma')
    op.drop_column('team_settings', 'external_opp_mu_max')
    op.drop_column('team_settings', 'external_opp_mu_min')
    op.drop_column('team_settings', 'external_impact_multiplier')
    op.drop_column('team_settings', 'winner_floor_factor')
    op.drop_column('team_settings', 'break_bonus_per_goal')
    op.drop_column('team_settings', 'defense_weight')
