"""Shared analysis payload builders for cohort and workspace surfaces."""

from __future__ import annotations

import json
from io import StringIO
from typing import Any, Callable, Dict, Optional, TypedDict

import pandas as pd

from cohort_tools import summarize_cohort_by_root_batch
from dashboard_analytics import calculate_fade_rate
from database import get_hydrated_experiment_payload


ExperimentPayloadLoader = Callable[[int], Optional[tuple[int, str, str]]]


class AnalysisSurfacePlots(TypedDict, total=False):
    cells_data: list[Dict[str, Any]]
    project_summaries: list[Dict[str, Any]]
    experiments_data: list[Dict[str, Any]]
    metric_rows: list[Dict[str, Any]]


class AnalysisSurfacePayload(TypedDict, total=False):
    plots: AnalysisSurfacePlots
    lineage_context: Dict[str, Any]
    tracking_context: Dict[str, Any]
    plot_summary: Dict[str, Any]


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


def build_analysis_project_summaries(records: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    grouped: Dict[tuple[Any, Any], Dict[str, Any]] = {}
    for record in records:
        project_key = (record.get("project_id"), record.get("project_name"))
        row = grouped.setdefault(
            project_key,
            {
                "project_id": record.get("project_id"),
                "project_name": record.get("project_name") or "Unknown",
                "project_type": record.get("project_type") or "Unknown",
                "cell_count": 0,
                "latest_cycle": 0,
                "best_cell_id": record.get("experiment_name") or "N/A",
                "best_retention_pct": 0.0,
                "avg_fade_values": [],
                "status": "medium",
            },
        )
        row["cell_count"] += int(record.get("cell_count") or 0)
        row["latest_cycle"] = max(
            int(row["latest_cycle"] or 0),
            int(record.get("best_cycle_life_80") or 0),
        )
        retention_pct = _safe_float(record.get("avg_retention_pct"))
        if retention_pct is not None and retention_pct > float(row["best_retention_pct"]):
            row["best_retention_pct"] = retention_pct
            row["best_cell_id"] = record.get("experiment_name") or "N/A"

        fade_rate = _safe_float(record.get("avg_fade_rate_pct_per_100_cycles"))
        if fade_rate is not None:
            row["avg_fade_values"].append(fade_rate)

    summaries: list[Dict[str, Any]] = []
    for row in grouped.values():
        avg_fade = (
            float(sum(row["avg_fade_values"]) / len(row["avg_fade_values"]))
            if row["avg_fade_values"]
            else 0.0
        )
        if avg_fade < 1.0:
            status = "good"
        elif avg_fade < 2.0:
            status = "medium"
        else:
            status = "bad"
        summaries.append(
            {
                "project_id": row["project_id"],
                "project_name": row["project_name"],
                "project_type": row["project_type"],
                "cell_count": row["cell_count"],
                "latest_cycle": row["latest_cycle"],
                "best_cell_id": row["best_cell_id"],
                "best_retention_pct": round(float(row["best_retention_pct"]), 2),
                "avg_fade_rate": round(avg_fade, 3),
                "status": status,
            }
        )
    return sorted(summaries, key=lambda item: item["project_name"].lower())


def build_analysis_metric_rows(records: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    metric_rows = []
    for record in records:
        metric_rows.append(
            {
                "experiment_id": record.get("experiment_id"),
                "experiment_name": record.get("experiment_name"),
                "project_name": record.get("project_name"),
                "ontology_root_batch_name": record.get("ontology_root_batch_name"),
                "ontology_batch_name": record.get("ontology_batch_name"),
                "avg_retention_pct": _safe_float(record.get("avg_retention_pct")),
                "avg_coulombic_efficiency_pct": _safe_float(record.get("avg_coulombic_efficiency_pct")),
                "avg_fade_rate_pct_per_100_cycles": _safe_float(record.get("avg_fade_rate_pct_per_100_cycles")),
                "best_cycle_life_80": _safe_float(record.get("best_cycle_life_80")),
                "avg_reversible_capacity_mAh_g": _safe_float(record.get("avg_reversible_capacity_mAh_g")),
                "derived_metrics_computed_at": record.get("derived_metrics_computed_at"),
                "metrics_source": record.get("metrics_source"),
            }
        )
    return metric_rows


def build_analysis_lineage_context(records: list[Dict[str, Any]]) -> Dict[str, Any]:
    root_batch_summary = summarize_cohort_by_root_batch(records)
    focus_contexts: Dict[str, Dict[str, Any]] = {}
    for record in records:
        root_batch_name = _normalize_text(record.get("ontology_root_batch_name"))
        if not root_batch_name or root_batch_name in focus_contexts:
            continue
        ontology_context = record.get("ontology")
        if isinstance(ontology_context, dict):
            focus_contexts[root_batch_name] = ontology_context
        else:
            focus_contexts[root_batch_name] = {
                "root_batch_name": root_batch_name,
                "batch_name": record.get("ontology_batch_name") or root_batch_name,
            }
    return {
        "root_batches": root_batch_summary,
        "focus_contexts": focus_contexts,
    }


def build_analysis_tracking_context(records: list[Dict[str, Any]]) -> Dict[str, Any]:
    status_counts: Dict[str, int] = {}
    tracking_rows = []
    for record in records:
        status = _normalize_text(record.get("tracking_status")) or "Unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        tracking_rows.append(
            {
                "Project": record.get("project_name") or "Unknown",
                "Experiment": record.get("experiment_name") or "Unknown",
                "Tracking Status": status,
                "Missing Cells": int(record.get("missing_cell_count") or 0),
                "Parent Batch": record.get("ontology_root_batch_name") or "",
                "Notes": record.get("tracking_notes") or "",
            }
        )
    return {
        "status_counts": status_counts,
        "rows": tracking_rows,
    }


def _build_plot_collections(
    records: list[Dict[str, Any]],
    *,
    experiment_loader: Optional[ExperimentPayloadLoader] = None,
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]], list[float]]:
    loader = experiment_loader or get_hydrated_experiment_payload
    cells_data: list[Dict[str, Any]] = []
    experiments_data: list[Dict[str, Any]] = []
    fade_rates: list[float] = []

    for record in records:
        experiment_id = record.get("experiment_id")
        if experiment_id is None:
            continue
        payload = loader(int(experiment_id))
        if not payload or not payload[2]:
            continue

        try:
            experiment_data = json.loads(payload[2])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(experiment_data, dict):
            continue

        cells = experiment_data.get("cells", [])
        if not isinstance(cells, list):
            continue

        experiment_frames = []
        for cell in cells:
            if not isinstance(cell, dict) or cell.get("excluded", False):
                continue
            cell_data_json = cell.get("data_json")
            if not cell_data_json:
                continue

            cell_id = cell.get("test_number") or cell.get("cell_name") or "Unknown"
            cells_data.append(
                {
                    "experiment_id": int(experiment_id),
                    "experiment_name": record.get("experiment_name") or payload[1],
                    "project_id": record.get("project_id"),
                    "project_name": record.get("project_name"),
                    "cell_id": cell_id,
                    "data_json": cell_data_json,
                    "formulation": cell.get("formulation", []),
                    "tracking_status": record.get("tracking_status"),
                    "ontology_root_batch_name": record.get("ontology_root_batch_name"),
                    "ontology_batch_name": record.get("ontology_batch_name"),
                    "temperature": cell.get("temperature"),
                    "c_rate": cell.get("c_rate"),
                }
            )

            try:
                df = pd.read_json(StringIO(cell_data_json))
            except ValueError:
                continue

            experiment_frames.append(
                {
                    "df": df,
                    "testnum": cell_id,
                    "formation_cycles": cell.get("formation_cycles") or 0,
                }
            )
            fade_rate = calculate_fade_rate(df)
            if fade_rate is not None:
                fade_rates.append(float(fade_rate))

        if experiment_frames:
            experiments_data.append(
                {
                    "experiment_id": int(experiment_id),
                    "experiment_name": record.get("experiment_name") or payload[1],
                    "project_id": record.get("project_id"),
                    "project_name": record.get("project_name"),
                    "dfs": experiment_frames,
                }
            )

    return cells_data, experiments_data, fade_rates


def build_analysis_surface_payload(
    records: list[Dict[str, Any]],
    *,
    experiment_loader: Optional[ExperimentPayloadLoader] = None,
) -> AnalysisSurfacePayload:
    cells_data, experiments_data, fade_rates = _build_plot_collections(
        records,
        experiment_loader=experiment_loader,
    )
    project_summaries = build_analysis_project_summaries(records)
    metric_rows = build_analysis_metric_rows(records)
    lineage_context = build_analysis_lineage_context(records)
    tracking_context = build_analysis_tracking_context(records)
    return {
        "plots": {
            "cells_data": cells_data,
            "project_summaries": project_summaries,
            "experiments_data": experiments_data,
            "metric_rows": metric_rows,
        },
        "lineage_context": lineage_context,
        "tracking_context": tracking_context,
        "plot_summary": {
            "cell_curve_count": len(cells_data),
            "project_count": len(project_summaries),
            "avg_fade_rate": round(sum(fade_rates) / len(fade_rates), 3) if fade_rates else None,
        },
    }
