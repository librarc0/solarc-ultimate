"""add wx_openid to player

Revision ID: b2d84eb45fa8
Revises: 52963d48edf5
Create Date: 2026-05-08 09:44:21.822059

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d84eb45fa8'
down_revision: Union[str, None] = '52963d48edf5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.add_column(sa.Column('wx_openid', sa.String(length=128), nullable=True))
        batch_op.create_index('ix_player_wx_openid', ['wx_openid'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.drop_index('ix_player_wx_openid')
        batch_op.drop_column('wx_openid')
