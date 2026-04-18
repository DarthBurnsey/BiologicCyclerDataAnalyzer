import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from batch_builder_service import list_batches
from database import get_db_connection, save_experiment
from ontology_workflow import get_name_based_ontology_context, normalize_ontology_context

BASE_DIR = Path(__file__).resolve().parent
TRACKING_CSV_FILENAME = "Cleaned_Cycler_Tracking.csv"
TRACKING_CSV_PATH = Path(TRACKING_CSV_FILENAME)

PROJECT_PREFIX_PREFERENCES = {
    "FC": ["NMC- Si Full Cell", "LFP Full Cell"],
    "T": ["LIB Anodes"],
    "N": ["NMC Half Cells"],
    "L": ["LFP Cathodes"],
    "H": ["Hybrid Cathodes"],
}
TRACKING_STATUS_ACTIVE = "Active"
TRACKING_STATUS_COMPLETED = "Completed"
TRACKING_STATUS_UNKNOWN = "Unknown"
LINEAGE_BATCH_STATUS_TRACKED = "Tracked"
LINEAGE_BATCH_STATUS_IN_CELL_INPUTS = "In Cell Inputs"
LINEAGE_BATCH_STATUS_READY = "Ready for Cell Inputs"
LINEAGE_BATCH_STATUS_ONTOLOGY_ONLY = "Ontology Only"
LINEAGE_BATCH_STATUS_LEGACY_ONLY = "Legacy Only"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _parse_tracking_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _to_iso_date(value: Optional[datetime]) -> Optional[str]:
    return value.date().isoformat() if value else None


def _normalize_channel_token(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    token = re.sub(r"\s+", "", str(value)).upper()
    token = token.replace(".", "")
    if re.fullmatch(r"[A-Z]+\d+", token):
        return token
    if re.fullmatch(r"\d+-\d+", token):
        return token
    return None


def _parse_channel_parts(value: Optional[str]) -> Dict[str, Optional[str]]:
    normalized = _normalize_channel_token(value)
    if not normalized:
        return {
            "raw": (value or "").strip(),
            "normalized": None,
            "cycler": None,
            "channel": None,
        }

    if "-" in normalized:
        cycler, channel = normalized.split("-", 1)
    else:
        match = re.fullmatch(r"([A-Z]+)(\d+)", normalized)
        cycler = match.group(1) if match else None
        channel = match.group(2) if match else None

    return {
        "raw": (value or "").strip(),
        "normalized": normalized,
        "cycler": cycler,
        "channel": channel,
    }


def _split_tracking_channels(raw_value: str) -> List[Dict[str, Optional[str]]]:
    parts = [part.strip() for part in str(raw_value or "").split(",") if part.strip()]
    return [_parse_channel_parts(part) for part in parts]


def _extract_cell_channel(cell: Dict[str, Any]) -> Optional[Dict[str, Optional[str]]]:
    existing = _parse_channel_parts(cell.get("cycler_channel"))
    if existing.get("normalized"):
        return existing

    cycler = cell.get("cycler")
    channel = cell.get("channel")
    if cycler and channel:
        combined = f"{cycler}-{channel}" if str(cycler).isdigit() else f"{cycler}{channel}"
        parsed = _parse_channel_parts(combined)
        if parsed.get("normalized"):
            return parsed

    search_text = " ".join(
        str(cell.get(key, "") or "")
        for key in ("file_name", "test_number", "cell_name")
    )

    patterns = (
        r"([A-Z]+)\.(\d+)",
        r"(?:^|[_\s])([A-Z]+)\.(\d+)",
        r"(\d{1,2})-(\d{1,2})",
    )
    for pattern in patterns:
        match = re.search(pattern, search_text.upper())
        if not match:
            continue
        if "-" in match.group(0):
            return _parse_channel_parts(f"{match.group(1)}-{match.group(2)}")
        return _parse_channel_parts(f"{match.group(1)}{match.group(2)}")

    return None


def _int_to_roman(value: int) -> str:
    numerals = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    remainder = max(1, value)
    output = []
    for numeral_value, symbol in numerals:
        while remainder >= numeral_value:
            output.append(symbol)
            remainder -= numeral_value
    return "".join(output).lower()


def _normalize_tracking_status(value: Any) -> Optional[str]:
    if value in {TRACKING_STATUS_ACTIVE, TRACKING_STATUS_COMPLETED, TRACKING_STATUS_UNKNOWN}:
        return str(value)
    return None


def _derive_tracking_status(
    tracking_row: Dict[str, Any],
    matched_experiment: Optional[Dict[str, Any]],
    project_payload: Optional[Dict[str, Any]],
) -> str:
    has_missing_channels = any(
        "Missing cycler/channel assignments" in alert
        for alert in tracking_row.get("alerts", [])
    )
    unresolved_duplicate = tracking_row.get("is_duplicate_name") and not matched_experiment
    unresolved_project = not project_payload

    if has_missing_channels or unresolved_duplicate or unresolved_project:
        return TRACKING_STATUS_UNKNOWN
    if matched_experiment:
        return TRACKING_STATUS_COMPLETED
    return TRACKING_STATUS_ACTIVE


def _candidate_tracking_csv_paths(csv_path: Optional[Path] = None) -> List[Path]:
    if csv_path is not None:
        requested_path = Path(csv_path)
        raw_candidates = [requested_path]
        if not requested_path.is_absolute():
            raw_candidates.append(BASE_DIR / requested_path)
    else:
        raw_candidates = [
            Path.cwd() / TRACKING_CSV_FILENAME,
            Path.cwd() / "samples" / TRACKING_CSV_FILENAME,
            BASE_DIR / TRACKING_CSV_FILENAME,
            BASE_DIR / "samples" / TRACKING_CSV_FILENAME,
        ]

    unique_candidates: List[Path] = []
    seen = set()
    for candidate in raw_candidates:
        normalized = str(candidate.resolve(strict=False))
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate)

    return unique_candidates


def resolve_tracking_csv_path(csv_path: Optional[Path] = None) -> Tuple[Optional[Path], List[Path]]:
    candidates = _candidate_tracking_csv_paths(csv_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate, candidates
    return None, candidates


def _load_tracking_rows(csv_path: Path) -> List[Dict[str, Any]]:
    if not csv_path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with csv_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for index, raw_row in enumerate(reader):
            experiment_name = str(raw_row.get("Exp. #", "")).strip()
            tracking_date = _parse_tracking_date(str(raw_row.get("Date", "")).strip())
            tracked_cell_count = _safe_int(raw_row.get("Cell Count"), default=0)
            cycler_channels = _split_tracking_channels(str(raw_row.get("Cyclers", "")))

            alerts = []
            if not cycler_channels:
                alerts.append("Missing cycler/channel assignments")
            if cycler_channels and tracked_cell_count and len(cycler_channels) != tracked_cell_count:
                alerts.append(
                    f"Tracking row lists {len(cycler_channels)} channel(s) but cell count is {tracked_cell_count}"
                )

            rows.append(
                {
                    "row_index": index,
                    "row_key": "|".join(
                        [
                            experiment_name,
                            _to_iso_date(tracking_date) or "",
                            str(raw_row.get("Cyclers", "")).strip(),
                            str(raw_row.get("Loading", "")).strip(),
                            str(raw_row.get("Cell Count", "")).strip(),
                        ]
                    ),
                    "experiment_name": experiment_name,
                    "tracking_date": _to_iso_date(tracking_date),
                    "tracking_date_display": str(raw_row.get("Date", "")).strip(),
                    "cycler_channels": cycler_channels,
                    "cycler_channel_text": ", ".join(
                        channel.get("raw") or "" for channel in cycler_channels
                    ),
                    "tracked_cell_count": tracked_cell_count,
                    "loading_text": str(raw_row.get("Loading", "")).strip(),
                    "notes": str(raw_row.get("Notes", "")).strip(),
                    "alerts": alerts,
                }
            )

    duplicate_counts: Dict[str, int] = {}
    for row in rows:
        duplicate_counts[row["experiment_name"]] = duplicate_counts.get(row["experiment_name"], 0) + 1

    for row in rows:
        row["duplicate_count"] = duplicate_counts.get(row["experiment_name"], 0)
        row["is_duplicate_name"] = row["duplicate_count"] > 1
        if row["is_duplicate_name"]:
            row["alerts"].append(
                f"Tracking sheet contains {row['duplicate_count']} rows named {row['experiment_name']}"
            )

    return rows


def _load_project_lookup(conn) -> Tuple[Dict[int, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, project_type FROM projects ORDER BY id")
    by_id: Dict[int, Dict[str, Any]] = {}
    by_name: Dict[str, Dict[str, Any]] = {}
    for project_id, name, project_type in cursor.fetchall():
        payload = {"id": project_id, "name": name, "project_type": project_type}
        by_id[project_id] = payload
        by_name[name] = payload
    return by_id, by_name


def _load_database_experiments(conn) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            ce.id,
            ce.project_id,
            p.name,
            p.project_type,
            ce.cell_name,
            ce.data_json,
            ce.created_date
        FROM cell_experiments ce
        JOIN projects p ON p.id = ce.project_id
        ORDER BY ce.id
        """
    )

    experiments: List[Dict[str, Any]] = []
    for experiment_id, project_id, project_name, project_type, experiment_name, data_json, created_date in cursor.fetchall():
        experiment_data: Dict[str, Any] = {}
        if data_json:
            try:
                experiment_data = json.loads(data_json)
            except json.JSONDecodeError:
                experiment_data = {}

        cells = experiment_data.get("cells", []) if isinstance(experiment_data, dict) else []
        tracking_metadata = (
            experiment_data.get("tracking", {})
            if isinstance(experiment_data.get("tracking"), dict)
            else {}
        )
        ontology_metadata = normalize_ontology_context(
            experiment_data.get("ontology", {})
            if isinstance(experiment_data.get("ontology"), dict)
            else {}
        )
        inferred_channels = []
        for cell in cells:
            channel_info = _extract_cell_channel(cell)
            if channel_info and channel_info.get("normalized"):
                inferred_channels.append(channel_info["normalized"])

        experiments.append(
            {
                "experiment_id": experiment_id,
                "project_id": project_id,
                "project_name": project_name,
                "project_type": project_type,
                "experiment_name": str(experiment_name or "").strip(),
                "created_date": created_date,
                "experiment_date": experiment_data.get("experiment_date"),
                "cell_count": len(cells),
                "cells": cells,
                "channel_tokens": inferred_channels,
                "experiment_data": experiment_data,
                "tracking_metadata": tracking_metadata,
                "ontology_metadata": ontology_metadata,
            }
        )

    return experiments


def _resolve_project_for_row(
    tracking_row: Dict[str, Any],
    project_lookup_by_name: Dict[str, Dict[str, Any]],
    matched_experiment: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if matched_experiment:
        return project_lookup_by_name.get(matched_experiment["project_name"])

    experiment_name = tracking_row["experiment_name"]
    for prefix, project_names in PROJECT_PREFIX_PREFERENCES.items():
        if experiment_name.upper().startswith(prefix):
            for project_name in project_names:
                if project_name in project_lookup_by_name:
                    return project_lookup_by_name[project_name]
    return None


def _score_candidate_match(
    tracking_row: Dict[str, Any],
    experiment: Dict[str, Any],
) -> Tuple[int, int]:
    tracking_channels = {
        channel["normalized"]
        for channel in tracking_row["cycler_channels"]
        if channel.get("normalized")
    }
    db_channels = set(experiment.get("channel_tokens") or [])

    overlap = len(tracking_channels & db_channels)
    score = overlap * 100

    db_count = experiment.get("cell_count", 0)
    tracked_count = tracking_row.get("tracked_cell_count", 0)
    score -= abs(db_count - tracked_count)

    experiment_date = experiment.get("experiment_date")
    if experiment_date and tracking_row.get("tracking_date"):
        try:
            experiment_dt = datetime.fromisoformat(str(experiment_date))
            tracking_dt = datetime.fromisoformat(tracking_row["tracking_date"])
            delta_days = abs((experiment_dt.date() - tracking_dt.date()).days)
            score -= min(delta_days, 30)
        except ValueError:
            pass

    if not tracking_channels and overlap == 0 and tracking_row.get("duplicate_count", 1) == 1:
        score += 5

    return score, overlap


def _match_tracking_rows(
    tracking_rows: List[Dict[str, Any]],
    experiments: List[Dict[str, Any]],
    project_lookup_by_name: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows_by_name: Dict[str, List[Dict[str, Any]]] = {}
    for row in tracking_rows:
        rows_by_name.setdefault(row["experiment_name"], []).append(row)

    matched_rows: Dict[str, Dict[str, Any]] = {}
    for experiment in experiments:
        candidate_rows = rows_by_name.get(experiment["experiment_name"], [])
        if not candidate_rows:
            continue

        if len(candidate_rows) == 1:
            chosen_row = candidate_rows[0]
        else:
            scored_candidates = []
            for row in candidate_rows:
                score, overlap = _score_candidate_match(row, experiment)
                scored_candidates.append((score, overlap, row))
            scored_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
            top_score, top_overlap, chosen_row = scored_candidates[0]
            ambiguous_top_match = (
                len(scored_candidates) > 1
                and top_score == scored_candidates[1][0]
                and top_overlap == scored_candidates[1][1]
            )
            if ambiguous_top_match and top_overlap == 0:
                continue

        matched_rows[chosen_row["row_key"]] = experiment

    enriched_rows: List[Dict[str, Any]] = []
    for row in tracking_rows:
        matched_experiment = matched_rows.get(row["row_key"])
        project_payload = _resolve_project_for_row(row, project_lookup_by_name, matched_experiment)
        existing_tracking_metadata = (
            matched_experiment.get("tracking_metadata", {})
            if matched_experiment else {}
        )
        ontology_metadata = (
            normalize_ontology_context(matched_experiment.get("ontology_metadata", {}))
            if matched_experiment else {}
        ) or get_name_based_ontology_context(row["experiment_name"])

        database_cell_count = matched_experiment["cell_count"] if matched_experiment else 0
        tracked_cell_count = row.get("tracked_cell_count", 0)
        missing_cell_count = max(tracked_cell_count - database_cell_count, 0) if matched_experiment else 0

        alerts = list(row["alerts"])
        if matched_experiment and missing_cell_count:
            alerts.append(
                f"{missing_cell_count} tracked cell(s) never made it into the database"
            )

        normalized_channels = [
            channel.get("normalized")
            for channel in row["cycler_channels"]
            if channel.get("normalized")
        ]
        matched_channel_set = set()
        unassigned_channel_set = set(normalized_channels)
        if matched_experiment:
            matched_channel_set = set(normalized_channels) & set(matched_experiment.get("channel_tokens") or [])
            unassigned_channel_set = set(normalized_channels) - matched_channel_set

        auto_status = _derive_tracking_status(row, matched_experiment, project_payload)
        manual_status = _normalize_tracking_status(existing_tracking_metadata.get("manual_status"))
        effective_status = manual_status or auto_status

        enriched_rows.append(
            {
                **row,
                "status": effective_status,
                "auto_status": auto_status,
                "manual_status": manual_status,
                "status_source": "manual" if manual_status else "auto",
                "database_cell_count": database_cell_count,
                "missing_cell_count": missing_cell_count,
                "matched_channel_count": len(matched_channel_set),
                "matched_channels": sorted(matched_channel_set),
                "unassigned_channels": sorted(unassigned_channel_set),
                "yield_fraction": (
                    (database_cell_count / tracked_cell_count) if matched_experiment and tracked_cell_count else None
                ),
                "project_id": project_payload["id"] if project_payload else None,
                "project_name": project_payload["name"] if project_payload else None,
                "project_type": project_payload["project_type"] if project_payload else None,
                "db_experiment_id": matched_experiment["experiment_id"] if matched_experiment else None,
                "db_experiment_name": matched_experiment["experiment_name"] if matched_experiment else None,
                "db_project_name": matched_experiment["project_name"] if matched_experiment else None,
                "db_created_date": matched_experiment["created_date"] if matched_experiment else None,
                "db_cells": matched_experiment.get("cells", []) if matched_experiment else [],
                "db_experiment_data": matched_experiment.get("experiment_data", {}) if matched_experiment else {},
                "ontology": ontology_metadata,
                "ontology_batch_name": ontology_metadata.get("display_batch_name") or ontology_metadata.get("batch_name"),
                "ontology_root_batch_name": ontology_metadata.get("display_root_batch_name") or ontology_metadata.get("root_batch_name"),
                "ontology_mapping_basis": ontology_metadata.get("mapping_basis"),
                "can_open_in_editor": bool(
                    matched_experiment
                    or (project_payload and not row["is_duplicate_name"])
                ),
                "alerts": alerts,
            }
        )

    return enriched_rows


def summarize_tracking_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    completed_rows = [row for row in rows if row["status"] == TRACKING_STATUS_COMPLETED]
    active_rows = [row for row in rows if row["status"] == TRACKING_STATUS_ACTIVE]

    completed_tracked_cells = sum(row["tracked_cell_count"] for row in completed_rows)
    completed_db_cells = sum(row["database_cell_count"] for row in completed_rows)
    dud_cells = sum(row["missing_cell_count"] for row in completed_rows)

    return {
        "tracking_rows": len(rows),
        "active_experiments": len(active_rows),
        "completed_experiments": len(completed_rows),
        "active_cells": sum(row["tracked_cell_count"] for row in active_rows),
        "completed_tracked_cells": completed_tracked_cells,
        "completed_database_cells": completed_db_cells,
        "suspected_dud_cells": dud_cells,
        "defect_fraction": (
            (dud_cells / completed_tracked_cells) if completed_tracked_cells else None
        ),
        "issue_rows": sum(1 for row in rows if row["alerts"]),
    }


def _lineage_batch_status_sort_key(status: str) -> int:
    order = {
        LINEAGE_BATCH_STATUS_READY: 0,
        LINEAGE_BATCH_STATUS_ONTOLOGY_ONLY: 1,
        LINEAGE_BATCH_STATUS_IN_CELL_INPUTS: 2,
        LINEAGE_BATCH_STATUS_TRACKED: 3,
        LINEAGE_BATCH_STATUS_LEGACY_ONLY: 4,
    }
    return order.get(status, len(order))


def load_lineage_root_batch_tracking_rows(
    *,
    experiments: Optional[List[Dict[str, Any]]] = None,
    tracking_rows: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    try:
        root_batches = list_batches(roots_only=True)
    except Exception:
        root_batches = []
    experiments = experiments or []
    tracking_rows = tracking_rows or []

    legacy_counts: Dict[str, int] = {}
    tracking_counts: Dict[str, int] = {}
    active_tracking_counts: Dict[str, int] = {}
    completed_tracking_counts: Dict[str, int] = {}
    project_names_by_root: Dict[str, set[str]] = {}
    display_name_by_root: Dict[str, str] = {}

    for experiment in experiments:
        ontology = normalize_ontology_context(experiment.get("ontology_metadata"))
        root_batch_name = (
            ontology.get("display_root_batch_name")
            or ontology.get("root_batch_name")
            or ontology.get("display_batch_name")
            or ontology.get("batch_name")
        )
        root_batch_name = str(root_batch_name).strip() if root_batch_name else ""
        if not root_batch_name:
            continue
        root_key = root_batch_name.casefold()
        display_name_by_root.setdefault(root_key, root_batch_name)
        legacy_counts[root_key] = legacy_counts.get(root_key, 0) + 1
        project_name = str(experiment.get("project_name") or "").strip()
        if project_name:
            project_names_by_root.setdefault(root_key, set()).add(project_name)

    for row in tracking_rows:
        root_batch_name = str(row.get("ontology_root_batch_name") or "").strip()
        if not root_batch_name:
            continue
        root_key = root_batch_name.casefold()
        display_name_by_root.setdefault(root_key, root_batch_name)
        tracking_counts[root_key] = tracking_counts.get(root_key, 0) + 1
        project_name = str(row.get("project_name") or "").strip()
        if project_name:
            project_names_by_root.setdefault(root_key, set()).add(project_name)
        if row.get("status") == TRACKING_STATUS_ACTIVE:
            active_tracking_counts[root_key] = active_tracking_counts.get(root_key, 0) + 1
        if row.get("status") == TRACKING_STATUS_COMPLETED:
            completed_tracking_counts[root_key] = completed_tracking_counts.get(root_key, 0) + 1

    rows: List[Dict[str, Any]] = []
    seen_root_names: set[str] = set()

    for root_batch in root_batches:
        root_batch_name = str(root_batch.get("batch_name") or "").strip()
        if not root_batch_name:
            continue
        root_key = root_batch_name.casefold()
        display_name_by_root.setdefault(root_key, root_batch_name)
        seen_root_names.add(root_key)
        tracking_row_count = tracking_counts.get(root_key, 0)
        legacy_experiment_count = legacy_counts.get(root_key, 0)
        default_project_id = root_batch.get("default_project_id")
        default_project_name = root_batch.get("default_project_name")
        inferred_project_names = sorted(project_names_by_root.get(root_key, set()))
        resolved_project_name = default_project_name or (", ".join(inferred_project_names) if inferred_project_names else None)

        if tracking_row_count:
            status = LINEAGE_BATCH_STATUS_TRACKED
        elif legacy_experiment_count:
            status = LINEAGE_BATCH_STATUS_IN_CELL_INPUTS
        elif default_project_id or resolved_project_name:
            status = LINEAGE_BATCH_STATUS_READY
        else:
            status = LINEAGE_BATCH_STATUS_ONTOLOGY_ONLY

        rows.append(
            {
                "batch_id": root_batch.get("id"),
                "root_batch_name": root_batch_name,
                "default_project_id": default_project_id,
                "default_project_name": resolved_project_name,
                "study_focus": root_batch.get("study_focus"),
                "legacy_experiment_count": legacy_experiment_count,
                "tracking_row_count": tracking_row_count,
                "active_tracking_count": active_tracking_counts.get(root_key, 0),
                "completed_tracking_count": completed_tracking_counts.get(root_key, 0),
                "status": status,
                "can_open_in_cell_inputs": bool(root_batch.get("id")),
            }
        )

    supplemental_root_keys = sorted(
        {name for name in set(legacy_counts) | set(tracking_counts) if name not in seen_root_names},
        key=lambda key: display_name_by_root.get(key, key).casefold(),
    )
    for root_key in supplemental_root_keys:
        root_batch_name = display_name_by_root.get(root_key, root_key)
        tracking_row_count = tracking_counts.get(root_key, 0)
        legacy_experiment_count = legacy_counts.get(root_key, 0)
        if tracking_row_count:
            status = LINEAGE_BATCH_STATUS_TRACKED
        else:
            status = LINEAGE_BATCH_STATUS_LEGACY_ONLY if legacy_experiment_count else LINEAGE_BATCH_STATUS_ONTOLOGY_ONLY
        rows.append(
            {
                "batch_id": None,
                "root_batch_name": root_batch_name,
                "default_project_id": None,
                "default_project_name": ", ".join(sorted(project_names_by_root.get(root_key, set()))) or None,
                "study_focus": None,
                "legacy_experiment_count": legacy_experiment_count,
                "tracking_row_count": tracking_row_count,
                "active_tracking_count": active_tracking_counts.get(root_key, 0),
                "completed_tracking_count": completed_tracking_counts.get(root_key, 0),
                "status": status,
                "can_open_in_cell_inputs": False,
            }
        )

    rows.sort(
        key=lambda row: (
            _lineage_batch_status_sort_key(str(row.get("status") or "")),
            str(row.get("root_batch_name") or "").casefold(),
        )
    )
    return rows


def get_tracking_dashboard_payload(csv_path: Optional[Path] = None) -> Dict[str, Any]:
    resolved_csv_path, searched_paths = resolve_tracking_csv_path(csv_path)
    with get_db_connection() as conn:
        _, project_lookup_by_name = _load_project_lookup(conn)
        experiments = _load_database_experiments(conn)

    if not resolved_csv_path:
        return {
            "available": False,
            "rows": [],
            "summary": summarize_tracking_rows([]),
            "reason": "missing_file",
            "source_path": None,
            "searched_paths": [str(path.resolve(strict=False)) for path in searched_paths],
            "lineage_root_batches": load_lineage_root_batch_tracking_rows(
                experiments=experiments,
                tracking_rows=[],
            ),
        }

    tracking_rows = _load_tracking_rows(resolved_csv_path)
    if not tracking_rows:
        return {
            "available": False,
            "rows": [],
            "summary": summarize_tracking_rows([]),
            "reason": "empty_file",
            "source_path": str(resolved_csv_path.resolve(strict=False)),
            "searched_paths": [str(path.resolve(strict=False)) for path in searched_paths],
            "lineage_root_batches": load_lineage_root_batch_tracking_rows(
                experiments=experiments,
                tracking_rows=[],
            ),
        }

    rows = _match_tracking_rows(tracking_rows, experiments, project_lookup_by_name)
    rows.sort(
        key=lambda row: (
            row["status"] != TRACKING_STATUS_ACTIVE,
            row["tracking_date"] or "",
            row["experiment_name"],
        ),
        reverse=False,
    )
    return {
        "available": True,
        "rows": rows,
        "summary": summarize_tracking_rows(rows),
        "reason": None,
        "source_path": str(resolved_csv_path.resolve(strict=False)),
        "searched_paths": [str(path.resolve(strict=False)) for path in searched_paths],
        "lineage_root_batches": load_lineage_root_batch_tracking_rows(
            experiments=experiments,
            tracking_rows=rows,
        ),
    }


def _assign_tracking_channels_to_cells(
    cells: List[Dict[str, Any]],
    tracking_row: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    updated_cells = [dict(cell) for cell in cells]
    remaining_channels = [
        dict(channel)
        for channel in tracking_row["cycler_channels"]
        if channel.get("normalized")
    ]
    remaining_by_normalized = {channel["normalized"]: channel for channel in remaining_channels}

    for cell in updated_cells:
        existing_info = _extract_cell_channel(cell)
        normalized = existing_info.get("normalized") if existing_info else None
        if normalized and normalized in remaining_by_normalized:
            channel = remaining_by_normalized.pop(normalized)
            cell["cycler"] = channel.get("cycler")
            cell["channel"] = channel.get("channel")
            cell["cycler_channel"] = channel.get("normalized")
            if "tracking_placeholder" not in cell:
                cell["tracking_placeholder"] = False

    unmatched_cells = [
        cell for cell in updated_cells if not _parse_channel_parts(cell.get("cycler_channel")).get("normalized")
    ]
    for cell in unmatched_cells:
        if not remaining_by_normalized:
            break
        normalized, channel = remaining_by_normalized.popitem()
        cell["cycler"] = channel.get("cycler")
        cell["channel"] = channel.get("channel")
        cell["cycler_channel"] = normalized
        if "tracking_placeholder" not in cell:
            cell["tracking_placeholder"] = False

    return updated_cells, sorted(remaining_by_normalized.keys())


def sync_tracking_rows_to_database(rows: List[Dict[str, Any]]) -> int:
    updated_count = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for row in rows:
            experiment_id = row.get("db_experiment_id")
            experiment_data = row.get("db_experiment_data")
            if not experiment_id or not isinstance(experiment_data, dict):
                continue

            cells = experiment_data.get("cells", [])
            updated_cells, unassigned_channels = _assign_tracking_channels_to_cells(cells, row)
            existing_tracking = (
                experiment_data.get("tracking", {})
                if isinstance(experiment_data.get("tracking"), dict)
                else {}
            )
            manual_status = _normalize_tracking_status(existing_tracking.get("manual_status"))

            tracking_payload = {
                "source": "Cleaned_Cycler_Tracking.csv",
                "row_key": row["row_key"],
                "tracking_date": row["tracking_date"],
                "tracked_cell_count": row["tracked_cell_count"],
                "loading_text": row["loading_text"],
                "notes": row["notes"],
                "cycler_channel_text": row["cycler_channel_text"],
                "cycler_channels": row["cycler_channels"],
                "database_cell_count": row["database_cell_count"],
                "missing_cell_count": row["missing_cell_count"],
                "status": row["status"],
                "alerts": row["alerts"],
                "unassigned_channels": unassigned_channels,
            }
            if manual_status:
                tracking_payload["manual_status"] = manual_status
                if existing_tracking.get("manual_status_updated_at"):
                    tracking_payload["manual_status_updated_at"] = existing_tracking["manual_status_updated_at"]

            updated_experiment_data = dict(experiment_data)
            updated_experiment_data["cells"] = updated_cells
            updated_experiment_data["tracking"] = tracking_payload

            previous_payload = json.dumps(experiment_data, sort_keys=True)
            next_payload = json.dumps(updated_experiment_data, sort_keys=True)
            if previous_payload == next_payload:
                continue

            cursor.execute(
                "UPDATE cell_experiments SET data_json = ? WHERE id = ?",
                (json.dumps(updated_experiment_data), experiment_id),
            )
            updated_count += 1

        if updated_count:
            conn.commit()

    return updated_count


def _build_tracking_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": "Cleaned_Cycler_Tracking.csv",
        "row_key": row["row_key"],
        "tracking_date": row["tracking_date"],
        "tracked_cell_count": row["tracked_cell_count"],
        "loading_text": row["loading_text"],
        "notes": row["notes"],
        "cycler_channel_text": row["cycler_channel_text"],
        "cycler_channels": row["cycler_channels"],
        "status": "Active",
        "alerts": row["alerts"],
    }


def set_tracking_status_override(experiment_id: int, manual_status: Optional[str]) -> bool:
    normalized_status = _normalize_tracking_status(manual_status) if manual_status is not None else None
    if manual_status is not None and normalized_status is None:
        raise ValueError(f"Unsupported tracking status override: {manual_status}")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data_json FROM cell_experiments WHERE id = ?", (experiment_id,))
        row = cursor.fetchone()
        if not row:
            return False

        raw_payload = row[0]
        experiment_data: Dict[str, Any] = {}
        if raw_payload:
            try:
                experiment_data = json.loads(raw_payload) or {}
            except json.JSONDecodeError:
                experiment_data = {}

        tracking_payload = (
            dict(experiment_data.get("tracking", {}))
            if isinstance(experiment_data.get("tracking"), dict)
            else {}
        )

        if normalized_status:
            tracking_payload["manual_status"] = normalized_status
            tracking_payload["manual_status_updated_at"] = datetime.now().isoformat(timespec="seconds")
        else:
            tracking_payload.pop("manual_status", None)
            tracking_payload.pop("manual_status_updated_at", None)

        experiment_data["tracking"] = tracking_payload
        cursor.execute(
            "UPDATE cell_experiments SET data_json = ? WHERE id = ?",
            (json.dumps(experiment_data), experiment_id),
        )
        conn.commit()

    return True


def create_tracking_draft_experiment(row: Dict[str, Any]) -> Optional[int]:
    if row.get("db_experiment_id") or not row.get("project_id"):
        return row.get("db_experiment_id")

    placeholder_loading = _safe_float(row.get("loading_text")) or 0.0
    cells_data = []
    tracked_count = max(row.get("tracked_cell_count", 0), len(row.get("cycler_channels", [])))
    for index in range(tracked_count):
        channel_info = row["cycler_channels"][index] if index < len(row["cycler_channels"]) else {}
        cells_data.append(
            {
                "cell_name": f"{row['experiment_name']} {_int_to_roman(index + 1)}",
                "file_name": None,
                "loading": placeholder_loading,
                "active_material": 90.0,
                "formation_cycles": 4,
                "test_number": f"{row['experiment_name']} {_int_to_roman(index + 1)}",
                "electrolyte": "1M LiPF6 1:1:1",
                "substrate": "Copper",
                "separator": "25um PP",
                "formulation": [],
                "data_json": None,
                "excluded": False,
                "cycler": channel_info.get("cycler"),
                "channel": channel_info.get("channel"),
                "cycler_channel": channel_info.get("normalized"),
                "tracking_placeholder": True,
            }
        )

    experiment_date = _parse_tracking_date(row.get("tracking_date_display", ""))
    experiment_id = save_experiment(
        project_id=row["project_id"],
        experiment_name=row["experiment_name"],
        experiment_date=experiment_date.date() if experiment_date else None,
        disc_diameter_mm=15,
        group_assignments=None,
        group_names=["Group A", "Group B", "Group C"],
        cells_data=cells_data,
        solids_content=0.0,
        pressed_thickness=0.0,
        experiment_notes=row.get("notes", ""),
        cell_format_data=None,
        additional_data={
            "tracking": _build_tracking_metadata(row),
            "tracking_draft": True,
            **(
                {"ontology": row["ontology"]}
                if isinstance(row.get("ontology"), dict) and row.get("ontology")
                else {}
            ),
        },
    )
    return experiment_id
