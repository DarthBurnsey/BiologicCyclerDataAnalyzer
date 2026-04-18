"""Schemas for live cycler collection, anomalies, and reporting."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CyclerVendor(str, Enum):
    BIOLOGIC = "biologic"
    NEWARE = "neware"
    MTI = "mti"


class ParserType(str, Enum):
    AUTO = "auto"
    BIOLOGIC_CSV = "biologic_csv"
    NEWARE_XLSX = "neware_xlsx"
    MTI_XLSX = "mti_xlsx"


class ArtifactStatus(str, Enum):
    DISCOVERED = "discovered"
    INGESTED = "ingested"
    IGNORED = "ignored"
    FAILED = "failed"


class MappingDecisionStatus(str, Enum):
    AUTO_ACCEPTED = "auto_accepted"
    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class MappingReviewResolution(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ChannelStatus(str, Enum):
    UNKNOWN = "unknown"
    ACTIVE = "active"
    STALLED = "stalled"
    OFFLINE = "offline"
    COMPLETED = "completed"
    ERROR = "error"


class RunStatus(str, Enum):
    DISCOVERED = "discovered"
    ACTIVE = "active"
    PAUSED = "paused"
    STALLED = "stalled"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    ERROR = "error"


class IngestionOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"


class RunLifecycleEventType(str, Enum):
    INGESTED = "ingested"
    REPROCESSED = "reprocessed"
    STALLED = "stalled"
    COMPLETED = "completed"
    RESUMED = "resumed"
    FAILED = "failed"


class AnomalySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


class NotificationTargetType(str, Enum):
    EMAIL = "email"


class CyclerSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    vendor: CyclerVendor
    export_path: str = Field(..., min_length=1, max_length=2000)
    parser_type: ParserType = ParserType.AUTO
    poll_interval_seconds: int = Field(300, ge=60, le=3600)
    stable_window_seconds: int = Field(120, ge=10, le=3600)
    timezone: str = Field("America/Chicago", min_length=3, max_length=64)
    file_glob: str = Field("*", min_length=1, max_length=255)
    enabled: bool = True
    metadata_json: Optional[Dict[str, Any]] = None


class CyclerSourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    export_path: Optional[str] = Field(None, min_length=1, max_length=2000)
    parser_type: Optional[ParserType] = None
    poll_interval_seconds: Optional[int] = Field(None, ge=60, le=3600)
    stable_window_seconds: Optional[int] = Field(None, ge=10, le=3600)
    timezone: Optional[str] = Field(None, min_length=3, max_length=64)
    file_glob: Optional[str] = Field(None, min_length=1, max_length=255)
    enabled: Optional[bool] = None
    metadata_json: Optional[Dict[str, Any]] = None


class CyclerSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    vendor: CyclerVendor
    export_path: str
    parser_type: ParserType
    poll_interval_seconds: int
    stable_window_seconds: int
    timezone: str
    file_glob: str
    enabled: bool
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class CyclerChannelCreate(BaseModel):
    source_id: int
    source_channel_id: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    file_pattern: Optional[str] = Field(None, max_length=255)
    project_id: Optional[int] = None
    experiment_id: Optional[int] = None
    cell_id: Optional[int] = None
    cell_build_id: Optional[int] = None
    metadata_json: Optional[Dict[str, Any]] = None


class CyclerChannelUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    file_pattern: Optional[str] = Field(None, max_length=255)
    project_id: Optional[int] = None
    experiment_id: Optional[int] = None
    cell_id: Optional[int] = None
    cell_build_id: Optional[int] = None
    status: Optional[ChannelStatus] = None
    metadata_json: Optional[Dict[str, Any]] = None


class CyclerChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    source_channel_id: str
    display_name: Optional[str]
    file_pattern: Optional[str]
    project_id: Optional[int]
    experiment_id: Optional[int]
    cell_id: Optional[int]
    cell_build_id: Optional[int]
    status: ChannelStatus
    last_seen_at: Optional[datetime]
    last_file_path: Optional[str]
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class CyclerArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    channel_id: Optional[int]
    run_id: Optional[int]
    file_path: str
    file_name: str
    fingerprint: str
    size_bytes: int
    modified_at: datetime
    discovered_at: datetime
    stable_at: Optional[datetime]
    ingested_at: Optional[datetime]
    status: ArtifactStatus
    error_message: Optional[str]


class CyclePointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cycle_index: int
    sample_time: Optional[datetime]
    charge_capacity_mah: Optional[float]
    discharge_capacity_mah: Optional[float]
    specific_charge_capacity_mah_g: Optional[float]
    specific_discharge_capacity_mah_g: Optional[float]
    efficiency: Optional[float]


class AnomalyEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: Optional[int]
    channel_id: Optional[int]
    run_id: Optional[int]
    cell_id: Optional[int]
    event_key: str
    anomaly_type: str
    severity: AnomalySeverity
    title: str
    description: str
    recommendation: Optional[str]
    confidence: Optional[float]
    active: bool
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    first_seen_at: datetime
    last_seen_at: datetime
    metadata_json: Optional[Dict[str, Any]]


class ParserReleaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    version: str
    parser_type: ParserType
    vendor: Optional[CyclerVendor]
    code_reference: Optional[str]
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class MappingDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    channel_id: Optional[int]
    artifact_id: int
    run_id: Optional[int]
    project_id: Optional[int]
    experiment_id: Optional[int]
    cell_id: Optional[int]
    cell_build_id: Optional[int]
    status: MappingDecisionStatus
    mapping_rule: Optional[str]
    confidence: Optional[float]
    review_reason: Optional[str]
    decided_by: Optional[str]
    decided_at: Optional[datetime]
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class IngestionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    channel_id: Optional[int]
    artifact_id: int
    run_id: Optional[int]
    parser_release_id: Optional[int]
    mapping_decision_id: Optional[int]
    outcome: IngestionOutcome
    was_reprocessed: bool
    started_at: datetime
    finished_at: Optional[datetime]
    error_message: Optional[str]
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime


class RunLifecycleEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    ingestion_run_id: Optional[int]
    event_type: RunLifecycleEventType
    status: Optional[RunStatus]
    summary: str
    metadata_json: Optional[Dict[str, Any]]
    occurred_at: datetime


class TestRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    channel_id: Optional[int]
    project_id: Optional[int]
    experiment_id: Optional[int]
    cell_id: Optional[int]
    cell_build_id: Optional[int]
    protocol_version_id: Optional[int]
    fixture_id: Optional[int]
    equipment_asset_id: Optional[int]
    parser_release_id: Optional[int]
    run_key: str
    source_file_path: str
    parser_type: ParserType
    status: RunStatus
    started_at: Optional[datetime]
    last_sampled_at: Optional[datetime]
    completed_at: Optional[datetime]
    last_cycle_index: Optional[int]
    latest_charge_capacity_mah: Optional[float]
    latest_discharge_capacity_mah: Optional[float]
    latest_efficiency: Optional[float]
    capacity_retention_pct: Optional[float]
    summary_json: Optional[Dict[str, Any]]
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class TestRunDetailRead(TestRunRead):
    cycle_points: List[CyclePointRead] = []
    anomalies: List[AnomalyEventRead] = []
    artifacts: List[CyclerArtifactRead] = []
    parser_release: Optional[ParserReleaseRead] = None
    mapping_decisions: List[MappingDecisionRead] = []
    ingestion_runs: List[IngestionRunRead] = []
    lifecycle_events: List[RunLifecycleEventRead] = []


class RunProvenanceRead(BaseModel):
    run: TestRunRead
    parser_release: Optional[ParserReleaseRead] = None
    artifacts: List[CyclerArtifactRead] = []
    mapping_decisions: List[MappingDecisionRead] = []
    ingestion_runs: List[IngestionRunRead] = []
    lifecycle_events: List[RunLifecycleEventRead] = []


class MappingReviewItemRead(BaseModel):
    artifact: CyclerArtifactRead
    mapping_decision: MappingDecisionRead
    latest_ingestion_run: Optional[IngestionRunRead] = None


class MappingReviewResolveRequest(BaseModel):
    resolution: MappingReviewResolution
    reviewed_by: str = Field("operator", min_length=1, max_length=255)
    review_reason: Optional[str] = Field(None, max_length=4000)
    channel_id: Optional[int] = None
    cell_id: Optional[int] = None
    cell_build_id: Optional[int] = None
    file_pattern: Optional[str] = Field(None, min_length=1, max_length=255)
    reprocess_now: bool = True


class MappingReviewResolutionRead(BaseModel):
    mapping_decision: MappingDecisionRead
    artifact: CyclerArtifactRead
    latest_ingestion_run: Optional[IngestionRunRead] = None
    run: Optional[TestRunRead] = None


class NotificationTargetCreate(BaseModel):
    project_id: Optional[int] = None
    target_type: NotificationTargetType = NotificationTargetType.EMAIL
    destination: str = Field(..., min_length=3, max_length=500)
    name: Optional[str] = Field(None, max_length=255)
    enabled: bool = True


class NotificationTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: Optional[int]
    target_type: NotificationTargetType
    destination: str
    name: Optional[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class DailyReportRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_date: date
    started_at: datetime
    finished_at: Optional[datetime]
    delivery_status: DeliveryStatus
    email_subject: Optional[str]
    recipient_count: int
    summary_markdown: str
    summary_json: Optional[Dict[str, Any]]
    error_message: Optional[str]


class LiveDashboardRead(BaseModel):
    generated_at: datetime
    sources: Dict[str, int]
    channels: Dict[str, int]
    runs: Dict[str, int]
    anomalies: Dict[str, int]
    active_runs: List[TestRunRead]
    recent_anomalies: List[AnomalyEventRead]
    recent_reports: List[DailyReportRunRead]


class CollectorRunResult(BaseModel):
    generated_at: datetime
    sources_polled: int
    files_seen: int
    files_ingested: int
    files_skipped: int
    files_failed: int
    anomalies_raised: int
    next_poll_seconds: int


class ReportRunRequest(BaseModel):
    report_date: Optional[date] = None
    force: bool = False
    send_email: bool = True


class AcknowledgeAnomalyRequest(BaseModel):
    acknowledged_by: str = Field("operator", min_length=1, max_length=255)
