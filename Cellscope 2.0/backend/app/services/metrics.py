"""Backend-native derived metrics registry, computation, and read payloads."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.live import CyclePoint, TestRun
from app.models.metrics import (
    CycleMetricValue,
    MetricDefinition,
    MetricRun,
    MetricRunStatus,
    MetricScope,
    MetricValueType,
    MetricVersion,
    RunMetricValue,
)


def utcnow() -> datetime:
    """Return a timezone-naive UTC timestamp for SQLite compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class MetricSpec:
    key: str
    name: str
    description: str
    scope: MetricScope
    unit: Optional[str]
    version: str
    code_reference: str
    value_type: MetricValueType = MetricValueType.NUMERIC
    metadata_json: Optional[Dict[str, Any]] = None


RUN_METRIC_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        key="capacity_retention_pct",
        name="Capacity Retention",
        description="Latest retained discharge capacity relative to the cycles 5-10 baseline when available.",
        scope=MetricScope.RUN,
        unit="%",
        version="1.0.0",
        code_reference="app.services.metrics.compute_metrics_for_run",
        metadata_json={"source": "cycle_points_dashboard_baseline"},
    ),
    MetricSpec(
        key="fade_rate_pct_per_100_cycles",
        name="Fade Rate",
        description="Linearized capacity fade expressed as percentage loss per 100 cycles.",
        scope=MetricScope.RUN,
        unit="% per 100 cycles",
        version="1.0.0",
        code_reference="app.services.metrics.compute_metrics_for_run",
        metadata_json={"source": "cycle_points_dashboard_linear_fit"},
    ),
    MetricSpec(
        key="average_coulombic_efficiency_pct",
        name="Average Coulombic Efficiency",
        description="Average coulombic efficiency across valid cycles.",
        scope=MetricScope.RUN,
        unit="%",
        version="1.0.0",
        code_reference="app.services.metrics.compute_metrics_for_run",
        metadata_json={"source": "live_summary_or_cycle_points"},
    ),
    MetricSpec(
        key="latest_charge_capacity_mah",
        name="Latest Charge Capacity",
        description="Most recent absolute charge capacity reported for the run.",
        scope=MetricScope.RUN,
        unit="mAh",
        version="1.0.0",
        code_reference="app.services.metrics.compute_metrics_for_run",
    ),
    MetricSpec(
        key="latest_discharge_capacity_mah",
        name="Latest Discharge Capacity",
        description="Most recent absolute discharge capacity reported for the run.",
        scope=MetricScope.RUN,
        unit="mAh",
        version="1.0.0",
        code_reference="app.services.metrics.compute_metrics_for_run",
    ),
    MetricSpec(
        key="latest_efficiency_pct",
        name="Latest Efficiency",
        description="Most recent efficiency value reported for the run.",
        scope=MetricScope.RUN,
        unit="%",
        version="1.0.0",
        code_reference="app.services.metrics.compute_metrics_for_run",
    ),
    MetricSpec(
        key="last_cycle_index",
        name="Last Cycle Index",
        description="Most recent cycle index observed for the run.",
        scope=MetricScope.RUN,
        unit="cycles",
        version="1.0.0",
        code_reference="app.services.metrics.compute_metrics_for_run",
    ),
)

CYCLE_METRIC_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        key="discharge_capacity_mah",
        name="Cycle Discharge Capacity",
        description="Absolute discharge capacity for a cycle.",
        scope=MetricScope.CYCLE,
        unit="mAh",
        version="1.0.0",
        code_reference="app.services.metrics.compute_metrics_for_run",
    ),
    MetricSpec(
        key="specific_discharge_capacity_mah_g",
        name="Cycle Specific Discharge Capacity",
        description="Specific discharge capacity for a cycle.",
        scope=MetricScope.CYCLE,
        unit="mAh/g",
        version="1.0.0",
        code_reference="app.services.metrics.compute_metrics_for_run",
    ),
    MetricSpec(
        key="efficiency_pct",
        name="Cycle Efficiency",
        description="Efficiency reported for a cycle.",
        scope=MetricScope.CYCLE,
        unit="%",
        version="1.0.0",
        code_reference="app.services.metrics.compute_metrics_for_run",
    ),
    MetricSpec(
        key="retention_pct",
        name="Cycle Retention",
        description="Cycle-level retained capacity relative to the cycles 5-10 baseline when available.",
        scope=MetricScope.CYCLE,
        unit="%",
        version="1.0.0",
        code_reference="app.services.metrics.compute_metrics_for_run",
        metadata_json={"source": "cycle_points_dashboard_baseline"},
    ),
)

ALL_METRIC_SPECS: tuple[MetricSpec, ...] = RUN_METRIC_SPECS + CYCLE_METRIC_SPECS


@dataclass
class RegistryEntry:
    definition: MetricDefinition
    version: MetricVersion
    spec: MetricSpec


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _summary_value(run: TestRun, key: str) -> Optional[float]:
    summary = run.summary_json if isinstance(run.summary_json, dict) else {}
    return _safe_float(summary.get(key))


def _load_cycle_points(run: TestRun) -> list[CyclePoint]:
    return sorted(run.cycle_points or [], key=lambda point: point.cycle_index)


def _retention_series(
    run: TestRun,
    cycle_points: Iterable[CyclePoint],
) -> tuple[list[tuple[int, float]], Optional[float], str]:
    del run
    discharge_series = [
        (point.cycle_index, float(point.discharge_capacity_mah))
        for point in cycle_points
        if _safe_float(point.discharge_capacity_mah) and float(point.discharge_capacity_mah) > 0
    ]
    if discharge_series:
        baseline = _dashboard_retention_baseline(discharge_series)
        return discharge_series, baseline, "discharge_capacity_mah"

    specific_series = [
        (point.cycle_index, float(point.specific_discharge_capacity_mah_g))
        for point in cycle_points
        if _safe_float(point.specific_discharge_capacity_mah_g)
        and float(point.specific_discharge_capacity_mah_g) > 0
    ]
    if specific_series:
        baseline = _dashboard_retention_baseline(specific_series)
        return specific_series, baseline, "specific_discharge_capacity_mah_g"
    return [], None, "discharge_capacity_mah"


def _dashboard_retention_baseline(
    series: list[tuple[int, float]],
) -> Optional[float]:
    if not series:
        return None
    cycles_five_to_ten = [
        value for cycle_index, value in series if cycle_index >= 5 and cycle_index <= 10
    ]
    if cycles_five_to_ten:
        return float(sum(cycles_five_to_ten) / len(cycles_five_to_ten))
    return series[0][1]


def _compute_cycle_retention_map(
    run: TestRun,
    cycle_points: Iterable[CyclePoint],
) -> dict[int, float]:
    series, baseline, _source = _retention_series(run, cycle_points)
    if baseline is None or baseline <= 0:
        return {}
    return {
        cycle_index: round((value / baseline) * 100.0, 4)
        for cycle_index, value in series
    }


def _compute_fade_rate_from_cycles(run: TestRun, cycle_points: Iterable[CyclePoint]) -> Optional[float]:
    del run
    absolute_series = [
        (point.cycle_index, float(point.discharge_capacity_mah))
        for point in cycle_points
        if _safe_float(point.discharge_capacity_mah) and float(point.discharge_capacity_mah) > 0
    ]
    specific_series = [
        (point.cycle_index, float(point.specific_discharge_capacity_mah_g))
        for point in cycle_points
        if _safe_float(point.specific_discharge_capacity_mah_g)
        and float(point.specific_discharge_capacity_mah_g) > 0
    ]
    series = absolute_series or specific_series
    if len(series) < 10:
        return None
    baseline = series[0][1]
    if baseline <= 0:
        return None
    cycle_indexes = np.asarray([cycle_index for cycle_index, _value in series], dtype=float)
    retention_values = np.asarray(
        [(value / baseline) * 100.0 for _cycle_index, value in series],
        dtype=float,
    )
    if len(cycle_indexes) < 2:
        return None
    try:
        slope, _intercept = np.polyfit(cycle_indexes, retention_values, 1)
        return round(float(-slope * 100.0), 3)
    except Exception:
        first_retention = float(retention_values[0])
        last_retention = float(retention_values[-1])
        cycle_delta = float(cycle_indexes[-1] - cycle_indexes[0])
        if cycle_delta <= 0:
            return None
        return round(((first_retention - last_retention) / cycle_delta) * 100.0, 3)


def _compute_average_efficiency(cycle_points: Iterable[CyclePoint]) -> Optional[float]:
    values = [
        float(point.efficiency)
        for point in cycle_points
        if _safe_float(point.efficiency) is not None
    ]
    if not values:
        return None
    return round(float(sum(values) / len(values)), 4)


def _compute_run_metric_values(
    run: TestRun,
    cycle_points: list[CyclePoint],
) -> dict[str, Optional[float]]:
    cycle_retention = _compute_cycle_retention_map(run, cycle_points)

    return {
        "capacity_retention_pct": cycle_retention.get(run.last_cycle_index or -1)
        or _safe_float(run.capacity_retention_pct)
        or _summary_value(run, "capacity_retention_pct"),
        "fade_rate_pct_per_100_cycles": _compute_fade_rate_from_cycles(run, cycle_points)
        or _summary_value(run, "fade_rate_per_100"),
        "average_coulombic_efficiency_pct": _summary_value(run, "coulombic_efficiency")
        or _compute_average_efficiency(cycle_points),
        "latest_charge_capacity_mah": _safe_float(run.latest_charge_capacity_mah),
        "latest_discharge_capacity_mah": _safe_float(run.latest_discharge_capacity_mah),
        "latest_efficiency_pct": _safe_float(run.latest_efficiency),
        "last_cycle_index": _safe_float(run.last_cycle_index),
    }


def _compute_cycle_metric_values(
    run: TestRun,
    cycle_points: list[CyclePoint],
) -> dict[str, dict[int, Optional[float]]]:
    cycle_retention = _compute_cycle_retention_map(run, cycle_points)
    return {
        "discharge_capacity_mah": {
            point.cycle_index: _safe_float(point.discharge_capacity_mah) for point in cycle_points
        },
        "specific_discharge_capacity_mah_g": {
            point.cycle_index: _safe_float(point.specific_discharge_capacity_mah_g)
            for point in cycle_points
        },
        "efficiency_pct": {
            point.cycle_index: _safe_float(point.efficiency) for point in cycle_points
        },
        "retention_pct": cycle_retention,
    }


async def ensure_metric_registry(session: AsyncSession) -> dict[str, RegistryEntry]:
    """Create the first backend-native metric registry entries if needed."""
    registry: dict[str, RegistryEntry] = {}

    for spec in ALL_METRIC_SPECS:
        result = await session.execute(
            select(MetricDefinition).where(MetricDefinition.key == spec.key)
        )
        definition = result.scalar_one_or_none()
        if definition is None:
            definition = MetricDefinition(
                key=spec.key,
                name=spec.name,
                description=spec.description,
                scope=spec.scope,
                unit=spec.unit,
                value_type=spec.value_type,
                metadata_json=spec.metadata_json,
            )
            session.add(definition)
            await session.flush()
        else:
            definition.name = spec.name
            definition.description = spec.description
            definition.scope = spec.scope
            definition.unit = spec.unit
            definition.value_type = spec.value_type
            definition.metadata_json = spec.metadata_json

        result = await session.execute(
            select(MetricVersion).where(
                MetricVersion.metric_definition_id == definition.id,
                MetricVersion.version == spec.version,
            )
        )
        version = result.scalar_one_or_none()
        if version is None:
            version = MetricVersion(
                metric_definition_id=definition.id,
                version=spec.version,
                code_reference=spec.code_reference,
                is_active=True,
                metadata_json={"metric_key": spec.key},
            )
            session.add(version)
            await session.flush()
        else:
            version.code_reference = spec.code_reference
            version.is_active = True
            version.metadata_json = {"metric_key": spec.key}

        registry[spec.key] = RegistryEntry(definition=definition, version=version, spec=spec)

    return registry


def _build_input_signature(run: TestRun, registry: dict[str, RegistryEntry]) -> str:
    payload = {
        "run_id": run.id,
        "source_file_hash": run.source_file_hash,
        "parser_release_id": run.parser_release_id,
        "last_cycle_index": run.last_cycle_index,
        "metric_versions": {
            key: entry.version.version for key, entry in sorted(registry.items(), key=lambda item: item[0])
        },
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


async def list_metric_definitions(
    session: AsyncSession,
    *,
    scope: Optional[MetricScope] = None,
) -> list[MetricDefinition]:
    await ensure_metric_registry(session)
    stmt = select(MetricDefinition).order_by(MetricDefinition.scope.asc(), MetricDefinition.key.asc())
    if scope is not None:
        stmt = stmt.where(MetricDefinition.scope == scope)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def compute_metrics_for_run(
    session: AsyncSession,
    *,
    run_id: int,
    ingestion_run_id: Optional[int] = None,
    force: bool = False,
) -> MetricRun:
    """Compute and persist backend-native metrics for a live run."""
    registry = await ensure_metric_registry(session)
    result = await session.execute(
        select(TestRun)
        .options(selectinload(TestRun.cycle_points))
        .where(TestRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise ValueError(f"Run {run_id} does not exist")

    input_signature = _build_input_signature(run, registry)

    if ingestion_run_id is not None and not force:
        result = await session.execute(
            select(MetricRun)
            .options(
                selectinload(MetricRun.run_metric_values).selectinload(RunMetricValue.definition),
                selectinload(MetricRun.run_metric_values).selectinload(RunMetricValue.metric_version),
                selectinload(MetricRun.cycle_metric_values).selectinload(CycleMetricValue.definition),
                selectinload(MetricRun.cycle_metric_values).selectinload(CycleMetricValue.metric_version),
            )
            .where(MetricRun.ingestion_run_id == ingestion_run_id)
        )
        existing_for_ingestion = result.scalar_one_or_none()
        if existing_for_ingestion is not None:
            return existing_for_ingestion

    if not force:
        result = await session.execute(
            select(MetricRun)
            .options(
                selectinload(MetricRun.run_metric_values).selectinload(RunMetricValue.definition),
                selectinload(MetricRun.run_metric_values).selectinload(RunMetricValue.metric_version),
                selectinload(MetricRun.cycle_metric_values).selectinload(CycleMetricValue.definition),
                selectinload(MetricRun.cycle_metric_values).selectinload(CycleMetricValue.metric_version),
            )
            .where(
                MetricRun.test_run_id == run.id,
                MetricRun.input_signature == input_signature,
                MetricRun.status == MetricRunStatus.SUCCEEDED,
            )
            .order_by(MetricRun.id.desc())
        )
        existing = result.scalars().first()
        if existing is not None:
            return existing

    metric_run = MetricRun(
        test_run_id=run.id,
        ingestion_run_id=ingestion_run_id,
        parser_release_id=run.parser_release_id,
        input_signature=input_signature,
        status=MetricRunStatus.SUCCEEDED,
        started_at=utcnow(),
        metadata_json={
            "run_id": run.id,
            "last_cycle_index": run.last_cycle_index,
            "source_file_hash": run.source_file_hash,
        },
    )
    session.add(metric_run)
    await session.flush()

    try:
        cycle_points = _load_cycle_points(run)
        run_metric_values = _compute_run_metric_values(run, cycle_points)
        cycle_metric_values = _compute_cycle_metric_values(run, cycle_points)

        for spec in RUN_METRIC_SPECS:
            entry = registry[spec.key]
            session.add(
                RunMetricValue(
                    metric_run_id=metric_run.id,
                    test_run_id=run.id,
                    metric_definition_id=entry.definition.id,
                    metric_version_id=entry.version.id,
                    value_numeric=run_metric_values.get(spec.key),
                    value_json=None,
                )
            )

        for spec in CYCLE_METRIC_SPECS:
            entry = registry[spec.key]
            for cycle_index, value_numeric in sorted(
                cycle_metric_values.get(spec.key, {}).items(),
                key=lambda item: item[0],
            ):
                session.add(
                    CycleMetricValue(
                        metric_run_id=metric_run.id,
                        test_run_id=run.id,
                        cycle_index=cycle_index,
                        metric_definition_id=entry.definition.id,
                        metric_version_id=entry.version.id,
                        value_numeric=value_numeric,
                        value_json=None,
                    )
                )

        metric_run.finished_at = utcnow()
        metric_run.error_message = None
        await session.flush()
        await session.refresh(metric_run)
        return metric_run
    except Exception as exc:  # noqa: BLE001 - persist failure for auditability
        metric_run.status = MetricRunStatus.FAILED
        metric_run.finished_at = utcnow()
        metric_run.error_message = str(exc)
        await session.flush()
        await session.refresh(metric_run)
        return metric_run


def _serialize_run_metric_value(value: RunMetricValue) -> Dict[str, Any]:
    return {
        "metric_definition_id": value.metric_definition_id,
        "metric_version_id": value.metric_version_id,
        "metric_key": value.definition.key,
        "metric_name": value.definition.name,
        "unit": value.definition.unit,
        "value_numeric": value.value_numeric,
        "value_json": value.value_json,
        "computed_at": value.computed_at,
    }


def _serialize_cycle_metric_value(value: CycleMetricValue) -> Dict[str, Any]:
    return {
        "cycle_index": value.cycle_index,
        "metric_definition_id": value.metric_definition_id,
        "metric_version_id": value.metric_version_id,
        "metric_key": value.definition.key,
        "metric_name": value.definition.name,
        "unit": value.definition.unit,
        "value_numeric": value.value_numeric,
        "value_json": value.value_json,
        "computed_at": value.computed_at,
    }


async def get_run_metrics_payload(
    session: AsyncSession,
    *,
    run_id: int,
) -> Optional[Dict[str, Any]]:
    """Return the latest successful metric batch for a run."""
    result = await session.execute(
        select(MetricRun)
        .options(
            selectinload(MetricRun.run_metric_values).selectinload(RunMetricValue.definition),
            selectinload(MetricRun.run_metric_values).selectinload(RunMetricValue.metric_version),
            selectinload(MetricRun.cycle_metric_values).selectinload(CycleMetricValue.definition),
            selectinload(MetricRun.cycle_metric_values).selectinload(CycleMetricValue.metric_version),
        )
        .where(
            MetricRun.test_run_id == run_id,
            MetricRun.status == MetricRunStatus.SUCCEEDED,
        )
        .order_by(MetricRun.id.desc())
    )
    metric_run = result.scalars().first()
    if metric_run is None:
        return None

    return {
        "metric_run": metric_run,
        "run_metrics": [
            _serialize_run_metric_value(value)
            for value in sorted(metric_run.run_metric_values, key=lambda item: item.definition.key)
        ],
        "cycle_metrics": [
            _serialize_cycle_metric_value(value)
            for value in sorted(
                metric_run.cycle_metric_values,
                key=lambda item: (item.cycle_index, item.definition.key),
            )
        ],
    }
