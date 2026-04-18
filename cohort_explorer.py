"""Temporary ontology-backed cohort explorer for the legacy CellScope app."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

import pandas as pd
import streamlit as st

from analysis_surface_service import build_analysis_metric_rows
from backend_analysis_client import (
    get_cohort_snapshot_payload_preferred,
    list_cohort_snapshot_records,
)
from backend_metrics_bridge import load_preferred_experiment_metrics_map
from cohort_tools import (
    apply_cohort_filters,
    build_cohort_comparison_payload,
    build_cohort_snapshot_export_payload,
    build_cohort_filter_options,
    delete_saved_cohort,
    delete_cohort_snapshot,
    format_cohort_snapshot_markdown,
    list_saved_cohorts,
    load_cohort_records,
    normalize_cohort_filters,
    save_saved_cohort,
    save_cohort_snapshot,
    summarize_cohort,
    summarize_cohort_by_root_batch,
)


COHORT_STATE_DEFAULTS = {
    "cohort_project_ids": [],
    "cohort_root_batches": [],
    "cohort_batches": [],
    "cohort_electrolytes": [],
    "cohort_tracking_statuses": [],
    "cohort_only_ontology": True,
    "cohort_derived_metrics_only": False,
    "cohort_min_retention_pct": "",
    "cohort_min_ce_pct": "",
    "cohort_max_fade_pct": "",
    "cohort_min_cycle_life": "",
    "cohort_search_query": "",
}


def _ensure_default_state() -> None:
    for key, value in COHORT_STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _current_filters() -> Dict[str, Any]:
    return normalize_cohort_filters(
        {
            "project_ids": st.session_state.get("cohort_project_ids", []),
            "ontology_root_batch_names": st.session_state.get("cohort_root_batches", []),
            "ontology_batch_names": st.session_state.get("cohort_batches", []),
            "electrolytes": st.session_state.get("cohort_electrolytes", []),
            "tracking_statuses": st.session_state.get("cohort_tracking_statuses", []),
            "ontology_only": st.session_state.get("cohort_only_ontology", True),
            "derived_metrics_only": st.session_state.get("cohort_derived_metrics_only", False),
            "min_avg_retention_pct": st.session_state.get("cohort_min_retention_pct", ""),
            "min_avg_coulombic_efficiency_pct": st.session_state.get("cohort_min_ce_pct", ""),
            "max_avg_fade_rate_pct_per_100_cycles": st.session_state.get("cohort_max_fade_pct", ""),
            "min_best_cycle_life_80": st.session_state.get("cohort_min_cycle_life", ""),
            "search_query": st.session_state.get("cohort_search_query", ""),
        }
    )


def _apply_saved_filters(filters: Dict[str, Any]) -> None:
    normalized = normalize_cohort_filters(filters)
    st.session_state["cohort_project_ids"] = normalized["project_ids"]
    st.session_state["cohort_root_batches"] = normalized["ontology_root_batch_names"]
    st.session_state["cohort_batches"] = normalized["ontology_batch_names"]
    st.session_state["cohort_electrolytes"] = normalized["electrolytes"]
    st.session_state["cohort_tracking_statuses"] = normalized["tracking_statuses"]
    st.session_state["cohort_only_ontology"] = normalized["ontology_only"]
    st.session_state["cohort_derived_metrics_only"] = normalized["derived_metrics_only"]
    st.session_state["cohort_min_retention_pct"] = (
        "" if normalized["min_avg_retention_pct"] is None else str(normalized["min_avg_retention_pct"])
    )
    st.session_state["cohort_min_ce_pct"] = (
        "" if normalized["min_avg_coulombic_efficiency_pct"] is None else str(normalized["min_avg_coulombic_efficiency_pct"])
    )
    st.session_state["cohort_max_fade_pct"] = (
        "" if normalized["max_avg_fade_rate_pct_per_100_cycles"] is None else str(normalized["max_avg_fade_rate_pct_per_100_cycles"])
    )
    st.session_state["cohort_min_cycle_life"] = (
        "" if normalized["min_best_cycle_life_80"] is None else str(normalized["min_best_cycle_life_80"])
    )
    st.session_state["cohort_search_query"] = normalized["search_query"]


def _reset_filters() -> None:
    for key, value in COHORT_STATE_DEFAULTS.items():
        st.session_state[key] = value


def _build_member_rows(records: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return [
        {
            "Project": record["project_name"],
            "Experiment": record["experiment_name"],
            "Parent Batch": record.get("ontology_root_batch_name") or "",
            "Canonical Batch": record.get("ontology_batch_name") or "",
            "Electrolyte": record.get("electrolyte") or "",
            "Tracking Status": record.get("tracking_status") or "",
            "Cells": record.get("cell_count") or 0,
            "Missing Cells": record.get("missing_cell_count") or 0,
            "Experiment Date": record.get("experiment_date") or "",
        }
        for record in records
    ]


def _build_metric_table_rows(records: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    rows = []
    for row in build_analysis_metric_rows(
        [record for record in records if record.get("derived_metrics_cached")]
    ):
        rows.append(
            {
                "Experiment": row.get("experiment_name"),
                "Project": row.get("project_name"),
                "Parent Batch": row.get("ontology_root_batch_name") or "",
                "Canonical Batch": row.get("ontology_batch_name") or "",
                "Avg Retention (%)": row.get("avg_retention_pct"),
                "Avg CE (%)": row.get("avg_coulombic_efficiency_pct"),
                "Avg Fade (%/100 cyc)": row.get("avg_fade_rate_pct_per_100_cycles"),
                "Best Cycle Life (80%)": row.get("best_cycle_life_80"),
                "Avg Reversible Capacity (mAh/g)": row.get("avg_reversible_capacity_mAh_g"),
                "Metric Source": row.get("metrics_source") or "",
                "Metrics Computed": row.get("derived_metrics_computed_at") or "",
            }
        )
    return rows


def render_cohort_explorer(
    *,
    open_experiment_callback: Callable[[int, int, str], None],
    queue_comparison_callback: Optional[Callable[[int, str, list[str], Optional[str]], None]] = None,
    queue_dashboard_snapshot_callback: Optional[Callable[[int, Optional[str]], None]] = None,
    queue_workspace_callback: Optional[Callable[[int, Optional[str]], None]] = None,
    current_project_id: Optional[int] = None,
    current_project_name: Optional[str] = None,
) -> None:
    del current_project_id, current_project_name

    _ensure_default_state()
    records = load_cohort_records()
    saved_cohorts = list_saved_cohorts()
    saved_snapshots = list_cohort_snapshot_records()
    filter_options = build_cohort_filter_options(records)
    selected_saved_cohort_name: Optional[str] = None
    selected_snapshot_id = st.session_state.get("cohort_snapshot_select")
    selected_snapshot = (
        get_cohort_snapshot_payload_preferred(selected_snapshot_id)
        if selected_snapshot_id
        else None
    )

    st.header("🗂️ Cohorts")
    st.caption("Temporary cohort builder backed by canonical ontology batch mappings in the legacy app.")

    with st.container(border=True):
        st.markdown("#### Saved Cohorts")
        if saved_cohorts:
            cohort_lookup = {cohort["id"]: cohort for cohort in saved_cohorts}
            selected_saved_cohort_id = st.selectbox(
                "Saved cohort",
                options=[cohort["id"] for cohort in saved_cohorts],
                format_func=lambda cohort_id: cohort_lookup[cohort_id]["name"],
                key="cohort_saved_select",
            )
            selected_saved_cohort = cohort_lookup[selected_saved_cohort_id]
            selected_saved_cohort_name = selected_saved_cohort["name"]
            action_cols = st.columns([0.25, 0.25, 0.5])
            if action_cols[0].button("Load Cohort", use_container_width=True, key="cohort_load_button"):
                _apply_saved_filters(selected_saved_cohort["filters"])
                st.rerun()
            if action_cols[1].button("Delete Cohort", use_container_width=True, key="cohort_delete_button"):
                delete_saved_cohort(selected_saved_cohort_id)
                st.session_state.pop("cohort_saved_select", None)
                st.rerun()
            description = selected_saved_cohort.get("description")
            if description:
                st.caption(description)
        else:
            st.caption("No saved cohorts yet. Build a filter below and save one.")

    with st.container(border=True):
        st.markdown("#### Saved Snapshots")
        if saved_snapshots:
            snapshot_lookup = {snapshot["id"]: snapshot for snapshot in saved_snapshots}
            selected_snapshot_id = st.selectbox(
                "Snapshot",
                options=[snapshot["id"] for snapshot in saved_snapshots],
                format_func=lambda snapshot_id: snapshot_lookup[snapshot_id]["name"],
                key="cohort_snapshot_select",
            )
            selected_snapshot = (
                get_cohort_snapshot_payload_preferred(selected_snapshot_id)
                or snapshot_lookup[selected_snapshot_id]
            )
            snapshot_action_cols = st.columns([0.17, 0.17, 0.17, 0.17, 0.12, 0.20])
            if snapshot_action_cols[0].button("Load Snapshot Filters", use_container_width=True, key="cohort_load_snapshot_filters"):
                _apply_saved_filters(selected_snapshot["filters"])
                st.rerun()
            snapshot_comparison_payload = build_cohort_comparison_payload(selected_snapshot.get("member_records", []))
            if snapshot_action_cols[1].button(
                "Snapshot to Comparison",
                use_container_width=True,
                disabled=snapshot_comparison_payload is None or queue_comparison_callback is None,
                key="cohort_snapshot_to_comparison",
                ):
                queue_comparison_callback(
                    snapshot_comparison_payload["project_id"],
                    snapshot_comparison_payload["project_name"],
                    snapshot_comparison_payload["experiment_names"],
                    selected_snapshot["name"],
                )
                st.info(f"{selected_snapshot['name']} is loaded into Comparison.")
            if snapshot_action_cols[2].button(
                "Open Workspace",
                use_container_width=True,
                disabled=queue_workspace_callback is None,
                key="cohort_snapshot_to_workspace",
            ):
                queue_workspace_callback(selected_snapshot_id, selected_snapshot.get("name"))
                st.info(f"{selected_snapshot['name']} is loaded into Study Workspace.")
            if snapshot_action_cols[3].button(
                "Use in Dashboard",
                use_container_width=True,
                disabled=queue_dashboard_snapshot_callback is None,
                key="cohort_snapshot_to_dashboard",
            ):
                queue_dashboard_snapshot_callback(selected_snapshot_id, selected_snapshot.get("name"))
                st.info(f"{selected_snapshot['name']} is focused on the Dashboard.")
            if snapshot_action_cols[4].button("Delete Snapshot", use_container_width=True, key="cohort_delete_snapshot"):
                delete_cohort_snapshot(selected_snapshot_id)
                st.session_state.pop("cohort_snapshot_select", None)
                st.rerun()
            snapshot_meta = []
            if selected_snapshot.get("cohort_name"):
                snapshot_meta.append(f"Cohort: {selected_snapshot['cohort_name']}")
            if selected_snapshot.get("updated_date"):
                snapshot_meta.append(f"Updated: {selected_snapshot['updated_date']}")
            if snapshot_meta:
                st.caption(" | ".join(snapshot_meta))
            if selected_snapshot.get("description"):
                st.caption(selected_snapshot["description"])
        else:
            st.caption("No saved snapshots yet. Snapshot a filtered cohort below to persist its member set and rollups.")

    with st.container(border=True):
        toolbar_cols = st.columns([0.82, 0.18])
        with toolbar_cols[0]:
            st.markdown("#### Build a Cohort")
            st.caption("Filter by canonical parent batch, branch, project, electrolyte, tracking state, and derived metrics.")
        with toolbar_cols[1]:
            st.button(
                "Reset Filters",
                key="cohort_reset_filters",
                on_click=_reset_filters,
                use_container_width=True,
            )

        project_options = filter_options["project_options"]
        selected_project_ids = st.multiselect(
            "Projects",
            options=[item["id"] for item in project_options],
            default=st.session_state.get("cohort_project_ids", []),
            format_func=lambda project_id: next(item["label"] for item in project_options if item["id"] == project_id),
            key="cohort_project_ids",
        )
        st.multiselect(
            "Parent Batches",
            options=filter_options["ontology_root_batch_names"],
            default=st.session_state.get("cohort_root_batches", []),
            key="cohort_root_batches",
        )
        st.multiselect(
            "Canonical Batches",
            options=filter_options["ontology_batch_names"],
            default=st.session_state.get("cohort_batches", []),
            key="cohort_batches",
        )
        st.multiselect(
            "Electrolytes",
            options=filter_options["electrolytes"],
            default=st.session_state.get("cohort_electrolytes", []),
            key="cohort_electrolytes",
        )
        st.multiselect(
            "Tracking Status",
            options=filter_options["tracking_statuses"],
            default=st.session_state.get("cohort_tracking_statuses", []),
            key="cohort_tracking_statuses",
        )
        st.checkbox(
            "Only ontology-mapped experiments",
            key="cohort_only_ontology",
            value=st.session_state.get("cohort_only_ontology", True),
        )
        with st.expander("Derived Metric Filters", expanded=False):
            st.checkbox(
                "Only experiments with cached derived metrics",
                key="cohort_derived_metrics_only",
                value=st.session_state.get("cohort_derived_metrics_only", False),
            )
            metric_filter_cols = st.columns(2)
            metric_filter_cols[0].text_input(
                "Min avg retention (%)",
                key="cohort_min_retention_pct",
                placeholder="e.g. 85",
            )
            metric_filter_cols[1].text_input(
                "Min avg CE (%)",
                key="cohort_min_ce_pct",
                placeholder="e.g. 99.3",
            )
            metric_filter_cols[0].text_input(
                "Max avg fade (% / 100 cycles)",
                key="cohort_max_fade_pct",
                placeholder="e.g. 2.5",
            )
            metric_filter_cols[1].text_input(
                "Min best cycle life (80%)",
                key="cohort_min_cycle_life",
                placeholder="e.g. 150",
            )
        st.text_input(
            "Search within the cohort",
            key="cohort_search_query",
            placeholder="Try N10, N16, acid wash, LiTFSI, or porosity",
        )

    filters = _current_filters()
    filtered_records = apply_cohort_filters(records, filters)
    summary = summarize_cohort(filtered_records)
    comparison_payload = build_cohort_comparison_payload(filtered_records)
    member_rows_data = _build_member_rows(filtered_records)
    member_rows = pd.DataFrame(member_rows_data)

    metric_cols = st.columns(6)
    metric_cols[0].metric("Experiments", summary["experiment_count"])
    metric_cols[1].metric("Cells", summary["cell_count"])
    metric_cols[2].metric("Metrics Ready", summary["metrics_ready_experiment_count"])
    metric_cols[3].metric("Parent Batches", summary["unique_parent_batches"])
    metric_cols[4].metric(
        "Avg Retention",
        f"{summary['avg_retention_pct']:.2f}%" if summary.get("avg_retention_pct") is not None else "N/A",
    )
    metric_cols[5].metric(
        "Best Cycle Life",
        f"{summary['best_cycle_life_80']:.0f}" if summary.get("best_cycle_life_80") is not None else "N/A",
    )

    with st.container(border=True):
        st.markdown("#### Cohort Actions")
        action_cols = st.columns([0.28, 0.24, 0.48])
        with action_cols[0]:
            st.download_button(
                "Download Members CSV",
                data=member_rows.to_csv(index=False),
                file_name="cohort_members.csv",
                mime="text/csv",
                disabled=member_rows.empty,
                use_container_width=True,
                key="cohort_download_members_csv",
            )
        with action_cols[1]:
            if st.button(
                "Send to Comparison",
                disabled=comparison_payload is None or queue_comparison_callback is None,
                use_container_width=True,
                key="cohort_send_to_comparison",
            ):
                cohort_label = selected_saved_cohort_name or "Current cohort"
                queue_comparison_callback(
                    comparison_payload["project_id"],
                    comparison_payload["project_name"],
                    comparison_payload["experiment_names"],
                    cohort_label,
                )
                st.info(
                    f"{cohort_label} is loaded into the Comparison tab for {comparison_payload['project_name']}."
                )
        with action_cols[2]:
            if filtered_records and comparison_payload is None:
                st.caption("Comparison handoff needs at least 2 experiments from a single project in the current cohort.")
            elif comparison_payload:
                st.caption(
                    f"Ready for comparison in {comparison_payload['project_name']} with "
                    f"{len(comparison_payload['experiment_names'])} experiments."
                )
            else:
                st.caption("Filter the cohort to start exporting or comparing a focused set.")

    root_batch_summary = summarize_cohort_by_root_batch(filtered_records)
    if root_batch_summary:
        st.markdown("#### Parent Batch Summary")
        st.dataframe(pd.DataFrame(root_batch_summary), use_container_width=True, hide_index=True)

    st.markdown("#### Cohort Members")
    if not member_rows.empty:
        st.dataframe(member_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No experiments match the current cohort filters.")

    with st.container(border=True):
        st.markdown("#### Derived Metrics")
        st.caption("Backend-native metrics are preferred when linked runs exist; legacy persisted metrics remain the fallback during the bridge.")
        metric_cols = st.columns([0.2, 0.2, 0.6])
        load_metrics = metric_cols[0].button("Compute Missing", use_container_width=True, key="cohort_load_metrics")
        refresh_metrics = metric_cols[1].button("Refresh Metrics", use_container_width=True, key="cohort_refresh_metrics")
        if filtered_records and (load_metrics or refresh_metrics):
            load_preferred_experiment_metrics_map(
                [record["experiment_id"] for record in filtered_records],
                compute_missing_legacy=True,
                refresh=refresh_metrics,
            )
            st.rerun()

        metric_ready_records = [record for record in filtered_records if record.get("derived_metrics_cached")]
        if metric_ready_records:
            summary_cols = st.columns(4)
            summary_cols[0].metric(
                "Avg Retention",
                f"{summary['avg_retention_pct']:.2f}%" if summary.get("avg_retention_pct") is not None else "N/A",
            )
            summary_cols[1].metric(
                "Avg CE",
                f"{summary['avg_coulombic_efficiency_pct']:.3f}%"
                if summary.get("avg_coulombic_efficiency_pct") is not None
                else "N/A",
            )
            summary_cols[2].metric(
                "Avg Fade",
                f"{summary['avg_fade_rate_pct_per_100_cycles']:.3f}% / 100 cyc"
                if summary.get("avg_fade_rate_pct_per_100_cycles") is not None
                else "N/A",
            )
            summary_cols[3].metric(
                "Avg Rev. Capacity",
                f"{summary['avg_reversible_capacity_mAh_g']:.2f} mAh/g"
                if summary.get("avg_reversible_capacity_mAh_g") is not None
                else "N/A",
            )

            metric_table = pd.DataFrame(_build_metric_table_rows(metric_ready_records))
            st.dataframe(metric_table, use_container_width=True, hide_index=True)
            st.download_button(
                "Download Metrics CSV",
                data=metric_table.to_csv(index=False),
                file_name="cohort_derived_metrics.csv",
                mime="text/csv",
                use_container_width=False,
                key="cohort_download_metrics_csv",
            )
        elif filtered_records:
            st.caption("This cohort has no cached metrics yet. Compute missing metrics to activate metric filters and snapshot rollups.")
        else:
            st.caption("Build a non-empty cohort first, then load derived metrics for it.")

    with st.container(border=True):
        st.markdown("#### Save Current Cohort")
        st.caption("Save this filter definition so you can reload the same canonical experiment set later.")
        save_cols = st.columns([0.42, 0.42, 0.16])
        cohort_name = save_cols[0].text_input("Cohort name", key="cohort_name_input")
        cohort_description = save_cols[1].text_input("Description", key="cohort_description_input")
        update_existing = save_cols[2].checkbox("Update selected", key="cohort_update_existing")
        if st.button("Save Cohort", use_container_width=True, key="cohort_save_button"):
            if not cohort_name.strip():
                st.error("Enter a cohort name before saving.")
            else:
                target_cohort_id = st.session_state.get("cohort_saved_select") if update_existing else None
                cohort_id = save_saved_cohort(
                    name=cohort_name,
                    description=cohort_description,
                    filters=filters,
                    cohort_id=target_cohort_id,
                )
                st.session_state["cohort_saved_select"] = cohort_id
                st.success(f"Saved cohort `{cohort_name.strip()}`.")
                st.rerun()

    with st.container(border=True):
        st.markdown("#### Snapshot Current Cohort")
        st.caption("Persist the current member set, root-batch rollups, and an AI-ready cohort brief.")
        snapshot_cols = st.columns([0.38, 0.38, 0.12, 0.12])
        snapshot_name = snapshot_cols[0].text_input("Snapshot name", key="cohort_snapshot_name_input")
        snapshot_description = snapshot_cols[1].text_input("Snapshot description", key="cohort_snapshot_description_input")
        update_snapshot = snapshot_cols[2].checkbox("Update", key="cohort_snapshot_update_existing")
        target_snapshot_id = st.session_state.get("cohort_snapshot_select") if update_snapshot else None
        if snapshot_cols[3].button("Save", use_container_width=True, key="cohort_snapshot_save_button"):
            if not filtered_records:
                st.error("Build a non-empty cohort before saving a snapshot.")
            elif not snapshot_name.strip():
                st.error("Enter a snapshot name before saving.")
            else:
                linked_cohort_id = st.session_state.get("cohort_saved_select")
                snapshot_id = save_cohort_snapshot(
                    name=snapshot_name,
                    description=snapshot_description,
                    filters=filters,
                    records=filtered_records,
                    cohort_id=linked_cohort_id,
                    snapshot_id=target_snapshot_id,
                )
                st.session_state["cohort_snapshot_select"] = snapshot_id
                st.success(f"Saved snapshot `{snapshot_name.strip()}`.")
                st.rerun()

    if selected_snapshot:
        st.markdown("#### Snapshot Detail")
        snapshot_summary = selected_snapshot.get("summary", {})
        snapshot_metric_cols = st.columns(5)
        snapshot_metric_cols[0].metric("Experiments", snapshot_summary.get("experiment_count", 0))
        snapshot_metric_cols[1].metric("Cells", snapshot_summary.get("cell_count", 0))
        snapshot_metric_cols[2].metric("Metrics Ready", snapshot_summary.get("metrics_ready_experiment_count", 0))
        snapshot_metric_cols[3].metric(
            "Avg Retention",
            f"{snapshot_summary['avg_retention_pct']:.2f}%"
            if snapshot_summary.get("avg_retention_pct") is not None
            else "N/A",
        )
        snapshot_metric_cols[4].metric(
            "Best Cycle Life",
            f"{snapshot_summary['best_cycle_life_80']:.0f}"
            if snapshot_summary.get("best_cycle_life_80") is not None
            else "N/A",
        )
        if selected_snapshot.get("ai_summary_text"):
            st.text_area(
                "AI-ready cohort brief",
                value=selected_snapshot["ai_summary_text"],
                height=220,
                key="cohort_snapshot_ai_summary",
            )
        snapshot_export_cols = st.columns([0.2, 0.2, 0.2, 0.4])
        snapshot_export_payload = build_cohort_snapshot_export_payload(selected_snapshot)
        snapshot_export_cols[0].download_button(
            "Download Snapshot JSON",
            data=json.dumps(snapshot_export_payload, indent=2, default=str),
            file_name="cohort_snapshot.json",
            mime="application/json",
            key="cohort_snapshot_json_download",
            use_container_width=True,
        )
        snapshot_export_cols[1].download_button(
            "Download AI Brief",
            data=format_cohort_snapshot_markdown(selected_snapshot),
            file_name="cohort_snapshot_brief.md",
            mime="text/markdown",
            key="cohort_snapshot_brief_download",
            use_container_width=True,
        )
        if queue_workspace_callback is not None and snapshot_export_cols[2].button(
            "Open in Workspace",
            key="cohort_snapshot_open_workspace",
            use_container_width=True,
        ):
            queue_workspace_callback(selected_snapshot["id"], selected_snapshot.get("name"))
            st.info(f"{selected_snapshot['name']} is loaded into Study Workspace.")
        if queue_dashboard_snapshot_callback is not None and snapshot_export_cols[3].button(
            "Open Snapshot on Dashboard",
            key="cohort_snapshot_open_dashboard",
            use_container_width=True,
        ):
            queue_dashboard_snapshot_callback(selected_snapshot["id"], selected_snapshot.get("name"))
            st.info(f"{selected_snapshot['name']} is focused on the Dashboard.")
        snapshot_root_rows = pd.DataFrame(selected_snapshot.get("root_batch_summary", []))
        if not snapshot_root_rows.empty:
            st.dataframe(snapshot_root_rows, use_container_width=True, hide_index=True)
        snapshot_member_rows = pd.DataFrame(_build_member_rows(selected_snapshot.get("member_records", [])))
        if not snapshot_member_rows.empty:
            st.download_button(
                "Download Snapshot Members CSV",
                data=snapshot_member_rows.to_csv(index=False),
                file_name="cohort_snapshot_members.csv",
                mime="text/csv",
                key="cohort_snapshot_member_download",
            )

    if filtered_records:
        st.markdown("#### Open an Experiment")
        selected_experiment_id = st.selectbox(
            "Cohort member",
            options=[record["experiment_id"] for record in filtered_records],
            format_func=lambda experiment_id: next(
                (
                    f"{record['experiment_name']} | {record['project_name']} | "
                    f"{record.get('ontology_root_batch_name') or 'Unmapped'}"
                )
                for record in filtered_records
                if record["experiment_id"] == experiment_id
            ),
            key="cohort_open_experiment_select",
        )
        selected_record = next(record for record in filtered_records if record["experiment_id"] == selected_experiment_id)
        if st.button("Open in Cell Inputs", use_container_width=True, key="cohort_open_button"):
            open_experiment_callback(
                selected_record["experiment_id"],
                selected_record["project_id"],
                selected_record["project_name"],
            )
            st.rerun()
