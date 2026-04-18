"""Schemas for canonical ontology APIs."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.ontology import (
    CellBuildStatus,
    ElectrodeRole,
    EquipmentType,
    LineageEntityType,
    MaterialCategory,
    ProcessType,
    ProtocolType,
)


class MaterialBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: MaterialCategory = MaterialCategory.OTHER
    manufacturer: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[MaterialCategory] = None
    manufacturer: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class MaterialRead(MaterialBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class MaterialLotBase(BaseModel):
    material_id: int
    lot_code: str = Field(..., min_length=1, max_length=255)
    supplier_name: Optional[str] = Field(None, max_length=255)
    received_at: Optional[date] = None
    certificate_uri: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class MaterialLotCreate(MaterialLotBase):
    pass


class MaterialLotUpdate(BaseModel):
    material_id: Optional[int] = None
    lot_code: Optional[str] = Field(None, min_length=1, max_length=255)
    supplier_name: Optional[str] = Field(None, max_length=255)
    received_at: Optional[date] = None
    certificate_uri: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class MaterialLotRead(MaterialLotBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ProtocolVersionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    version: str = Field(..., min_length=1, max_length=100)
    protocol_type: ProtocolType = ProtocolType.OTHER
    description: Optional[str] = None
    step_definition_json: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None


class ProtocolVersionCreate(ProtocolVersionBase):
    pass


class ProtocolVersionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    version: Optional[str] = Field(None, min_length=1, max_length=100)
    protocol_type: Optional[ProtocolType] = None
    description: Optional[str] = None
    step_definition_json: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None


class ProtocolVersionRead(ProtocolVersionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class OperatorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    team: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    active: bool = True
    metadata_json: Optional[Dict[str, Any]] = None


class OperatorCreate(OperatorBase):
    pass


class OperatorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    team: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    active: Optional[bool] = None
    metadata_json: Optional[Dict[str, Any]] = None


class OperatorRead(OperatorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class FixtureBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    fixture_type: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    metadata_json: Optional[Dict[str, Any]] = None


class FixtureCreate(FixtureBase):
    pass


class FixtureUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    fixture_type: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    metadata_json: Optional[Dict[str, Any]] = None


class FixtureRead(FixtureBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class EquipmentAssetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    asset_type: EquipmentType = EquipmentType.OTHER
    vendor: Optional[str] = Field(None, max_length=255)
    model: Optional[str] = Field(None, max_length=255)
    serial_number: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    metadata_json: Optional[Dict[str, Any]] = None


class EquipmentAssetCreate(EquipmentAssetBase):
    pass


class EquipmentAssetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    asset_type: Optional[EquipmentType] = None
    vendor: Optional[str] = Field(None, max_length=255)
    model: Optional[str] = Field(None, max_length=255)
    serial_number: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    metadata_json: Optional[Dict[str, Any]] = None


class EquipmentAssetRead(EquipmentAssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ProcessRunBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    process_type: ProcessType = ProcessType.OTHER
    protocol_version_id: Optional[int] = None
    operator_id: Optional[int] = None
    equipment_asset_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    settings_json: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class ProcessRunCreate(ProcessRunBase):
    pass


class ProcessRunUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    process_type: Optional[ProcessType] = None
    protocol_version_id: Optional[int] = None
    operator_id: Optional[int] = None
    equipment_asset_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    settings_json: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class ProcessRunRead(ProcessRunBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ElectrodeBatchBase(BaseModel):
    batch_name: str = Field(..., min_length=1, max_length=255)
    electrode_role: ElectrodeRole
    active_material_id: Optional[int] = None
    process_run_id: Optional[int] = None
    formulation_json: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class ElectrodeBatchCreate(ElectrodeBatchBase):
    pass


class ElectrodeBatchUpdate(BaseModel):
    batch_name: Optional[str] = Field(None, min_length=1, max_length=255)
    electrode_role: Optional[ElectrodeRole] = None
    active_material_id: Optional[int] = None
    process_run_id: Optional[int] = None
    formulation_json: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class ElectrodeBatchRead(ElectrodeBatchBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class CellBuildBase(BaseModel):
    build_name: str = Field(..., min_length=1, max_length=255)
    chemistry: Optional[str] = Field(None, max_length=255)
    form_factor: Optional[str] = Field(None, max_length=100)
    build_date: Optional[date] = None
    status: CellBuildStatus = CellBuildStatus.PLANNED
    notes: Optional[str] = None
    legacy_project_id: Optional[int] = None
    legacy_experiment_id: Optional[int] = None
    legacy_cell_id: Optional[int] = None
    legacy_test_number: Optional[str] = Field(None, max_length=255)
    metadata_json: Optional[Dict[str, Any]] = None


class CellBuildCreate(CellBuildBase):
    pass


class CellBuildUpdate(BaseModel):
    build_name: Optional[str] = Field(None, min_length=1, max_length=255)
    chemistry: Optional[str] = Field(None, max_length=255)
    form_factor: Optional[str] = Field(None, max_length=100)
    build_date: Optional[date] = None
    status: Optional[CellBuildStatus] = None
    notes: Optional[str] = None
    legacy_project_id: Optional[int] = None
    legacy_experiment_id: Optional[int] = None
    legacy_cell_id: Optional[int] = None
    legacy_test_number: Optional[str] = Field(None, max_length=255)
    metadata_json: Optional[Dict[str, Any]] = None


class CellBuildRead(CellBuildBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class LineageEdgeBase(BaseModel):
    parent_type: LineageEntityType
    parent_id: int = Field(..., ge=1)
    child_type: LineageEntityType
    child_id: int = Field(..., ge=1)
    relationship_type: str = Field(..., min_length=1, max_length=255)
    source: Optional[str] = Field(None, max_length=255)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    notes: Optional[str] = None


class LineageEdgeCreate(LineageEdgeBase):
    pass


class LineageEdgeUpdate(BaseModel):
    relationship_type: Optional[str] = Field(None, min_length=1, max_length=255)
    source: Optional[str] = Field(None, max_length=255)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    notes: Optional[str] = None


class LineageEdgeRead(LineageEdgeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class OntologySummary(BaseModel):
    materials: int = 0
    material_lots: int = 0
    protocol_versions: int = 0
    operators: int = 0
    fixtures: int = 0
    equipment_assets: int = 0
    process_runs: int = 0
    electrode_batches: int = 0
    cell_builds: int = 0
    lineage_edges: int = 0


class OntologySearchResult(BaseModel):
    entity_type: str
    entity_id: int
    name: str
    detail: Optional[str] = None


class LegacyExperimentSummary(BaseModel):
    legacy_experiment_id: int = Field(..., ge=1)
    experiment_name: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None


class ElectrodeBatchLineageRead(BaseModel):
    batch: ElectrodeBatchRead
    active_material: Optional[MaterialRead] = None
    process_run: Optional[ProcessRunRead] = None
    parent_batches: List[ElectrodeBatchRead] = Field(default_factory=list)
    child_batches: List[ElectrodeBatchRead] = Field(default_factory=list)
    formulation_materials: List[MaterialRead] = Field(default_factory=list)
    cell_builds: List[CellBuildRead] = Field(default_factory=list)
    legacy_experiments: List[LegacyExperimentSummary] = Field(default_factory=list)
    lineage_edges: List[LineageEdgeRead] = Field(default_factory=list)


class BatchDescendantRead(BaseModel):
    depth: int = Field(..., ge=1)
    ancestor_path: List[str] = Field(default_factory=list)
    batch: ElectrodeBatchRead
    cell_build_count: int = Field(default=0, ge=0)
    legacy_experiment_count: int = Field(default=0, ge=0)


class ElectrodeBatchDescendantsRead(BaseModel):
    root_batch: ElectrodeBatchRead
    descendants: List[BatchDescendantRead] = Field(default_factory=list)
    related_cell_builds: List[CellBuildRead] = Field(default_factory=list)
    related_legacy_experiments: List[LegacyExperimentSummary] = Field(default_factory=list)
    lineage_edges: List[LineageEdgeRead] = Field(default_factory=list)


class CellBuildLineageRead(BaseModel):
    cell_build: CellBuildRead
    source_batches: List[ElectrodeBatchRead] = Field(default_factory=list)
    source_materials: List[MaterialRead] = Field(default_factory=list)
    related_legacy_experiments: List[LegacyExperimentSummary] = Field(default_factory=list)
    lineage_edges: List[LineageEdgeRead] = Field(default_factory=list)


class LegacyExperimentSourcesRead(BaseModel):
    legacy_experiment_id: int = Field(..., ge=1)
    experiment_name: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    source_batches: List[ElectrodeBatchRead] = Field(default_factory=list)
    source_materials: List[MaterialRead] = Field(default_factory=list)
    related_cell_builds: List[CellBuildRead] = Field(default_factory=list)
    lineage_edges: List[LineageEdgeRead] = Field(default_factory=list)
