"""Collector and live dashboard services for CellScope live cycler workflows."""

from __future__ import annotations

import fnmatch
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pandas as pd
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.cell import Cell
from app.models.experiment import Experiment
from app.models.live import (
    AnomalyEvent,
    AnomalySeverity,
    ArtifactStatus,
    ChannelStatus,
    CyclePoint,
    CyclerArtifact,
    CyclerChannel,
    CyclerSource,
    DailyReportRun,
    IngestionOutcome,
    IngestionCheckpoint,
    IngestionRun,
    MappingDecision,
    MappingDecisionStatus,
    ParserRelease,
    ParserType,
    RunLifecycleEvent,
    RunLifecycleEventType,
    RunStatus,
    TestRun,
)
from app.models.ontology import CellBuild, CellBuildStatus
from app.services.legacy_adapter import (
    dataframe_to_cycle_payloads,
    detect_run_flags,
    parse_cycler_file,
    summarize_run,
)
from app.services.metrics import compute_metrics_for_run

LEGACY_PARSER_RELEASE_NAME = "legacy_adapter"
LEGACY_PARSER_RELEASE_VERSION = "bridge-v1"


def utcnow() -> datetime:
    """Return a timezone-naive UTC timestamp for SQLite compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_datetime(epoch_seconds: float) -> datetime:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).replace(tzinfo=None)


def assume_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def severity_from_flag_name(value: Optional[str]) -> AnomalySeverity:
    mapping = {
        "INFO": AnomalySeverity.INFO,
        "WARNING": AnomalySeverity.WARNING,
        "CRITICAL": AnomalySeverity.CRITICAL,
    }
    return mapping.get(str(value).upper(), AnomalySeverity.WARNING)


async def get_or_create_parser_release(
    session: AsyncSession,
    *,
    source: CyclerSource,
    parser_type: ParserType,
) -> ParserRelease:
    result = await session.execute(
        select(ParserRelease).where(
            ParserRelease.name == LEGACY_PARSER_RELEASE_NAME,
            ParserRelease.version == LEGACY_PARSER_RELEASE_VERSION,
            ParserRelease.parser_type == parser_type,
            ParserRelease.vendor == source.vendor,
        )
    )
    parser_release = result.scalar_one_or_none()
    if parser_release:
        return parser_release

    parser_release = ParserRelease(
        name=LEGACY_PARSER_RELEASE_NAME,
        version=LEGACY_PARSER_RELEASE_VERSION,
        parser_type=parser_type,
        vendor=source.vendor,
        code_reference="app.services.legacy_adapter.parse_cycler_file",
        metadata_json={"adapter": "legacy_adapter", "source_vendor": source.vendor.value},
    )
    session.add(parser_release)
    await session.flush()
    return parser_release


async def resolve_cell_build_for_channel(
    session: AsyncSession,
    *,
    channel: CyclerChannel,
    cell: Cell,
) -> CellBuild:
    if channel.cell_build_id:
        build = await session.get(CellBuild, channel.cell_build_id)
        if build:
            return build

    result = await session.execute(select(CellBuild).where(CellBuild.legacy_cell_id == cell.id))
    build = result.scalar_one_or_none()
    if not build:
        build = CellBuild(
            build_name=f"legacy-cell-{cell.id}",
            status=CellBuildStatus.TESTING,
            legacy_project_id=cell.experiment.project_id if cell.experiment else None,
            legacy_experiment_id=cell.experiment_id,
            legacy_cell_id=cell.id,
            legacy_test_number=cell.test_number,
            metadata_json={
                "source": "live_ingest_backfill",
                "confidence": "inferred",
                "cell_name": cell.cell_name,
            },
        )
        session.add(build)
        await session.flush()

    channel.cell_build_id = build.id
    return build


async def upsert_mapping_decision(
    session: AsyncSession,
    *,
    source_id: int,
    channel_id: Optional[int],
    artifact_id: int,
    project_id: Optional[int],
    experiment_id: Optional[int],
    cell_id: Optional[int],
    cell_build_id: Optional[int],
    status: MappingDecisionStatus,
    mapping_rule: Optional[str],
    confidence: Optional[float],
    review_reason: Optional[str],
    metadata_json: Optional[Dict[str, Any]],
    run_id: Optional[int] = None,
    decided_by: Optional[str] = None,
    decided_at: Optional[datetime] = None,
) -> MappingDecision:
    result = await session.execute(
        select(MappingDecision).where(MappingDecision.artifact_id == artifact_id)
    )
    mapping_decision = result.scalar_one_or_none()
    if not mapping_decision:
        mapping_decision = MappingDecision(
            source_id=source_id,
            channel_id=channel_id,
            artifact_id=artifact_id,
        )
        session.add(mapping_decision)

    mapping_decision.run_id = run_id
    mapping_decision.project_id = project_id
    mapping_decision.experiment_id = experiment_id
    mapping_decision.cell_id = cell_id
    mapping_decision.cell_build_id = cell_build_id
    mapping_decision.status = status
    mapping_decision.mapping_rule = mapping_rule
    mapping_decision.confidence = confidence
    mapping_decision.review_reason = review_reason
    mapping_decision.metadata_json = metadata_json
    if status != MappingDecisionStatus.PENDING_REVIEW:
        mapping_decision.decided_by = decided_by or "collector"
        mapping_decision.decided_at = decided_at or utcnow()
    else:
        mapping_decision.decided_by = None
        mapping_decision.decided_at = None
    await session.flush()
    return mapping_decision


async def create_ingestion_run(
    session: AsyncSession,
    *,
    source_id: int,
    channel_id: Optional[int],
    artifact_id: int,
    started_at: datetime,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> IngestionRun:
    ingestion_run = IngestionRun(
        source_id=source_id,
        channel_id=channel_id,
        artifact_id=artifact_id,
        started_at=started_at,
        metadata_json=metadata_json,
    )
    session.add(ingestion_run)
    await session.flush()
    return ingestion_run


async def record_run_lifecycle_event(
    session: AsyncSession,
    *,
    run: TestRun,
    event_type: RunLifecycleEventType,
    summary: str,
    status: Optional[RunStatus] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
    ingestion_run_id: Optional[int] = None,
) -> RunLifecycleEvent:
    event = RunLifecycleEvent(
        run_id=run.id,
        ingestion_run_id=ingestion_run_id,
        event_type=event_type,
        status=status,
        summary=summary,
        metadata_json=metadata_json,
    )
    session.add(event)
    await session.flush()
    return event


@dataclass
class CollectorStats:
    sources_polled: int = 0
    files_seen: int = 0
    files_ingested: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    anomalies_raised: int = 0

    def to_dict(self, next_poll_seconds: int) -> Dict[str, Any]:
        return {
            "generated_at": utcnow(),
            "sources_polled": self.sources_polled,
            "files_seen": self.files_seen,
            "files_ingested": self.files_ingested,
            "files_skipped": self.files_skipped,
            "files_failed": self.files_failed,
            "anomalies_raised": self.anomalies_raised,
            "next_poll_seconds": next_poll_seconds,
        }


async def poll_all_sources(session: AsyncSession) -> Dict[str, Any]:
    """Poll every enabled source once."""
    result = await session.execute(
        select(CyclerSource)
        .options(
            selectinload(CyclerSource.channels)
            .selectinload(CyclerChannel.runs),
            selectinload(CyclerSource.channels)
            .selectinload(CyclerChannel.source),
        )
        .where(CyclerSource.enabled.is_(True))
        .order_by(CyclerSource.id.asc())
    )
    sources = result.scalars().all()

    stats = CollectorStats()
    for source in sources:
        stats.sources_polled += 1
        await poll_source(session, source, stats)

    next_poll_seconds = (
        min(source.poll_interval_seconds for source in sources)
        if sources
        else settings.live_poll_default_seconds
    )
    await session.flush()
    return stats.to_dict(next_poll_seconds=next_poll_seconds)


async def poll_source(session: AsyncSession, source: CyclerSource, stats: CollectorStats) -> None:
    """Poll a single source export directory and upsert normalized runs."""
    export_path = Path(source.export_path)
    now = utcnow()

    await deactivate_anomaly(session, f"source:{source.id}:path_unreachable")

    if not export_path.exists():
        await upsert_anomaly(
            session,
            event_key=f"source:{source.id}:path_unreachable",
            source_id=source.id,
            channel_id=None,
            run_id=None,
            cell_id=None,
            anomaly_type="source_path_unreachable",
            severity=AnomalySeverity.CRITICAL,
            title=f"Source path unavailable: {source.name}",
            description=f"Collector could not reach export path `{source.export_path}`.",
            recommendation="Verify that the workstation can reach the shared folder and that the source path is correct.",
            confidence=1.0,
            metadata_json={"export_path": source.export_path},
        )
        stats.anomalies_raised += 1
        return

    files = [path for path in export_path.rglob(source.file_glob or "*") if path.is_file()]
    matched_channel_ids: set[int] = set()

    for file_path in sorted(files):
        stats.files_seen += 1
        checkpoint = await get_or_create_checkpoint(session, source.id, str(file_path))

        try:
            stat = file_path.stat()
        except OSError as exc:
            checkpoint.error_message = str(exc)
            checkpoint.last_seen_at = now
            stats.files_failed += 1
            continue

        modified_at = to_utc_datetime(stat.st_mtime)
        if now - modified_at < timedelta(seconds=source.stable_window_seconds):
            checkpoint.last_seen_at = now
            checkpoint.last_modified_at = modified_at
            checkpoint.last_file_size_bytes = stat.st_size
            stats.files_skipped += 1
            continue

        fingerprint = compute_file_hash(file_path)
        checkpoint.last_seen_at = now
        checkpoint.last_modified_at = modified_at
        checkpoint.last_file_size_bytes = stat.st_size

        if checkpoint.file_fingerprint == fingerprint and checkpoint.last_success_at:
            stats.files_skipped += 1
            continue

        channel = match_channel_for_path(file_path.name, source.channels)
        artifact = CyclerArtifact(
            source_id=source.id,
            channel_id=channel.id if channel else None,
            file_path=str(file_path),
            file_name=file_path.name,
            fingerprint=fingerprint,
            size_bytes=stat.st_size,
            modified_at=modified_at,
            stable_at=now,
            status=ArtifactStatus.DISCOVERED,
        )
        session.add(artifact)
        await session.flush()
        ingestion_run = await create_ingestion_run(
            session,
            source_id=source.id,
            channel_id=channel.id if channel else None,
            artifact_id=artifact.id,
            started_at=now,
            metadata_json={"file_path": str(file_path), "fingerprint": fingerprint},
        )

        if not channel or channel.cell_id is None:
            artifact.status = ArtifactStatus.IGNORED
            artifact.error_message = "No mapped cycler channel/cell matched this file."
            mapping_decision = await upsert_mapping_decision(
                session,
                source_id=source.id,
                channel_id=channel.id if channel else None,
                artifact_id=artifact.id,
                project_id=channel.project_id if channel else None,
                experiment_id=channel.experiment_id if channel else None,
                cell_id=channel.cell_id if channel else None,
                cell_build_id=channel.cell_build_id if channel else None,
                status=MappingDecisionStatus.PENDING_REVIEW,
                mapping_rule="channel_pattern_match",
                confidence=0.0,
                review_reason=artifact.error_message,
                metadata_json={"file_name": file_path.name},
            )
            ingestion_run.mapping_decision_id = mapping_decision.id
            ingestion_run.outcome = IngestionOutcome.PENDING_REVIEW
            ingestion_run.finished_at = now
            ingestion_run.error_message = artifact.error_message
            checkpoint.file_fingerprint = fingerprint
            checkpoint.error_message = artifact.error_message
            stats.files_skipped += 1
            continue

        result = await session.execute(
            select(Cell)
            .options(selectinload(Cell.experiment).selectinload(Experiment.project))
            .where(Cell.id == channel.cell_id)
        )
        cell = result.scalar_one_or_none()
        if not cell:
            artifact.status = ArtifactStatus.FAILED
            artifact.error_message = "Mapped cell no longer exists."
            mapping_decision = await upsert_mapping_decision(
                session,
                source_id=source.id,
                channel_id=channel.id,
                artifact_id=artifact.id,
                project_id=channel.project_id,
                experiment_id=channel.experiment_id,
                cell_id=channel.cell_id,
                cell_build_id=channel.cell_build_id,
                status=MappingDecisionStatus.PENDING_REVIEW,
                mapping_rule="channel.cell_id",
                confidence=0.0,
                review_reason=artifact.error_message,
                metadata_json={"file_name": file_path.name},
            )
            ingestion_run.mapping_decision_id = mapping_decision.id
            ingestion_run.outcome = IngestionOutcome.PENDING_REVIEW
            ingestion_run.finished_at = now
            ingestion_run.error_message = artifact.error_message
            checkpoint.retry_count += 1
            checkpoint.error_message = artifact.error_message
            stats.files_failed += 1
            continue

        had_explicit_cell_build = channel.cell_build_id is not None
        cell_build = await resolve_cell_build_for_channel(session, channel=channel, cell=cell)
        mapping_rule = "channel.cell_build_id" if had_explicit_cell_build else "legacy_cell_backfill"
        mapping_confidence = 1.0 if had_explicit_cell_build else 0.92
        mapping_decision = await upsert_mapping_decision(
            session,
            source_id=source.id,
            channel_id=channel.id,
            artifact_id=artifact.id,
            project_id=channel.project_id or cell.experiment.project_id,
            experiment_id=channel.experiment_id or cell.experiment_id,
            cell_id=cell.id,
            cell_build_id=cell_build.id,
            status=MappingDecisionStatus.AUTO_ACCEPTED,
            mapping_rule=mapping_rule,
            confidence=mapping_confidence,
            review_reason=None,
            metadata_json={
                "file_name": file_path.name,
                "build_name": cell_build.build_name,
                "source": "collector",
            },
        )
        ingestion_run.mapping_decision_id = mapping_decision.id

        project_type = (
            getattr(getattr(cell, "experiment", None), "project", None).project_type.value
            if getattr(getattr(cell, "experiment", None), "project", None) is not None
            else "Full Cell"
        )
        try:
            parsed = parse_cycler_file(
                str(file_path),
                loading=cell.loading,
                active_material_pct=cell.active_material_pct,
                test_number=cell.test_number,
                project_type=project_type,
                parser_type=source.parser_type.value,
            )
            parser_release = await get_or_create_parser_release(
                session,
                source=source,
                parser_type=ParserType(parsed["parser_type"]),
            )
            run, was_reprocessed = await upsert_test_run(
                session,
                source=source,
                channel=channel,
                cell=cell,
                cell_build=cell_build,
                parser_release=parser_release,
                file_path=str(file_path),
                fingerprint=fingerprint,
                modified_at=modified_at,
                parsed=parsed,
                project_type=project_type,
            )
            artifact.run_id = run.id
            artifact.status = ArtifactStatus.INGESTED
            artifact.ingested_at = now
            mapping_decision = await upsert_mapping_decision(
                session,
                source_id=source.id,
                channel_id=channel.id,
                artifact_id=artifact.id,
                project_id=run.project_id,
                experiment_id=run.experiment_id,
                cell_id=run.cell_id,
                cell_build_id=run.cell_build_id,
                status=MappingDecisionStatus.AUTO_ACCEPTED,
                mapping_rule=mapping_rule,
                confidence=mapping_confidence,
                review_reason=None,
                metadata_json={
                    "file_name": file_path.name,
                    "build_name": cell_build.build_name,
                    "source": "collector",
                },
                run_id=run.id,
            )
            ingestion_run.run_id = run.id
            ingestion_run.parser_release_id = parser_release.id
            ingestion_run.mapping_decision_id = mapping_decision.id
            ingestion_run.outcome = IngestionOutcome.SUCCEEDED
            ingestion_run.was_reprocessed = was_reprocessed
            ingestion_run.finished_at = now
            ingestion_run.error_message = None
            ingestion_run.metadata_json = {
                **(ingestion_run.metadata_json or {}),
                "parser_type": parsed["parser_type"],
                "run_id": run.id,
                "cell_build_id": run.cell_build_id,
            }
            checkpoint.file_fingerprint = fingerprint
            checkpoint.last_parsed_cycle = run.last_cycle_index
            checkpoint.last_success_at = now
            checkpoint.retry_count = 0
            checkpoint.error_message = None
            channel.last_seen_at = now
            channel.last_file_path = str(file_path)
            matched_channel_ids.add(channel.id)
            await deactivate_anomaly(
                session, f"parser:{source.id}:{channel.id}:{file_path.name}"
            )
            await record_run_lifecycle_event(
                session,
                run=run,
                ingestion_run_id=ingestion_run.id,
                event_type=(
                    RunLifecycleEventType.REPROCESSED
                    if was_reprocessed
                    else RunLifecycleEventType.INGESTED
                ),
                status=run.status,
                summary=(
                    "Run reprocessed from updated cycler artifact."
                    if was_reprocessed
                    else "Run ingested from cycler artifact."
                ),
                metadata_json={
                    "artifact_id": artifact.id,
                    "mapping_decision_id": mapping_decision.id,
                    "parser_release_id": parser_release.id,
                },
            )
            metric_run = await compute_metrics_for_run(
                session,
                run_id=run.id,
                ingestion_run_id=ingestion_run.id,
            )
            ingestion_run.metadata_json = {
                **(ingestion_run.metadata_json or {}),
                "metric_run_id": metric_run.id,
                "metric_run_status": metric_run.status.value,
            }
            stats.files_ingested += 1
        except Exception as exc:  # noqa: BLE001 - surface parser/IO errors as anomalies
            artifact.status = ArtifactStatus.FAILED
            artifact.error_message = str(exc)
            ingestion_run.outcome = IngestionOutcome.FAILED
            ingestion_run.finished_at = now
            ingestion_run.error_message = str(exc)
            checkpoint.file_fingerprint = fingerprint
            checkpoint.retry_count += 1
            checkpoint.error_message = str(exc)
            channel.status = ChannelStatus.ERROR
            await upsert_anomaly(
                session,
                event_key=f"parser:{source.id}:{channel.id}:{file_path.name}",
                source_id=source.id,
                channel_id=channel.id,
                run_id=None,
                cell_id=channel.cell_id,
                anomaly_type="parser_failure",
                severity=AnomalySeverity.CRITICAL,
                title=f"Parser failure on {channel.source_channel_id}",
                description=str(exc),
                recommendation="Check the export format and confirm the mapped cell metadata includes loading and active material %. Re-run ingestion after the issue is corrected.",
                confidence=1.0,
                metadata_json={"file_path": str(file_path)},
            )
            stats.files_failed += 1
            stats.anomalies_raised += 1

    await evaluate_channel_health(session, source, matched_channel_ids, stats)


async def build_dashboard_payload(session: AsyncSession) -> Dict[str, Any]:
    """Build a lightweight live dashboard payload for API or reports."""
    generated_at = utcnow()

    source_counts = await _enum_counts(session, CyclerSource, enabled_only=False)
    channel_counts = await _status_counts(session, CyclerChannel.status)
    run_counts = await _status_counts(session, TestRun.status)

    anomaly_counts_result = await session.execute(
        select(AnomalyEvent.severity, func.count(AnomalyEvent.id))
        .where(AnomalyEvent.active.is_(True))
        .group_by(AnomalyEvent.severity)
    )
    anomaly_counts = {
        "info": 0,
        "warning": 0,
        "critical": 0,
        "active_total": 0,
    }
    for severity, count in anomaly_counts_result.all():
        key = severity.value if hasattr(severity, "value") else str(severity)
        anomaly_counts[key] = count
        anomaly_counts["active_total"] += count

    active_runs_result = await session.execute(
        select(TestRun)
        .where(TestRun.status.in_((RunStatus.ACTIVE, RunStatus.STALLED)))
        .order_by(TestRun.updated_at.desc())
        .limit(10)
    )
    recent_anomalies_result = await session.execute(
        select(AnomalyEvent)
        .where(AnomalyEvent.active.is_(True))
        .order_by(AnomalyEvent.last_seen_at.desc())
        .limit(10)
    )
    recent_reports_rows = await session.execute(
        select(DailyReportRun)
        .order_by(DailyReportRun.started_at.desc())
        .limit(5)
    )

    return {
        "generated_at": generated_at,
        "sources": source_counts,
        "channels": channel_counts,
        "runs": run_counts,
        "anomalies": anomaly_counts,
        "active_runs": active_runs_result.scalars().all(),
        "recent_anomalies": recent_anomalies_result.scalars().all(),
        "recent_reports": recent_reports_rows.scalars().all(),
    }


async def get_run_provenance_payload(
    session: AsyncSession,
    *,
    run_id: int,
) -> Optional[Dict[str, Any]]:
    result = await session.execute(
        select(TestRun)
        .options(
            selectinload(TestRun.artifacts),
            selectinload(TestRun.parser_release),
            selectinload(TestRun.mapping_decisions),
            selectinload(TestRun.ingestion_runs),
            selectinload(TestRun.lifecycle_events),
        )
        .where(TestRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return None

    return {
        "run": run,
        "parser_release": run.parser_release,
        "artifacts": sorted(run.artifacts, key=lambda artifact: artifact.id),
        "mapping_decisions": sorted(
            run.mapping_decisions,
            key=lambda decision: decision.id,
        ),
        "ingestion_runs": sorted(
            run.ingestion_runs,
            key=lambda ingestion_run: ingestion_run.id,
        ),
        "lifecycle_events": sorted(
            run.lifecycle_events,
            key=lambda lifecycle_event: lifecycle_event.id,
        ),
    }


async def list_mapping_review_payload(
    session: AsyncSession,
    *,
    limit: int = 100,
) -> list[Dict[str, Any]]:
    latest_artifact_per_path = (
        select(
            CyclerArtifact.source_id.label("source_id"),
            CyclerArtifact.file_path.label("file_path"),
            func.max(CyclerArtifact.id).label("artifact_id"),
        )
        .group_by(CyclerArtifact.source_id, CyclerArtifact.file_path)
        .subquery()
    )
    latest_ingestion_per_artifact = (
        select(
            IngestionRun.artifact_id.label("artifact_id"),
            func.max(IngestionRun.id).label("ingestion_run_id"),
        )
        .group_by(IngestionRun.artifact_id)
        .subquery()
    )

    result = await session.execute(
        select(CyclerArtifact, MappingDecision, IngestionRun)
        .join(
            latest_artifact_per_path,
            CyclerArtifact.id == latest_artifact_per_path.c.artifact_id,
        )
        .join(MappingDecision, MappingDecision.artifact_id == CyclerArtifact.id)
        .outerjoin(
            latest_ingestion_per_artifact,
            latest_ingestion_per_artifact.c.artifact_id == CyclerArtifact.id,
        )
        .outerjoin(IngestionRun, IngestionRun.id == latest_ingestion_per_artifact.c.ingestion_run_id)
        .where(MappingDecision.status == MappingDecisionStatus.PENDING_REVIEW)
        .order_by(CyclerArtifact.modified_at.desc(), CyclerArtifact.id.desc())
        .limit(limit)
    )

    items: list[Dict[str, Any]] = []
    for artifact, mapping_decision, ingestion_run in result.all():
        items.append(
            {
                "artifact": artifact,
                "mapping_decision": mapping_decision,
                "latest_ingestion_run": ingestion_run,
            }
        )
    return items


def append_mapping_review_history(
    mapping_decision: MappingDecision,
    *,
    previous_status: MappingDecisionStatus,
    reviewed_by: str,
    review_reason: Optional[str],
    reprocess_now: bool,
) -> None:
    metadata_json = dict(mapping_decision.metadata_json or {})
    review_history = list(metadata_json.get("review_history") or [])
    review_history.append(
        {
            "previous_status": previous_status.value,
            "new_status": mapping_decision.status.value,
            "reviewed_by": reviewed_by,
            "review_reason": review_reason,
            "reprocess_now": reprocess_now,
            "channel_id": mapping_decision.channel_id,
            "cell_id": mapping_decision.cell_id,
            "cell_build_id": mapping_decision.cell_build_id,
            "decided_at": (
                mapping_decision.decided_at.isoformat()
                if mapping_decision.decided_at is not None
                else None
            ),
        }
    )
    metadata_json["review_history"] = review_history
    mapping_decision.metadata_json = metadata_json


async def get_latest_ingestion_run_for_artifact(
    session: AsyncSession,
    *,
    artifact_id: int,
) -> Optional[IngestionRun]:
    result = await session.execute(
        select(IngestionRun)
        .where(IngestionRun.artifact_id == artifact_id)
        .order_by(IngestionRun.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def reprocess_reviewed_artifact(
    session: AsyncSession,
    *,
    source: CyclerSource,
    artifact: CyclerArtifact,
    channel: CyclerChannel,
    mapping_decision: MappingDecision,
) -> Dict[str, Any]:
    now = utcnow()
    checkpoint = await get_or_create_checkpoint(session, source.id, artifact.file_path)
    checkpoint.last_seen_at = now
    checkpoint.last_modified_at = artifact.modified_at
    checkpoint.last_file_size_bytes = artifact.size_bytes
    checkpoint.error_message = None

    ingestion_run = await create_ingestion_run(
        session,
        source_id=source.id,
        channel_id=channel.id,
        artifact_id=artifact.id,
        started_at=now,
        metadata_json={
            "file_path": artifact.file_path,
            "fingerprint": artifact.fingerprint,
            "mapping_review_resolved": True,
            "reviewed_by": mapping_decision.decided_by,
        },
    )
    ingestion_run.mapping_decision_id = mapping_decision.id

    result = await session.execute(
        select(Cell)
        .options(selectinload(Cell.experiment).selectinload(Experiment.project))
        .where(Cell.id == channel.cell_id)
    )
    cell = result.scalar_one_or_none()
    if cell is None:
        artifact.status = ArtifactStatus.FAILED
        artifact.error_message = "Reviewed cell no longer exists."
        ingestion_run.outcome = IngestionOutcome.FAILED
        ingestion_run.finished_at = now
        ingestion_run.error_message = artifact.error_message
        checkpoint.file_fingerprint = artifact.fingerprint
        checkpoint.retry_count += 1
        checkpoint.error_message = artifact.error_message
        channel.status = ChannelStatus.ERROR
        await session.flush()
        return {
            "mapping_decision": mapping_decision,
            "artifact": artifact,
            "latest_ingestion_run": ingestion_run,
            "run": None,
        }

    had_explicit_cell_build = channel.cell_build_id is not None
    cell_build = await resolve_cell_build_for_channel(session, channel=channel, cell=cell)
    mapping_decision.run_id = None
    mapping_decision.project_id = channel.project_id or cell.experiment.project_id
    mapping_decision.experiment_id = channel.experiment_id or cell.experiment_id
    mapping_decision.cell_id = cell.id
    mapping_decision.cell_build_id = cell_build.id
    mapping_decision.mapping_rule = (
        "manual_review.channel.cell_build_id"
        if had_explicit_cell_build
        else "manual_review.legacy_cell_backfill"
    )
    mapping_decision.confidence = 1.0

    project_type = (
        getattr(getattr(cell, "experiment", None), "project", None).project_type.value
        if getattr(getattr(cell, "experiment", None), "project", None) is not None
        else "Full Cell"
    )
    try:
        file_path = Path(artifact.file_path)
        parsed = parse_cycler_file(
            str(file_path),
            loading=cell.loading,
            active_material_pct=cell.active_material_pct,
            test_number=cell.test_number,
            project_type=project_type,
            parser_type=source.parser_type.value,
        )
        parser_release = await get_or_create_parser_release(
            session,
            source=source,
            parser_type=ParserType(parsed["parser_type"]),
        )
        run, was_reprocessed = await upsert_test_run(
            session,
            source=source,
            channel=channel,
            cell=cell,
            cell_build=cell_build,
            parser_release=parser_release,
            file_path=artifact.file_path,
            fingerprint=artifact.fingerprint,
            modified_at=artifact.modified_at,
            parsed=parsed,
            project_type=project_type,
        )
        artifact.channel_id = channel.id
        artifact.run_id = run.id
        artifact.status = ArtifactStatus.INGESTED
        artifact.ingested_at = now
        artifact.error_message = None
        mapping_decision.run_id = run.id
        ingestion_run.run_id = run.id
        ingestion_run.parser_release_id = parser_release.id
        ingestion_run.outcome = IngestionOutcome.SUCCEEDED
        ingestion_run.was_reprocessed = was_reprocessed
        ingestion_run.finished_at = now
        ingestion_run.error_message = None
        ingestion_run.metadata_json = {
            **(ingestion_run.metadata_json or {}),
            "parser_type": parsed["parser_type"],
            "run_id": run.id,
            "cell_build_id": run.cell_build_id,
        }
        checkpoint.file_fingerprint = artifact.fingerprint
        checkpoint.last_parsed_cycle = run.last_cycle_index
        checkpoint.last_success_at = now
        checkpoint.retry_count = 0
        checkpoint.error_message = None
        channel.last_seen_at = now
        channel.last_file_path = artifact.file_path
        channel.status = ChannelStatus.ACTIVE
        await deactivate_anomaly(
            session,
            f"parser:{source.id}:{channel.id}:{artifact.file_name}",
        )
        await record_run_lifecycle_event(
            session,
            run=run,
            ingestion_run_id=ingestion_run.id,
            event_type=(
                RunLifecycleEventType.REPROCESSED
                if was_reprocessed
                else RunLifecycleEventType.INGESTED
            ),
            status=run.status,
            summary=(
                "Run reprocessed after mapping review confirmation."
                if was_reprocessed
                else "Run ingested after mapping review confirmation."
            ),
            metadata_json={
                "artifact_id": artifact.id,
                "mapping_decision_id": mapping_decision.id,
                "parser_release_id": parser_release.id,
                "reviewed_by": mapping_decision.decided_by,
            },
        )
        metric_run = await compute_metrics_for_run(
            session,
            run_id=run.id,
            ingestion_run_id=ingestion_run.id,
        )
        ingestion_run.metadata_json = {
            **(ingestion_run.metadata_json or {}),
            "metric_run_id": metric_run.id,
            "metric_run_status": metric_run.status.value,
        }
        await session.flush()
        return {
            "mapping_decision": mapping_decision,
            "artifact": artifact,
            "latest_ingestion_run": ingestion_run,
            "run": run,
        }
    except Exception as exc:  # noqa: BLE001 - review is recorded even if reprocess fails
        artifact.status = ArtifactStatus.FAILED
        artifact.error_message = str(exc)
        ingestion_run.outcome = IngestionOutcome.FAILED
        ingestion_run.finished_at = now
        ingestion_run.error_message = str(exc)
        checkpoint.file_fingerprint = artifact.fingerprint
        checkpoint.retry_count += 1
        checkpoint.error_message = str(exc)
        channel.status = ChannelStatus.ERROR
        await upsert_anomaly(
            session,
            event_key=f"parser:{source.id}:{channel.id}:{artifact.file_name}",
            source_id=source.id,
            channel_id=channel.id,
            run_id=None,
            cell_id=channel.cell_id,
            anomaly_type="parser_failure",
            severity=AnomalySeverity.CRITICAL,
            title=f"Parser failure on {channel.source_channel_id}",
            description=str(exc),
            recommendation="Check the export format and confirm the reviewed channel metadata includes loading and active material %. Re-run ingestion after the issue is corrected.",
            confidence=1.0,
            metadata_json={
                "file_path": artifact.file_path,
                "mapping_decision_id": mapping_decision.id,
            },
        )
        await session.flush()
        return {
            "mapping_decision": mapping_decision,
            "artifact": artifact,
            "latest_ingestion_run": ingestion_run,
            "run": None,
        }


async def resolve_mapping_review(
    session: AsyncSession,
    *,
    mapping_decision_id: int,
    resolution: MappingDecisionStatus,
    reviewed_by: str,
    review_reason: Optional[str] = None,
    channel_id: Optional[int] = None,
    cell_id: Optional[int] = None,
    cell_build_id: Optional[int] = None,
    file_pattern: Optional[str] = None,
    reprocess_now: bool = True,
) -> Dict[str, Any]:
    result = await session.execute(
        select(MappingDecision)
        .options(selectinload(MappingDecision.artifact))
        .where(MappingDecision.id == mapping_decision_id)
    )
    mapping_decision = result.scalar_one_or_none()
    if mapping_decision is None:
        raise LookupError("Mapping decision not found")
    if mapping_decision.status != MappingDecisionStatus.PENDING_REVIEW:
        raise ValueError("Only pending mapping review items can be resolved")

    artifact = mapping_decision.artifact
    if artifact is None:
        raise LookupError("Mapping review artifact not found")
    source = await session.get(CyclerSource, mapping_decision.source_id)
    if source is None:
        raise LookupError("Cycler source not found")

    normalized_reason = review_reason.strip() if isinstance(review_reason, str) else None
    decision_time = utcnow()

    if resolution == MappingDecisionStatus.REJECTED:
        previous_status = mapping_decision.status
        mapping_decision.status = MappingDecisionStatus.REJECTED
        mapping_decision.review_reason = (
            normalized_reason or "Mapping rejected during manual review."
        )
        mapping_decision.decided_by = reviewed_by
        mapping_decision.decided_at = decision_time
        artifact.status = ArtifactStatus.IGNORED
        artifact.error_message = mapping_decision.review_reason
        checkpoint = await get_or_create_checkpoint(session, source.id, artifact.file_path)
        checkpoint.file_fingerprint = artifact.fingerprint
        checkpoint.last_seen_at = decision_time
        checkpoint.last_modified_at = artifact.modified_at
        checkpoint.last_file_size_bytes = artifact.size_bytes
        checkpoint.last_success_at = decision_time
        checkpoint.error_message = mapping_decision.review_reason
        append_mapping_review_history(
            mapping_decision,
            previous_status=previous_status,
            reviewed_by=reviewed_by,
            review_reason=mapping_decision.review_reason,
            reprocess_now=False,
        )
        await session.flush()
        return {
            "mapping_decision": mapping_decision,
            "artifact": artifact,
            "latest_ingestion_run": await get_latest_ingestion_run_for_artifact(
                session,
                artifact_id=artifact.id,
            ),
            "run": None,
        }

    if resolution != MappingDecisionStatus.CONFIRMED:
        raise ValueError("Unsupported mapping review resolution")

    target_channel_id = channel_id or mapping_decision.channel_id or artifact.channel_id
    if target_channel_id is None:
        raise ValueError("Confirming a mapping review requires a cycler channel")

    channel = await session.get(CyclerChannel, target_channel_id)
    if channel is None:
        raise LookupError("Cycler channel not found")
    if channel.source_id != source.id:
        raise ValueError("Cycler channel must belong to the same source as the reviewed artifact")

    normalized_pattern = file_pattern.strip() if isinstance(file_pattern, str) else None
    if normalized_pattern:
        channel.file_pattern = normalized_pattern

    target_cell_id = cell_id or channel.cell_id or mapping_decision.cell_id
    if target_cell_id is None:
        raise ValueError("Confirming a mapping review requires a mapped cell")

    result = await session.execute(
        select(Cell)
        .options(selectinload(Cell.experiment).selectinload(Experiment.project))
        .where(Cell.id == target_cell_id)
    )
    cell = result.scalar_one_or_none()
    if cell is None:
        raise LookupError("Mapped cell not found")
    if getattr(cell, "experiment", None) is None:
        raise ValueError("Mapped cell must belong to an experiment before review can be confirmed")

    channel.cell_id = cell.id
    channel.experiment_id = cell.experiment_id
    channel.project_id = cell.experiment.project_id
    if cell_build_id is not None:
        selected_build = await session.get(CellBuild, cell_build_id)
        if selected_build is None:
            raise LookupError("Cell build not found")
        channel.cell_build_id = selected_build.id
        cell_build = selected_build
    else:
        cell_build = await resolve_cell_build_for_channel(session, channel=channel, cell=cell)

    artifact.channel_id = channel.id
    artifact.error_message = None
    previous_status = mapping_decision.status
    mapping_decision.channel_id = channel.id
    mapping_decision.project_id = channel.project_id
    mapping_decision.experiment_id = channel.experiment_id
    mapping_decision.cell_id = cell.id
    mapping_decision.cell_build_id = cell_build.id
    mapping_decision.status = MappingDecisionStatus.CONFIRMED
    mapping_decision.mapping_rule = "manual_review"
    mapping_decision.confidence = 1.0
    mapping_decision.review_reason = normalized_reason
    mapping_decision.decided_by = reviewed_by
    mapping_decision.decided_at = decision_time
    append_mapping_review_history(
        mapping_decision,
        previous_status=previous_status,
        reviewed_by=reviewed_by,
        review_reason=normalized_reason,
        reprocess_now=reprocess_now,
    )

    checkpoint = await get_or_create_checkpoint(session, source.id, artifact.file_path)
    checkpoint.last_seen_at = decision_time
    checkpoint.last_modified_at = artifact.modified_at
    checkpoint.last_file_size_bytes = artifact.size_bytes
    checkpoint.error_message = None

    if reprocess_now:
        return await reprocess_reviewed_artifact(
            session,
            source=source,
            artifact=artifact,
            channel=channel,
            mapping_decision=mapping_decision,
        )

    artifact.status = ArtifactStatus.DISCOVERED
    await session.flush()
    return {
        "mapping_decision": mapping_decision,
        "artifact": artifact,
        "latest_ingestion_run": await get_latest_ingestion_run_for_artifact(
            session,
            artifact_id=artifact.id,
        ),
        "run": None,
    }


async def upsert_test_run(
    session: AsyncSession,
    *,
    source: CyclerSource,
    channel: CyclerChannel,
    cell: Cell,
    cell_build: CellBuild,
    parser_release: ParserRelease,
    file_path: str,
    fingerprint: str,
    modified_at: datetime,
    parsed: Dict[str, Any],
    project_type: str,
) -> tuple[TestRun, bool]:
    """Create or refresh a normalized run from a parsed file."""
    run_key = f"{source.id}:{channel.id}:{file_path}"
    result = await session.execute(select(TestRun).where(TestRun.run_key == run_key))
    run = result.scalar_one_or_none()
    was_reprocessed = run is not None
    if not run:
        run = TestRun(
            source_id=source.id,
            channel_id=channel.id,
            project_id=channel.project_id or cell.experiment.project_id,
            experiment_id=channel.experiment_id or cell.experiment_id,
            cell_id=cell.id,
            cell_build_id=cell_build.id,
            parser_release_id=parser_release.id,
            run_key=run_key,
            source_file_path=file_path,
            started_at=modified_at,
        )
        session.add(run)
        await session.flush()

    df = parsed["dataframe"]
    summary = summarize_run(
        df,
        cell_name=cell.cell_name,
        test_number=cell.test_number,
        loading=cell.loading,
        active_material_pct=cell.active_material_pct,
        formation_cycles=cell.formation_cycles,
        porosity=cell.porosity,
        project_type=project_type,
        disc_diameter_mm=cell.experiment.disc_diameter_mm if cell.experiment else 15.0,
        anode_mass=getattr(cell, "anode_mass", None),
        cathode_mass=getattr(cell, "cathode_mass", None),
        overhang_ratio=getattr(cell, "overhang_ratio", None),
    )

    peer_summaries = await get_peer_summaries(session, run, summary)
    flags = detect_run_flags(df, summary, peer_summaries=peer_summaries)
    operational_flags = detect_operational_flags(df, summary, modified_at)
    all_flags = flags + operational_flags

    run.source_file_hash = fingerprint
    run.parser_type = ParserType(parsed["parser_type"])
    run.cell_build_id = cell_build.id
    run.parser_release_id = parser_release.id
    run.status = RunStatus.ACTIVE
    run.completed_at = None
    run.last_sampled_at = modified_at
    run.last_cycle_index = summary.get("current_cycle")
    run.latest_charge_capacity_mah = summary.get("latest_charge_capacity_mah")
    run.latest_discharge_capacity_mah = summary.get("latest_discharge_capacity_mah")
    run.latest_efficiency = summary.get("latest_efficiency")
    run.capacity_retention_pct = summary.get("capacity_retention_pct")
    run.summary_json = summary
    run.metadata_json = {
        "lower_cutoff": parsed.get("lower_cutoff"),
        "upper_cutoff": parsed.get("upper_cutoff"),
    }

    await replace_cycle_points(session, run, dataframe_to_cycle_payloads(df))
    await sync_run_anomalies(session, run, source, channel, all_flags)
    return run, was_reprocessed


async def get_peer_summaries(
    session: AsyncSession,
    run: TestRun,
    current_summary: Dict[str, Any],
) -> list[Dict[str, Any]]:
    if not run.experiment_id:
        return [current_summary]

    result = await session.execute(
        select(TestRun.summary_json)
        .where(
            TestRun.experiment_id == run.experiment_id,
            TestRun.id != run.id,
            TestRun.summary_json.is_not(None),
        )
    )
    summaries = [row for row in result.scalars().all() if isinstance(row, dict)]
    summaries.append(current_summary)
    return summaries


async def replace_cycle_points(
    session: AsyncSession, run: TestRun, payloads: Iterable[Dict[str, Any]]
) -> None:
    await session.execute(delete(CyclePoint).where(CyclePoint.run_id == run.id))
    for payload in payloads:
        session.add(CyclePoint(run_id=run.id, **payload))
    await session.flush()


async def sync_run_anomalies(
    session: AsyncSession,
    run: TestRun,
    source: CyclerSource,
    channel: CyclerChannel,
    anomalies: Iterable[Dict[str, Any]],
) -> None:
    active_keys: set[str] = set()
    for anomaly in anomalies:
        event_key = f"run:{run.id}:{anomaly['flag_id']}:{anomaly.get('cycle') or 'na'}"
        active_keys.add(event_key)
        await upsert_anomaly(
            session,
            event_key=event_key,
            source_id=source.id,
            channel_id=channel.id,
            run_id=run.id,
            cell_id=run.cell_id,
            anomaly_type=anomaly["flag_id"],
            severity=severity_from_flag_name(anomaly.get("severity")),
            title=anomaly.get("flag_type", anomaly["flag_id"]),
            description=anomaly.get("description", ""),
            recommendation=anomaly.get("recommendation"),
            confidence=anomaly.get("confidence"),
            metadata_json=anomaly,
        )

    existing = await session.execute(
        select(AnomalyEvent)
        .where(AnomalyEvent.run_id == run.id)
    )
    for row in existing.scalars().all():
        if row.event_key.startswith(f"run:{run.id}:") and row.event_key not in active_keys:
            row.active = False


async def evaluate_channel_health(
    session: AsyncSession,
    source: CyclerSource,
    matched_channel_ids: set[int],
    stats: CollectorStats,
) -> None:
    """Update channel/run health based on freshness even if no new file was ingested."""
    now = utcnow()
    completion_threshold = timedelta(hours=settings.live_run_completion_hours)
    offline_threshold = timedelta(minutes=max(settings.live_channel_offline_minutes, 1))

    for channel in source.channels:
        latest_run = await get_latest_run_for_channel(session, channel.id)
        if channel.id in matched_channel_ids:
            channel.status = ChannelStatus.ACTIVE
            if latest_run and latest_run.status == RunStatus.STALLED:
                latest_run.status = RunStatus.ACTIVE
                await record_run_lifecycle_event(
                    session,
                    run=latest_run,
                    event_type=RunLifecycleEventType.RESUMED,
                    status=latest_run.status,
                    summary="Run resumed after fresh data was detected.",
                )
            await deactivate_anomaly(session, f"freshness:{source.id}:{channel.id}")
            if latest_run:
                await deactivate_anomaly(
                    session, f"completed:{source.id}:{channel.id}:{latest_run.id}"
                )
            continue

        if channel.last_seen_at is None:
            channel.status = ChannelStatus.UNKNOWN
            continue

        age = now - channel.last_seen_at
        if latest_run and latest_run.status == RunStatus.ACTIVE and age >= completion_threshold:
            latest_run.status = RunStatus.COMPLETED
            latest_run.completed_at = now
            channel.status = ChannelStatus.COMPLETED
            await record_run_lifecycle_event(
                session,
                run=latest_run,
                event_type=RunLifecycleEventType.COMPLETED,
                status=latest_run.status,
                summary="Run marked complete after export inactivity crossed the completion window.",
                metadata_json={"age_minutes": int(age.total_seconds() // 60)},
            )
            await upsert_anomaly(
                session,
                event_key=f"completed:{source.id}:{channel.id}:{latest_run.id}",
                source_id=source.id,
                channel_id=channel.id,
                run_id=latest_run.id,
                cell_id=latest_run.cell_id,
                anomaly_type="completed_run",
                severity=AnomalySeverity.INFO,
                title=f"Run completed on {channel.source_channel_id}",
                description="No fresh export updates were detected within the completion window, so the run has been marked complete.",
                recommendation="Review the run in the dashboard and archive or remap the channel when the next test begins.",
                confidence=0.8,
                metadata_json={"age_minutes": int(age.total_seconds() // 60)},
            )
            stats.anomalies_raised += 1
            continue

        if age >= offline_threshold:
            channel.status = ChannelStatus.STALLED if latest_run else ChannelStatus.OFFLINE
            if latest_run and latest_run.status == RunStatus.ACTIVE:
                latest_run.status = RunStatus.STALLED
                await record_run_lifecycle_event(
                    session,
                    run=latest_run,
                    event_type=RunLifecycleEventType.STALLED,
                    status=latest_run.status,
                    summary="Run marked stalled because no fresh data arrived within the freshness window.",
                    metadata_json={"age_minutes": int(age.total_seconds() // 60)},
                )
            await upsert_anomaly(
                session,
                event_key=f"freshness:{source.id}:{channel.id}",
                source_id=source.id,
                channel_id=channel.id,
                run_id=latest_run.id if latest_run else None,
                cell_id=latest_run.cell_id if latest_run else channel.cell_id,
                anomaly_type="stalled_channel" if latest_run else "no_fresh_data",
                severity=AnomalySeverity.WARNING,
                title=f"No fresh data on {channel.source_channel_id}",
                description=f"No new stable file update has been seen for {int(age.total_seconds() // 60)} minutes.",
                recommendation="Check the cycler export folder, confirm the test is still running, and verify the workstation can reach the share.",
                confidence=0.9,
                metadata_json={"age_minutes": int(age.total_seconds() // 60)},
            )
            stats.anomalies_raised += 1
        else:
            channel.status = ChannelStatus.ACTIVE
            await deactivate_anomaly(session, f"freshness:{source.id}:{channel.id}")


async def get_latest_run_for_channel(
    session: AsyncSession, channel_id: int
) -> Optional[TestRun]:
    result = await session.execute(
        select(TestRun)
        .where(TestRun.channel_id == channel_id)
        .order_by(TestRun.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_or_create_checkpoint(
    session: AsyncSession, source_id: int, file_path: str
) -> IngestionCheckpoint:
    result = await session.execute(
        select(IngestionCheckpoint).where(
            IngestionCheckpoint.source_id == source_id,
            IngestionCheckpoint.file_path == file_path,
        )
    )
    checkpoint = result.scalar_one_or_none()
    if checkpoint:
        return checkpoint

    checkpoint = IngestionCheckpoint(source_id=source_id, file_path=file_path)
    session.add(checkpoint)
    await session.flush()
    return checkpoint


def compute_file_hash(file_path: Path) -> str:
    sha = hashlib.sha256()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def match_channel_for_path(
    file_name: str, channels: Iterable[CyclerChannel]
) -> Optional[CyclerChannel]:
    lower_name = file_name.lower()
    for channel in channels:
        if channel.file_pattern and fnmatch.fnmatch(lower_name, channel.file_pattern.lower()):
            return channel
        if channel.source_channel_id and channel.source_channel_id.lower() in lower_name:
            return channel
        if channel.display_name and channel.display_name.lower() in lower_name:
            return channel
    return None


def detect_operational_flags(
    df: pd.DataFrame, summary: Dict[str, Any], modified_at: datetime
) -> list[Dict[str, Any]]:
    """Add live-ops heuristics on top of the reused anomaly rules."""
    flags: list[Dict[str, Any]] = []

    if len(df) >= 10 and "Efficiency (-)" in df.columns:
        eff = pd.to_numeric(df["Efficiency (-)"], errors="coerce").dropna()
        if len(eff) >= 10:
            head = eff.head(min(5, len(eff))) * 100
            tail = eff.tail(min(5, len(eff))) * 100
            if not head.empty and not tail.empty:
                drift = float(head.mean() - tail.mean())
                if drift > 2.0:
                    flags.append(
                        {
                            "flag_id": "ce_drift",
                            "flag_type": "CE Drift",
                            "severity": "WARNING",
                            "description": f"Coulombic efficiency drift detected: baseline {head.mean():.2f}% to recent {tail.mean():.2f}%.",
                            "confidence": 0.82,
                            "recommendation": "Inspect the recent cycles for emerging side reactions or export instability.",
                            "cycle": summary.get("current_cycle"),
                            "metric_value": tail.mean(),
                            "threshold_value": head.mean(),
                        }
                    )
    return flags


async def upsert_anomaly(
    session: AsyncSession,
    *,
    event_key: str,
    source_id: Optional[int],
    channel_id: Optional[int],
    run_id: Optional[int],
    cell_id: Optional[int],
    anomaly_type: str,
    severity: AnomalySeverity,
    title: str,
    description: str,
    recommendation: Optional[str],
    confidence: Optional[float],
    metadata_json: Optional[Dict[str, Any]] = None,
) -> AnomalyEvent:
    now = utcnow()
    result = await session.execute(
        select(AnomalyEvent).where(AnomalyEvent.event_key == event_key)
    )
    anomaly = result.scalar_one_or_none()
    if not anomaly:
        anomaly = AnomalyEvent(
            event_key=event_key,
            source_id=source_id,
            channel_id=channel_id,
            run_id=run_id,
            cell_id=cell_id,
            anomaly_type=anomaly_type,
            severity=severity,
            title=title,
            description=description,
            recommendation=recommendation,
            confidence=confidence,
            metadata_json=metadata_json,
            active=True,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(anomaly)
        await session.flush()
        return anomaly

    anomaly.source_id = source_id
    anomaly.channel_id = channel_id
    anomaly.run_id = run_id
    anomaly.cell_id = cell_id
    anomaly.anomaly_type = anomaly_type
    anomaly.severity = severity
    anomaly.title = title
    anomaly.description = description
    anomaly.recommendation = recommendation
    anomaly.confidence = confidence
    anomaly.metadata_json = metadata_json
    anomaly.active = True
    anomaly.acknowledged_at = None
    anomaly.acknowledged_by = None
    anomaly.last_seen_at = now
    return anomaly


async def deactivate_anomaly(session: AsyncSession, event_key: str) -> None:
    result = await session.execute(
        select(AnomalyEvent).where(AnomalyEvent.event_key == event_key)
    )
    anomaly = result.scalar_one_or_none()
    if anomaly:
        anomaly.active = False


async def _enum_counts(
    session: AsyncSession, model: Any, enabled_only: bool = False
) -> Dict[str, int]:
    count_result = await session.execute(select(func.count(model.id)))
    total = count_result.scalar_one()
    if enabled_only and hasattr(model, "enabled"):
        enabled_result = await session.execute(
            select(func.count(model.id)).where(model.enabled.is_(True))
        )
        enabled = enabled_result.scalar_one()
    elif hasattr(model, "enabled"):
        enabled_result = await session.execute(
            select(func.count(model.id)).where(model.enabled.is_(True))
        )
        enabled = enabled_result.scalar_one()
    else:
        enabled = total
    return {"total": total, "enabled": enabled}


async def _status_counts(session: AsyncSession, column: Any) -> Dict[str, int]:
    entity = getattr(column, "class_", None)
    total_result = await session.execute(select(func.count(entity.id)))
    grouped = await session.execute(select(column, func.count(entity.id)).group_by(column))
    counts: Dict[str, int] = {"total": total_result.scalar_one()}
    for status, count in grouped.all():
        key = status.value if hasattr(status, "value") else str(status)
        counts[key] = count
    return counts
