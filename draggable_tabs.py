"""Helpers for managing the order of the main Streamlit tabs."""

from __future__ import annotations

import hashlib

BASE_MAIN_TAB_LABELS = [
    "Cell Inputs",
    "📊 Dashboard",
    "⚡ Cycler Tracking",
    "🗂️ Cohorts",
    "🧪 Study Workspace",
    "🧬 Lineage Explorer",
    "🏗️ Batch Builder",
    "Plots",
    "Export",
]
PROJECT_MAIN_TAB_LABELS = BASE_MAIN_TAB_LABELS + ["Comparison", "Master Table"]


def _clean_tab_label(label: object) -> str:
    return str(label).strip()


def normalize_tab_order(visible_tab_labels, saved_order=None) -> list[str]:
    """Return a de-duplicated tab order limited to the currently visible labels."""
    visible = [_clean_tab_label(label) for label in visible_tab_labels]
    visible = [label for label in visible if label]
    visible_set = set(visible)

    ordered: list[str] = []
    seen: set[str] = set()

    for label in [_clean_tab_label(item) for item in (saved_order or [])] + visible:
        if label and label in visible_set and label not in seen:
            ordered.append(label)
            seen.add(label)

    return ordered


def build_tab_order_storage_key(visible_tab_labels) -> str:
    normalized = normalize_tab_order(visible_tab_labels)
    digest = hashlib.sha1("|".join(normalized).encode("utf-8")).hexdigest()[:12]
    return f"cellscope-main-tab-order-v1-{digest}"


def get_available_main_tab_labels(has_project: bool) -> list[str]:
    return PROJECT_MAIN_TAB_LABELS if has_project else BASE_MAIN_TAB_LABELS


def move_tab(tab_order, tab_label: str, direction: int) -> list[str]:
    """Move a tab one position left or right within the current order."""
    ordered = [_clean_tab_label(label) for label in tab_order]
    target_label = _clean_tab_label(tab_label)
    if target_label not in ordered:
        return ordered

    current_index = ordered.index(target_label)
    next_index = current_index + direction
    if next_index < 0 or next_index >= len(ordered):
        return ordered

    ordered[current_index], ordered[next_index] = ordered[next_index], ordered[current_index]
    return ordered


def get_ordered_tab_labels(visible_tab_labels) -> list[str]:
    import streamlit as st

    state_key = build_tab_order_storage_key(visible_tab_labels)
    normalized_order = normalize_tab_order(
        visible_tab_labels,
        st.session_state.get(state_key),
    )
    st.session_state[state_key] = normalized_order
    return normalized_order


def render_tab_settings_section(visible_tab_labels, *, section_label: str = "Main Tabs") -> list[str]:
    import streamlit as st

    state_key = build_tab_order_storage_key(visible_tab_labels)
    current_order = get_ordered_tab_labels(visible_tab_labels)

    st.markdown(f"**{section_label}**")
    st.caption("Reorder the top tabs. Changes apply immediately.")

    if st.button("Reset order", key=f"{state_key}_reset", use_container_width=True):
        st.session_state[state_key] = normalize_tab_order(visible_tab_labels)
        st.rerun()

    st.markdown("---")

    for index, tab_label in enumerate(current_order):
        move_cols = st.columns([0.56, 0.22, 0.22])
        move_cols[0].markdown(f"{index + 1}. `{tab_label}`")

        move_left = move_cols[1].button(
            "Left",
            key=f"{state_key}_left_{index}",
            use_container_width=True,
            disabled=index == 0,
        )
        move_right = move_cols[2].button(
            "Right",
            key=f"{state_key}_right_{index}",
            use_container_width=True,
            disabled=index == len(current_order) - 1,
        )

        if move_left:
            st.session_state[state_key] = move_tab(current_order, tab_label, -1)
            st.rerun()

        if move_right:
            st.session_state[state_key] = move_tab(current_order, tab_label, 1)
            st.rerun()

    return current_order
