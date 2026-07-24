"""20260320 — 实况断点续录字段与约束

Revision ID: 20260320_live_draft
Revises: 20260320_audit_log
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260320_live_draft"
down_revision = "20260320_audit_log"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns(table_name)}
    return column_name in cols


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
    return index_name in indexes


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    if not _has_column("match", "draft_owner_id"):
        op.add_column("match", sa.Column("draft_owner_id", sa.Integer(), nullable=True))
    if not _has_column("match", "last_event_seq"):
        op.add_column("match", sa.Column("last_event_seq", sa.Integer(), nullable=False, server_default="0"))
    if not _has_column("match", "last_synced_at"):
        op.add_column("match", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_column("match", "saved_at"):
        op.add_column("match", sa.Column("saved_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_column("match", "expires_at"):
        op.add_column("match", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_column("match", "deleted_at"):
        op.add_column("match", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_column("match", "draft_snapshot_json"):
        op.add_column("match", sa.Column("draft_snapshot_json", sa.Text(), nullable=True))

    if not _has_index("match", "ix_match_draft_owner_id"):
        op.create_index("ix_match_draft_owner_id", "match", ["draft_owner_id"])
    if not _has_index("match", "ix_match_expires_at"):
        op.create_index("ix_match_expires_at", "match", ["expires_at"])
    if not _has_index("match", "ix_match_deleted_at"):
        op.create_index("ix_match_deleted_at", "match", ["deleted_at"])

    if dialect != "sqlite":
        op.create_foreign_key("fk_match_draft_owner_id", "match", "player", ["draft_owner_id"], ["id"])

    if not _has_column("match_event", "seq"):
        op.add_column("match_event", sa.Column("seq", sa.Integer(), nullable=True))
    if not _has_column("match_event", "client_event_id"):
        op.add_column("match_event", sa.Column("client_event_id", sa.String(length=64), nullable=True))
    if not _has_column("match_event", "event_version"):
        op.add_column("match_event", sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"))
    if not _has_column("match_event", "payload_json"):
        op.add_column("match_event", sa.Column("payload_json", sa.Text(), nullable=True))
    if not _has_column("match_event", "created_by"):
        op.add_column("match_event", sa.Column("created_by", sa.Integer(), nullable=True))
    if not _has_column("match_event", "source"):
        op.add_column("match_event", sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"))
    if not _has_column("match_event", "deleted_at"):
        op.add_column("match_event", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    if dialect == "sqlite":
        if not _has_index("match_event", "uq_match_event_seq"):
            op.create_index("uq_match_event_seq", "match_event", ["match_id", "seq"], unique=True)
        if not _has_index("match_event", "uq_match_event_client_event"):
            op.create_index("uq_match_event_client_event", "match_event", ["match_id", "client_event_id"], unique=True)
    else:
        op.create_foreign_key("fk_match_event_created_by", "match_event", "player", ["created_by"], ["id"])
        op.create_unique_constraint("uq_match_event_seq", "match_event", ["match_id", "seq"])
        op.create_unique_constraint("uq_match_event_client_event", "match_event", ["match_id", "client_event_id"])


def downgrade() -> None:
    dialect = op.get_bind().dialect.name

    if dialect == "sqlite":
        if _has_index("match_event", "uq_match_event_client_event"):
            op.drop_index("uq_match_event_client_event", table_name="match_event")
        if _has_index("match_event", "uq_match_event_seq"):
            op.drop_index("uq_match_event_seq", table_name="match_event")
    else:
        op.drop_constraint("uq_match_event_client_event", "match_event", type_="unique")
        op.drop_constraint("uq_match_event_seq", "match_event", type_="unique")
        op.drop_constraint("fk_match_event_created_by", "match_event", type_="foreignkey")

    op.drop_column("match_event", "deleted_at")
    op.drop_column("match_event", "source")
    op.drop_column("match_event", "created_by")
    op.drop_column("match_event", "payload_json")
    op.drop_column("match_event", "event_version")
    op.drop_column("match_event", "client_event_id")
    op.drop_column("match_event", "seq")

    op.drop_index("ix_match_deleted_at", table_name="match")
    op.drop_index("ix_match_expires_at", table_name="match")
    op.drop_index("ix_match_draft_owner_id", table_name="match")
    if dialect != "sqlite":
        op.drop_constraint("fk_match_draft_owner_id", "match", type_="foreignkey")

    op.drop_column("match", "draft_snapshot_json")
    op.drop_column("match", "deleted_at")
    op.drop_column("match", "expires_at")
    op.drop_column("match", "saved_at")
    op.drop_column("match", "last_synced_at")
    op.drop_column("match", "last_event_seq")
    op.drop_column("match", "draft_owner_id")
