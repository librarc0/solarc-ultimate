"""add team ranking tables with linli seed

Revision ID: 20260415_team_ranking
Revises: 20260413_add_is_guest
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = "20260415_team_ranking"
down_revision = "20260413_add_is_guest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ranking_admin ──────────────────────────────────────
    op.create_table(
        "ranking_admin",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── ranking_api_key ────────────────────────────────────
    op.create_table(
        "ranking_api_key",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_prefix", sa.String(10), nullable=False),
        sa.Column("key_hash", sa.String(256), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── ranking_upload_batch ───────────────────────────────
    op.create_table(
        "ranking_upload_batch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False, default=0),
        sa.Column("exported_at", sa.String(50), nullable=True),
    )

    # ── external_team ──────────────────────────────────────
    op.create_table(
        "external_team",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, default=0),
        sa.Column("prev_rank", sa.Integer(), nullable=False, default=0),
        sa.Column("rank_change", sa.Integer(), nullable=False, default=0),
        sa.Column("total_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("avg_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("tournament_count", sa.Integer(), nullable=False, default=0),
        sa.Column("wins", sa.Integer(), nullable=False, default=0),
        sa.Column("losses", sa.Integer(), nullable=False, default=0),
        sa.Column("draws", sa.Integer(), nullable=False, default=0),
        sa.Column("forfeits", sa.Integer(), nullable=False, default=0),
        sa.Column("total_games", sa.Integer(), nullable=False, default=0),
        sa.Column("win_rate", sa.Float(), nullable=False, default=0.0),
        sa.Column("points_scored", sa.Integer(), nullable=False, default=0),
        sa.Column("points_conceded", sa.Integer(), nullable=False, default=0),
        sa.Column("net_points", sa.Integer(), nullable=False, default=0),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_external_team_id", "external_team", ["id"])
    op.create_index("ix_external_team_name", "external_team", ["name"])

    # ── tournament_record ──────────────────────────────────
    op.create_table(
        "tournament_record",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("ranking_upload_batch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("external_team.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_name", sa.String(100), nullable=False),
        sa.Column("tournament_name", sa.String(200), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False, default=0),
        sa.Column("losses", sa.Integer(), nullable=False, default=0),
        sa.Column("draws", sa.Integer(), nullable=False, default=0),
        sa.Column("forfeits", sa.Integer(), nullable=False, default=0),
        sa.Column("total_games", sa.Integer(), nullable=False, default=0),
        sa.Column("win_rate", sa.Float(), nullable=False, default=0.0),
        sa.Column("points_scored", sa.Integer(), nullable=False, default=0),
        sa.Column("points_conceded", sa.Integer(), nullable=False, default=0),
        sa.Column("pool", sa.String(10), nullable=False),
        sa.Column("final_rank", sa.Integer(), nullable=False, default=0),
        sa.Column("computed_score", sa.Float(), nullable=False, default=0.0),
    )
    op.create_index("ix_tournament_record_id", "tournament_record", ["id"])
    op.create_index("ix_tournament_record_batch_id", "tournament_record", ["batch_id"])
    op.create_index("ix_tournament_record_team_id", "tournament_record", ["team_id"])
    op.create_index("ix_tournament_record_team_name", "tournament_record", ["team_name"])

    # Ranking admin accounts must be created by an explicit setup command.
    # Do not seed default credentials in migrations.


def downgrade() -> None:
    op.drop_table("tournament_record")
    op.drop_table("external_team")
    op.drop_table("ranking_upload_batch")
    op.drop_table("ranking_api_key")
    op.drop_table("ranking_admin")
