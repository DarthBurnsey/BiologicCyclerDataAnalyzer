"""Persistence and payload assembly for snapshot-backed study workspaces."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Literal, Optional, TypedDict

from analysis_surface_service import build_analysis_surface_payload
from backend_metrics_bridge import load_preferred_experiment_metrics_map
from cohort_tools import (
    build_cohort_comparison_payload,
    get_cohort_snapshot,
    load_cohort_records,
    summarize_cohort,
)
from database import get_db_connection


StudyWorkspaceItemType = Literal["COHORT_SNAPSHOT", "EXPERIMENT", "ROOT_BATCH", "NOTE"]


class StudyWorkspace(TypedDict, total=False):
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


class StudyWorkspaceItem(TypedDict, total=False):
    id: int
    workspace_id: int
    item_type: StudyWorkspaceItemType
    item_key: str
    item_label: Optional[str]
    payload: Dict[str, Any]
    created_date: Optional[str]
    updated_date: Optional[str]


class StudyWorkspaceAnnotation(TypedDict, total=False):
    id: int
    workspace_id: int
    annotation_type: str
    title: Optional[str]
    body: str
    related_item_type: Optional[str]
    related_item_key: Optional[str]
    created_date: Optional[str]
    updated_date: Optional[str]


class StudyWorkspacePayload(TypedDict, total=False):
    summary: Dict[str, Any]
    members: list[Dict[str, Any]]
    plots: Dict[str, Any]
    lineage_context: Dict[str, Any]
    tracking_context: Dict[str, Any]
    annotations: list[StudyWorkspaceAnnotation]


def _ensure_workspace_tables() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS study_workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                cohort_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                source_membership_signature TEXT NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (snapshot_id) REFERENCES cohort_snapshots (id) ON DELETE CASCADE,
                FOREIGN KEY (cohort_id) REFERENCES saved_cohorts (id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS study_workspace_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                item_key TEXT NOT NULL,
                item_label TEXT,
                payload_json TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES study_workspaces (id) ON DELETE CASCADE,
                UNIQUE(workspace_id, item_type, item_key)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS study_workspace_annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                annotation_type TEXT NOT NULL DEFAULT 'NOTE',
                title TEXT,
                body TEXT NOT NULL,
                related_item_type TEXT,
                related_item_key TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES study_workspaces (id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def _normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_json_dict(raw_value: Any) -> Dict[str, Any]:
    if not raw_value:
        return {}
    try:
        payload = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _workspace_name_for_snapshot(snapshot: Dict[str, Any], override_name: Optional[str] = None) -> str:
    if _normalize_text(override_name):
        return str(override_name).strip()
    base_name = _normalize_text(snapshot.get("name")) or "Snapshot"
    return f"{base_name} Workspace"


def _fetch_workspace_row(workspace_id: int) -> Optional[StudyWorkspace]:
    _ensure_workspace_tables()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                sw.id,
                sw.snapshot_id,
                sw.cohort_id,
                cs.name,
                sc.name,
                sw.name,
                sw.description,
                sw.status,
                sw.source_membership_signature,
                (
                    SELECT COUNT(*)
                    FROM study_workspace_items swi
                    WHERE swi.workspace_id = sw.id
                ) AS item_count,
                (
                    SELECT COUNT(*)
                    FROM study_workspace_annotations swa
                    WHERE swa.workspace_id = sw.id
                ) AS annotation_count,
                sw.created_date,
                sw.updated_date,
                sw.last_opened_at
            FROM study_workspaces sw
            LEFT JOIN cohort_snapshots cs ON cs.id = sw.snapshot_id
            LEFT JOIN saved_cohorts sc ON sc.id = sw.cohort_id
            WHERE sw.id = ?
            """,
            (int(workspace_id),),
        )
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": int(row[0]),
        "snapshot_id": int(row[1]),
        "cohort_id": int(row[2]) if row[2] is not None else None,
        "snapshot_name": row[3],
        "cohort_name": row[4],
        "name": row[5],
        "description": row[6],
        "status": row[7],
        "source_membership_signature": row[8],
        "item_count": int(row[9] or 0),
        "annotation_count": int(row[10] or 0),
        "created_date": row[11],
        "updated_date": row[12],
        "last_opened_at": row[13],
    }


def _list_workspace_annotations(workspace_id: int) -> list[StudyWorkspaceAnnotation]:
    _ensure_workspace_tables()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id,
                workspace_id,
                annotation_type,
                title,
                body,
                related_item_type,
                related_item_key,
                created_date,
                updated_date
            FROM study_workspace_annotations
            WHERE workspace_id = ?
            ORDER BY updated_date DESC, id DESC
            """,
            (int(workspace_id),),
        )
        rows = cursor.fetchall()

    return [
        {
            "id": int(row[0]),
            "workspace_id": int(row[1]),
            "annotation_type": row[2],
            "title": row[3],
            "body": row[4],
            "related_item_type": row[5],
            "related_item_key": row[6],
            "created_date": row[7],
            "updated_date": row[8],
        }
        for row in rows
    ]


def _sync_workspace_items(workspace_id: int, snapshot: Dict[str, Any]) -> None:
    member_records = snapshot.get("member_records") or []
    root_batch_payloads: Dict[str, Dict[str, Any]] = {}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM study_workspace_items WHERE workspace_id = ? AND item_type != 'NOTE'",
            (int(workspace_id),),
        )
        cursor.execute(
            """
            INSERT OR REPLACE INTO study_workspace_items (
                workspace_id, item_type, item_key, item_label, payload_json, updated_date
            )
            VALUES (?, 'COHORT_SNAPSHOT', ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                int(workspace_id),
                str(snapshot.get("id")),
                snapshot.get("name"),
                json.dumps(
                    {
                        "snapshot_id": snapshot.get("id"),
                        "snapshot_name": snapshot.get("name"),
                        "cohort_name": snapshot.get("cohort_name"),
                        "membership_signature": snapshot.get("membership_signature"),
                    }
                ),
            ),
        )

        for member in member_records:
            experiment_id = member.get("experiment_id")
            if experiment_id is None:
                continue
            cursor.execute(
                """
                INSERT OR REPLACE INTO study_workspace_items (
                    workspace_id, item_type, item_key, item_label, payload_json, updated_date
                )
                VALUES (?, 'EXPERIMENT', ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    int(workspace_id),
                    str(experiment_id),
                    member.get("experiment_name"),
                    json.dumps(
                        {
                            "experiment_id": experiment_id,
                            "experiment_name": member.get("experiment_name"),
                            "project_id": member.get("project_id"),
                            "project_name": member.get("project_name"),
                        }
                    ),
                ),
            )

            root_batch_name = _normalize_text(member.get("ontology_root_batch_name"))
            if root_batch_name and root_batch_name not in root_batch_payloads:
                root_batch_payloads[root_batch_name] = {
                    "root_batch_name": root_batch_name,
                    "ontology": _json_safe(member.get("ontology") or {}),
                }

        for root_batch_name, payload in root_batch_payloads.items():
            cursor.execute(
                """
                INSERT OR REPLACE INTO study_workspace_items (
                    workspace_id, item_type, item_key, item_label, payload_json, updated_date
                )
                VALUES (?, 'ROOT_BATCH', ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    int(workspace_id),
                    root_batch_name,
                    root_batch_name,
                    json.dumps(payload),
                ),
            )
        conn.commit()


def create_or_open_study_workspace_from_snapshot(
    snapshot_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> tuple[int, bool]:
    _ensure_workspace_tables()
    snapshot = get_cohort_snapshot(int(snapshot_id))
    if not snapshot:
        raise ValueError("That cohort snapshot is no longer available.")

    created = False
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id
            FROM study_workspaces
            WHERE snapshot_id = ?
            ORDER BY updated_date DESC, id DESC
            LIMIT 1
            """,
            (int(snapshot_id),),
        )
        row = cursor.fetchone()

        if row:
            workspace_id = int(row[0])
            cursor.execute(
                """
                UPDATE study_workspaces
                SET last_opened_at = CURRENT_TIMESTAMP,
                    updated_date = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (workspace_id,),
            )
            conn.commit()
        else:
            cursor.execute(
                """
                INSERT INTO study_workspaces (
                    snapshot_id,
                    cohort_id,
                    name,
                    description,
                    status,
                    source_membership_signature
                )
                VALUES (?, ?, ?, ?, 'ACTIVE', ?)
                """,
                (
                    int(snapshot_id),
                    snapshot.get("cohort_id"),
                    _workspace_name_for_snapshot(snapshot, name),
                    _normalize_text(description),
                    snapshot.get("membership_signature") or "",
                ),
            )
            workspace_id = int(cursor.lastrowid)
            conn.commit()
            created = True

    _sync_workspace_items(workspace_id, snapshot)
    return workspace_id, created


def list_study_workspaces() -> list[StudyWorkspace]:
    _ensure_workspace_tables()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id
            FROM study_workspaces
            ORDER BY last_opened_at DESC, updated_date DESC, id DESC
            """
        )
        workspace_ids = [int(row[0]) for row in cursor.fetchall()]
    return [workspace for workspace in (_fetch_workspace_row(workspace_id) for workspace_id in workspace_ids) if workspace]


def get_study_workspace(workspace_id: int) -> Optional[StudyWorkspace]:
    return _fetch_workspace_row(int(workspace_id))


def delete_study_workspace(workspace_id: int) -> None:
    _ensure_workspace_tables()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM study_workspaces WHERE id = ?", (int(workspace_id),))
        conn.commit()


def save_study_workspace_annotation(
    workspace_id: int,
    *,
    body: str,
    title: Optional[str] = None,
    annotation_type: str = "NOTE",
    related_item_type: Optional[str] = None,
    related_item_key: Optional[str] = None,
) -> int:
    _ensure_workspace_tables()
    normalized_body = _normalize_text(body)
    if not normalized_body:
        raise ValueError("Enter note text before saving.")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO study_workspace_annotations (
                workspace_id,
                annotation_type,
                title,
                body,
                related_item_type,
                related_item_key
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(workspace_id),
                _normalize_text(annotation_type) or "NOTE",
                _normalize_text(title),
                normalized_body,
                _normalize_text(related_item_type),
                _normalize_text(related_item_key),
            ),
        )
        annotation_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT OR REPLACE INTO study_workspace_items (
                workspace_id, item_type, item_key, item_label, payload_json, updated_date
            )
            VALUES (?, 'NOTE', ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                int(workspace_id),
                str(annotation_id),
                _normalize_text(title) or "Note",
                json.dumps(
                    {
                        "annotation_id": annotation_id,
                        "title": _normalize_text(title),
                        "body": normalized_body,
                        "related_item_type": _normalize_text(related_item_type),
                        "related_item_key": _normalize_text(related_item_key),
                    }
                ),
            ),
        )
        cursor.execute(
            """
            UPDATE study_workspaces
            SET updated_date = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (int(workspace_id),),
        )
        conn.commit()
    return annotation_id


def delete_study_workspace_annotation(annotation_id: int) -> None:
    _ensure_workspace_tables()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT workspace_id FROM study_workspace_annotations WHERE id = ?",
            (int(annotation_id),),
        )
        row = cursor.fetchone()
        if not row:
            return
        workspace_id = int(row[0])
        cursor.execute(
            "DELETE FROM study_workspace_annotations WHERE id = ?",
            (int(annotation_id),),
        )
        cursor.execute(
            """
            DELETE FROM study_workspace_items
            WHERE workspace_id = ? AND item_type = 'NOTE' AND item_key = ?
            """,
            (workspace_id, str(annotation_id)),
        )
        cursor.execute(
            """
            UPDATE study_workspaces
            SET updated_date = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (workspace_id,),
        )
        conn.commit()


def _build_workspace_members(
    snapshot: Dict[str, Any],
    metrics_map: Dict[int, Dict[str, Any]],
) -> list[Dict[str, Any]]:
    current_records = {
        int(record["experiment_id"]): record
        for record in load_cohort_records()
        if record.get("experiment_id") is not None
    }
    members: list[Dict[str, Any]] = []
    for stored_member in snapshot.get("member_records") or []:
        experiment_id = stored_member.get("experiment_id")
        if experiment_id is None:
            continue
        merged = dict(stored_member)
        latest = current_records.get(int(experiment_id))
        if latest:
            merged.update(latest)
            merged["workspace_member_source"] = "current"
        else:
            merged["workspace_member_source"] = "snapshot"

        metrics_payload = metrics_map.get(int(experiment_id), {})
        metrics_source = _normalize_text(metrics_payload.get("metrics_source"))
        merged["derived_metrics_cache_hit"] = bool(metrics_payload.get("cache_hit"))
        merged["derived_metrics_computed_at"] = (
            metrics_payload.get("computed_at") or merged.get("derived_metrics_computed_at")
        )
        if metrics_source and metrics_source.startswith("backend"):
            merged["metrics_source"] = metrics_source
            merged["metric_refresh_status"] = "backend"
        elif metrics_payload:
            merged["metrics_source"] = metrics_source or "legacy"
            merged["metric_refresh_status"] = (
                "cached" if metrics_payload.get("cache_hit") else "refreshed"
            )
        else:
            merged["metrics_source"] = "unavailable"
            merged["metric_refresh_status"] = "unavailable"
        members.append(merged)
    return members


def build_workspace_cells_data(members: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return (build_analysis_surface_payload(members).get("plots") or {}).get("cells_data") or []


def build_workspace_project_summaries(members: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return (build_analysis_surface_payload(members).get("plots") or {}).get("project_summaries") or []


def build_workspace_experiments_data(members: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return (build_analysis_surface_payload(members).get("plots") or {}).get("experiments_data") or []


def build_workspace_metric_rows(members: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return (build_analysis_surface_payload(members).get("plots") or {}).get("metric_rows") or []


def build_study_workspace_payload(
    workspace_id: int,
    *,
    refresh: bool = False,
    compute_missing_legacy: bool = True,
) -> Optional[StudyWorkspacePayload]:
    workspace = get_study_workspace(int(workspace_id))
    if not workspace:
        return None

    snapshot = get_cohort_snapshot(int(workspace["snapshot_id"]))
    if not snapshot:
        return None

    experiment_ids = [int(item) for item in snapshot.get("experiment_ids", [])]
    metrics_map = load_preferred_experiment_metrics_map(
        experiment_ids,
        refresh=refresh,
        compute_missing_legacy=compute_missing_legacy,
    )
    members = _build_workspace_members(snapshot, metrics_map)
    analysis_payload = build_analysis_surface_payload(members)
    plot_payload = analysis_payload.get("plots") or {}
    annotations = _list_workspace_annotations(int(workspace_id))
    lineage_context = analysis_payload.get("lineage_context") or {}
    tracking_context = analysis_payload.get("tracking_context") or {}

    summary = summarize_cohort(members)
    computed_at_values = sorted(
        {
            str(member.get("derived_metrics_computed_at"))
            for member in members
            if member.get("derived_metrics_computed_at")
        }
    )
    metrics_refreshed_count = sum(
        1 for member in members if member.get("metric_refresh_status") == "refreshed"
    )
    metrics_backend_count = sum(
        1 for member in members if member.get("metric_refresh_status") == "backend"
    )
    metrics_cached_count = sum(
        1 for member in members if member.get("metric_refresh_status") == "cached"
    )
    metrics_unavailable_count = sum(
        1 for member in members if member.get("metric_refresh_status") == "unavailable"
    )
    summary.update(
        {
            "workspace_id": workspace["id"],
            "workspace_name": workspace["name"],
            "workspace_description": workspace.get("description"),
            "workspace_status": workspace.get("status"),
            "snapshot_id": workspace["snapshot_id"],
            "snapshot_name": workspace.get("snapshot_name"),
            "cohort_id": workspace.get("cohort_id"),
            "cohort_name": workspace.get("cohort_name"),
            "metrics_refreshed_count": metrics_refreshed_count,
            "metrics_cached_count": metrics_cached_count,
            "metrics_backend_count": metrics_backend_count,
            "metrics_unavailable_count": metrics_unavailable_count,
            "metrics_oldest_computed_at": computed_at_values[0] if computed_at_values else None,
            "metrics_latest_computed_at": computed_at_values[-1] if computed_at_values else None,
            "annotation_count": len(annotations),
            "root_batch_count": len(lineage_context.get("root_batches") or []),
            "plot_summary": _json_safe(analysis_payload.get("plot_summary") or {}),
        }
    )

    return {
        "summary": _json_safe(summary),
        "members": _json_safe(members),
        "plots": {
            "cells_data": _json_safe(plot_payload.get("cells_data") or []),
            "project_summaries": _json_safe(plot_payload.get("project_summaries") or []),
            "experiments_data": plot_payload.get("experiments_data") or [],
            "metric_rows": _json_safe(plot_payload.get("metric_rows") or []),
        },
        "lineage_context": _json_safe(lineage_context),
        "tracking_context": _json_safe(tracking_context),
        "annotations": _json_safe(annotations),
    }


def build_study_workspace_comparison_payload(
    payload: StudyWorkspacePayload,
    experiment_ids: Optional[Iterable[int]] = None,
) -> Optional[Dict[str, Any]]:
    members = payload.get("members") or []
    if experiment_ids is not None:
        selected = {int(item) for item in experiment_ids}
        members = [
            member for member in members
            if member.get("experiment_id") is not None and int(member["experiment_id"]) in selected
        ]
    return build_cohort_comparison_payload(members)


def build_study_workspace_export_payload(payload: StudyWorkspacePayload) -> Dict[str, Any]:
    summary = dict(payload.get("summary") or {})
    plot_summary = summary.pop("plot_summary", {})
    return {
        "summary": _json_safe(summary),
        "members": _json_safe(payload.get("members") or []),
        "lineage_context": {
            "root_batches": _json_safe((payload.get("lineage_context") or {}).get("root_batches") or []),
        },
        "tracking_context": _json_safe(payload.get("tracking_context") or {}),
        "annotations": _json_safe(payload.get("annotations") or []),
        "plot_summary": _json_safe(plot_summary),
    }


def format_study_workspace_markdown(payload: StudyWorkspacePayload) -> str:
    summary = payload.get("summary") or {}
    lines = [
        f"# Study Workspace: {summary.get('workspace_name') or 'Unnamed Workspace'}",
        "",
        f"- Snapshot: {summary.get('snapshot_name') or 'Unknown'}",
        f"- Cohort: {summary.get('cohort_name') or 'Standalone snapshot'}",
        f"- Experiments: {summary.get('experiment_count', 0)}",
        f"- Cells: {summary.get('cell_count', 0)}",
        f"- Metrics Ready: {summary.get('metrics_ready_experiment_count', 0)}",
        f"- Parent Batches: {summary.get('root_batch_count', 0)}",
    ]
    if summary.get("avg_retention_pct") is not None:
        lines.append(f"- Avg Retention: {summary['avg_retention_pct']:.2f}%")
    if summary.get("avg_coulombic_efficiency_pct") is not None:
        lines.append(f"- Avg CE: {summary['avg_coulombic_efficiency_pct']:.3f}%")
    if summary.get("avg_fade_rate_pct_per_100_cycles") is not None:
        lines.append(f"- Avg Fade: {summary['avg_fade_rate_pct_per_100_cycles']:.3f}% / 100 cycles")
    if summary.get("best_cycle_life_80") is not None:
        lines.append(f"- Best Cycle Life (80%): {summary['best_cycle_life_80']:.0f}")
    if summary.get("metrics_latest_computed_at"):
        lines.append(f"- Metrics Freshness: {summary['metrics_latest_computed_at']}")

    root_batches = (payload.get("lineage_context") or {}).get("root_batches") or []
    if root_batches:
        lines.extend(["", "## Parent Batch Rollup", ""])
        for row in root_batches:
            lines.append(
                f"- {row['Parent Batch']}: {row['Experiments']} experiments, "
                f"{row['Cells']} cells"
            )

    annotations = payload.get("annotations") or []
    if annotations:
        lines.extend(["", "## Notes", ""])
        for annotation in annotations:
            title = annotation.get("title") or "Note"
            lines.append(f"- {title}: {annotation.get('body') or ''}")

    return "\n".join(lines)
