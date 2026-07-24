"""drop single-column unique on external_team.name

The table currently has both:
  CONSTRAINT uq_external_team_name_season UNIQUE (name, season_id)  <- correct
  UNIQUE (name)  <- old, must be removed to allow same team across seasons

SQLite does not support ALTER TABLE DROP CONSTRAINT, so we recreate the table.

Revision ID: 20260415_drop_name_unique_external_team
Revises: 20260415_fix_team_unique_apikey_season
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = "20260415_drop_name_unique_external_team"
down_revision = "20260415_fix_team_unique_apikey_season"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite cannot drop constraints via ALTER TABLE.
    # Recreate the table with only the composite unique.
    op.execute("""
        CREATE TABLE external_team_v2 (
            id          INTEGER NOT NULL,
            season_id   INTEGER,
            name        VARCHAR(100) NOT NULL,
            rank        INTEGER NOT NULL,
            prev_rank   INTEGER NOT NULL,
            rank_change INTEGER NOT NULL,
            total_score FLOAT   NOT NULL,
            avg_score   FLOAT   NOT NULL,
            tournament_count INTEGER NOT NULL,
            wins        INTEGER NOT NULL,
            losses      INTEGER NOT NULL,
            draws       INTEGER NOT NULL,
            forfeits    INTEGER NOT NULL,
            total_games INTEGER NOT NULL,
            win_rate    FLOAT   NOT NULL,
            points_scored   INTEGER NOT NULL,
            points_conceded INTEGER NOT NULL,
            net_points  INTEGER NOT NULL,
            last_updated DATETIME NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_external_team_name_season UNIQUE (name, season_id),
            FOREIGN KEY (season_id) REFERENCES ranking_season (id) ON DELETE CASCADE
        )
    """)
    op.execute("INSERT INTO external_team_v2 SELECT id, season_id, name, rank, prev_rank, rank_change, total_score, avg_score, tournament_count, wins, losses, draws, forfeits, total_games, win_rate, points_scored, points_conceded, net_points, last_updated FROM external_team")
    op.execute("DROP TABLE external_team")
    op.execute("ALTER TABLE external_team_v2 RENAME TO external_team")

    # Recreate indexes
    op.create_index("ix_external_team_id", "external_team", ["id"])
    op.create_index("ix_external_team_name", "external_team", ["name"])
    op.create_index("ix_external_team_season_id", "external_team", ["season_id"])


def downgrade() -> None:
    # Re-add the single-column unique (restoring original broken state)
    op.execute("""
        CREATE TABLE external_team_v2 (
            id          INTEGER NOT NULL,
            season_id   INTEGER,
            name        VARCHAR(100) NOT NULL UNIQUE,
            rank        INTEGER NOT NULL,
            prev_rank   INTEGER NOT NULL,
            rank_change INTEGER NOT NULL,
            total_score FLOAT   NOT NULL,
            avg_score   FLOAT   NOT NULL,
            tournament_count INTEGER NOT NULL,
            wins        INTEGER NOT NULL,
            losses      INTEGER NOT NULL,
            draws       INTEGER NOT NULL,
            forfeits    INTEGER NOT NULL,
            total_games INTEGER NOT NULL,
            win_rate    FLOAT   NOT NULL,
            points_scored   INTEGER NOT NULL,
            points_conceded INTEGER NOT NULL,
            net_points  INTEGER NOT NULL,
            last_updated DATETIME NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_external_team_name_season UNIQUE (name, season_id),
            FOREIGN KEY (season_id) REFERENCES ranking_season (id) ON DELETE CASCADE
        )
    """)
    op.execute("INSERT INTO external_team_v2 SELECT id, season_id, name, rank, prev_rank, rank_change, total_score, avg_score, tournament_count, wins, losses, draws, forfeits, total_games, win_rate, points_scored, points_conceded, net_points, last_updated FROM external_team")
    op.execute("DROP TABLE external_team")
    op.execute("ALTER TABLE external_team_v2 RENAME TO external_team")
    op.create_index("ix_external_team_id", "external_team", ["id"])
    op.create_index("ix_external_team_name", "external_team", ["name"])
    op.create_index("ix_external_team_season_id", "external_team", ["season_id"])
