"""Bridge service for legacy cohort snapshots and study workspaces."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from app.config import settings

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _resolve_legacy_db_path() -> Path:
    legacy_db_path = Path(settings.legacy_database_path).expanduser()
    if not legacy_db_path.is_absolute():
        legacy_db_path = (REPO_ROOT / legacy_db_path).resolve()
    return legacy_db_path


def _legacy_modules():
    import cohort_tools as legacy_cohort_tools
    import database as legacy_database
    import study_workspace_service as legacy_workspace_service

    return legacy_database, legacy_cohort_tools, legacy_workspace_service


@contextmanager
def _legacy_database_context() -> Iterator[tuple[Any, Any, Any]]:
    legacy_database, legacy_cohort_tools, legacy_workspace_service = _legacy_modules()
    original_path = legacy_database.DATABASE_PATH
    legacy_database.DATABASE_PATH = str(_resolve_legacy_db_path())
    try:
        yield legacy_database, legacy_cohort_tools, legacy_workspace_service
    finally:
        legacy_database.DATABASE_PATH = original_path


def _snapshot_summary_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(snapshot["id"]),
        "cohort_id": int(snapshot["cohort_id"]) if snapshot.get("cohort_id") is not None else None,
        "cohort_name": snapshot.get("cohort_name"),
        "name": snapshot.get("name") or "Unnamed Snapshot",
        "description": snapshot.get("description"),
        "filters": snapshot.get("filters") or {},
        "experiment_ids": [int(item) for item in snapshot.get("experiment_ids") or []],
        "membership_signature": snapshot.get("membership_signature") or "",
        "summary": snapshot.get("summary") or {},
        "root_batch_summary": snapshot.get("root_batch_summary") or [],
        "ai_summary_text": snapshot.get("ai_summary_text") or "",
        "created_date": snapshot.get("created_date"),
        "updated_date": snapshot.get("updated_date"),
    }


def list_cohort_snapshot_payloads() -> list[Dict[str, Any]]:
    legacy_db_path = _resolve_legacy_db_path()
    if not legacy_db_path.exists():
        return []

    with _legacy_database_context() as (_, legacy_cohort_tools, _):
        snapshots = legacy_cohort_tools.list_cohort_snapshots()
    return [_snapshot_summary_payload(snapshot) for snapshot in snapshots]


def get_cohort_snapshot_payload(snapshot_id: int) -> Optional[Dict[str, Any]]:
    legacy_db_path = _resolve_legacy_db_path()
    if not legacy_db_path.exists():
        return None

    with _legacy_database_context() as (_, legacy_cohort_tools, _):
        snapshot = legacy_cohort_tools.get_cohort_snapshot(int(snapshot_id))
    if not snapshot:
        return None

    payload = _snapshot_summary_payload(snapshot)
    payload["member_records"] = snapshot.get("member_records") or []
    return payload


def list_study_workspace_payloads() -> list[Dict[str, Any]]:
    legacy_db_path = _resolve_legacy_db_path()
    if not legacy_db_path.exists():
        return []

    with _legacy_database_context() as (_, _, legacy_workspace_service):
        workspaces = legacy_workspace_service.list_study_workspaces()
    return workspaces


def get_study_workspace_payload(
    workspace_id: int,
    *,
    refresh: bool = False,
    compute_missing_legacy: bool = False,
) -> Optional[Dict[str, Any]]:
    legacy_db_path = _resolve_legacy_db_path()
    if not legacy_db_path.exists():
        return None

    with _legacy_database_context() as (_, _, legacy_workspace_service):
        payload = legacy_workspace_service.build_study_workspace_payload(
            int(workspace_id),
            refresh=refresh,
            compute_missing_legacy=compute_missing_legacy,
        )
    if not payload:
        return None

    plots = payload.get("plots") or {}
    return {
        "summary": payload.get("summary") or {},
        "members": payload.get("members") or [],
        "plots": {
            "cells_data": plots.get("cells_data") or [],
            "project_summaries": plots.get("project_summaries") or [],
            "metric_rows": plots.get("metric_rows") or [],
        },
        "lineage_context": payload.get("lineage_context") or {},
        "tracking_context": payload.get("tracking_context") or {},
        "annotations": payload.get("annotations") or [],
    }


def create_workspace_from_snapshot(
    snapshot_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> tuple[int, bool]:
    with _legacy_database_context() as (_, _, legacy_workspace_service):
        workspace_id, created = legacy_workspace_service.create_or_open_study_workspace_from_snapshot(
            snapshot_id, name=name, description=description,
        )
    return workspace_id, created


def save_workspace_annotation(
    workspace_id: int,
    *,
    body: str,
    title: Optional[str] = None,
    annotation_type: str = "NOTE",
) -> int:
    with _legacy_database_context() as (_, _, legacy_workspace_service):
        annotation_id = legacy_workspace_service.save_study_workspace_annotation(
            workspace_id, body=body, title=title, annotation_type=annotation_type,
        )
    return annotation_id


def delete_workspace_annotation(annotation_id: int) -> None:
    with _legacy_database_context() as (_, _, legacy_workspace_service):
        legacy_workspace_service.delete_study_workspace_annotation(annotation_id)


def delete_workspace(workspace_id: int) -> None:
    with _legacy_database_context() as (_, _, legacy_workspace_service):
        legacy_workspace_service.delete_study_workspace(workspace_id)


def load_cohort_records_and_options() -> Dict[str, Any]:
    legacy_db_path = _resolve_legacy_db_path()
    if not legacy_db_path.exists():
        return {"records": [], "filter_options": {}}

    with _legacy_database_context() as (_, legacy_cohort_tools, _):
        records = legacy_cohort_tools.load_cohort_records()
        filter_options = legacy_cohort_tools.build_cohort_filter_options(records)
    return {"records": records, "filter_options": filter_options}


def preview_cohort(filters: Dict[str, Any]) -> Dict[str, Any]:
    legacy_db_path = _resolve_legacy_db_path()
    if not legacy_db_path.exists():
        return {"records": [], "summary": {}, "total": 0}

    with _legacy_database_context() as (_, legacy_cohort_tools, _):
        all_records = legacy_cohort_tools.load_cohort_records()
        filtered = legacy_cohort_tools.apply_cohort_filters(all_records, filters)
        summary = legacy_cohort_tools.summarize_cohort(filtered)
    return {"records": filtered, "summary": summary, "total": len(filtered)}


def create_cohort_snapshot(
    *,
    name: str,
    description: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> int:
    with _legacy_database_context() as (_, legacy_cohort_tools, _):
        all_records = legacy_cohort_tools.load_cohort_records()
        filtered = legacy_cohort_tools.apply_cohort_filters(all_records, filters or {})
        snapshot_id = legacy_cohort_tools.save_cohort_snapshot(
            name=name,
            description=description,
            filters=filters or {},
            records=filtered,
        )
    return snapshot_id
