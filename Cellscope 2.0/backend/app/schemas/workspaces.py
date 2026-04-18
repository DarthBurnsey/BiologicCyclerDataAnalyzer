"""Schemas for backend read models over legacy cohort snapshots and study workspaces."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class CohortSnapshotSummaryRead(BaseModel):
    id: int
    cohort_id: Optional[int]
    cohort_name: Optional[str]
    name: str
    description: Optional[str]
    filters: Dict[str, Any]
    experiment_ids: List[int]
    membership_signature: str
    summary: Dict[str, Any]
    root_batch_summary: List[Dict[str, Any]]
    ai_summary_text: str
    created_date: Optional[str]
    updated_date: Optional[str]


class CohortSnapshotDetailRead(CohortSnapshotSummaryRead):
    member_records: List[Dict[str, Any]]


class StudyWorkspaceListRead(BaseModel):
    id: int
    snapshot_id: int
    cohort_id: Optional[int]
    snapshot_name: Optional[str]
    cohort_name: Optional[str]
    name: str
    description: Optional[str]
    status: str
    source_membership_signature: str
    item_count: int
    annotation_count: int
    created_date: Optional[str]
    updated_date: Optional[str]
    last_opened_at: Optional[str]


class StudyWorkspacePlotsRead(BaseModel):
    cells_data: List[Dict[str, Any]]
    project_summaries: List[Dict[str, Any]]
    metric_rows: List[Dict[str, Any]]


class StudyWorkspacePayloadRead(BaseModel):
    summary: Dict[str, Any]
    members: List[Dict[str, Any]]
    plots: StudyWorkspacePlotsRead
    lineage_context: Dict[str, Any]
    tracking_context: Dict[str, Any]
    annotations: List[Dict[str, Any]]


# --- Mutation schemas ---

class WorkspaceCreateFromSnapshot(BaseModel):
    snapshot_id: int
    name: Optional[str] = None
    description: Optional[str] = None


class WorkspaceCreateResponse(BaseModel):
    workspace_id: int
    created: bool


class AnnotationCreate(BaseModel):
    body: str
    title: Optional[str] = None
    annotation_type: str = "NOTE"


class AnnotationCreateResponse(BaseModel):
    annotation_id: int


class CohortRecordsResponse(BaseModel):
    records: List[Dict[str, Any]]
    filter_options: Dict[str, Any]


class CohortPreviewRequest(BaseModel):
    filters: Dict[str, Any]


class CohortPreviewResponse(BaseModel):
    records: List[Dict[str, Any]]
    summary: Dict[str, Any]
    total: int


class CohortSnapshotCreate(BaseModel):
    name: str
    description: Optional[str] = None
    filters: Dict[str, Any]


class CohortSnapshotCreateResponse(BaseModel):
    snapshot_id: int
