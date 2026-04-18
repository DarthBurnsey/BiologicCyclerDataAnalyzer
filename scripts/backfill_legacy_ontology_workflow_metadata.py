#!/usr/bin/env python3
"""Backfill legacy CellScope experiment records with canonical ontology metadata."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ontology_workflow import LEGACY_DB_PATH, backfill_legacy_experiment_ontology_contexts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stamp legacy cell_experiments.data_json payloads with canonical ontology metadata."
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Write the ontology mappings into the legacy cellscope.db file.",
    )
    parser.add_argument(
        "--backup-dir",
        default="docs/reconciliation/backups",
        help="Directory to store the pre-update SQLite backup when --persist is used.",
    )
    args = parser.parse_args()

    backup_path = None
    if args.persist:
        backup_dir = Path(args.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"cellscope-pre-ontology-workflow-{date.today().isoformat()}.db"
        shutil.copy2(LEGACY_DB_PATH, backup_path)

    summary = backfill_legacy_experiment_ontology_contexts(persist=args.persist)
    payload = {
        **summary,
        "persisted": args.persist,
        "backup_path": str(backup_path.resolve()) if backup_path else None,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
