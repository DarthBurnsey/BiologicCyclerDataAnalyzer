"""Persisted experiment-level derived metrics for the legacy CellScope app."""

from __future__ import annotations

import hashlib
import json
import os
from io import StringIO
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from dashboard_analytics import calculate_fade_rate, calculate_retention_percent
from data_analysis import calculate_cell_summary
from database import get_db_connection, hydrate_data_json


def _ensure_metrics_table() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS derived_experiment_metrics (
                experiment_id INTEGER PRIMARY KEY,
                source_signature TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (experiment_id) REFERENCES cell_experiments (id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _load_json_dict(raw_value: Any) -> Dict[str, Any]:
    if not raw_value:
        return {}
    try:
        payload = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _disc_area_cm2(experiment_data: Dict[str, Any]) -> float:
    diameter_mm = _safe_float(experiment_data.get("disc_diameter_mm"))
    if not diameter_mm or diameter_mm <= 0:
        return 1.0
    radius_cm = diameter_mm / 20.0
    return float(np.pi * (radius_cm ** 2))


def _path_signature(path_value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path_value:
        return None
    if not os.path.exists(path_value):
        return {"path": path_value, "exists": False}
    stat = os.stat(path_value)
    return {
        "path": path_value,
        "exists": True,
        "size": stat.st_size,
        "mtime": round(stat.st_mtime, 6),
    }


def _build_source_signature(
    *,
    experiment_id: int,
    created_date: Optional[str],
    parquet_path: Optional[str],
    raw_data_json: Optional[str],
) -> str:
    payload = {
        "experiment_id": experiment_id,
        "created_date": created_date,
        "parquet": _path_signature(parquet_path),
        "raw_data_json": raw_data_json,
    }

    experiment_data = _load_json_dict(raw_data_json)
    cell_parquet_paths: List[Dict[str, Any]] = []
    for cell in experiment_data.get("cells", []):
        if not isinstance(cell, dict):
            continue
        signature = _path_signature(cell.get("parquet_path"))
        if signature:
            cell_parquet_paths.append(signature)
    if cell_parquet_paths:
        payload["cell_parquet_paths"] = cell_parquet_paths

    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _extract_last_cycle_index(df: pd.DataFrame) -> Optional[float]:
    if df.empty:
        return None
    cycle_series = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna()
    if cycle_series.empty:
        return None
    return float(cycle_series.iloc[-1])


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    valid = [float(value) for value in values if value is not None]
    if not valid:
        return None
    return float(sum(valid) / len(valid))


def _max(values: Iterable[Optional[float]]) -> Optional[float]:
    valid = [float(value) for value in values if value is not None]
    return max(valid) if valid else None


def _build_experiment_metric_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    hydrated_json = hydrate_data_json(row["raw_data_json"], row["parquet_path"], row["experiment_id"])
    experiment_data = _load_json_dict(hydrated_json)
    cells = experiment_data.get("cells", []) if isinstance(experiment_data.get("cells"), list) else []
    project_type = row.get("project_type") or "Full Cell"
    disc_area = _disc_area_cm2(experiment_data)
    ontology = experiment_data.get("ontology") if isinstance(experiment_data.get("ontology"), dict) else {}

    cell_metrics: List[Dict[str, Any]] = []
    for index, cell in enumerate(cells, start=1):
        if not isinstance(cell, dict):
            continue
        cell_name = (
            str(cell.get("test_number") or cell.get("cell_name") or f"{row['experiment_name']}::{index}")
        ).strip()
        cell_data_json = cell.get("data_json")
        if not cell_data_json:
            cell_metrics.append(
                {
                    "cell_name": cell_name,
                    "has_data": False,
                }
            )
            continue

        try:
            df = pd.read_json(StringIO(cell_data_json))
        except ValueError:
            cell_metrics.append(
                {
                    "cell_name": cell_name,
                    "has_data": False,
                }
            )
            continue

        if df.empty:
            cell_metrics.append(
                {
                    "cell_name": cell_name,
                    "has_data": False,
                }
            )
            continue

        summary = calculate_cell_summary(df, cell, disc_area, project_type)
        retention_pct = calculate_retention_percent(df)
        fade_rate_pct_per_100_cycles = calculate_fade_rate(df)
        cell_metrics.append(
            {
                "cell_name": cell_name,
                "has_data": True,
                "retention_pct": retention_pct,
                "fade_rate_pct_per_100_cycles": fade_rate_pct_per_100_cycles,
                "coulombic_efficiency_pct": summary.get("coulombic_efficiency"),
                "cycle_life_80": summary.get("cycle_life_80"),
                "first_discharge_mAh_g": summary.get("first_discharge"),
                "reversible_capacity_mAh_g": summary.get("reversible_capacity"),
                "areal_capacity_mAh_cm2": summary.get("areal_capacity"),
                "last_cycle_index": _extract_last_cycle_index(df),
                "cycle_point_count": int(len(df)),
            }
        )

    cells_with_data = [item for item in cell_metrics if item.get("has_data")]
    experiment_summary = {
        "experiment_id": row["experiment_id"],
        "experiment_name": row["experiment_name"],
        "project_id": row["project_id"],
        "project_name": row["project_name"],
        "project_type": project_type,
        "experiment_date": experiment_data.get("experiment_date"),
        "cell_count_total": len(cells),
        "cell_count_with_data": len(cells_with_data),
        "avg_retention_pct": _mean(item.get("retention_pct") for item in cells_with_data),
        "best_retention_pct": _max(item.get("retention_pct") for item in cells_with_data),
        "avg_coulombic_efficiency_pct": _mean(item.get("coulombic_efficiency_pct") for item in cells_with_data),
        "avg_fade_rate_pct_per_100_cycles": _mean(item.get("fade_rate_pct_per_100_cycles") for item in cells_with_data),
        "best_cycle_life_80": _max(item.get("cycle_life_80") for item in cells_with_data),
        "avg_first_discharge_mAh_g": _mean(item.get("first_discharge_mAh_g") for item in cells_with_data),
        "avg_reversible_capacity_mAh_g": _mean(item.get("reversible_capacity_mAh_g") for item in cells_with_data),
        "avg_areal_capacity_mAh_cm2": _mean(item.get("areal_capacity_mAh_cm2") for item in cells_with_data),
        "ontology_batch_name": ontology.get("display_batch_name") or ontology.get("batch_name"),
        "ontology_root_batch_name": ontology.get("display_root_batch_name") or ontology.get("root_batch_name"),
    }

    return {
        "experiment_summary": experiment_summary,
        "cell_metrics": cell_metrics,
    }


def _get_experiment_row(experiment_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        conn.row_factory = None
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                ce.id,
                ce.project_id,
                p.name,
                p.project_type,
                ce.cell_name,
                ce.created_date,
                ce.parquet_path,
                ce.data_json
            FROM cell_experiments ce
            JOIN projects p ON p.id = ce.project_id
            WHERE ce.id = ?
            """,
            (experiment_id,),
        )
        row = cursor.fetchone()
    if not row:
        return None
    return {
        "experiment_id": row[0],
        "project_id": row[1],
        "project_name": row[2],
        "project_type": row[3],
        "experiment_name": row[4],
        "created_date": row[5],
        "parquet_path": row[6],
        "raw_data_json": row[7],
    }


def get_or_refresh_experiment_derived_metrics(
    experiment_id: int,
    *,
    refresh: bool = False,
) -> Optional[Dict[str, Any]]:
    _ensure_metrics_table()
    row = _get_experiment_row(experiment_id)
    if row is None:
        return None

    source_signature = _build_source_signature(
        experiment_id=row["experiment_id"],
        created_date=row.get("created_date"),
        parquet_path=row.get("parquet_path"),
        raw_data_json=row.get("raw_data_json"),
    )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if not refresh:
            cursor.execute(
                """
                SELECT metrics_json, source_signature, computed_at
                FROM derived_experiment_metrics
                WHERE experiment_id = ?
                """,
                (experiment_id,),
            )
            cached = cursor.fetchone()
            if cached and cached[1] == source_signature:
                metrics_payload = _load_json_dict(cached[0])
                if metrics_payload:
                    metrics_payload["cache_hit"] = True
                    metrics_payload["computed_at"] = cached[2]
                    return metrics_payload

        metrics_payload = _json_safe(_build_experiment_metric_payload(row))
        cursor.execute(
            """
            INSERT INTO derived_experiment_metrics (experiment_id, source_signature, metrics_json)
            VALUES (?, ?, ?)
            ON CONFLICT(experiment_id) DO UPDATE SET
                source_signature = excluded.source_signature,
                metrics_json = excluded.metrics_json,
                computed_at = CURRENT_TIMESTAMP,
                updated_date = CURRENT_TIMESTAMP
            """,
            (
                experiment_id,
                source_signature,
                json.dumps(metrics_payload),
            ),
        )
        conn.commit()
        cursor.execute(
            "SELECT computed_at FROM derived_experiment_metrics WHERE experiment_id = ?",
            (experiment_id,),
        )
        computed_row = cursor.fetchone()

    metrics_payload["cache_hit"] = False
    metrics_payload["computed_at"] = computed_row[0] if computed_row else None
    return metrics_payload


def load_derived_metrics_map(
    experiment_ids: Iterable[int],
    *,
    refresh: bool = False,
) -> Dict[int, Dict[str, Any]]:
    payload: Dict[int, Dict[str, Any]] = {}
    for experiment_id in sorted({int(item) for item in experiment_ids if item is not None}):
        metrics = get_or_refresh_experiment_derived_metrics(experiment_id, refresh=refresh)
        if metrics:
            payload[experiment_id] = metrics
    return payload
