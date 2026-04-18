"""Metrics API routes for backend-native derived metrics."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.metrics import MetricScope
from app.schemas.metrics import MetricDefinitionRead, RunMetricsRead
from app.services.metrics import get_run_metrics_payload, list_metric_definitions

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/definitions", response_model=list[MetricDefinitionRead])
async def get_metric_definitions(
    scope: Optional[MetricScope] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    definitions = await list_metric_definitions(db, scope=scope)
    return [MetricDefinitionRead.model_validate(definition) for definition in definitions]


@router.get("/runs/{run_id}", response_model=RunMetricsRead)
async def get_run_metrics(run_id: int, db: AsyncSession = Depends(get_db)):
    payload = await get_run_metrics_payload(db, run_id=run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run metrics not found")
    return RunMetricsRead.model_validate(payload)
