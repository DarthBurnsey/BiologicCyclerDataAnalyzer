"""Streamlit Batch Builder page for ontology-backed batch authoring."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional

import pandas as pd
import streamlit as st

from batch_builder_service import (
    BRANCH_TYPE_OPTIONS,
    CELL_FORMAT_OPTIONS,
    ELECTRODE_ROLE_OPTIONS,
    EQUIPMENT_TYPE_OPTIONS,
    MATERIAL_CATEGORY_OPTIONS,
    PROCESS_TYPE_OPTIONS,
    PROTOCOL_TYPE_OPTIONS,
    build_batch_cell_inputs_template,
    build_experiment_additional_data_from_template,
    create_batch_record,
    create_material_record,
    default_formulation_rows,
    list_batches,
    list_legacy_projects,
    list_materials,
    update_material_record,
)
from ontology_explorer import queue_lineage_explorer_focus
from ontology_workflow import clear_ontology_workflow_caches


BATCH_BUILDER_REQUEST_KEY = "batch_builder_cell_inputs_request"
BATCH_BUILDER_ACTIVE_TEMPLATE_KEY = "batch_builder_active_template"
BATCH_BUILDER_ADDITIONAL_DATA_KEY = "batch_builder_experiment_additional_data"


@st.cache_data(ttl=30, show_spinner=False)
def _load_project_rows() -> list[dict[str, Any]]:
    return list_legacy_projects()


@st.cache_data(ttl=30, show_spinner=False)
def _load_material_rows() -> list[dict[str, Any]]:
    return list_materials()


@st.cache_data(ttl=30, show_spinner=False)
def _load_batch_rows() -> list[dict[str, Any]]:
    return list_batches()


@st.cache_data(ttl=30, show_spinner=False)
def _load_root_batch_rows() -> list[dict[str, Any]]:
    return list_batches(roots_only=True)


def _invalidate_builder_caches() -> None:
    _load_project_rows.clear()
    _load_material_rows.clear()
    _load_batch_rows.clear()
    _load_root_batch_rows.clear()
    clear_ontology_workflow_caches()
    st.cache_data.clear()


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_aliases(raw_value: str) -> list[str]:
    if not raw_value:
        return []
    pieces = []
    for chunk in raw_value.replace("\n", ",").split(","):
        text = _text(chunk)
        if text:
            pieces.append(text)
    seen: set[str] = set()
    output: list[str] = []
    for item in pieces:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _parse_json_dict(raw_value: str, *, label: str) -> dict[str, Any]:
    text = _text(raw_value)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return payload


def _project_label(project: dict[str, Any]) -> str:
    return f"{project['name']} • {project.get('project_type') or 'Unknown'}"


def _batch_label(batch: dict[str, Any]) -> str:
    parent = _text(batch.get("parent_batch_name"))
    if parent:
        return f"{batch['batch_name']} • child of {parent}"
    return f"{batch['batch_name']} • root batch"


def _default_substrate_for_role(electrode_role: str) -> str:
    return "Copper" if electrode_role == "anode" else "Aluminum"


def _build_formulation_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    normalized_rows = []
    for row in rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        normalized_rows.append(
            {
                "Component": row.get("Component") or row.get("name") or "",
                "Category": row.get("Category") or row.get("category") or "other",
                "Dry Mass Fraction (%)": row.get("Dry Mass Fraction (%)"),
                "Manufacturer": metadata.get("manufacturer_hint") or row.get("Manufacturer") or "",
                "Source Name": metadata.get("source_name") or row.get("Source Name") or "",
                "Post Processing": metadata.get("post_processing") or row.get("Post Processing") or "",
                "Notes": metadata.get("component_notes") or row.get("Notes") or "",
            }
        )
    if not normalized_rows:
        normalized_rows = default_formulation_rows("cathode")
    return pd.DataFrame(normalized_rows)


def _normalize_inline_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _extract_formulation_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for raw_row in frame.to_dict(orient="records"):
        component_name = _text(raw_row.get("Component"))
        if not component_name:
            continue
        rows.append(
            {
                "Component": component_name,
                "Category": _text(raw_row.get("Category")) or "other",
                "Dry Mass Fraction (%)": _coerce_float(raw_row.get("Dry Mass Fraction (%)")),
                "Manufacturer": _text(raw_row.get("Manufacturer")),
                "Source Name": _text(raw_row.get("Source Name")) or component_name,
                "Post Processing": _text(raw_row.get("Post Processing")),
                "Notes": _text(raw_row.get("Notes")),
            }
        )
    return rows


def _render_material_library_section(material_rows: list[dict[str, Any]]) -> None:
    st.markdown("#### Material Library")
    st.caption("Keep core materials reusable so future batch authoring and automated ingestion use the same canonical names.")

    material_header_cols = st.columns([0.78, 0.22])
    with material_header_cols[0]:
        st.markdown("##### Canonical Materials")
    material_button_label = "Close Material Form" if st.session_state.get("batch_builder_show_material_form") else "Add New Material"
    if material_header_cols[1].button(material_button_label, use_container_width=True, key="batch_builder_toggle_material_form"):
        st.session_state["batch_builder_show_material_form"] = not st.session_state.get("batch_builder_show_material_form", False)
        st.rerun()

    material_table = [
        {
            "Name": row.get("name"),
            "Category": row.get("category"),
            "Manufacturer": row.get("manufacturer") or "",
            "Description": row.get("description") or "",
            "Created": str(row.get("created_at") or "")[:10],
        }
        for row in material_rows
    ]
    if material_table:
        material_editor = st.data_editor(
            pd.DataFrame(material_table),
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=["Name", "Category", "Created"],
            key="batch_builder_material_library_editor",
        )
        if st.button("Save Material Edits", use_container_width=True, key="batch_builder_material_library_save"):
            try:
                updates_made = 0
                original_rows = {row["Name"]: row for row in material_table}
                for edited_row in material_editor.to_dict(orient="records"):
                    material_name = _normalize_inline_text(edited_row.get("Name"))
                    if not material_name or material_name not in original_rows:
                        continue
                    original_row = original_rows[material_name]
                    new_manufacturer = _normalize_inline_text(edited_row.get("Manufacturer"))
                    new_description = _normalize_inline_text(edited_row.get("Description"))
                    if (
                        new_manufacturer == _normalize_inline_text(original_row.get("Manufacturer"))
                        and new_description == _normalize_inline_text(original_row.get("Description"))
                    ):
                        continue
                    update_material_record(
                        name=material_name,
                        manufacturer=new_manufacturer or None,
                        description=new_description or None,
                    )
                    updates_made += 1
            except Exception as exc:
                st.error(str(exc))
            else:
                if updates_made:
                    _invalidate_builder_caches()
                    st.success(f"Updated {updates_made} material record(s).")
                    st.rerun()
                else:
                    st.info("No material changes to save.")
    else:
        st.info("No canonical materials exist yet.")

    if st.session_state.get("batch_builder_show_material_form"):
        st.markdown("##### Add Material")
        material_col1, material_col2, material_col3 = st.columns(3)
        with material_col1:
            material_name = st.text_input("Material Name", key="batch_builder_material_name", placeholder="e.g. Hx-T")
        with material_col2:
            material_category = st.selectbox("Category", MATERIAL_CATEGORY_OPTIONS, key="batch_builder_material_category")
        with material_col3:
            material_manufacturer = st.text_input("Manufacturer", key="batch_builder_material_manufacturer", placeholder="Optional")
        material_description = st.text_area("Description", key="batch_builder_material_description", height=80)
        material_metadata_raw = st.text_area(
            "Structured Metadata (JSON)",
            key="batch_builder_material_metadata",
            height=90,
            placeholder='{"source_name": "Hx-T", "default_supplier": "Hexegen"}',
        )
        material_action_cols = st.columns(2)
        if material_action_cols[0].button("Create Material", type="primary", use_container_width=True, key="batch_builder_material_submit"):
            try:
                material_metadata = _parse_json_dict(material_metadata_raw, label="Structured Metadata")
                create_material_record(
                    name=material_name,
                    category=material_category,
                    manufacturer=material_manufacturer,
                    description=material_description,
                    metadata=material_metadata,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.session_state["batch_builder_show_material_form"] = False
                _invalidate_builder_caches()
                st.success(f"Saved material `{material_name}`.")
                st.rerun()
        if material_action_cols[1].button("Cancel", use_container_width=True, key="batch_builder_material_cancel"):
            st.session_state["batch_builder_show_material_form"] = False
            st.rerun()


def queue_batch_builder_cell_inputs_request(template: dict[str, Any]) -> None:
    st.session_state[BATCH_BUILDER_REQUEST_KEY] = template


def clear_batch_builder_cell_input_state(*, preserve_request: bool = False) -> None:
    if not preserve_request:
        st.session_state.pop(BATCH_BUILDER_REQUEST_KEY, None)
    st.session_state.pop(BATCH_BUILDER_ACTIVE_TEMPLATE_KEY, None)
    st.session_state.pop(BATCH_BUILDER_ADDITIONAL_DATA_KEY, None)


def get_active_batch_builder_template() -> Optional[dict[str, Any]]:
    template = st.session_state.get(BATCH_BUILDER_ACTIVE_TEMPLATE_KEY)
    return template if isinstance(template, dict) else None


def get_active_batch_builder_additional_data() -> dict[str, Any]:
    additional_data = st.session_state.get(BATCH_BUILDER_ADDITIONAL_DATA_KEY)
    return additional_data if isinstance(additional_data, dict) else {}


def apply_batch_builder_cell_input_request() -> Optional[dict[str, Any]]:
    template = st.session_state.pop(BATCH_BUILDER_REQUEST_KEY, None)
    if not isinstance(template, dict):
        return None

    defaults = template.get("cell_inputs_defaults") or {}
    experiment_date_value = defaults.get("experiment_date")
    parsed_experiment_date = date.today()
    if experiment_date_value:
        try:
            parsed_experiment_date = datetime.fromisoformat(str(experiment_date_value)).date()
        except Exception:
            try:
                parsed_experiment_date = datetime.strptime(str(experiment_date_value)[:10], "%Y-%m-%d").date()
            except Exception:
                parsed_experiment_date = date.today()

    st.session_state["current_experiment_name"] = template.get("preferred_experiment_name") or template.get("batch_name") or ""
    st.session_state["main_experiment_name"] = st.session_state["current_experiment_name"]
    st.session_state["current_experiment_date"] = parsed_experiment_date
    st.session_state["current_disc_diameter_mm"] = defaults.get("disc_diameter_mm") or 15.0
    st.session_state["current_group_assignments"] = None
    st.session_state["current_group_names"] = ["Group A", "Group B", "Group C"]
    if defaults.get("solids_content") is not None:
        st.session_state["solids_content"] = defaults.get("solids_content")
    if defaults.get("pressed_thickness") is not None:
        st.session_state["pressed_thickness"] = defaults.get("pressed_thickness")
    st.session_state["experiment_notes"] = template.get("experiment_notes") or ""
    st.session_state["current_cell_format"] = defaults.get("cell_format") or "Coin"

    if defaults.get("loading_mg") is not None:
        st.session_state["loading_0"] = defaults.get("loading_mg")
    if defaults.get("active_material_pct") is not None:
        st.session_state["active_0"] = defaults.get("active_material_pct")
    if defaults.get("formation_cycles") is not None:
        st.session_state["formation_cycles_0"] = defaults.get("formation_cycles")
    if defaults.get("electrolyte"):
        st.session_state["electrolyte_0"] = defaults.get("electrolyte")
    if defaults.get("substrate"):
        st.session_state["substrate_0"] = defaults.get("substrate")
    if defaults.get("separator"):
        st.session_state["separator_0"] = defaults.get("separator")
    if defaults.get("cutoff_voltage_lower") is not None:
        st.session_state["cutoff_lower_0"] = defaults.get("cutoff_voltage_lower")
    if defaults.get("cutoff_voltage_upper") is not None:
        st.session_state["cutoff_upper_0"] = defaults.get("cutoff_voltage_upper")
    if defaults.get("formulation"):
        st.session_state["formulation_data_formulation_0_main_cell_inputs"] = defaults.get("formulation")
        st.session_state["use_same_formulation_main_cell_inputs"] = True

    st.session_state[BATCH_BUILDER_ACTIVE_TEMPLATE_KEY] = template
    st.session_state[BATCH_BUILDER_ADDITIONAL_DATA_KEY] = build_experiment_additional_data_from_template(template)
    return template


def _prepare_process_payload(prefix: str) -> dict[str, Any]:
    capture_process = st.checkbox(
        "Capture process run details",
        key=f"{prefix}_capture_process",
        help="Store process, protocol, operator, and equipment metadata alongside the batch.",
    )
    if not capture_process:
        return {}

    process_col1, process_col2, process_col3 = st.columns(3)
    with process_col1:
        process_name = st.text_input("Process Run Name", key=f"{prefix}_process_name", placeholder="e.g. N17 slurry build")
        process_type = st.selectbox("Process Type", PROCESS_TYPE_OPTIONS, key=f"{prefix}_process_type")
        process_started_at = st.date_input("Started", value=date.today(), key=f"{prefix}_process_started")
    with process_col2:
        protocol_name = st.text_input("Protocol Name", key=f"{prefix}_protocol_name", placeholder="e.g. Cathode Coating SOP")
        protocol_version = st.text_input("Protocol Version", key=f"{prefix}_protocol_version", placeholder="e.g. v1")
        protocol_type = st.selectbox("Protocol Type", PROTOCOL_TYPE_OPTIONS, key=f"{prefix}_protocol_type")
    with process_col3:
        operator_name = st.text_input("Operator", key=f"{prefix}_operator_name", placeholder="Optional")
        equipment_name = st.text_input("Equipment", key=f"{prefix}_equipment_name", placeholder="Optional")
        equipment_type = st.selectbox("Equipment Type", EQUIPMENT_TYPE_OPTIONS, key=f"{prefix}_equipment_type")

    process_settings_raw = st.text_area(
        "Structured Process Settings (JSON)",
        key=f"{prefix}_process_settings",
        height=110,
        placeholder='{"mix_rpm": 1200, "calendar_gap_um": 95}',
    )
    process_notes = st.text_area("Process Notes", key=f"{prefix}_process_notes", height=90)
    return {
        "process_name": process_name,
        "process_type": process_type,
        "process_started_at": process_started_at,
        "process_completed_at": process_started_at,
        "protocol_name": protocol_name,
        "protocol_version": protocol_version,
        "protocol_type": protocol_type,
        "operator_name": operator_name,
        "equipment_name": equipment_name,
        "equipment_type": equipment_type,
        "process_settings_raw": process_settings_raw,
        "process_notes": process_notes,
    }


def _render_batch_defaults_panel(
    prefix: str,
    *,
    project_options: list[dict[str, Any]],
    default_project_id: Optional[int],
    electrode_role: str,
    preferred_name_default: str,
    study_focus_default: str = "",
    electrolyte_default: str = "",
    separator_default: str = "25um PP",
    substrate_default: Optional[str] = None,
) -> dict[str, Any]:
    project_ids = [None] + [project["id"] for project in project_options]
    default_project_index = project_ids.index(default_project_id) if default_project_id in project_ids else 0
    default_substrate = substrate_default or _default_substrate_for_role(electrode_role)

    identity_col1, identity_col2, identity_col3 = st.columns(3)
    with identity_col1:
        selected_project_id = st.selectbox(
            "Default Project",
            options=project_ids,
            index=default_project_index,
            key=f"{prefix}_project_id",
            format_func=lambda value: "No default project" if value is None else _project_label(next(project for project in project_options if project["id"] == value)),
        )
        preferred_experiment_name = st.text_input(
            "Preferred Experiment Name",
            key=f"{prefix}_preferred_experiment_name",
            value=preferred_name_default,
        )
        experiment_prefix = st.text_input(
            "Experiment Prefix",
            key=f"{prefix}_experiment_prefix",
            value=preferred_name_default,
            help="Future ingestion systems can use this as the preferred experiment prefix.",
        )
    with identity_col2:
        study_focus = st.text_input("Study Focus", key=f"{prefix}_study_focus", value=study_focus_default)
        aliases = st.text_input(
            "Batch / Connector Aliases",
            key=f"{prefix}_aliases",
            help="Comma-separated aliases used in notes, cycler exports, or legacy filenames.",
        )
        cell_build_naming = st.text_input(
            "Future Cell Naming Pattern",
            key=f"{prefix}_cell_build_naming",
            value="{experiment_name} {roman_index}",
            help="Forward-looking hint for direct cycler / build synchronization.",
        )
    with identity_col3:
        cell_format = st.selectbox("Cell Format", CELL_FORMAT_OPTIONS, key=f"{prefix}_cell_format")
        expected_cell_count = st.number_input(
            "Expected Cell Count",
            min_value=0,
            step=1,
            key=f"{prefix}_expected_cell_count",
            value=0,
            help="Optional hint for future automatic cycler-to-batch matching.",
        )
        launch_after_save = st.checkbox(
            "Launch in Cell Inputs after save",
            key=f"{prefix}_launch_after_save",
            value=True,
        )

    defaults_col1, defaults_col2, defaults_col3, defaults_col4 = st.columns(4)
    with defaults_col1:
        default_disc_diameter_mm = st.number_input(
            "Disc Diameter (mm)",
            min_value=0.0,
            step=0.1,
            value=15.0,
            key=f"{prefix}_disc_diameter",
        )
        default_loading_mg = st.number_input(
            "Default Disc Loading (mg)",
            min_value=0.0,
            step=0.1,
            value=0.0,
            key=f"{prefix}_default_loading",
        )
    with defaults_col2:
        solids_content_pct = st.number_input(
            "Solids Content (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            value=0.0,
            key=f"{prefix}_solids_content",
        )
        pressed_thickness_um = st.number_input(
            "Pressed Thickness (um)",
            min_value=0.0,
            step=0.1,
            value=0.0,
            key=f"{prefix}_pressed_thickness",
        )
    with defaults_col3:
        electrolyte_hint = st.text_input("Default Electrolyte", key=f"{prefix}_electrolyte", value=electrolyte_default)
        substrate_hint = st.text_input("Default Substrate", key=f"{prefix}_substrate", value=default_substrate)
    with defaults_col4:
        separator_hint = st.text_input("Default Separator", key=f"{prefix}_separator", value=separator_default)
        formation_cycles = st.number_input("Formation Cycles", min_value=0, step=1, value=4, key=f"{prefix}_formation_cycles")

    cutoff_col1, cutoff_col2, cutoff_col3 = st.columns(3)
    with cutoff_col1:
        cutoff_voltage_lower = st.number_input(
            "Lower Cutoff (V)",
            min_value=0.0,
            max_value=10.0,
            step=0.1,
            value=2.5,
            key=f"{prefix}_cutoff_lower",
        )
    with cutoff_col2:
        cutoff_voltage_upper = st.number_input(
            "Upper Cutoff (V)",
            min_value=0.0,
            max_value=10.0,
            step=0.1,
            value=4.2,
            key=f"{prefix}_cutoff_upper",
        )
    with cutoff_col3:
        branch_type = st.selectbox("Branch Type", BRANCH_TYPE_OPTIONS, key=f"{prefix}_branch_type")

    selected_project_name = None
    if selected_project_id is not None:
        selected_project_name = next(
            (project["name"] for project in project_options if project["id"] == selected_project_id),
            None,
        )

    return {
        "target_project_id": selected_project_id,
        "target_project_name": selected_project_name,
        "preferred_experiment_name": preferred_experiment_name,
        "experiment_prefix": experiment_prefix,
        "study_focus": study_focus,
        "ingestion_aliases": _parse_aliases(aliases),
        "cell_build_naming": cell_build_naming,
        "cell_format": cell_format,
        "expected_cell_count": expected_cell_count or None,
        "launch_after_save": launch_after_save,
        "default_disc_diameter_mm": default_disc_diameter_mm or None,
        "default_loading_mg": default_loading_mg or None,
        "solids_content_pct": solids_content_pct or None,
        "pressed_thickness_um": pressed_thickness_um or None,
        "electrolyte_hint": _text(electrolyte_hint),
        "substrate_hint": _text(substrate_hint),
        "separator_hint": _text(separator_hint),
        "formation_cycles": formation_cycles,
        "cutoff_voltage_lower": cutoff_voltage_lower,
        "cutoff_voltage_upper": cutoff_voltage_upper,
        "branch_type": branch_type,
    }


def _submit_created_batch(
    created_batch: dict[str, Any],
    *,
    launch_after_save: bool,
    activate_project_callback: Callable[[int, str, bool], None],
) -> None:
    _invalidate_builder_caches()
    st.success(f"Saved canonical batch `{created_batch['batch_name']}`.")
    template = build_batch_cell_inputs_template(batch_id=created_batch["id"])
    if not launch_after_save or not template:
        return
    project_id = template.get("project_id")
    project_name = template.get("project_name")
    if not project_id or not project_name:
        st.info("The batch is saved. Add a default project in the batch metadata before sending it to Cell Inputs.")
        return
    queue_batch_builder_cell_inputs_request(template)
    st.session_state["_sidebar_pending_project_selector"] = project_id
    activate_project_callback(project_id, project_name, True)
    st.rerun()


def render_batch_builder(
    *,
    activate_project_callback: Callable[[int, str, bool], None],
    current_project_id: Optional[int] = None,
    current_project_name: Optional[str] = None,
) -> None:
    project_rows = _load_project_rows()
    material_rows = _load_material_rows()
    batch_rows = _load_batch_rows()
    root_batches = _load_root_batch_rows()
    root_lookup = {batch["id"]: batch for batch in root_batches}
    batch_lookup = {batch["id"]: batch for batch in batch_rows}

    st.header("🏗️ Batch Builder")
    st.caption(
        "Create canonical source materials, root batches, and child branches in one place. "
        "Every batch stores the metadata needed for immediate Cell Inputs handoff today and faster cycler-linked ingestion later."
    )

    summary_cols = st.columns(4)
    summary_cols[0].metric("Root Batches", len(root_batches))
    summary_cols[1].metric("All Batches", len(batch_rows))
    summary_cols[2].metric("Materials", len(material_rows))
    summary_cols[3].metric("Active Project", current_project_name or "None")

    root_tab, branch_tab, library_tab, materials_tab = st.tabs(
        ["Create Root Batch", "Create Branch", "Batch Library", "Materials"]
    )

    with root_tab:
        st.markdown("#### Create a Root Batch")
        st.caption("Use this for the first canonical batch in a branch family. Child variants can inherit from it later.")

        root_identity_col1, root_identity_col2, root_identity_col3 = st.columns(3)
        with root_identity_col1:
            root_batch_name = st.text_input("Batch Name", key="batch_builder_root_batch_name", placeholder="e.g. N17")
        with root_identity_col2:
            root_role = st.selectbox("Electrode Role", ELECTRODE_ROLE_OPTIONS, key="batch_builder_root_role")
        with root_identity_col3:
            root_created_at = st.date_input("Batch Date", value=date.today(), key="batch_builder_root_created_at")

        root_defaults = _render_batch_defaults_panel(
            "batch_builder_root",
            project_options=project_rows,
            default_project_id=current_project_id,
            electrode_role=root_role,
            preferred_name_default=root_batch_name or "",
            substrate_default=_default_substrate_for_role(root_role),
        )
        root_notes = st.text_area(
            "Batch Notes",
            key="batch_builder_root_notes",
            height=100,
            placeholder="Capture what makes this batch important for traceability and analysis.",
        )

        root_action_cols = st.columns([0.2, 0.8])
        if root_action_cols[0].button("Reset Formulation", key="batch_builder_root_reset_formulation", use_container_width=True):
            st.session_state["batch_builder_root_formulation_seed"] = default_formulation_rows(root_role)
            st.rerun()
        root_formula_seed = st.session_state.get("batch_builder_root_formulation_seed") or default_formulation_rows(root_role)
        root_formula_frame = st.data_editor(
            _build_formulation_dataframe(root_formula_seed),
            num_rows="dynamic",
            use_container_width=True,
            key=f"batch_builder_root_formula_editor_{root_role}",
        )

        process_payload = _prepare_process_payload("batch_builder_root")
        if st.button("Create Root Batch", type="primary", use_container_width=True, key="batch_builder_create_root"):
            try:
                process_settings = _parse_json_dict(
                    process_payload.get("process_settings_raw", ""),
                    label="Structured Process Settings",
                )
                created_batch = create_batch_record(
                    batch_name=root_batch_name,
                    electrode_role=root_role,
                    created_at=root_created_at,
                    formulation_components=_extract_formulation_rows(root_formula_frame),
                    notes=root_notes,
                    process_name=process_payload.get("process_name"),
                    process_type=process_payload.get("process_type", "other"),
                    process_started_at=process_payload.get("process_started_at"),
                    process_completed_at=process_payload.get("process_completed_at"),
                    protocol_name=process_payload.get("protocol_name"),
                    protocol_version=process_payload.get("protocol_version"),
                    protocol_type=process_payload.get("protocol_type", "other"),
                    operator_name=process_payload.get("operator_name"),
                    equipment_name=process_payload.get("equipment_name"),
                    equipment_type=process_payload.get("equipment_type", "other"),
                    process_settings=process_settings,
                    process_notes=process_payload.get("process_notes"),
                    **root_defaults,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                _submit_created_batch(
                    created_batch,
                    launch_after_save=bool(root_defaults.get("launch_after_save")),
                    activate_project_callback=activate_project_callback,
                )

    with branch_tab:
        st.markdown("#### Create a Child Branch")
        st.caption("Use this for a calendared, electrolyte-swapped, protocol-adjusted, or otherwise branched variant of an existing root batch.")

        branch_parent_options = [batch["id"] for batch in root_batches]
        if not branch_parent_options:
            st.info("Create at least one root batch before adding child branches.")
        else:
            selected_parent_id = st.selectbox(
                "Parent Batch",
                options=branch_parent_options,
                key="batch_builder_branch_parent",
                format_func=lambda batch_id: _batch_label(root_lookup[batch_id]),
            )
            parent_batch = root_lookup[selected_parent_id]
            parent_metadata = parent_batch.get("metadata_json") or {}
            branch_col1, branch_col2, branch_col3 = st.columns(3)
            with branch_col1:
                child_batch_name = st.text_input("Child Batch Name", key="batch_builder_child_batch_name", placeholder="e.g. N17a")
            with branch_col2:
                child_created_at = st.date_input("Branch Date", value=date.today(), key="batch_builder_child_created_at")
            with branch_col3:
                inherit_parent_process = st.checkbox(
                    "Inherit parent process run",
                    key="batch_builder_child_inherit_process",
                    value=True,
                )

            branch_defaults = _render_batch_defaults_panel(
                "batch_builder_child",
                project_options=project_rows,
                default_project_id=parent_metadata.get("default_legacy_project_id") or current_project_id,
                electrode_role=parent_batch.get("electrode_role") or "cathode",
                preferred_name_default=child_batch_name or "",
                study_focus_default=_text(parent_metadata.get("study_focus")) or "",
                electrolyte_default=_text(parent_metadata.get("electrolyte_hint")) or "",
                separator_default=_text(parent_metadata.get("separator_hint")) or "25um PP",
                substrate_default=_text(parent_metadata.get("substrate_hint")) or _default_substrate_for_role(parent_batch.get("electrode_role") or "cathode"),
            )
            branch_notes = st.text_area(
                "Branch Notes",
                key="batch_builder_child_notes",
                height=100,
                placeholder="Capture the change that makes this branch distinct from the parent.",
            )
            inherit_formulation = st.checkbox(
                "Inherit parent formulation",
                key="batch_builder_child_inherit_formulation",
                value=True,
            )

            branch_formula_source = parent_batch.get("formulation_json") or default_formulation_rows(parent_batch.get("electrode_role") or "cathode")
            branch_editor_key = f"batch_builder_child_formula_editor_{selected_parent_id}_{'inherit' if inherit_formulation else 'custom'}"
            if inherit_formulation:
                st.dataframe(
                    _build_formulation_dataframe(branch_formula_source),
                    use_container_width=True,
                    hide_index=True,
                )
                branch_formula_frame = None
            else:
                branch_formula_frame = st.data_editor(
                    _build_formulation_dataframe(branch_formula_source),
                    num_rows="dynamic",
                    use_container_width=True,
                    key=branch_editor_key,
                )

            child_process_payload = _prepare_process_payload("batch_builder_child")
            if st.button("Create Child Branch", type="primary", use_container_width=True, key="batch_builder_create_child"):
                try:
                    process_settings = _parse_json_dict(
                        child_process_payload.get("process_settings_raw", ""),
                        label="Structured Process Settings",
                    )
                    created_branch = create_batch_record(
                        batch_name=child_batch_name,
                        electrode_role=parent_batch.get("electrode_role") or "cathode",
                        created_at=child_created_at,
                        formulation_components=None if inherit_formulation else _extract_formulation_rows(branch_formula_frame),
                        parent_batch_name=parent_batch.get("batch_name"),
                        inherit_parent_process=inherit_parent_process,
                        notes=branch_notes,
                        process_name=child_process_payload.get("process_name"),
                        process_type=child_process_payload.get("process_type", "other"),
                        process_started_at=child_process_payload.get("process_started_at"),
                        process_completed_at=child_process_payload.get("process_completed_at"),
                        protocol_name=child_process_payload.get("protocol_name"),
                        protocol_version=child_process_payload.get("protocol_version"),
                        protocol_type=child_process_payload.get("protocol_type", "other"),
                        operator_name=child_process_payload.get("operator_name"),
                        equipment_name=child_process_payload.get("equipment_name"),
                        equipment_type=child_process_payload.get("equipment_type", "other"),
                        process_settings=process_settings,
                        process_notes=child_process_payload.get("process_notes"),
                        **branch_defaults,
                    )
                except Exception as exc:
                    st.error(str(exc))
                else:
                    _submit_created_batch(
                        created_branch,
                        launch_after_save=bool(branch_defaults.get("launch_after_save")),
                        activate_project_callback=activate_project_callback,
                    )

    with library_tab:
        st.markdown("#### Batch Library")
        st.caption("Inspect a canonical batch, send it into Cell Inputs, or jump straight into the Lineage Explorer.")

        if not batch_rows:
            st.info("No ontology batches are available yet.")
        else:
            batch_options = [batch["id"] for batch in batch_rows]
            selected_batch_id = st.selectbox(
                "Batch",
                options=batch_options,
                key="batch_builder_library_batch",
                format_func=lambda batch_id: _batch_label(batch_lookup[batch_id]),
            )
            selected_batch = batch_lookup[selected_batch_id]
            selected_template = build_batch_cell_inputs_template(batch_id=selected_batch_id)

            detail_cols = st.columns(4)
            detail_cols[0].metric("Canonical Batch", selected_batch.get("batch_name"))
            detail_cols[1].metric("Parent Batch", selected_template.get("root_batch_name") if selected_template else selected_batch.get("parent_batch_name") or "None")
            detail_cols[2].metric("Role", str(selected_batch.get("electrode_role") or "").title())
            detail_cols[3].metric("Created", str(selected_batch.get("created_at") or "")[:10] or "Unknown")

            metadata = selected_batch.get("metadata_json") or {}
            meta_bits = [
                f"Study focus: {metadata.get('study_focus')}" if metadata.get("study_focus") else None,
                f"Default project: {metadata.get('default_legacy_project_name')}" if metadata.get("default_legacy_project_name") else None,
                f"Preferred experiment: {metadata.get('preferred_experiment_name')}" if metadata.get("preferred_experiment_name") else None,
            ]
            if any(meta_bits):
                st.caption(" | ".join(bit for bit in meta_bits if bit))

            st.dataframe(
                _build_formulation_dataframe(selected_batch.get("formulation_json") or []),
                use_container_width=True,
                hide_index=True,
            )

            action_cols = st.columns([0.34, 0.33, 0.33])
            if action_cols[0].button("Send to Cell Inputs", use_container_width=True, key="batch_builder_library_send"):
                if not selected_template:
                    st.error("Unable to build a Cell Inputs template for this batch.")
                elif not selected_template.get("project_id") or not selected_template.get("project_name"):
                    st.info("Add a default project to this batch before sending it to Cell Inputs.")
                else:
                    queue_batch_builder_cell_inputs_request(selected_template)
                    st.session_state["_sidebar_pending_project_selector"] = selected_template["project_id"]
                    activate_project_callback(selected_template["project_id"], selected_template["project_name"], True)
                    st.rerun()
            if action_cols[1].button("Focus in Lineage Explorer", use_container_width=True, key="batch_builder_library_lineage"):
                if selected_template:
                    queue_lineage_explorer_focus(selected_template.get("ontology_context") or {})
                    st.info(f"Lineage Explorer is focused on {selected_template.get('root_batch_name')}.")
            if action_cols[2].button("Refresh Library", use_container_width=True, key="batch_builder_library_refresh"):
                _invalidate_builder_caches()
                st.rerun()

            recent_rows = [
                {
                    "Batch": batch.get("batch_name"),
                    "Parent": batch.get("parent_batch_name") or "",
                    "Role": batch.get("electrode_role"),
                    "Created": str(batch.get("created_at") or "")[:10],
                    "Project": (batch.get("metadata_json") or {}).get("default_legacy_project_name") or "",
                    "Study Focus": (batch.get("metadata_json") or {}).get("study_focus") or "",
                }
                for batch in batch_rows[:12]
            ]
            st.markdown("##### Recent Batches")
            st.dataframe(pd.DataFrame(recent_rows), use_container_width=True, hide_index=True)

    with materials_tab:
        _render_material_library_section(material_rows)
