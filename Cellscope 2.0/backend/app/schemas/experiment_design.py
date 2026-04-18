"""Pydantic schemas for Experiment Design API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DesignStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    REALIZED = "realized"


class FormulationEntry(BaseModel):
    """A single component in a designed formulation."""
    material_id: Optional[int] = None
    material_name: str = Field(..., min_length=1)
    category: Optional[str] = None
    dry_mass_fraction_pct: float = Field(..., ge=0, le=100)


class ExperimentDesignCreate(BaseModel):
    """Schema for creating a new experiment design."""
    name: str = Field(..., min_length=1, max_length=255)
    status: DesignStatus = DesignStatus.DRAFT
    target_project_id: Optional[int] = None
    electrode_role: Optional[str] = Field(None, pattern="^(cathode|anode)$")
    formulation_json: Optional[List[FormulationEntry]] = None
    disc_diameter_mm: Optional[float] = Field(15.0, ge=0.1, le=100.0)
    target_loading_mg_cm2: Optional[float] = Field(None, ge=0)
    target_thickness_um: Optional[float] = Field(None, ge=0)
    target_porosity: Optional[float] = Field(None, ge=0, le=1)
    solids_content_pct: Optional[float] = Field(None, ge=0, le=100)
    pressed_thickness_um: Optional[float] = Field(None, ge=0)
    active_mass_density_g_cc: Optional[float] = Field(None, ge=0)
    slurry_density_g_ml: Optional[float] = Field(None, ge=0)
    form_factor: Optional[str] = None
    electrolyte: Optional[str] = None
    separator: Optional[str] = None
    current_collector: Optional[str] = None
    formation_protocol_id: Optional[int] = None
    cycling_protocol_id: Optional[int] = None
    formation_cycles: Optional[int] = Field(4, ge=0, le=50)
    cutoff_voltage_lower: Optional[float] = None
    cutoff_voltage_upper: Optional[float] = None
    c_rate_charge: Optional[float] = Field(None, ge=0)
    c_rate_discharge: Optional[float] = Field(None, ge=0)
    temperature_c: Optional[float] = None
    num_cells: int = Field(3, ge=1, le=100)
    cell_naming_pattern: Optional[str] = None
    target_equipment_id: Optional[int] = None
    channel_assignments_json: Optional[Dict[str, Any]] = None
    designed_by_id: Optional[int] = None
    notes: Optional[str] = None


class ExperimentDesignUpdate(BaseModel):
    """Schema for updating an experiment design. All fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[DesignStatus] = None
    target_project_id: Optional[int] = None
    electrode_role: Optional[str] = None
    formulation_json: Optional[List[FormulationEntry]] = None
    disc_diameter_mm: Optional[float] = Field(None, ge=0.1, le=100.0)
    target_loading_mg_cm2: Optional[float] = None
    target_thickness_um: Optional[float] = None
    target_porosity: Optional[float] = None
    solids_content_pct: Optional[float] = None
    pressed_thickness_um: Optional[float] = None
    active_mass_density_g_cc: Optional[float] = None
    slurry_density_g_ml: Optional[float] = None
    form_factor: Optional[str] = None
    electrolyte: Optional[str] = None
    separator: Optional[str] = None
    current_collector: Optional[str] = None
    formation_protocol_id: Optional[int] = None
    cycling_protocol_id: Optional[int] = None
    formation_cycles: Optional[int] = None
    cutoff_voltage_lower: Optional[float] = None
    cutoff_voltage_upper: Optional[float] = None
    c_rate_charge: Optional[float] = None
    c_rate_discharge: Optional[float] = None
    temperature_c: Optional[float] = None
    num_cells: Optional[int] = None
    cell_naming_pattern: Optional[str] = None
    target_equipment_id: Optional[int] = None
    channel_assignments_json: Optional[Dict[str, Any]] = None
    designed_by_id: Optional[int] = None
    notes: Optional[str] = None


class ExperimentDesignRead(BaseModel):
    """Schema for reading an experiment design with full details."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: DesignStatus
    target_project_id: Optional[int]
    electrode_role: Optional[str]
    formulation_json: Optional[List[Dict[str, Any]]]
    disc_diameter_mm: Optional[float]
    target_loading_mg_cm2: Optional[float]
    target_thickness_um: Optional[float]
    target_porosity: Optional[float]
    solids_content_pct: Optional[float]
    pressed_thickness_um: Optional[float]
    active_mass_density_g_cc: Optional[float]
    slurry_density_g_ml: Optional[float]
    form_factor: Optional[str]
    electrolyte: Optional[str]
    separator: Optional[str]
    current_collector: Optional[str]
    formation_protocol_id: Optional[int]
    cycling_protocol_id: Optional[int]
    formation_cycles: Optional[int]
    cutoff_voltage_lower: Optional[float]
    cutoff_voltage_upper: Optional[float]
    c_rate_charge: Optional[float]
    c_rate_discharge: Optional[float]
    temperature_c: Optional[float]
    num_cells: int
    cell_naming_pattern: Optional[str]
    target_equipment_id: Optional[int]
    channel_assignments_json: Optional[Dict[str, Any]]
    realized_experiment_id: Optional[int]
    designed_by_id: Optional[int]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Resolved relationship names for display
    target_project_name: Optional[str] = None
    formation_protocol_name: Optional[str] = None
    cycling_protocol_name: Optional[str] = None
    target_equipment_name: Optional[str] = None
    designed_by_name: Optional[str] = None


class ExperimentDesignListRead(BaseModel):
    """Lightweight schema for listing designs."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: DesignStatus
    electrode_role: Optional[str]
    target_project_id: Optional[int]
    target_project_name: Optional[str] = None
    num_cells: int
    created_at: datetime
    updated_at: datetime


class RealizeDesignRequest(BaseModel):
    """Request body to realize (convert) a design into a real experiment."""
    project_id: int
    experiment_name: Optional[str] = None
