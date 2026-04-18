"""Schemas for backend-native run and cycle metrics."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class MetricScope(str, Enum):
    RUN = "run"
    CYCLE = "cycle"


class MetricValueType(str, Enum):
    NUMERIC = "numeric"
    JSON = "json"


class MetricRunStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class MetricDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    description: Optional[str]
    scope: MetricScope
    unit: Optional[str]
    value_type: MetricValueType
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class MetricVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_definition_id: int
    version: str
    code_reference: Optional[str]
    is_active: bool
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class MetricRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    test_run_id: int
    ingestion_run_id: Optional[int]
    parser_release_id: Optional[int]
    input_signature: str
    status: MetricRunStatus
    started_at: datetime
    finished_at: Optional[datetime]
    error_message: Optional[str]
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime


class RunMetricValueRead(BaseModel):
    metric_definition_id: int
    metric_version_id: int
    metric_key: str
    metric_name: str
    unit: Optional[str]
    value_numeric: Optional[float]
    value_json: Optional[Dict[str, Any]]
    computed_at: datetime


class CycleMetricValueRead(BaseModel):
    cycle_index: int
    metric_definition_id: int
    metric_version_id: int
    metric_key: str
    metric_name: str
    unit: Optional[str]
    value_numeric: Optional[float]
    value_json: Optional[Dict[str, Any]]
    computed_at: datetime


class RunMetricsRead(BaseModel):
    metric_run: MetricRunRead
    run_metrics: List[RunMetricValueRead]
    cycle_metrics: List[CycleMetricValueRead]
