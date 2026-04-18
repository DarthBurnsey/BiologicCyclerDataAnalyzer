"""Thin client for backend-native analysis payloads with safe legacy fallback."""

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional, Protocol


BACKEND_ROOT = Path(__file__).resolve().parent / "Cellscope 2.0" / "backend"


class _BackendWorkspaceService(Protocol):
    def __call__(self, workspace_id: int, *, refresh: bool = False) -> Optional[Dict[str, Any]]: ...


class _BackendWorkspaceListService(Protocol):
    def __call__(self) -> list[Dict[str, Any]]: ...


class _BackendSnapshotService(Protocol):
    def __call__(self, snapshot_id: int) -> Optional[Dict[str, Any]]: ...


class _BackendSnapshotListService(Protocol):
    def __call__(self) -> list[Dict[str, Any]]: ...


@contextmanager
def _temporary_backend_import_path():
    backend_path = str(BACKEND_ROOT)
    original_indexes = [index for index, value in enumerate(sys.path) if value == backend_path]
    sys.path[:] = [value for value in sys.path if value != backend_path]
    sys.path.insert(0, backend_path)
    try:
        yield
    finally:
        sys.path[:] = [value for value in sys.path if value != backend_path]
        if original_indexes:
            restore_index = min(original_indexes[0], len(sys.path))
            sys.path.insert(restore_index, backend_path)


def _load_backend_analysis_services() -> tuple[
    _BackendWorkspaceListService,
    _BackendWorkspaceService,
    _BackendSnapshotListService,
    _BackendSnapshotService,
]:
    with _temporary_backend_import_path():
        workspaces_module = importlib.import_module("app.services.workspaces")

    return (
        workspaces_module.list_study_workspace_payloads,
        workspaces_module.get_study_workspace_payload,
        workspaces_module.list_cohort_snapshot_payloads,
        workspaces_module.get_cohort_snapshot_payload,
    )


def list_study_workspace_records() -> list[Dict[str, Any]]:
    try:
        backend_list_workspaces, _, _, _ = _load_backend_analysis_services()
        workspaces = backend_list_workspaces()
        if isinstance(workspaces, list):
            return workspaces
    except Exception:
        pass

    from study_workspace_service import list_study_workspaces

    return list_study_workspaces()


def get_study_workspace_payload_preferred(
    workspace_id: int,
    *,
    refresh: bool = False,
) -> Optional[Dict[str, Any]]:
    if not refresh:
        try:
            _, backend_get_workspace_payload, _, _ = _load_backend_analysis_services()
            payload = backend_get_workspace_payload(int(workspace_id), refresh=False)
            if payload is not None:
                return payload
        except Exception:
            pass

    from study_workspace_service import build_study_workspace_payload

    return build_study_workspace_payload(int(workspace_id), refresh=refresh)


def list_cohort_snapshot_records() -> list[Dict[str, Any]]:
    try:
        _, _, backend_list_snapshots, _ = _load_backend_analysis_services()
        snapshots = backend_list_snapshots()
        if isinstance(snapshots, list):
            return snapshots
    except Exception:
        pass

    from cohort_tools import list_cohort_snapshots

    return list_cohort_snapshots()


def get_cohort_snapshot_payload_preferred(snapshot_id: int) -> Optional[Dict[str, Any]]:
    try:
        _, _, _, backend_get_snapshot_payload = _load_backend_analysis_services()
        payload = backend_get_snapshot_payload(int(snapshot_id))
        if payload is not None:
            return payload
    except Exception:
        pass

    from cohort_tools import get_cohort_snapshot

    return get_cohort_snapshot(int(snapshot_id))
