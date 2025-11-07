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
        formulation_json = exp.get('formulation_json')
        if formulation_json and formulation_json not in (None, '', 'null'):
            try:
                formulation = json.loads(formulation_json)
                if isinstance(formulation, list):
                    for item in formulation:
                        if isinstance(item, dict) and item.get('Component'):
                            component = item['Component'].strip()
                            all_components.add(component)
                            if exp_name not in component_data:
                                component_data[exp_name] = {}
                            component_data[exp_name][component] = item.get('Dry Mass Fraction (%)', np.nan)
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass
    
    # Process individual cells (Section 2)
    for cell in individual_cells:
        cell_name = cell['cell_name']
        exp_name = cell.get('experiment_name', '')
        
        # Active material is already in the data
        active_material_data[cell_name] = cell.get('active_material', np.nan)
        
        # Extract formulation components if available
        formulation_json = cell.get('formulation_json')
        if formulation_json and formulation_json not in (None, '', 'null'):
            try:
                formulation = json.loads(formulation_json)
                if isinstance(formulation, list):
                    for item in formulation:
                        if isinstance(item, dict) and item.get('Component'):
                            component = item['Component'].strip()
                            all_components.add(component)
                            if cell_name not in component_data:
                                component_data[cell_name] = {}
                            component_data[cell_name][component] = item.get('Dry Mass Fraction (%)', np.nan)
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass
    
    return sorted(list(all_components)), component_data, active_material_data

def style_porosity(val):
    """Style porosity values with color coding for warnings."""
    if val == "N/A":
        return 'background-color: #ffcccc; color: #cc0000; font-weight: bold;'
    try:
        porosity_val = float(val.replace('%', ''))
        if porosity_val < 10 or porosity_val > 80:  # Unusual porosity range
            return 'background-color: #fff2cc; color: #cc6600; font-weight: bold;'
        elif porosity_val < 20 or porosity_val > 60:  # Warning range
            return 'background-color: #ffe6cc; color: #cc4400;'
        else:  # Normal range
            return ''
    except:
        return ''

def display_experiment_summaries_table(experiment_summaries):
    """Display the experiment summaries table with column filtering and Active Material % column."""
    if not experiment_summaries:
        return
    
    # Extract formulation data and active material
    all_components, component_data, active_material_data = extract_formulation_data(experiment_summaries, [])
    
    # Define all possible columns
    all_columns = [
        'Experiment',
        'Active Material (%)',
        'Loading (mg/cm²)',
        'Pressed Thickness (μm)',
        'Reversible Capacity (mAh/g)',
        'Coulombic Efficiency (%)',
        'Areal Capacity (mAh/cm²)',
        '1st Discharge (mAh/g)',
        'First Efficiency (%)',
        'Cycle Life (80%)',
        'Porosity (%)',
        'Electrolyte',
        'Substrate',
        'Separator',
        'Date'
    ]
    
    # Add component columns
    for component in all_components:
        all_columns.append(f'{component} (%)')
    
    # Improved Column Filter UI
    with st.expander("🔧 Column Filter", expanded=False):
        st.markdown("**Select columns to display:**")
        
        # Initialize session state for column selection if not exists
        if 'section1_selected_columns' not in st.session_state:
            st.session_state.section1_selected_columns = all_columns[:14]  # Default to first 14 columns including Electrolyte, Substrate, Separator
        
        # Quick Actions Row
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        with col1:
            if st.button("Select All", key="section1_select_all", use_container_width=True):
                st.session_state.section1_selected_columns = all_columns
                st.rerun()
        with col2:
            if st.button("Clear All", key="section1_clear_all", use_container_width=True):
                st.session_state.section1_selected_columns = []
                st.rerun()
        with col3:
            if st.button("Core Data", key="section1_core_preset", use_container_width=True):
                st.session_state.section1_selected_columns = all_columns[:14]
                st.rerun()
        with col4:
            if st.button("Performance", key="section1_perf_preset", use_container_width=True):
                perf_columns = ['Experiment', 'Reversible Capacity (mAh/g)', 'Coulombic Efficiency (%)', 
                               '1st Discharge (mAh/g)', 'First Efficiency (%)', 'Cycle Life (80%)']
                st.session_state.section1_selected_columns = [col for col in perf_columns if col in all_columns]
                st.rerun()
        
        st.markdown("---")
        
        # Column Selection in a more compact layout
        selected_columns = []
        
        # Core Data Columns (2 columns layout)
        st.markdown("**📊 Core Data Columns:**")
        core_cols = st.columns(2)
        
        # Split core columns between the two columns
        core_columns = all_columns[:14]  # First 14 columns including Electrolyte, Substrate, Separator
        mid_point = len(core_columns) // 2
        
        with core_cols[0]:
            for col in core_columns[:mid_point]:
                if st.checkbox(col, value=col in st.session_state.section1_selected_columns, key=f"section1_core_{col}"):
                    selected_columns.append(col)
        
        with core_cols[1]:
            for col in core_columns[mid_point:]:
                if st.checkbox(col, value=col in st.session_state.section1_selected_columns, key=f"section1_core_{col}"):
                    selected_columns.append(col)
        
        # Component columns (if any) in a scrollable container
        if all_components:
            st.markdown("**🧪 Component Columns:**")
            # Create a more compact layout for components
            comp_cols = st.columns(3)  # 3 columns for components
            comp_per_col = len(all_components) // 3 + 1
            
            for i, component in enumerate(all_components):
                col_idx = i // comp_per_col
                col_name = f'{component} (%)'
                with comp_cols[col_idx]:
                    if st.checkbox(col_name, value=col_name in st.session_state.section1_selected_columns, key=f"section1_comp_{component}"):
                        selected_columns.append(col_name)
        
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
        # Calculate loading density (mg/cm²)
        loading_density = np.nan
        if exp.get('loading') is not None and exp.get('disc_diameter_mm') is not None:
            disc_radius_cm = (exp['disc_diameter_mm'] / 2) / 10.0  # mm to cm
            disc_area_cm2 = np.pi * disc_radius_cm ** 2
            loading_density = exp['loading'] / disc_area_cm2
        
        row = {
            'Experiment': exp['experiment_name'],
            'Active Material (%)': f"{exp.get('active_material', np.nan):.1f}" if exp.get('active_material') is not None and not np.isnan(exp.get('active_material')) else np.nan,
            'Loading (mg/cm²)': f"{loading_density:.2f}" if loading_density is not np.nan else np.nan,
            'Pressed Thickness (μm)': f"{exp.get('pressed_thickness', np.nan):.1f}" if exp.get('pressed_thickness') is not None and not np.isnan(exp.get('pressed_thickness')) else np.nan,
            'Date': exp.get('experiment_date', np.nan),
            '1st Discharge (mAh/g)': exp['first_discharge'] if exp['first_discharge'] is not None else np.nan,
            'First Efficiency (%)': exp['first_efficiency'] if exp['first_efficiency'] is not None else np.nan,
            'Cycle Life (80%)': exp['cycle_life_80'] if exp['cycle_life_80'] is not None else np.nan,
            'Areal Capacity (mAh/cm²)': exp['areal_capacity'] if exp['areal_capacity'] is not None else np.nan,
            'Reversible Capacity (mAh/g)': exp['reversible_capacity'] if exp['reversible_capacity'] is not None else np.nan,
            'Coulombic Efficiency (%)': exp['coulombic_efficiency'] if exp['coulombic_efficiency'] is not None else np.nan,
            'Porosity (%)': f"{exp['porosity']*100:.1f}%" if exp['porosity'] is not None and exp['porosity'] > 0 else "N/A",
            'Electrolyte': exp.get('electrolyte', 'N/A'),
            'Substrate': exp.get('substrate', 'N/A'),
            'Separator': exp.get('separator', 'N/A'),
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
    
    # Display the dataframe with styling
    styled_df = df.style
    
    # Apply porosity styling if the column exists
    if 'Porosity (%)' in df.columns:
        styled_df = styled_df.map(style_porosity, subset=['Porosity (%)'])
    
    # Format numeric columns for display while preserving sortability
    format_dict = {}
    if 'Cycle Life (80%)' in df.columns:
        format_dict['Cycle Life (80%)'] = '{:.1f}'
    if 'Reversible Capacity (mAh/g)' in df.columns:
        format_dict['Reversible Capacity (mAh/g)'] = '{:.1f}'
    if 'Areal Capacity (mAh/cm²)' in df.columns:
        format_dict['Areal Capacity (mAh/cm²)'] = '{:.2f}'
    if '1st Discharge (mAh/g)' in df.columns:
        format_dict['1st Discharge (mAh/g)'] = '{:.1f}'
    if 'Coulombic Efficiency (%)' in df.columns:
        format_dict['Coulombic Efficiency (%)'] = '{:.3f}%'
    if 'First Efficiency (%)' in df.columns:
        format_dict['First Efficiency (%)'] = '{:.3f}%'
    
    # Add formatters for component columns
    for component in all_components:
        component_col = f'{component} (%)'
        if component_col in df.columns:
            format_dict[component_col] = lambda x: 'N/A' if pd.isna(x) else f"{x:.1f}"
    
    if format_dict:
        styled_df = styled_df.format(format_dict, na_rep='N/A')
    
    st.dataframe(styled_df, use_container_width=True)

def display_individual_cells_table(individual_cells):
    """Display the individual cells table with column filtering and component columns."""
    if not individual_cells:
        return
    
    # Extract formulation data and active material
    all_components, component_data, active_material_data = extract_formulation_data([], individual_cells)
    
    # Define all possible columns
    all_columns = [
        'Cell Name',
        'Active Material (%)',
        'Loading (mg/cm²)',
        'Pressed Thickness (μm)',
        'Reversible Capacity (mAh/g)',
        'Coulombic Efficiency (%)',
        'Areal Capacity (mAh/cm²)',
        '1st Discharge (mAh/g)',
        'First Efficiency (%)',
        'Cycle Life (80%)',
        'Porosity (%)',
        'Electrolyte',
        'Substrate',
        'Separator',
        'Date',
        'Experiment'
    ]
    
    # Add component columns
    for component in all_components:
        all_columns.append(f'{component} (%)')
    
    # Improved Column Filter UI
    with st.expander("🔧 Column Filter", expanded=False):
        st.markdown("**Select columns to display:**")
        
        # Initialize session state for column selection if not exists
        if 'section2_selected_columns' not in st.session_state:
            st.session_state.section2_selected_columns = all_columns[:14]  # Default to first 14 columns including Electrolyte, Substrate, Separator
        
        # Quick Actions Row
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        with col1:
            if st.button("Select All", key="section2_select_all", use_container_width=True):
                st.session_state.section2_selected_columns = all_columns
                st.rerun()
        with col2:
            if st.button("Clear All", key="section2_clear_all", use_container_width=True):
                st.session_state.section2_selected_columns = []
                st.rerun()
        with col3:
            if st.button("Core Data", key="section2_core_preset", use_container_width=True):
                st.session_state.section2_selected_columns = all_columns[:14]
                st.rerun()
        with col4:
            if st.button("Performance", key="section2_perf_preset", use_container_width=True):
                perf_columns = ['Cell Name', 'Reversible Capacity (mAh/g)', 'Coulombic Efficiency (%)', 
                               '1st Discharge (mAh/g)', 'First Efficiency (%)', 'Cycle Life (80%)', 'Experiment']
                st.session_state.section2_selected_columns = [col for col in perf_columns if col in all_columns]
                st.rerun()
        
        st.markdown("---")
        
        # Column Selection in a more compact layout
        selected_columns = []
        
        # Core Data Columns (2 columns layout)
        st.markdown("**📊 Core Data Columns:**")
        core_cols = st.columns(2)
        
        # Split core columns between the two columns
        core_columns = all_columns[:14]  # First 14 columns including Electrolyte, Substrate, Separator
        mid_point = len(core_columns) // 2
        
        with core_cols[0]:
            for col in core_columns[:mid_point]:
                if st.checkbox(col, value=col in st.session_state.section2_selected_columns, key=f"section2_core_{col}"):
                    selected_columns.append(col)
        
        with core_cols[1]:
            for col in core_columns[mid_point:]:
                if st.checkbox(col, value=col in st.session_state.section2_selected_columns, key=f"section2_core_{col}"):
                    selected_columns.append(col)
        
        # Component columns (if any) in a scrollable container
        if all_components:
            st.markdown("**🧪 Component Columns:**")
            # Create a more compact layout for components
            comp_cols = st.columns(3)  # 3 columns for components
            comp_per_col = len(all_components) // 3 + 1
            
            for i, component in enumerate(all_components):
                col_idx = i // comp_per_col
                col_name = f'{component} (%)'
                with comp_cols[col_idx]:
                    if st.checkbox(col_name, value=col_name in st.session_state.section2_selected_columns, key=f"section2_comp_{component}"):
                        selected_columns.append(col_name)
        
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
        # Calculate loading density (mg/cm²)
        loading_density = np.nan
        if cell.get('loading') is not None and cell.get('disc_diameter_mm') is not None:
            disc_radius_cm = (cell['disc_diameter_mm'] / 2) / 10.0  # mm to cm
            disc_area_cm2 = np.pi * disc_radius_cm ** 2
            loading_density = cell['loading'] / disc_area_cm2
        
        row = {
            'Experiment': cell.get('experiment_name', np.nan),
            'Cell Name': cell['cell_name'],
            'Active Material (%)': f"{cell['active_material']:.1f}" if cell['active_material'] is not None and not np.isnan(cell['active_material']) else np.nan,
            'Loading (mg/cm²)': f"{loading_density:.2f}" if loading_density is not np.nan else np.nan,
            'Pressed Thickness (μm)': f"{cell.get('pressed_thickness', np.nan):.1f}" if cell.get('pressed_thickness') is not None and not np.isnan(cell.get('pressed_thickness')) else np.nan,
            'Date': cell.get('experiment_date', np.nan),
            '1st Discharge (mAh/g)': cell['first_discharge'] if cell['first_discharge'] is not None else np.nan,
            'First Efficiency (%)': cell['first_efficiency'] if cell['first_efficiency'] is not None else np.nan,
            'Cycle Life (80%)': cell['cycle_life_80'] if cell['cycle_life_80'] is not None else np.nan,
            'Areal Capacity (mAh/cm²)': cell['areal_capacity'] if cell['areal_capacity'] is not None else np.nan,
            'Reversible Capacity (mAh/g)': cell['reversible_capacity'] if cell['reversible_capacity'] is not None else np.nan,
            'Coulombic Efficiency (%)': cell['coulombic_efficiency'] if cell['coulombic_efficiency'] is not None else np.nan,
            'Porosity (%)': f"{cell['porosity']*100:.1f}%" if cell['porosity'] is not None and cell['porosity'] > 0 else "N/A",
            'Electrolyte': cell.get('electrolyte', 'N/A'),
            'Substrate': cell.get('substrate', 'N/A'),
            'Separator': cell.get('separator', 'N/A'),
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
    
    # Display the dataframe with styling
    styled_df = df.style
    
    # Apply porosity styling if the column exists
    if 'Porosity (%)' in df.columns:
        styled_df = styled_df.map(style_porosity, subset=['Porosity (%)'])
    
    # Format numeric columns for display while preserving sortability
    format_dict = {}
    if 'Cycle Life (80%)' in df.columns:
        format_dict['Cycle Life (80%)'] = '{:.1f}'
    if 'Reversible Capacity (mAh/g)' in df.columns:
        format_dict['Reversible Capacity (mAh/g)'] = '{:.1f}'
    if 'Areal Capacity (mAh/cm²)' in df.columns:
        format_dict['Areal Capacity (mAh/cm²)'] = '{:.2f}'
    if '1st Discharge (mAh/g)' in df.columns:
        format_dict['1st Discharge (mAh/g)'] = '{:.1f}'
    if 'Coulombic Efficiency (%)' in df.columns:
        format_dict['Coulombic Efficiency (%)'] = '{:.3f}%'
    if 'First Efficiency (%)' in df.columns:
        format_dict['First Efficiency (%)'] = '{:.3f}%'
    
    # Add formatters for component columns
    for component in all_components:
        component_col = f'{component} (%)'
        if component_col in df.columns:
            format_dict[component_col] = lambda x: 'N/A' if pd.isna(x) else f"{x:.1f}"
    
    if format_dict:
        styled_df = styled_df.format(format_dict, na_rep='N/A')
    
    st.dataframe(styled_df, use_container_width=True)

def display_best_performers_analysis(individual_cells):
    """Display the best performers analysis with the requested column order."""
    if not individual_cells:
        st.info("No individual cell data available for analysis.")
        return
    
    # Import outlier detection
    try:
        from outlier_detection import filter_outliers, get_outlier_detection_ui_settings, BATTERY_DATA_BOUNDS
        
        # Get outlier detection settings from UI (including manual exclusions)
        outlier_settings = get_outlier_detection_ui_settings(individual_cells)
        
        # Extract manual exclusions from settings
        manual_exclusion_names = outlier_settings.get('manual_exclusions', [])
        
        # Apply outlier filtering
        filtered_cells, outlier_summary = filter_outliers(individual_cells, outlier_settings, manual_exclusion_names)
        
        # Show filtering summary
        total_cells = len(individual_cells)
        filtered_count = len(filtered_cells)
        excluded_count = total_cells - filtered_count
        
        if excluded_count > 0:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Cells", total_cells)
            with col2:
                st.metric("Included", filtered_count, delta=f"-{excluded_count}")
            with col3:
                st.metric("Excluded", excluded_count, delta_color="inverse")
        
        # Show outlier detection results
        if outlier_summary:
            total_outliers = sum(len(outliers) for outliers in outlier_summary.values())
            st.info(f"🔧 Applied field-specific filtering: {total_outliers} outlier data points excluded from {len(outlier_summary)} metrics (cells with valid data in other fields are still included)")
            
            with st.expander("🔍 View Detected Outliers", expanded=False):
                for field, outliers in outlier_summary.items():
                    st.markdown(f"**{BATTERY_DATA_BOUNDS.get(field, {}).get('description', field)}:**")
                    for outlier in outliers:
                        reasons = "; ".join(outlier['outlier_reasons'])
                        st.text(f"• {outlier['cell_name']} ({outlier['experiment_name']}): {outlier['value']:.3f} - {reasons}")
                    st.markdown("---")
                
                # Debug: Show which cells contain "L8" for troubleshooting
                l8_cells = [cell for cell in individual_cells if 'L8' in cell.get('cell_name', '')]
                if l8_cells:
                    st.markdown("**🔍 Debug: L8 Cells Analysis**")
                    for cell in l8_cells:
                        cell_name = cell.get('cell_name', 'Unknown')
                        is_excluded = cell_name not in [c.get('cell_name', '') for c in filtered_cells]
                        status = "EXCLUDED" if is_excluded else "INCLUDED"
                        cycle_life = cell.get('cycle_life_80', 'N/A')
                        st.text(f"• {cell_name}: Cycle Life = {cycle_life}, Status = {status}")
                        
                        # Check all fields for this cell
                        if is_excluded:
                            st.text(f"    Checking why {cell_name} is excluded:")
                            for check_field in ['first_efficiency', 'coulombic_efficiency', 'first_discharge', 
                                              'reversible_capacity', 'areal_capacity', 'cycle_life_80']:
                                value = cell.get(check_field)
                                if value is not None:
                                    from outlier_detection import detect_outliers_hard_bounds
                                    is_outlier, reason = detect_outliers_hard_bounds(cell, check_field)
                                    if is_outlier:
                                        st.text(f"      - {check_field}: {value} - OUTLIER ({reason})")
                    st.markdown("---")
        
        if manual_exclusion_names:
            st.info(f"📝 Manually excluded {len(manual_exclusion_names)} cells")
        
        if excluded_count == 0:
            st.success("✅ No cells excluded from analysis")
        
        # Use filtered cells for analysis
        valid_cells = [cell for cell in filtered_cells if any([
            cell['first_discharge'], cell['first_efficiency'], cell['cycle_life_80'], 
            cell['areal_capacity'], cell['reversible_capacity'], cell['coulombic_efficiency']
        ])]
        
    except ImportError:
        # Fallback to original behavior if outlier detection is not available
        st.warning("Outlier detection module not available. Using all data.")
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
            # Filter out cells that are outliers for THIS SPECIFIC field
            valid_for_metric = []
            for cell in valid_cells:
                if cell[field] is not None:
                    # Check if this cell is an outlier for this specific field
                    is_outlier_for_field = False
                    if field in outlier_summary:
                        for outlier in outlier_summary[field]:
                            if outlier['cell_name'] == cell['cell_name']:
                                is_outlier_for_field = True
                                break
                    
                    # Only include if not an outlier for this field
                    if not is_outlier_for_field:
                        valid_for_metric.append(cell)
            
            if valid_for_metric:
                best_cell = max(valid_for_metric, key=lambda x: transform(x[field]))
                value = transform(best_cell[field])
                
                # Apply appropriate formatting based on metric type
                if 'Reversible Capacity' in metric_name or '1st Discharge' in metric_name or 'Cycle Life' in metric_name:
                    formatted_value = f"{value:.1f} {unit}"
                elif 'Areal Capacity' in metric_name:
                    formatted_value = f"{value:.2f} {unit}"
                elif 'Efficiency' in metric_name:
                    formatted_value = f"{value:.3f} {unit}"
                else:
                    formatted_value = f"{value:.2f} {unit}" if isinstance(value, float) else f"{value} {unit}"
                
                st.metric(
                    label=metric_name,
                    value=formatted_value,
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
                # Check if this cell is an outlier for this specific field
                is_outlier_for_field = False
                if field in outlier_summary:
                    for outlier in outlier_summary[field]:
                        if outlier['cell_name'] == cell['cell_name']:
                            is_outlier_for_field = True
                            break
                
                # Only include this metric in the score if it's not an outlier
                if not is_outlier_for_field:
                    # Get all non-outlier values for this field to calculate min/max
                    all_values = []
                    for c in valid_cells:
                        if c[field] is not None:
                            is_c_outlier = False
                            if field in outlier_summary:
                                for outlier in outlier_summary[field]:
                                    if outlier['cell_name'] == c['cell_name']:
                                        is_c_outlier = True
                                        break
                            if not is_c_outlier:
                                all_values.append(c[field])
                    
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
        # Create DataFrame for analysis with numeric values for proper sorting
        # Map field names to column names
        field_to_column = {
            'reversible_capacity': 'Reversible Capacity (mAh/g)',
            'coulombic_efficiency': 'Coulombic Efficiency (%)',
            'first_discharge': '1st Cycle Discharge (mAh/g)',
            'first_efficiency': 'First Cycle Efficiency (%)',
            'areal_capacity': 'Areal Capacity (mAh/cm²)',
            'cycle_life_80': 'Cycle Life (80%)'
        }
        
        df_data = []
        for cell in valid_cells:
            row = {
                'Cell': cell['cell_name'],
                'Experiment': cell.get('experiment_name', 'Unknown'),
            }
            
            # Add each metric, but set to NaN if it's an outlier for this field
            for field, column in field_to_column.items():
                value = cell[field] if cell[field] is not None else np.nan
                
                # Check if this cell is an outlier for this specific field
                is_outlier_for_field = False
                if field in outlier_summary:
                    for outlier in outlier_summary[field]:
                        if outlier['cell_name'] == cell['cell_name']:
                            is_outlier_for_field = True
                            break
                
                # Set to NaN if it's an outlier
                row[column] = np.nan if is_outlier_for_field else value
            
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
                
                # Show top 5 with proper formatting
                top_5 = sorted_df.head(5)[['Cell', 'Experiment', metric]].copy()
                
                # Format the metric column for display
                if 'Reversible Capacity' in metric or '1st Cycle Discharge' in metric or 'Cycle Life' in metric:
                    top_5[metric] = top_5[metric].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
                elif 'Areal Capacity' in metric:
                    top_5[metric] = top_5[metric].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
                elif 'Efficiency' in metric:
                    top_5[metric] = top_5[metric].apply(lambda x: f"{x:.3f}%" if pd.notna(x) else "N/A")
                else:
                    top_5[metric] = top_5[metric].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
                
                st.dataframe(top_5, use_container_width=True)
                st.markdown("---")
