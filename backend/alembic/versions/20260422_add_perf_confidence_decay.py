"""add perf_confidence_decay to team_settings

Revision ID: 20260422_perf_confidence
Revises: 20260421_mip_settings
Create Date: 2026-04-22

新增 perf_confidence_decay（float，默认 8.0）到 team_settings。

用于综合战力中的表现分场次置信折扣：
  perf_score = 50 + (1 - exp(-matches / N)) * (raw_perf - 50)
场次越少，表现分越向基准 50 收敛，防止新人/小样本球员因短期高数据异常排名靠前。
N=8 时各场次对应置信度：
  1场→11.8%，3场→31.3%，5场→46.5%，8场→63.2%，12场→77.7%，20场→91.8%
"""
from alembic import op
import sqlalchemy as sa

revision = '20260422_perf_confidence'
down_revision = 'bbcfbe5bb989'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('team_settings', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('perf_confidence_decay', sa.Float(), nullable=False, server_default='8.0')
        )


def downgrade() -> None:
    with op.batch_alter_table('team_settings', schema=None) as batch_op:
        batch_op.drop_column('perf_confidence_decay')
