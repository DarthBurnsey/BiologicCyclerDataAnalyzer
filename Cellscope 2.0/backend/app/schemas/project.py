"""Pydantic schemas for Project API."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectType(str, Enum):
    CATHODE = "Cathode"
    ANODE = "Anode"
    FULL_CELL = "Full Cell"


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""
    name: str = Field(..., min_length=1, max_length=255, examples=["Silicon Anode Study"])
    description: Optional[str] = Field(None, max_length=2000)
    project_type: ProjectType = ProjectType.FULL_CELL


class ProjectUpdate(BaseModel):
    """Schema for updating a project. All fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    project_type: Optional[ProjectType] = None


class ProjectRead(BaseModel):
    """Schema for reading a project with all details."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    project_type: ProjectType
    created_at: datetime
    updated_at: datetime
    experiment_count: int = 0
    cell_count: int = 0


class ProjectListRead(BaseModel):
    """Schema for listing projects (lightweight)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    project_type: ProjectType
    created_at: datetime
    updated_at: datetime
    experiment_count: int = 0
