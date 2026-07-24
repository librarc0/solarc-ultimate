"""add dynamic k-factor and frisbee event columns

Revision ID: 20260319_dynamic_k_frisbee
Revises: 20260319_add_openskill_cols
Create Date: 2026-03-19

New fields on team_settings:
  sigma_bonus_factor           - additional sigma reduction for outstanding performance
  universal_point_bonus        - mu bonus for scoring the game-deciding point
  block_mu_bonus               - mu bonus per defensive play (EventType.defense)
  consecutive_turnover_threshold   - turnovers above this get a higher penalty
  consecutive_turnover_multiplier  - extra penalty multiplier beyond the threshold

New field on match_event:
  is_universe_point  - True when this goal was the game-deciding universe point
"""
from alembic import op
import sqlalchemy as sa


revision = "20260319_dynamic_k_frisbee"
down_revision = "20260319_add_openskill_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── team_settings columns ─────────────────────────────────────────────────
    existing_ts = {col["name"] for col in inspector.get_columns("team_settings")}
    with op.batch_alter_table("team_settings") as batch_op:
        if "sigma_bonus_factor" not in existing_ts:
            batch_op.add_column(sa.Column(
                "sigma_bonus_factor", sa.Float(), nullable=False, server_default="0.15"
            ))
        if "universal_point_bonus" not in existing_ts:
            batch_op.add_column(sa.Column(
                "universal_point_bonus", sa.Float(), nullable=False, server_default="0.5"
            ))
        if "block_mu_bonus" not in existing_ts:
            batch_op.add_column(sa.Column(
                "block_mu_bonus", sa.Float(), nullable=False, server_default="0.05"
            ))
        if "consecutive_turnover_threshold" not in existing_ts:
            batch_op.add_column(sa.Column(
                "consecutive_turnover_threshold", sa.Integer(), nullable=False, server_default="3"
            ))
        if "consecutive_turnover_multiplier" not in existing_ts:
            batch_op.add_column(sa.Column(
                "consecutive_turnover_multiplier", sa.Float(), nullable=False, server_default="1.5"
            ))

    # ── match_event columns ───────────────────────────────────────────────────
    existing_me = {col["name"] for col in inspector.get_columns("match_event")}
    with op.batch_alter_table("match_event") as batch_op:
        if "is_universe_point" not in existing_me:
            batch_op.add_column(sa.Column(
                "is_universe_point", sa.Boolean(), nullable=True
            ))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_me = {col["name"] for col in inspector.get_columns("match_event")}
    with op.batch_alter_table("match_event") as batch_op:
        if "is_universe_point" in existing_me:
            batch_op.drop_column("is_universe_point")

    existing_ts = {col["name"] for col in inspector.get_columns("team_settings")}
    with op.batch_alter_table("team_settings") as batch_op:
        for col in ("consecutive_turnover_multiplier", "consecutive_turnover_threshold",
                    "block_mu_bonus", "universal_point_bonus", "sigma_bonus_factor"):
            if col in existing_ts:
                batch_op.drop_column(col)
