from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import batch_builder_service
from batch_builder_service import (
    build_batch_cell_inputs_template,
    build_experiment_additional_data_from_template,
    create_batch_record,
    list_batches,
    list_materials,
    update_material_record,
)


def _init_ontology_db(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE ontology_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                manufacturer TEXT,
                description TEXT,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE ontology_protocol_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                protocol_type TEXT NOT NULL,
                description TEXT,
                step_definition_json TEXT,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE ontology_operators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                team TEXT,
                email TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE ontology_equipment_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                asset_type TEXT NOT NULL,
                vendor TEXT,
                model TEXT,
                serial_number TEXT,
                location TEXT,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE ontology_process_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                process_type TEXT NOT NULL,
                protocol_version_id INTEGER,
                operator_id INTEGER,
                equipment_asset_id INTEGER,
                started_at TEXT,
                completed_at TEXT,
                settings_json TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(parent_type, parent_id, child_type, child_id, relationship_type)
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def _init_legacy_db(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY,
                user_id TEXT DEFAULT 'admin',
                name TEXT NOT NULL,
                description TEXT,
                project_type TEXT,
                created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                last_modified TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        connection.execute(
            """
            INSERT INTO projects (id, name, description, project_type)
            VALUES (1, 'NMC Half Cells', 'Cathode development', 'Cathode')
            """
        )
        connection.commit()
    finally:
        connection.close()


def test_create_root_batch_and_build_template(tmp_path, monkeypatch):
    ontology_db = tmp_path / "cellscope2.db"
    legacy_db = tmp_path / "cellscope.db"
    _init_ontology_db(ontology_db)
    _init_legacy_db(legacy_db)

    monkeypatch.setattr(batch_builder_service, "ONTOLOGY_DB_PATH", ontology_db)
    monkeypatch.setattr(batch_builder_service, "LEGACY_DB_PATH", legacy_db)

    created = create_batch_record(
        batch_name="N17",
        electrode_role="cathode",
        created_at=date(2026, 3, 20),
        formulation_components=[
            {
                "Component": "NMC811",
                "Category": "cathode_active",
                "Dry Mass Fraction (%)": 92.0,
                "Manufacturer": "BASF",
            },
            {
                "Component": "Hx-T",
                "Category": "conductive_additive",
                "Dry Mass Fraction (%)": 4.0,
                "Manufacturer": "Hexegen",
            },
            {
                "Component": "PVDF HSV1810",
                "Category": "binder",
                "Dry Mass Fraction (%)": 4.0,
                "Manufacturer": "Arkema",
            },
        ],
        preferred_experiment_name="N17",
        target_project_id=1,
        target_project_name="NMC Half Cells",
        study_focus="Binder and conductive additive study",
        default_loading_mg=13.2,
        solids_content_pct=96.0,
        pressed_thickness_um=82.5,
        electrolyte_hint="1M LiPF6 1:1:1",
        separator_hint="25um PP",
        substrate_hint="Aluminum",
        process_name="N17 slurry build",
        process_type="slurry",
        process_settings={"mix_rpm": 1500},
    )

    assert created["batch_name"] == "N17"
    assert created["metadata_json"]["active_material_source"] == "BASF"
    assert created["metadata_json"]["default_legacy_project_id"] == 1
    assert created["metadata_json"]["authoring_mode"] == "root"

    materials = list_materials()
    assert {row["name"] for row in materials} == {"NMC811", "Hx-T", "PVDF HSV1810"}

    batches = list_batches(roots_only=True)
    assert [row["batch_name"] for row in batches] == ["N17"]

    template = build_batch_cell_inputs_template(batch_id=created["id"])
    assert template is not None
    assert template["project_id"] == 1
    assert template["root_batch_name"] == "N17"
    assert template["cell_inputs_defaults"]["loading_mg"] == 13.2
    assert template["cell_inputs_defaults"]["active_material_pct"] == 92.0
    assert template["ontology_context"]["display_root_batch_name"] == "N17"

    additional_data = build_experiment_additional_data_from_template(template)
    assert additional_data["ontology"]["batch_name"] == "N17"
    assert additional_data["batch_builder"]["root_batch_name"] == "N17"
    assert additional_data["default_cell_values"]["formulation"][0]["Component"] == "NMC811"


def test_create_child_branch_inherits_parent_lineage(tmp_path, monkeypatch):
    ontology_db = tmp_path / "cellscope2.db"
    legacy_db = tmp_path / "cellscope.db"
    _init_ontology_db(ontology_db)
    _init_legacy_db(legacy_db)

    monkeypatch.setattr(batch_builder_service, "ONTOLOGY_DB_PATH", ontology_db)
    monkeypatch.setattr(batch_builder_service, "LEGACY_DB_PATH", legacy_db)

    parent = create_batch_record(
        batch_name="N17",
        electrode_role="cathode",
        created_at=date(2026, 3, 20),
        formulation_components=[
            {
                "Component": "NMC811",
                "Category": "cathode_active",
                "Dry Mass Fraction (%)": 92.0,
                "Manufacturer": "BASF",
            },
            {
                "Component": "Hx-e",
                "Category": "conductive_additive",
                "Dry Mass Fraction (%)": 4.0,
                "Manufacturer": "Hexegen",
            },
            {
                "Component": "PVDF HSV1810",
                "Category": "binder",
                "Dry Mass Fraction (%)": 4.0,
                "Manufacturer": "Arkema",
            },
        ],
        preferred_experiment_name="N17",
        target_project_id=1,
        target_project_name="NMC Half Cells",
        process_name="N17 base build",
        process_type="coating",
    )

    child = create_batch_record(
        batch_name="N17a",
        electrode_role="cathode",
        created_at=date(2026, 3, 21),
        parent_batch_name="N17",
        preferred_experiment_name="N17a",
        target_project_id=1,
        target_project_name="NMC Half Cells",
        study_focus="Electrolyte screening",
        electrolyte_hint="1M LiFSI 3:7 + 10% FEC",
        inherit_parent_process=True,
    )

    assert child["metadata_json"]["parent_batch_name"] == "N17"
    assert child["metadata_json"]["authoring_mode"] == "branch"
    assert child["process_run_id"] == parent["process_run_id"]

    all_batches = list_batches()
    assert {row["batch_name"] for row in all_batches} == {"N17", "N17a"}
    assert [row["batch_name"] for row in list_batches(roots_only=True)] == ["N17"]

    child_template = build_batch_cell_inputs_template(batch_id=child["id"])
    assert child_template is not None
    assert child_template["batch_name"] == "N17a"
    assert child_template["root_batch_name"] == "N17"
    assert child_template["cell_inputs_defaults"]["electrolyte"] == "1M LiFSI 3:7 + 10% FEC"
    assert child_template["ontology_context"]["display_batch_name"] == "N17a"
    assert child_template["ontology_context"]["display_root_batch_name"] == "N17"

    connection = sqlite3.connect(ontology_db)
    try:
        branch_edges = connection.execute(
            """
            SELECT COUNT(*)
            FROM ontology_lineage_edges
            WHERE parent_type = 'ELECTRODE_BATCH'
              AND child_type = 'ELECTRODE_BATCH'
              AND relationship_type = 'branches_to'
            """
        ).fetchone()[0]
        formulation_edges = connection.execute(
            """
            SELECT COUNT(*)
            FROM ontology_lineage_edges
            WHERE parent_type = 'MATERIAL'
              AND child_type = 'ELECTRODE_BATCH'
              AND relationship_type = 'formulates_into'
              AND child_id = ?
            """,
            (child["id"],),
        ).fetchone()[0]
    finally:
        connection.close()

    assert branch_edges == 1
    assert formulation_edges == 3


def test_update_material_record_persists_manufacturer_and_description(tmp_path, monkeypatch):
    ontology_db = tmp_path / "cellscope2.db"
    legacy_db = tmp_path / "cellscope.db"
    _init_ontology_db(ontology_db)
    _init_legacy_db(legacy_db)

    monkeypatch.setattr(batch_builder_service, "ONTOLOGY_DB_PATH", ontology_db)
    monkeypatch.setattr(batch_builder_service, "LEGACY_DB_PATH", legacy_db)

    create_batch_record(
        batch_name="N18",
        electrode_role="cathode",
        created_at=date(2026, 3, 20),
        formulation_components=[
            {
                "Component": "NMC811",
                "Category": "cathode_active",
                "Dry Mass Fraction (%)": 92.0,
            },
            {
                "Component": "Hx-e",
                "Category": "conductive_additive",
                "Dry Mass Fraction (%)": 4.0,
            },
            {
                "Component": "PVDF HSV1810",
                "Category": "binder",
                "Dry Mass Fraction (%)": 4.0,
            },
        ],
        preferred_experiment_name="N18",
        target_project_id=1,
        target_project_name="NMC Half Cells",
    )

    updated = update_material_record(
        name="NMC811",
        manufacturer="BASF",
        description="Layered NMC811 cathode active material.",
    )
    assert updated["manufacturer"] == "BASF"
    assert updated["description"] == "Layered NMC811 cathode active material."

    materials = {row["name"]: row for row in list_materials()}
    assert materials["NMC811"]["manufacturer"] == "BASF"
    assert materials["NMC811"]["description"] == "Layered NMC811 cathode active material."
