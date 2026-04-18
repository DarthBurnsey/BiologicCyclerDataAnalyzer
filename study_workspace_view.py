"""Streamlit UI for snapshot-backed study workspaces."""

from __future__ import annotations

import json
from typing import Callable, Optional

import pandas as pd
import streamlit as st

from backend_analysis_client import (
    get_study_workspace_payload_preferred,
    list_study_workspace_records,
)
from dashboard_plots import (
    plot_fade_rate_scatter,
    plot_multi_project_retention,
    plot_project_comparison_bar,
)
from ontology_explorer import queue_lineage_explorer_focus
from study_workspace_service import (
    build_study_workspace_comparison_payload,
    build_study_workspace_export_payload,
    create_or_open_study_workspace_from_snapshot,
    delete_study_workspace,
    delete_study_workspace_annotation,
    format_study_workspace_markdown,
    save_study_workspace_annotation,
)


def _workspace_notice(message: str) -> None:
    st.session_state["study_workspace_notice"] = message


def _pop_workspace_notice() -> Optional[str]:
    return st.session_state.pop("study_workspace_notice", None)


def _handle_pending_snapshot_open() -> None:
    pending_snapshot_id = st.session_state.pop("study_workspace_pending_snapshot_id", None)
    pending_snapshot_name = st.session_state.pop("study_workspace_pending_snapshot_name", None)
    if pending_snapshot_id is None:
        return

    try:
        workspace_id, created = create_or_open_study_workspace_from_snapshot(
            int(pending_snapshot_id)
        )
    except ValueError as exc:
        _workspace_notice(str(exc))
        return

    st.session_state["study_workspace_active_id"] = workspace_id
    if pending_snapshot_name:
        verb = "created from" if created else "opened from"
        _workspace_notice(f"{pending_snapshot_name} is {verb} in Study Workspace.")


def _member_frame(members: list[dict]) -> pd.DataFrame:
    rows = []
    for member in members:
        rows.append(
            {
                "Experiment ID": member.get("experiment_id"),
                "Project": member.get("project_name") or "",
                "Experiment": member.get("experiment_name") or "",
                "Parent Batch": member.get("ontology_root_batch_name") or "",
                "Canonical Batch": member.get("ontology_batch_name") or "",
                "Tracking Status": member.get("tracking_status") or "",
                "Cells": int(member.get("cell_count") or 0),
                "Avg Retention (%)": member.get("avg_retention_pct"),
                "Avg CE (%)": member.get("avg_coulombic_efficiency_pct"),
                "Avg Fade (%/100 cyc)": member.get("avg_fade_rate_pct_per_100_cycles"),
                "Best Cycle Life (80%)": member.get("best_cycle_life_80"),
                "Metrics": member.get("metric_refresh_status") or "",
                "Computed": member.get("derived_metrics_computed_at") or "",
            }
        )
    return pd.DataFrame(rows)


def _annotation_label(annotation: dict) -> str:
    title = annotation.get("title") or "Note"
    created_date = str(annotation.get("created_date") or "")[:16]
    return f"{title} | {created_date}" if created_date else title


def render_study_workspace(
    *,
    open_experiment_callback: Callable[[int, int, str], None],
    queue_comparison_callback: Optional[Callable[[int, str, list[str], Optional[str]], None]] = None,
) -> None:
    _handle_pending_snapshot_open()

    st.header("🧪 Study Workspace")
    st.caption(
        "A study workspace turns a frozen cohort snapshot into a reusable analysis surface with fresh metrics, lineage focus, and notes."
    )

    notice = _pop_workspace_notice()
    if notice:
        st.info(notice)

    workspaces = list_study_workspace_records()
    if not workspaces:
        st.info(
            "No study workspaces yet. Save a cohort snapshot in `🗂️ Cohorts` or focus a snapshot on the Dashboard, then open it in Study Workspace."
        )
        return

    workspace_lookup = {workspace["id"]: workspace for workspace in workspaces}
    default_workspace_id = st.session_state.get("study_workspace_active_id")
    if default_workspace_id not in workspace_lookup:
        default_workspace_id = workspaces[0]["id"]
        st.session_state["study_workspace_active_id"] = default_workspace_id

    with st.container(border=True):
        toolbar_cols = st.columns([0.58, 0.14, 0.14, 0.14])
        selected_workspace_id = toolbar_cols[0].selectbox(
            "Workspace",
            options=[workspace["id"] for workspace in workspaces],
            index=[workspace["id"] for workspace in workspaces].index(default_workspace_id),
            format_func=lambda workspace_id: workspace_lookup[workspace_id]["name"],
            key="study_workspace_active_id",
        )
        refresh_workspace = toolbar_cols[1].button(
            "Refresh Data",
            use_container_width=True,
            key="study_workspace_refresh_data",
        )
        delete_workspace_requested = toolbar_cols[2].button(
            "Delete",
            use_container_width=True,
            key="study_workspace_delete",
        )
        open_snapshot_source = toolbar_cols[3].button(
            "Source Snapshot",
            use_container_width=True,
            key="study_workspace_source_snapshot",
        )

        selected_workspace = workspace_lookup[selected_workspace_id]
        meta_bits = []
        if selected_workspace.get("cohort_name"):
            meta_bits.append(f"Cohort: {selected_workspace['cohort_name']}")
        if selected_workspace.get("snapshot_name"):
            meta_bits.append(f"Snapshot: {selected_workspace['snapshot_name']}")
        if selected_workspace.get("last_opened_at"):
            meta_bits.append(f"Opened: {selected_workspace['last_opened_at']}")
        if meta_bits:
            st.caption(" | ".join(meta_bits))
        if selected_workspace.get("description"):
            st.caption(selected_workspace["description"])

    if delete_workspace_requested:
        delete_study_workspace(selected_workspace_id)
        st.session_state.pop("study_workspace_active_id", None)
        _workspace_notice(f"Removed workspace `{selected_workspace['name']}`.")
        st.rerun()

    if open_snapshot_source and selected_workspace.get("snapshot_id"):
        st.session_state["cohort_snapshot_select"] = int(selected_workspace["snapshot_id"])
        _workspace_notice(
            f"{selected_workspace.get('snapshot_name') or 'Source snapshot'} is selected in Cohorts."
        )

    payload = get_study_workspace_payload_preferred(
        selected_workspace_id,
        refresh=refresh_workspace,
    )
    if not payload:
        st.warning("Unable to build that workspace. Its source snapshot may have been removed.")
        return

    summary = payload["summary"]
    members = payload["members"]
    member_frame = _member_frame(members)
    comparison_payload = build_study_workspace_comparison_payload(payload)
    workspace_export_payload = build_study_workspace_export_payload(payload)

    header_cols = st.columns(6)
    header_cols[0].metric("Experiments", summary.get("experiment_count", 0))
    header_cols[1].metric("Cells", summary.get("cell_count", 0))
    header_cols[2].metric("Parent Batches", summary.get("root_batch_count", 0))
    header_cols[3].metric("Metrics Ready", summary.get("metrics_ready_experiment_count", 0))
    header_cols[4].metric(
        "Avg Retention",
        f"{summary['avg_retention_pct']:.2f}%"
        if summary.get("avg_retention_pct") is not None
        else "N/A",
    )
    header_cols[5].metric(
        "Refreshed Now",
        int(summary.get("metrics_refreshed_count") or 0),
    )

    with st.container(border=True):
        action_cols = st.columns([0.16, 0.16, 0.16, 0.16, 0.36])
        action_cols[0].download_button(
            "Workspace JSON",
            data=json.dumps(workspace_export_payload, indent=2, default=str),
            file_name="study_workspace.json",
            mime="application/json",
            use_container_width=True,
            key="study_workspace_json_download",
        )
        action_cols[1].download_button(
            "Workspace Brief",
            data=format_study_workspace_markdown(payload),
            file_name="study_workspace_brief.md",
            mime="text/markdown",
            use_container_width=True,
            key="study_workspace_brief_download",
        )
        action_cols[2].download_button(
            "Members CSV",
            data=member_frame.to_csv(index=False),
            file_name="study_workspace_members.csv",
            mime="text/csv",
            use_container_width=True,
            key="study_workspace_members_download",
        )
        if action_cols[3].button(
            "To Comparison",
            disabled=comparison_payload is None or queue_comparison_callback is None,
            use_container_width=True,
            key="study_workspace_to_comparison",
        ):
            queue_comparison_callback(
                comparison_payload["project_id"],
                comparison_payload["project_name"],
                comparison_payload["experiment_names"],
                summary.get("workspace_name"),
            )
            st.info(
                f"{summary.get('workspace_name') or 'Workspace'} is loaded into Comparison for {comparison_payload['project_name']}."
            )
        if comparison_payload is None:
            action_cols[4].caption(
                "Workspace-wide comparison needs at least 2 experiments from one project. Use the member drilldown below to compare a focused subset."
            )
        else:
            action_cols[4].caption(
                f"Ready for comparison in {comparison_payload['project_name']} with {len(comparison_payload['experiment_names'])} experiments."
            )

    plot_tabs = st.tabs(["Retention", "Fade", "Project Rollup"])
    plot_data = payload["plots"]

    with plot_tabs[0]:
        retention_cols = st.columns([0.24, 0.24, 0.52])
        show_average = retention_cols[0].checkbox(
            "Show Average",
            value=True,
            key="study_workspace_retention_average",
        )
        max_cells = retention_cols[1].slider(
            "Max cells per project",
            min_value=3,
            max_value=20,
            value=10,
            key="study_workspace_retention_max_cells",
        )
        retention_cols[2].caption(
            f"Curves loaded: {plot_data['cells_data'] and len(plot_data['cells_data']) or 0} cell traces from the frozen workspace membership."
        )
        retention_fig = plot_multi_project_retention(
            plot_data["cells_data"],
            group_by="project",
            show_average=show_average,
            max_cells_per_group=max_cells,
        )
        st.plotly_chart(retention_fig, use_container_width=True)

    with plot_tabs[1]:
        fade_cols = st.columns([0.26, 0.26, 0.48])
        fade_axis = fade_cols[0].selectbox(
            "X-axis",
            options=["initial_capacity", "temperature", "c_rate"],
            format_func=lambda value: value.replace("_", " ").title(),
            key="study_workspace_fade_axis",
        )
        filter_outliers = fade_cols[1].checkbox(
            "Filter outliers",
            value=True,
            key="study_workspace_fade_filter",
        )
        fade_cols[2].caption(
            "Temperature and C-rate are only available when the underlying experiment metadata includes them."
        )
        fade_fig = plot_fade_rate_scatter(
            plot_data["cells_data"],
            x_axis=fade_axis,
            color_by="project",
            filter_outliers=filter_outliers,
        )
        st.plotly_chart(fade_fig, use_container_width=True)

    with plot_tabs[2]:
        project_fig = plot_project_comparison_bar(plot_data["project_summaries"])
        st.plotly_chart(project_fig, use_container_width=True)

    lower_left, lower_right = st.columns([0.58, 0.42])

    with lower_left:
        st.markdown("#### Member Drilldown")
        if member_frame.empty:
            st.info("This workspace has no member experiments.")
        else:
            st.dataframe(member_frame, use_container_width=True, hide_index=True)

            selected_member_id = st.selectbox(
                "Open an experiment",
                options=[int(member["experiment_id"]) for member in members if member.get("experiment_id") is not None],
                format_func=lambda experiment_id: next(
                    (
                        f"{member['experiment_name']} | {member['project_name']} | "
                        f"{member.get('ontology_root_batch_name') or 'Unmapped'}"
                    )
                    for member in members
                    if member.get("experiment_id") == experiment_id
                ),
                key="study_workspace_open_experiment_select",
            )
            selected_member = next(
                member for member in members if member.get("experiment_id") == selected_member_id
            )
            drilldown_cols = st.columns([0.3, 0.3, 0.4])
            if drilldown_cols[0].button(
                "Open in Cell Inputs",
                use_container_width=True,
                key="study_workspace_open_experiment",
            ):
                open_experiment_callback(
                    int(selected_member["experiment_id"]),
                    int(selected_member["project_id"]),
                    str(selected_member["project_name"]),
                )
                st.rerun()

            subset_default = [selected_member_id]
            selected_subset_ids = drilldown_cols[1].multiselect(
                "Comparison subset",
                options=[int(member["experiment_id"]) for member in members if member.get("experiment_id") is not None],
                default=subset_default,
                format_func=lambda experiment_id: next(
                    member["experiment_name"]
                    for member in members
                    if member.get("experiment_id") == experiment_id
                ),
                key="study_workspace_comparison_subset",
            )
            subset_payload = build_study_workspace_comparison_payload(payload, selected_subset_ids)
            if drilldown_cols[2].button(
                "Subset to Comparison",
                disabled=subset_payload is None or queue_comparison_callback is None,
                use_container_width=True,
                key="study_workspace_subset_to_comparison",
            ):
                queue_comparison_callback(
                    subset_payload["project_id"],
                    subset_payload["project_name"],
                    subset_payload["experiment_names"],
                    f"{summary.get('workspace_name') or 'Workspace'} subset",
                )
                st.info(
                    f"Selected subset is loaded into Comparison for {subset_payload['project_name']}."
                )
            if selected_subset_ids and subset_payload is None:
                st.caption(
                    "The selected subset needs at least 2 experiments from one project before Comparison can open."
                )

    with lower_right:
        st.markdown("#### Lineage Context")
        root_batches = (payload.get("lineage_context") or {}).get("root_batches") or []
        if root_batches:
            root_batch_frame = pd.DataFrame(root_batches)
            st.dataframe(root_batch_frame, use_container_width=True, hide_index=True)
            available_roots = [row["Parent Batch"] for row in root_batches if row.get("Parent Batch")]
            selected_root = st.selectbox(
                "Focus a parent batch",
                options=available_roots,
                key="study_workspace_root_batch_select",
            )
            focus_context = ((payload.get("lineage_context") or {}).get("focus_contexts") or {}).get(
                selected_root
            )
            if st.button(
                "Focus in Lineage Explorer",
                use_container_width=True,
                key="study_workspace_focus_lineage",
            ):
                queue_lineage_explorer_focus(focus_context or {"root_batch_name": selected_root})
                st.info(f"{selected_root} is focused in the Lineage Explorer.")
        else:
            st.caption("No ontology-linked parent batches are available in this workspace.")

        st.markdown("#### Tracking Status")
        tracking_context = payload.get("tracking_context") or {}
        status_counts = tracking_context.get("status_counts") or {}
        tracking_metric_cols = st.columns(3)
        tracking_metric_cols[0].metric("Completed", int(status_counts.get("Completed", 0)))
        tracking_metric_cols[1].metric("Active", int(status_counts.get("Active", 0)))
        tracking_metric_cols[2].metric("Unknown", int(status_counts.get("Unknown", 0)))
        tracking_rows = tracking_context.get("rows") or []
        if tracking_rows:
            st.dataframe(pd.DataFrame(tracking_rows), use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.markdown("#### Notes")
        note_cols = st.columns([0.32, 0.5, 0.18])
        note_title = note_cols[0].text_input(
            "Title",
            key="study_workspace_note_title",
            placeholder="Interpretation, risk, next step",
        )
        note_body = note_cols[1].text_area(
            "Note",
            key="study_workspace_note_body",
            height=90,
            placeholder="Capture what this cohort is telling you and what should happen next.",
        )
        if note_cols[2].button(
            "Save Note",
            use_container_width=True,
            key="study_workspace_note_save",
        ):
            try:
                save_study_workspace_annotation(
                    selected_workspace_id,
                    title=note_title,
                    body=note_body,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["study_workspace_note_title"] = ""
                st.session_state["study_workspace_note_body"] = ""
                _workspace_notice("Saved note to the current workspace.")
                st.rerun()

        annotations = payload.get("annotations") or []
        if annotations:
            selected_annotation_id = st.selectbox(
                "Saved notes",
                options=[int(annotation["id"]) for annotation in annotations],
                format_func=lambda annotation_id: _annotation_label(
                    next(
                        annotation
                        for annotation in annotations
                        if int(annotation["id"]) == int(annotation_id)
                    )
                ),
                key="study_workspace_annotation_select",
            )
            selected_annotation = next(
                annotation
                for annotation in annotations
                if int(annotation["id"]) == int(selected_annotation_id)
            )
            st.text_area(
                "Workspace note",
                value=selected_annotation.get("body") or "",
                height=160,
                key="study_workspace_note_preview",
            )
            if st.button(
                "Delete Note",
                use_container_width=False,
                key="study_workspace_note_delete",
            ):
                delete_study_workspace_annotation(selected_annotation_id)
                _workspace_notice("Removed the selected note.")
                st.rerun()
        else:
            st.caption("No notes saved yet for this workspace.")
