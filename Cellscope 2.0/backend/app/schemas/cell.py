"""Pydantic schemas for Cell API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FormulationComponent(BaseModel):
    """A single component in a cell formulation."""
    Component: str = Field(..., examples=["NMC811"])
    dry_mass_fraction_pct: float = Field(
        ..., ge=0, le=100, alias="Dry Mass Fraction (%)",
        examples=[90.0]
    )

    model_config = ConfigDict(populate_by_name=True)


class CellCreate(BaseModel):
    """Schema for creating a new cell."""
    cell_name: str = Field(..., min_length=1, max_length=255, examples=["Cell 1"])
    file_name: Optional[str] = Field(None, max_length=255)
    loading: Optional[float] = Field(None, ge=0, examples=[5.2])
    active_material_pct: Optional[float] = Field(None, ge=0, le=100, examples=[92.0])
    formation_cycles: int = Field(4, ge=0, le=50)
    test_number: Optional[str] = None
    electrolyte: Optional[str] = Field(None, examples=["1M LiPF6 EC:DMC (1:1)"])
    substrate: Optional[str] = Field(None, examples=["Copper"])
    separator: Optional[str] = Field(None, examples=["25um PP"])
    formulation: Optional[List[FormulationComponent]] = None
    group_assignment: Optional[str] = None
    excluded: bool = False
    cutoff_voltage_lower: Optional[float] = None
    cutoff_voltage_upper: Optional[float] = None


class CellUpdate(BaseModel):
    """Schema for updating a cell. All fields optional."""
    cell_name: Optional[str] = Field(None, min_length=1, max_length=255)
    loading: Optional[float] = Field(None, ge=0)
    active_material_pct: Optional[float] = Field(None, ge=0, le=100)
    formation_cycles: Optional[int] = Field(None, ge=0, le=50)
    test_number: Optional[str] = None
    electrolyte: Optional[str] = None
    substrate: Optional[str] = None
    separator: Optional[str] = None
    formulation: Optional[List[FormulationComponent]] = None
    group_assignment: Optional[str] = None
    excluded: Optional[bool] = None
    cutoff_voltage_lower: Optional[float] = None
    cutoff_voltage_upper: Optional[float] = None


class CellRead(BaseModel):
    """Schema for reading a cell."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    experiment_id: int
    cell_name: str
    file_name: Optional[str]
    loading: Optional[float]
    active_material_pct: Optional[float]
    formation_cycles: int
    test_number: Optional[str]
    electrolyte: Optional[str]
    substrate: Optional[str]
    separator: Optional[str]
    formulation: Optional[List[FormulationComponent]]
    group_assignment: Optional[str]
    excluded: bool
    porosity: Optional[float]
    cutoff_voltage_lower: Optional[float]
    cutoff_voltage_upper: Optional[float]
    parquet_path: Optional[str]
    data_json: Optional[dict] = None
    created_at: datetime
