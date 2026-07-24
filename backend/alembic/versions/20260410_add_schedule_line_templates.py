"""add schedule line templates

Revision ID: 20260410_sched_tpl
Revises: 20260410_comp_att_weight
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260410_sched_tpl"
down_revision = "20260410_comp_att_weight"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "schedule_line_template" not in existing_tables:
        op.create_table(
            "schedule_line_template",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("team_id", sa.Integer(), sa.ForeignKey("team.id"), nullable=False),
            sa.Column(
                "event_type",
                sa.Enum("game", "training", "internal", "other", name="scheduleeventtype"),
                nullable=False,
            ),
            sa.Column("template_name", sa.String(length=50), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("player.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("team_id", "event_type", "template_name", name="uq_schedule_line_template_name"),
        )
        op.create_index("ix_schedule_line_template_id", "schedule_line_template", ["id"], unique=False)
        op.create_index("ix_schedule_line_template_team_id", "schedule_line_template", ["team_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "schedule_line_template" in existing_tables:
        with op.batch_alter_table("schedule_line_template") as batch_op:
            try:
                batch_op.drop_index("ix_schedule_line_template_team_id")
            except Exception:
                pass
            try:
                batch_op.drop_index("ix_schedule_line_template_id")
            except Exception:
                pass
        op.drop_table("schedule_line_template")
