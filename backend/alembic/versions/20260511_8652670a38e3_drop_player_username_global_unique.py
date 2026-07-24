"""drop_player_username_global_unique

Revision ID: 8652670a38e3
Revises: 33524efda735
Create Date: 2026-05-11 13:38:00.619105

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8652670a38e3'
down_revision: Union[str, None] = '33524efda735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite requires batch mode to alter columns/indexes
    with op.batch_alter_table('player', schema=None) as batch_op:
        # Drop the global unique index on username
        batch_op.drop_index('ix_player_username')
        # Re-create as a non-unique index (for query performance only)
        batch_op.create_index('ix_player_username', ['username'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.drop_index('ix_player_username')
        batch_op.create_index('ix_player_username', ['username'], unique=True)