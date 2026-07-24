"""add_team_id_to_rating_history

Revision ID: 02b7f39776e1
Revises: c3f7a2d81e09
Create Date: 2026-05-09 10:35:33.250097

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02b7f39776e1'
down_revision: Union[str, None] = 'c3f7a2d81e09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fully idempotent upgrade: check existing DB state before every operation.
    from sqlalchemy import inspect as sa_inspect, text

    conn = op.get_bind()
    inspector = sa_inspect(conn)

    # Clean up leftover temp tables from any previously failed batch runs.
    for tmp in [t for t in inspector.get_table_names() if t.startswith('_alembic_tmp_')]:
        op.execute(text(f'DROP TABLE IF EXISTS "{tmp}"'))
    inspector = sa_inspect(conn)  # refresh after cleanup

    def _fk_cols(table: str) -> set:
        return {
            fk["constrained_columns"][0]
            for fk in inspector.get_foreign_keys(table)
            if fk.get("constrained_columns")
        }

    # ── match ──────────────────────────────────────────────────────────────────
    match_cols = {c["name"] for c in inspector.get_columns("match")}
    match_fk_cols = _fk_cols("match")
    if "season_id" in match_cols or "draft_owner_id" not in match_fk_cols:
        with op.batch_alter_table('match', schema=None) as batch_op:
            if "draft_owner_id" not in match_fk_cols:
                batch_op.create_foreign_key('fk_match_draft_owner_id', 'player', ['draft_owner_id'], ['id'])
            if "season_id" in match_cols:
                batch_op.drop_column('season_id')

    # ── match_event ────────────────────────────────────────────────────────────
    me_fk_cols = _fk_cols("match_event")
    if "created_by" not in me_fk_cols:
        me_idxs = {i["name"] for i in inspector.get_indexes("match_event")}
        with op.batch_alter_table('match_event', schema=None) as batch_op:
            if 'uq_match_event_client_event' in me_idxs:
                batch_op.drop_index(batch_op.f('uq_match_event_client_event'))
            batch_op.create_unique_constraint('uq_match_event_client_event', ['match_id', 'client_event_id'])
            if 'uq_match_event_seq' in me_idxs:
                batch_op.drop_index(batch_op.f('uq_match_event_seq'))
            batch_op.create_unique_constraint('uq_match_event_seq', ['match_id', 'seq'])
            batch_op.create_foreign_key('fk_match_event_created_by', 'player', ['created_by'], ['id'])

    # ── player ─────────────────────────────────────────────────────────────────
    if "default_team_id" not in _fk_cols("player"):
        with op.batch_alter_table('player', schema=None) as batch_op:
            batch_op.create_foreign_key('fk_player_default_team_id', 'team', ['default_team_id'], ['id'])

    # ── player_team_membership ──────────────────────────────────────────────────
    ptm_idxs = {i["name"] for i in inspector.get_indexes("player_team_membership")}
    if 'ix_player_team_membership_player_id' not in ptm_idxs:
        with op.batch_alter_table('player_team_membership', schema=None) as batch_op:
            batch_op.alter_column('role',
                existing_type=sa.VARCHAR(length=20),
                type_=sa.Enum('owner', 'admin', 'member', name='userrole'),
                existing_nullable=False,
                existing_server_default=sa.text("'member'"))
            batch_op.alter_column('status',
                existing_type=sa.VARCHAR(length=20),
                type_=sa.Enum('pending', 'active', 'rejected', name='playerstatus'),
                existing_nullable=False,
                existing_server_default=sa.text("'active'"))
            if 'ix_ptm_player_id' in ptm_idxs:
                batch_op.drop_index(batch_op.f('ix_ptm_player_id'))
            if 'ix_ptm_team_id' in ptm_idxs:
                batch_op.drop_index(batch_op.f('ix_ptm_team_id'))
            batch_op.create_index(batch_op.f('ix_player_team_membership_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_player_team_membership_player_id'), ['player_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_player_team_membership_team_id'), ['team_id'], unique=False)

    # ── rating_history ──────────────────────────────────────────────────────────
    rh_cols = {c["name"] for c in inspector.get_columns("rating_history")}
    if "team_id" not in rh_cols:
        with op.batch_alter_table('rating_history', schema=None) as batch_op:
            batch_op.add_column(sa.Column('team_id', sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f('ix_rating_history_team_id'), ['team_id'], unique=False)
            batch_op.create_foreign_key('fk_rating_history_team_id', 'team', ['team_id'], ['id'])

    # ── schedule_line (indexes already exist in DB - skip) ─────────────────────
    sl_idxs = {i["name"] for i in inspector.get_indexes("schedule_line")}
    if 'ix_schedule_line_div_id' not in sl_idxs or 'ix_schedule_line_id' not in sl_idxs:
        with op.batch_alter_table('schedule_line', schema=None) as batch_op:
            if 'ix_schedule_line_div_id' not in sl_idxs:
                batch_op.create_index('ix_schedule_line_div_id', ['division_id'], unique=False)
            if 'ix_schedule_line_id' not in sl_idxs:
                batch_op.create_index(batch_op.f('ix_schedule_line_id'), ['id'], unique=False)

    # ── team_post ───────────────────────────────────────────────────────────────
    tp_idxs = {i["name"] for i in inspector.get_indexes("team_post")}
    tp_fk_cols = _fk_cols("team_post")
    if 'parent_id' not in tp_fk_cols or 'ix_team_post_parent_id' not in tp_idxs:
        with op.batch_alter_table('team_post', schema=None) as batch_op:
            if 'ix_team_post_parent_id' not in tp_idxs:
                batch_op.create_index(batch_op.f('ix_team_post_parent_id'), ['parent_id'], unique=False)
            if 'parent_id' not in tp_fk_cols:
                batch_op.create_foreign_key('fk_team_post_parent_id', 'team_post', ['parent_id'], ['id'])

    # ── team_settings (FKs already exist in DB - skip if done) ─────────────────
    ts_fk_cols = _fk_cols("team_settings")
    if 'team_id' not in ts_fk_cols or 'updated_by' not in ts_fk_cols:
        ts_uq = {uc["name"] for uc in inspector.get_unique_constraints("team_settings")}
        with op.batch_alter_table('team_settings', schema=None) as batch_op:
            batch_op.alter_column('id', existing_type=sa.INTEGER(), nullable=False, autoincrement=True)
            batch_op.alter_column('team_id', existing_type=sa.INTEGER(), nullable=False)
            batch_op.alter_column('alpha', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('beta', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('gamma', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('defense_weight', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('composite_ts_weight', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('composite_perf_weight', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('composite_attendance_weight', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('turnover_penalty', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('turnover_sigma_factor', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('break_bonus_per_goal', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('winner_floor_factor', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('external_impact_multiplier', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('external_opp_mu_min', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('external_opp_mu_max', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('external_opp_sigma', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('openskill_mu', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('openskill_sigma', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('openskill_beta', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('openskill_tau', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('openskill_kappa', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('openskill_margin', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('openskill_limit_sigma', existing_type=sa.NUMERIC(), type_=sa.Boolean(), nullable=False)
            batch_op.alter_column('openskill_balance', existing_type=sa.NUMERIC(), type_=sa.Boolean(), nullable=False)
            batch_op.alter_column('chemistry_win_weight', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('chemistry_combo_weight', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('chemistry_decay_constant', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('sigma_bonus_factor', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('weight_cap', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('universal_point_bonus', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('block_mu_bonus', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('consecutive_turnover_threshold', existing_type=sa.INTEGER(), nullable=False)
            batch_op.alter_column('consecutive_turnover_multiplier', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('mip_weight_mu_delta', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('mip_weight_slope', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('mip_weight_half', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('mip_weight_sigma', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('mip_slope_lambda', existing_type=sa.REAL(), type_=sa.Float(), nullable=False)
            batch_op.alter_column('mip_min_matches', existing_type=sa.INTEGER(), nullable=False)
            batch_op.alter_column('updated_at', existing_type=sa.NUMERIC(), type_=sa.DateTime(timezone=True), nullable=False)
            batch_op.alter_column('updated_by', existing_type=sa.INTEGER(), nullable=False)
            if 'uq_team_settings_team_id' not in ts_uq:
                batch_op.create_unique_constraint('uq_team_settings_team_id', ['team_id'])
            if 'updated_by' not in ts_fk_cols:
                batch_op.create_foreign_key('fk_team_settings_updated_by', 'player', ['updated_by'], ['id'])
            if 'team_id' not in ts_fk_cols:
                batch_op.create_foreign_key('fk_team_settings_team_id', 'team', ['team_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('team_settings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_team_settings_updated_by', type_='foreignkey')
        batch_op.drop_constraint('fk_team_settings_team_id', type_='foreignkey')
        batch_op.drop_constraint('uq_team_settings_team_id', type_='unique')
        batch_op.alter_column('updated_by', existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column('updated_at', existing_type=sa.DateTime(timezone=True), type_=sa.NUMERIC(), nullable=True)
        batch_op.alter_column('mip_min_matches', existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column('mip_slope_lambda', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('mip_weight_sigma', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('mip_weight_half', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('mip_weight_slope', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('mip_weight_mu_delta', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('consecutive_turnover_multiplier', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('consecutive_turnover_threshold', existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column('block_mu_bonus', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('universal_point_bonus', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('weight_cap', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('sigma_bonus_factor', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('chemistry_decay_constant', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('chemistry_combo_weight', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('chemistry_win_weight', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('openskill_balance', existing_type=sa.Boolean(), type_=sa.NUMERIC(), nullable=True)
        batch_op.alter_column('openskill_limit_sigma', existing_type=sa.Boolean(), type_=sa.NUMERIC(), nullable=True)
        batch_op.alter_column('openskill_margin', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('openskill_kappa', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('openskill_tau', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('openskill_beta', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('openskill_sigma', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('openskill_mu', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('external_opp_sigma', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('external_opp_mu_max', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('external_opp_mu_min', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('external_impact_multiplier', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('winner_floor_factor', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('break_bonus_per_goal', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('turnover_sigma_factor', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('turnover_penalty', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('composite_attendance_weight', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('composite_perf_weight', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('composite_ts_weight', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('defense_weight', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('gamma', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('beta', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('alpha', existing_type=sa.Float(), type_=sa.REAL(), nullable=True)
        batch_op.alter_column('team_id', existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column('id', existing_type=sa.INTEGER(), nullable=True, autoincrement=True)

    with op.batch_alter_table('team_post', schema=None) as batch_op:
        batch_op.drop_constraint('fk_team_post_parent_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_team_post_parent_id'))

    with op.batch_alter_table('schedule_line', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_schedule_line_id'))
        batch_op.drop_index('ix_schedule_line_div_id')

    with op.batch_alter_table('rating_history', schema=None) as batch_op:
        batch_op.drop_constraint('fk_rating_history_team_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_rating_history_team_id'))
        batch_op.drop_column('team_id')

    with op.batch_alter_table('player_team_membership', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_player_team_membership_team_id'))
        batch_op.drop_index(batch_op.f('ix_player_team_membership_player_id'))
        batch_op.drop_index(batch_op.f('ix_player_team_membership_id'))
        batch_op.create_index(batch_op.f('ix_ptm_team_id'), ['team_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ptm_player_id'), ['player_id'], unique=False)
        batch_op.alter_column('status',
            existing_type=sa.Enum('pending', 'active', 'rejected', name='playerstatus'),
            type_=sa.VARCHAR(length=20),
            existing_nullable=False,
            existing_server_default=sa.text("'active'"))
        batch_op.alter_column('role',
            existing_type=sa.Enum('owner', 'admin', 'member', name='userrole'),
            type_=sa.VARCHAR(length=20),
            existing_nullable=False,
            existing_server_default=sa.text("'member'"))

    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.drop_constraint('fk_player_default_team_id', type_='foreignkey')

    with op.batch_alter_table('match_event', schema=None) as batch_op:
        batch_op.drop_constraint('fk_match_event_created_by', type_='foreignkey')
        batch_op.drop_constraint('uq_match_event_seq', type_='unique')
        batch_op.create_index(batch_op.f('uq_match_event_seq'), ['match_id', 'seq'], unique=1)
        batch_op.drop_constraint('uq_match_event_client_event', type_='unique')
        batch_op.create_index(batch_op.f('uq_match_event_client_event'), ['match_id', 'client_event_id'], unique=1)

    with op.batch_alter_table('match', schema=None) as batch_op:
        batch_op.add_column(sa.Column('season_id', sa.INTEGER(), nullable=True))
        batch_op.drop_constraint('fk_match_draft_owner_id', type_='foreignkey')
