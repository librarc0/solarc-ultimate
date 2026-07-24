"""add openskill columns to team_settings

Revision ID: 20260319_add_openskill_cols
Revises: 20260319_turnover_sigma
Create Date: 2026-03-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260319_add_openskill_cols"
down_revision = "20260319_turnover_sigma"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("team_settings")}

    with op.batch_alter_table("team_settings") as batch_op:
        if "openskill_mu" not in existing_columns:
            batch_op.add_column(sa.Column("openskill_mu", sa.Float(), nullable=False, server_default="25.0"))
        if "openskill_sigma" not in existing_columns:
            batch_op.add_column(sa.Column("openskill_sigma", sa.Float(), nullable=False, server_default=str(25.0 / 3.0)))
        if "openskill_beta" not in existing_columns:
            batch_op.add_column(sa.Column("openskill_beta", sa.Float(), nullable=False, server_default=str(25.0 / 6.0)))
        if "openskill_tau" not in existing_columns:
            batch_op.add_column(sa.Column("openskill_tau", sa.Float(), nullable=False, server_default=str(25.0 / 300.0)))
        if "openskill_kappa" not in existing_columns:
            batch_op.add_column(sa.Column("openskill_kappa", sa.Float(), nullable=False, server_default="0.0001"))
        if "openskill_margin" not in existing_columns:
            batch_op.add_column(sa.Column("openskill_margin", sa.Float(), nullable=False, server_default="0.0"))
        if "openskill_limit_sigma" not in existing_columns:
            batch_op.add_column(sa.Column("openskill_limit_sigma", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "openskill_balance" not in existing_columns:
            batch_op.add_column(sa.Column("openskill_balance", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("team_settings")}

    with op.batch_alter_table("team_settings") as batch_op:
        if "openskill_balance" in existing_columns:
            batch_op.drop_column("openskill_balance")
        if "openskill_limit_sigma" in existing_columns:
            batch_op.drop_column("openskill_limit_sigma")
        if "openskill_margin" in existing_columns:
            batch_op.drop_column("openskill_margin")
        if "openskill_kappa" in existing_columns:
            batch_op.drop_column("openskill_kappa")
        if "openskill_tau" in existing_columns:
            batch_op.drop_column("openskill_tau")
        if "openskill_beta" in existing_columns:
            batch_op.drop_column("openskill_beta")
        if "openskill_sigma" in existing_columns:
            batch_op.drop_column("openskill_sigma")
        if "openskill_mu" in existing_columns:
            batch_op.drop_column("openskill_mu")
