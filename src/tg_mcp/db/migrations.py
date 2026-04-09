"""Schema migrations for the SQLite database.

Simple version-table approach: schema.sql is version 1.
Future migrations are added as numbered functions.
"""

from __future__ import annotations

from importlib import resources as pkg_resources

import aiosqlite

from tg_mcp.config import logger

CURRENT_VERSION = 1


async def _get_schema_version(conn: aiosqlite.Connection) -> int:
    """Read the current schema version, or 0 if no schema exists yet."""
    try:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        row = await cursor.fetchone()
        if row is None:
            return 0

        cursor = await conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_version"
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
    except aiosqlite.Error:
        return 0


async def _apply_v1(conn: aiosqlite.Connection) -> None:
    """Version 1: initial schema from schema.sql."""
    schema_path = pkg_resources.files("tg_mcp.db").joinpath("schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")

    await conn.executescript(schema_sql)

    await conn.execute(
        "INSERT INTO schema_version (version) VALUES (?)", (1,)
    )
    await conn.commit()

    logger.info("db.migration_applied", extra={"version": 1})


_MIGRATIONS: list = [
    _apply_v1,
]


async def apply_migrations(conn: aiosqlite.Connection) -> None:
    """Apply any pending migrations."""
    current = await _get_schema_version(conn)

    if current > CURRENT_VERSION:
        raise RuntimeError(
            f"Database schema version {current} is newer than code version {CURRENT_VERSION}. "
            f"Update tg-mcp or delete the database to start fresh."
        )

    if current == CURRENT_VERSION:
        logger.debug("db.schema_up_to_date", extra={"version": current})
        return

    logger.info(
        "db.migrating",
        extra={"from_version": current, "to_version": CURRENT_VERSION},
    )

    for version in range(current + 1, CURRENT_VERSION + 1):
        migration_fn = _MIGRATIONS[version - 1]
        await migration_fn(conn)

    logger.info("db.migration_complete", extra={"version": CURRENT_VERSION})
