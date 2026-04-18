from __future__ import annotations

import json
import sqlite3

import pandas as pd

import analysis_surface_service
import database
from cohort_tools import load_cohort_records, save_cohort_snapshot
from study_workspace_service import (
    build_study_workspace_comparison_payload,
    build_study_workspace_export_payload,
    build_study_workspace_payload,
    create_or_open_study_workspace_from_snapshot,
    delete_study_workspace_annotation,
    format_study_workspace_markdown,
    list_study_workspaces,
    save_study_workspace_annotation,
)


def _init_backend_metrics_db(
    db_path,
    *,
    legacy_experiment_ids: list[int],
    retention_values: list[float],
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE ontology_cell_builds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                build_name TEXT NOT NULL,
                legacy_experiment_id INTEGER,
                legacy_test_number TEXT
            );

            CREATE TABLE test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cell_build_id INTEGER,
                last_cycle_index INTEGER,
                latest_charge_capacity_mah REAL,
                latest_discharge_capacity_mah REAL,
                latest_efficiency REAL
            );

            CREATE TABLE metric_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_run_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                finished_at TEXT
            );

            CREATE TABLE metric_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE
            );

            CREATE TABLE run_metric_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_run_id INTEGER NOT NULL,
                metric_definition_id INTEGER NOT NULL,
                value_numeric REAL,
                value_json TEXT
            );

            CREATE TABLE cycle_metric_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_run_id INTEGER NOT NULL,
                cycle_index INTEGER NOT NULL,
                metric_definition_id INTEGER NOT NULL,
                value_numeric REAL
            );
            """
        )
        metric_keys = [
            "capacity_retention_pct",
            "average_coulombic_efficiency_pct",
            "fade_rate_pct_per_100_cycles",
            "last_cycle_index",
            "latest_charge_capacity_mah",
            "latest_discharge_capacity_mah",
            "latest_efficiency_pct",
        ]
        for index, key in enumerate(metric_keys, start=1):
            connection.execute(
                "INSERT INTO metric_definitions (id, key) VALUES (?, ?)",
                (index, key),
            )

        for index, (legacy_experiment_id, retention_value) in enumerate(
            zip(legacy_experiment_ids, retention_values),
            start=1,
        ):
            connection.execute(
                """
                INSERT INTO ontology_cell_builds (
                    id, build_name, legacy_experiment_id, legacy_test_number
                ) VALUES (?, ?, ?, ?)
                """,
                (index, f"build-{legacy_experiment_id}", legacy_experiment_id, f"FC{index + 4} i"),
            )
            connection.execute(
                """
                INSERT INTO test_runs (
                    id, cell_build_id, last_cycle_index, latest_charge_capacity_mah,
                    latest_discharge_capacity_mah, latest_efficiency
                ) VALUES (?, ?, 120, 2.01, 1.98, 99.2)
                """,
                (index, index),
            )
            connection.execute(
                """
                INSERT INTO metric_runs (id, test_run_id, status, finished_at)
                VALUES (?, ?, 'SUCCEEDED', '2026-03-22 12:00:00')
                """,
                (index, index),
            )
            rows = [
                (index, 1, retention_value),
                (index, 2, 99.5),
                (index, 3, 1.4),
                (index, 4, 120.0),
                (index, 5, 2.01),
                (index, 6, 1.98),
                (index, 7, 99.2),
            ]
            for metric_run_id, metric_definition_id, value_numeric in rows:
                connection.execute(
                    """
                    INSERT INTO run_metric_values (
                        metric_run_id, metric_definition_id, value_numeric, value_json
                    ) VALUES (?, ?, ?, NULL)
                    """,
                    (metric_run_id, metric_definition_id, value_numeric),
                )
        connection.commit()
    finally:
        connection.close()


def _experiment_payload(
    *,
    test_number: str,
    root_batch_name: str,
    qdis_values: list[float],
    tracking_status: str = "Completed",
) -> str:
    cycle_count = len(qdis_values)
    df = pd.DataFrame(
        {
            "Cycle": list(range(1, cycle_count + 1)),
            "Q Dis (mAh/g)": qdis_values,
            "Q charge (mA.h)": [(value + 2.0) / 100 for value in qdis_values],
            "Q discharge (mA.h)": [value / 100 for value in qdis_values],
        }
    )
    return json.dumps(
        {
            "experiment_date": "2026-01-20",
            "disc_diameter_mm": 15,
            "cells": [
                {
                    "cell_name": test_number,
                    "test_number": test_number,
                    "loading": 16.8,
                    "active_material": 92.0,
                    "formation_cycles": 1,
                    "data_json": df.to_json(),
                }
            ],
            "tracking": {"status": tracking_status, "missing_cell_count": 0},
            "ontology": {
                "display_batch_name": root_batch_name,
                "display_root_batch_name": root_batch_name,
                "mapping_basis": "cell_build_edge",
            },
        }
    )


def _seed_workspace_snapshot(tmp_path, monkeypatch) -> tuple[int, list[dict]]:
    db_path = tmp_path / "cellscope.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    database.init_database()
    database.migrate_database()

    with database.get_db_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, user_id, name, project_type) VALUES (1, 'admin', 'NMC Full Cells', 'Full Cell')"
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
                "1M LiPF6 EC:EMC:DMC 1:1:1 + 2% LiDFOB",
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
                "1M LiPF6 EC:EMC:DMC 1:1:1 + 2% LiDFOB",
                _experiment_payload(
                    test_number="FC6 i",
                    root_batch_name="N11",
                    qdis_values=[210.0, 209.5, 209.0, 208.5, 208.0, 207.5, 207.0, 206.5, 206.0, 205.5],
                ),
            ),
        )
        conn.commit()

    records = load_cohort_records()
    snapshot_id = save_cohort_snapshot(
        name="Workspace Snapshot",
        description="Snapshot used for workspace tests",
        filters={"ontology_only": True},
        records=records,
    )
    return snapshot_id, records


def test_create_or_open_workspace_from_snapshot_persists_seed_items(tmp_path, monkeypatch):
    snapshot_id, _ = _seed_workspace_snapshot(tmp_path, monkeypatch)

    workspace_id, created = create_or_open_study_workspace_from_snapshot(snapshot_id)
    assert created is True

    reopened_id, reopened_created = create_or_open_study_workspace_from_snapshot(snapshot_id)
    assert reopened_id == workspace_id
    assert reopened_created is False

    workspaces = list_study_workspaces()
    assert len(workspaces) == 1
    assert workspaces[0]["snapshot_id"] == snapshot_id
    assert workspaces[0]["item_count"] >= 5

    with database.get_db_connection() as conn:
        item_types = {
            row[0]
            for row in conn.execute(
                "SELECT item_type FROM study_workspace_items WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchall()
        }
    assert {"COHORT_SNAPSHOT", "EXPERIMENT", "ROOT_BATCH"}.issubset(item_types)


def test_workspace_payload_auto_refreshes_metrics_and_supports_exports(tmp_path, monkeypatch):
    snapshot_id, records = _seed_workspace_snapshot(tmp_path, monkeypatch)
    workspace_id, _ = create_or_open_study_workspace_from_snapshot(snapshot_id)

    payload = build_study_workspace_payload(workspace_id)
    assert payload is not None
    assert payload["summary"]["experiment_count"] == len(records)
    assert payload["summary"]["metrics_ready_experiment_count"] == len(records)
    assert payload["summary"]["metrics_refreshed_count"] == len(records)
    assert len(payload["plots"]["cells_data"]) == len(records)
    assert len(payload["plots"]["project_summaries"]) == 1

    comparison_payload = build_study_workspace_comparison_payload(payload)
    assert comparison_payload == {
        "project_id": 1,
        "project_name": "NMC Full Cells",
        "experiment_names": ["FC5", "FC6"],
    }

    export_payload = build_study_workspace_export_payload(payload)
    assert export_payload["summary"]["workspace_name"] == "Workspace Snapshot Workspace"
    assert len(export_payload["members"]) == len(records)

    markdown = format_study_workspace_markdown(payload)
    assert "# Study Workspace: Workspace Snapshot Workspace" in markdown
    assert "## Parent Batch Rollup" in markdown


def test_workspace_payload_recomputes_stale_metrics_when_experiment_changes(tmp_path, monkeypatch):
    snapshot_id, _ = _seed_workspace_snapshot(tmp_path, monkeypatch)
    workspace_id, _ = create_or_open_study_workspace_from_snapshot(snapshot_id)

    first_payload = build_study_workspace_payload(workspace_id)
    assert first_payload is not None
    first_retention = first_payload["summary"]["avg_retention_pct"]

    with database.get_db_connection() as conn:
        conn.execute(
            "UPDATE cell_experiments SET data_json = ? WHERE id = ?",
            (
                _experiment_payload(
                    test_number="FC5 i",
                    root_batch_name="N10",
                    qdis_values=[200.0, 196.0, 192.0, 188.0, 184.0, 180.0, 170.0, 160.0, 150.0, 140.0],
                ),
                10,
            ),
        )
        conn.commit()

    second_payload = build_study_workspace_payload(workspace_id)
    assert second_payload is not None
    assert second_payload["summary"]["metrics_refreshed_count"] >= 1
    assert second_payload["summary"]["avg_retention_pct"] != first_retention


def test_workspace_payload_uses_shared_analysis_loader_once_per_experiment(tmp_path, monkeypatch):
    snapshot_id, records = _seed_workspace_snapshot(tmp_path, monkeypatch)
    workspace_id, _ = create_or_open_study_workspace_from_snapshot(snapshot_id)
    calls: list[int] = []
    original_loader = analysis_surface_service.get_hydrated_experiment_payload

    def counting_loader(experiment_id: int):
        calls.append(int(experiment_id))
        return original_loader(experiment_id)

    monkeypatch.setattr(
        analysis_surface_service,
        "get_hydrated_experiment_payload",
        counting_loader,
    )

    payload = build_study_workspace_payload(workspace_id)

    assert payload is not None
    assert sorted(calls) == sorted(int(record["experiment_id"]) for record in records)
    assert len(calls) == len(records)


def test_workspace_annotations_round_trip_and_create_note_items(tmp_path, monkeypatch):
    snapshot_id, _ = _seed_workspace_snapshot(tmp_path, monkeypatch)
    workspace_id, _ = create_or_open_study_workspace_from_snapshot(snapshot_id)

    annotation_id = save_study_workspace_annotation(
        workspace_id,
        title="Next step",
        body="Prioritize the N10 branch for follow-up testing.",
    )
    payload = build_study_workspace_payload(workspace_id)
    assert payload is not None
    assert len(payload["annotations"]) == 1
    assert payload["annotations"][0]["title"] == "Next step"

    with database.get_db_connection() as conn:
        note_items = conn.execute(
            """
            SELECT item_type, item_key
            FROM study_workspace_items
            WHERE workspace_id = ? AND item_type = 'NOTE'
            """,
            (workspace_id,),
        ).fetchall()
    assert note_items == [("NOTE", str(annotation_id))]

    delete_study_workspace_annotation(annotation_id)
    refreshed_payload = build_study_workspace_payload(workspace_id)
    assert refreshed_payload is not None
    assert refreshed_payload["annotations"] == []


def test_workspace_payload_prefers_backend_metric_bridge_when_available(tmp_path, monkeypatch):
    snapshot_id, records = _seed_workspace_snapshot(tmp_path, monkeypatch)
    backend_db = tmp_path / "Cellscope 2.0" / "backend" / "cellscope2.db"
    _init_backend_metrics_db(
        backend_db,
        legacy_experiment_ids=[10, 11],
        retention_values=[90.0, 88.0],
    )

    with database.get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO derived_experiment_metrics (experiment_id, source_signature, metrics_json)
            VALUES (?, ?, ?)
            """,
            (
                10,
                "sig-10",
                json.dumps({"experiment_summary": {"avg_retention_pct": 70.0}}),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO derived_experiment_metrics (experiment_id, source_signature, metrics_json)
            VALUES (?, ?, ?)
            """,
            (
                11,
                "sig-11",
                json.dumps({"experiment_summary": {"avg_retention_pct": 71.0}}),
            ),
        )
        conn.commit()

    workspace_id, _ = create_or_open_study_workspace_from_snapshot(snapshot_id)
    payload = build_study_workspace_payload(workspace_id)

    assert payload is not None
    assert payload["summary"]["experiment_count"] == len(records)
    assert payload["summary"]["metrics_refreshed_count"] == 0
    assert payload["summary"]["metrics_backend_count"] == len(records)
    assert payload["summary"]["avg_retention_pct"] == 89.0
    assert {member["metric_refresh_status"] for member in payload["members"]} == {"backend"}
    assert all(str(member.get("metrics_source", "")).startswith("backend") for member in payload["members"])
