"""Integration tests for read-only cohort snapshot and study workspace API bridging."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import database as legacy_database
from app.api.workspaces import (
    get_cohort_snapshot,
    get_study_workspace,
    list_cohort_snapshots,
    list_study_workspaces,
    router as workspaces_router,
)
from app.config import settings
from app.main import app
from app.services.workspaces import get_study_workspace_payload
from cohort_tools import load_cohort_records, save_cohort_snapshot
from study_workspace_service import create_or_open_study_workspace_from_snapshot


def _experiment_payload(
    *,
    test_number: str,
    root_batch_name: str,
    qdis_values: list[float],
) -> str:
    df = pd.DataFrame(
        {
            "Cycle": list(range(1, len(qdis_values) + 1)),
            "Q Dis (mAh/g)": qdis_values,
            "Q charge (mA.h)": [(value + 2.0) / 100 for value in qdis_values],
            "Q discharge (mA.h)": [value / 100 for value in qdis_values],
        }
    )
    return json.dumps(
        {
            "experiment_date": "2026-03-20",
            "cells": [
                {
                    "cell_name": test_number,
                    "test_number": test_number,
                    "formation_cycles": 1,
                    "temperature": 25.0,
                    "c_rate": 0.5,
                    "data_json": df.to_json(),
                }
            ],
            "tracking": {"status": "Completed", "missing_cell_count": 0},
            "ontology": {
                "display_batch_name": root_batch_name,
                "display_root_batch_name": root_batch_name,
                "mapping_basis": "cell_build_edge",
            },
        }
    )


def _seed_legacy_workspace(tmp_path: Path, monkeypatch, *, include_metrics: bool = True) -> tuple[int, int]:
    db_path = tmp_path / "legacy-cellscope.db"
    monkeypatch.setattr(legacy_database, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(settings, "legacy_database_path", str(db_path))
    legacy_database.init_database()
    legacy_database.migrate_database()

    with legacy_database.get_db_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, user_id, name, project_type) VALUES (1, 'admin', 'Bridge Project', 'Full Cell')"
        )
        conn.execute(
            """
            INSERT INTO cell_experiments (id, project_id, cell_name, electrolyte, data_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                10,
                1,
                "FC5",
                "LiPF6",
                _experiment_payload(
                    test_number="FC5 i",
                    root_batch_name="N10",
                    qdis_values=[200.0, 199.0, 198.0, 197.0, 196.0, 195.0, 194.0, 193.0, 192.0, 191.0],
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO cell_experiments (id, project_id, cell_name, electrolyte, data_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                11,
                1,
                "FC6",
                "LiPF6",
                _experiment_payload(
                    test_number="FC6 i",
                    root_batch_name="N11",
                    qdis_values=[210.0, 209.0, 208.0, 207.0, 206.0, 205.0, 204.0, 203.0, 202.0, 201.0],
                ),
            ),
        )
        conn.commit()

    load_cohort_records()

    if include_metrics:
        with legacy_database.get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO derived_experiment_metrics (experiment_id, source_signature, metrics_json)
                VALUES (?, ?, ?)
                """,
                (
                    10,
                    "sig-10",
                    json.dumps(
                        {
                            "experiment_summary": {
                                "avg_retention_pct": 91.0,
                                "avg_coulombic_efficiency_pct": 99.4,
                                "avg_fade_rate_pct_per_100_cycles": 1.8,
                                "best_cycle_life_80": 180,
                            }
                        }
                    ),
                ),
            )
            conn.execute(
                """
                INSERT INTO derived_experiment_metrics (experiment_id, source_signature, metrics_json)
                VALUES (?, ?, ?)
                """,
                (
                    11,
                    "sig-11",
                    json.dumps(
                        {
                            "experiment_summary": {
                                "avg_retention_pct": 88.0,
                                "avg_coulombic_efficiency_pct": 99.1,
                                "avg_fade_rate_pct_per_100_cycles": 2.2,
                                "best_cycle_life_80": 155,
                            }
                        }
                    ),
                ),
            )
            conn.commit()

    records = load_cohort_records()
    snapshot_id = save_cohort_snapshot(
        name="Backend Bridge Snapshot",
        description="Legacy snapshot exposed through FastAPI",
        filters={"ontology_only": True},
        records=records,
    )
    workspace_id, _ = create_or_open_study_workspace_from_snapshot(snapshot_id)
    return snapshot_id, workspace_id


def test_workspace_router_registers_read_only_analysis_routes():
    route_paths = {route.path for route in workspaces_router.routes}
    assert "/api/analysis/cohort-snapshots" in route_paths
    assert "/api/analysis/cohort-snapshots/{snapshot_id}" in route_paths
    assert "/api/analysis/study-workspaces" in route_paths
    assert "/api/analysis/study-workspaces/{workspace_id}" in route_paths

    app_route_paths = {route.path for route in app.routes}
    assert "/api/analysis/cohort-snapshots" in app_route_paths
    assert "/api/analysis/study-workspaces/{workspace_id}" in app_route_paths


def test_workspace_api_reads_legacy_snapshot_and_workspace_payloads(tmp_path, monkeypatch):
    snapshot_id, workspace_id = _seed_legacy_workspace(tmp_path, monkeypatch, include_metrics=True)

    snapshot_list = list_cohort_snapshots()
    snapshot_detail = get_cohort_snapshot(snapshot_id)
    workspace_list = list_study_workspaces()
    workspace_payload = get_study_workspace(workspace_id, refresh=False)

    assert len(snapshot_list) == 1
    assert snapshot_detail.name == "Backend Bridge Snapshot"
    assert len(snapshot_detail.member_records) == 2
    assert snapshot_detail.summary["metrics_ready_experiment_count"] == 2

    assert len(workspace_list) == 1
    assert workspace_list[0].snapshot_id == snapshot_id
    assert workspace_payload.summary["workspace_name"] == "Backend Bridge Snapshot Workspace"
    assert workspace_payload.summary["experiment_count"] == 2
    assert len(workspace_payload.plots.cells_data) == 2
    assert len(workspace_payload.plots.project_summaries) == 1
    assert len(workspace_payload.plots.metric_rows) == 2
    assert workspace_payload.lineage_context["root_batches"][0]["Parent Batch"] == "N10"


def test_workspace_service_is_read_only_by_default_for_missing_legacy_metrics(tmp_path, monkeypatch):
    _, workspace_id = _seed_legacy_workspace(tmp_path, monkeypatch, include_metrics=False)

    payload = get_study_workspace_payload(workspace_id)

    assert payload is not None
    assert payload["summary"]["metrics_ready_experiment_count"] == 0
    assert payload["summary"]["metrics_refreshed_count"] == 0

    with legacy_database.get_db_connection() as conn:
        metric_rows = conn.execute("SELECT COUNT(*) FROM derived_experiment_metrics").fetchone()

    assert metric_rows[0] == 0
