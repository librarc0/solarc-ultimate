"""add composite attendance weight to team_settings

Revision ID: 20260410_comp_att_weight
Revises: b7d3e1a8f2b1
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260410_comp_att_weight"
down_revision = "b7d3e1a8f2b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("team_settings")}

    with op.batch_alter_table("team_settings") as batch_op:
        if "composite_attendance_weight" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "composite_attendance_weight",
                    sa.Float(),
                    nullable=False,
                    server_default="0.0",
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("team_settings")}

    with op.batch_alter_table("team_settings") as batch_op:
        if "composite_attendance_weight" in existing_columns:
            batch_op.drop_column("composite_attendance_weight")
