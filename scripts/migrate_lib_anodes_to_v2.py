"""Migrate LIB Anodes cycling data from CellScope v1 to v2.

Reads from cellscope.db (v1) and writes to Cellscope 2.0/backend/cellscope2.db (v2).
Creates: Project, Experiments, Cells, CyclerSource, TestRuns, CyclePoints.
Links TestRuns to existing ontology_cell_builds where names match.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
V1_DB = REPO_ROOT / "cellscope.db"
V2_DB = REPO_ROOT / "Cellscope 2.0" / "backend" / "cellscope2.db"
V1_PROJECT_ID = 4  # LIB Anodes in v1

NOW = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def load_v1_experiments(v1_conn: sqlite3.Connection) -> list[dict]:
    """Load all LIB Anodes experiments with their cell data from v1."""
    rows = v1_conn.execute(
        "SELECT id, cell_name, data_json, created_date FROM cell_experiments "
        "WHERE project_id = ? ORDER BY id",
        (V1_PROJECT_ID,),
    ).fetchall()

    experiments = []
    for row in rows:
        exp_id, cell_name, data_json_str, created_date = row
        data = json.loads(data_json_str)
        experiments.append({
            "v1_id": exp_id,
            "name": cell_name.strip(),
            "experiment_date": data.get("experiment_date"),
            "disc_diameter_mm": data.get("disc_diameter_mm"),
            "group_names": data.get("group_names"),
            "cells": data.get("cells", []),
            "created_date": created_date,
        })
    return experiments


def load_cell_dataframe(cell: dict) -> pd.DataFrame | None:
    """Load cycling dataframe from parquet or inline data_json."""
    parquet_path = cell.get("parquet_path")
    if parquet_path:
        full_path = REPO_ROOT / parquet_path
        if full_path.exists():
            return pd.read_parquet(full_path)

    inline = cell.get("data_json")
    if inline:
        if isinstance(inline, str):
            inline = json.loads(inline)
        if isinstance(inline, dict):
            return pd.DataFrame.from_dict(inline)
        if isinstance(inline, list):
            return pd.DataFrame(inline)

    return None


def build_cell_build_lookup(v2_conn: sqlite3.Connection) -> dict[str, int]:
    """Map build_name -> id for ontology_cell_builds."""
    rows = v2_conn.execute(
        "SELECT id, build_name FROM ontology_cell_builds"
    ).fetchall()
    return {name: id_ for id_, name in rows}


def create_project(v2_conn: sqlite3.Connection) -> int:
    """Create the LIB Anodes project in v2. Returns project id."""
    existing = v2_conn.execute(
        "SELECT id FROM projects WHERE name = ?", ("LIB Anodes",)
    ).fetchone()
    if existing:
        return existing[0]

    cur = v2_conn.execute(
        "INSERT INTO projects (name, description, project_type, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("LIB Anodes", "LIB Anode formulation development", "anode", NOW, NOW),
    )
    return cur.lastrowid


def create_experiment(
    v2_conn: sqlite3.Connection,
    project_id: int,
    exp: dict,
) -> int:
    """Create an experiment in v2. Returns experiment id."""
    cur = v2_conn.execute(
        "INSERT INTO experiments "
        "(project_id, name, experiment_date, disc_diameter_mm, group_names, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            project_id,
            exp["name"],
            exp.get("experiment_date"),
            exp.get("disc_diameter_mm"),
            json.dumps(exp.get("group_names")) if exp.get("group_names") else None,
            exp.get("created_date") or NOW,
            NOW,
        ),
    )
    return cur.lastrowid


def create_cell(
    v2_conn: sqlite3.Connection,
    experiment_id: int,
    cell: dict,
) -> int:
    """Create a cell in v2. Returns cell id."""
    cur = v2_conn.execute(
        "INSERT INTO cells "
        "(experiment_id, cell_name, file_name, loading, active_material_pct, "
        "formation_cycles, test_number, electrolyte, substrate, separator, "
        "formulation, group_assignment, excluded, porosity, "
        "cutoff_voltage_lower, cutoff_voltage_upper, parquet_path, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            experiment_id,
            cell.get("cell_name", ""),
            cell.get("file_name"),
            cell.get("loading"),
            cell.get("active_material"),
            cell.get("formation_cycles", 3),
            cell.get("test_number"),
            cell.get("electrolyte"),
            cell.get("substrate"),
            cell.get("separator"),
            json.dumps(cell.get("formulation")) if cell.get("formulation") else None,
            cell.get("group_assignment"),
            0,  # not excluded
            cell.get("porosity"),
            cell.get("cutoff_voltage_lower"),
            cell.get("cutoff_voltage_upper"),
            cell.get("parquet_path"),
            NOW,
        ),
    )
    return cur.lastrowid


def create_cycler_source(v2_conn: sqlite3.Connection) -> int:
    """Create a synthetic cycler source for the legacy import."""
    existing = v2_conn.execute(
        "SELECT id FROM cycler_sources WHERE name = ?",
        ("Legacy v1 Import - LIB Anodes",),
    ).fetchone()
    if existing:
        return existing[0]

    cur = v2_conn.execute(
        "INSERT INTO cycler_sources "
        "(name, vendor, export_path, parser_type, poll_interval_seconds, "
        "stable_window_seconds, timezone, file_glob, enabled, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "Legacy v1 Import - LIB Anodes",
            "biologic",
            str(REPO_ROOT / "data" / "experiments"),
            "auto",
            0,
            0,
            "America/Chicago",
            "*",
            0,  # disabled — historical only
            NOW,
            NOW,
        ),
    )
    return cur.lastrowid


def as_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def create_test_run_and_points(
    v2_conn: sqlite3.Connection,
    source_id: int,
    cell_id: int,
    cell_build_id: int | None,
    project_id: int,
    experiment_id: int,
    experiment_name: str,
    cell: dict,
    df: pd.DataFrame,
) -> int:
    """Create a TestRun and its CyclePoints. Returns run id."""
    cell_name = cell.get("cell_name", "unknown")
    file_name = cell.get("file_name") or cell.get("parquet_path") or "legacy_import"
    run_key = f"legacy-v1-lib-anodes-{experiment_name}-{cell_name}"

    # Compute summary stats from dataframe
    last_cycle = as_int(df.iloc[-1, 0]) if not df.empty else None

    qdis_col = "Q discharge (mA.h)"
    qchg_col = "Q charge (mA.h)"
    eff_col = "Efficiency (-)"
    qdis_specific_col = "Q Dis (mAh/g)"

    latest_charge = as_float(df[qchg_col].iloc[-1]) if qchg_col in df.columns and not df.empty else None
    latest_discharge = as_float(df[qdis_col].iloc[-1]) if qdis_col in df.columns and not df.empty else None
    latest_efficiency = as_float(df[eff_col].iloc[-1]) if eff_col in df.columns and not df.empty else None

    # Capacity retention
    capacity_retention = None
    if qdis_specific_col in df.columns:
        qdis = pd.to_numeric(df[qdis_specific_col], errors="coerce").dropna()
        formation = cell.get("formation_cycles", 3) or 3
        if len(qdis) > formation:
            baseline = qdis.iloc[formation]
        elif not qdis.empty:
            baseline = qdis.iloc[0]
        else:
            baseline = None
        if baseline and baseline > 0 and not qdis.empty:
            capacity_retention = float((qdis.iloc[-1] / baseline) * 100)

    cur = v2_conn.execute(
        "INSERT INTO test_runs "
        "(source_id, project_id, experiment_id, cell_id, cell_build_id, "
        "run_key, source_file_path, parser_type, status, "
        "last_cycle_index, latest_charge_capacity_mah, latest_discharge_capacity_mah, "
        "latest_efficiency, capacity_retention_pct, "
        "metadata_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            source_id,
            project_id,
            experiment_id,
            cell_id,
            cell_build_id,
            run_key,
            file_name,
            "biologic_csv",
            "completed",
            last_cycle,
            latest_charge,
            latest_discharge,
            latest_efficiency,
            capacity_retention,
            json.dumps({
                "import_source": "cellscope_v1",
                "v1_cell_name": cell_name,
                "loading": cell.get("loading"),
                "active_material": cell.get("active_material"),
                "formation_cycles": cell.get("formation_cycles"),
            }),
            NOW,
            NOW,
        ),
    )
    run_id = cur.lastrowid

    # Insert cycle points
    for _, row in df.iterrows():
        cycle_index = as_int(row.iloc[0])
        if cycle_index is None:
            continue

        payload = {}
        for col in df.columns:
            val = row[col]
            if val is None:
                payload[col] = None
            elif isinstance(val, float) and pd.isna(val):
                payload[col] = None
            elif isinstance(val, (str, int, float, bool)):
                payload[col] = val
            elif isinstance(val, pd.Timestamp):
                payload[col] = val.isoformat()
            else:
                payload[col] = str(val)

        v2_conn.execute(
            "INSERT INTO cycle_points "
            "(run_id, cycle_index, charge_capacity_mah, discharge_capacity_mah, "
            "specific_charge_capacity_mah_g, specific_discharge_capacity_mah_g, "
            "efficiency, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                cycle_index,
                as_float(row.get(qchg_col)),
                as_float(row.get(qdis_col)),
                as_float(row.get("Q Chg (mAh/g)")),
                as_float(row.get("Q Dis (mAh/g)")),
                as_float(row.get(eff_col)),
                json.dumps(payload),
                NOW,
            ),
        )

    return run_id


def main():
    if not V1_DB.exists():
        print(f"ERROR: v1 database not found at {V1_DB}")
        sys.exit(1)
    if not V2_DB.exists():
        print(f"ERROR: v2 database not found at {V2_DB}")
        sys.exit(1)

    v1_conn = sqlite3.connect(str(V1_DB))
    v2_conn = sqlite3.connect(str(V2_DB))
    v2_conn.execute("PRAGMA foreign_keys = ON")

    try:
        experiments = load_v1_experiments(v1_conn)
        print(f"Found {len(experiments)} LIB Anodes experiments in v1")

        cell_build_lookup = build_cell_build_lookup(v2_conn)
        print(f"Found {len(cell_build_lookup)} ontology cell builds in v2")

        project_id = create_project(v2_conn)
        print(f"Project 'LIB Anodes' -> id={project_id}")

        source_id = create_cycler_source(v2_conn)
        print(f"CyclerSource 'Legacy v1 Import' -> id={source_id}")

        total_cells = 0
        total_runs = 0
        total_points = 0
        skipped_no_data = 0

        for exp in experiments:
            experiment_id = create_experiment(v2_conn, project_id, exp)
            print(f"\n  Experiment '{exp['name']}' -> id={experiment_id} ({len(exp['cells'])} cells)")

            for cell in exp["cells"]:
                cell_name = cell.get("cell_name", "unknown")
                cell_id = create_cell(v2_conn, experiment_id, cell)
                total_cells += 1

                df = load_cell_dataframe(cell)
                if df is None or df.empty:
                    print(f"    Cell '{cell_name}' -> id={cell_id} (NO DATA - skipped)")
                    skipped_no_data += 1
                    continue

                cell_build_id = cell_build_lookup.get(cell_name)

                run_id = create_test_run_and_points(
                    v2_conn,
                    source_id=source_id,
                    cell_id=cell_id,
                    cell_build_id=cell_build_id,
                    project_id=project_id,
                    experiment_id=experiment_id,
                    experiment_name=exp["name"],
                    cell=cell,
                    df=df,
                )
                total_runs += 1
                n_points = len(df)
                total_points += n_points
                build_tag = f" (build={cell_build_id})" if cell_build_id else ""
                print(f"    Cell '{cell_name}' -> id={cell_id}, run={run_id}, {n_points} cycles{build_tag}")

        v2_conn.commit()

        print(f"\n{'='*60}")
        print(f"Migration complete!")
        print(f"  Project:      1 (LIB Anodes)")
        print(f"  Experiments:  {len(experiments)}")
        print(f"  Cells:        {total_cells}")
        print(f"  TestRuns:     {total_runs}")
        print(f"  CyclePoints:  {total_points}")
        print(f"  Skipped:      {skipped_no_data} cells (no data)")
        print(f"{'='*60}")

    except Exception as e:
        v2_conn.rollback()
        print(f"\nERROR: Migration failed, rolled back: {e}")
        raise
    finally:
        v1_conn.close()
        v2_conn.close()


if __name__ == "__main__":
    main()
