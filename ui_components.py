# ui_components.py
import streamlit as st
from typing import List, Dict, Any, Tuple
import pandas as pd
import uuid

def calculate_cell_metrics(df_cell, formation_cycles, disc_area_cm2):
    """Centralized metric calculation to avoid duplication"""
    metrics = {}
    
    # 1st Cycle Discharge Capacity
    first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
    metrics['max_qdis'] = max(first_three_qdis) if first_three_qdis else None
    
    # First Cycle Efficiency
    if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
        first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
        try:
            metrics['first_cycle_eff'] = float(first_cycle_eff) * 100
        except (ValueError, TypeError):
            metrics['first_cycle_eff'] = None
    else:
        metrics['first_cycle_eff'] = None
    
    # Cycle Life (expensive calculation - do once)
    qdis_series = get_qdis_series(df_cell)
    cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
    metrics['cycle_life_80'] = calculate_cycle_life_80(qdis_series, cycle_index_series)
    
    # Initial Areal Capacity
    areal_capacity, chosen_cycle, diff_pct, eff_val = get_initial_areal_capacity(df_cell, disc_area_cm2)
    metrics['areal_capacity'] = areal_capacity
    
    # Reversible Capacity
    if len(df_cell) > formation_cycles:
        metrics['reversible_capacity'] = df_cell['Q Dis (mAh/g)'].iloc[formation_cycles]
    else:
        metrics['reversible_capacity'] = None
    
    # Coulombic Efficiency (post-formation)
    eff_col = 'Efficiency (-)'
    qdis_col = 'Q Dis (mAh/g)'
    n_cycles = len(df_cell)
    ceff_values = []
    if eff_col in df_cell.columns and qdis_col in df_cell.columns and n_cycles > formation_cycles+1:
        prev_qdis = df_cell[qdis_col].iloc[formation_cycles]
        prev_eff = df_cell[eff_col].iloc[formation_cycles]
        for i in range(formation_cycles+1, n_cycles):
            curr_qdis = df_cell[qdis_col].iloc[i]
            curr_eff = df_cell[eff_col].iloc[i]
            try:
                pq = float(prev_qdis)
                cq = float(curr_qdis)
                pe = float(prev_eff)
                ce = float(curr_eff)
                if pq > 0 and (cq < 0.95 * pq or ce < 0.95 * pe):
                    break
                ceff_values.append(ce)
                prev_qdis = cq
                prev_eff = ce
            except (ValueError, TypeError):
                continue
    
    if ceff_values:
        metrics['coulombic_eff'] = sum(ceff_values) / len(ceff_values) * 100
    else:
        metrics['coulombic_eff'] = None
    
    return metrics

def render_toggle_section(dfs: List[Dict[str, Any]], enable_grouping: bool = False) -> Tuple[Dict[str, bool], Dict[str, bool], bool, bool, bool, Dict[str, bool], bool, bool, Dict[str, bool]]:
    """Render all toggles and return their states: show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers, hide_legend, group_plot_toggles."""
    with st.expander("⚙️ Graph Display Options", expanded=True):
        st.markdown("### Graph Display Options")
        dis_col, chg_col, eff_col = st.columns(3)

        # Helper functions for toggling all
        def set_all_discharge(val):
            for label in discharge_labels:
                st.session_state[f'show_{label}'] = val
        def set_all_charge(val):
            for label in charge_labels:
                st.session_state[f'show_{label}'] = val
        def set_all_efficiency(val):
            for label in efficiency_labels:
                st.session_state[f'show_{label}'] = val

        # Discharge toggles
        with dis_col:
            st.markdown("**Discharge Capacity**")
            discharge_labels = []
            for i, d in enumerate(dfs):
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_dis = f"{cell_name} Q Dis"
                discharge_labels.append(label_dis)
            if len(dfs) > 1:
                toggle_all_discharge = st.checkbox('Toggle All Discharge', value=True, key='toggle_all_discharge', on_change=set_all_discharge, args=(not st.session_state.get('toggle_all_discharge', True),))
            else:
                toggle_all_discharge = True

        # Charge toggles
        with chg_col:
            st.markdown("**Charge Capacity**")
            charge_labels = []
            for i, d in enumerate(dfs):
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_chg = f"{cell_name} Q Chg"
                charge_labels.append(label_chg)
            if len(dfs) > 1:
                toggle_all_charge = st.checkbox('Toggle All Charge', value=True, key='toggle_all_charge', on_change=set_all_charge, args=(not st.session_state.get('toggle_all_charge', True),))
            else:
                toggle_all_charge = True

        # Efficiency toggles
        with eff_col:
            st.markdown("**Efficiency**")
            efficiency_labels = []
            for i, d in enumerate(dfs):
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_eff = f"{cell_name} Efficiency"
                efficiency_labels.append(label_eff)
            if len(dfs) > 1:
                toggle_all_efficiency = st.checkbox('Toggle All Efficiency', value=False, key='toggle_all_efficiency', on_change=set_all_efficiency, args=(not st.session_state.get('toggle_all_efficiency', False),))
            else:
                toggle_all_efficiency = False

        show_lines = {}
        with dis_col:
            for label in discharge_labels:
                show_lines[label] = st.checkbox(f"Show {label}", value=toggle_all_discharge, key=f'show_{label}')
        with chg_col:
            for label in charge_labels:
                show_lines[label] = st.checkbox(f"Show {label}", value=toggle_all_charge, key=f'show_{label}')
        show_efficiency_lines = {}
        with eff_col:
            for label in efficiency_labels:
                show_efficiency_lines[label] = st.checkbox(f"Show {label}", value=toggle_all_efficiency, key=f'show_{label}')

        avg_line_toggles = {"Average Q Dis": True, "Average Q Chg": True, "Average Efficiency": True}
        group_plot_toggles = {"Group Q Dis": False, "Group Q Chg": False, "Group Efficiency": False}
        st.markdown("---")
        with st.expander("📊 Graphing Options", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                remove_last_cycle = st.checkbox('Remove last cycle', value=False)
            with col2:
                remove_markers = st.checkbox('Remove markers', value=False)
                show_graph_title = st.checkbox('Show graph title', value=False)
            with col3:
                hide_legend = st.checkbox('Hide Legend', value=False)
                show_average_performance = False
                if len(dfs) > 1:
                    show_average_performance = st.checkbox('Average Cell Performance', value=False)
        # Place average toggles in the same columns as the main toggles, if Average Cell Performance is checked
        if show_average_performance:
            with dis_col:
                avg_line_toggles["Average Q Dis"] = st.checkbox('Show Average Q Dis', value=True, key='show_avg_qdis')
            with chg_col:
                avg_line_toggles["Average Q Chg"] = st.checkbox('Show Average Q Chg', value=True, key='show_avg_qchg')
            with eff_col:
                avg_line_toggles["Average Efficiency"] = st.checkbox('Show Average Efficiency', value=True, key='show_avg_eff')
        # Group plotting toggles in expander if grouping is enabled
        if enable_grouping:
            with st.expander('Group Plotting Options', expanded=True):
                group_plot_toggles["Group Q Dis"] = st.checkbox('Plot Group Q Dis', value=True, key='plot_group_qdis')
                group_plot_toggles["Group Q Chg"] = st.checkbox('Plot Group Q Chg (Charge Capacity)', value=False, key='plot_group_qchg')
                group_plot_toggles["Group Efficiency"] = st.checkbox('Plot Group Efficiency', value=False, key='plot_group_eff')
        return show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers, hide_legend, group_plot_toggles

def render_retention_display_options() -> Tuple[bool, bool, bool, bool, bool]:
    """Render capacity retention plot display options and return their states: 
    remove_markers, hide_legend, show_graph_title, show_baseline_line, show_threshold_line."""
    
    with st.expander("🎨 Retention Plot Display Options", expanded=False):
        st.markdown("### Capacity Retention Plot Customization")
        
        # Main display controls
        display_col1, display_col2, display_col3 = st.columns(3)
        
        with display_col1:
            st.markdown("**Data Display**")
            remove_markers = st.checkbox(
                '🔘 Remove markers', 
                value=False,
                key='retention_remove_markers',
                help="Hide data point markers on the retention plot for cleaner lines"
            )
            show_graph_title = st.checkbox(
                '📝 Show graph title', 
                value=True,
                key='retention_show_title',
                help="Display the capacity retention plot title"
            )
        
        with display_col2:
            st.markdown("**Legend & Labels**")
            hide_legend = st.checkbox(
                '🏷️ Hide legend', 
                value=False,
                key='retention_hide_legend',
                help="Remove the plot legend (useful for single-cell data or cleaner visuals)"
            )
            
        with display_col3:
            st.markdown("**Reference Lines**")
            show_baseline_line = st.checkbox(
                '📏 Show 100% baseline', 
                value=True,
                key='retention_show_baseline',
                help="Display the horizontal reference line at 100% capacity"
            )
            show_threshold_line = st.checkbox(
                '🚨 Show threshold line', 
                value=True,
                key='retention_show_threshold',
                help="Display the horizontal threshold line at the selected retention percentage"
            )
    
    return remove_markers, hide_legend, show_graph_title, show_baseline_line, show_threshold_line

def render_cell_inputs(context_key=None, project_id=None, get_components_func=None):
    """Render multi-file upload and per-file inputs for each cell. Returns datasets list."""
    if context_key is None:
        context_key = str(uuid.uuid4())
    with st.expander('🧪 Cell Inputs', expanded=True):
        upload_key = f"multi_file_upload_{context_key}"
        uploaded_files = st.file_uploader('Upload CSV or XLSX file(s) for Cells', type=['csv', 'xlsx'], accept_multiple_files=True, key=upload_key)
        st.caption("💡 Supported formats: Biologic CSV files (semicolon-delimited) and Neware XLSX files (with 'cycle' sheet)")
        datasets = []
        if uploaded_files:
            # Handle multiple cells with assign-to-all functionality
            if len(uploaded_files) > 1:
                # First cell with assign-to-all checkbox
                with st.expander(f'Cell 1: {uploaded_files[0].name}', expanded=False):
                    col1, col2 = st.columns(2)
                    # --- Defaults logic ---
                    loading_default = st.session_state.get('loading_0', 20.0)
                    active_default = st.session_state.get('active_0', 90.0)
                    formation_default = st.session_state.get('formation_cycles_0', 4)
                    electrolyte_default = st.session_state.get('electrolyte_0', '1M LiPF6 1:1:1')
                    with col1:
                        disc_loading_0 = st.number_input(f'Disc loading (mg) for Cell 1', min_value=0.0, step=1.0, value=loading_default, key=f'loading_0')
                        formation_cycles_0 = st.number_input(f'Formation Cycles for Cell 1', min_value=0, step=1, value=formation_default, key=f'formation_cycles_0')
                    with col2:
                        active_material_0 = st.number_input(f'% Active material for Cell 1', min_value=0.0, max_value=100.0, step=1.0, value=active_default, key=f'active_0')
                        test_number_0 = st.text_input(f'Test Number for Cell 1', value='Cell 1', key=f'testnum_0')
                    
                    # Electrolyte selection
                    electrolyte_options = ['1M LiPF6 1:1:1', '1M LiTFSI 3:7 +10% FEC']
                    electrolyte_0 = st.selectbox(f'Electrolyte for Cell 1', electrolyte_options, 
                                               index=electrolyte_options.index(electrolyte_default) if electrolyte_default in electrolyte_options else 0,
                                               key=f'electrolyte_0')
                    
                    # Formulation table
                    st.markdown("**Formulation:**")
                    formulation_0 = render_formulation_table(f'formulation_0_{context_key}', project_id, get_components_func)
                    
                    assign_all = st.checkbox('Assign values to all cells', key=f'assign_all_cells_{context_key}')
                
                # Add first cell to datasets
                datasets.append({
                    'file': uploaded_files[0], 
                    'loading': disc_loading_0, 
                    'active': active_material_0, 
                    'testnum': test_number_0, 
                    'formation_cycles': formation_cycles_0,
                    'electrolyte': electrolyte_0,
                    'formulation': formulation_0
                })
                
                # Handle remaining cells
                for i in range(1, len(uploaded_files)):
                    uploaded_file = uploaded_files[i]
                    with st.expander(f'Cell {i+1}: {uploaded_file.name}', expanded=False):
                        col1, col2 = st.columns(2)
                        if assign_all:
                            # Use values from first cell
                            disc_loading = disc_loading_0
                            formation_cycles = formation_cycles_0
                            active_material = active_material_0
                            electrolyte = electrolyte_0
                            formulation = formulation_0
                        else:
                            # Individual inputs for this cell
                            loading_default = st.session_state.get(f'loading_{i}', disc_loading_0)
                            active_default = st.session_state.get(f'active_{i}', active_material_0)
                            formation_default = st.session_state.get(f'formation_cycles_{i}', formation_cycles_0)
                            electrolyte_default = st.session_state.get(f'electrolyte_{i}', electrolyte_0)
                            with col1:
                                disc_loading = st.number_input(f'Disc loading (mg) for Cell {i+1}', min_value=0.0, step=1.0, value=loading_default, key=f'loading_{i}')
                                formation_cycles = st.number_input(f'Formation Cycles for Cell {i+1}', min_value=0, step=1, value=formation_default, key=f'formation_cycles_{i}')
                            with col2:
                                active_material = st.number_input(f'% Active material for Cell {i+1}', min_value=0.0, max_value=100.0, step=1.0, value=active_default, key=f'active_{i}')
                            
                            # Electrolyte selection
                            electrolyte = st.selectbox(f'Electrolyte for Cell {i+1}', electrolyte_options, 
                                                     index=electrolyte_options.index(electrolyte_default) if electrolyte_default in electrolyte_options else 0,
                                                     key=f'electrolyte_{i}')
                            
                            # Formulation table
                            st.markdown("**Formulation:**")
                            formulation = render_formulation_table(f'formulation_{i}_{context_key}', project_id, get_components_func)
                        
                        # Test number is always individual (not assigned to all)
                        with col2:
                            default_test_num = f'Cell {i+1}'
                            test_number = st.text_input(f'Test Number for Cell {i+1}', value=default_test_num, key=f'testnum_{i}')
                        
                        datasets.append({
                            'file': uploaded_file, 
                            'loading': disc_loading, 
                            'active': active_material, 
                            'testnum': test_number, 
                            'formation_cycles': formation_cycles,
                            'electrolyte': electrolyte,
                            'formulation': formulation
                        })
            else:
                # Single cell - no assign-to-all needed
                uploaded_file = uploaded_files[0]
                with st.expander(f'Cell 1: {uploaded_file.name}', expanded=False):
                    col1, col2 = st.columns(2)
                    # --- Defaults logic ---
                    loading_default = st.session_state.get('loading_0', 20.0)
                    active_default = st.session_state.get('active_0', 90.0)
                    formation_default = st.session_state.get('formation_cycles_0', 4)
                    electrolyte_default = st.session_state.get('electrolyte_0', '1M LiPF6 1:1:1')
                    with col1:
                        disc_loading = st.number_input(f'Disc loading (mg) for Cell 1', min_value=0.0, step=1.0, value=loading_default, key=f'loading_0')
                        formation_cycles = st.number_input(f'Formation Cycles for Cell 1', min_value=0, step=1, value=formation_default, key=f'formation_cycles_0')
                    with col2:
                        active_material = st.number_input(f'% Active material for Cell 1', min_value=0.0, max_value=100.0, step=1.0, value=active_default, key=f'active_0')
                        test_number = st.text_input(f'Test Number for Cell 1', value='Cell 1', key=f'testnum_0')
                    
                    # Electrolyte selection
                    electrolyte_options = ['1M LiPF6 1:1:1', '1M LiTFSI 3:7 +10% FEC']
                    electrolyte = st.selectbox(f'Electrolyte for Cell 1', electrolyte_options, 
                                             index=electrolyte_options.index(electrolyte_default) if electrolyte_default in electrolyte_options else 0,
                                             key=f'electrolyte_0')
                    
                    # Formulation table
                    st.markdown("**Formulation:**")
                    formulation = render_formulation_table(f'formulation_0_{context_key}', project_id, get_components_func)
                    
                    datasets.append({
                        'file': uploaded_file, 
                        'loading': disc_loading, 
                        'active': active_material, 
                        'testnum': test_number, 
                        'formation_cycles': formation_cycles,
                        'electrolyte': electrolyte,
                        'formulation': formulation
                    })
    return datasets

def render_formulation_table(key_suffix, project_id=None, get_components_func=None):
    """Render a formulation table with Component and Dry Mass Fraction columns."""
    # Initialize formulation data in session state if not exists
    formulation_key = f'formulation_data_{key_suffix}'
    save_flag_key = f'formulation_saved_{key_suffix}'
    if formulation_key not in st.session_state:
        st.session_state[formulation_key] = [
            {'Component': '', 'Dry Mass Fraction (%)': 0.0}
        ]
    if save_flag_key not in st.session_state:
        st.session_state[save_flag_key] = False
    
    formulation_data = st.session_state[formulation_key]
    
    # Get previously used components from project if project_id and function are provided
    previous_components = []
    if project_id and get_components_func:
        try:
            previous_components = get_components_func(project_id)
        except Exception:
            previous_components = []
    
    # Create editable table
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        st.markdown("**Component**")
    with col2:
        st.markdown("**Dry Mass Fraction (%)**")
    with col3:
        st.markdown("**Actions**")
    
    # Display all rows (including empty ones)
    updated_formulation = []
    total_fraction = 0.0
    changed = False
    
    for i, row in enumerate(formulation_data):
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            # Component selection with dropdown for previous components
            component_options = ["Type new component..."] + previous_components
            current_component = row['Component']
            
            # Determine default selection
            if current_component in previous_components:
                default_index = previous_components.index(current_component) + 1  # +1 for "Type new component"
            else:
                default_index = 0  # "Type new component"
            
            selected_option = st.selectbox(
                f"Component", 
                component_options, 
                index=default_index,
                key=f'component_dropdown_{i}_{key_suffix}', 
                label_visibility="collapsed"
            )
            
            if selected_option == "Type new component...":
                # Show text input for new component
                component = st.text_input(
                    f"New Component", 
                    value=current_component if current_component not in previous_components else '',
                    key=f'component_text_{i}_{key_suffix}', 
                    label_visibility="collapsed",
                    placeholder="Enter component name"
                )
            else:
                # Use selected component from dropdown
                component = selected_option
                
        with col2:
            fraction = st.number_input(f"Fraction", value=row['Dry Mass Fraction (%)'], min_value=0.0, max_value=100.0, step=0.1, key=f'fraction_{i}_{key_suffix}', label_visibility="collapsed")
            total_fraction += fraction
        with col3:
            if st.button("🗑️", key=f'delete_{i}_{key_suffix}', help="Delete row"):
                # Remove this row and update session state
                st.session_state[formulation_key] = [row for j, row in enumerate(formulation_data) if j != i]
                st.session_state[save_flag_key] = False
                st.rerun()
        # Detect changes
        if component != row['Component'] or fraction != row['Dry Mass Fraction (%)']:
            changed = True
        # Always keep all rows, even if empty
        updated_formulation.append({'Component': component, 'Dry Mass Fraction (%)': fraction})
    
    # Add new row button
    if st.button(f"➕ Add Component", key=f'add_component_{key_suffix}'):
        st.session_state[formulation_key].append({'Component': '', 'Dry Mass Fraction (%)': 0.0})
        st.session_state[save_flag_key] = False
        st.rerun()
    
    # If any changes, reset the save flag
    if changed:
        st.session_state[save_flag_key] = False
    
    # Save/Done Editing button
    if st.button("💾 Save Formulation", key=f'save_formulation_{key_suffix}'):
        st.session_state[save_flag_key] = True
    
    # Validation (only show if saved)
    if st.session_state[save_flag_key]:
        if total_fraction > 100.0:
            st.error(f"⚠️ Total dry mass fraction ({total_fraction:.1f}%) exceeds 100%!")
        elif total_fraction < 99.9 and any(row['Component'] for row in updated_formulation):
            st.warning(f"⚠️ Total dry mass fraction ({total_fraction:.1f}%) is less than 100%")
        elif total_fraction >= 99.9 and total_fraction <= 100.1:
            st.success(f"✅ Total dry mass fraction: {total_fraction:.1f}%")
    
    # Update session state (keep all rows, even empty)
    st.session_state[formulation_key] = updated_formulation if updated_formulation else [{'Component': '', 'Dry Mass Fraction (%)': 0.0}]
    
    # Only filter out empty rows when returning
    filtered = [row for row in updated_formulation if row['Component'] or row['Dry Mass Fraction (%)'] > 0]
    return filtered

def get_qdis_series(df_cell):
    qdis_raw = df_cell['Q Dis (mAh/g)']
    if pd.api.types.is_scalar(qdis_raw):
        return pd.Series([qdis_raw]).dropna()
    else:
        return pd.Series(qdis_raw).dropna()

def calculate_cycle_life_80(qdis_series, cycle_index_series):
    if len(qdis_series) >= 4:
        initial_qdis = max(qdis_series.iloc[2], qdis_series.iloc[3])
    elif len(qdis_series) > 0:
        initial_qdis = qdis_series.iloc[-1]
    else:
        return None
    threshold = 0.8 * initial_qdis
    below_threshold = qdis_series <= threshold
    if below_threshold.any():
        first_below_idx = below_threshold.idxmin()
        return int(cycle_index_series.iloc[first_below_idx])
    else:
        return int(cycle_index_series.iloc[-1])

# --- Helper for robust areal capacity calculation ---
def get_initial_areal_capacity(df_cell, disc_area_cm2):
    # Use max of cycles 3 and 4 if available, else last available
    qdis_col = 'Q discharge (mA.h)'
    eff_col = 'Efficiency (-)'
    n = len(df_cell)
    if qdis_col not in df_cell.columns or n == 0:
        return None, None, None, None
    # Get values for cycles 1, 3, 4
    val1 = abs(df_cell[qdis_col].iloc[0]) if n >= 1 and not pd.isnull(df_cell[qdis_col].iloc[0]) else None
    val3 = abs(df_cell[qdis_col].iloc[2]) if n >= 3 and not pd.isnull(df_cell[qdis_col].iloc[2]) else None
    val4 = abs(df_cell[qdis_col].iloc[3]) if n >= 4 and not pd.isnull(df_cell[qdis_col].iloc[3]) else None
    # Choose best initial
    if n >= 4 and val3 is not None and val4 is not None:
        chosen_val = max(val3, val4)
        chosen_cycle = 4 if val4 >= val3 else 3
    elif n >= 4 and val3 is not None:
        chosen_val = val3
        chosen_cycle = 3
    elif n >= 4 and val4 is not None:
        chosen_val = val4
        chosen_cycle = 4
    elif n >= 3 and val3 is not None:
        chosen_val = val3
        chosen_cycle = 3
    else:
        last_val = df_cell[qdis_col].iloc[-1]
        chosen_val = abs(last_val) if not pd.isnull(last_val) else None
        chosen_cycle = n
    areal_capacity = chosen_val / disc_area_cm2 if chosen_val is not None else None
    # Compare to cycle 1
    warn = False
    diff_pct = None
    if val1 is not None and chosen_val is not None and chosen_cycle != 1:
        diff_pct = abs(chosen_val - val1) / val1 if val1 != 0 else None
        if diff_pct is not None and diff_pct > 0.2:
            warn = True
    # Check efficiency for chosen cycle
    eff_val = None
    if eff_col in df_cell.columns and n >= chosen_cycle:
        eff_val = df_cell[eff_col].iloc[chosen_cycle-1] if not pd.isnull(df_cell[eff_col].iloc[chosen_cycle-1]) else None
        try:
            if eff_val is not None and float(eff_val) < 0.8:
                warn = True
        except (ValueError, TypeError):
            pass  # Ignore non-numeric efficiency values
    return areal_capacity, chosen_cycle, diff_pct, eff_val

def display_summary_stats(dfs: List[Dict[str, Any]], disc_area_cm2: float, show_average_col: bool = True, group_assignments: List[str] = None, group_names: List[str] = None):
    """Display summary statistics as a table in Streamlit."""
    import pandas as pd
    # Calculate metrics once for all cells
    cell_metrics = []
    for i, d in enumerate(dfs):
        metrics = calculate_cell_metrics(d['df'], d.get('formation_cycles', 4), disc_area_cm2)
        cell_metrics.append(metrics)
    # Prepare summary data - reordered as requested: Reversible capacity, coulombic efficiency, 1st cycle discharge, 1st cycle efficiency, cycle life
    param_names = [
        "Reversible Capacity (mAh/g)",
        "Coulombic Efficiency (post-formation)",
        "1st Cycle Discharge Capacity (mAh/g)",
        "First Cycle Efficiency (%)",
        "Cycle Life (80%)",
        "Initial Areal Capacity (mAh/cm²)"
    ]
    summary_dict = {param: [] for param in param_names}
    cell_names = []
    for i, (d, metrics) in enumerate(zip(dfs, cell_metrics)):
        cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
        cell_names.append(cell_name)
        summary_dict[param_names[0]].append(metrics['reversible_capacity'])
        summary_dict[param_names[1]].append(metrics['coulombic_eff'])
        summary_dict[param_names[2]].append(metrics['max_qdis'])
        summary_dict[param_names[3]].append(metrics['first_cycle_eff'])
        summary_dict[param_names[4]].append(metrics['cycle_life_80'])
        summary_dict[param_names[5]].append(metrics['areal_capacity'])
    # Add group summary rows if grouping is enabled
    group_names_final = []
    if group_assignments is not None and group_names is not None:
        for group_idx, group_name in enumerate(group_names):
            group_indices = [i for i, g in enumerate(group_assignments) if g == group_name]
            if len(group_indices) > 1:
                group_metrics = [cell_metrics[i] for i in group_indices]
                # Calculate group averages
                avg_values = {}
                for param_key in ['max_qdis', 'first_cycle_eff', 'cycle_life_80', 'areal_capacity', 'reversible_capacity', 'coulombic_eff']:
                    values = [m[param_key] for m in group_metrics if m[param_key] is not None]
                    avg_values[param_key] = sum(values) / len(values) if values else None
                # Add to summary
                for i, param in enumerate(param_names):
                    param_keys = ['reversible_capacity', 'coulombic_eff', 'max_qdis', 'first_cycle_eff', 'cycle_life_80', 'areal_capacity']
                    summary_dict[param].append(avg_values[param_keys[i]])
                group_names_final.append(group_name + " (Group Avg)")
    # Compute overall averages
    if show_average_col and len(dfs) > 1:
        for param in param_names:
            vals = [v for v in summary_dict[param] if v is not None]
            avg = sum(vals) / len(vals) if vals else None
            summary_dict[param].append(avg)
        col_labels = cell_names + group_names_final + ["Average"]
    else:
        col_labels = cell_names + group_names_final
    # Ensure unique column labels (cell names, group names, Average)
    def make_unique(labels):
        seen = {}
        result = []
        for label in labels:
            if label not in seen:
                seen[label] = 1
                result.append(label)
            else:
                seen[label] += 1
                result.append(f"{label} ({seen[label]})")
        return result
    col_labels = make_unique(col_labels)
    # Format for display (updated for new column order)
    display_data = {}
    for idx, param in enumerate(param_names):
        row = []
        for v in summary_dict[param]:
            if v is None:
                row.append("N/A")
            elif idx == 0:  # Reversible Capacity (mAh/g) - 1 decimal place
                row.append(f"{v:.1f}")
            elif idx == 1:  # Coulombic Efficiency (post-formation) - 3 decimal places
                row.append(f"{v:.3f}%")
            elif idx == 2:  # 1st Cycle Discharge Capacity (mAh/g) - 1 decimal place
                row.append(f"{v:.1f}")
            elif idx == 3:  # First Cycle Efficiency (%) - 3 decimal places
                row.append(f"{v:.3f}%")
            elif idx == 4:  # Cycle Life (80%) - 1 decimal place
                row.append(f"{v:.1f}")
            elif idx == 5:  # Initial Areal Capacity (mAh/cm²) - 2 decimal places
                row.append(f"{v:.2f}")
            else:
                row.append(f"{v:.1f}")
        display_data[param] = row
    df = pd.DataFrame(display_data, index=col_labels).T
    df = df.T
    # Keep existing styling logic
    def style_table(styler):
        styler.set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#2563eb'), ('color', '#fff'), ('font-weight', 'bold'), ('font-size', '1.1em'), ('border-radius', '8px 8px 0 0'), ('padding', '10px')]},
            {'selector': 'td', 'props': [('background-color', '#fff'), ('color', '#222'), ('font-size', '1em'), ('padding', '10px')]},
            {'selector': 'tr:hover td', 'props': [('background-color', '#e0e7ef')]} ,
            {'selector': 'table', 'props': [('border-collapse', 'separate'), ('border-spacing', '0'), ('border-radius', '12px'), ('overflow', 'hidden'), ('box-shadow', '0 2px 8px rgba(0,0,0,0.07)')]} 
        ])
        styler.apply(lambda x: ['background-color: #f3f6fa' if i%2==0 else '' for i in range(len(x))], axis=1)
        for group_name in group_names_final:
            if group_name in df.index:
                styler.apply(lambda x: ['background-color: #fef3c7' if x.name == group_name else '' for _ in x], axis=1)
        if 'Average' in df.index:
            styler.apply(lambda x: ['background-color: #fbbf24' if x.name == 'Average' else '' for _ in x], axis=1)
        styler.set_properties(**{'border': '1px solid #d1d5db'})
        return styler
    styled = df.style.pipe(style_table)
    st.markdown('<style>table {margin-bottom: 2em;} th, td {text-align: center !important;} </style>', unsafe_allow_html=True)
    st.write(styled.to_html(escape=False), unsafe_allow_html=True)


def display_averages(dfs: List[Dict[str, Any]], show_averages: bool, disc_area_cm2: float):
    """Display averages in Streamlit if requested."""
    if show_averages and len(dfs) > 1:
        st.markdown("---")
        with st.expander("Average Values Across All Cells", expanded=True):
            # Calculate metrics once for all cells
            all_metrics = []
            for d in dfs:
                metrics = calculate_cell_metrics(d['df'], d.get('formation_cycles', 4), disc_area_cm2)
                all_metrics.append(metrics)
            
            # Calculate averages
            def safe_average(values):
                valid_values = [v for v in values if v is not None]
                return sum(valid_values) / len(valid_values) if valid_values else None
            
            avg_qdis = safe_average([m['max_qdis'] for m in all_metrics])
            avg_eff = safe_average([m['first_cycle_eff'] for m in all_metrics])
            avg_cycle_life = safe_average([m['cycle_life_80'] for m in all_metrics])
            avg_areal = safe_average([m['areal_capacity'] for m in all_metrics])
            avg_reversible = safe_average([m['reversible_capacity'] for m in all_metrics])
            avg_ceff = safe_average([m['coulombic_eff'] for m in all_metrics])
            
            # Display results
            if avg_qdis is not None:
                st.info(f"1st Cycle Discharge Capacity (mAh/g): {avg_qdis:.1f}")
            if avg_eff is not None:
                st.info(f"First Cycle Efficiency: {avg_eff:.1f}%")
            else:
                st.warning('No data for average First Cycle Efficiency.')
            if avg_cycle_life is not None:
                st.info(f"Cycle Life (80%): {avg_cycle_life:.0f}")
            if avg_areal is not None:
                st.info(f"Initial Areal Capacity (mAh/cm²): {avg_areal:.3f}")
            if avg_reversible is not None:
                st.info(f"Reversible Capacity (mAh/g): {avg_reversible:.1f}")
            else:
                st.warning('No data for average Reversible Capacity after formation.')
            if avg_ceff is not None:
                st.info(f"Coulombic Efficiency (post-formation): {avg_ceff:.2f}%")
            else:
                st.warning('No data for average Coulombic Efficiency (post-formation).') 