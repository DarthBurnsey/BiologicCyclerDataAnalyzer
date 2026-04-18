"""Experiment Design ORM model — planned experiments with formulation, parameters, and ontology links."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DesignStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    REALIZED = "realized"


class ExperimentDesign(Base):
    """A planned experiment design with formulation, electrode parameters,
    cell assembly details, test protocol, and cycler assignment readiness."""

    __tablename__ = "experiment_designs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[DesignStatus] = mapped_column(
        Enum(DesignStatus), default=DesignStatus.DRAFT, nullable=False
    )

    # Target project
    target_project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # --- Electrode formulation ---
    electrode_role: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    formulation_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON, default=None
    )
    # Each entry: { material_id?, material_name, category, dry_mass_fraction_pct }

    # --- Electrode parameters ---
    disc_diameter_mm: Mapped[Optional[float]] = mapped_column(Float, default=15.0)
    target_loading_mg_cm2: Mapped[Optional[float]] = mapped_column(Float, default=None)
    target_thickness_um: Mapped[Optional[float]] = mapped_column(Float, default=None)
    target_porosity: Mapped[Optional[float]] = mapped_column(Float, default=None)
    solids_content_pct: Mapped[Optional[float]] = mapped_column(Float, default=None)
    pressed_thickness_um: Mapped[Optional[float]] = mapped_column(Float, default=None)
    active_mass_density_g_cc: Mapped[Optional[float]] = mapped_column(
        Float, default=None
    )
    slurry_density_g_ml: Mapped[Optional[float]] = mapped_column(Float, default=None)

    # --- Cell assembly ---
    form_factor: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    electrolyte: Mapped[Optional[str]] = mapped_column(String(500), default=None)
    separator: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    current_collector: Mapped[Optional[str]] = mapped_column(String(255), default=None)

    # --- Test parameters ---
    formation_protocol_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_protocol_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    cycling_protocol_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_protocol_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    formation_cycles: Mapped[Optional[int]] = mapped_column(Integer, default=4)
    cutoff_voltage_lower: Mapped[Optional[float]] = mapped_column(Float, default=None)
    cutoff_voltage_upper: Mapped[Optional[float]] = mapped_column(Float, default=None)
    c_rate_charge: Mapped[Optional[float]] = mapped_column(Float, default=None)
    c_rate_discharge: Mapped[Optional[float]] = mapped_column(Float, default=None)
    temperature_c: Mapped[Optional[float]] = mapped_column(Float, default=None)

    # --- Cell plan ---
    num_cells: Mapped[int] = mapped_column(Integer, default=3)
    cell_naming_pattern: Mapped[Optional[str]] = mapped_column(
        String(255), default=None
    )

    # --- Cycler assignment (future) ---
    target_equipment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_equipment_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel_assignments_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, default=None
    )

    # --- Realized experiment link ---
    realized_experiment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True
    )

    # --- Attribution ---
    designed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ontology_operators.id", ondelete="SET NULL"), nullable=True
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # --- Relationships ---
    target_project: Mapped[Optional["Project"]] = relationship(
        "Project", foreign_keys=[target_project_id], lazy="selectin"
    )
    formation_protocol: Mapped[Optional["ProtocolVersion"]] = relationship(
        "ProtocolVersion", foreign_keys=[formation_protocol_id], lazy="selectin"
    )
    cycling_protocol: Mapped[Optional["ProtocolVersion"]] = relationship(
        "ProtocolVersion", foreign_keys=[cycling_protocol_id], lazy="selectin"
    )
    target_equipment: Mapped[Optional["EquipmentAsset"]] = relationship(
        "EquipmentAsset", foreign_keys=[target_equipment_id], lazy="selectin"
    )
    designed_by: Mapped[Optional["Operator"]] = relationship(
        "Operator", foreign_keys=[designed_by_id], lazy="selectin"
    )
    realized_experiment: Mapped[Optional["Experiment"]] = relationship(
        "Experiment", foreign_keys=[realized_experiment_id], lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ExperimentDesign(id={self.id}, name='{self.name}', status='{self.status}')>"
