"""Pydantic schemas for CellScope 2.0 API (Python 3.9 compatible)."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── Project ────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    project_type: str = "Full Cell"  # Cathode | Anode | Full Cell


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    project_type: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    project_type: str
    created_date: Optional[str]
    last_modified: Optional[str]
    experiment_count: int = 0


# ─── Experiment ─────────────────────────────────────────────────────────────

class ExperimentSummary(BaseModel):
    """Lightweight experiment listing."""
    id: int
    cell_name: str
    file_name: Optional[str]
    created_date: Optional[str]
    has_data: bool = False


class ExperimentDetail(BaseModel):
    """Full experiment data."""
    id: int
    project_id: int
    cell_name: str
    file_name: Optional[str]
    loading: Optional[float]
    active_material: Optional[float]
    formation_cycles: Optional[int]
    test_number: Optional[str]
    electrolyte: Optional[str]
    substrate: Optional[str]
    separator: Optional[str]
    formulation_json: Optional[str]
    data_json: Optional[str]
    solids_content: Optional[float]
    pressed_thickness: Optional[float]
    experiment_notes: Optional[str]
    created_date: Optional[str]
    porosity: Optional[float]


class ExperimentCreate(BaseModel):
    """Create a new experiment."""
    experiment_name: str
    experiment_date: Optional[str] = None
    disc_diameter_mm: float = 15.0
    group_assignments: Optional[Dict[str, str]] = None
    group_names: Optional[List[str]] = None
    cells_data: List[Dict[str, Any]] = []
    solids_content: Optional[float] = None
    pressed_thickness: Optional[float] = None
    experiment_notes: Optional[str] = None
    cell_format_data: Optional[Dict[str, Any]] = None


class ExperimentUpdate(BaseModel):
    """Update an existing experiment."""
    experiment_name: str
    experiment_date: Optional[str] = None
    disc_diameter_mm: float = 15.0
    group_assignments: Optional[Dict[str, str]] = None
    group_names: Optional[List[str]] = None
    cells_data: List[Dict[str, Any]] = []
    solids_content: Optional[float] = None
    pressed_thickness: Optional[float] = None
    experiment_notes: Optional[str] = None
    cell_format_data: Optional[Dict[str, Any]] = None


# ─── Preferences ────────────────────────────────────────────────────────────

class PreferencesUpdate(BaseModel):
    """Key-value preference pairs."""
    preferences: Dict[str, Optional[str]]


# ─── Formulation ────────────────────────────────────────────────────────────

class FormulationQuery(BaseModel):
    """Query for experiments by formulation component."""
    component_name: str
    min_percentage: Optional[float] = None
    max_percentage: Optional[float] = None


# ─── Health ─────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str
