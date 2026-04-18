"""Temporary Streamlit lineage explorer for the ontology-backed battery graph."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import pandas as pd
import streamlit as st

from batch_builder_service import build_batch_cell_inputs_template
from ontology_workflow import normalize_ontology_context


ONTOLOGY_DB_PATH = Path(__file__).resolve().parent / "Cellscope 2.0" / "backend" / "cellscope2.db"
LINEAGE_MODE_KEY = "lineage_explorer_mode"
LINEAGE_BATCH_SELECT_KEY = "lineage_parent_batch_select"
LINEAGE_BUILD_SELECT_KEY = "lineage_cell_build_select"
LINEAGE_LEGACY_EXPERIMENT_SELECT_KEY = "lineage_legacy_experiment_select"
LINEAGE_FOCUS_REQUEST_KEY = "lineage_focus_request"
LINEAGE_CELL_INPUT_BATCH_SELECT_KEY = "lineage_cell_input_batch_select"


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_json(value: Any) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(ONTOLOGY_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _format_timestamp(value: Any) -> Optional[str]:
    text = _text(value)
    if not text:
        return None
    return text.replace("T", " ")[:10]


def queue_lineage_explorer_focus(
    ontology_context: Dict[str, Any],
    *,
    legacy_experiment_id: Optional[int] = None,
    legacy_experiment_name: Optional[str] = None,
) -> None:
    context = normalize_ontology_context(ontology_context)
    if not context:
        return

    root_batch_name = (
        _text(context.get("root_batch_name"))
        or _text(context.get("parent_batch_name"))
        or _text(context.get("batch_name"))
    )
    batch_name = _text(context.get("batch_name"))
    linked_build_names = context.get("display_linked_cell_build_names") or context.get("linked_cell_build_names") or []

    st.session_state[LINEAGE_MODE_KEY] = "Electrode Batch"
    if root_batch_name:
        st.session_state[LINEAGE_BATCH_SELECT_KEY] = root_batch_name
    st.session_state[LINEAGE_FOCUS_REQUEST_KEY] = {
        "mode": "Electrode Batch",
        "root_batch_name": root_batch_name,
        "batch_name": batch_name,
        "legacy_experiment_id": legacy_experiment_id,
        "legacy_experiment_name": _text(legacy_experiment_name),
        "linked_cell_build_names": linked_build_names,
    }


def _fetch_rows_by_ids(
    connection: sqlite3.Connection,
    table_name: str,
    ids: Iterable[int],
) -> list[dict[str, Any]]:
    normalized_ids = sorted({int(item) for item in ids if item is not None})
    if not normalized_ids:
        return []
    placeholders = ",".join("?" for _ in normalized_ids)
    rows = connection.execute(
        f"SELECT * FROM {table_name} WHERE id IN ({placeholders})",
        normalized_ids,
    ).fetchall()
    return [dict(row) for row in rows]


def _fetch_legacy_experiments(
    connection: sqlite3.Connection,
    experiment_ids: Iterable[int],
) -> list[dict[str, Any]]:
    normalized_ids = sorted({int(item) for item in experiment_ids if item is not None})
    if not normalized_ids:
        return []
    placeholders = ",".join("?" for _ in normalized_ids)
    rows = connection.execute(
        f"""
        SELECT
            e.id AS legacy_experiment_id,
            e.name AS experiment_name,
            e.project_id AS project_id,
            p.name AS project_name
        FROM experiments e
        LEFT JOIN projects p ON p.id = e.project_id
        WHERE e.id IN ({placeholders})
        ORDER BY e.name ASC, e.id ASC
        """,
        normalized_ids,
    ).fetchall()
    present = {row["legacy_experiment_id"] for row in rows}
    payload = [dict(row) for row in rows]
    for missing_id in normalized_ids:
        if missing_id not in present:
            payload.append(
                {
                    "legacy_experiment_id": missing_id,
                    "experiment_name": None,
                    "project_id": None,
                    "project_name": None,
                }
            )
    return sorted(payload, key=lambda row: ((row.get("project_name") or ""), (row.get("experiment_name") or ""), row["legacy_experiment_id"]))


def _normalize_batch_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["metadata_json"] = _load_json(payload.get("metadata_json")) or {}
    payload["formulation_json"] = _load_json(payload.get("formulation_json")) or []
    payload["created_at"] = _format_timestamp(payload.get("created_at"))
    return payload


def _normalize_build_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["metadata_json"] = _load_json(payload.get("metadata_json")) or {}
    payload["created_at"] = _format_timestamp(payload.get("created_at"))
    return payload


def _build_contextual_source_material_rows(
    batches: list[dict[str, Any]],
    material_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    materials_by_name: dict[str, dict[str, Any]] = {}
    for material in material_rows:
        payload = dict(material)
        payload["metadata_json"] = _load_json(payload.get("metadata_json")) or {}
        material_name = _text(payload.get("name"))
        if material_name:
            materials_by_name[material_name] = payload

    rows: list[dict[str, Any]] = []
    for batch in batches:
        batch_name = _text(batch.get("batch_name")) or "Unknown"
        batch_metadata = batch.get("metadata_json") or {}
        batch_created_at = _format_timestamp(batch.get("created_at"))
        for component in batch.get("formulation_json", []):
            if not isinstance(component, dict):
                continue
            component_name = _text(component.get("Component"))
            if not component_name:
                continue
            component_metadata = component.get("metadata") if isinstance(component.get("metadata"), dict) else {}
            material = materials_by_name.get(component_name, {})
            manufacturer = (
                _text(component_metadata.get("manufacturer_hint"))
                or (_text(batch_metadata.get("active_material_source")) if component_name == "NMC811" else None)
                or _text(material.get("manufacturer"))
            )
            material_metadata = material.get("metadata_json") if isinstance(material.get("metadata_json"), dict) else {}
            rows.append(
                {
                    "Source Batch": batch_name,
                    "Batch Created At": batch_created_at,
                    "name": component_name,
                    "category": material.get("category"),
                    "manufacturer": manufacturer,
                    "Source Name": _text(component_metadata.get("source_name")) or _text(material_metadata.get("source_name")),
                    "Dry Mass Fraction (%)": component.get("Dry Mass Fraction (%)"),
                    "Post Processing": _text(component_metadata.get("post_processing")),
                }
            )

    if rows:
        return rows

    return [
        {
            "name": row.get("name"),
            "category": row.get("category"),
            "manufacturer": row.get("manufacturer"),
        }
        for row in material_rows
    ]


def _compute_descendants(
    connection: sqlite3.Connection,
    *,
    root_batch_id: int,
) -> list[dict[str, Any]]:
    parent_by_child: dict[int, int] = {}
    depth_by_id: dict[int, int] = {}
    descendant_ids: set[int] = set()
    queue: list[int] = [root_batch_id]
    branch_edges: list[sqlite3.Row] = []

    while queue:
        parent_id = queue.pop(0)
        edges = connection.execute(
            """
            SELECT *
            FROM ontology_lineage_edges
            WHERE parent_type = 'ELECTRODE_BATCH'
              AND child_type = 'ELECTRODE_BATCH'
              AND parent_id = ?
            ORDER BY id ASC
            """,
            (parent_id,),
        ).fetchall()
        for edge in edges:
            child_id = edge["child_id"]
            if child_id in descendant_ids:
                continue
            descendant_ids.add(child_id)
            parent_by_child[child_id] = parent_id
            depth_by_id[child_id] = depth_by_id.get(parent_id, 0) + 1
            branch_edges.append(edge)
            queue.append(child_id)

    batches = {
        row["id"]: _normalize_batch_row(row)
        for row in _fetch_rows_by_ids(connection, "ontology_electrode_batches", descendant_ids)
    }

    build_counts: dict[int, int] = {}
    legacy_counts: dict[int, int] = {}
    for batch_id in descendant_ids:
        build_count = connection.execute(
            """
            SELECT COUNT(*) AS row_count
            FROM ontology_lineage_edges
            WHERE parent_type = 'ELECTRODE_BATCH'
              AND child_type = 'CELL_BUILD'
              AND parent_id = ?
            """,
            (batch_id,),
        ).fetchone()["row_count"]
        legacy_count = connection.execute(
            """
            SELECT COUNT(*) AS row_count
            FROM ontology_lineage_edges
            WHERE parent_type = 'ELECTRODE_BATCH'
              AND child_type = 'EXPERIMENT'
              AND parent_id = ?
            """,
            (batch_id,),
        ).fetchone()["row_count"]
        build_counts[batch_id] = build_count
        legacy_counts[batch_id] = legacy_count

    descendants: list[dict[str, Any]] = []
    for batch_id, batch in sorted(batches.items(), key=lambda item: item[1]["batch_name"].lower()):
        path_names: list[str] = []
        current_id = batch_id
        while current_id in parent_by_child:
            parent_id = parent_by_child[current_id]
            if parent_id == root_batch_id:
                root_batch_name = connection.execute(
                    "SELECT batch_name FROM ontology_electrode_batches WHERE id = ?",
                    (root_batch_id,),
                ).fetchone()["batch_name"]
                path_names.append(root_batch_name)
                break
            parent_batch = batches.get(parent_id)
            if not parent_batch:
                break
            path_names.append(parent_batch["batch_name"])
            current_id = parent_id
        descendants.append(
            {
                "batch_id": batch_id,
                "batch_name": batch["batch_name"],
                "depth": depth_by_id[batch_id],
                "ancestor_path": list(reversed(path_names)),
                "study_focus": batch["metadata_json"].get("override_metadata", {}).get("study_focus")
                or batch["metadata_json"].get("study_focus"),
                "cell_build_count": build_counts.get(batch_id, 0),
                "legacy_experiment_count": legacy_counts.get(batch_id, 0),
            }
        )

    return descendants


@st.cache_data(show_spinner=False, ttl=60)
def load_ontology_batch_index() -> list[dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return []
    connection = _get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, batch_name, metadata_json
            FROM ontology_electrode_batches
            ORDER BY batch_name COLLATE NOCASE ASC
            """
        ).fetchall()
        payload = []
        for row in rows:
            metadata = _load_json(row["metadata_json"]) or {}
            payload.append(
                {
                    "id": row["id"],
                    "batch_name": row["batch_name"],
                    "parent_batch_name": metadata.get("parent_batch_name"),
                    "study_focus": metadata.get("override_metadata", {}).get("study_focus")
                    or metadata.get("study_focus"),
                }
            )
        return payload
    finally:
        connection.close()


@st.cache_data(show_spinner=False, ttl=60)
def load_ontology_cell_build_index() -> list[dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return []
    connection = _get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, build_name, chemistry, metadata_json
            FROM ontology_cell_builds
            ORDER BY build_name COLLATE NOCASE ASC
            """
        ).fetchall()
        payload = []
        for row in rows:
            metadata = _load_json(row["metadata_json"]) or {}
            payload.append(
                {
                    "id": row["id"],
                    "build_name": row["build_name"],
                    "chemistry": row["chemistry"],
                    "legacy_cell_name": metadata.get("legacy_cell_name"),
                }
            )
        return payload
    finally:
        connection.close()


@st.cache_data(show_spinner=False, ttl=60)
def load_ontology_legacy_experiment_index() -> list[dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return []
    connection = _get_connection()
    try:
        rows = connection.execute(
            """
            SELECT DISTINCT child_id AS legacy_experiment_id
            FROM ontology_lineage_edges
            WHERE child_type = 'EXPERIMENT'
            ORDER BY child_id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


@st.cache_data(show_spinner=False, ttl=60)
def load_batch_lineage_payload(batch_id: int) -> Optional[dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return None
    connection = _get_connection()
    try:
        batch_row = connection.execute(
            """
            SELECT
                b.*,
                m.name AS active_material_name,
                pr.name AS process_run_name,
                pr.process_type AS process_type
            FROM ontology_electrode_batches b
            LEFT JOIN ontology_materials m ON m.id = b.active_material_id
            LEFT JOIN ontology_process_runs pr ON pr.id = b.process_run_id
            WHERE b.id = ?
            """,
            (batch_id,),
        ).fetchone()
        if not batch_row:
            return None

        batch = _normalize_batch_row(dict(batch_row))
        incoming_edges = connection.execute(
            """
            SELECT *
            FROM ontology_lineage_edges
            WHERE child_type = 'ELECTRODE_BATCH'
              AND child_id = ?
            ORDER BY id ASC
            """,
            (batch_id,),
        ).fetchall()
        outgoing_edges = connection.execute(
            """
            SELECT *
            FROM ontology_lineage_edges
            WHERE parent_type = 'ELECTRODE_BATCH'
              AND parent_id = ?
            ORDER BY id ASC
            """,
            (batch_id,),
        ).fetchall()

        parent_batch_ids = [edge["parent_id"] for edge in incoming_edges if edge["parent_type"] == "ELECTRODE_BATCH"]
        child_batch_ids = [edge["child_id"] for edge in outgoing_edges if edge["child_type"] == "ELECTRODE_BATCH"]
        material_ids = [edge["parent_id"] for edge in incoming_edges if edge["parent_type"] == "MATERIAL"]
        cell_build_ids = [edge["child_id"] for edge in outgoing_edges if edge["child_type"] == "CELL_BUILD"]
        legacy_experiment_ids = [edge["child_id"] for edge in outgoing_edges if edge["child_type"] == "EXPERIMENT"]

        parent_batches = [_normalize_batch_row(row) for row in _fetch_rows_by_ids(connection, "ontology_electrode_batches", parent_batch_ids)]
        child_batches = [_normalize_batch_row(row) for row in _fetch_rows_by_ids(connection, "ontology_electrode_batches", child_batch_ids)]
        materials = _fetch_rows_by_ids(connection, "ontology_materials", material_ids)
        cell_builds = [_normalize_build_row(row) for row in _fetch_rows_by_ids(connection, "ontology_cell_builds", cell_build_ids)]
        descendants = _compute_descendants(connection, root_batch_id=batch_id)

        descendant_batch_ids = [item["batch_id"] for item in descendants]
        descendant_build_edges = []
        descendant_experiment_edges = []
        if descendant_batch_ids:
            placeholders = ",".join("?" for _ in descendant_batch_ids)
            descendant_build_edges = connection.execute(
                f"""
                SELECT *
                FROM ontology_lineage_edges
                WHERE parent_type = 'ELECTRODE_BATCH'
                  AND child_type = 'CELL_BUILD'
                  AND parent_id IN ({placeholders})
                ORDER BY id ASC
                """,
                descendant_batch_ids,
            ).fetchall()
            descendant_experiment_edges = connection.execute(
                f"""
                SELECT *
                FROM ontology_lineage_edges
                WHERE parent_type = 'ELECTRODE_BATCH'
                  AND child_type = 'EXPERIMENT'
                  AND parent_id IN ({placeholders})
                ORDER BY id ASC
                """,
                descendant_batch_ids,
            ).fetchall()

        descendant_cell_builds = [
            _normalize_build_row(row)
            for row in _fetch_rows_by_ids(
                connection,
                "ontology_cell_builds",
                [edge["child_id"] for edge in descendant_build_edges],
            )
        ]
        direct_legacy_experiments = _fetch_legacy_experiments(connection, legacy_experiment_ids)
        descendant_legacy_experiments = _fetch_legacy_experiments(
            connection,
            [edge["child_id"] for edge in descendant_experiment_edges],
        )

        return {
            "batch": batch,
            "parent_batches": sorted(parent_batches, key=lambda row: row["batch_name"].lower()),
            "child_batches": sorted(child_batches, key=lambda row: row["batch_name"].lower()),
            "formulation_materials": sorted(materials, key=lambda row: row["name"].lower()),
            "direct_cell_builds": sorted(cell_builds, key=lambda row: row["build_name"].lower()),
            "direct_legacy_experiments": direct_legacy_experiments,
            "descendants": descendants,
            "descendant_cell_builds": sorted(descendant_cell_builds, key=lambda row: row["build_name"].lower()),
            "descendant_legacy_experiments": descendant_legacy_experiments,
        }
    finally:
        connection.close()


@st.cache_data(show_spinner=False, ttl=60)
def load_cell_build_lineage_payload(build_id: int) -> Optional[dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return None
    connection = _get_connection()
    try:
        build_row = connection.execute(
            "SELECT * FROM ontology_cell_builds WHERE id = ?",
            (build_id,),
        ).fetchone()
        if not build_row:
            return None

        build = _normalize_build_row(dict(build_row))
        incoming_edges = connection.execute(
            """
            SELECT *
            FROM ontology_lineage_edges
            WHERE child_type = 'CELL_BUILD'
              AND child_id = ?
            ORDER BY id ASC
            """,
            (build_id,),
        ).fetchall()
        source_batch_ids = [edge["parent_id"] for edge in incoming_edges if edge["parent_type"] == "ELECTRODE_BATCH"]
        source_batches = [_normalize_batch_row(row) for row in _fetch_rows_by_ids(connection, "ontology_electrode_batches", source_batch_ids)]

        material_edges = []
        experiment_edges = []
        if source_batch_ids:
            placeholders = ",".join("?" for _ in source_batch_ids)
            material_edges = connection.execute(
                f"""
                SELECT *
                FROM ontology_lineage_edges
                WHERE parent_type = 'MATERIAL'
                  AND child_type = 'ELECTRODE_BATCH'
                  AND child_id IN ({placeholders})
                ORDER BY id ASC
                """,
                source_batch_ids,
            ).fetchall()
            experiment_edges = connection.execute(
                f"""
                SELECT *
                FROM ontology_lineage_edges
                WHERE parent_type = 'ELECTRODE_BATCH'
                  AND child_type = 'EXPERIMENT'
                  AND parent_id IN ({placeholders})
                ORDER BY id ASC
                """,
                source_batch_ids,
            ).fetchall()

        materials = _fetch_rows_by_ids(connection, "ontology_materials", [edge["parent_id"] for edge in material_edges])
        related_experiment_ids = [edge["child_id"] for edge in experiment_edges]
        if build.get("legacy_experiment_id"):
            related_experiment_ids.append(build["legacy_experiment_id"])
        legacy_experiments = _fetch_legacy_experiments(connection, related_experiment_ids)

        return {
            "cell_build": build,
            "source_batches": sorted(source_batches, key=lambda row: row["batch_name"].lower()),
            "source_materials": sorted(materials, key=lambda row: row["name"].lower()),
            "related_legacy_experiments": legacy_experiments,
        }
    finally:
        connection.close()


@st.cache_data(show_spinner=False, ttl=60)
def load_legacy_experiment_lineage_payload(legacy_experiment_id: int) -> dict[str, Any]:
    connection = _get_connection()
    try:
        incoming_edges = connection.execute(
            """
            SELECT *
            FROM ontology_lineage_edges
            WHERE parent_type = 'ELECTRODE_BATCH'
              AND child_type = 'EXPERIMENT'
              AND child_id = ?
            ORDER BY id ASC
            """,
            (legacy_experiment_id,),
        ).fetchall()
        source_batch_ids = [edge["parent_id"] for edge in incoming_edges]
        source_batches = [_normalize_batch_row(row) for row in _fetch_rows_by_ids(connection, "ontology_electrode_batches", source_batch_ids)]

        material_edges = []
        build_edges = []
        if source_batch_ids:
            placeholders = ",".join("?" for _ in source_batch_ids)
            material_edges = connection.execute(
                f"""
                SELECT *
                FROM ontology_lineage_edges
                WHERE parent_type = 'MATERIAL'
                  AND child_type = 'ELECTRODE_BATCH'
                  AND child_id IN ({placeholders})
                ORDER BY id ASC
                """,
                source_batch_ids,
            ).fetchall()
            build_edges = connection.execute(
                f"""
                SELECT *
                FROM ontology_lineage_edges
                WHERE parent_type = 'ELECTRODE_BATCH'
                  AND child_type = 'CELL_BUILD'
                  AND parent_id IN ({placeholders})
                ORDER BY id ASC
                """,
                source_batch_ids,
            ).fetchall()

        materials = _fetch_rows_by_ids(connection, "ontology_materials", [edge["parent_id"] for edge in material_edges])
        related_builds = [
            _normalize_build_row(row)
            for row in _fetch_rows_by_ids(connection, "ontology_cell_builds", [edge["child_id"] for edge in build_edges])
        ]
        experiments = _fetch_legacy_experiments(connection, [legacy_experiment_id])
        experiment = experiments[0] if experiments else {
            "legacy_experiment_id": legacy_experiment_id,
            "experiment_name": None,
            "project_id": None,
            "project_name": None,
        }

        return {
            "experiment": experiment,
            "source_batches": sorted(source_batches, key=lambda row: row["batch_name"].lower()),
            "source_materials": sorted(materials, key=lambda row: row["name"].lower()),
            "related_cell_builds": sorted(related_builds, key=lambda row: row["build_name"].lower()),
        }
    finally:
        connection.close()


def _render_table(
    title: str,
    rows: list[dict[str, Any]],
    preferred_columns: Optional[list[str]] = None,
) -> None:
    st.subheader(title)
    if not rows:
        st.caption("No records found.")
        return
    frame = pd.DataFrame(rows)
    if preferred_columns:
        visible_columns = [column for column in preferred_columns if column in frame.columns]
        remaining_columns = [column for column in frame.columns if column not in visible_columns]
        frame = frame[visible_columns + remaining_columns]
    st.dataframe(frame, use_container_width=True, hide_index=True)


def _build_cell_input_candidates(
    payload: dict[str, Any],
    *,
    highlighted_batch_name: Optional[str] = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    selected_batch = payload.get("batch") if isinstance(payload.get("batch"), dict) else {}
    selected_metadata = (
        selected_batch.get("metadata_json")
        if isinstance(selected_batch.get("metadata_json"), dict)
        else {}
    )
    selected_batch_id = selected_batch.get("id")
    if selected_batch_id is not None:
        seen_ids.add(int(selected_batch_id))
        candidates.append(
            {
                "batch_id": int(selected_batch_id),
                "batch_name": _text(selected_batch.get("batch_name")) or f"Batch {selected_batch_id}",
                "selection_label": "Selected parent batch",
                "study_focus": selected_metadata.get("override_metadata", {}).get("study_focus")
                or selected_metadata.get("study_focus"),
            }
        )

    descendants = payload.get("descendants") if isinstance(payload.get("descendants"), list) else []
    for row in descendants:
        if not isinstance(row, dict) or row.get("batch_id") is None:
            continue
        batch_id = int(row["batch_id"])
        if batch_id in seen_ids:
            continue
        seen_ids.add(batch_id)
        depth = row.get("depth")
        selection_label = "Descendant branch"
        if depth is not None:
            selection_label = f"Descendant branch · depth {depth}"
        candidates.append(
            {
                "batch_id": batch_id,
                "batch_name": _text(row.get("batch_name")) or f"Batch {batch_id}",
                "selection_label": selection_label,
                "study_focus": _text(row.get("study_focus")),
            }
        )

    if highlighted_batch_name:
        highlighted_key = highlighted_batch_name.casefold()
        candidates.sort(
            key=lambda row: (
                ((row.get("batch_name") or "").strip().casefold()) != highlighted_key,
                row.get("batch_id"),
            )
        )
    return candidates


def render_lineage_explorer(
    *,
    open_batch_in_cell_inputs_callback: Optional[Callable[[int], bool]] = None,
) -> None:
    st.header("🧬 Lineage Explorer")
    st.caption("Temporary ontology explorer backed by the CellScope 2.0 ontology database.")

    if not ONTOLOGY_DB_PATH.exists():
        st.info(
            f"Ontology database not found at `{ONTOLOGY_DB_PATH}`. Run the ontology import first."
        )
        return

    batch_index = load_ontology_batch_index()
    cell_build_index = load_ontology_cell_build_index()
    legacy_experiment_index = load_ontology_legacy_experiment_index()

    if not batch_index:
        st.info("No ontology batches have been imported yet.")
        return

    mode_options = ["Electrode Batch", "Cell Build", "Legacy Experiment ID"]
    if st.session_state.get(LINEAGE_MODE_KEY) not in mode_options:
        st.session_state[LINEAGE_MODE_KEY] = "Electrode Batch"
    focus_request = st.session_state.get(LINEAGE_FOCUS_REQUEST_KEY, {})

    mode = st.radio(
        "Explore by",
        options=mode_options,
        horizontal=True,
        key=LINEAGE_MODE_KEY,
    )

    if mode == "Electrode Batch":
        parent_batch_index = [
            item for item in batch_index
            if not _text(item.get("parent_batch_name"))
        ]
        batch_lookup = {
            item["batch_name"]: item
            for item in parent_batch_index
        }
        batch_options = list(batch_lookup.keys())
        if not batch_options:
            st.info("No parent batches are available to explore yet.")
            return
        if st.session_state.get(LINEAGE_BATCH_SELECT_KEY) not in batch_options:
            st.session_state[LINEAGE_BATCH_SELECT_KEY] = batch_options[0]

        selected_batch_name = st.selectbox(
            "Select a parent batch",
            options=batch_options,
            key=LINEAGE_BATCH_SELECT_KEY,
        )
        st.caption("Child and sub-branch experiments are shown through the lineage tables below.")
        payload = load_batch_lineage_payload(batch_lookup[selected_batch_name]["id"])
        if not payload:
            st.warning("Unable to load lineage for that batch.")
            return

        highlighted_batch_name = None
        highlighted_experiment_id = None
        if _text(focus_request.get("root_batch_name")) == _text(selected_batch_name):
            highlighted_batch_name = _text(focus_request.get("batch_name"))
            highlighted_experiment_id = focus_request.get("legacy_experiment_id")
            focus_bits = []
            if focus_request.get("legacy_experiment_name"):
                focus_bits.append(f"legacy experiment {focus_request['legacy_experiment_name']}")
            elif highlighted_experiment_id:
                focus_bits.append(f"legacy experiment ID {highlighted_experiment_id}")
            if highlighted_batch_name and highlighted_batch_name != _text(selected_batch_name):
                focus_bits.append(f"branch {highlighted_batch_name}")
            linked_build_names = focus_request.get("linked_cell_build_names") or []
            if linked_build_names:
                preview_names = ", ".join(str(name) for name in linked_build_names[:3])
                if len(linked_build_names) > 3:
                    preview_names += ", ..."
                focus_bits.append(f"cell builds {preview_names}")
            if focus_bits:
                st.info("Focused from " + " | ".join(focus_bits))

        batch = payload["batch"]
        metadata = batch["metadata_json"]
        summary_cols = st.columns(4)
        summary_cols[0].metric("Batch", batch["batch_name"])
        summary_cols[1].metric("Parent", metadata.get("parent_batch_name") or "Root")
        summary_cols[2].metric("Children", len(payload["child_batches"]))
        summary_cols[3].metric("Descendants", len(payload["descendants"]))

        detail_cols = st.columns(3)
        detail_cols[0].metric("Active Material", batch.get("active_material_name") or "Unknown")
        detail_cols[1].metric("Process", batch.get("process_run_name") or "Unknown")
        detail_cols[2].metric(
            "Study Focus",
            metadata.get("override_metadata", {}).get("study_focus")
            or metadata.get("study_focus")
            or "Unspecified",
        )

        cell_input_candidates = _build_cell_input_candidates(
            payload,
            highlighted_batch_name=highlighted_batch_name,
        )
        if cell_input_candidates:
            candidate_lookup = {
                int(candidate["batch_id"]): candidate
                for candidate in cell_input_candidates
            }
            candidate_ids = list(candidate_lookup)
            preferred_candidate_id = candidate_ids[0]
            if highlighted_batch_name:
                highlighted_key = highlighted_batch_name.casefold()
                for candidate in cell_input_candidates:
                    if ((candidate.get("batch_name") or "").strip().casefold()) == highlighted_key:
                        preferred_candidate_id = int(candidate["batch_id"])
                        break
            if st.session_state.get(LINEAGE_CELL_INPUT_BATCH_SELECT_KEY) not in candidate_ids:
                st.session_state[LINEAGE_CELL_INPUT_BATCH_SELECT_KEY] = preferred_candidate_id

            selected_candidate_id = st.selectbox(
                "Batch to prepare in Cell Inputs",
                options=candidate_ids,
                key=LINEAGE_CELL_INPUT_BATCH_SELECT_KEY,
                format_func=lambda value: (
                    f"{candidate_lookup[value]['batch_name']} | {candidate_lookup[value]['selection_label']}"
                ),
            )
            selected_candidate = candidate_lookup[int(selected_candidate_id)]
            selected_template = build_batch_cell_inputs_template(batch_id=int(selected_candidate_id))

            with st.container(border=True):
                st.markdown("### Cell Inputs Connector")
                st.caption(
                    "Pull the canonical formulation, electrolyte, separator, cutoff voltages, and ontology context into Cell Inputs, then drop in the csv/xlsx files."
                )
                preview_bits = [selected_candidate.get("selection_label")]
                if selected_template:
                    preview_bits.extend(
                        [
                            selected_template.get("project_name"),
                            selected_template.get("preferred_experiment_name"),
                            (
                                f"{len(selected_template.get('formulation') or [])} formulation component(s)"
                                if selected_template.get("formulation")
                                else "No saved formulation yet"
                            ),
                        ]
                    )
                    defaults = selected_template.get("cell_inputs_defaults") or {}
                    if defaults.get("electrolyte"):
                        preview_bits.append(f"Electrolyte: {defaults['electrolyte']}")
                if selected_candidate.get("study_focus"):
                    preview_bits.append(f"Study focus: {selected_candidate['study_focus']}")
                st.caption(" | ".join(bit for bit in preview_bits if bit))

                if selected_template and not selected_template.get("project_id") and not selected_template.get("project_name"):
                    st.info(
                        "This batch does not have a default legacy project yet. If a project is already active in the sidebar, that project will be used for the Cell Inputs handoff."
                    )

                if st.button(
                    "Prepare in Cell Inputs",
                    key="lineage_prepare_cell_inputs",
                    use_container_width=True,
                    disabled=open_batch_in_cell_inputs_callback is None,
                ):
                    if open_batch_in_cell_inputs_callback and open_batch_in_cell_inputs_callback(int(selected_candidate_id)):
                        st.rerun()

        st.markdown("### Overview")
        overview_rows = [
            {"Field": "Batch Name", "Value": batch["batch_name"]},
            {"Field": "Created At", "Value": batch.get("created_at")},
            {"Field": "Electrode Role", "Value": batch.get("electrode_role")},
            {"Field": "Source Kind", "Value": metadata.get("source_kind") or metadata.get("source_origin")},
            {"Field": "Active Material Source", "Value": metadata.get("active_material_source")},
            {"Field": "Default Electrolyte", "Value": metadata.get("electrolyte") or metadata.get("default_electrolyte")},
            {"Field": "Variant Descriptor", "Value": metadata.get("variant_descriptor")},
        ]
        _render_table("Batch Details", [row for row in overview_rows if row["Value"]], ["Field", "Value"])

        formulation_rows = []
        for component in batch.get("formulation_json", []):
            metadata_json = component.get("metadata", {}) if isinstance(component, dict) else {}
            formulation_rows.append(
                {
                    "Component": component.get("Component"),
                    "Dry Mass Fraction (%)": component.get("Dry Mass Fraction (%)"),
                    "Post Processing": metadata_json.get("post_processing"),
                    "Descriptor": metadata_json.get("variant_descriptor"),
                }
            )
        _render_table(
            "Formulation",
            formulation_rows,
            ["Component", "Dry Mass Fraction (%)", "Post Processing", "Descriptor"],
        )
        _render_table(
            "Source Materials",
            _build_contextual_source_material_rows([batch], payload["formulation_materials"]),
            ["Source Batch", "Batch Created At", "name", "category", "manufacturer", "Source Name", "Dry Mass Fraction (%)", "Post Processing"],
        )
        _render_table(
            "Parent Batches",
            payload["parent_batches"],
            ["batch_name", "created_at", "electrode_role"],
        )
        child_batch_rows = [
            {
                **row,
                **(
                    {"focus_match": _text(row.get("batch_name")) == highlighted_batch_name}
                    if highlighted_batch_name else {}
                ),
            }
            for row in payload["child_batches"]
        ]
        _render_table(
            "Child Batches",
            child_batch_rows,
            ["batch_name", "created_at", "electrode_role", "focus_match"],
        )
        descendant_rows = [
            {
                **row,
                **(
                    {"focus_match": _text(row.get("batch_name")) == highlighted_batch_name}
                    if highlighted_batch_name else {}
                ),
            }
            for row in payload["descendants"]
        ]
        _render_table(
            "Descendant Branches",
            descendant_rows,
            ["batch_name", "focus_match", "depth", "ancestor_path", "study_focus", "cell_build_count", "legacy_experiment_count"],
        )
        _render_table(
            "Direct Cell Builds",
            payload["direct_cell_builds"],
            ["build_name", "chemistry", "legacy_test_number"],
        )
        _render_table(
            "Descendant Cell Builds",
            payload["descendant_cell_builds"],
            ["build_name", "chemistry", "legacy_test_number"],
        )
        _render_table(
            "Direct Legacy Experiments",
            [
                {
                    **row,
                    **(
                        {"focus_match": row.get("legacy_experiment_id") == highlighted_experiment_id}
                        if highlighted_experiment_id else {}
                    ),
                }
                for row in payload["direct_legacy_experiments"]
            ],
            ["legacy_experiment_id", "focus_match", "experiment_name", "project_name"],
        )
        _render_table(
            "Descendant Legacy Experiments",
            [
                {
                    **row,
                    **(
                        {"focus_match": row.get("legacy_experiment_id") == highlighted_experiment_id}
                        if highlighted_experiment_id else {}
                    ),
                }
                for row in payload["descendant_legacy_experiments"]
            ],
            ["legacy_experiment_id", "focus_match", "experiment_name", "project_name"],
        )
        with st.expander("Raw Metadata", expanded=False):
            st.json(metadata)

    elif mode == "Cell Build":
        build_lookup = {item["build_name"]: item for item in cell_build_index}
        build_options = list(build_lookup.keys())
        if not build_options:
            st.info("No ontology cell builds are currently available.")
            return
        if st.session_state.get(LINEAGE_BUILD_SELECT_KEY) not in build_options:
            st.session_state[LINEAGE_BUILD_SELECT_KEY] = build_options[0]
        selected_build_name = st.selectbox(
            "Select a cell build",
            options=build_options,
            key=LINEAGE_BUILD_SELECT_KEY,
        )
        payload = load_cell_build_lineage_payload(build_lookup[selected_build_name]["id"])
        if not payload:
            st.warning("Unable to load lineage for that cell build.")
            return

        build = payload["cell_build"]
        metadata = build["metadata_json"]
        build_cols = st.columns(4)
        build_cols[0].metric("Build", build["build_name"])
        build_cols[1].metric("Chemistry", build.get("chemistry") or "Unknown")
        build_cols[2].metric("Source Batches", len(payload["source_batches"]))
        build_cols[3].metric("Related Legacy Experiments", len(payload["related_legacy_experiments"]))

        _render_table(
            "Source Batches",
            payload["source_batches"],
            ["batch_name", "created_at", "electrode_role"],
        )
        _render_table(
            "Source Materials",
            _build_contextual_source_material_rows(payload["source_batches"], payload["source_materials"]),
            ["Source Batch", "Batch Created At", "name", "category", "manufacturer", "Source Name", "Dry Mass Fraction (%)", "Post Processing"],
        )
        _render_table(
            "Related Legacy Experiments",
            payload["related_legacy_experiments"],
            ["legacy_experiment_id", "experiment_name", "project_name"],
        )
        with st.expander("Build Metadata", expanded=False):
            st.json(metadata)

    else:
        if not legacy_experiment_index:
            st.info("No ontology-linked legacy experiments are currently available.")
            return

        available_ids = [item["legacy_experiment_id"] for item in legacy_experiment_index]
        if st.session_state.get(LINEAGE_LEGACY_EXPERIMENT_SELECT_KEY) not in available_ids:
            st.session_state[LINEAGE_LEGACY_EXPERIMENT_SELECT_KEY] = available_ids[0]
        selected_legacy_experiment_id = st.selectbox(
            "Select a legacy experiment ID",
            options=available_ids,
            format_func=lambda value: f"Legacy Experiment {value}",
            key=LINEAGE_LEGACY_EXPERIMENT_SELECT_KEY,
        )
        payload = load_legacy_experiment_lineage_payload(int(selected_legacy_experiment_id))
        experiment = payload["experiment"]

        exp_cols = st.columns(4)
        exp_cols[0].metric("Legacy Experiment ID", experiment["legacy_experiment_id"])
        exp_cols[1].metric("Experiment Name", experiment.get("experiment_name") or "Unknown")
        exp_cols[2].metric("Project", experiment.get("project_name") or "Unknown")
        exp_cols[3].metric("Source Batches", len(payload["source_batches"]))

        _render_table(
            "Source Batches",
            payload["source_batches"],
            ["batch_name", "created_at", "electrode_role"],
        )
        _render_table(
            "Source Materials",
            _build_contextual_source_material_rows(payload["source_batches"], payload["source_materials"]),
            ["Source Batch", "Batch Created At", "name", "category", "manufacturer", "Source Name", "Dry Mass Fraction (%)", "Post Processing"],
        )
        _render_table(
            "Related Cell Builds",
            payload["related_cell_builds"],
            ["build_name", "chemistry", "legacy_test_number"],
        )
