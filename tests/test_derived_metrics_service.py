from __future__ import annotations

import json

import pandas as pd

import database
from derived_metrics_service import get_or_refresh_experiment_derived_metrics, load_derived_metrics_map


def test_persisted_derived_metrics_cache_round_trip(tmp_path, monkeypatch):
    db_path = tmp_path / "cellscope.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    database.init_database()
    database.migrate_database()

    df = pd.DataFrame(
        {
            "Cycle": [1, 2, 3, 4, 5],
            "Q Dis (mAh/g)": [200.0, 198.0, 196.0, 194.0, 192.0],
            "Q charge (mA.h)": [2.02, 2.0, 1.99, 1.97, 1.95],
            "Q discharge (mA.h)": [2.0, 1.98, 1.96, 1.94, 1.92],
        }
    )
    experiment_payload = {
        "experiment_date": "2026-01-20",
        "disc_diameter_mm": 15,
        "cells": [
            {
                "cell_name": "FC5 i",
                "test_number": "FC5 i",
                "loading": 16.8,
                "active_material": 92.0,
                "formation_cycles": 1,
                "data_json": df.to_json(),
            }
        ],
        "ontology": {
            "display_batch_name": "N10",
            "display_root_batch_name": "N10",
        },
    }

    with database.get_db_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, user_id, name, project_type) VALUES (1, 'admin', 'NMC- Si Full Cell', 'Full Cell')"
        )
        conn.execute(
            """
            INSERT INTO cell_experiments (
                id, project_id, cell_name, electrolyte, data_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                10,
                1,
                "FC5",
                "1M LiPF6 EC:EMC:DMC 1:1:1 + 2% LiDFOB",
                json.dumps(experiment_payload),
            ),
        )
        conn.commit()

    first_metrics = get_or_refresh_experiment_derived_metrics(10)
    assert first_metrics is not None
    assert first_metrics["cache_hit"] is False
    summary = first_metrics["experiment_summary"]
    assert summary["experiment_name"] == "FC5"
    assert summary["ontology_root_batch_name"] == "N10"
    assert summary["cell_count_with_data"] == 1
    assert summary["avg_retention_pct"] is not None
    assert summary["avg_coulombic_efficiency_pct"] is not None

    second_metrics = get_or_refresh_experiment_derived_metrics(10)
    assert second_metrics is not None
    assert second_metrics["cache_hit"] is True

    metrics_map = load_derived_metrics_map([10])
    assert 10 in metrics_map
    assert metrics_map[10]["experiment_summary"]["experiment_name"] == "FC5"
