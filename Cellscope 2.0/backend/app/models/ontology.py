"""Canonical battery ontology models for materials, builds, equipment, and lineage."""

from __future__ import annotations

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


class MaterialCategory(str, enum.Enum):
    CATHODE_ACTIVE = "cathode_active"
    ANODE_ACTIVE = "anode_active"
    ELECTROLYTE_SALT = "electrolyte_salt"
    ELECTROLYTE_SOLVENT = "electrolyte_solvent"
    ELECTROLYTE_ADDITIVE = "electrolyte_additive"
    SEPARATOR = "separator"
    BINDER = "binder"
    CONDUCTIVE_ADDITIVE = "conductive_additive"
    CURRENT_COLLECTOR = "current_collector"
    OTHER = "other"


class ProtocolType(str, enum.Enum):
    FORMATION = "formation"
    CYCLING = "cycling"
    RPT = "rpt"
    PULSE = "pulse"
    EIS = "eis"
    CALENDAR_AGING = "calendar_aging"
    OTHER = "other"


class EquipmentType(str, enum.Enum):
    CYCLER = "cycler"
    CHAMBER = "chamber"
    POTENTIOSTAT = "potentiostat"
    IMPEDANCE_ANALYZER = "impedance_analyzer"
    DISPENSER = "dispenser"
    COATER = "coater"
    CALENDAR = "calendar"
    FIXTURE = "fixture"
    OTHER = "other"


class ProcessType(str, enum.Enum):
    SLURRY = "slurry"
    COATING = "coating"
    DRYING = "drying"
    CALENDARING = "calendaring"
    CUTTING = "cutting"
    ASSEMBLY = "assembly"
    ELECTROLYTE_FILL = "electrolyte_fill"
    FORMATION = "formation"
    OTHER = "other"


class ElectrodeRole(str, enum.Enum):
    ANODE = "anode"
    CATHODE = "cathode"


class CellBuildStatus(str, enum.Enum):
    PLANNED = "planned"
    BUILT = "built"
    TESTING = "testing"
    RETIRED = "retired"
    FAILED = "failed"


class LineageEntityType(str, enum.Enum):
    MATERIAL = "material"
    MATERIAL_LOT = "material_lot"
    ELECTRODE_BATCH = "electrode_batch"
    PROTOCOL_VERSION = "protocol_version"
    OPERATOR = "operator"
    FIXTURE = "fixture"
    EQUIPMENT_ASSET = "equipment_asset"
    PROCESS_RUN = "process_run"
    CELL_BUILD = "cell_build"
    PROJECT = "project"
    EXPERIMENT = "experiment"
    CELL = "cell"
    TEST_RUN = "test_run"


class Material(Base):
    """A canonical battery material record."""

    __tablename__ = "ontology_materials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    category: Mapped[MaterialCategory] = mapped_column(
        Enum(MaterialCategory), default=MaterialCategory.OTHER, nullable=False
    )
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    lots: Mapped[List["MaterialLot"]] = relationship(
        back_populates="material", cascade="all, delete-orphan", lazy="selectin"
    )


class MaterialLot(Base):
    """A lot or batch for a canonical material."""

    __tablename__ = "ontology_material_lots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("ontology_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lot_code: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    received_at: Mapped[Optional[date]] = mapped_column(Date, default=None)
    certificate_uri: Mapped[Optional[str]] = mapped_column(String(1000), default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("material_id", "lot_code", name="uq_material_lot_code"),
    )

    material: Mapped["Material"] = relationship(back_populates="lots")


class ProtocolVersion(Base):
    """Immutable versioned test or process protocol definition."""

    __tablename__ = "ontology_protocol_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    protocol_type: Mapped[ProtocolType] = mapped_column(
        Enum(ProtocolType), default=ProtocolType.OTHER, nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    step_definition_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_protocol_name_version"),
    )


class Operator(Base):
    """A person or automation actor who performs a build or test step."""

    __tablename__ = "ontology_operators"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    team: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    email: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    process_runs: Mapped[List["ProcessRun"]] = relationship(
        back_populates="operator", lazy="selectin"
    )


class Fixture(Base):
    """A reusable testing or assembly fixture."""

    __tablename__ = "ontology_fixtures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    fixture_type: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    location: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class EquipmentAsset(Base):
    """A piece of lab or process equipment used in build or test operations."""

    __tablename__ = "ontology_equipment_assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    asset_type: Mapped[EquipmentType] = mapped_column(
        Enum(EquipmentType), default=EquipmentType.OTHER, nullable=False
    )
    vendor: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    model: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    serial_number: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    location: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    process_runs: Mapped[List["ProcessRun"]] = relationship(
        back_populates="equipment_asset", lazy="selectin"
    )


class ProcessRun(Base):
    """A structured process record with settings, attribution, and timing."""

    __tablename__ = "ontology_process_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    process_type: Mapped[ProcessType] = mapped_column(
        Enum(ProcessType), default=ProcessType.OTHER, nullable=False
    )
    protocol_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_protocol_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    operator_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_operators.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    equipment_asset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_equipment_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    settings_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    protocol_version: Mapped[Optional["ProtocolVersion"]] = relationship(lazy="selectin")
    operator: Mapped[Optional["Operator"]] = relationship(back_populates="process_runs")
    equipment_asset: Mapped[Optional["EquipmentAsset"]] = relationship(
        back_populates="process_runs"
    )


class ElectrodeBatch(Base):
    """A prepared electrode batch with role-specific identity and lineage hooks."""

    __tablename__ = "ontology_electrode_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    electrode_role: Mapped[ElectrodeRole] = mapped_column(
        Enum(ElectrodeRole), nullable=False
    )
    active_material_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_materials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    process_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_process_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    formulation_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    active_material: Mapped[Optional["Material"]] = relationship(lazy="selectin")
    process_run: Mapped[Optional["ProcessRun"]] = relationship(lazy="selectin")


class CellBuild(Base):
    """A physical cell identity record, separate from test events."""

    __tablename__ = "ontology_cell_builds"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    build_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    chemistry: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    form_factor: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    build_date: Mapped[Optional[date]] = mapped_column(Date, default=None)
    status: Mapped[CellBuildStatus] = mapped_column(
        Enum(CellBuildStatus), default=CellBuildStatus.PLANNED, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    legacy_project_id: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    legacy_experiment_id: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    legacy_cell_id: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    legacy_test_number: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class LineageEdge(Base):
    """A flexible lineage graph edge connecting ontology and legacy entities."""

    __tablename__ = "ontology_lineage_edges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parent_type: Mapped[LineageEntityType] = mapped_column(
        Enum(LineageEntityType), nullable=False, index=True
    )
    parent_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    child_type: Mapped[LineageEntityType] = mapped_column(
        Enum(LineageEntityType), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    confidence: Mapped[Optional[float]] = mapped_column(Float, default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "parent_type",
            "parent_id",
            "child_type",
            "child_id",
            "relationship_type",
            name="uq_lineage_edge",
        ),
    )
