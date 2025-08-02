import streamlit as st
import pandas as pd
import numpy as np
import json

def extract_formulation_data(experiment_summaries, individual_cells):
    """Extract formulation components and active material data from experiments."""
    all_components = set()
    component_data = {}
    active_material_data = {}
    
    # Process experiment summaries (Section 1)
    for exp in experiment_summaries:
        exp_name = exp['experiment_name']
        # Active material is already in the data
        active_material_data[exp_name] = exp.get('active_material', np.nan)
        
        # Extract formulation components if available
        if 'formulation_json' in exp:
            try:
                formulation = json.loads(exp['formulation_json'])
                if isinstance(formulation, list):
                    for item in formulation:
                        if isinstance(item, dict) and item.get('Component'):
                            component = item['Component'].strip()
                            all_components.add(component)
                            if exp_name not in component_data:
                                component_data[exp_name] = {}
                            component_data[exp_name][component] = item.get('Value', np.nan)
            except (json.JSONDecodeError, AttributeError):
                pass
    
    # Process individual cells (Section 2)
    for cell in individual_cells:
        cell_name = cell['cell_name']
        exp_name = cell.get('experiment_name', '')
        
        # Active material is already in the data
        active_material_data[cell_name] = cell.get('active_material', np.nan)
        
        # Extract formulation components if available
        if 'formulation_json' in cell:
            try:
                formulation = json.loads(cell['formulation_json'])
                if isinstance(formulation, list):
                    for item in formulation:
                        if isinstance(item, dict) and item.get('Component'):
                            component = item['Component'].strip()
                            all_components.add(component)
                            if cell_name not in component_data:
                                component_data[cell_name] = {}
                            component_data[cell_name][component] = item.get('Value', np.nan)
            except (json.JSONDecodeError, AttributeError):
                pass
    
    return sorted(list(all_components)), component_data, active_material_data

def display_experiment_summaries_table(experiment_summaries):
    """Display the experiment summaries table with column filtering and Active Material % column."""
    if not experiment_summaries:
        return
    
    # Extract formulation data and active material
    all_components, component_data, active_material_data = extract_formulation_data(experiment_summaries, [])
    
    # Define all possible columns
    all_columns = [
        'Experiment',
        'Active Material (%)',  # New column
        'Reversible Capacity (mAh/g)',
        'Coulombic Efficiency (%)',
        'Areal Capacity (mAh/cm²)',
        '1st Discharge (mAh/g)',
        'First Efficiency (%)',
        'Cycle Life (80%)',
        'Date'
    ]
    
    # Add component columns
    for component in all_components:
        all_columns.append(f'{component} (%)')
    
    # Column filtering with Excel-like interface
    with st.expander("🔧 Column Filter", expanded=False):
        st.markdown("**Select columns to display:**")
        
        # Initialize session state for column selection if not exists
        if 'section1_selected_columns' not in st.session_state:
            st.session_state.section1_selected_columns = all_columns[:8]  # Default to first 8 columns
        
        # Create columns for better layout
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # Main column selection with checkboxes
            st.markdown("**Data Columns:**")
            selected_columns = []
            
            # Core data columns (first 8)
            core_columns = all_columns[:8]
            for col in core_columns:
                if st.checkbox(col, value=col in st.session_state.section1_selected_columns, key=f"section1_core_{col}"):
                    selected_columns.append(col)
            
            # Component columns (if any)
            if all_components:
                st.markdown("**Component Columns:**")
                for component in all_components:
                    col_name = f'{component} (%)'
                    if st.checkbox(col_name, value=col_name in st.session_state.section1_selected_columns, key=f"section1_comp_{component}"):
                        selected_columns.append(col_name)
        
        with col2:
            st.markdown("**Quick Actions:**")
            if st.button("Select All", key="section1_select_all"):
                st.session_state.section1_selected_columns = all_columns
                st.rerun()
            
            if st.button("Clear All", key="section1_clear_all"):
                st.session_state.section1_selected_columns = []
                st.rerun()
        
        with col3:
            st.markdown("**Presets:**")
            if st.button("Core Data", key="section1_core_preset"):
                st.session_state.section1_selected_columns = all_columns[:8]
                st.rerun()
            
            if st.button("Performance", key="section1_perf_preset"):
                perf_columns = ['Experiment', 'Reversible Capacity (mAh/g)', 'Coulombic Efficiency (%)', 
                               '1st Discharge (mAh/g)', 'First Efficiency (%)', 'Cycle Life (80%)']
                st.session_state.section1_selected_columns = [col for col in perf_columns if col in all_columns]
                st.rerun()
        
        # Update session state
        st.session_state.section1_selected_columns = selected_columns
    
    # Display selected columns info
    if st.session_state.section1_selected_columns:
        st.info(f"📊 Showing {len(st.session_state.section1_selected_columns)} of {len(all_columns)} columns")
    else:
        st.warning("⚠️ No columns selected. Please select at least one column to display.")
        return
    
    # Prepare data
    df_data = []
    for exp in experiment_summaries:
        row = {
            'Experiment': exp['experiment_name'],
            'Active Material (%)': exp.get('active_material', np.nan),
            'Date': exp.get('experiment_date', np.nan),
            '1st Discharge (mAh/g)': exp['first_discharge'] if exp['first_discharge'] is not None else np.nan,
            'First Efficiency (%)': exp['first_efficiency'] if exp['first_efficiency'] is not None else np.nan,
            'Cycle Life (80%)': exp['cycle_life_80'] if exp['cycle_life_80'] is not None else np.nan,
            'Areal Capacity (mAh/cm²)': exp['areal_capacity'] if exp['areal_capacity'] is not None else np.nan,
            'Reversible Capacity (mAh/g)': exp['reversible_capacity'] if exp['reversible_capacity'] is not None else np.nan,
            'Coulombic Efficiency (%)': exp['coulombic_efficiency'] if exp['coulombic_efficiency'] is not None else np.nan
        }
        
        # Add component data
        exp_name = exp['experiment_name']
        for component in all_components:
            component_key = f'{component} (%)'
            if exp_name in component_data and component in component_data[exp_name]:
                row[component_key] = component_data[exp_name][component]
            else:
                row[component_key] = np.nan
        
        df_data.append(row)
    
    df = pd.DataFrame(df_data)
    
    # Filter to selected columns and maintain order
    available_columns = [col for col in st.session_state.section1_selected_columns if col in df.columns]
    df = df[available_columns]
    
    st.dataframe(df, use_container_width=True)

def display_individual_cells_table(individual_cells):
    """Display the individual cells table with column filtering and component columns."""
    if not individual_cells:
        return
    
    # Extract formulation data and active material
    all_components, component_data, active_material_data = extract_formulation_data([], individual_cells)
    
    # Define all possible columns
    all_columns = [
        'Cell Name',
        'Active Material (%)',  # Already exists, but ensure it's prominent
        'Reversible Capacity (mAh/g)',
        'Coulombic Efficiency (%)',
        'Areal Capacity (mAh/cm²)',
        '1st Discharge (mAh/g)',
        'First Efficiency (%)',
        'Cycle Life (80%)',
        'Loading (mg)',
        'Date',
        'Experiment'
    ]
    
    # Add component columns
    for component in all_components:
        all_columns.append(f'{component} (%)')
    
    # Column filtering with Excel-like interface
    with st.expander("🔧 Column Filter", expanded=False):
        st.markdown("**Select columns to display:**")
        
        # Initialize session state for column selection if not exists
        if 'section2_selected_columns' not in st.session_state:
            st.session_state.section2_selected_columns = all_columns[:11]  # Default to first 11 columns
        
        # Create columns for better layout
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # Main column selection with checkboxes
            st.markdown("**Data Columns:**")
            selected_columns = []
            
            # Core data columns (first 11)
            core_columns = all_columns[:11]
            for col in core_columns:
                if st.checkbox(col, value=col in st.session_state.section2_selected_columns, key=f"section2_core_{col}"):
                    selected_columns.append(col)
            
            # Component columns (if any)
            if all_components:
                st.markdown("**Component Columns:**")
                for component in all_components:
                    col_name = f'{component} (%)'
                    if st.checkbox(col_name, value=col_name in st.session_state.section2_selected_columns, key=f"section2_comp_{component}"):
                        selected_columns.append(col_name)
        
        with col2:
            st.markdown("**Quick Actions:**")
            if st.button("Select All", key="section2_select_all"):
                st.session_state.section2_selected_columns = all_columns
                st.rerun()
            
            if st.button("Clear All", key="section2_clear_all"):
                st.session_state.section2_selected_columns = []
                st.rerun()
        
        with col3:
            st.markdown("**Presets:**")
            if st.button("Core Data", key="section2_core_preset"):
                st.session_state.section2_selected_columns = all_columns[:11]
                st.rerun()
            
            if st.button("Performance", key="section2_perf_preset"):
                perf_columns = ['Cell Name', 'Reversible Capacity (mAh/g)', 'Coulombic Efficiency (%)', 
                               '1st Discharge (mAh/g)', 'First Efficiency (%)', 'Cycle Life (80%)', 'Experiment']
                st.session_state.section2_selected_columns = [col for col in perf_columns if col in all_columns]
                st.rerun()
        
        # Update session state
        st.session_state.section2_selected_columns = selected_columns
    
    # Display selected columns info
    if st.session_state.section2_selected_columns:
        st.info(f"📊 Showing {len(st.session_state.section2_selected_columns)} of {len(all_columns)} columns")
    else:
        st.warning("⚠️ No columns selected. Please select at least one column to display.")
        return
    
    # Prepare data
    df_data = []
    for cell in individual_cells:
        row = {
            'Experiment': cell.get('experiment_name', np.nan),
            'Cell Name': cell['cell_name'],
            'Active Material (%)': cell['active_material'] if cell['active_material'] is not None else np.nan,
            'Date': cell.get('experiment_date', np.nan),
            'Loading (mg)': cell['loading'] if cell['loading'] is not None else np.nan,
            '1st Discharge (mAh/g)': cell['first_discharge'] if cell['first_discharge'] is not None else np.nan,
            'First Efficiency (%)': cell['first_efficiency'] if cell['first_efficiency'] is not None else np.nan,
            'Cycle Life (80%)': cell['cycle_life_80'] if cell['cycle_life_80'] is not None else np.nan,
            'Areal Capacity (mAh/cm²)': cell['areal_capacity'] if cell['areal_capacity'] is not None else np.nan,
            'Reversible Capacity (mAh/g)': cell['reversible_capacity'] if cell['reversible_capacity'] is not None else np.nan,
            'Coulombic Efficiency (%)': cell['coulombic_efficiency'] if cell['coulombic_efficiency'] is not None else np.nan
        }
        
        # Add component data
        cell_name = cell['cell_name']
        for component in all_components:
            component_key = f'{component} (%)'
            if cell_name in component_data and component in component_data[cell_name]:
                row[component_key] = component_data[cell_name][component]
            else:
                row[component_key] = np.nan
        
        df_data.append(row)
    
    df = pd.DataFrame(df_data)
    
    # Filter to selected columns and maintain order
    available_columns = [col for col in st.session_state.section2_selected_columns if col in df.columns]
    df = df[available_columns]
    
    st.dataframe(df, use_container_width=True)

def display_best_performers_analysis(individual_cells):
    """Display the best performers analysis with the requested column order."""
    if not individual_cells:
        st.info("No individual cell data available for analysis.")
        return
    
    # Filter cells with valid data
    valid_cells = [cell for cell in individual_cells if any([
        cell['first_discharge'], cell['first_efficiency'], cell['cycle_life_80'], 
        cell['areal_capacity'], cell['reversible_capacity'], cell['coulombic_efficiency']
    ])]
    
    if not valid_cells:
        st.info("No valid data for performance analysis.")
        return
    
    # Find best performers for each metric (NEW ORDER)
    metrics = {
        'Highest Reversible Capacity': ('reversible_capacity', lambda x: x, 'mAh/g'),
        'Highest Coulombic Efficiency': ('coulombic_efficiency', lambda x: x, '%'),
        'Highest 1st Discharge Capacity': ('first_discharge', lambda x: x, 'mAh/g'),
        'Highest First Cycle Efficiency': ('first_efficiency', lambda x: x, '%'),
        'Highest Areal Capacity': ('areal_capacity', lambda x: x, 'mAh/cm²'),
        'Longest Cycle Life': ('cycle_life_80', lambda x: x, 'cycles')
    }
    
    st.markdown("#### 🥇 Best Individual Performers by Metric")
    
    cols = st.columns(2)
    for i, (metric_name, (field, transform, unit)) in enumerate(metrics.items()):
        with cols[i % 2]:
            valid_for_metric = [cell for cell in valid_cells if cell[field] is not None]
            if valid_for_metric:
                best_cell = max(valid_for_metric, key=lambda x: transform(x[field]))
                value = transform(best_cell[field])
                st.metric(
                    label=metric_name,
                    value=f"{value:.2f} {unit}" if isinstance(value, float) else f"{value} {unit}",
                    help=f"Cell: {best_cell['cell_name']} from {best_cell.get('experiment_name', 'Unknown')}"
                )
    
    st.markdown("#### 🏆 Overall Best Performer")
    
    # Calculate normalized scores for overall performance
    # Normalize each metric to 0-1 scale and sum them
    performance_scores = []
    
    for cell in valid_cells:
        score = 0
        valid_metrics = 0
        
        # Normalize each metric (higher is better for all)
        for field, transform, unit in metrics.values():
            if cell[field] is not None:
                all_values = [c[field] for c in valid_cells if c[field] is not None]
                if all_values:
                    min_val = min(all_values)
                    max_val = max(all_values)
                    if max_val > min_val:
                        normalized = (transform(cell[field]) - min_val) / (max_val - min_val)
                        score += normalized
                        valid_metrics += 1
        
        if valid_metrics > 0:
            avg_score = score / valid_metrics
            performance_scores.append((cell, avg_score, valid_metrics))
    
    if performance_scores:
        # Sort by average score descending
        performance_scores.sort(key=lambda x: x[1], reverse=True)
        
        best_overall = performance_scores[0]
        best_cell, best_score, metrics_count = best_overall
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.success(f"🏆 **{best_cell['cell_name']}** from experiment **{best_cell.get('experiment_name', 'Unknown')}**")
            st.markdown(f"**Overall Performance Score:** {best_score:.2f}/1.00 (based on {metrics_count} metrics)")
        
        with col2:
            # Show top 3 performers
            st.markdown("**Top 3 Overall:**")
            for i, (cell, score, _) in enumerate(performance_scores[:3]):
                medal = ["🥇", "🥈", "🥉"][i]
                st.write(f"{medal} {cell['cell_name']} ({score:.2f})")
    
    else:
        st.info("Insufficient data for overall performance ranking.")
    
    # New subsection with detailed rankings tables
    with st.expander("📊 Detailed Rankings Tables", expanded=False):
        # Create DataFrame for analysis
        df_data = []
        for cell in individual_cells:
            row = {
                'Cell': cell['cell_name'],
                'Experiment': cell.get('experiment_name', 'Unknown'),
                'Reversible Capacity (mAh/g)': cell['reversible_capacity'] if cell['reversible_capacity'] is not None else np.nan,
                'Coulombic Efficiency (%)': cell['coulombic_efficiency'] if cell['coulombic_efficiency'] is not None else np.nan,
                '1st Cycle Discharge (mAh/g)': cell['first_discharge'] if cell['first_discharge'] is not None else np.nan,
                'First Cycle Efficiency (%)': cell['first_efficiency'] if cell['first_efficiency'] is not None else np.nan,
                'Areal Capacity (mAh/cm²)': cell['areal_capacity'] if cell['areal_capacity'] is not None else np.nan,
                'Cycle Life (80%)': cell['cycle_life_80'] if cell['cycle_life_80'] is not None else np.nan
            }
            df_data.append(row)
        
        df = pd.DataFrame(df_data)
        
        # Remove rows with all NaN values in key metrics
        key_metrics = ['Reversible Capacity (mAh/g)', 'Coulombic Efficiency (%)', '1st Cycle Discharge (mAh/g)', 
                       'First Cycle Efficiency (%)', 'Areal Capacity (mAh/cm²)', 'Cycle Life (80%)']
        df_clean = df.dropna(subset=key_metrics, how='all')
        
        if df_clean.empty:
            st.info("No valid data available for detailed rankings.")
            return
        
        # Display best performers for each metric
        metrics_tables = {
            'Reversible Capacity (mAh/g)': 'Highest',
            'Coulombic Efficiency (%)': 'Highest', 
            '1st Cycle Discharge (mAh/g)': 'Highest',
            'First Cycle Efficiency (%)': 'Highest',
            'Areal Capacity (mAh/cm²)': 'Highest',
            'Cycle Life (80%)': 'Highest'
        }
        
        for metric, direction in metrics_tables.items():
            if metric in df_clean.columns and not df_clean[metric].isna().all():
                st.markdown(f"**{metric} - {direction} Values:**")
                
                # Sort by the metric
                if direction == 'Highest':
                    sorted_df = df_clean.sort_values(metric, ascending=False)
                else:
                    sorted_df = df_clean.sort_values(metric, ascending=True)
                
                # Show top 5
                top_5 = sorted_df.head(5)[['Cell', 'Experiment', metric]]
                st.dataframe(top_5, use_container_width=True)
                st.markdown("---")
