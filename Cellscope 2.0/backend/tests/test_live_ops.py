"""Integration-style tests for the live collector and daily reporter."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings
from app.database import Base
from app.models.cell import Cell
from app.models.experiment import Experiment
from app.models.live import (
    AnomalyEvent,
    CyclerChannel,
    CyclerSource,
    CyclerVendor,
    DeliveryStatus,
    NotificationTarget,
    TestRun as LiveRun,
)
from app.models.project import Project, ProjectType
from app.services.live_monitor import poll_all_sources
from app.services.reporting import generate_daily_report


pytestmark = pytest.mark.asyncio


def write_biologic_csv(file_path: Path) -> None:
    rows = ["Cycle;Q charge (mA.h);Q discharge (mA.h)"]
    charge = 1.10
    discharge = 1.04
    for cycle in range(1, 13):
        rows.append(f"{cycle};{charge - (cycle * 0.01):.3f};{discharge - (cycle * 0.008):.3f}")
    file_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    old_epoch = time.time() - 600
    os.utime(file_path, (old_epoch, old_epoch))


async def create_session_factory(tmp_path: Path):
    db_path = tmp_path / "live-ops-test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "smtp_host", None)
    monkeypatch.setattr(settings, "report_sender", "cellscope@example.com")
    monkeypatch.setattr(settings, "live_channel_offline_minutes", 15)
    monkeypatch.setattr(settings, "live_run_completion_hours", 12)
    monkeypatch.setattr(settings, "report_timezone", "America/Chicago")


async def seed_live_mapping(session_factory, export_dir: Path, *, loading: float | None = 30.0):
    async with session_factory() as session:
        project = Project(name="Live Ops Project", project_type=ProjectType.FULL_CELL)
        session.add(project)
        await session.flush()

        experiment = Experiment(project_id=project.id, name="BioLogic Live Experiment")
        session.add(experiment)
        await session.flush()

        cell = Cell(
            experiment_id=experiment.id,
            cell_name="Cell 1",
            test_number="B1",
            loading=loading,
            active_material_pct=90.0,
            formation_cycles=2,
        )
        session.add(cell)
        await session.flush()

        source = CyclerSource(
            name="BioLogic Share",
            vendor=CyclerVendor.BIOLOGIC,
            export_path=str(export_dir),
            poll_interval_seconds=60,
            stable_window_seconds=1,
            file_glob="*.csv",
        )
        session.add(source)
        await session.flush()

        channel = CyclerChannel(
            source_id=source.id,
            source_channel_id="B1",
            display_name="BT-Test B1",
            file_pattern="*B1*",
            project_id=project.id,
            experiment_id=experiment.id,
            cell_id=cell.id,
        )
        session.add(channel)

        notification = NotificationTarget(
            project_id=project.id,
            destination="lab@example.com",
        )
        session.add(notification)
        await session.commit()

        return {
            "project_id": project.id,
            "experiment_id": experiment.id,
            "cell_id": cell.id,
            "source_id": source.id,
            "channel_id": channel.id,
        }


async def test_live_collection_ingests_biologic_export_and_creates_report(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    write_biologic_csv(export_dir / "BT_Test_B1.csv")

    await seed_live_mapping(session_factory, export_dir)

    async with session_factory() as session:
        collector_result = await poll_all_sources(session)
        await session.commit()

    assert collector_result["files_ingested"] == 1
    assert collector_result["files_failed"] == 0

    async with session_factory() as session:
        run_rows = (await session.execute(select(LiveRun))).scalars().all()
        assert len(run_rows) == 1
        run = run_rows[0]
        assert run.last_cycle_index == 12
        assert run.capacity_retention_pct is not None
        assert run.summary_json["cell_name"] == "B1"

        report = await generate_daily_report(session, force=True, send_email=False)
        await session.commit()

        assert report.delivery_status == DeliveryStatus.SKIPPED
        assert "CellScope Daily Report" in report.summary_markdown
        assert report.summary_json["active_runs"][0]["id"] == run.id

    await engine.dispose()


async def test_live_collection_raises_parser_failure_for_missing_cell_metadata(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    write_biologic_csv(export_dir / "BT_Test_B1.csv")

    await seed_live_mapping(session_factory, export_dir, loading=None)

    async with session_factory() as session:
        collector_result = await poll_all_sources(session)
        await session.commit()

    assert collector_result["files_ingested"] == 0
    assert collector_result["files_failed"] == 1

    async with session_factory() as session:
        anomalies = (await session.execute(select(AnomalyEvent))).scalars().all()
        assert any(anomaly.anomaly_type == "parser_failure" for anomaly in anomalies)

    await engine.dispose()
