"""Bridge backend-native metric payloads into the legacy app's experiment views."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import database
from database import get_db_connection
from derived_metrics_service import load_derived_metrics_map


BASE_DIR = Path(__file__).resolve().parent
BACKEND_DB_PATH = BASE_DIR / "Cellscope 2.0" / "backend" / "cellscope2.db"
REQUIRED_BACKEND_METRIC_TABLES = (
    "ontology_cell_builds",
    "test_runs",
    "metric_runs",
    "metric_definitions",
    "run_metric_values",
    "cycle_metric_values",
)
logger = logging.getLogger(__name__)


def _normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_json_dict(raw_value: Any) -> Dict[str, Any]:
    if not raw_value:
        return {}
    try:
        payload = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    valid = [float(value) for value in values if value is not None]
    if not valid:
        return None
    return float(sum(valid) / len(valid))


def _max(values: Iterable[Optional[float]]) -> Optional[float]:
    valid = [float(value) for value in values if value is not None]
    return max(valid) if valid else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _resolve_backend_db_path() -> Path:
    legacy_db_path = Path(database.DATABASE_PATH)
    if not legacy_db_path.is_absolute():
        legacy_db_path = (BASE_DIR / legacy_db_path).resolve()
    return legacy_db_path.parent / "Cellscope 2.0" / "backend" / "cellscope2.db"


def _get_backend_connection() -> Optional[sqlite3.Connection]:
    backend_db_path = _resolve_backend_db_path()
    if not backend_db_path.exists():
        return None
    connection = sqlite3.connect(backend_db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _load_existing_table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()
    return {
        str(row["name"])
        for row in rows
        if row["name"]
    }


def _backend_missing_metric_tables(connection: sqlite3.Connection) -> list[str]:
    existing_tables = _load_existing_table_names(connection)
    return [
        table_name
        for table_name in REQUIRED_BACKEND_METRIC_TABLES
        if table_name not in existing_tables
    ]


def _load_cached_legacy_metrics_map(experiment_ids: Iterable[int]) -> Dict[int, Dict[str, Any]]:
    ids = sorted({int(item) for item in experiment_ids if item is not None})
    if not ids:
        return {}

    placeholders = ",".join("?" for _ in ids)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT experiment_id, metrics_json, computed_at
            FROM derived_experiment_metrics
            WHERE experiment_id IN ({placeholders})
            """,
            ids,
        )
        rows = cursor.fetchall()

    payload: Dict[int, Dict[str, Any]] = {}
    for experiment_id, metrics_json, computed_at in rows:
        metrics_payload = _load_json_dict(metrics_json)
        if not metrics_payload:
            continue
        metrics_payload["cache_hit"] = True
        metrics_payload["computed_at"] = computed_at
        metrics_payload["metrics_source"] = "legacy"
        payload[int(experiment_id)] = metrics_payload
    return payload


def _cycle_life_80_from_retention(retention_by_cycle: Dict[int, Optional[float]]) -> Optional[float]:
    if not retention_by_cycle:
        return None
    for cycle_index in sorted(retention_by_cycle):
        retention = _safe_float(retention_by_cycle.get(cycle_index))
        if retention is not None and retention <= 80.0:
            return float(cycle_index)
    return None


def _build_backend_experiment_payload(
    *,
    legacy_experiment_id: int,
    run_entries: list[Dict[str, Any]],
) -> Dict[str, Any]:
    cell_metrics: list[Dict[str, Any]] = []
    computed_at_values: list[str] = []

    for run_entry in run_entries:
        metric_values = run_entry["run_metric_values"]
        retention_by_cycle = run_entry["cycle_metric_values"].get("retention_pct", {})
        specific_discharge_by_cycle = run_entry["cycle_metric_values"].get(
            "specific_discharge_capacity_mah_g",
            {}
        )

        cycle_life_80 = _cycle_life_80_from_retention(retention_by_cycle)
        reversible_capacity = None
        if specific_discharge_by_cycle:
            candidate_cycles = [
                cycle_index
                for cycle_index, value in sorted(specific_discharge_by_cycle.items())
                if _safe_float(value) is not None and int(cycle_index) > 1
            ]
            if candidate_cycles:
                reversible_capacity = _safe_float(
                    specific_discharge_by_cycle.get(candidate_cycles[0])
                )

        cell_metrics.append(
            {
                "cell_name": run_entry.get("legacy_test_number")
                or run_entry.get("build_name")
                or f"Run {run_entry['test_run_id']}",
                "has_data": True,
                "retention_pct": _safe_float(metric_values.get("capacity_retention_pct")),
                "fade_rate_pct_per_100_cycles": _safe_float(
                    metric_values.get("fade_rate_pct_per_100_cycles")
                ),
                "coulombic_efficiency_pct": _safe_float(
                    metric_values.get("average_coulombic_efficiency_pct")
                ),
                "cycle_life_80": cycle_life_80,
                "reversible_capacity_mAh_g": reversible_capacity,
                "last_cycle_index": _safe_float(metric_values.get("last_cycle_index")),
                "latest_discharge_capacity_mah": _safe_float(
                    metric_values.get("latest_discharge_capacity_mah")
                ),
                "latest_charge_capacity_mah": _safe_float(
                    metric_values.get("latest_charge_capacity_mah")
                ),
                "latest_efficiency_pct": _safe_float(metric_values.get("latest_efficiency_pct")),
                "metric_run_id": run_entry["metric_run_id"],
                "test_run_id": run_entry["test_run_id"],
                "cell_build_id": run_entry["cell_build_id"],
            }
        )
        if run_entry.get("computed_at"):
            computed_at_values.append(str(run_entry["computed_at"]))

    experiment_summary = {
        "experiment_id": legacy_experiment_id,
        "cell_count_total": len(cell_metrics),
        "cell_count_with_data": len(cell_metrics),
        "avg_retention_pct": _mean(item.get("retention_pct") for item in cell_metrics),
        "best_retention_pct": _max(item.get("retention_pct") for item in cell_metrics),
        "avg_coulombic_efficiency_pct": _mean(
            item.get("coulombic_efficiency_pct") for item in cell_metrics
        ),
        "avg_fade_rate_pct_per_100_cycles": _mean(
            item.get("fade_rate_pct_per_100_cycles") for item in cell_metrics
        ),
        "best_cycle_life_80": _max(item.get("cycle_life_80") for item in cell_metrics),
        "avg_reversible_capacity_mAh_g": _mean(
            item.get("reversible_capacity_mAh_g") for item in cell_metrics
        ),
    }

    computed_at = max(computed_at_values) if computed_at_values else None
    return {
        "experiment_summary": experiment_summary,
        "cell_metrics": cell_metrics,
        "computed_at": computed_at,
        "cache_hit": True,
        "metrics_source": "backend",
        "backend_metrics": {
            "legacy_experiment_id": legacy_experiment_id,
            "run_count": len(run_entries),
            "metric_run_ids": [item["metric_run_id"] for item in run_entries],
            "cell_build_ids": sorted({int(item["cell_build_id"]) for item in run_entries}),
        },
    }


def load_backend_experiment_metrics_map(
    experiment_ids: Iterable[int],
) -> Dict[int, Dict[str, Any]]:
    ids = sorted({int(item) for item in experiment_ids if item is not None})
    if not ids:
        return {}

    connection = _get_backend_connection()
    if connection is None:
        return {}

    try:
        missing_tables = _backend_missing_metric_tables(connection)
        if missing_tables:
            logger.info(
                "Skipping backend metrics bridge for %s because the backend schema is missing tables: %s",
                _resolve_backend_db_path(),
                ", ".join(missing_tables),
            )
            return {}

        placeholders = ",".join("?" for _ in ids)
        build_rows = connection.execute(
            f"""
            SELECT id, legacy_experiment_id, build_name, legacy_test_number
            FROM ontology_cell_builds
            WHERE legacy_experiment_id IN ({placeholders})
            ORDER BY legacy_experiment_id ASC, id ASC
            """,
            ids,
        ).fetchall()
        if not build_rows:
            return {}

        build_rows_by_id = {int(row["id"]): dict(row) for row in build_rows}
        build_ids = sorted(build_rows_by_id)
        build_placeholders = ",".join("?" for _ in build_ids)

        run_rows = connection.execute(
            f"""
            SELECT
                tr.id AS test_run_id,
                tr.cell_build_id AS cell_build_id,
                mr.id AS metric_run_id,
                mr.finished_at AS computed_at
            FROM test_runs tr
            JOIN (
                SELECT test_run_id, MAX(id) AS metric_run_id
                FROM metric_runs
                WHERE UPPER(status) = 'SUCCEEDED'
                GROUP BY test_run_id
            ) latest ON latest.test_run_id = tr.id
            JOIN metric_runs mr ON mr.id = latest.metric_run_id
            WHERE tr.cell_build_id IN ({build_placeholders})
            ORDER BY tr.cell_build_id ASC, mr.id ASC
            """,
            build_ids,
        ).fetchall()
        if not run_rows:
            return {}

        metric_run_ids = [int(row["metric_run_id"]) for row in run_rows]
        metric_run_placeholders = ",".join("?" for _ in metric_run_ids)

        run_metric_rows = connection.execute(
            f"""
            SELECT
                rmv.metric_run_id,
                md.key AS metric_key,
                rmv.value_numeric,
                rmv.value_json
            FROM run_metric_values rmv
            JOIN metric_definitions md ON md.id = rmv.metric_definition_id
            WHERE rmv.metric_run_id IN ({metric_run_placeholders})
            ORDER BY rmv.metric_run_id ASC, md.key ASC
            """,
            metric_run_ids,
        ).fetchall()

        cycle_metric_rows = connection.execute(
            f"""
            SELECT
                cmv.metric_run_id,
                cmv.cycle_index,
                md.key AS metric_key,
                cmv.value_numeric
            FROM cycle_metric_values cmv
            JOIN metric_definitions md ON md.id = cmv.metric_definition_id
            WHERE cmv.metric_run_id IN ({metric_run_placeholders})
              AND md.key IN ('retention_pct', 'specific_discharge_capacity_mah_g')
            ORDER BY cmv.metric_run_id ASC, cmv.cycle_index ASC, md.key ASC
            """,
            metric_run_ids,
        ).fetchall()
    except sqlite3.OperationalError as exc:
        error_text = str(exc).lower()
        if "no such table" in error_text or "no such column" in error_text:
            logger.warning(
                "Skipping backend metrics bridge for %s because the backend schema is incomplete: %s",
                _resolve_backend_db_path(),
                exc,
            )
            return {}
        raise
    finally:
        connection.close()

    run_metric_map: Dict[int, Dict[str, Any]] = {}
    for row in run_metric_rows:
        metric_run_id = int(row["metric_run_id"])
        run_metric_map.setdefault(metric_run_id, {})
        if row["value_numeric"] is not None:
            run_metric_map[metric_run_id][row["metric_key"]] = float(row["value_numeric"])
        elif row["value_json"]:
            run_metric_map[metric_run_id][row["metric_key"]] = _load_json_dict(row["value_json"])
        else:
            run_metric_map[metric_run_id][row["metric_key"]] = None

    cycle_metric_map: Dict[int, Dict[str, Dict[int, Optional[float]]]] = {}
    for row in cycle_metric_rows:
        metric_run_id = int(row["metric_run_id"])
        metric_key = str(row["metric_key"])
        cycle_metric_map.setdefault(metric_run_id, {}).setdefault(metric_key, {})
        cycle_metric_map[metric_run_id][metric_key][int(row["cycle_index"])] = _safe_float(
            row["value_numeric"]
        )

    experiments: Dict[int, list[Dict[str, Any]]] = {}
    for row in run_rows:
        cell_build_id = int(row["cell_build_id"])
        build_row = build_rows_by_id.get(cell_build_id)
        if not build_row:
            continue
        legacy_experiment_id = build_row.get("legacy_experiment_id")
        if legacy_experiment_id is None:
            continue
        metric_run_id = int(row["metric_run_id"])
        experiments.setdefault(int(legacy_experiment_id), []).append(
            {
                "test_run_id": int(row["test_run_id"]),
                "cell_build_id": cell_build_id,
                "metric_run_id": metric_run_id,
                "computed_at": row["computed_at"],
                "build_name": build_row.get("build_name"),
                "legacy_test_number": build_row.get("legacy_test_number"),
                "run_metric_values": run_metric_map.get(metric_run_id, {}),
                "cycle_metric_values": cycle_metric_map.get(metric_run_id, {}),
            }
        )

    payload: Dict[int, Dict[str, Any]] = {}
    for legacy_experiment_id, run_entries in experiments.items():
        if not run_entries:
            continue
        payload[int(legacy_experiment_id)] = _build_backend_experiment_payload(
            legacy_experiment_id=int(legacy_experiment_id),
            run_entries=run_entries,
        )
    return payload


def _merge_metric_payloads(
    legacy_payload: Optional[Dict[str, Any]],
    backend_payload: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not legacy_payload and not backend_payload:
        return None
    if backend_payload and not legacy_payload:
        return _json_safe(backend_payload)
    if legacy_payload and not backend_payload:
        return _json_safe(legacy_payload)

    assert legacy_payload is not None
    assert backend_payload is not None

    legacy_summary = legacy_payload.get("experiment_summary") if isinstance(
        legacy_payload.get("experiment_summary"), dict
    ) else {}
    backend_summary = backend_payload.get("experiment_summary") if isinstance(
        backend_payload.get("experiment_summary"), dict
    ) else {}

    merged_summary = dict(legacy_summary)
    for key, value in backend_summary.items():
        if value is not None:
            merged_summary[key] = value

    merged_payload = dict(legacy_payload)
    merged_payload.update(
        {
            "experiment_summary": merged_summary,
            "cell_metrics": backend_payload.get("cell_metrics") or legacy_payload.get("cell_metrics") or [],
            "computed_at": backend_payload.get("computed_at") or legacy_payload.get("computed_at"),
            "cache_hit": True,
            "metrics_source": "backend+legacy",
            "backend_metrics": backend_payload.get("backend_metrics"),
        }
    )
    return _json_safe(merged_payload)


def load_preferred_experiment_metrics_map(
    experiment_ids: Iterable[int],
    *,
    refresh: bool = False,
    compute_missing_legacy: bool = False,
) -> Dict[int, Dict[str, Any]]:
    ids = sorted({int(item) for item in experiment_ids if item is not None})
    if not ids:
        return {}

    backend_map = load_backend_experiment_metrics_map(ids)
    cached_legacy_map = _load_cached_legacy_metrics_map(ids)

    legacy_fallback_ids = [
        experiment_id for experiment_id in ids if experiment_id not in backend_map
    ]
    if compute_missing_legacy and (legacy_fallback_ids or refresh):
        legacy_map = load_derived_metrics_map(legacy_fallback_ids or ids, refresh=refresh)
        for experiment_id, metrics_payload in legacy_map.items():
            metrics_payload["metrics_source"] = "legacy"
        cached_legacy_map.update(legacy_map)

    payload: Dict[int, Dict[str, Any]] = {}
    for experiment_id in ids:
        merged = _merge_metric_payloads(
            cached_legacy_map.get(experiment_id),
            backend_map.get(experiment_id),
        )
        if merged:
            payload[int(experiment_id)] = merged
    return payload
