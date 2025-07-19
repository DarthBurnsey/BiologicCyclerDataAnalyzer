# ui_components.py
import streamlit as st
from typing import List, Dict, Any, Tuple
import pandas as pd

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

def render_cell_inputs() -> list:
    """Render multi-file upload and per-file inputs for each cell. Returns datasets list."""
    with st.expander('🧪 Cell Inputs', expanded=True):
        uploaded_files = st.file_uploader('Upload CSV file(s) for Cells', type=['csv'], accept_multiple_files=True, key='multi_file_upload')
        datasets = []
        if uploaded_files:
            for i, uploaded_file in enumerate(uploaded_files):
                with st.expander(f'Cell {i+1}: {uploaded_file.name}', expanded=False):
                    col1, col2 = st.columns(2)
                    # --- Defaults logic ---
                    if i == 0:
                        # First cell: use hardcoded defaults if not in session_state
                        loading_default = st.session_state.get('loading_0', 20.0)
                        active_default = st.session_state.get('active_0', 90.0)
                        formation_default = st.session_state.get('formation_cycles_0', 4)
                    else:
                        # Subsequent cells: use first cell's values if available, else hardcoded defaults
                        loading_default = st.session_state.get(f'loading_{i}', st.session_state.get('loading_0', 20.0))
                        active_default = st.session_state.get(f'active_{i}', st.session_state.get('active_0', 90.0))
                        formation_default = st.session_state.get(f'formation_cycles_{i}', st.session_state.get('formation_cycles_0', 4))
                    with col1:
                        disc_loading = st.number_input(f'Disc loading (mg) for Cell {i+1}', min_value=0.0, step=1.0, value=loading_default, key=f'loading_{i}')
                        formation_cycles = st.number_input(f'Formation Cycles for Cell {i+1}', min_value=0, step=1, value=formation_default, key=f'formation_cycles_{i}')
                    with col2:
                        active_material = st.number_input(f'% Active material for Cell {i+1}', min_value=0.0, max_value=100.0, step=1.0, value=active_default, key=f'active_{i}')
                        default_test_num = f'Cell {i+1}'
                        test_number = st.text_input(f'Test Number for Cell {i+1}', value=default_test_num, key=f'testnum_{i}')
                    datasets.append({'file': uploaded_file, 'loading': disc_loading, 'active': active_material, 'testnum': test_number, 'formation_cycles': formation_cycles})
    return datasets

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
    # Prepare summary data
    param_names = [
        "1st Cycle Discharge Capacity (mAh/g)",
        "First Cycle Efficiency (%)",
        "Cycle Life (80%)",
        "Initial Areal Capacity (mAh/cm²)",
        "Reversible Capacity (mAh/g)",
        "Coulombic Efficiency (post-formation)"
    ]
    summary_dict = {param: [] for param in param_names}
    cell_names = []
    for i, d in enumerate(dfs):
        df_cell = d['df']
        cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
        cell_names.append(cell_name)
        # 1st Cycle Discharge Capacity (mAh/g)
        first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
        max_qdis = max(first_three_qdis) if first_three_qdis else None
        summary_dict[param_names[0]].append(max_qdis if isinstance(max_qdis, (int, float)) else None)
        # First Cycle Efficiency (%)
        if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
            first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
            eff_pct = first_cycle_eff * 100
            summary_dict[param_names[1]].append(eff_pct if isinstance(eff_pct, (int, float)) else None)
        else:
            summary_dict[param_names[1]].append(None)
        # Cycle Life (80%)
        qdis_series = get_qdis_series(df_cell)
        cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
        cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
        summary_dict[param_names[2]].append(cycle_life_80 if isinstance(cycle_life_80, (int, float)) else None)
        # Initial Areal Capacity (mAh/cm²)
        areal_capacity, chosen_cycle, diff_pct, eff_val = get_initial_areal_capacity(df_cell, disc_area_cm2)
        summary_dict[param_names[3]].append(areal_capacity if areal_capacity is not None else None)
        # Reversible Capacity (mAh/g)
        formation_cycles = d.get('formation_cycles', 4)
        if len(df_cell) > formation_cycles:
            reversible_capacity = df_cell['Q Dis (mAh/g)'].iloc[formation_cycles]
            summary_dict[param_names[4]].append(reversible_capacity if isinstance(reversible_capacity, (int, float)) else None)
        else:
            summary_dict[param_names[4]].append(None)
        # Coulombic Efficiency (post-formation, %)
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
            avg_ceff = sum(ceff_values) / len(ceff_values) * 100
            summary_dict[param_names[5]].append(avg_ceff)
        else:
            summary_dict[param_names[5]].append(None)
    
    # Add group summary rows if grouping is enabled
    group_names_final = []
    if group_assignments is not None and group_names is not None:
        for group_idx, group_name in enumerate(group_names):
            group_dfs = [df for df, g in zip(dfs, group_assignments) if g == group_name]
            if len(group_dfs) > 1:
                avg_qdis_values = []
                avg_eff_values = []
                avg_cycle_life_values = []
                avg_areal_capacity_values = []
                avg_reversible_capacities = []
                avg_ceff_values = []
                for d in group_dfs:
                    df_cell = d['df']
                    first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
                    max_qdis = max(first_three_qdis) if first_three_qdis else None
                    if max_qdis is not None:
                        avg_qdis_values.append(max_qdis)
                    if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
                        first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
                        eff_pct = first_cycle_eff * 100
                        avg_eff_values.append(eff_pct)
                    qdis_series = get_qdis_series(df_cell)
                    cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
                    cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
                    if cycle_life_80 is not None:
                        avg_cycle_life_values.append(cycle_life_80)
                    areal_capacity, chosen_cycle, diff_pct, eff_val = get_initial_areal_capacity(df_cell, disc_area_cm2)
                    if areal_capacity is not None:
                        avg_areal_capacity_values.append(areal_capacity)
                    formation_cycles = d.get('formation_cycles', 4)
                    if len(df_cell) > formation_cycles:
                        reversible_capacity = df_cell['Q Dis (mAh/g)'].iloc[formation_cycles]
                        avg_reversible_capacities.append(reversible_capacity)
                    # Coulombic Efficiency (post-formation, %)
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
                        avg_ceff = sum(ceff_values) / len(ceff_values) * 100
                        avg_ceff_values.append(avg_ceff)
                avg_qdis = sum(avg_qdis_values) / len(avg_qdis_values) if avg_qdis_values else 0
                avg_eff = sum(avg_eff_values) / len(avg_eff_values) if avg_eff_values else 0
                avg_cycle_life = sum(avg_cycle_life_values) / len(avg_cycle_life_values) if avg_cycle_life_values else 0
                avg_areal = sum(avg_areal_capacity_values) / len(avg_areal_capacity_values) if avg_areal_capacity_values else 0
                avg_reversible = sum(avg_reversible_capacities) / len(avg_reversible_capacities) if avg_reversible_capacities else None
                avg_ceff = sum(avg_ceff_values) / len(avg_ceff_values) if avg_ceff_values else None
                # Add group averages to summary dict
                for param in param_names:
                    if param == param_names[0]:  # 1st Cycle Discharge Capacity
                        summary_dict[param].append(avg_qdis)
                    elif param == param_names[1]:  # First Cycle Efficiency
                        summary_dict[param].append(avg_eff)
                    elif param == param_names[2]:  # Cycle Life
                        summary_dict[param].append(avg_cycle_life)
                    elif param == param_names[3]:  # Areal Capacity
                        summary_dict[param].append(avg_areal)
                    elif param == param_names[4]:  # Reversible Capacity
                        summary_dict[param].append(avg_reversible)
                    elif param == param_names[5]:  # Coulombic Efficiency
                        summary_dict[param].append(avg_ceff)
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
    
    # Format for display
    display_data = {}
    for idx, param in enumerate(param_names):
        row = []
        for v in summary_dict[param]:
            if v is None:
                row.append("N/A")
            elif idx == 1 or idx == 5:  # Efficiency columns
                row.append(f"{v:.2f}%")
            elif idx == 3:  # Areal capacity
                row.append(f"{v:.3f}")
            else:
                row.append(f"{v:.1f}")
        display_data[param] = row
    df = pd.DataFrame(display_data, index=col_labels).T
    # Transpose so cells are rows and parameters are columns
    df = df.T
    # Modern styling with more contrast
    def style_table(styler):
        styler.set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#2563eb'), ('color', '#fff'), ('font-weight', 'bold'), ('font-size', '1.1em'), ('border-radius', '8px 8px 0 0'), ('padding', '10px')]},
            {'selector': 'td', 'props': [('background-color', '#fff'), ('color', '#222'), ('font-size', '1em'), ('padding', '10px')]},
            {'selector': 'tr:hover td', 'props': [('background-color', '#e0e7ef')]} ,
            {'selector': 'table', 'props': [('border-collapse', 'separate'), ('border-spacing', '0'), ('border-radius', '12px'), ('overflow', 'hidden'), ('box-shadow', '0 2px 8px rgba(0,0,0,0.07)')]} 
        ])
        # Alternate row shading
        styler.apply(lambda x: ['background-color: #f3f6fa' if i%2==0 else '' for i in range(len(x))], axis=1)
        # Highlight group average rows
        for group_name in group_names_final:
            if group_name in df.index:
                styler.apply(lambda x: ['background-color: #fef3c7' if x.name == group_name else '' for _ in x], axis=1)
        # Highlight overall average row if present
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
            avg_qdis_values = []
            avg_eff_values = []
            avg_cycle_life_values = []
            avg_areal_capacity_values = []
            avg_reversible_capacities = []
            for d in dfs:
                df_cell = d['df']
                first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
                max_qdis = max(first_three_qdis) if first_three_qdis else None
                if max_qdis is not None:
                    avg_qdis_values.append(max_qdis)
                if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
                    first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
                    eff_pct = first_cycle_eff * 100
                    avg_eff_values.append(eff_pct)
                # Use the same logic as display_summary_stats for cycle life
                qdis_series = get_qdis_series(df_cell)
                cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
                cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
                if cycle_life_80 is not None:
                    avg_cycle_life_values.append(cycle_life_80)
                # Initial Areal Capacity (mAh/cm²) using robust logic
                areal_capacity, chosen_cycle, diff_pct, eff_val = get_initial_areal_capacity(df_cell, disc_area_cm2)
                if areal_capacity is not None:
                    avg_areal_capacity_values.append(areal_capacity)
                # Reversible Capacity (mAh/g) after formation
                formation_cycles = d.get('formation_cycles', 4)
                if len(df_cell) > formation_cycles:
                    reversible_capacity = df_cell['Q Dis (mAh/g)'].iloc[formation_cycles]
                    avg_reversible_capacities.append(reversible_capacity)
            # Calculate averages
            avg_qdis = sum(avg_qdis_values) / len(avg_qdis_values) if avg_qdis_values else 0
            avg_eff = sum(avg_eff_values) / len(avg_eff_values) if avg_eff_values else 0
            avg_cycle_life = sum(avg_cycle_life_values) / len(avg_cycle_life_values) if avg_cycle_life_values else 0
            avg_areal = sum(avg_areal_capacity_values) / len(avg_areal_capacity_values) if avg_areal_capacity_values else 0
            st.info(f"1st Cycle Discharge Capacity (mAh/g): {avg_qdis:.1f}")
            st.info(f"First Cycle Efficiency: {avg_eff:.1f}%")
            st.info(f"Cycle Life (80%): {avg_cycle_life:.0f}")
            st.info(f"Initial Areal Capacity (mAh/cm²): {avg_areal:.3f}")
            if avg_reversible_capacities:
                avg_reversible = sum(avg_reversible_capacities) / len(avg_reversible_capacities)
                st.info(f"Reversible Capacity (mAh/g): {avg_reversible:.1f}")
            else:
                st.warning('No data for average Reversible Capacity after formation.')
            # Average Coulombic Efficiency (post-formation, %)
            avg_ceff_values = []
            for d in dfs:
                df_cell = d['df']
                eff_col = 'Efficiency (-)'
                qdis_col = 'Q Dis (mAh/g)'
                formation_cycles = d.get('formation_cycles', 4)
                n_cycles = len(df_cell)
                ceff_values = []
                if eff_col in df_cell.columns and qdis_col in df_cell.columns and n_cycles > formation_cycles+1:
                    prev_qdis = df_cell[qdis_col].iloc[formation_cycles]
                    prev_eff = df_cell[eff_col].iloc[formation_cycles]
                    for i in range(formation_cycles+1, n_cycles):
                        curr_qdis = df_cell[qdis_col].iloc[i]
                        curr_eff = df_cell[eff_col].iloc[i]
                        if prev_qdis > 0 and (curr_qdis < 0.95 * prev_qdis or curr_eff < 0.95 * prev_eff):
                            break
                        ceff_values.append(curr_eff)
                        prev_qdis = curr_qdis
                        prev_eff = curr_eff
                if ceff_values:
                    avg_ceff = sum(ceff_values) / len(ceff_values) * 100
                    avg_ceff_values.append(avg_ceff)
            if avg_ceff_values:
                st.info(f"Coulombic Efficiency (post-formation): {sum(avg_ceff_values)/len(avg_ceff_values):.2f}%")
            else:
                st.warning('No data for average Coulombic Efficiency (post-formation).') 