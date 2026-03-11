"""Pydantic schemas for Experiment API."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.cell import CellRead


class ExperimentCreate(BaseModel):
    """Schema for creating a new experiment."""
    name: str = Field(..., min_length=1, max_length=255, examples=["Exp-001 NMC811"])
    experiment_date: Optional[date] = None
    disc_diameter_mm: Optional[float] = Field(15.0, ge=0.1, le=100.0)
    solids_content: Optional[float] = Field(None, ge=0, le=100)
    pressed_thickness: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None
    group_names: Optional[List[str]] = Field(None, examples=[["Group A", "Group B"]])


class ExperimentUpdate(BaseModel):
    """Schema for updating an experiment. All fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    experiment_date: Optional[date] = None
    disc_diameter_mm: Optional[float] = Field(None, ge=0.1, le=100.0)
    solids_content: Optional[float] = Field(None, ge=0, le=100)
    pressed_thickness: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None
    group_names: Optional[List[str]] = None


class ExperimentRead(BaseModel):
    """Schema for reading an experiment with its cells."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    experiment_date: Optional[date]
    disc_diameter_mm: Optional[float]
    solids_content: Optional[float]
    pressed_thickness: Optional[float]
    notes: Optional[str]
    group_names: Optional[List[str]]
    created_at: datetime
    updated_at: datetime
    cells: List[CellRead] = []


class ExperimentListRead(BaseModel):
    """Schema for listing experiments (without full cell data)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    experiment_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    cell_count: int = 0
