"""Regression tests for SQLite schema compatibility upgrades."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base, ensure_sqlite_schema_compatibility
from app.services.live_monitor import build_dashboard_payload


pytestmark = pytest.mark.asyncio


def create_legacy_live_tables(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE cycler_channels (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                source_channel_id VARCHAR(255) NOT NULL,
                display_name VARCHAR(255),
                file_pattern VARCHAR(500),
                project_id INTEGER,
                experiment_id INTEGER,
                cell_id INTEGER,
                status VARCHAR(10) NOT NULL,
                last_seen_file_path VARCHAR(2000),
                last_seen_at DATETIME,
                metadata_json JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            );

            CREATE TABLE test_runs (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                channel_id INTEGER,
                project_id INTEGER,
                experiment_id INTEGER,
                cell_id INTEGER,
                run_key VARCHAR(500) NOT NULL UNIQUE,
                source_file_path VARCHAR(2000) NOT NULL,
                source_file_hash VARCHAR(128),
                parser_type VARCHAR(12) NOT NULL,
                status VARCHAR(9) NOT NULL,
                started_at DATETIME,
                last_sampled_at DATETIME,
                completed_at DATETIME,
                last_cycle_index INTEGER,
                latest_charge_capacity_mah FLOAT,
                latest_discharge_capacity_mah FLOAT,
                latest_efficiency FLOAT,
                capacity_retention_pct FLOAT,
                summary_json JSON,
                metadata_json JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


async def test_schema_compatibility_upgrades_older_live_tables(tmp_path):
    db_path = tmp_path / "legacy-live.db"
    create_legacy_live_tables(db_path)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await ensure_sqlite_schema_compatibility(engine)

    async with engine.begin() as conn:
        channel_columns_result = await conn.exec_driver_sql("PRAGMA table_info(cycler_channels)")
        channel_columns = {row[1] for row in channel_columns_result.fetchall()}

        run_columns_result = await conn.exec_driver_sql("PRAGMA table_info(test_runs)")
        run_columns = {row[1] for row in run_columns_result.fetchall()}

        channel_indexes_result = await conn.exec_driver_sql("PRAGMA index_list(cycler_channels)")
        channel_indexes = {row[1] for row in channel_indexes_result.fetchall()}

        run_indexes_result = await conn.exec_driver_sql("PRAGMA index_list(test_runs)")
        run_indexes = {row[1] for row in run_indexes_result.fetchall()}

    assert "cell_build_id" in channel_columns
    assert {
        "cell_build_id",
        "protocol_version_id",
        "fixture_id",
        "equipment_asset_id",
        "parser_release_id",
    }.issubset(run_columns)
    assert "ix_cycler_channels_cell_build_id" in channel_indexes
    assert {
        "ix_test_runs_cell_build_id",
        "ix_test_runs_protocol_version_id",
        "ix_test_runs_fixture_id",
        "ix_test_runs_equipment_asset_id",
        "ix_test_runs_parser_release_id",
    }.issubset(run_indexes)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        payload = await build_dashboard_payload(session)

    assert payload["active_runs"] == []
    assert payload["recent_anomalies"] == []
    assert payload["recent_reports"] == []

    await engine.dispose()
