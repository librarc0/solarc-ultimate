"""add province and city to external_team

Revision ID: 20260419_add_province_city
Revises: 20260416_add_ranking_season
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa

revision = "20260419_add_province_city"
down_revision = "20260415_drop_name_unique_external_team"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_team",
        sa.Column("province", sa.String(20), nullable=True),
    )
    op.add_column(
        "external_team",
        sa.Column("city", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_team", "city")
    op.drop_column("external_team", "province")
