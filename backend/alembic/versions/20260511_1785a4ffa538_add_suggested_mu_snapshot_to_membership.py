"""add_suggested_mu_snapshot_to_membership

Revision ID: 1785a4ffa538
Revises: a1f2e3d4c5b6
Create Date: 2026-05-11 11:23:24.455927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1785a4ffa538'
down_revision: Union[str, None] = 'a1f2e3d4c5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # T040 [US4]: 添加 suggested_mu_snapshot 字段到 PlayerTeamMembership
    with op.batch_alter_table('player_team_membership', schema=None) as batch_op:
        batch_op.add_column(sa.Column('suggested_mu_snapshot', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('player_team_membership', schema=None) as batch_op:
        batch_op.drop_column('suggested_mu_snapshot')
