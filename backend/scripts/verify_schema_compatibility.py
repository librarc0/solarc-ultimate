"""Verify DB schema compatibility against SQLAlchemy models.

This script is intended to run at container startup right after Alembic migration.
It fails fast when ORM models contain columns that do not exist in the database.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import inspect

from app.core.database import Base, engine
import app.models  # noqa: F401 - ensure all model tables are registered


def _collect_missing_columns(sync_conn) -> dict[str, list[str]]:
    """Compare ORM model columns with real DB columns and return missing items."""
    missing: dict[str, list[str]] = {}

    inspector = inspect(sync_conn)

    for mapper in Base.registry.mappers:
        table = mapper.local_table
        table_name = str(getattr(table, "name", ""))

        if not inspector.has_table(table_name):
            missing[table_name] = [col.name for col in table.columns]
            continue

        db_columns = {col["name"] for col in inspector.get_columns(table_name)}
        model_columns = {col.name for col in table.columns}
        missing_cols = sorted(model_columns - db_columns)
        if missing_cols:
            missing[table_name] = missing_cols

    return missing


async def main() -> int:
    async with engine.connect() as conn:
        missing = await conn.run_sync(_collect_missing_columns)

    if missing:
        print("[schema-check] Incompatible DB schema detected:")
        for table_name, cols in sorted(missing.items()):
            print(f"  - {table_name}: missing columns -> {', '.join(cols)}")
        print("[schema-check] Please create/apply Alembic migration before starting service.")
        return 1

    print("[schema-check] Schema compatibility check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
