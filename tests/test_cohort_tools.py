from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import database
from cohort_tools import (
    apply_cohort_filters,
    build_cohort_comparison_payload,
    build_cohort_snapshot_export_payload,
    delete_cohort_snapshot,
    delete_saved_cohort,
    format_cohort_snapshot_markdown,
    get_cohort_snapshot,
    list_saved_cohorts,
    list_cohort_snapshots,
    load_cohort_records,
    save_saved_cohort,
    save_cohort_snapshot,
)


def _init_backend_metrics_db(
    db_path: Path,
    *,
    legacy_experiment_id: int,
    retention_pct: float,
    ce_pct: float,
    fade_pct_per_100: float,
    cycle_life_80: int,
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
        connection.execute(
            """
            INSERT INTO ontology_cell_builds (
                id, build_name, legacy_experiment_id, legacy_test_number
            ) VALUES (1, 'FC5-build', ?, 'FC5 i')
            """,
            (legacy_experiment_id,),
        )
        connection.execute(
            """
            INSERT INTO test_runs (
                id, cell_build_id, last_cycle_index, latest_charge_capacity_mah,
                latest_discharge_capacity_mah, latest_efficiency
            ) VALUES (1, 1, 160, 2.02, 1.95, 99.3)
            """
        )
        connection.execute(
            """
            INSERT INTO metric_runs (id, test_run_id, status, finished_at)
            VALUES (1, 1, 'SUCCEEDED', '2026-03-22 10:00:00')
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
            "retention_pct",
        ]
        for index, key in enumerate(metric_keys, start=1):
            connection.execute(
                "INSERT INTO metric_definitions (id, key) VALUES (?, ?)",
                (index, key),
            )
        run_metric_rows = [
            (1, 1, retention_pct),
            (1, 2, ce_pct),
            (1, 3, fade_pct_per_100),
            (1, 4, 160.0),
            (1, 5, 2.02),
            (1, 6, 1.95),
            (1, 7, 99.3),
        ]
        for metric_run_id, metric_definition_id, value_numeric in run_metric_rows:
            connection.execute(
                """
                INSERT INTO run_metric_values (
                    metric_run_id, metric_definition_id, value_numeric, value_json
                ) VALUES (?, ?, ?, NULL)
                """,
                (metric_run_id, metric_definition_id, value_numeric),
            )
        cycle_rows = [
            (1, 1, 8, 100.0),
            (1, cycle_life_80, 8, 79.5),
        ]
        for metric_run_id, cycle_index, metric_definition_id, value_numeric in cycle_rows:
            connection.execute(
                """
                INSERT INTO cycle_metric_values (
                    metric_run_id, cycle_index, metric_definition_id, value_numeric
                ) VALUES (?, ?, ?, ?)
                """,
                (metric_run_id, cycle_index, metric_definition_id, value_numeric),
            )
        connection.commit()
    finally:
        connection.close()


def _init_backend_ontology_only_db(
    db_path: Path,
    *,
    legacy_experiment_id: int,
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
            """
        )
        connection.execute(
            """
            INSERT INTO ontology_cell_builds (
                id, build_name, legacy_experiment_id, legacy_test_number
            ) VALUES (1, 'FC5-build', ?, 'FC5 i')
            """,
            (legacy_experiment_id,),
        )
        connection.execute(
            """
            INSERT INTO test_runs (
                id, cell_build_id, last_cycle_index, latest_charge_capacity_mah,
                latest_discharge_capacity_mah, latest_efficiency
            ) VALUES (1, 1, 160, 2.02, 1.95, 99.3)
            """
        )
        connection.commit()
    finally:
        connection.close()


def test_cohort_tools_filter_and_persist_saved_cohorts(tmp_path, monkeypatch):
    db_path = tmp_path / "cellscope.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    database.init_database()
    database.migrate_database()

    with database.get_db_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, user_id, name, project_type) VALUES (1, 'admin', 'NMC Half Cells', 'Cathode')"
        )
        conn.execute(
            "INSERT INTO projects (id, user_id, name, project_type) VALUES (2, 'admin', 'NMC- Si Full Cell', 'Full Cell')"
        )

        mapped_payload = {
            "experiment_date": "2026-01-20",
            "cells": [{"cell_name": "FC5 i", "electrolyte": "1M LiPF6 EC:EMC:DMC 1:1:1 + 2% LiDFOB"}],
            "tracking": {"status": "Completed", "missing_cell_count": 0},
            "ontology": {
                "display_batch_name": "N10",
                "display_root_batch_name": "N10",
                "mapping_basis": "cell_build_edge",
            },
        }
        unmapped_payload = {
            "experiment_date": "2026-02-01",
            "cells": [{"cell_name": "T35a i", "electrolyte": "Baseline"}],
            "tracking": {"status": "Active", "missing_cell_count": 1},
        }
        conn.execute(
            """
            INSERT INTO cell_experiments (
                id, project_id, cell_name, electrolyte, experiment_notes, data_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (10, 2, "FC5", "1M LiPF6 EC:EMC:DMC 1:1:1 + 2% LiDFOB", "Mapped full-cell experiment", json.dumps(mapped_payload)),
        )
        conn.execute(
            """
            INSERT INTO cell_experiments (
                id, project_id, cell_name, electrolyte, experiment_notes, data_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (11, 1, "Unmapped Test", "Baseline", "No ontology mapping yet", json.dumps(unmapped_payload)),
        )
        conn.commit()

    records = load_cohort_records()
    assert len(records) == 2
    assert any(record["ontology_root_batch_name"] == "N10" for record in records)

    filtered = apply_cohort_filters(
        records,
        {
            "ontology_only": True,
            "ontology_root_batch_names": ["N10"],
        },
    )
    assert [record["experiment_name"] for record in filtered] == ["FC5"]

    cohort_id = save_saved_cohort(
        name="N10 parent cohort",
        description="All ontology-mapped N10 experiments",
        filters={"ontology_only": True, "ontology_root_batch_names": ["N10"]},
    )
    saved = list_saved_cohorts()
    assert saved[0]["id"] == cohort_id
    assert saved[0]["filters"]["ontology_root_batch_names"] == ["N10"]

    delete_saved_cohort(cohort_id)
    assert list_saved_cohorts() == []


def test_build_cohort_comparison_payload_requires_single_project_scope():
    single_project_records = [
        {
            "project_id": 2,
            "project_name": "NMC- Si Full Cell",
            "experiment_name": "FC4a",
        },
        {
            "project_id": 2,
            "project_name": "NMC- Si Full Cell",
            "experiment_name": "FC5",
        },
    ]
    payload = build_cohort_comparison_payload(single_project_records)
    assert payload == {
        "project_id": 2,
        "project_name": "NMC- Si Full Cell",
        "experiment_names": ["FC4a", "FC5"],
    }

    mixed_project_records = single_project_records + [
        {
            "project_id": 1,
            "project_name": "NMC Half Cells",
            "experiment_name": "N10d",
        }
    ]
    assert build_cohort_comparison_payload(mixed_project_records) is None


def test_cohort_metric_filters_and_snapshot_persistence(tmp_path, monkeypatch):
    db_path = tmp_path / "cellscope.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    database.init_database()
    database.migrate_database()

    with database.get_db_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, user_id, name, project_type) VALUES (1, 'admin', 'NMC Half Cells', 'Cathode')"
        )
        payload_a = {
            "experiment_date": "2026-01-10",
            "cells": [{"cell_name": "N10d i", "electrolyte": "LiTFSI"}],
            "tracking": {"status": "Completed", "missing_cell_count": 0},
            "ontology": {"display_batch_name": "N10d", "display_root_batch_name": "N10"},
        }
        payload_b = {
            "experiment_date": "2026-01-11",
            "cells": [{"cell_name": "N9x i", "electrolyte": "LiPF6"}],
            "tracking": {"status": "Completed", "missing_cell_count": 0},
            "ontology": {"display_batch_name": "N9x", "display_root_batch_name": "N9"},
        }
        conn.execute(
            "INSERT INTO cell_experiments (id, project_id, cell_name, electrolyte, data_json) VALUES (10, 1, 'N10d', 'LiTFSI', ?)",
            (json.dumps(payload_a),),
        )
        conn.execute(
            "INSERT INTO cell_experiments (id, project_id, cell_name, electrolyte, data_json) VALUES (11, 1, 'N9x', 'LiPF6', ?)",
            (json.dumps(payload_b),),
        )
        conn.execute(
            """
            INSERT INTO derived_experiment_metrics (experiment_id, source_signature, metrics_json)
            VALUES (?, ?, ?)
            """,
            (
                10,
                "sig-a",
                json.dumps(
                    {
                        "experiment_summary": {
                            "experiment_name": "N10d",
                            "project_name": "NMC Half Cells",
                            "avg_retention_pct": 92.5,
                            "avg_coulombic_efficiency_pct": 99.4,
                            "avg_fade_rate_pct_per_100_cycles": 1.8,
                            "best_cycle_life_80": 180,
                            "avg_reversible_capacity_mAh_g": 201.5,
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
                "sig-b",
                json.dumps(
                    {
                        "experiment_summary": {
                            "experiment_name": "N9x",
                            "project_name": "NMC Half Cells",
                            "avg_retention_pct": 78.0,
                            "avg_coulombic_efficiency_pct": 98.7,
                            "avg_fade_rate_pct_per_100_cycles": 4.9,
                            "best_cycle_life_80": 95,
                            "avg_reversible_capacity_mAh_g": 182.0,
                        }
                    }
                ),
            ),
        )
        conn.commit()

    records = load_cohort_records()
    filtered = apply_cohort_filters(
        records,
        {
            "derived_metrics_only": True,
            "min_avg_retention_pct": 90,
            "max_avg_fade_rate_pct_per_100_cycles": 2.0,
            "min_best_cycle_life_80": 150,
        },
    )
    assert [record["experiment_name"] for record in filtered] == ["N10d"]

    cohort_id = save_saved_cohort(
        name="Strong N10 cohort",
        description="Metric-qualified N10d experiment",
        filters={
            "derived_metrics_only": True,
            "min_avg_retention_pct": 90,
            "max_avg_fade_rate_pct_per_100_cycles": 2.0,
            "min_best_cycle_life_80": 150,
        },
    )
    snapshot_id = save_cohort_snapshot(
        name="Strong N10 snapshot",
        description="Persisted metric-qualified snapshot",
        filters={
            "derived_metrics_only": True,
            "min_avg_retention_pct": 90,
            "max_avg_fade_rate_pct_per_100_cycles": 2.0,
            "min_best_cycle_life_80": 150,
        },
        records=filtered,
        cohort_id=cohort_id,
    )

    snapshots = list_cohort_snapshots()
    assert snapshots[0]["id"] == snapshot_id
    assert snapshots[0]["summary"]["avg_retention_pct"] == 92.5
    snapshot = get_cohort_snapshot(snapshot_id)
    assert snapshot is not None
    assert snapshot["member_records"][0]["experiment_name"] == "N10d"
    assert "Average retention: 92.50%" in snapshot["ai_summary_text"]
    export_payload = build_cohort_snapshot_export_payload(snapshot)
    assert export_payload["name"] == "Strong N10 snapshot"
    markdown = format_cohort_snapshot_markdown(snapshot)
    assert "# Cohort Snapshot: Strong N10 snapshot" in markdown
    assert "## AI Brief" in markdown

    delete_cohort_snapshot(snapshot_id)
    assert list_cohort_snapshots() == []


def test_cohort_records_prefer_backend_metrics_bridge_and_preserve_legacy_fields(tmp_path, monkeypatch):
    db_path = tmp_path / "cellscope.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    database.init_database()
    database.migrate_database()

    backend_db = tmp_path / "Cellscope 2.0" / "backend" / "cellscope2.db"
    _init_backend_metrics_db(
        backend_db,
        legacy_experiment_id=10,
        retention_pct=91.2,
        ce_pct=99.4,
        fade_pct_per_100=1.7,
        cycle_life_80=155,
    )

    with database.get_db_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, user_id, name, project_type) VALUES (1, 'admin', 'NMC Full Cells', 'Full Cell')"
        )
        payload = {
            "experiment_date": "2026-01-10",
            "cells": [{"cell_name": "FC5 i", "electrolyte": "LiPF6"}],
            "tracking": {"status": "Completed", "missing_cell_count": 0},
            "ontology": {"display_batch_name": "N10", "display_root_batch_name": "N10"},
        }
        conn.execute(
            """
            INSERT INTO cell_experiments (id, project_id, cell_name, electrolyte, data_json)
            VALUES (10, 1, 'FC5', 'LiPF6', ?)
            """,
            (json.dumps(payload),),
        )
        conn.execute(
            """
            INSERT INTO derived_experiment_metrics (experiment_id, source_signature, metrics_json)
            VALUES (?, ?, ?)
            """,
            (
                10,
                "sig-a",
                json.dumps(
                    {
                        "experiment_summary": {
                            "avg_retention_pct": 72.5,
                            "avg_coulombic_efficiency_pct": 98.1,
                            "avg_fade_rate_pct_per_100_cycles": 5.2,
                            "best_cycle_life_80": 120,
                            "avg_reversible_capacity_mAh_g": 201.5,
                        }
                    }
                ),
            ),
        )
        conn.commit()

    records = load_cohort_records()
    assert len(records) == 1
    assert records[0]["derived_metrics_cached"] is True
    assert records[0]["metrics_source"] == "backend+legacy"
    assert records[0]["avg_retention_pct"] == 91.2
    assert records[0]["avg_coulombic_efficiency_pct"] == 99.4
    assert records[0]["avg_fade_rate_pct_per_100_cycles"] == 1.7
    assert records[0]["best_cycle_life_80"] == 155.0
    assert records[0]["avg_reversible_capacity_mAh_g"] == 201.5


def test_cohort_records_fall_back_to_legacy_metrics_when_backend_metric_tables_are_missing(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "cellscope.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    database.init_database()
    database.migrate_database()

    backend_db = tmp_path / "Cellscope 2.0" / "backend" / "cellscope2.db"
    _init_backend_ontology_only_db(
        backend_db,
        legacy_experiment_id=10,
    )

    with database.get_db_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, user_id, name, project_type) VALUES (1, 'admin', 'NMC Full Cells', 'Full Cell')"
        )
        payload = {
            "experiment_date": "2026-01-10",
            "cells": [{"cell_name": "FC5 i", "electrolyte": "LiPF6"}],
            "tracking": {"status": "Completed", "missing_cell_count": 0},
            "ontology": {"display_batch_name": "N10", "display_root_batch_name": "N10"},
        }
        conn.execute(
            """
            INSERT INTO cell_experiments (id, project_id, cell_name, electrolyte, data_json)
            VALUES (10, 1, 'FC5', 'LiPF6', ?)
            """,
            (json.dumps(payload),),
        )
        conn.execute(
            """
            INSERT INTO derived_experiment_metrics (experiment_id, source_signature, metrics_json)
            VALUES (?, ?, ?)
            """,
            (
                10,
                "sig-a",
                json.dumps(
                    {
                        "experiment_summary": {
                            "avg_retention_pct": 87.5,
                            "avg_coulombic_efficiency_pct": 98.9,
                            "avg_fade_rate_pct_per_100_cycles": 2.4,
                            "best_cycle_life_80": 140,
                        }
                    }
                ),
            ),
        )
        conn.commit()

    records = load_cohort_records()
    assert len(records) == 1
    assert records[0]["derived_metrics_cached"] is True
    assert records[0]["metrics_source"] == "legacy"
    assert records[0]["avg_retention_pct"] == 87.5
    assert records[0]["avg_coulombic_efficiency_pct"] == 98.9
    assert records[0]["avg_fade_rate_pct_per_100_cycles"] == 2.4
    assert records[0]["best_cycle_life_80"] == 140.0
