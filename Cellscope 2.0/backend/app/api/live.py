"""Live cycler operations API routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.cell import Cell
from app.models.live import (
    AnomalyEvent,
    CyclerChannel,
    CyclerSource,
    DailyReportRun,
    MappingDecision,
    MappingDecisionStatus,
    NotificationTarget,
    RunStatus,
    TestRun,
)
from app.models.ontology import CellBuild
from app.schemas.live import (
    AcknowledgeAnomalyRequest,
    AnomalyEventRead,
    CollectorRunResult,
    CyclerChannelCreate,
    CyclerChannelRead,
    CyclerChannelUpdate,
    CyclerSourceCreate,
    CyclerSourceRead,
    CyclerSourceUpdate,
    DailyReportRunRead,
    LiveDashboardRead,
    MappingDecisionRead,
    MappingReviewItemRead,
    MappingReviewResolveRequest,
    MappingReviewResolutionRead,
    NotificationTargetCreate,
    NotificationTargetRead,
    ReportRunRequest,
    RunProvenanceRead,
    TestRunDetailRead,
    TestRunRead,
)
from app.services.live_monitor import (
    build_dashboard_payload,
    get_run_provenance_payload,
    list_mapping_review_payload,
    poll_all_sources,
    resolve_mapping_review,
)
from app.services.reporting import generate_daily_report

router = APIRouter(prefix="/api/live", tags=["live"])


async def _get_source(db: AsyncSession, source_id: int) -> CyclerSource:
    source = await db.get(CyclerSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Cycler source not found")
    return source


async def _get_channel(db: AsyncSession, channel_id: int) -> CyclerChannel:
    channel = await db.get(CyclerChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Cycler channel not found")
    return channel


@router.get("/dashboard", response_model=LiveDashboardRead)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Return current live dashboard data for workstation or future web UI use."""
    payload = await build_dashboard_payload(db)
    return LiveDashboardRead.model_validate(payload)


@router.get("/sources", response_model=list[CyclerSourceRead])
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CyclerSource).order_by(CyclerSource.name.asc()))
    return [CyclerSourceRead.model_validate(source) for source in result.scalars().all()]


@router.post("/sources", response_model=CyclerSourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(source_in: CyclerSourceCreate, db: AsyncSession = Depends(get_db)):
    source = CyclerSource(**source_in.model_dump())
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return CyclerSourceRead.model_validate(source)


@router.patch("/sources/{source_id}", response_model=CyclerSourceRead)
async def update_source(
    source_id: int,
    source_in: CyclerSourceUpdate,
    db: AsyncSession = Depends(get_db),
):
    source = await _get_source(db, source_id)
    for field, value in source_in.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    await db.flush()
    await db.refresh(source)
    return CyclerSourceRead.model_validate(source)


@router.get("/channels", response_model=list[CyclerChannelRead])
async def list_channels(
    source_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CyclerChannel).order_by(CyclerChannel.source_id.asc(), CyclerChannel.source_channel_id.asc())
    if source_id is not None:
        stmt = stmt.where(CyclerChannel.source_id == source_id)
    result = await db.execute(stmt)
    return [CyclerChannelRead.model_validate(channel) for channel in result.scalars().all()]


@router.post("/channels", response_model=CyclerChannelRead, status_code=status.HTTP_201_CREATED)
async def create_channel(
    channel_in: CyclerChannelCreate,
    db: AsyncSession = Depends(get_db),
):
    await _get_source(db, channel_in.source_id)

    channel_data = channel_in.model_dump()
    if channel_in.cell_id is not None:
        result = await db.execute(
            select(Cell)
            .options(selectinload(Cell.experiment))
            .where(Cell.id == channel_in.cell_id)
        )
        cell = result.scalar_one_or_none()
        if not cell:
            raise HTTPException(status_code=404, detail="Cell not found")
        channel_data["experiment_id"] = channel_data.get("experiment_id") or cell.experiment_id
        if getattr(cell, "experiment", None):
            channel_data["project_id"] = channel_data.get("project_id") or cell.experiment.project_id
    if channel_in.cell_build_id is not None:
        cell_build = await db.get(CellBuild, channel_in.cell_build_id)
        if not cell_build:
            raise HTTPException(status_code=404, detail="Cell build not found")

    channel = CyclerChannel(**channel_data)
    db.add(channel)
    await db.flush()
    await db.refresh(channel)
    return CyclerChannelRead.model_validate(channel)


@router.patch("/channels/{channel_id}", response_model=CyclerChannelRead)
async def update_channel(
    channel_id: int,
    channel_in: CyclerChannelUpdate,
    db: AsyncSession = Depends(get_db),
):
    channel = await _get_channel(db, channel_id)
    if channel_in.cell_build_id is not None:
        cell_build = await db.get(CellBuild, channel_in.cell_build_id)
        if not cell_build:
            raise HTTPException(status_code=404, detail="Cell build not found")
    for field, value in channel_in.model_dump(exclude_unset=True).items():
        setattr(channel, field, value)
    await db.flush()
    await db.refresh(channel)
    return CyclerChannelRead.model_validate(channel)


@router.get("/runs", response_model=list[TestRunRead])
async def list_runs(
    source_id: Optional[int] = Query(default=None),
    channel_id: Optional[int] = Query(default=None),
    active_only: bool = Query(default=False),
    limit: int = Query(default=25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TestRun).order_by(TestRun.updated_at.desc()).limit(limit)
    if source_id is not None:
        stmt = stmt.where(TestRun.source_id == source_id)
    if channel_id is not None:
        stmt = stmt.where(TestRun.channel_id == channel_id)
    if active_only:
        stmt = stmt.where(TestRun.status.in_((RunStatus.ACTIVE, RunStatus.STALLED)))
    result = await db.execute(stmt)
    return [TestRunRead.model_validate(run) for run in result.scalars().all()]


@router.get("/runs/{run_id}", response_model=TestRunDetailRead)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TestRun)
        .options(
            selectinload(TestRun.cycle_points),
            selectinload(TestRun.anomalies),
            selectinload(TestRun.artifacts),
            selectinload(TestRun.parser_release),
            selectinload(TestRun.mapping_decisions),
            selectinload(TestRun.ingestion_runs),
            selectinload(TestRun.lifecycle_events),
        )
        .where(TestRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return TestRunDetailRead.model_validate(run)


@router.get("/runs/{run_id}/provenance", response_model=RunProvenanceRead)
async def get_run_provenance(run_id: int, db: AsyncSession = Depends(get_db)):
    payload = await get_run_provenance_payload(db, run_id=run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunProvenanceRead.model_validate(payload)


@router.get("/mapping-decisions", response_model=list[MappingDecisionRead])
async def list_mapping_decisions(
    status: Optional[MappingDecisionStatus] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MappingDecision).order_by(MappingDecision.updated_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(MappingDecision.status == status)
    result = await db.execute(stmt)
    return [MappingDecisionRead.model_validate(decision) for decision in result.scalars().all()]


@router.get("/mapping-review", response_model=list[MappingReviewItemRead])
async def get_mapping_review(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    payload = await list_mapping_review_payload(db, limit=limit)
    return [MappingReviewItemRead.model_validate(item) for item in payload]


@router.post(
    "/mapping-review/{mapping_decision_id}/resolve",
    response_model=MappingReviewResolutionRead,
)
async def resolve_mapping_review_item(
    mapping_decision_id: int,
    request: MappingReviewResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = await resolve_mapping_review(
            db,
            mapping_decision_id=mapping_decision_id,
            resolution=MappingDecisionStatus(request.resolution.value),
            reviewed_by=request.reviewed_by,
            review_reason=request.review_reason,
            channel_id=request.channel_id,
            cell_id=request.cell_id,
            cell_build_id=request.cell_build_id,
            file_pattern=request.file_pattern,
            reprocess_now=request.reprocess_now,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MappingReviewResolutionRead.model_validate(payload)


@router.get("/anomalies", response_model=list[AnomalyEventRead])
async def list_anomalies(
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AnomalyEvent).order_by(AnomalyEvent.last_seen_at.desc()).limit(limit)
    if active_only:
        stmt = stmt.where(AnomalyEvent.active.is_(True))
    result = await db.execute(stmt)
    return [AnomalyEventRead.model_validate(anomaly) for anomaly in result.scalars().all()]


@router.post("/anomalies/{anomaly_id}/acknowledge", response_model=AnomalyEventRead)
async def acknowledge_anomaly(
    anomaly_id: int,
    request: AcknowledgeAnomalyRequest,
    db: AsyncSession = Depends(get_db),
):
    anomaly = await db.get(AnomalyEvent, anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    anomaly.acknowledged_at = datetime.utcnow()
    anomaly.acknowledged_by = request.acknowledged_by
    anomaly.active = False
    await db.flush()
    await db.refresh(anomaly)
    return AnomalyEventRead.model_validate(anomaly)


@router.get("/notification-targets", response_model=list[NotificationTargetRead])
async def list_notification_targets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(NotificationTarget).order_by(NotificationTarget.created_at.desc())
    )
    return [NotificationTargetRead.model_validate(row) for row in result.scalars().all()]


@router.post(
    "/notification-targets",
    response_model=NotificationTargetRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_target(
    target_in: NotificationTargetCreate,
    db: AsyncSession = Depends(get_db),
):
    target = NotificationTarget(**target_in.model_dump())
    db.add(target)
    await db.flush()
    await db.refresh(target)
    return NotificationTargetRead.model_validate(target)


@router.get("/reports", response_model=list[DailyReportRunRead])
async def list_reports(
    limit: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DailyReportRun)
        .order_by(DailyReportRun.started_at.desc())
        .limit(limit)
    )
    return [DailyReportRunRead.model_validate(report) for report in result.scalars().all()]


@router.get("/reports/{report_id}", response_model=DailyReportRunRead)
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    report = await db.get(DailyReportRun, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return DailyReportRunRead.model_validate(report)


@router.post("/collector/run-once", response_model=CollectorRunResult)
async def run_collector_once(db: AsyncSession = Depends(get_db)):
    """Trigger a manual single poll run from the API."""
    result = await poll_all_sources(db)
    return CollectorRunResult.model_validate(result)


@router.post("/reports/run", response_model=DailyReportRunRead)
async def run_report(
    request: ReportRunRequest,
    db: AsyncSession = Depends(get_db),
):
    report = await generate_daily_report(
        db,
        report_date=request.report_date,
        force=request.force,
        send_email=request.send_email,
    )
    return DailyReportRunRead.model_validate(report)
