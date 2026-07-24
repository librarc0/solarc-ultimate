"""add raw_payload to ranking_upload_batch

Revision ID: 20260416_add_raw_payload
Revises: 20260415_team_ranking
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = "20260416_add_raw_payload"
down_revision = "20260415_team_ranking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ranking_upload_batch",
        sa.Column("raw_payload", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ranking_upload_batch", "raw_payload")
