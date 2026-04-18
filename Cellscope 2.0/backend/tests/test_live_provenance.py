"""Integration tests for live provenance, mapping review, and reprocessing auditability."""

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

from app.api.live import router as live_router
from app.config import settings
from app.database import Base
from app.models.cell import Cell
from app.models.experiment import Experiment
from app.models.live import (
    CyclerArtifact,
    CyclerChannel,
    CyclerSource,
    CyclerVendor,
    IngestionOutcome,
    IngestionRun,
    MappingDecision,
    MappingDecisionStatus,
    ParserRelease,
    RunLifecycleEvent,
    RunLifecycleEventType,
    TestRun as LiveRun,
)
from app.models.ontology import CellBuild
from app.models.project import Project, ProjectType
from app.services.live_monitor import (
    get_run_provenance_payload,
    list_mapping_review_payload,
    poll_all_sources,
    resolve_mapping_review,
)


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
    db_path = tmp_path / "live-provenance-test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch):
    monkeypatch.setattr(settings, "live_channel_offline_minutes", 15)
    monkeypatch.setattr(settings, "live_run_completion_hours", 12)


async def seed_live_mapping(
    session_factory,
    export_dir: Path,
    *,
    loading: float | None = 30.0,
    channel_cell_id: bool = True,
):
    async with session_factory() as session:
        project = Project(name="Live Provenance Project", project_type=ProjectType.FULL_CELL)
        session.add(project)
        await session.flush()

        experiment = Experiment(project_id=project.id, name="BioLogic Provenance Experiment")
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
            cell_id=cell.id if channel_cell_id else None,
        )
        session.add(channel)
        await session.commit()

        return {
            "project_id": project.id,
            "experiment_id": experiment.id,
            "cell_id": cell.id,
            "source_id": source.id,
            "channel_id": channel.id,
        }


async def test_successful_ingest_creates_run_provenance_records(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    write_biologic_csv(export_dir / "BT_Test_B1.csv")

    ids = await seed_live_mapping(session_factory, export_dir)

    async with session_factory() as session:
        collector_result = await poll_all_sources(session)
        await session.commit()

    assert collector_result["files_ingested"] == 1

    async with session_factory() as session:
        run = (await session.execute(select(LiveRun))).scalar_one()
        build = await session.get(CellBuild, run.cell_build_id)
        parser_release = (await session.execute(select(ParserRelease))).scalar_one()
        mapping_decision = (await session.execute(select(MappingDecision))).scalar_one()
        ingestion_run = (await session.execute(select(IngestionRun))).scalar_one()
        lifecycle_events = (await session.execute(select(RunLifecycleEvent))).scalars().all()
        provenance = await get_run_provenance_payload(session, run_id=run.id)

    assert build is not None
    assert build.legacy_cell_id == ids["cell_id"]
    assert build.metadata_json["source"] == "live_ingest_backfill"
    assert parser_release.name == "legacy_adapter"
    assert run.cell_build_id == build.id
    assert run.parser_release_id == parser_release.id
    assert mapping_decision.status == MappingDecisionStatus.AUTO_ACCEPTED
    assert mapping_decision.run_id == run.id
    assert mapping_decision.cell_build_id == build.id
    assert ingestion_run.outcome == IngestionOutcome.SUCCEEDED
    assert ingestion_run.run_id == run.id
    assert ingestion_run.mapping_decision_id == mapping_decision.id
    assert ingestion_run.parser_release_id == parser_release.id
    assert ingestion_run.was_reprocessed is False
    assert [event.event_type for event in lifecycle_events] == [RunLifecycleEventType.INGESTED]
    assert provenance is not None
    assert provenance["run"].id == run.id
    assert len(provenance["artifacts"]) == 1
    assert len(provenance["mapping_decisions"]) == 1
    assert len(provenance["ingestion_runs"]) == 1

    await engine.dispose()


async def test_mapping_review_is_pending_for_unmatched_file_and_deduped(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    file_path = export_dir / "unmapped.csv"
    write_biologic_csv(file_path)

    await seed_live_mapping(session_factory, export_dir)

    async with session_factory() as session:
        first_result = await poll_all_sources(session)
        await session.commit()

    assert first_result["files_ingested"] == 0

    write_biologic_csv(file_path, cycles=14, charge_start=1.20, discharge_start=1.12)

    async with session_factory() as session:
        second_result = await poll_all_sources(session)
        await session.commit()

    assert second_result["files_ingested"] == 0

    async with session_factory() as session:
        decisions = (await session.execute(select(MappingDecision).order_by(MappingDecision.id.asc()))).scalars().all()
        ingestion_runs = (await session.execute(select(IngestionRun).order_by(IngestionRun.id.asc()))).scalars().all()
        artifacts = (await session.execute(select(CyclerArtifact).order_by(CyclerArtifact.id.asc()))).scalars().all()
        review_items = await list_mapping_review_payload(session)
        run_count = len((await session.execute(select(LiveRun))).scalars().all())

    assert run_count == 0
    assert len(decisions) == 2
    assert all(decision.status == MappingDecisionStatus.PENDING_REVIEW for decision in decisions)
    assert len(ingestion_runs) == 2
    assert all(run.outcome == IngestionOutcome.PENDING_REVIEW for run in ingestion_runs)
    assert len(artifacts) == 2
    assert len(review_items) == 1
    assert review_items[0]["artifact"].id == artifacts[-1].id
    assert review_items[0]["mapping_decision"].id == decisions[-1].id

    await engine.dispose()


async def test_confirming_mapping_review_reprocesses_artifact_and_records_audit_history(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    write_biologic_csv(export_dir / "BT_Test_B1.csv")

    ids = await seed_live_mapping(session_factory, export_dir, channel_cell_id=False)

    async with session_factory() as session:
        first_result = await poll_all_sources(session)
        await session.commit()

    assert first_result["files_ingested"] == 0

    async with session_factory() as session:
        decision = (await session.execute(select(MappingDecision))).scalar_one()
        payload = await resolve_mapping_review(
            session,
            mapping_decision_id=decision.id,
            resolution=MappingDecisionStatus.CONFIRMED,
            reviewed_by="qa.operator",
            review_reason="Matched to the legacy B1 channel and cell.",
            channel_id=ids["channel_id"],
            cell_id=ids["cell_id"],
            reprocess_now=True,
        )
        await session.commit()

    assert payload["run"] is not None
    assert payload["latest_ingestion_run"] is not None
    assert payload["latest_ingestion_run"].outcome == IngestionOutcome.SUCCEEDED

    async with session_factory() as session:
        decision = (await session.execute(select(MappingDecision))).scalar_one()
        artifact = (await session.execute(select(CyclerArtifact))).scalar_one()
        run = (await session.execute(select(LiveRun))).scalar_one()
        channel = (await session.execute(select(CyclerChannel))).scalar_one()
        ingestion_runs = (
            await session.execute(select(IngestionRun).order_by(IngestionRun.id.asc()))
        ).scalars().all()
        review_items = await list_mapping_review_payload(session)

    assert decision.status == MappingDecisionStatus.CONFIRMED
    assert decision.decided_by == "qa.operator"
    assert decision.run_id == run.id
    assert decision.cell_id == ids["cell_id"]
    assert decision.cell_build_id == run.cell_build_id
    assert decision.metadata_json["review_history"][-1]["previous_status"] == "pending_review"
    assert decision.metadata_json["review_history"][-1]["new_status"] == "confirmed"
    assert decision.metadata_json["review_history"][-1]["reprocess_now"] is True
    assert artifact.status.value == "ingested"
    assert artifact.run_id == run.id
    assert channel.cell_id == ids["cell_id"]
    assert channel.cell_build_id == run.cell_build_id
    assert len(ingestion_runs) == 2
    assert [item.outcome for item in ingestion_runs] == [
        IngestionOutcome.PENDING_REVIEW,
        IngestionOutcome.SUCCEEDED,
    ]
    assert len(review_items) == 0

    await engine.dispose()


async def test_rejecting_mapping_review_clears_queue_without_creating_run(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    write_biologic_csv(export_dir / "BT_Test_B1.csv")

    await seed_live_mapping(session_factory, export_dir, channel_cell_id=False)

    async with session_factory() as session:
        first_result = await poll_all_sources(session)
        await session.commit()

    assert first_result["files_ingested"] == 0

    async with session_factory() as session:
        decision = (await session.execute(select(MappingDecision))).scalar_one()
        payload = await resolve_mapping_review(
            session,
            mapping_decision_id=decision.id,
            resolution=MappingDecisionStatus.REJECTED,
            reviewed_by="qa.operator",
            review_reason="Ignore this file until the lab remaps the workstation.",
            reprocess_now=False,
        )
        await session.commit()

    assert payload["run"] is None
    assert payload["latest_ingestion_run"] is not None
    assert payload["latest_ingestion_run"].outcome == IngestionOutcome.PENDING_REVIEW

    async with session_factory() as session:
        second_result = await poll_all_sources(session)
        await session.commit()

    assert second_result["files_ingested"] == 0

    async with session_factory() as session:
        decisions = (
            await session.execute(select(MappingDecision).order_by(MappingDecision.id.asc()))
        ).scalars().all()
        decision = decisions[0]
        artifact = (await session.execute(select(CyclerArtifact))).scalar_one()
        runs = (await session.execute(select(LiveRun))).scalars().all()
        review_items = await list_mapping_review_payload(session)
        ingestion_runs = (await session.execute(select(IngestionRun))).scalars().all()

    assert decision.status == MappingDecisionStatus.REJECTED
    assert decision.decided_by == "qa.operator"
    assert decision.review_reason == "Ignore this file until the lab remaps the workstation."
    assert decision.metadata_json["review_history"][-1]["new_status"] == "rejected"
    assert artifact.status.value == "ignored"
    assert len(decisions) == 1
    assert len(runs) == 0
    assert len(review_items) == 0
    assert len(ingestion_runs) == 1

    await engine.dispose()


async def test_reprocessing_tracks_multiple_ingestion_runs_and_lifecycle_events(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    file_path = export_dir / "BT_Test_B1.csv"
    write_biologic_csv(file_path)

    await seed_live_mapping(session_factory, export_dir)

    async with session_factory() as session:
        await poll_all_sources(session)
        await session.commit()

    write_biologic_csv(file_path, cycles=16, charge_start=1.15, discharge_start=1.10)

    async with session_factory() as session:
        await poll_all_sources(session)
        await session.commit()

    async with session_factory() as session:
        run = (await session.execute(select(LiveRun))).scalar_one()
        artifacts = (await session.execute(select(CyclerArtifact).order_by(CyclerArtifact.id.asc()))).scalars().all()
        ingestion_runs = (
            await session.execute(select(IngestionRun).order_by(IngestionRun.id.asc()))
        ).scalars().all()
        lifecycle_events = (
            await session.execute(select(RunLifecycleEvent).order_by(RunLifecycleEvent.id.asc()))
        ).scalars().all()
        decisions = (await session.execute(select(MappingDecision).order_by(MappingDecision.id.asc()))).scalars().all()
        provenance = await get_run_provenance_payload(session, run_id=run.id)

    assert len(artifacts) == 2
    assert len(decisions) == 2
    assert len(ingestion_runs) == 2
    assert ingestion_runs[-1].run_id == run.id
    assert ingestion_runs[-1].was_reprocessed is True
    assert [event.event_type for event in lifecycle_events] == [
        RunLifecycleEventType.INGESTED,
        RunLifecycleEventType.REPROCESSED,
    ]
    assert provenance is not None
    assert len(provenance["artifacts"]) == 2
    assert len(provenance["mapping_decisions"]) == 2
    assert len(provenance["ingestion_runs"]) == 2
    assert len(provenance["lifecycle_events"]) == 2

    await engine.dispose()


async def test_parser_failure_creates_failed_ingestion_run(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    write_biologic_csv(export_dir / "BT_Test_B1.csv")

    await seed_live_mapping(session_factory, export_dir, loading=None)

    async with session_factory() as session:
        collector_result = await poll_all_sources(session)
        await session.commit()

    assert collector_result["files_failed"] == 1

    async with session_factory() as session:
        decisions = (await session.execute(select(MappingDecision))).scalars().all()
        ingestion_runs = (await session.execute(select(IngestionRun))).scalars().all()
        runs = (await session.execute(select(LiveRun))).scalars().all()

    assert len(runs) == 0
    assert len(decisions) == 1
    assert decisions[0].status == MappingDecisionStatus.AUTO_ACCEPTED
    assert len(ingestion_runs) == 1
    assert ingestion_runs[0].outcome == IngestionOutcome.FAILED
    assert ingestion_runs[0].mapping_decision_id == decisions[0].id

    await engine.dispose()


async def test_live_router_registers_provenance_routes():
    route_paths = {route.path for route in live_router.routes}
    assert "/api/live/runs/{run_id}/provenance" in route_paths
    assert "/api/live/mapping-review" in route_paths
    assert "/api/live/mapping-review/{mapping_decision_id}/resolve" in route_paths
    assert "/api/live/mapping-decisions" in route_paths
