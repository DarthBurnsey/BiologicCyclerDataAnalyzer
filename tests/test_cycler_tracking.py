from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import batch_builder_service
import cycler_tracking
import database


def _init_ontology_db(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE ontology_electrode_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_name TEXT NOT NULL UNIQUE,
                electrode_role TEXT NOT NULL,
                active_material_id INTEGER,
                process_run_id INTEGER,
                formulation_json TEXT,
                notes TEXT,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE ontology_lineage_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_type TEXT NOT NULL,
                parent_id INTEGER NOT NULL,
                child_type TEXT NOT NULL,
                child_id INTEGER NOT NULL,
                relationship_type TEXT NOT NULL,
                source TEXT,
                confidence REAL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        connection.execute(
            """
            INSERT INTO ontology_electrode_batches (
                id, batch_name, electrode_role, metadata_json
            ) VALUES (?, ?, ?, ?)
            """,
            (
                1,
                "N8",
                "CATHODE",
                json.dumps(
                    {
                        "default_legacy_project_id": 1,
                        "default_legacy_project_name": "NMC Half Cells",
                        "study_focus": "Binder screening",
                    }
                ),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _init_legacy_db(db_path: Path) -> None:
    database.DATABASE_PATH = str(db_path)
    database.init_database()
    database.migrate_database()
    with database.get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, user_id, name, project_type)
            VALUES (1, 'admin', 'NMC Half Cells', 'Cathode')
            """
        )
        conn.commit()


def _seed_legacy_experiment(*, experiment_id: int = 10) -> None:
    payload = {
        "experiment_date": "2026-03-20",
        "cells": [
            {
                "cell_name": "N8 i",
                "test_number": "N8 i",
                "loading": 14.2,
                "active_material": 92.0,
                "formation_cycles": 4,
                "electrolyte": "1M LiPF6 1:1:1",
                "substrate": "Aluminum",
                "separator": "25um PP",
                "formulation": [
                    {"Component": "NMC811", "Dry Mass Fraction (%)": 92.0},
                    {"Component": "PVDF HSV1810", "Dry Mass Fraction (%)": 4.0},
                    {"Component": "Hx-T", "Dry Mass Fraction (%)": 4.0},
                ],
                "cycler": "A",
                "channel": "1",
                "cycler_channel": "A1",
            }
        ],
        "ontology": {
            "source": "cellscope2_ontology",
            "mapping_basis": "batch_builder_selection",
            "batch_id": 1,
            "batch_name": "N8",
            "display_batch_name": "N8",
            "root_batch_id": 1,
            "root_batch_name": "N8",
            "display_root_batch_name": "N8",
        },
        "tracking": {
            "status": "Completed",
            "missing_cell_count": 0,
        },
    }
    with database.get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO cell_experiments (
                id, project_id, cell_name, electrolyte, substrate, separator, data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                1,
                "N8",
                "1M LiPF6 1:1:1",
                "Aluminum",
                "25um PP",
                json.dumps(payload),
            ),
        )
        conn.commit()


def _write_tracking_csv(csv_path: Path) -> None:
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Exp. #", "Date", "Cyclers", "Loading", "Cell Count", "Notes"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "Exp. #": "N8",
                "Date": "03/20/2026",
                "Cyclers": "A1",
                "Loading": "14.2 mg",
                "Cell Count": "1",
                "Notes": "Linked to N8 lineage batch",
            }
        )


def test_tracking_payload_surfaces_lineage_root_batches_without_tracking_sheet(tmp_path, monkeypatch):
    ontology_db = tmp_path / "cellscope2.db"
    legacy_db = tmp_path / "cellscope.db"
    _init_ontology_db(ontology_db)
    _init_legacy_db(legacy_db)

    monkeypatch.setattr(batch_builder_service, "ONTOLOGY_DB_PATH", ontology_db)
    monkeypatch.setattr(database, "DATABASE_PATH", str(legacy_db))

    payload = cycler_tracking.get_tracking_dashboard_payload(csv_path=tmp_path / "missing_tracking.csv")

    assert payload["available"] is False
    assert payload["reason"] == "missing_file"
    assert payload["lineage_root_batches"] == [
        {
            "batch_id": 1,
            "root_batch_name": "N8",
            "default_project_id": 1,
            "default_project_name": "NMC Half Cells",
            "study_focus": "Binder screening",
            "legacy_experiment_count": 0,
            "tracking_row_count": 0,
            "active_tracking_count": 0,
            "completed_tracking_count": 0,
            "status": "Ready for Cell Inputs",
            "can_open_in_cell_inputs": True,
        }
    ]


def test_tracking_payload_rolls_up_root_batch_tracking_coverage(tmp_path, monkeypatch):
    ontology_db = tmp_path / "cellscope2.db"
    legacy_db = tmp_path / "cellscope.db"
    tracking_csv = tmp_path / "Cleaned_Cycler_Tracking.csv"
    _init_ontology_db(ontology_db)
    _init_legacy_db(legacy_db)
    _seed_legacy_experiment()
    _write_tracking_csv(tracking_csv)

    monkeypatch.setattr(batch_builder_service, "ONTOLOGY_DB_PATH", ontology_db)
    monkeypatch.setattr(database, "DATABASE_PATH", str(legacy_db))

    payload = cycler_tracking.get_tracking_dashboard_payload(csv_path=tracking_csv)

    assert payload["available"] is True
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["ontology_root_batch_name"] == "N8"
    assert payload["lineage_root_batches"] == [
        {
            "batch_id": 1,
            "root_batch_name": "N8",
            "default_project_id": 1,
            "default_project_name": "NMC Half Cells",
            "study_focus": "Binder screening",
            "legacy_experiment_count": 1,
            "tracking_row_count": 1,
            "active_tracking_count": 0,
            "completed_tracking_count": 1,
            "status": "Tracked",
            "can_open_in_cell_inputs": True,
        }
    ]
