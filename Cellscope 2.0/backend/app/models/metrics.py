"""ORM models for backend-native metric definitions, runs, and values."""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
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


class MetricScope(str, enum.Enum):
    RUN = "run"
    CYCLE = "cycle"


class MetricValueType(str, enum.Enum):
    NUMERIC = "numeric"
    JSON = "json"


class MetricRunStatus(str, enum.Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class MetricDefinition(Base):
    """Canonical metric registry entry."""

    __tablename__ = "metric_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    scope: Mapped[MetricScope] = mapped_column(Enum(MetricScope), nullable=False, index=True)
    unit: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    value_type: Mapped[MetricValueType] = mapped_column(
        Enum(MetricValueType), default=MetricValueType.NUMERIC, nullable=False
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[List["MetricVersion"]] = relationship(
        back_populates="definition", cascade="all, delete-orphan", lazy="selectin"
    )
    run_values: Mapped[List["RunMetricValue"]] = relationship(
        back_populates="definition", lazy="selectin"
    )
    cycle_values: Mapped[List["CycleMetricValue"]] = relationship(
        back_populates="definition", lazy="selectin"
    )


class MetricVersion(Base):
    """Versioned implementation metadata for a metric definition."""

    __tablename__ = "metric_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_definition_id: Mapped[int] = mapped_column(
        ForeignKey("metric_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    code_reference: Mapped[Optional[str]] = mapped_column(String(500), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("metric_definition_id", "version", name="uq_metric_definition_version"),
    )

    definition: Mapped["MetricDefinition"] = relationship(back_populates="versions")
    run_values: Mapped[List["RunMetricValue"]] = relationship(
        back_populates="metric_version", lazy="selectin"
    )
    cycle_values: Mapped[List["CycleMetricValue"]] = relationship(
        back_populates="metric_version", lazy="selectin"
    )


class MetricRun(Base):
    """Audited metric computation batch for a live run."""

    __tablename__ = "metric_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingestion_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parser_release_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("parser_releases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    input_signature: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[MetricRunStatus] = mapped_column(
        Enum(MetricRunStatus), default=MetricRunStatus.SUCCEEDED, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("test_run_id", "ingestion_run_id", name="uq_metric_run_per_ingestion"),
    )

    run: Mapped["TestRun"] = relationship(back_populates="metric_runs")
    ingestion_run: Mapped[Optional["IngestionRun"]] = relationship(back_populates="metric_runs")
    parser_release: Mapped[Optional["ParserRelease"]] = relationship(
        back_populates="metric_runs"
    )
    run_metric_values: Mapped[List["RunMetricValue"]] = relationship(
        back_populates="metric_run", cascade="all, delete-orphan", lazy="selectin"
    )
    cycle_metric_values: Mapped[List["CycleMetricValue"]] = relationship(
        back_populates="metric_run", cascade="all, delete-orphan", lazy="selectin"
    )


class RunMetricValue(Base):
    """Persisted run-level metric value."""

    __tablename__ = "run_metric_values"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_run_id: Mapped[int] = mapped_column(
        ForeignKey("metric_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_definition_id: Mapped[int] = mapped_column(
        ForeignKey("metric_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_version_id: Mapped[int] = mapped_column(
        ForeignKey("metric_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value_numeric: Mapped[Optional[float]] = mapped_column(Float, default=None)
    value_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("metric_run_id", "metric_definition_id", name="uq_run_metric_value"),
    )

    metric_run: Mapped["MetricRun"] = relationship(back_populates="run_metric_values")
    definition: Mapped["MetricDefinition"] = relationship(back_populates="run_values")
    metric_version: Mapped["MetricVersion"] = relationship(back_populates="run_values")


class CycleMetricValue(Base):
    """Persisted cycle-level metric value."""

    __tablename__ = "cycle_metric_values"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_run_id: Mapped[int] = mapped_column(
        ForeignKey("metric_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cycle_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    metric_definition_id: Mapped[int] = mapped_column(
        ForeignKey("metric_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_version_id: Mapped[int] = mapped_column(
        ForeignKey("metric_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value_numeric: Mapped[Optional[float]] = mapped_column(Float, default=None)
    value_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "metric_run_id",
            "metric_definition_id",
            "cycle_index",
            name="uq_cycle_metric_value",
        ),
    )

    metric_run: Mapped["MetricRun"] = relationship(back_populates="cycle_metric_values")
    definition: Mapped["MetricDefinition"] = relationship(back_populates="cycle_values")
    metric_version: Mapped["MetricVersion"] = relationship(back_populates="cycle_values")
