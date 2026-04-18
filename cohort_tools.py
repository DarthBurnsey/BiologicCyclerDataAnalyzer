"""Utilities for ontology-backed experiment cohorts in the legacy CellScope app."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from backend_metrics_bridge import load_preferred_experiment_metrics_map
from database import get_db_connection
from ontology_workflow import normalize_ontology_context


def _ensure_saved_cohort_table() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_cohorts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                filters_json TEXT NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def _ensure_cohort_snapshot_tables() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cohort_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cohort_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                filters_json TEXT NOT NULL,
                experiment_ids_json TEXT NOT NULL,
                membership_signature TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                root_batch_summary_json TEXT NOT NULL,
                ai_summary_text TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cohort_id) REFERENCES saved_cohorts (id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cohort_snapshot_members (
                snapshot_id INTEGER NOT NULL,
                experiment_id INTEGER NOT NULL,
                member_json TEXT NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (snapshot_id, experiment_id),
                FOREIGN KEY (snapshot_id) REFERENCES cohort_snapshots (id) ON DELETE CASCADE,
                FOREIGN KEY (experiment_id) REFERENCES cell_experiments (id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def _ensure_derived_metrics_table() -> None:
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


def _load_json_dict(raw_value: Any) -> Dict[str, Any]:
    if not raw_value:
        return {}
    try:
        payload = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_optional_float(value: Any) -> Optional[float]:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _mean(values: List[Optional[float]]) -> Optional[float]:
    valid = [float(value) for value in values if value is not None]
    if not valid:
        return None
    return float(sum(valid) / len(valid))


def _max(values: List[Optional[float]]) -> Optional[float]:
    valid = [float(value) for value in values if value is not None]
    return max(valid) if valid else None


def normalize_cohort_filters(raw_filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    filters = dict(raw_filters or {})
    normalized = {
        "project_ids": sorted({int(item) for item in filters.get("project_ids", []) if item is not None}),
        "ontology_root_batch_names": sorted({_normalize_text(item) for item in filters.get("ontology_root_batch_names", []) if _normalize_text(item)}),
        "ontology_batch_names": sorted({_normalize_text(item) for item in filters.get("ontology_batch_names", []) if _normalize_text(item)}),
        "electrolytes": sorted({_normalize_text(item) for item in filters.get("electrolytes", []) if _normalize_text(item)}),
        "tracking_statuses": sorted({_normalize_text(item) for item in filters.get("tracking_statuses", []) if _normalize_text(item)}),
        "ontology_only": bool(filters.get("ontology_only")),
        "derived_metrics_only": bool(filters.get("derived_metrics_only")),
        "min_avg_retention_pct": _normalize_optional_float(filters.get("min_avg_retention_pct")),
        "min_avg_coulombic_efficiency_pct": _normalize_optional_float(filters.get("min_avg_coulombic_efficiency_pct")),
        "max_avg_fade_rate_pct_per_100_cycles": _normalize_optional_float(filters.get("max_avg_fade_rate_pct_per_100_cycles")),
        "min_best_cycle_life_80": _normalize_optional_float(filters.get("min_best_cycle_life_80")),
        "search_query": _normalize_text(filters.get("search_query")),
    }
    return normalized


def list_saved_cohorts() -> List[Dict[str, Any]]:
    _ensure_saved_cohort_table()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, description, filters_json, created_date, updated_date
            FROM saved_cohorts
            ORDER BY updated_date DESC, id DESC
            """
        )
        rows = cursor.fetchall()

    payload = []
    for cohort_id, name, description, filters_json, created_date, updated_date in rows:
        payload.append(
            {
                "id": cohort_id,
                "name": name,
                "description": description,
                "filters": normalize_cohort_filters(_load_json_dict(filters_json)),
                "created_date": created_date,
                "updated_date": updated_date,
            }
        )
    return payload


def save_saved_cohort(
    *,
    name: str,
    description: Optional[str],
    filters: Dict[str, Any],
    cohort_id: Optional[int] = None,
) -> int:
    _ensure_saved_cohort_table()
    normalized_filters = normalize_cohort_filters(filters)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if cohort_id is None:
            cursor.execute(
                """
                INSERT INTO saved_cohorts (name, description, filters_json)
                VALUES (?, ?, ?)
                """,
                (name.strip(), _normalize_text(description) or None, json.dumps(normalized_filters)),
            )
            conn.commit()
            return int(cursor.lastrowid)

        cursor.execute(
            """
            UPDATE saved_cohorts
            SET name = ?, description = ?, filters_json = ?, updated_date = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name.strip(), _normalize_text(description) or None, json.dumps(normalized_filters), int(cohort_id)),
        )
        conn.commit()
        return int(cohort_id)


def delete_saved_cohort(cohort_id: int) -> None:
    _ensure_saved_cohort_table()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM saved_cohorts WHERE id = ?", (int(cohort_id),))
        conn.commit()


def load_cohort_records() -> List[Dict[str, Any]]:
    _ensure_derived_metrics_table()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                ce.id,
                ce.project_id,
                p.name AS project_name,
                p.project_type,
                ce.cell_name,
                ce.electrolyte,
                ce.experiment_notes,
                ce.created_date,
                ce.data_json
            FROM cell_experiments ce
            JOIN projects p ON p.id = ce.project_id
            ORDER BY p.name ASC, ce.cell_name ASC, ce.id ASC
            """
        )
        rows = cursor.fetchall()

    experiment_ids = [int(row[0]) for row in rows if row and row[0] is not None]
    metrics_map = load_preferred_experiment_metrics_map(
        experiment_ids,
        compute_missing_legacy=False,
    )

    records: List[Dict[str, Any]] = []
    for (
        experiment_id,
        project_id,
        project_name,
        project_type,
        experiment_name,
        electrolyte,
        experiment_notes,
        created_date,
        data_json,
    ) in rows:
        experiment_data = _load_json_dict(data_json)
        cells = experiment_data.get("cells", []) if isinstance(experiment_data.get("cells"), list) else []
        tracking = experiment_data.get("tracking") if isinstance(experiment_data.get("tracking"), dict) else {}
        ontology = normalize_ontology_context(experiment_data.get("ontology"))
        experiment_date = _normalize_text(experiment_data.get("experiment_date")) or _normalize_text(created_date)
        metrics_payload = metrics_map.get(int(experiment_id), {})
        experiment_summary = metrics_payload.get("experiment_summary") if isinstance(metrics_payload.get("experiment_summary"), dict) else {}
        metrics_computed_at = metrics_payload.get("computed_at")

        cell_electrolytes = sorted(
            {
                _normalize_text(cell.get("electrolyte"))
                for cell in cells
                if isinstance(cell, dict) and _normalize_text(cell.get("electrolyte"))
            }
        )
        canonical_electrolyte = _normalize_text(electrolyte) or (cell_electrolytes[0] if cell_electrolytes else "")
        tracking_status = _normalize_text(tracking.get("manual_status")) or _normalize_text(tracking.get("status"))
        missing_cell_count = tracking.get("missing_cell_count")
        tracked_cell_count = tracking.get("tracked_cell_count") or len(cells)

        records.append(
            {
                "experiment_id": int(experiment_id),
                "project_id": int(project_id),
                "project_name": project_name,
                "project_type": project_type,
                "experiment_name": experiment_name,
                "experiment_date": experiment_date,
                "created_date": created_date,
                "electrolyte": canonical_electrolyte,
                "cell_count": len(cells),
                "tracked_cell_count": tracked_cell_count,
                "missing_cell_count": int(missing_cell_count or 0),
                "tracking_status": tracking_status,
                "tracking_notes": _normalize_text(tracking.get("notes")),
                "experiment_notes": _normalize_text(experiment_notes) or _normalize_text(experiment_data.get("experiment_notes")),
                "ontology": ontology,
                "ontology_mapped": bool(ontology),
                "ontology_batch_name": ontology.get("display_batch_name") or ontology.get("batch_name"),
                "ontology_root_batch_name": ontology.get("display_root_batch_name") or ontology.get("root_batch_name"),
                "ontology_mapping_basis": ontology.get("mapping_basis"),
                "derived_metrics_cached": bool(experiment_summary),
                "derived_metrics_computed_at": metrics_computed_at,
                "metrics_source": _normalize_text(metrics_payload.get("metrics_source")) or "legacy",
                "avg_retention_pct": _normalize_optional_float(experiment_summary.get("avg_retention_pct")),
                "avg_coulombic_efficiency_pct": _normalize_optional_float(experiment_summary.get("avg_coulombic_efficiency_pct")),
                "avg_fade_rate_pct_per_100_cycles": _normalize_optional_float(experiment_summary.get("avg_fade_rate_pct_per_100_cycles")),
                "best_cycle_life_80": _normalize_optional_float(experiment_summary.get("best_cycle_life_80")),
                "avg_reversible_capacity_mAh_g": _normalize_optional_float(experiment_summary.get("avg_reversible_capacity_mAh_g")),
                "metrics_summary": experiment_summary,
            }
        )
    return records


def build_cohort_filter_options(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    project_options = sorted(
        {
            (record["project_id"], record["project_name"])
            for record in records
        },
        key=lambda item: item[1].lower(),
    )
    return {
        "project_options": [{"id": project_id, "label": project_name} for project_id, project_name in project_options],
        "ontology_root_batch_names": sorted({record["ontology_root_batch_name"] for record in records if record.get("ontology_root_batch_name")}),
        "ontology_batch_names": sorted({record["ontology_batch_name"] for record in records if record.get("ontology_batch_name")}),
        "electrolytes": sorted({record["electrolyte"] for record in records if record.get("electrolyte")}),
        "tracking_statuses": sorted({record["tracking_status"] for record in records if record.get("tracking_status")}),
    }


def apply_cohort_filters(records: List[Dict[str, Any]], raw_filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    filters = normalize_cohort_filters(raw_filters)
    search_query = filters["search_query"].casefold()
    filtered: List[Dict[str, Any]] = []

    for record in records:
        if filters["ontology_only"] and not record.get("ontology_mapped"):
            continue
        if filters["derived_metrics_only"] and not record.get("derived_metrics_cached"):
            continue
        if filters["project_ids"] and record["project_id"] not in filters["project_ids"]:
            continue
        if filters["ontology_root_batch_names"] and record.get("ontology_root_batch_name") not in filters["ontology_root_batch_names"]:
            continue
        if filters["ontology_batch_names"] and record.get("ontology_batch_name") not in filters["ontology_batch_names"]:
            continue
        if filters["electrolytes"] and record.get("electrolyte") not in filters["electrolytes"]:
            continue
        if filters["tracking_statuses"] and record.get("tracking_status") not in filters["tracking_statuses"]:
            continue
        if filters["min_avg_retention_pct"] is not None:
            retention_pct = record.get("avg_retention_pct")
            if retention_pct is None or float(retention_pct) < float(filters["min_avg_retention_pct"]):
                continue
        if filters["min_avg_coulombic_efficiency_pct"] is not None:
            ce_pct = record.get("avg_coulombic_efficiency_pct")
            if ce_pct is None or float(ce_pct) < float(filters["min_avg_coulombic_efficiency_pct"]):
                continue
        if filters["max_avg_fade_rate_pct_per_100_cycles"] is not None:
            fade_rate = record.get("avg_fade_rate_pct_per_100_cycles")
            if fade_rate is None or float(fade_rate) > float(filters["max_avg_fade_rate_pct_per_100_cycles"]):
                continue
        if filters["min_best_cycle_life_80"] is not None:
            cycle_life = record.get("best_cycle_life_80")
            if cycle_life is None or float(cycle_life) < float(filters["min_best_cycle_life_80"]):
                continue

        if search_query:
            search_blob = " ".join(
                [
                    _normalize_text(record.get("project_name")),
                    _normalize_text(record.get("experiment_name")),
                    _normalize_text(record.get("ontology_root_batch_name")),
                    _normalize_text(record.get("ontology_batch_name")),
                    _normalize_text(record.get("electrolyte")),
                    _normalize_text(record.get("tracking_notes")),
                    _normalize_text(record.get("experiment_notes")),
                ]
            ).casefold()
            if search_query not in search_blob:
                continue

        filtered.append(record)

    return filtered


def summarize_cohort(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    metrics_ready_records = [record for record in records if record.get("derived_metrics_cached")]
    return {
        "experiment_count": len(records),
        "cell_count": sum(int(record.get("cell_count") or 0) for record in records),
        "mapped_experiment_count": sum(1 for record in records if record.get("ontology_mapped")),
        "metrics_ready_experiment_count": len(metrics_ready_records),
        "unique_parent_batches": len({record["ontology_root_batch_name"] for record in records if record.get("ontology_root_batch_name")}),
        "unique_canonical_batches": len({record["ontology_batch_name"] for record in records if record.get("ontology_batch_name")}),
        "avg_retention_pct": _mean([record.get("avg_retention_pct") for record in metrics_ready_records]),
        "avg_coulombic_efficiency_pct": _mean([record.get("avg_coulombic_efficiency_pct") for record in metrics_ready_records]),
        "avg_fade_rate_pct_per_100_cycles": _mean([record.get("avg_fade_rate_pct_per_100_cycles") for record in metrics_ready_records]),
        "best_cycle_life_80": _max([record.get("best_cycle_life_80") for record in metrics_ready_records]),
        "avg_reversible_capacity_mAh_g": _mean([record.get("avg_reversible_capacity_mAh_g") for record in metrics_ready_records]),
    }


def summarize_cohort_by_root_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for record in records:
        root_batch = record.get("ontology_root_batch_name") or "Unmapped"
        row = grouped.setdefault(
            root_batch,
            {
                "Parent Batch": root_batch,
                "Experiments": 0,
                "Canonical Branches": set(),
                "Projects": set(),
                "Cells": 0,
                "Retention Values": [],
                "CE Values": [],
                "Fade Values": [],
                "Cycle Life Values": [],
            },
        )
        row["Experiments"] += 1
        row["Cells"] += int(record.get("cell_count") or 0)
        if record.get("ontology_batch_name"):
            row["Canonical Branches"].add(record["ontology_batch_name"])
        row["Projects"].add(record["project_name"])
        if record.get("avg_retention_pct") is not None:
            row["Retention Values"].append(float(record["avg_retention_pct"]))
        if record.get("avg_coulombic_efficiency_pct") is not None:
            row["CE Values"].append(float(record["avg_coulombic_efficiency_pct"]))
        if record.get("avg_fade_rate_pct_per_100_cycles") is not None:
            row["Fade Values"].append(float(record["avg_fade_rate_pct_per_100_cycles"]))
        if record.get("best_cycle_life_80") is not None:
            row["Cycle Life Values"].append(float(record["best_cycle_life_80"]))

    rows = []
    for row in grouped.values():
        rows.append(
            {
                "Parent Batch": row["Parent Batch"],
                "Experiments": row["Experiments"],
                "Canonical Branches": len(row["Canonical Branches"]),
                "Projects": ", ".join(sorted(row["Projects"])),
                "Cells": row["Cells"],
                "Avg Retention (%)": _mean(row["Retention Values"]),
                "Avg CE (%)": _mean(row["CE Values"]),
                "Avg Fade (%/100 cyc)": _mean(row["Fade Values"]),
                "Best Cycle Life (80%)": _max(row["Cycle Life Values"]),
            }
        )
    return sorted(rows, key=lambda item: item["Parent Batch"])


def build_cohort_comparison_payload(records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    project_scope = {
        (record["project_id"], record["project_name"])
        for record in records
        if record.get("project_id") is not None and record.get("project_name")
    }
    if len(records) < 2 or len(project_scope) != 1:
        return None

    project_id, project_name = next(iter(project_scope))
    experiment_names = sorted(
        {
            _normalize_text(record.get("experiment_name"))
            for record in records
            if _normalize_text(record.get("experiment_name"))
        }
    )
    if len(experiment_names) < 2:
        return None

    return {
        "project_id": int(project_id),
        "project_name": project_name,
        "experiment_names": experiment_names,
    }


def build_cohort_ai_summary(
    *,
    cohort_name: str,
    filters: Dict[str, Any],
    summary: Dict[str, Any],
    root_batch_summary: List[Dict[str, Any]],
) -> str:
    normalized_filters = normalize_cohort_filters(filters)
    filter_bits = []
    if normalized_filters["project_ids"]:
        filter_bits.append(f"Projects={normalized_filters['project_ids']}")
    if normalized_filters["ontology_root_batch_names"]:
        filter_bits.append(f"Parent batches={', '.join(normalized_filters['ontology_root_batch_names'])}")
    if normalized_filters["ontology_batch_names"]:
        filter_bits.append(f"Branches={', '.join(normalized_filters['ontology_batch_names'])}")
    if normalized_filters["electrolytes"]:
        filter_bits.append(f"Electrolytes={', '.join(normalized_filters['electrolytes'])}")
    if normalized_filters["derived_metrics_only"]:
        filter_bits.append("Derived metrics only")
    if normalized_filters["min_avg_retention_pct"] is not None:
        filter_bits.append(f"Min retention={normalized_filters['min_avg_retention_pct']:.2f}%")
    if normalized_filters["min_best_cycle_life_80"] is not None:
        filter_bits.append(f"Min cycle life={normalized_filters['min_best_cycle_life_80']:.0f}")

    lines = [
        f"COHORT SNAPSHOT: {cohort_name}",
        f"Experiments: {summary['experiment_count']}",
        f"Cells: {summary['cell_count']}",
        f"Metrics coverage: {summary['metrics_ready_experiment_count']}/{summary['experiment_count']}",
        f"Parent batches: {summary['unique_parent_batches']}",
        f"Canonical branches: {summary['unique_canonical_batches']}",
    ]

    if summary.get("avg_retention_pct") is not None:
        lines.append(f"Average retention: {summary['avg_retention_pct']:.2f}%")
    if summary.get("avg_coulombic_efficiency_pct") is not None:
        lines.append(f"Average coulombic efficiency: {summary['avg_coulombic_efficiency_pct']:.3f}%")
    if summary.get("avg_fade_rate_pct_per_100_cycles") is not None:
        lines.append(f"Average fade rate: {summary['avg_fade_rate_pct_per_100_cycles']:.3f}% per 100 cycles")
    if summary.get("best_cycle_life_80") is not None:
        lines.append(f"Best cycle life (80%): {summary['best_cycle_life_80']:.0f}")

    if filter_bits:
        lines.append(f"Applied filters: {' | '.join(filter_bits)}")

    top_batches = sorted(
        root_batch_summary,
        key=lambda item: (
            -(item.get("Experiments") or 0),
            -(item.get("Avg Retention (%)") or -1),
            item.get("Parent Batch") or "",
        ),
    )[:5]
    if top_batches:
        lines.append("Top parent batch rollups:")
        for row in top_batches:
            retention = row.get("Avg Retention (%)")
            ce_pct = row.get("Avg CE (%)")
            fade = row.get("Avg Fade (%/100 cyc)")
            cycle_life = row.get("Best Cycle Life (80%)")
            metrics_bits = []
            if retention is not None:
                metrics_bits.append(f"retention={retention:.2f}%")
            if ce_pct is not None:
                metrics_bits.append(f"CE={ce_pct:.3f}%")
            if fade is not None:
                metrics_bits.append(f"fade={fade:.3f}%/100 cyc")
            if cycle_life is not None:
                metrics_bits.append(f"cycle life={cycle_life:.0f}")
            detail = ", ".join(metrics_bits) if metrics_bits else "no cached metrics"
            lines.append(f"- {row['Parent Batch']}: {row['Experiments']} experiments, {row['Cells']} cells, {detail}")

    return "\n".join(lines)


def save_cohort_snapshot(
    *,
    name: str,
    description: Optional[str],
    filters: Dict[str, Any],
    records: List[Dict[str, Any]],
    cohort_id: Optional[int] = None,
    snapshot_id: Optional[int] = None,
) -> int:
    _ensure_saved_cohort_table()
    _ensure_cohort_snapshot_tables()

    normalized_filters = normalize_cohort_filters(filters)
    experiment_ids = sorted({int(record["experiment_id"]) for record in records if record.get("experiment_id") is not None})
    summary = summarize_cohort(records)
    root_batch_summary = summarize_cohort_by_root_batch(records)
    membership_signature = hashlib.sha256(json.dumps(experiment_ids).encode("utf-8")).hexdigest()
    ai_summary_text = build_cohort_ai_summary(
        cohort_name=name.strip(),
        filters=normalized_filters,
        summary=summary,
        root_batch_summary=root_batch_summary,
    )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if snapshot_id is None:
            cursor.execute(
                """
                INSERT INTO cohort_snapshots (
                    cohort_id, name, description, filters_json, experiment_ids_json,
                    membership_signature, summary_json, root_batch_summary_json, ai_summary_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(cohort_id) if cohort_id is not None else None,
                    name.strip(),
                    _normalize_text(description) or None,
                    json.dumps(_json_safe(normalized_filters)),
                    json.dumps(experiment_ids),
                    membership_signature,
                    json.dumps(_json_safe(summary)),
                    json.dumps(_json_safe(root_batch_summary)),
                    ai_summary_text,
                ),
            )
            snapshot_id = int(cursor.lastrowid)
        else:
            cursor.execute(
                """
                UPDATE cohort_snapshots
                SET cohort_id = ?, name = ?, description = ?, filters_json = ?, experiment_ids_json = ?,
                    membership_signature = ?, summary_json = ?, root_batch_summary_json = ?,
                    ai_summary_text = ?, updated_date = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    int(cohort_id) if cohort_id is not None else None,
                    name.strip(),
                    _normalize_text(description) or None,
                    json.dumps(_json_safe(normalized_filters)),
                    json.dumps(experiment_ids),
                    membership_signature,
                    json.dumps(_json_safe(summary)),
                    json.dumps(_json_safe(root_batch_summary)),
                    ai_summary_text,
                    int(snapshot_id),
                ),
            )
            cursor.execute("DELETE FROM cohort_snapshot_members WHERE snapshot_id = ?", (int(snapshot_id),))

        for record in records:
            experiment_id = record.get("experiment_id")
            if experiment_id is None:
                continue
            cursor.execute(
                """
                INSERT INTO cohort_snapshot_members (snapshot_id, experiment_id, member_json)
                VALUES (?, ?, ?)
                """,
                (
                    int(snapshot_id),
                    int(experiment_id),
                    json.dumps(_json_safe(record)),
                ),
            )
        conn.commit()

    return int(snapshot_id)


def list_cohort_snapshots() -> List[Dict[str, Any]]:
    _ensure_cohort_snapshot_tables()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                cs.id,
                cs.cohort_id,
                sc.name,
                cs.name,
                cs.description,
                cs.filters_json,
                cs.experiment_ids_json,
                cs.membership_signature,
                cs.summary_json,
                cs.root_batch_summary_json,
                cs.ai_summary_text,
                cs.created_date,
                cs.updated_date
            FROM cohort_snapshots cs
            LEFT JOIN saved_cohorts sc ON sc.id = cs.cohort_id
            ORDER BY cs.updated_date DESC, cs.id DESC
            """
        )
        rows = cursor.fetchall()

    snapshots = []
    for (
        snapshot_id,
        cohort_id,
        cohort_name,
        snapshot_name,
        description,
        filters_json,
        experiment_ids_json,
        membership_signature,
        summary_json,
        root_batch_summary_json,
        ai_summary_text,
        created_date,
        updated_date,
    ) in rows:
        snapshots.append(
            {
                "id": int(snapshot_id),
                "cohort_id": int(cohort_id) if cohort_id is not None else None,
                "cohort_name": cohort_name,
                "name": snapshot_name,
                "description": description,
                "filters": normalize_cohort_filters(_load_json_dict(filters_json)),
                "experiment_ids": [int(item) for item in json.loads(experiment_ids_json or "[]")],
                "membership_signature": membership_signature,
                "summary": _load_json_dict(summary_json),
                "root_batch_summary": json.loads(root_batch_summary_json or "[]"),
                "ai_summary_text": ai_summary_text or "",
                "created_date": created_date,
                "updated_date": updated_date,
            }
        )
    return snapshots


def get_cohort_snapshot(snapshot_id: int) -> Optional[Dict[str, Any]]:
    _ensure_cohort_snapshot_tables()
    snapshots = {snapshot["id"]: snapshot for snapshot in list_cohort_snapshots()}
    snapshot = snapshots.get(int(snapshot_id))
    if not snapshot:
        return None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT experiment_id, member_json
            FROM cohort_snapshot_members
            WHERE snapshot_id = ?
            ORDER BY experiment_id ASC
            """,
            (int(snapshot_id),),
        )
        rows = cursor.fetchall()

    snapshot["member_records"] = []
    for experiment_id, member_json in rows:
        member_record = _load_json_dict(member_json)
        member_record["experiment_id"] = int(experiment_id)
        snapshot["member_records"].append(member_record)
    return snapshot


def delete_cohort_snapshot(snapshot_id: int) -> None:
    _ensure_cohort_snapshot_tables()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM cohort_snapshots WHERE id = ?", (int(snapshot_id),))
        conn.commit()


def build_cohort_snapshot_export_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": snapshot.get("id"),
        "cohort_id": snapshot.get("cohort_id"),
        "cohort_name": snapshot.get("cohort_name"),
        "name": snapshot.get("name"),
        "description": snapshot.get("description"),
        "filters": _json_safe(snapshot.get("filters") or {}),
        "experiment_ids": [int(item) for item in snapshot.get("experiment_ids", [])],
        "membership_signature": snapshot.get("membership_signature"),
        "summary": _json_safe(snapshot.get("summary") or {}),
        "root_batch_summary": _json_safe(snapshot.get("root_batch_summary") or []),
        "ai_summary_text": snapshot.get("ai_summary_text") or "",
        "created_date": snapshot.get("created_date"),
        "updated_date": snapshot.get("updated_date"),
        "member_records": _json_safe(snapshot.get("member_records") or []),
    }


def format_cohort_snapshot_markdown(snapshot: Dict[str, Any]) -> str:
    summary = snapshot.get("summary") or {}
    lines = [f"# Cohort Snapshot: {snapshot.get('name') or 'Unnamed Snapshot'}"]
    if snapshot.get("description"):
        lines.append("")
        lines.append(snapshot["description"])
    lines.append("")
    lines.append(f"- Cohort: {snapshot.get('cohort_name') or 'Standalone snapshot'}")
    lines.append(f"- Experiments: {summary.get('experiment_count', 0)}")
    lines.append(f"- Cells: {summary.get('cell_count', 0)}")
    lines.append(f"- Metrics Ready: {summary.get('metrics_ready_experiment_count', 0)}")
    if summary.get("avg_retention_pct") is not None:
        lines.append(f"- Avg Retention: {summary['avg_retention_pct']:.2f}%")
    if summary.get("avg_coulombic_efficiency_pct") is not None:
        lines.append(f"- Avg CE: {summary['avg_coulombic_efficiency_pct']:.3f}%")
    if summary.get("avg_fade_rate_pct_per_100_cycles") is not None:
        lines.append(f"- Avg Fade: {summary['avg_fade_rate_pct_per_100_cycles']:.3f}% / 100 cycles")
    if summary.get("best_cycle_life_80") is not None:
        lines.append(f"- Best Cycle Life (80%): {summary['best_cycle_life_80']:.0f}")
    if snapshot.get("ai_summary_text"):
        lines.append("")
        lines.append("## AI Brief")
        lines.append("")
        lines.append(snapshot["ai_summary_text"])
    return "\n".join(lines)
