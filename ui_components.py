# ui_components.py
import streamlit as st
from typing import List, Dict, Any, Tuple
import pandas as pd

def render_toggle_section(dfs: List[Dict[str, Any]]) -> Tuple[Dict[str, bool], Dict[str, bool], bool, bool, bool, bool]:
    """Render all toggles and return their states: show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title."""
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

    show_average_performance_displayed = False
    st.markdown("---")
    with st.expander("📊 Graphing Options", expanded=False):
        remove_last_cycle = st.checkbox('Remove last cycle from graph', value=False)
        show_graph_title = st.checkbox('Show graph title', value=False)
        show_average_performance = False
        if len(dfs) > 1:
            show_average_performance = st.checkbox('Average cell performance', value=False)
    # Display options for toggling average line
    if show_average_performance:
        show_average_performance_displayed = st.checkbox('Show Average Cell Performance', value=True, key='show_average_performance_displayed')
    return show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, show_average_performance_displayed

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
                default_test_num = f'Cell {i+1}'
                test_number = st.text_input(f'Test Number for Cell {i+1}', value=default_test_num, key=f'testnum_{idx}')
                datasets.append({'file': uploaded_file, 'loading': disc_loading, 'active': active_material, 'testnum': test_number})
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

def display_summary_stats(dfs: List[Dict[str, Any]]):
    """Display summary statistics in Streamlit."""
    summary_cols = st.columns(len(dfs))
    for i, d in enumerate(dfs):
        with summary_cols[i]:
            df_cell = d['df']
            cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
            st.markdown(f"**{cell_name}**")
            first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
            max_qdis = max(first_three_qdis) if first_three_qdis else None
            if isinstance(max_qdis, (int, float)) and max_qdis is not None:
                st.info(f"1st Cycle Discharge Capacity (mAh/g): {max_qdis:.1f}")
            else:
                st.warning('Not enough data for 1st cycle discharge capacity.')
            if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
                first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
                eff_pct = first_cycle_eff * 100
                if isinstance(eff_pct, (int, float)):
                    st.info(f"First Cycle Efficiency: {eff_pct:.1f}%")
                else:
                    st.warning('Invalid efficiency data format.')
            else:
                st.warning('Efficiency (-) column not found in data.')
            # Updated cycle life calculation
            qdis_series = get_qdis_series(df_cell)
            cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
            cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
            st.info(f"Cycle Life (80%): {cycle_life_80 if cycle_life_80 is not None else 'N/A'}")


def display_averages(dfs: List[Dict[str, Any]], show_averages: bool):
    """Display averages in Streamlit if requested."""
    if show_averages and len(dfs) > 1:
        st.markdown("---")
        st.markdown("**Average Values Across All Cells:**")
        avg_qdis_values = []
        avg_eff_values = []
        avg_cycle_life_values = []
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
            try:
                if not df_cell['Q Dis (mAh/g)'].empty:
                    qdis_raw = df_cell['Q Dis (mAh/g)']
                    if pd.api.types.is_scalar(qdis_raw):
                        qdis_series = pd.Series([qdis_raw]).dropna()
                    else:
                        qdis_series = pd.Series(qdis_raw).dropna()
                    if not qdis_series.empty:
                        initial_qdis = qdis_series.iloc[0]
                        threshold = 0.8 * initial_qdis
                        below_threshold = qdis_series <= threshold
                        if below_threshold.any():
                            first_below_idx = below_threshold.idxmin()
                            cycle_life_80 = int(df_cell.loc[first_below_idx, df_cell.columns[0]])
                        else:
                            cycle_life_80 = int(df_cell[df_cell.columns[0]].iloc[-1])
                        avg_cycle_life_values.append(cycle_life_80)
            except Exception:
                pass
        avg_cols = st.columns(3)
        with avg_cols[0]:
            if avg_qdis_values:
                avg_qdis = sum(avg_qdis_values) / len(avg_qdis_values)
                if isinstance(avg_qdis, (int, float)):
                    st.success(f"Avg 1st Cycle Discharge Capacity: {avg_qdis:.1f} mAh/g")
                else:
                    st.warning("Invalid discharge capacity data for averaging")
            else:
                st.warning("No discharge capacity data for averaging")
        with avg_cols[1]:
            if avg_eff_values:
                avg_eff = sum(avg_eff_values) / len(avg_eff_values)
                if isinstance(avg_eff, (int, float)):
                    st.success(f"Avg First Cycle Efficiency: {avg_eff:.1f}%")
                else:
                    st.warning("Invalid efficiency data for averaging")
            else:
                st.warning("No efficiency data for averaging")
        with avg_cols[2]:
            if avg_cycle_life_values:
                avg_cycle_life = sum(avg_cycle_life_values) / len(avg_cycle_life_values)
                if isinstance(avg_cycle_life, (int, float)):
                    st.success(f"Avg Cycle Life (80%): {avg_cycle_life:.0f}")
                else:
                    st.warning("Invalid cycle life data for averaging")
            else:
                st.warning("No cycle life data for averaging") 