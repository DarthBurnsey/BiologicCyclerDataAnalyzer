from __future__ import annotations

import json

import pandas as pd

from analysis_surface_service import build_analysis_metric_rows, build_analysis_surface_payload


def _cell_payload(
    *,
    test_number: str,
    qdis_values: list[float],
    temperature: float,
    c_rate: float,
    formation_cycles: int = 1,
) -> dict:
    df = pd.DataFrame(
        {
            "Cycle": list(range(1, len(qdis_values) + 1)),
            "Q Dis (mAh/g)": qdis_values,
            "Q discharge (mA.h)": [value / 100 for value in qdis_values],
            "Efficiency": [99.2 for _ in qdis_values],
        }
    )
    return {
        "cell_name": test_number,
        "test_number": test_number,
        "formation_cycles": formation_cycles,
        "temperature": temperature,
        "c_rate": c_rate,
        "data_json": df.to_json(),
    }


def test_build_analysis_surface_payload_builds_shared_workspace_ready_payload():
    records = [
        {
            "experiment_id": 10,
            "project_id": 1,
            "project_name": "NMC Full Cells",
            "project_type": "Full Cell",
            "experiment_name": "FC5",
            "cell_count": 1,
            "tracking_status": "Completed",
            "tracking_notes": "Ready for review",
            "missing_cell_count": 0,
            "ontology_root_batch_name": "N10",
            "ontology_batch_name": "N10a",
            "ontology": {"root_batch_name": "N10", "batch_name": "N10a"},
            "avg_retention_pct": 92.0,
            "avg_coulombic_efficiency_pct": 99.4,
            "avg_fade_rate_pct_per_100_cycles": 1.8,
            "best_cycle_life_80": 180,
            "avg_reversible_capacity_mAh_g": 201.5,
            "derived_metrics_computed_at": "2026-03-22 09:00:00",
            "metrics_source": "backend",
        },
        {
            "experiment_id": 11,
            "project_id": 1,
            "project_name": "NMC Full Cells",
            "project_type": "Full Cell",
            "experiment_name": "FC6",
            "cell_count": 1,
            "tracking_status": "Active",
            "tracking_notes": "",
            "missing_cell_count": 1,
            "ontology_root_batch_name": "N10",
            "ontology_batch_name": "N10b",
            "ontology": {"root_batch_name": "N10", "batch_name": "N10b"},
            "avg_retention_pct": 88.0,
            "avg_coulombic_efficiency_pct": 99.1,
            "avg_fade_rate_pct_per_100_cycles": 2.2,
            "best_cycle_life_80": 155,
            "avg_reversible_capacity_mAh_g": 198.4,
            "derived_metrics_computed_at": "2026-03-22 09:01:00",
            "metrics_source": "legacy",
        },
    ]
    payload_lookup = {
        10: (
            1,
            "FC5",
            json.dumps(
                {
                    "cells": [
                        _cell_payload(
                            test_number="FC5 i",
                            qdis_values=[200.0, 199.0, 198.0, 197.0, 196.0, 195.0, 194.0, 193.0, 192.0, 191.0],
                            temperature=25.0,
                            c_rate=0.5,
                        )
                    ]
                }
            ),
        ),
        11: (
            1,
            "FC6",
            json.dumps(
                {
                    "cells": [
                        _cell_payload(
                            test_number="FC6 i",
                            qdis_values=[210.0, 209.0, 208.0, 207.0, 206.0, 205.0, 204.0, 203.0, 202.0, 201.0],
                            temperature=30.0,
                            c_rate=1.0,
                        )
                    ]
                }
            ),
        ),
    }
    calls: list[int] = []

    def loader(experiment_id: int):
        calls.append(experiment_id)
        return payload_lookup.get(experiment_id)

    payload = build_analysis_surface_payload(records, experiment_loader=loader)

    assert calls == [10, 11]
    assert len(payload["plots"]["cells_data"]) == 2
    assert len(payload["plots"]["experiments_data"]) == 2
    assert len(payload["plots"]["project_summaries"]) == 1
    assert payload["plots"]["project_summaries"][0]["project_name"] == "NMC Full Cells"
    assert payload["plots"]["project_summaries"][0]["best_cell_id"] == "FC5"
    assert payload["plot_summary"]["cell_curve_count"] == 2
    assert payload["plot_summary"]["project_count"] == 1
    assert payload["plot_summary"]["avg_fade_rate"] is not None
    assert payload["tracking_context"]["status_counts"] == {"Completed": 1, "Active": 1}
    assert payload["lineage_context"]["root_batches"][0]["Parent Batch"] == "N10"
    assert payload["lineage_context"]["focus_contexts"]["N10"]["batch_name"] == "N10a"


def test_build_analysis_metric_rows_normalizes_numeric_fields():
    rows = build_analysis_metric_rows(
        [
            {
                "experiment_id": 10,
                "experiment_name": "FC5",
                "project_name": "NMC Full Cells",
                "ontology_root_batch_name": "N10",
                "ontology_batch_name": "N10a",
                "avg_retention_pct": "91.2",
                "avg_coulombic_efficiency_pct": "99.4",
                "avg_fade_rate_pct_per_100_cycles": "1.7",
                "best_cycle_life_80": "155",
                "avg_reversible_capacity_mAh_g": "201.5",
                "derived_metrics_computed_at": "2026-03-22 10:00:00",
                "metrics_source": "backend+legacy",
            }
        ]
    )

    assert rows == [
        {
            "experiment_id": 10,
            "experiment_name": "FC5",
            "project_name": "NMC Full Cells",
            "ontology_root_batch_name": "N10",
            "ontology_batch_name": "N10a",
            "avg_retention_pct": 91.2,
            "avg_coulombic_efficiency_pct": 99.4,
            "avg_fade_rate_pct_per_100_cycles": 1.7,
            "best_cycle_life_80": 155.0,
            "avg_reversible_capacity_mAh_g": 201.5,
            "derived_metrics_computed_at": "2026-03-22 10:00:00",
            "metrics_source": "backend+legacy",
        }
    ]
