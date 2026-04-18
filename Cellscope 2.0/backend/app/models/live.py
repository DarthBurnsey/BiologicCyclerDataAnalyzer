"""ORM models for live cycler collection, anomaly tracking, and reporting."""

import enum
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CyclerVendor(str, enum.Enum):
    BIOLOGIC = "biologic"
    NEWARE = "neware"
    MTI = "mti"


class ParserType(str, enum.Enum):
    AUTO = "auto"
    BIOLOGIC_CSV = "biologic_csv"
    NEWARE_XLSX = "neware_xlsx"
    MTI_XLSX = "mti_xlsx"


class MappingDecisionStatus(str, enum.Enum):
    AUTO_ACCEPTED = "auto_accepted"
    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ChannelStatus(str, enum.Enum):
    UNKNOWN = "unknown"
    ACTIVE = "active"
    STALLED = "stalled"
    OFFLINE = "offline"
    COMPLETED = "completed"
    ERROR = "error"


class ArtifactStatus(str, enum.Enum):
    DISCOVERED = "discovered"
    INGESTED = "ingested"
    IGNORED = "ignored"
    FAILED = "failed"


class RunStatus(str, enum.Enum):
    DISCOVERED = "discovered"
    ACTIVE = "active"
    PAUSED = "paused"
    STALLED = "stalled"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    ERROR = "error"


class IngestionOutcome(str, enum.Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"


class RunLifecycleEventType(str, enum.Enum):
    INGESTED = "ingested"
    REPROCESSED = "reprocessed"
    STALLED = "stalled"
    COMPLETED = "completed"
    RESUMED = "resumed"
    FAILED = "failed"


class AnomalySeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


class NotificationTargetType(str, enum.Enum):
    EMAIL = "email"


class CyclerSource(Base):
    """A cycler export location monitored by the collector."""

    __tablename__ = "cycler_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vendor: Mapped[CyclerVendor] = mapped_column(Enum(CyclerVendor), nullable=False)
    export_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    parser_type: Mapped[ParserType] = mapped_column(
        Enum(ParserType), default=ParserType.AUTO, nullable=False
    )
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    stable_window_seconds: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Chicago", nullable=False)
    file_glob: Mapped[str] = mapped_column(String(255), default="*", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    channels: Mapped[List["CyclerChannel"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )
    artifacts: Mapped[List["CyclerArtifact"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )
    checkpoints: Mapped[List["IngestionCheckpoint"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )
    mapping_decisions: Mapped[List["MappingDecision"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )
    ingestion_runs: Mapped[List["IngestionRun"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )


class CyclerChannel(Base):
    """Mapping between a source channel and a CellScope cell."""

    __tablename__ = "cycler_channels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("cycler_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    file_pattern: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    experiment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True
    )
    cell_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cells.id", ondelete="SET NULL"), nullable=True
    )
    cell_build_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_cell_builds.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ChannelStatus] = mapped_column(
        Enum(ChannelStatus), default=ChannelStatus.UNKNOWN, nullable=False
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    last_file_path: Mapped[Optional[str]] = mapped_column(String(2000), default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source_id", "source_channel_id", name="uq_source_channel"),
    )

    source: Mapped["CyclerSource"] = relationship(back_populates="channels")
    artifacts: Mapped[List["CyclerArtifact"]] = relationship(back_populates="channel", lazy="selectin")
    runs: Mapped[List["TestRun"]] = relationship(back_populates="channel", lazy="selectin")
    mapping_decisions: Mapped[List["MappingDecision"]] = relationship(
        back_populates="channel", lazy="selectin"
    )
    ingestion_runs: Mapped[List["IngestionRun"]] = relationship(
        back_populates="channel", lazy="selectin"
    )


class CyclerArtifact(Base):
    """File-level provenance for every discovered export artifact."""

    __tablename__ = "cycler_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("cycler_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cycler_channels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    file_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    stable_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    status: Mapped[ArtifactStatus] = mapped_column(
        Enum(ArtifactStatus), default=ArtifactStatus.DISCOVERED, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)

    source: Mapped["CyclerSource"] = relationship(back_populates="artifacts")
    channel: Mapped[Optional["CyclerChannel"]] = relationship(back_populates="artifacts")
    run: Mapped[Optional["TestRun"]] = relationship(back_populates="artifacts")
    mapping_decisions: Mapped[List["MappingDecision"]] = relationship(
        back_populates="artifact", lazy="selectin"
    )
    ingestion_runs: Mapped[List["IngestionRun"]] = relationship(
        back_populates="artifact", lazy="selectin"
    )


class IngestionCheckpoint(Base):
    """Last-known ingestion state for a given file path within a source."""

    __tablename__ = "ingestion_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("cycler_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    file_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    last_file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    last_modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    last_parsed_cycle: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source_id", "file_path", name="uq_source_checkpoint_file"),
    )

    source: Mapped["CyclerSource"] = relationship(back_populates="checkpoints")


class ParserRelease(Base):
    """Versioned parser provenance for normalized run ingestion."""

    __tablename__ = "parser_releases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_type: Mapped[ParserType] = mapped_column(Enum(ParserType), nullable=False)
    vendor: Mapped[Optional[CyclerVendor]] = mapped_column(Enum(CyclerVendor), nullable=True)
    code_reference: Mapped[Optional[str]] = mapped_column(String(500), default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("name", "version", "parser_type", "vendor", name="uq_parser_release"),
    )

    runs: Mapped[List["TestRun"]] = relationship(back_populates="parser_release", lazy="selectin")
    ingestion_runs: Mapped[List["IngestionRun"]] = relationship(
        back_populates="parser_release", lazy="selectin"
    )
    metric_runs: Mapped[List["MetricRun"]] = relationship(
        back_populates="parser_release", lazy="selectin"
    )


class MappingDecision(Base):
    """Auditable mapping result from an incoming artifact to a canonical build."""

    __tablename__ = "mapping_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("cycler_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cycler_channels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey("cycler_artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    experiment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cell_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cells.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cell_build_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_cell_builds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[MappingDecisionStatus] = mapped_column(
        Enum(MappingDecisionStatus), default=MappingDecisionStatus.PENDING_REVIEW, nullable=False
    )
    mapping_rule: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    confidence: Mapped[Optional[float]] = mapped_column(Float, default=None)
    review_reason: Mapped[Optional[str]] = mapped_column(Text, default=None)
    decided_by: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("artifact_id", name="uq_mapping_decision_artifact"),
    )

    source: Mapped["CyclerSource"] = relationship(back_populates="mapping_decisions")
    channel: Mapped[Optional["CyclerChannel"]] = relationship(back_populates="mapping_decisions")
    artifact: Mapped["CyclerArtifact"] = relationship(back_populates="mapping_decisions")
    run: Mapped[Optional["TestRun"]] = relationship(back_populates="mapping_decisions")
    ingestion_runs: Mapped[List["IngestionRun"]] = relationship(
        back_populates="mapping_decision", lazy="selectin"
    )


class IngestionRun(Base):
    """A single audited processing attempt for a discovered artifact."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("cycler_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cycler_channels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey("cycler_artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parser_release_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("parser_releases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mapping_decision_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("mapping_decisions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    outcome: Mapped[IngestionOutcome] = mapped_column(
        Enum(IngestionOutcome), default=IngestionOutcome.SUCCEEDED, nullable=False
    )
    was_reprocessed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source: Mapped["CyclerSource"] = relationship(back_populates="ingestion_runs")
    channel: Mapped[Optional["CyclerChannel"]] = relationship(back_populates="ingestion_runs")
    artifact: Mapped["CyclerArtifact"] = relationship(back_populates="ingestion_runs")
    run: Mapped[Optional["TestRun"]] = relationship(back_populates="ingestion_runs")
    parser_release: Mapped[Optional["ParserRelease"]] = relationship(back_populates="ingestion_runs")
    mapping_decision: Mapped[Optional["MappingDecision"]] = relationship(
        back_populates="ingestion_runs"
    )
    lifecycle_events: Mapped[List["RunLifecycleEvent"]] = relationship(
        back_populates="ingestion_run", lazy="selectin"
    )
    metric_runs: Mapped[List["MetricRun"]] = relationship(
        back_populates="ingestion_run", lazy="selectin"
    )


class TestRun(Base):
    """Normalized representation of a cycling run linked to a CellScope cell."""

    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("cycler_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cycler_channels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    experiment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cell_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cells.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cell_build_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_cell_builds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    protocol_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_protocol_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fixture_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_fixtures.id", ondelete="SET NULL"), nullable=True, index=True
    )
    equipment_asset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_equipment_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parser_release_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("parser_releases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    source_file_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_file_hash: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    parser_type: Mapped[ParserType] = mapped_column(
        Enum(ParserType), default=ParserType.AUTO, nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.ACTIVE, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    last_sampled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    last_cycle_index: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    latest_charge_capacity_mah: Mapped[Optional[float]] = mapped_column(Float, default=None)
    latest_discharge_capacity_mah: Mapped[Optional[float]] = mapped_column(Float, default=None)
    latest_efficiency: Mapped[Optional[float]] = mapped_column(Float, default=None)
    capacity_retention_pct: Mapped[Optional[float]] = mapped_column(Float, default=None)
    summary_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    channel: Mapped[Optional["CyclerChannel"]] = relationship(back_populates="runs")
    cycle_points: Mapped[List["CyclePoint"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )
    anomalies: Mapped[List["AnomalyEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )
    artifacts: Mapped[List["CyclerArtifact"]] = relationship(back_populates="run", lazy="selectin")
    parser_release: Mapped[Optional["ParserRelease"]] = relationship(
        back_populates="runs", lazy="selectin"
    )
    mapping_decisions: Mapped[List["MappingDecision"]] = relationship(
        back_populates="run", lazy="selectin"
    )
    ingestion_runs: Mapped[List["IngestionRun"]] = relationship(
        back_populates="run", lazy="selectin"
    )
    lifecycle_events: Mapped[List["RunLifecycleEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )
    metric_runs: Mapped[List["MetricRun"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )


class RunLifecycleEvent(Base):
    """Immutable lifecycle and provenance events for a run."""

    __tablename__ = "run_lifecycle_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingestion_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[RunLifecycleEventType] = mapped_column(
        Enum(RunLifecycleEventType), nullable=False
    )
    status: Mapped[Optional[RunStatus]] = mapped_column(Enum(RunStatus), default=None)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    run: Mapped["TestRun"] = relationship(back_populates="lifecycle_events")
    ingestion_run: Mapped[Optional["IngestionRun"]] = relationship(back_populates="lifecycle_events")


class CyclePoint(Base):
    """Per-cycle normalized points extracted from a run export."""

    __tablename__ = "cycle_points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cycle_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    charge_capacity_mah: Mapped[Optional[float]] = mapped_column(Float, default=None)
    discharge_capacity_mah: Mapped[Optional[float]] = mapped_column(Float, default=None)
    specific_charge_capacity_mah_g: Mapped[Optional[float]] = mapped_column(Float, default=None)
    specific_discharge_capacity_mah_g: Mapped[Optional[float]] = mapped_column(Float, default=None)
    efficiency: Mapped[Optional[float]] = mapped_column(Float, default=None)
    payload_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("run_id", "cycle_index", name="uq_run_cycle_index"),
    )

    run: Mapped["TestRun"] = relationship(back_populates="cycle_points")


class AnomalyEvent(Base):
    """Persisted anomaly event raised by parser, rules, or runtime monitoring."""

    __tablename__ = "anomaly_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cycler_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cycler_channels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    cell_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cells.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    anomaly_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[AnomalySeverity] = mapped_column(Enum(AnomalySeverity), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, default=None)
    confidence: Mapped[Optional[float]] = mapped_column(Float, default=None)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)

    run: Mapped[Optional["TestRun"]] = relationship(back_populates="anomalies")


class NotificationTarget(Base):
    """Destination for daily reports and runtime notifications."""

    __tablename__ = "notification_targets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_type: Mapped[NotificationTargetType] = mapped_column(
        Enum(NotificationTargetType), default=NotificationTargetType.EMAIL, nullable=False
    )
    destination: Mapped[str] = mapped_column(String(500), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class DailyReportRun(Base):
    """Stored daily report payloads for in-app access and email delivery tracking."""

    __tablename__ = "daily_report_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus), default=DeliveryStatus.PENDING, nullable=False
    )
    email_subject: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    recipient_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    summary_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
