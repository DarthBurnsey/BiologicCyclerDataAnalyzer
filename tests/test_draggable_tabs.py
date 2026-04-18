from draggable_tabs import (
    build_tab_order_storage_key,
    get_available_main_tab_labels,
    move_tab,
    normalize_tab_order,
)


def test_normalize_tab_order_filters_unknown_labels_and_appends_missing_tabs():
    visible = ["Cell Inputs", "Dashboard", "Plots", "Export"]
    saved = ["Plots", "Missing", "Dashboard", "Plots"]

    assert normalize_tab_order(visible, saved) == [
        "Plots",
        "Dashboard",
        "Cell Inputs",
        "Export",
    ]


def test_normalize_tab_order_uses_visible_order_when_nothing_is_saved():
    visible = ["Cell Inputs", "Dashboard", "Plots"]

    assert normalize_tab_order(visible) == visible


def test_tab_order_storage_key_changes_with_visible_tab_set():
    base_key = build_tab_order_storage_key(["Cell Inputs", "Dashboard", "Plots"])
    expanded_key = build_tab_order_storage_key(
        ["Cell Inputs", "Dashboard", "Plots", "Comparison"]
    )

    assert base_key != expanded_key


def test_move_tab_swaps_with_neighbor_and_respects_edges():
    ordered = ["Cell Inputs", "Dashboard", "Plots", "Export"]

    assert move_tab(ordered, "Plots", -1) == [
        "Cell Inputs",
        "Plots",
        "Dashboard",
        "Export",
    ]
    assert move_tab(ordered, "Cell Inputs", -1) == ordered
    assert move_tab(ordered, "Export", 1) == ordered


def test_available_main_tab_labels_match_project_context():
    base_tabs = get_available_main_tab_labels(False)
    project_tabs = get_available_main_tab_labels(True)

    assert "🧪 Study Workspace" in base_tabs
    assert "Comparison" not in base_tabs
    assert "Comparison" in project_tabs
