"""add_defenses_separate_plus_minus

区分 防守次数(defenses) 和 正负值(plus_minus=得分差) 两个字段。

Revision ID: bbcfbe5bb989
Revises: 20260421_mip_settings
Create Date: 2026-04-21 22:43:53.504577

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbcfbe5bb989'
down_revision: Union[str, None] = '20260421_mip_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 新增列 ────────────────────────────────────────────────────────────────
    # match_player.defenses: 防守次数（从事件统计）
    with op.batch_alter_table('match_player', schema=None) as batch_op:
        batch_op.add_column(sa.Column('defenses', sa.Integer(), nullable=True))

    # player.total_defenses: 累计防守次数
    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.add_column(sa.Column('total_defenses', sa.Integer(), nullable=False, server_default='0'))

    # ── 数据回填 ──────────────────────────────────────────────────────────────
    # 1. 旧 plus_minus 实为防守次数，迁移到 defenses
    op.execute("UPDATE match_player SET defenses = plus_minus")

    # 2. 重算 match_player.plus_minus = 得分差（A队: a-b; B队: b-a）
    op.execute("""
        UPDATE match_player
        SET plus_minus = (
            SELECT CASE match_player.team_side
                WHEN 'A' THEN m.team_a_score - m.team_b_score
                WHEN 'B' THEN m.team_b_score - m.team_a_score
                ELSE 0
            END
            FROM match m
            WHERE m.id = match_player.match_id
        )
    """)

    # 3. 旧 total_plus_minus（防守次数之和）迁移到 total_defenses
    op.execute("UPDATE player SET total_defenses = total_plus_minus")

    # 4. 重算 player.total_plus_minus = 已审批比赛的得分差合计
    op.execute("""
        UPDATE player
        SET total_plus_minus = COALESCE((
            SELECT SUM(mp.plus_minus)
            FROM match_player mp
            JOIN match m ON m.id = mp.match_id
            WHERE mp.player_id = player.id
              AND m.status = 'approved'
              AND mp.plus_minus IS NOT NULL
        ), 0)
    """)


def downgrade() -> None:
    # 回滚：删除新增列（plus_minus 和 total_plus_minus 的历史数据已不可恢复，接受损耗）
    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.drop_column('total_defenses')

    with op.batch_alter_table('match_player', schema=None) as batch_op:
        batch_op.drop_column('defenses')
