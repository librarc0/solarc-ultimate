"""drop_composite_rating

Revision ID: 52963d48edf5
Revises: 20260422_perf_confidence
Create Date: 2026-04-24 11:14:38.768360

Remove unused Player.composite_rating column (A8 废弃).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '52963d48edf5'
down_revision: Union[str, None] = '20260422_perf_confidence'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.drop_column('composite_rating')


def downgrade() -> None:
    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.add_column(sa.Column('composite_rating', sa.Float(), nullable=False, server_default='0.0'))
