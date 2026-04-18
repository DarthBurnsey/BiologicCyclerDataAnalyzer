"""Bridge to the existing CellScope 1.0 parser and anomaly logic."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

# Reuse the existing root-level analysis code rather than reimplementing it.
REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cell_flags import analyze_cell_for_flags, get_experiment_context  # noqa: E402
from data_analysis import calculate_cell_summary  # noqa: E402
from data_processing import (  # noqa: E402
    detect_file_type,
    parse_biologic_csv,
    parse_mti_xlsx,
    parse_neware_xlsx,
)


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _latest_series_value(df: pd.DataFrame, column: str) -> Optional[float]:
    if column not in df.columns or df.empty:
        return None
    return _as_float(df[column].iloc[-1])


def parse_cycler_file(
    file_path: str,
    *,
    loading: Optional[float],
    active_material_pct: Optional[float],
    test_number: Optional[str],
    project_type: str,
    parser_type: str = "auto",
) -> Dict[str, Any]:
    """Parse a cycler export file with the existing parser implementations."""
    if loading is None or loading <= 0:
        raise ValueError("Cell loading must be configured before live ingestion can parse data.")
    if active_material_pct is None or active_material_pct <= 0:
        raise ValueError(
            "Cell active material % must be configured before live ingestion can parse data."
        )

    dataset = {
        "loading": loading,
        "active": active_material_pct,
        "testnum": test_number or Path(file_path).stem,
    }

    with open(file_path, "rb") as handle:
        resolved_parser = parser_type or "auto"
        if resolved_parser == "auto":
            resolved_parser = detect_file_type(handle)
            handle.seek(0)

        if resolved_parser == "biologic_csv":
            df, lower_cutoff, upper_cutoff = parse_biologic_csv(handle, dataset, project_type)
        elif resolved_parser == "neware_xlsx":
            df, lower_cutoff, upper_cutoff = parse_neware_xlsx(handle, dataset, project_type)
        elif resolved_parser == "mti_xlsx":
            df, lower_cutoff, upper_cutoff = parse_mti_xlsx(handle, dataset, project_type)
        else:
            raise ValueError(f"Unsupported parser type: {resolved_parser}")

    if df.empty:
        raise ValueError(f"Parsed file {file_path} did not produce any cycle data.")

    return {
        "parser_type": resolved_parser,
        "dataframe": df,
        "lower_cutoff": lower_cutoff,
        "upper_cutoff": upper_cutoff,
    }


def summarize_run(
    df: pd.DataFrame,
    *,
    cell_name: str,
    test_number: Optional[str],
    loading: Optional[float],
    active_material_pct: Optional[float],
    formation_cycles: int,
    porosity: Optional[float],
    project_type: str,
    disc_diameter_mm: Optional[float],
    anode_mass: Optional[float] = None,
    cathode_mass: Optional[float] = None,
    overhang_ratio: Optional[float] = None,
) -> Dict[str, Any]:
    """Summarize a parsed dataframe using the existing analysis helpers."""
    disc_diameter_mm = disc_diameter_mm or 15.0
    disc_area_cm2 = math.pi * (disc_diameter_mm / 20.0) ** 2
    cell_data = {
        "cell_name": cell_name,
        "test_number": test_number,
        "loading": loading,
        "active_material": active_material_pct,
        "formation_cycles": formation_cycles,
        "porosity": porosity,
        "anode_mass": anode_mass,
        "cathode_mass": cathode_mass,
        "overhang_ratio": overhang_ratio,
    }
    summary = calculate_cell_summary(df, cell_data, disc_area_cm2, project_type)
    summary["cell_name"] = test_number or cell_name
    summary["current_cycle"] = _as_int(df.iloc[-1, 0]) if not df.empty else None
    summary["latest_charge_capacity_mah"] = _latest_series_value(df, "Q charge (mA.h)")
    summary["latest_discharge_capacity_mah"] = _latest_series_value(
        df, "Q discharge (mA.h)"
    )
    summary["latest_efficiency"] = _latest_series_value(df, "Efficiency (-)")

    qdis = pd.to_numeric(df.get("Q Dis (mAh/g)"), errors="coerce").dropna()
    if len(qdis) > formation_cycles:
        baseline = qdis.iloc[formation_cycles]
    elif not qdis.empty:
        baseline = qdis.iloc[0]
    else:
        baseline = None
    if baseline and baseline > 0 and not qdis.empty:
        summary["capacity_retention_pct"] = float((qdis.iloc[-1] / baseline) * 100)
    else:
        summary["capacity_retention_pct"] = None

    return summary


def detect_run_flags(
    df: pd.DataFrame,
    summary: Dict[str, Any],
    peer_summaries: Optional[Iterable[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Return serialized anomaly flags for a run."""
    context = None
    peer_summaries = list(peer_summaries or [])
    if peer_summaries:
        context = get_experiment_context(peer_summaries)

    flags = analyze_cell_for_flags(df, summary, context)
    return [flag.to_dict() for flag in flags]


def dataframe_to_cycle_payloads(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Normalize a parsed dataframe into per-cycle payload dictionaries."""
    time_columns = [
        "Date/Time",
        "Datetime",
        "Date Time",
        "Time",
        "Step Time",
        "Test Time",
    ]
    detected_time_column = next((column for column in time_columns if column in df.columns), None)

    payloads: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        sample_time = None
        if detected_time_column:
            parsed = pd.to_datetime(row.get(detected_time_column), errors="coerce")
            if parsed is not pd.NaT:
                sample_time = parsed.to_pydatetime()

        payloads.append(
            {
                "cycle_index": _as_int(row.iloc[0]),
                "sample_time": sample_time,
                "charge_capacity_mah": _as_float(row.get("Q charge (mA.h)")),
                "discharge_capacity_mah": _as_float(row.get("Q discharge (mA.h)")),
                "specific_charge_capacity_mah_g": _as_float(row.get("Q Chg (mAh/g)")),
                "specific_discharge_capacity_mah_g": _as_float(row.get("Q Dis (mAh/g)")),
                "efficiency": _as_float(row.get("Efficiency (-)")),
                "payload_json": {str(column): _serialize_value(row[column]) for column in df.columns},
            }
        )

    return [payload for payload in payloads if payload["cycle_index"] is not None]


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and pd.isna(value):
            return None
        return value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return str(value)
