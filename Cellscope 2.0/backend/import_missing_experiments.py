"""Import missing NMC Half Cells experiments from CellScope 1.0 into 2.0 DB.

The initial migration missed 6 experiments (IDs 83-86, 93-94 in v1.0).
This script imports them into the existing NMC Half Cells project (project_id=2).
"""

import json
import sqlite3
import sys
from pathlib import Path

LEGACY_DB = Path(__file__).resolve().parents[2] / "cellscope.db"
TARGET_DB = Path(__file__).resolve().parent / "cellscope2.db"

# v1.0 experiment IDs that are missing from v2.0
MISSING_IDS = [83, 84, 85, 86, 93, 94]

# v2.0 project_id for "NMC Half Cells"
TARGET_PROJECT_ID = 2


def safe_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def migrate():
    if not LEGACY_DB.exists():
        print(f"Legacy DB not found: {LEGACY_DB}")
        sys.exit(1)
    if not TARGET_DB.exists():
        print(f"Target DB not found: {TARGET_DB}")
        sys.exit(1)

    legacy = sqlite3.connect(str(LEGACY_DB))
    legacy.row_factory = sqlite3.Row
    target = sqlite3.connect(str(TARGET_DB))

    placeholders = ",".join("?" * len(MISSING_IDS))
    rows = legacy.execute(
        f"SELECT * FROM cell_experiments WHERE id IN ({placeholders})",
        MISSING_IDS,
    ).fetchall()

    print(f"Found {len(rows)} legacy experiments to import.")

    imported_experiments = 0
    imported_cells = 0

    for row in rows:
        data = json.loads(row["data_json"]) if row["data_json"] else {}
        cells = data.get("cells", [])
        experiment_name = row["cell_name"]

        # Check if already imported (idempotent)
        existing = target.execute(
            "SELECT id FROM experiments WHERE project_id = ? AND name = ?",
            (TARGET_PROJECT_ID, experiment_name),
        ).fetchone()
        if existing:
            print(f"  Skipping '{experiment_name}' — already exists (id={existing[0]})")
            continue

        # Insert experiment
        group_names = data.get("group_names")
        cursor = target.execute(
            """INSERT INTO experiments
               (project_id, name, experiment_date, disc_diameter_mm,
                solids_content, pressed_thickness, notes, group_names,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (
                TARGET_PROJECT_ID,
                experiment_name,
                data.get("experiment_date"),
                safe_float(data.get("disc_diameter_mm")),
                safe_float(row["solids_content"]),
                safe_float(row["pressed_thickness"]),
                row["experiment_notes"],
                json.dumps(group_names) if group_names else None,
            ),
        )
        experiment_id = cursor.lastrowid
        imported_experiments += 1
        print(f"  Created experiment '{experiment_name}' (id={experiment_id})")

        # Insert cells
        if not cells:
            # Flat row — single cell
            cells = [dict(row)]

        for cell in cells:
            cell_name = cell.get("cell_name") or cell.get("name") or experiment_name
            cell_data_json = cell.get("data_json")
            if cell_data_json and isinstance(cell_data_json, str):
                cell_data_json = json.loads(cell_data_json)
            elif cell_data_json is None:
                cell_data_json = None

            formulation = cell.get("formulation")
            if formulation and isinstance(formulation, str):
                try:
                    formulation = json.loads(formulation)
                except json.JSONDecodeError:
                    pass

            target.execute(
                """INSERT INTO cells
                   (experiment_id, cell_name, file_name, loading,
                    active_material_pct, formation_cycles, test_number,
                    electrolyte, substrate, separator, formulation,
                    group_assignment, excluded, porosity,
                    cutoff_voltage_lower, cutoff_voltage_upper,
                    data_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    experiment_id,
                    cell_name,
                    cell.get("file_name"),
                    safe_float(cell.get("loading") or row["loading"]),
                    safe_float(cell.get("active_material_pct") or cell.get("active_material") or row["active_material"]),
                    cell.get("formation_cycles") or row["formation_cycles"] or 4,
                    cell.get("test_number") or row["test_number"],
                    cell.get("electrolyte") or row["electrolyte"],
                    cell.get("substrate") or row["substrate"],
                    cell.get("separator") or row["separator"],
                    json.dumps(formulation) if formulation else None,
                    cell.get("group_assignment") or row["group_assignment"],
                    1 if cell.get("excluded") else 0,
                    safe_float(cell.get("porosity") or row["porosity"]),
                    safe_float(cell.get("cutoff_voltage_lower")),
                    safe_float(cell.get("cutoff_voltage_upper")),
                    json.dumps(cell_data_json) if cell_data_json else None,
                ),
            )
            imported_cells += 1

    target.commit()
    target.close()
    legacy.close()

    print(f"\nDone. Imported {imported_experiments} experiments and {imported_cells} cells.")


if __name__ == "__main__":
    migrate()
