# Dataset Color Customization - Implementation Guide

## Overview
Comprehensive color customization system for both Comparison and Plots pages, allowing users to customize dataset colors with immediate visual feedback and session persistence.

## Implementation Summary

### Phase 1: UI Components ✅
**Files Modified:** `ui_components.py`

**New Functions:**
1. `get_default_color_palette()` - Returns the default color palette matching plotting module
2. `render_comparison_color_customization()` - UI for comparison plot color customization
3. `render_experiment_color_customization()` - UI for individual experiment plot color customization

**Key Features:**
- Session state management for color persistence
- Organized by experiment/cell/average/group
- Reset all colors button
- Automatic grouping of datasets
- Real-time updates via Streamlit's reactive framework

### Phase 2: Plotting Functions ✅
**Files Modified:** `plotting.py`

**Functions Updated:**
1. `plot_comparison_capacity_graph()` - Added `custom_colors` parameter
2. `plot_capacity_graph()` - Added `custom_colors` parameter  
3. `plot_capacity_retention_graph()` - Added `custom_colors` parameter

**Implementation Details:**
- All functions now accept `Optional[Dict[str, str]]` custom_colors parameter
- Custom colors checked first, then fall back to defaults
- Applies to:
  - Individual cell traces
  - Average lines (Q Dis, Q Chg, Efficiency)
  - Group averages (A, B, C)
  - All plot types (capacity, efficiency, retention)

### Phase 3: Integration (TO DO)
**Files to Modify:** `app.py`

## Integration Instructions

### For Comparison Page:

```python
# After render_comparison_plot_options() call:
# Add color customization UI
custom_colors = render_comparison_color_customization(
    experiments_plot_data, 
    show_average_performance
)

# Pass custom_colors to plotting function:
comparison_fig = plot_comparison_capacity_graph(
    experiments_plot_data,
    show_lines,
    show_efficiency_lines,
    remove_last_cycle,
    show_graph_title,
    show_average_performance,
    avg_line_toggles,
    remove_markers,
    hide_legend,
    cycle_filter,
    custom_colors=custom_colors  # ADD THIS
)
```

### For Individual Experiment Plots Page:

```python
# After plot options are rendered:
# Add color customization UI
custom_colors = render_experiment_color_customization(
    dfs,
    experiment_name,
    show_average_performance,
    enable_grouping,
    group_names
)

# Pass custom_colors to plotting functions:
fig = plot_capacity_graph(
    dfs, show_lines, show_efficiency_lines, remove_last_cycle, 
    show_graph_title, experiment_name, show_average_performance, 
    avg_line_toggles, remove_markers, hide_legend,
    group_a_curve=..., group_b_curve=..., group_c_curve=...,
    group_a_qchg=..., group_b_qchg=..., group_c_qchg=...,
    group_a_eff=..., group_b_eff=..., group_c_eff=...,
    group_names=group_names, cycle_filter=cycle_filter,
    custom_colors=custom_colors  # ADD THIS
)

# Similarly for retention plot:
retention_fig = plot_capacity_retention_graph(
    dfs, show_lines, reference_cycle, formation_cycles,
    remove_last_cycle, show_graph_title, experiment_name,
    show_average_performance, avg_line_toggles, remove_markers, hide_legend,
    group_a_curve=..., group_b_curve=..., group_c_curve=...,
    group_names=group_names, retention_threshold=...,
    y_axis_min=..., y_axis_max=...,
    show_baseline_line=..., show_threshold_line=...,
    cycle_filter=cycle_filter,
    custom_colors=custom_colors  # ADD THIS
)
```

## User Experience

### Color Customization UI

**Location:** Expandable section titled "🎨 Dataset Color Customization"

**Layout:**
- **Comparison Page:** Organized by experiment, then by cell/average
- **Plots Page:** Organized by type (Individual Cells, Average Lines, Group Averages)

**Features:**
1. **Color Pickers:** Standard Streamlit color picker for each dataset
2. **Reset Button:** "🔄 Reset All Colors" - restores all to defaults
3. **Smart Defaults:** Uses matplotlib color cycle or predefined colors
4. **Visual Feedback:** Color changes appear immediately in plots
5. **Help Text:** Each picker has hover text explaining what it controls

### Session Persistence

**Comparison Page:**
- Colors stored in `st.session_state.comp_custom_colors`
- Persists across page interactions within the same session
- Separate from individual experiment colors

**Individual Experiment Page:**
- Colors stored in `st.session_state.exp_custom_colors_{experiment_name}`
- Unique per experiment
- Persists within session for that experiment

### User Workflows

**Workflow 1: Customize Comparison Colors**
1. Navigate to Comparison page
2. Select experiments to compare
3. Expand "🎨 Dataset Color Customization"
4. Click color picker for desired dataset
5. Select new color
6. Plot updates immediately
7. Continue comparing with custom colors

**Workflow 2: Customize Individual Experiment Colors**
1. Navigate to Plots page, select experiment
2. Configure plot options
3. Expand "🎨 Dataset Color Customization"
4. Customize cell colors, average colors, or group colors
5. All plots (capacity, efficiency, retention) use same colors
6. Colors persist if you change plot options

**Workflow 3: Reset to Defaults**
1. Click "🔄 Reset All Colors" button
2. All colors instantly reset to defaults
3. Can then re-customize individual datasets

## Technical Details

### Color Storage Format
- **Key:** Dataset label (string)
  - Comparison: `"{exp_name} - {cell_name}"` or `"{exp_name} - Average"`
  - Individual: `"{cell_name}"`, `"Average"`, or `"{group_name}"`
- **Value:** Hex color string (e.g., `"#1f77b4"`)

### Default Color Schemes

**Comparison Plots:**
```python
['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
 '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
```

**Individual Experiment Plots:**
- Cells: Matplotlib default color cycle
- Average: Black (#000000) for Q Dis, Gray (#808080) for Q Chg, Orange (#FFA500) for Efficiency
- Groups: Blue (#0000FF), Red (#FF0000), Green (#00FF00)

### Legend Behavior
- Legends automatically update with custom colors
- Only visible datasets appear in legend
- Colors remain consistent across all interactions (zoom, pan, filter)

## Accessibility Considerations

1. **High Contrast Support:** Users can choose contrasting colors
2. **Color Blind Friendly:** Users can customize to their needs
3. **Visual Indicators:** Dataset selection via standard UI elements
4. **Reset Functionality:** Easy return to defaults if customization causes issues

## Testing Checklist

- [ ] Comparison page color customization renders correctly
- [ ] Individual experiment page color customization renders correctly
- [ ] Colors persist within session
- [ ] Colors apply to all plot types (capacity, efficiency, retention)
- [ ] Reset button works on both pages
- [ ] Colors work with "Show Averages" mode
- [ ] Colors work with cell grouping
- [ ] Legend updates correctly with custom colors
- [ ] Color pickers show current custom color
- [ ] Multiple experiments maintain separate colors on comparison page
- [ ] Export functionality preserves custom colors

## Next Steps

1. ✅ Create UI components
2. ✅ Update plotting functions
3. ⏳ Integrate into Comparison page (app.py)
4. ⏳ Integrate into Plots page (app.py)
5. ⏳ Test all workflows
6. ⏳ Update export functions if needed

## Benefits

- **User Control:** Complete customization of plot aesthetics
- **Immediate Feedback:** Changes apply instantly
- **Session Persistence:** Colors maintained during analysis
- **Accessibility:** Users can choose colors that work for them
- **Professional Output:** Create publication-ready plots with custom branding
- **Consistency:** Same colors across multiple plots and views




