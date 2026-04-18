"""SQLAlchemy async database engine and session management."""

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

# Session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


SQLITE_COMPAT_COLUMNS: Mapping[str, Mapping[str, str]] = {
    "cycler_channels": {
        "cell_build_id": "INTEGER",
    },
    "test_runs": {
        "cell_build_id": "INTEGER",
        "protocol_version_id": "INTEGER",
        "fixture_id": "INTEGER",
        "equipment_asset_id": "INTEGER",
        "parser_release_id": "INTEGER",
    },
    "cells": {
        "data_json": "JSON",
    },
}

SQLITE_COMPAT_INDEXES: Mapping[str, Mapping[str, str]] = {
    "cycler_channels": {
        "ix_cycler_channels_cell_build_id": "cell_build_id",
    },
    "test_runs": {
        "ix_test_runs_cell_build_id": "cell_build_id",
        "ix_test_runs_protocol_version_id": "protocol_version_id",
        "ix_test_runs_fixture_id": "fixture_id",
        "ix_test_runs_equipment_asset_id": "equipment_asset_id",
        "ix_test_runs_parser_release_id": "parser_release_id",
    },
}


async def ensure_sqlite_schema_compatibility(async_engine: AsyncEngine) -> None:
    """Backfill required columns for pre-existing SQLite databases.

    SQLAlchemy's ``create_all()`` creates missing tables, but it will not alter
    older tables that are missing newly-added columns. The 2.0 live schema grew
    a few optional foreign-key columns after early databases were already on disk,
    so we add those columns explicitly during startup to keep older dev databases
    usable without a manual reset.
    """

    if async_engine.url.get_backend_name() != "sqlite":
        return

    async with async_engine.begin() as conn:
        for table_name, required_columns in SQLITE_COMPAT_COLUMNS.items():
            existing_columns_result = await conn.exec_driver_sql(f"PRAGMA table_info({table_name})")
            existing_columns = {row[1] for row in existing_columns_result.fetchall()}
            if not existing_columns:
                continue

            for column_name, column_sql in required_columns.items():
                if column_name in existing_columns:
                    continue
                await conn.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
                )

            for index_name, column_name in SQLITE_COMPAT_INDEXES.get(table_name, {}).items():
                await conn.exec_driver_sql(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
                )

        # Fix legacy project_type values that were stored in lowercase
        _PROJECT_TYPE_FIXES = {
            "anode": "Anode",
            "cathode": "Cathode",
            "full_cell": "Full Cell",
            "full cell": "Full Cell",
        }
        for old_val, new_val in _PROJECT_TYPE_FIXES.items():
            await conn.exec_driver_sql(
                "UPDATE projects SET project_type = ? WHERE project_type = ?",
                (new_val, old_val),
            )


async def get_db():
    """Dependency that provides a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
