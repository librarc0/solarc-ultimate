"""algorithm_v2_new_columns

Revision ID: 1ecfc7356fb2
Revises: 01ee54b86cfb
Create Date: 2026-04-20 16:16:48.293623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ecfc7356fb2'
down_revision: Union[str, None] = '01ee54b86cfb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('match', schema=None) as batch_op:
        batch_op.add_column(sa.Column('opponent_external_team_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('opponent_calibrated_mu', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('opponent_calibrated_sigma', sa.Float(), nullable=True))
        batch_op.create_foreign_key('fk_match_external_team', 'external_team', ['opponent_external_team_id'], ['id'])

    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.add_column(sa.Column('composite_rating', sa.Float(), nullable=False, server_default='0.0'))

    with op.batch_alter_table('player_chemistry', schema=None) as batch_op:
        batch_op.add_column(sa.Column('expected_win_rate', sa.Float(), nullable=False, server_default='0.5'))
        batch_op.add_column(sa.Column('synergy_score', sa.Float(), nullable=False, server_default='0.0'))

    with op.batch_alter_table('team_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('chemistry_decay_constant', sa.Float(), nullable=False, server_default='8.0'))
        batch_op.add_column(sa.Column('weight_cap', sa.Float(), nullable=False, server_default='2.0'))


def downgrade() -> None:
    with op.batch_alter_table('team_settings', schema=None) as batch_op:
        batch_op.drop_column('weight_cap')
        batch_op.drop_column('chemistry_decay_constant')

    with op.batch_alter_table('player_chemistry', schema=None) as batch_op:
        batch_op.drop_column('synergy_score')
        batch_op.drop_column('expected_win_rate')

    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.drop_column('composite_rating')

    with op.batch_alter_table('match', schema=None) as batch_op:
        batch_op.drop_constraint('fk_match_external_team', type_='foreignkey')
        batch_op.drop_column('opponent_calibrated_sigma')
        batch_op.drop_column('opponent_calibrated_mu')
        batch_op.drop_column('opponent_external_team_id')