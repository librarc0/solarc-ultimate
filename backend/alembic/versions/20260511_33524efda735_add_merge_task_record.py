"""add_merge_task_record

Revision ID: 33524efda735
Revises: 1785a4ffa538
Create Date: 2026-05-11 11:44:18.860390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33524efda735'
down_revision: Union[str, None] = '1785a4ffa538'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'merge_task_record',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('canonical_user_id', sa.Integer(), nullable=False),
        sa.Column('merged_player_ids', sa.Text(), nullable=False),
        sa.Column('snapshot_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['canonical_user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('merge_task_record', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_merge_task_record_canonical_user_id'), ['canonical_user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('merge_task_record', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_merge_task_record_canonical_user_id'))
    op.drop_table('merge_task_record')
