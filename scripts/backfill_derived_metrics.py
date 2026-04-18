#!/usr/bin/env python3
"""Backfill persisted derived experiment metrics in the legacy CellScope database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from derived_metrics_service import load_derived_metrics_map


def _parse_ids(raw_value: str | None) -> List[int]:
    if not raw_value:
        return []
    return [int(item.strip()) for item in raw_value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--experiment-ids",
        default=None,
        help="Optional comma-separated legacy experiment IDs to refresh. Defaults to all experiments.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force recomputation even when the cached source signature matches.",
    )
    args = parser.parse_args()

    if args.experiment_ids:
        experiment_ids = _parse_ids(args.experiment_ids)
    else:
        import database

        with database.get_db_connection() as conn:
            experiment_ids = [row[0] for row in conn.execute("SELECT id FROM cell_experiments ORDER BY id ASC").fetchall()]

    metrics_map = load_derived_metrics_map(experiment_ids, refresh=args.refresh)
    print(
        json.dumps(
            {
                "experiment_count": len(metrics_map),
                "cache_hits": sum(1 for payload in metrics_map.values() if payload.get("cache_hit")),
                "computed": sum(1 for payload in metrics_map.values() if not payload.get("cache_hit")),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
