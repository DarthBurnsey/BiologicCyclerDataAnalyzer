"""API routes for cohort snapshots and study workspaces."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.workspaces import (
    AnnotationCreate,
    AnnotationCreateResponse,
    CohortPreviewRequest,
    CohortPreviewResponse,
    CohortRecordsResponse,
    CohortSnapshotCreate,
    CohortSnapshotCreateResponse,
    CohortSnapshotDetailRead,
    CohortSnapshotSummaryRead,
    StudyWorkspaceListRead,
    StudyWorkspacePayloadRead,
    WorkspaceCreateFromSnapshot,
    WorkspaceCreateResponse,
)
from app.services.workspaces import (
    create_cohort_snapshot,
    create_workspace_from_snapshot,
    delete_workspace,
    delete_workspace_annotation,
    get_cohort_snapshot_payload,
    get_study_workspace_payload,
    list_cohort_snapshot_payloads,
    list_study_workspace_payloads,
    load_cohort_records_and_options,
    preview_cohort,
    save_workspace_annotation,
)

router = APIRouter(tags=["analysis"])


@router.get("/api/analysis/cohort-snapshots", response_model=list[CohortSnapshotSummaryRead])
def list_cohort_snapshots():
    return [CohortSnapshotSummaryRead.model_validate(item) for item in list_cohort_snapshot_payloads()]


@router.get(
    "/api/analysis/cohort-snapshots/{snapshot_id}",
    response_model=CohortSnapshotDetailRead,
)
def get_cohort_snapshot(snapshot_id: int):
    payload = get_cohort_snapshot_payload(snapshot_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Cohort snapshot not found")
    return CohortSnapshotDetailRead.model_validate(payload)


@router.get("/api/analysis/study-workspaces", response_model=list[StudyWorkspaceListRead])
def list_study_workspaces():
    return [StudyWorkspaceListRead.model_validate(item) for item in list_study_workspace_payloads()]


@router.get(
    "/api/analysis/study-workspaces/{workspace_id}",
    response_model=StudyWorkspacePayloadRead,
)
def get_study_workspace(
    workspace_id: int,
    refresh: bool = Query(default=False),
):
    payload = get_study_workspace_payload(
        workspace_id,
        refresh=refresh,
        compute_missing_legacy=False,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Study workspace not found")
    return StudyWorkspacePayloadRead.model_validate(payload)


@router.post(
    "/api/analysis/study-workspaces",
    response_model=WorkspaceCreateResponse,
    status_code=201,
)
def create_study_workspace(body: WorkspaceCreateFromSnapshot):
    try:
        workspace_id, created = create_workspace_from_snapshot(
            body.snapshot_id, name=body.name, description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return WorkspaceCreateResponse(workspace_id=workspace_id, created=created)


@router.delete("/api/analysis/study-workspaces/{workspace_id}", status_code=204)
def delete_study_workspace(workspace_id: int):
    delete_workspace(workspace_id)


@router.post(
    "/api/analysis/study-workspaces/{workspace_id}/annotations",
    response_model=AnnotationCreateResponse,
    status_code=201,
)
def create_workspace_annotation(workspace_id: int, body: AnnotationCreate):
    try:
        annotation_id = save_workspace_annotation(
            workspace_id,
            body=body.body,
            title=body.title,
            annotation_type=body.annotation_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return AnnotationCreateResponse(annotation_id=annotation_id)


@router.delete(
    "/api/analysis/study-workspaces/annotations/{annotation_id}",
    status_code=204,
)
def remove_workspace_annotation(annotation_id: int):
    delete_workspace_annotation(annotation_id)


# --- Cohort Builder ---


@router.get("/api/analysis/cohort-records", response_model=CohortRecordsResponse)
def get_cohort_records():
    return CohortRecordsResponse.model_validate(load_cohort_records_and_options())


@router.post("/api/analysis/cohort-preview", response_model=CohortPreviewResponse)
def cohort_preview(body: CohortPreviewRequest):
    return CohortPreviewResponse.model_validate(preview_cohort(body.filters))


@router.post(
    "/api/analysis/cohort-snapshots",
    response_model=CohortSnapshotCreateResponse,
    status_code=201,
)
def create_snapshot(body: CohortSnapshotCreate):
    try:
        snapshot_id = create_cohort_snapshot(
            name=body.name,
            description=body.description,
            filters=body.filters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CohortSnapshotCreateResponse(snapshot_id=snapshot_id)
