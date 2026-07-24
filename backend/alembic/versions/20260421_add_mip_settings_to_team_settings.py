"""add MIP scoring parameters to team_settings

Revision ID: 20260421_mip_settings
Revises: 1ecfc7356fb2
Create Date: 2026-04-21

新增六个 MIP（最佳进步球员）评分参数字段到 team_settings：
  - mip_weight_mu_delta  (float, default 0.40) — µ 绝对增幅权重
  - mip_weight_slope     (float, default 0.30) — 加权趋势斜率权重
  - mip_weight_half      (float, default 0.20) — 后半程 vs 前半程权重
  - mip_weight_sigma     (float, default 0.10) — σ 稳定性降幅权重
  - mip_slope_lambda     (float, default 0.15) — 指数衰减系数
  - mip_min_matches      (int,   default 6)    — 参与进步榜最少场次
"""
from alembic import op
import sqlalchemy as sa

revision = '20260421_mip_settings'
down_revision = '1ecfc7356fb2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('team_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mip_weight_mu_delta', sa.Float(), nullable=False, server_default='0.4'))
        batch_op.add_column(sa.Column('mip_weight_slope',    sa.Float(), nullable=False, server_default='0.3'))
        batch_op.add_column(sa.Column('mip_weight_half',     sa.Float(), nullable=False, server_default='0.2'))
        batch_op.add_column(sa.Column('mip_weight_sigma',    sa.Float(), nullable=False, server_default='0.1'))
        batch_op.add_column(sa.Column('mip_slope_lambda',    sa.Float(), nullable=False, server_default='0.15'))
        batch_op.add_column(sa.Column('mip_min_matches',     sa.Integer(), nullable=False, server_default='6'))


def downgrade() -> None:
    with op.batch_alter_table('team_settings', schema=None) as batch_op:
        batch_op.drop_column('mip_min_matches')
        batch_op.drop_column('mip_slope_lambda')
        batch_op.drop_column('mip_weight_sigma')
        batch_op.drop_column('mip_weight_half')
        batch_op.drop_column('mip_weight_slope')
        batch_op.drop_column('mip_weight_mu_delta')
