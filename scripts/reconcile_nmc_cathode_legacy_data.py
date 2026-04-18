#!/usr/bin/env python3
"""Apply user-confirmed fixes to legacy NMC cathode experiment metadata."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "cellscope.db"

ELECTROLYTE_PATCHES = {
    "N1b": "1M LiPF6 (1:1:1)",
    "N2a": "1M LiPF6 (1:1:1)",
    "N2a - repaired": "1M LiPF6 (1:1:1)",
    "N10d": "1M LiTFSI + 10% FEC",
}

FORMULATION_COMPONENT_RENAMES = {
    "CNTs": "MWCNTs",
}


def _load_json(value: Any) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _patch_component_names(components: Iterable[Dict[str, Any]]) -> Tuple[list[Dict[str, Any]], int]:
    patched: list[Dict[str, Any]] = []
    changes = 0
    for component in components:
        if not isinstance(component, dict):
            patched.append(component)
            continue
        updated = dict(component)
        current_name = updated.get("Component")
        replacement = FORMULATION_COMPONENT_RENAMES.get(current_name)
        if replacement and replacement != current_name:
            updated["Component"] = replacement
            changes += 1
        patched.append(updated)
    return patched, changes


def _patch_row(row: sqlite3.Row) -> Tuple[Dict[str, Any], Dict[str, int]]:
    updates: Dict[str, Any] = {}
    counts = {
        "row_electrolyte_updates": 0,
        "cell_electrolyte_updates": 0,
        "row_formulation_updates": 0,
        "cell_formulation_updates": 0,
    }

    target_electrolyte = ELECTROLYTE_PATCHES.get(row["cell_name"])
    if target_electrolyte and row["electrolyte"] != target_electrolyte:
        updates["electrolyte"] = target_electrolyte
        counts["row_electrolyte_updates"] += 1

    formulation = _load_json(row["formulation_json"])
    if isinstance(formulation, list):
        patched_formulation, formulation_changes = _patch_component_names(formulation)
        if formulation_changes:
            updates["formulation_json"] = _dump_json(patched_formulation)
            counts["row_formulation_updates"] += formulation_changes

    data_json = _load_json(row["data_json"])
    if isinstance(data_json, dict):
        patched_data = dict(data_json)
        cells = patched_data.get("cells")
        data_changed = False
        if isinstance(cells, list):
            patched_cells = []
            for cell in cells:
                if not isinstance(cell, dict):
                    patched_cells.append(cell)
                    continue

                patched_cell = dict(cell)
                if target_electrolyte and patched_cell.get("electrolyte") != target_electrolyte:
                    patched_cell["electrolyte"] = target_electrolyte
                    counts["cell_electrolyte_updates"] += 1
                    data_changed = True

                cell_formulation = patched_cell.get("formulation")
                if isinstance(cell_formulation, list):
                    patched_cell_formulation, cell_formulation_changes = _patch_component_names(cell_formulation)
                    if cell_formulation_changes:
                        patched_cell["formulation"] = patched_cell_formulation
                        counts["cell_formulation_updates"] += cell_formulation_changes
                        data_changed = True

                patched_cells.append(patched_cell)

            if data_changed:
                patched_data["cells"] = patched_cells
                updates["data_json"] = _dump_json(patched_data)

    return updates, counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to the legacy CellScope SQLite database.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the updates without writing them to the database.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    totals = {
        "rows_touched": 0,
        "row_electrolyte_updates": 0,
        "cell_electrolyte_updates": 0,
        "row_formulation_updates": 0,
        "cell_formulation_updates": 0,
    }
    changed_rows = []

    try:
        rows = conn.execute(
            """
            SELECT id, cell_name, electrolyte, formulation_json, data_json
            FROM cell_experiments
            WHERE cell_name IN ('N1b', 'N2a', 'N2a - repaired', 'N5a', 'N5g', 'N10d')
            ORDER BY id
            """
        ).fetchall()

        for row in rows:
            updates, counts = _patch_row(row)
            if not updates:
                continue

            totals["rows_touched"] += 1
            for key, value in counts.items():
                totals[key] += value

            changed_rows.append(
                {
                    "id": row["id"],
                    "cell_name": row["cell_name"],
                    "updated_fields": sorted(updates.keys()),
                }
            )

            if args.dry_run:
                continue

            assignments = ", ".join(f"{field} = ?" for field in updates)
            values = [updates[field] for field in updates]
            values.append(row["id"])
            conn.execute(
                f"UPDATE cell_experiments SET {assignments} WHERE id = ?",
                values,
            )

        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    finally:
        conn.close()

    print(
        json.dumps(
            {
                "database": str(db_path),
                "dry_run": args.dry_run,
                "totals": totals,
                "changed_rows": changed_rows,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
