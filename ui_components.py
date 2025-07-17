# ui_components.py
import streamlit as st
from typing import List, Dict, Any, Tuple
import pandas as pd

def render_toggle_section(dfs: List[Dict[str, Any]]) -> Tuple[Dict[str, bool], Dict[str, bool], bool, bool, bool, Dict[str, bool], bool]:
    """Render all toggles and return their states: show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers."""
    st.markdown("### Graph Display Options")
    dis_col, chg_col, eff_col = st.columns(3)

    # Discharge toggles
    with dis_col:
        st.markdown("**Discharge Capacity**")
        discharge_labels = []
        for i, d in enumerate(dfs):
            cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
            label_dis = f"{cell_name} Q Dis"
            discharge_labels.append(label_dis)
        if len(dfs) > 1:
            toggle_all_discharge = st.checkbox('Toggle All Discharge', value=True, key='toggle_all_discharge')
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
            toggle_all_charge = st.checkbox('Toggle All Charge', value=True, key='toggle_all_charge')
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
            toggle_all_efficiency = st.checkbox('Toggle All Efficiency', value=False, key='toggle_all_efficiency')
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
    st.markdown("---")
    with st.expander("📊 Graphing Options", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            remove_last_cycle = st.checkbox('Remove last cycle', value=False)
            remove_markers = st.checkbox('Remove markers', value=False)
        with col2:
            show_graph_title = st.checkbox('Show graph title', value=False)
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
    return show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers

def render_cell_inputs() -> list:
    """Render file upload, disc loading, % active, test number inputs for each cell. Handles add/remove and returns datasets list."""
    if 'num_datasets' not in st.session_state:
        st.session_state['num_datasets'] = 1
    if 'cell_indices' not in st.session_state:
        st.session_state['cell_indices'] = [0]
    if 'next_cell_idx' not in st.session_state:
        st.session_state['next_cell_idx'] = 1
    with st.expander('🧪 Cell Inputs', expanded=True):
        cols = st.columns(len(st.session_state['cell_indices']))
        header_cols = st.columns(len(st.session_state['cell_indices']))
        for i, idx in enumerate(st.session_state['cell_indices']):
            with header_cols[i]:
                col_head = st.columns([8,1])
                with col_head[0]:
                    st.markdown(f'**Cell {i+1}**')
                with col_head[1]:
                    if i > 0:
                        if st.button('➖', key=f'remove_{idx}_{i}'):
                            st.session_state['cell_indices'].remove(idx)
                            st.rerun()
        # Only render the '+ Comparison' button once, below the cell columns
        st.markdown('')
        if len(st.session_state['cell_indices']) < 6:
            if st.button('➕ Add Comparison', key='add_comparison'):
                st.session_state['cell_indices'].append(st.session_state['next_cell_idx'])
                st.session_state['next_cell_idx'] += 1
                st.rerun()
        datasets = []
        # Get first cell's values from session_state if available, else use defaults
        first_loading = st.session_state.get('loading_0', 20.0)
        first_active = st.session_state.get('active_0', 90.0)
        for i, idx in enumerate(st.session_state['cell_indices']):
            with cols[i]:
                uploaded_file = st.file_uploader(f'Upload CSV file for Cell {i+1}', type=['csv'], key=f'file_{idx}')
                if i == 0:
                    disc_loading = st.number_input(f'Disc loading (mg) for Cell {i+1}', min_value=0.0, step=1.0, value=20.0, key=f'loading_{idx}')
                    active_material = st.number_input(f'% Active material for Cell {i+1}', min_value=0.0, max_value=100.0, step=1.0, value=90.0, key=f'active_{idx}')
                else:
                    disc_loading = st.number_input(f'Disc loading (mg) for Cell {i+1}', min_value=0.0, step=1.0, value=first_loading, key=f'loading_{idx}')
                    active_material = st.number_input(f'% Active material for Cell {i+1}', min_value=0.0, max_value=100.0, step=1.0, value=first_active, key=f'active_{idx}')
                formation_cycles = st.number_input(f'Formation Cycles for Cell {i+1}', min_value=0, step=1, value=4, key=f'formation_cycles_{idx}')
                default_test_num = f'Cell {i+1}'
                test_number = st.text_input(f'Test Number for Cell {i+1}', value=default_test_num, key=f'testnum_{idx}')
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
        if eff_val is not None and eff_val < 0.8:
            warn = True
    return areal_capacity, chosen_cycle, diff_pct, eff_val

def display_summary_stats(dfs: List[Dict[str, Any]], disc_area_cm2: float):
    """Display summary statistics in Streamlit."""
    with st.expander('Summary Values', expanded=True):
        summary_cols = st.columns(len(dfs))
        for i, d in enumerate(dfs):
            with summary_cols[i]:
                df_cell = d['df']
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                warnings = []
                st.markdown(f"**{cell_name}**")
                first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
                max_qdis = max(first_three_qdis) if first_three_qdis else None
                if isinstance(max_qdis, (int, float)) and max_qdis is not None:
                    st.info(f"1st Cycle Discharge Capacity (mAh/g): {max_qdis:.1f}")
                else:
                    warnings.append('Not enough data for 1st cycle discharge capacity.')
                if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
                    first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
                    eff_pct = first_cycle_eff * 100
                    if isinstance(eff_pct, (int, float)):
                        st.info(f"First Cycle Efficiency: {eff_pct:.1f}%")
                    else:
                        warnings.append('Invalid efficiency data format.')
                else:
                    warnings.append('Efficiency (-) column not found in data.')
                # Updated cycle life calculation
                qdis_series = get_qdis_series(df_cell)
                cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
                cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
                st.info(f"Cycle Life (80%): {cycle_life_80 if cycle_life_80 is not None else 'N/A'}")
                # Initial Areal Capacity (mAh/cm²) using robust logic
                areal_capacity, chosen_cycle, diff_pct, eff_val = get_initial_areal_capacity(df_cell, disc_area_cm2)
                if areal_capacity is not None:
                    st.info(f"Initial Areal Capacity (mAh/cm²): {areal_capacity:.3f} (Cycle {chosen_cycle})")
                    if diff_pct is not None and diff_pct > 0.2:
                        warnings.append(f"Areal capacity differs >20% from cycle 1.")
                    if eff_val is not None and eff_val < 0.8:
                        warnings.append(f"Efficiency for chosen cycle is <80%.")
                else:
                    warnings.append('No data for Initial Areal Capacity.')
                # Reversible Capacity (mAh/g) after formation
                formation_cycles = d.get('formation_cycles', 4)
                if len(df_cell) > formation_cycles:
                    reversible_capacity = df_cell['Q Dis (mAh/g)'].iloc[formation_cycles]
                    st.info(f"Reversible Capacity (mAh/g): {reversible_capacity:.1f} (Cycle {formation_cycles+1})")
                else:
                    warnings.append('Not enough cycles for Reversible Capacity after formation.')
                # Coulombic Efficiency (post-formation, %) calculation
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
                        # Check for >5% drop in Q Dis or Efficiency
                        if prev_qdis > 0 and (curr_qdis < 0.95 * prev_qdis or curr_eff < 0.95 * prev_eff):
                            break
                        ceff_values.append(curr_eff)
                        prev_qdis = curr_qdis
                        prev_eff = curr_eff
                if ceff_values:
                    avg_ceff = sum(ceff_values) / len(ceff_values) * 100
                    st.info(f"Coulombic Efficiency (post-formation, %): {avg_ceff:.2f}")
                else:
                    st.info("Coulombic Efficiency (post-formation, %): N/A")
                # Show all warnings at the bottom
                for w in warnings:
                    st.warning(w)


def display_averages(dfs: List[Dict[str, Any]], show_averages: bool, disc_area_cm2: float):
    """Display averages in Streamlit if requested."""
    if show_averages and len(dfs) > 1:
        st.markdown("---")
        st.markdown("**Average Values Across All Cells:**")
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
            st.info(f"Coulombic Efficiency (post-formation, %): {sum(avg_ceff_values)/len(avg_ceff_values):.2f}")
        else:
            st.warning('No data for average Coulombic Efficiency (post-formation).') 