"""Integration tests for the backend-native metrics registry and run payloads."""

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

from app.api.metrics import get_metric_definitions, get_run_metrics, router as metrics_router
from app.config import settings
from app.database import Base
from app.main import app
from app.models.cell import Cell
from app.models.experiment import Experiment
from app.models.live import CyclerChannel, CyclerSource, CyclerVendor, TestRun as LiveRun
from app.models.metrics import (
    CycleMetricValue,
    MetricDefinition,
    MetricRun,
    MetricScope,
    RunMetricValue,
)
from app.models.project import Project, ProjectType
from app.services.live_monitor import poll_all_sources


pytestmark = pytest.mark.asyncio


def write_biologic_csv(
    file_path: Path,
    *,
    cycles: int = 12,
    charge_start: float = 1.10,
    discharge_start: float = 1.04,
) -> None:
    rows = ["Cycle;Q charge (mA.h);Q discharge (mA.h)"]
    for cycle in range(1, cycles + 1):
        rows.append(
            f"{cycle};{charge_start - (cycle * 0.01):.3f};{discharge_start - (cycle * 0.008):.3f}"
        )
    file_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    old_epoch = time.time() - 600
    os.utime(file_path, (old_epoch, old_epoch))


async def create_session_factory(tmp_path: Path):
    db_path = tmp_path / "metrics-platform-test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch):
    monkeypatch.setattr(settings, "live_channel_offline_minutes", 15)
    monkeypatch.setattr(settings, "live_run_completion_hours", 12)


async def seed_live_mapping(session_factory, export_dir: Path):
    async with session_factory() as session:
        project = Project(name="Metrics Platform Project", project_type=ProjectType.FULL_CELL)
        session.add(project)
        await session.flush()

        experiment = Experiment(project_id=project.id, name="Metrics Experiment")
        session.add(experiment)
        await session.flush()

        cell = Cell(
            experiment_id=experiment.id,
            cell_name="Cell 1",
            test_number="B1",
            loading=30.0,
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
        await session.commit()


async def test_metric_registry_and_routes_are_registered(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)

    async with session_factory() as session:
        run_definitions = await get_metric_definitions(scope=MetricScope.RUN, db=session)
        cycle_definitions = await get_metric_definitions(scope=MetricScope.CYCLE, db=session)
        persisted_definitions = (
            await session.execute(select(MetricDefinition).order_by(MetricDefinition.key.asc()))
        ).scalars().all()

    assert len(run_definitions) == 7
    assert len(cycle_definitions) == 4
    assert len(persisted_definitions) == 11
    assert run_definitions[0].scope == MetricScope.RUN
    assert cycle_definitions[0].scope == MetricScope.CYCLE

    route_paths = {route.path for route in metrics_router.routes}
    assert "/api/metrics/definitions" in route_paths
    assert "/api/metrics/runs/{run_id}" in route_paths

    app_route_paths = {route.path for route in app.routes}
    assert "/api/metrics/definitions" in app_route_paths
    assert "/api/metrics/runs/{run_id}" in app_route_paths

    await engine.dispose()


async def test_live_ingest_persists_metric_batch_and_run_payload(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    write_biologic_csv(export_dir / "BT_Test_B1.csv")

    await seed_live_mapping(session_factory, export_dir)

    async with session_factory() as session:
        collector_result = await poll_all_sources(session)
        await session.commit()

    assert collector_result["files_ingested"] == 1

    async with session_factory() as session:
        run = (await session.execute(select(LiveRun))).scalar_one()
        metric_runs = (
            await session.execute(select(MetricRun).order_by(MetricRun.id.asc()))
        ).scalars().all()
        run_values = (
            await session.execute(select(RunMetricValue).order_by(RunMetricValue.id.asc()))
        ).scalars().all()
        cycle_values = (
            await session.execute(select(CycleMetricValue).order_by(CycleMetricValue.id.asc()))
        ).scalars().all()
        payload = await get_run_metrics(run_id=run.id, db=session)

    assert len(metric_runs) == 1
    assert metric_runs[0].ingestion_run_id is not None
    assert metric_runs[0].status.value == "succeeded"
    assert len(run_values) == 7
    assert len(cycle_values) == 48

    run_metric_map = {item.metric_key: item.value_numeric for item in payload.run_metrics}
    assert run_metric_map["last_cycle_index"] == 12.0
    assert run_metric_map["latest_discharge_capacity_mah"] is not None
    assert run_metric_map["capacity_retention_pct"] is not None
    assert payload.metric_run.id == metric_runs[0].id
    assert len(payload.cycle_metrics) == 48

    await engine.dispose()


async def test_reprocessing_creates_new_metric_run_and_updates_latest_payload(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    file_path = export_dir / "BT_Test_B1.csv"
    write_biologic_csv(file_path, cycles=12, charge_start=1.10, discharge_start=1.04)

    await seed_live_mapping(session_factory, export_dir)

    async with session_factory() as session:
        await poll_all_sources(session)
        await session.commit()

    write_biologic_csv(file_path, cycles=16, charge_start=1.20, discharge_start=1.14)

    async with session_factory() as session:
        await poll_all_sources(session)
        await session.commit()

    async with session_factory() as session:
        run = (await session.execute(select(LiveRun))).scalar_one()
        metric_runs = (
            await session.execute(select(MetricRun).order_by(MetricRun.id.asc()))
        ).scalars().all()
        payload = await get_run_metrics(run_id=run.id, db=session)

    assert len(metric_runs) == 2
    assert metric_runs[0].input_signature != metric_runs[1].input_signature
    run_metric_map = {item.metric_key: item.value_numeric for item in payload.run_metrics}
    assert run_metric_map["last_cycle_index"] == 16.0
    assert payload.metric_run.id == metric_runs[-1].id

    await engine.dispose()
