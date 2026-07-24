"""normalize_schedule_attendance_no_to_leave

Revision ID: b7d3e1a8f2b1
Revises: 433c4fa5cec4
Create Date: 2026-04-10 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d3e1a8f2b1'
down_revision: Union[str, None] = '433c4fa5cec4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE schedule_attendance SET status = 'leave' WHERE status = 'no'"))


def downgrade() -> None:
    # 无法可靠区分原始 leave 与由 no 迁移而来的 leave，因此保持 no-op。
    pass
