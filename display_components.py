import streamlit as st
import pandas as pd
import numpy as np
import json
import html

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


def render_master_table_filter_styles():
    st.markdown(
        """
        <style>
        .master-table-filter-hint {
            color: #6b7280;
            font-size: 0.83rem;
            margin-top: 0.15rem;
        }

        .master-table-active-filters {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.55rem 0 0.3rem 0;
        }

        .master-table-active-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.35rem 0.65rem;
            border-radius: 999px;
            background: #f8fafc;
            border: 1px solid #dbe4f0;
            color: #334155;
            font-size: 0.82rem;
            font-weight: 600;
        }

        .master-table-active-label {
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-size: 0.72rem;
            font-weight: 700;
        }

        .master-table-summary-line {
            color: #6b7280;
            font-size: 0.95rem;
            margin: 0.1rem 0 0.2rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def _filter_multiselect_options(options, search_query, selected_values=None):
    """Filter multiselect options while keeping current selections available."""
    selected_values = selected_values or []
    normalized_query = (search_query or "").strip().casefold()
    if not normalized_query:
        return options
    return [
        option for option in options
        if option in selected_values or normalized_query in option.casefold()
    ]


def _truncate_filter_value(value, max_length=28):
    value = str(value)
    return value if len(value) <= max_length else f"{value[:max_length - 3]}..."


def _summarize_filter_values(values, max_items=2):
    cleaned_values = [_truncate_filter_value(value) for value in values if value]
    if not cleaned_values:
        return ""
    if len(cleaned_values) <= max_items:
        return ", ".join(cleaned_values)
    return f"{len(cleaned_values)} selected"


def _render_master_table_active_filters(active_filters, empty_message):
    if not active_filters:
        st.caption(empty_message)
        return

    chips = "".join(
        (
            f'<span class="master-table-active-chip">'
            f'<span class="master-table-active-label">{html.escape(label)}</span>'
            f'{html.escape(value)}</span>'
        )
        for label, value in active_filters
        if value
    )
    st.markdown(
        f'<div class="master-table-active-filters">{chips}</div>',
        unsafe_allow_html=True
    )


def _set_column_filter_state(section_prefix, selected_columns, performance_options, processing_options, materials_options, component_options):
    """Keep master-table column state and widget state aligned."""
    st.session_state[f'{section_prefix}_selected_columns'] = selected_columns
    st.session_state[f'{section_prefix}_perf_multi'] = [
        column for column in selected_columns if column in performance_options
    ]
    st.session_state[f'{section_prefix}_proc_multi'] = [
        column for column in selected_columns if column in processing_options
    ]
    st.session_state[f'{section_prefix}_mat_multi'] = [
        column for column in selected_columns if column in materials_options
    ]
    st.session_state[f'{section_prefix}_comp_multi'] = [
        column for column in selected_columns if column in component_options
    ]


def _render_pill_filter_group(label, options, key, help_text, empty_message):
    """Render a clean pill-style multi-select group."""
    if not options:
        st.caption(empty_message)
        return []
    return st.pills(
        label,
        options=options,
        selection_mode='multi',
        key=key,
        help=help_text
    ) or []

def display_experiment_summaries_table(experiment_summaries, all_flags=None):
    """Display the experiment summaries table with column filtering and Active Material % column."""
    if not experiment_summaries:
        return
    
    # Extract formulation data and active material
    all_components, component_data, active_material_data = extract_formulation_data(experiment_summaries, [])
    
    # Define all possible columns
    all_columns = [
        'Experiment',
        'Flags',
        'Active Material (%)',
        'Loading (mg/cm²)',
        'Pressed Thickness (μm)',
        'Reversible Capacity (mAh/g)',
        'Coulombic Efficiency (%)',
        'Areal Capacity (mAh/cm²)',
        '1st Discharge (mAh/g)',
        'First Efficiency (%)',
        'Cycle Life (80%)',
        'Fade Rate (%/cyc)',
        'Fade Rate (%/100cyc)',
        'Porosity (%)',
        'Cutoff Voltages (V)',
        'Electrolyte',
        'Substrate',
        'Separator',
        'Date'
    ]
    
    # Add component columns
    for component in all_components:
        all_columns.append(f'{component} (%)')
    
    default_cols = [
        'Experiment', 'Flags', 'Reversible Capacity (mAh/g)',
        'Coulombic Efficiency (%)', 'Cycle Life (80%)',
        'Fade Rate (%/cyc)', 'Fade Rate (%/100cyc)',
        'Areal Capacity (mAh/cm²)', 'Porosity (%)',
        'Cutoff Voltages (V)', 'Electrolyte', 'Date'
    ]
    if 'section1_selected_columns' not in st.session_state:
        st.session_state.section1_selected_columns = [c for c in default_cols if c in all_columns]
    if 'section1_column_search' not in st.session_state:
        st.session_state.section1_column_search = ''

    basic_cols = ['Experiment', 'Flags', 'Date']
    processing_cols = ['Active Material (%)', 'Loading (mg/cm²)', 'Pressed Thickness (μm)', 'Porosity (%)']
    performance_cols = [
        'Reversible Capacity (mAh/g)', 'Coulombic Efficiency (%)',
        'Areal Capacity (mAh/cm²)', '1st Discharge (mAh/g)',
        'First Efficiency (%)', 'Cycle Life (80%)',
        'Fade Rate (%/cyc)', 'Fade Rate (%/100cyc)'
    ]
    materials_cols = ['Electrolyte', 'Substrate', 'Separator', 'Cutoff Voltages (V)']
    component_cols = [f'{comp} (%)' for comp in all_components]
    performance_filter_options = basic_cols + performance_cols

    render_master_table_filter_styles()
    with st.container(border=True):
        toolbar_cols = st.columns([0.82, 0.18])
        with toolbar_cols[0]:
            st.markdown("#### Find the experiment columns that matter")
            st.caption(
                "Start with a quick view, search by column name, then fine-tune the table with multi-select filters."
            )
        with toolbar_cols[1]:
            if st.button("Reset Filters", key="section1_reset_columns", use_container_width=True):
                reset_selection = [c for c in default_cols if c in all_columns]
                _set_column_filter_state(
                    'section1',
                    reset_selection,
                    performance_filter_options,
                    processing_cols,
                    materials_cols,
                    component_cols
                )
                st.session_state.section1_column_search = ''
                st.rerun()

        search_query = st.text_input(
            "Find columns",
            key="section1_column_search",
            placeholder="Try porosity, electrolyte, fade, separator, or graphite"
        ).strip()
        st.markdown(
            '<div class="master-table-filter-hint">Each pill group supports multi-select. Search narrows the options while keeping your current picks visible.</div>',
            unsafe_allow_html=True
        )

        preset_col1, preset_col2, preset_col3, preset_col4 = st.columns(4)
        with preset_col1:
            if st.button(
                "Essential",
                key="section1_preset_essential",
                use_container_width=True,
                help="Show only the most important columns"
            ):
                essential_selection = [
                    'Experiment', 'Reversible Capacity (mAh/g)', 'Coulombic Efficiency (%)',
                    'Cycle Life (80%)', 'Electrolyte'
                ]
                _set_column_filter_state(
                    'section1',
                    essential_selection,
                    performance_filter_options,
                    processing_cols,
                    materials_cols,
                    component_cols
                )
                st.rerun()
        with preset_col2:
            if st.button(
                "Performance",
                key="section1_preset_performance",
                use_container_width=True,
                help="Focus on cell performance metrics"
            ):
                perf_cols = [
                    'Experiment', 'Flags', 'Reversible Capacity (mAh/g)',
                    'Coulombic Efficiency (%)', '1st Discharge (mAh/g)',
                    'First Efficiency (%)', 'Cycle Life (80%)',
                    'Fade Rate (%/cyc)', 'Fade Rate (%/100cyc)', 'Areal Capacity (mAh/cm²)'
                ]
                performance_selection = [c for c in perf_cols if c in all_columns]
                _set_column_filter_state(
                    'section1',
                    performance_selection,
                    performance_filter_options,
                    processing_cols,
                    materials_cols,
                    component_cols
                )
                st.rerun()
        with preset_col3:
            if st.button(
                "Processing",
                key="section1_preset_processing",
                use_container_width=True,
                help="Focus on cell preparation data"
            ):
                proc_cols = [
                    'Experiment', 'Active Material (%)', 'Loading (mg/cm²)',
                    'Pressed Thickness (μm)', 'Porosity (%)', 'Substrate',
                    'Separator', 'Cutoff Voltages (V)', 'Date'
                ]
                processing_selection = [c for c in proc_cols if c in all_columns]
                _set_column_filter_state(
                    'section1',
                    processing_selection,
                    performance_filter_options,
                    processing_cols,
                    materials_cols,
                    component_cols
                )
                st.rerun()
        with preset_col4:
            if st.button(
                "All Data",
                key="section1_preset_all",
                use_container_width=True,
                help="Show all available columns"
            ):
                _set_column_filter_state(
                    'section1',
                    all_columns.copy(),
                    performance_filter_options,
                    processing_cols,
                    materials_cols,
                    component_cols
                )
                st.rerun()

        current_perf = [
            c for c in st.session_state.section1_selected_columns
            if c in (basic_cols + performance_cols)
        ]
        current_proc = [c for c in st.session_state.section1_selected_columns if c in processing_cols]
        current_mat = [c for c in st.session_state.section1_selected_columns if c in materials_cols]
        current_comp = [c for c in st.session_state.section1_selected_columns if c in component_cols]

        selected_performance = _render_pill_filter_group(
            "Performance",
            _filter_multiselect_options(performance_filter_options, search_query, current_perf),
            "section1_perf_multi",
            "Choose the primary experiment metrics to display",
            "No performance columns match the current search."
        )
        selected_processing = _render_pill_filter_group(
            "Processing",
            _filter_multiselect_options(processing_cols, search_query, current_proc),
            "section1_proc_multi",
            "Choose preparation and porosity columns",
            "No processing columns match the current search."
        )
        selected_materials = _render_pill_filter_group(
            "Materials",
            _filter_multiselect_options(materials_cols, search_query, current_mat),
            "section1_mat_multi",
            "Choose electrolyte and hardware columns",
            "No material columns match the current search."
        )

        if component_cols:
            with st.expander("Formulation Components", expanded=bool(search_query or current_comp)):
                st.markdown(
                    '<div class="master-table-filter-hint">Use component filters when you want a deeper formulation view without crowding the main controls.</div>',
                    unsafe_allow_html=True
                )
                selected_components = _render_pill_filter_group(
                    "Components",
                    _filter_multiselect_options(component_cols, search_query, current_comp),
                    "section1_comp_multi",
                    "Choose formulation component columns",
                    "No formulation components match the current search."
                )
                comp_action_col1, comp_action_col2 = st.columns(2)
                with comp_action_col1:
                    if st.button("Select All Components", key="section1_select_all_comp", use_container_width=True):
                        new_selection = list(dict.fromkeys(
                            selected_performance + selected_processing + selected_materials + component_cols
                        ))
                        _set_column_filter_state(
                            'section1',
                            new_selection,
                            performance_filter_options,
                            processing_cols,
                            materials_cols,
                            component_cols
                        )
                        st.rerun()
                with comp_action_col2:
                    if st.button("Clear All Components", key="section1_clear_all_comp", use_container_width=True):
                        new_selection = list(dict.fromkeys(
                            selected_performance + selected_processing + selected_materials
                        ))
                        _set_column_filter_state(
                            'section1',
                            new_selection,
                            performance_filter_options,
                            processing_cols,
                            materials_cols,
                            component_cols
                        )
                        st.rerun()
        else:
            st.markdown(
                '<div class="master-table-filter-hint">No formulation components were found for this project yet.</div>',
                unsafe_allow_html=True
            )
            selected_components = []

        combined_selection = list(dict.fromkeys(
            selected_performance + selected_processing + selected_materials + selected_components
        ))
        if combined_selection and 'Experiment' in all_columns and 'Experiment' not in combined_selection:
            combined_selection.insert(0, 'Experiment')
        if set(combined_selection) != set(st.session_state.section1_selected_columns):
            st.session_state.section1_selected_columns = combined_selection

        if st.session_state.section1_selected_columns:
            active_filters = []
            if search_query:
                active_filters.append(("Search", _truncate_filter_value(search_query)))
            if selected_performance:
                active_filters.append(("Performance", _summarize_filter_values(selected_performance)))
            if selected_processing:
                active_filters.append(("Processing", _summarize_filter_values(selected_processing)))
            if selected_materials:
                active_filters.append(("Materials", _summarize_filter_values(selected_materials)))
            if selected_components:
                active_filters.append(("Components", _summarize_filter_values(selected_components)))
            _render_master_table_active_filters(
                active_filters,
                "Use a preset or pick columns from the groups below."
            )
            st.markdown(
                (
                    f'<div class="master-table-summary-line"><strong>{len(st.session_state.section1_selected_columns)}</strong> '
                    f'of {len(all_columns)} columns selected</div>'
                ),
                unsafe_allow_html=True
            )
            with st.expander("View Selected Columns", expanded=False):
                st.markdown("**Selected:** " + ", ".join(st.session_state.section1_selected_columns))

    if not st.session_state.section1_selected_columns:
        st.error("No columns selected. Choose a preset or add at least one column group to show the table.")
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
        
        # Get flags for cells in this experiment
        from cell_flags import format_flags_for_display
        exp_flags_display = ""
        if all_flags:
            exp_name = exp['experiment_name']
            # Aggregate flags from all cells in this experiment
            exp_flags_list = []
            for cell_name, flags in all_flags.items():
                # Match cells that belong to this experiment
                if exp_name in cell_name or (exp.get('cell_name') and cell_name == exp.get('cell_name')):
                    exp_flags_list.extend(flags)
            if exp_flags_list:
                exp_flags_display = format_flags_for_display(exp_flags_list)
        
        row = {
            'Experiment': exp['experiment_name'],
            'Flags': exp_flags_display,
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
            'Fade Rate (%/cyc)': exp.get('fade_rate_per_cycle') if exp.get('fade_rate_per_cycle') is not None else np.nan,
            'Fade Rate (%/100cyc)': exp.get('fade_rate_per_100') if exp.get('fade_rate_per_100') is not None else np.nan,
            'Porosity (%)': f"{exp['porosity']*100:.1f}%" if exp['porosity'] is not None and exp['porosity'] > 0 else "N/A",
            'Cutoff Voltages (V)': f"{exp.get('cutoff_voltage_lower', 'N/A')}-{exp.get('cutoff_voltage_upper', 'N/A')}" if exp.get('cutoff_voltage_lower') is not None and exp.get('cutoff_voltage_upper') is not None else "N/A",
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
    
    # Filter to selected columns and ensure 'Experiment' is first
    available_columns = [col for col in st.session_state.section1_selected_columns if col in df.columns]
    
    # Ensure 'Experiment' column is always first (pinned left)
    if 'Experiment' in available_columns:
        available_columns.remove('Experiment')
        available_columns.insert(0, 'Experiment')
    
    df = df[available_columns]
    
    # Display the dataframe with styling and column configuration
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
    if 'Fade Rate (%/cyc)' in df.columns:
        format_dict['Fade Rate (%/cyc)'] = '{:.4f}'
    if 'Fade Rate (%/100cyc)' in df.columns:
        format_dict['Fade Rate (%/100cyc)'] = '{:.2f}'
    
    # Add formatters for component columns
    for component in all_components:
        component_col = f'{component} (%)'
        if component_col in df.columns:
            format_dict[component_col] = lambda x: 'N/A' if pd.isna(x) else f"{x:.1f}"
    
    if format_dict:
        styled_df = styled_df.format(format_dict, na_rep='N/A')
    
    # Configure column settings with pinned 'Experiment' column
    column_config = {}
    if 'Experiment' in df.columns:
        column_config['Experiment'] = st.column_config.TextColumn(
            "Experiment",
            help="Experiment name (pinned to left)",
            width="medium",
        )
    
    st.dataframe(
        styled_df, 
        use_container_width=True,
        column_config=column_config,
        hide_index=True
    )

def display_individual_cells_table(individual_cells, all_flags=None):
    """Display the individual cells table with column filtering and component columns."""
    if not individual_cells:
        return
    
    # Extract formulation data and active material
    all_components, component_data, active_material_data = extract_formulation_data([], individual_cells)
    
    # Define all possible columns
    all_columns = [
        'Cell Name',
        'Flags',
        'Active Material (%)',
        'Loading (mg/cm²)',
        'Pressed Thickness (μm)',
        'Reversible Capacity (mAh/g)',
        'Coulombic Efficiency (%)',
        'Areal Capacity (mAh/cm²)',
        '1st Discharge (mAh/g)',
        'First Efficiency (%)',
        'Cycle Life (80%)',
        'Fade Rate (%/cyc)',
        'Fade Rate (%/100cyc)',
        'Porosity (%)',
        'Cutoff Voltages (V)',
        'Electrolyte',
        'Substrate',
        'Separator',
        'Date',
        'Experiment'
    ]
    
    # Add component columns
    for component in all_components:
        all_columns.append(f'{component} (%)')
    
    default_cols = [
        'Cell Name', 'Experiment', 'Flags', 'Reversible Capacity (mAh/g)',
        'Coulombic Efficiency (%)', 'Cycle Life (80%)',
        'Fade Rate (%/cyc)', 'Fade Rate (%/100cyc)',
        'Areal Capacity (mAh/cm²)', 'Porosity (%)',
        'Cutoff Voltages (V)', 'Electrolyte'
    ]
    if 'section2_selected_columns' not in st.session_state:
        st.session_state.section2_selected_columns = [c for c in default_cols if c in all_columns]
    if 'section2_column_search' not in st.session_state:
        st.session_state.section2_column_search = ''

    basic_cols = ['Cell Name', 'Experiment', 'Flags', 'Date']
    processing_cols = ['Active Material (%)', 'Loading (mg/cm²)', 'Pressed Thickness (μm)', 'Porosity (%)']
    performance_cols = [
        'Reversible Capacity (mAh/g)', 'Coulombic Efficiency (%)',
        'Areal Capacity (mAh/cm²)', '1st Discharge (mAh/g)',
        'First Efficiency (%)', 'Cycle Life (80%)',
        'Fade Rate (%/cyc)', 'Fade Rate (%/100cyc)'
    ]
    materials_cols = ['Electrolyte', 'Substrate', 'Separator', 'Cutoff Voltages (V)']
    component_cols = [f'{comp} (%)' for comp in all_components]
    performance_filter_options = basic_cols + performance_cols

    render_master_table_filter_styles()
    with st.container(border=True):
        toolbar_cols = st.columns([0.82, 0.18])
        with toolbar_cols[0]:
            st.markdown("#### Find the cell columns that matter")
            st.caption(
                "Start with a quick view, search by column name, then fine-tune the cell table with multi-select filters."
            )
        with toolbar_cols[1]:
            if st.button("Reset Filters", key="section2_reset_columns", use_container_width=True):
                reset_selection = [c for c in default_cols if c in all_columns]
                _set_column_filter_state(
                    'section2',
                    reset_selection,
                    performance_filter_options,
                    processing_cols,
                    materials_cols,
                    component_cols
                )
                st.session_state.section2_column_search = ''
                st.rerun()

        search_query = st.text_input(
            "Find columns",
            key="section2_column_search",
            placeholder="Try cell name, porosity, fade, separator, or graphite"
        ).strip()
        st.markdown(
            '<div class="master-table-filter-hint">Each pill group supports multi-select. Search narrows the options while keeping your current picks visible.</div>',
            unsafe_allow_html=True
        )

        preset_col1, preset_col2, preset_col3, preset_col4 = st.columns(4)
        with preset_col1:
            if st.button(
                "Essential",
                key="section2_preset_essential",
                use_container_width=True,
                help="Show only the most important cell data"
            ):
                essential_selection = [
                    'Cell Name', 'Experiment', 'Reversible Capacity (mAh/g)',
                    'Coulombic Efficiency (%)', 'Cycle Life (80%)'
                ]
                _set_column_filter_state(
                    'section2',
                    essential_selection,
                    performance_filter_options,
                    processing_cols,
                    materials_cols,
                    component_cols
                )
                st.rerun()
        with preset_col2:
            if st.button(
                "Performance",
                key="section2_preset_performance",
                use_container_width=True,
                help="Focus on individual cell performance"
            ):
                perf_cols = [
                    'Cell Name', 'Experiment', 'Flags', 'Reversible Capacity (mAh/g)',
                    'Coulombic Efficiency (%)', '1st Discharge (mAh/g)',
                    'First Efficiency (%)', 'Cycle Life (80%)',
                    'Fade Rate (%/cyc)', 'Fade Rate (%/100cyc)', 'Areal Capacity (mAh/cm²)'
                ]
                performance_selection = [c for c in perf_cols if c in all_columns]
                _set_column_filter_state(
                    'section2',
                    performance_selection,
                    performance_filter_options,
                    processing_cols,
                    materials_cols,
                    component_cols
                )
                st.rerun()
        with preset_col3:
            if st.button(
                "Processing",
                key="section2_preset_processing",
                use_container_width=True,
                help="Focus on cell preparation details"
            ):
                proc_cols = [
                    'Cell Name', 'Experiment', 'Active Material (%)', 'Loading (mg/cm²)',
                    'Pressed Thickness (μm)', 'Porosity (%)', 'Substrate',
                    'Separator', 'Cutoff Voltages (V)', 'Date'
                ]
                processing_selection = [c for c in proc_cols if c in all_columns]
                _set_column_filter_state(
                    'section2',
                    processing_selection,
                    performance_filter_options,
                    processing_cols,
                    materials_cols,
                    component_cols
                )
                st.rerun()
        with preset_col4:
            if st.button(
                "All Data",
                key="section2_preset_all",
                use_container_width=True,
                help="Show all available columns"
            ):
                _set_column_filter_state(
                    'section2',
                    all_columns.copy(),
                    performance_filter_options,
                    processing_cols,
                    materials_cols,
                    component_cols
                )
                st.rerun()

        current_perf = [
            c for c in st.session_state.section2_selected_columns
            if c in (basic_cols + performance_cols)
        ]
        current_proc = [c for c in st.session_state.section2_selected_columns if c in processing_cols]
        current_mat = [c for c in st.session_state.section2_selected_columns if c in materials_cols]
        current_comp = [c for c in st.session_state.section2_selected_columns if c in component_cols]

        selected_performance = _render_pill_filter_group(
            "Performance",
            _filter_multiselect_options(performance_filter_options, search_query, current_perf),
            "section2_perf_multi",
            "Choose the primary cell metrics to display",
            "No performance columns match the current search."
        )
        selected_processing = _render_pill_filter_group(
            "Processing",
            _filter_multiselect_options(processing_cols, search_query, current_proc),
            "section2_proc_multi",
            "Choose preparation and porosity columns",
            "No processing columns match the current search."
        )
        selected_materials = _render_pill_filter_group(
            "Materials",
            _filter_multiselect_options(materials_cols, search_query, current_mat),
            "section2_mat_multi",
            "Choose electrolyte and hardware columns",
            "No material columns match the current search."
        )

        if component_cols:
            with st.expander("Formulation Components", expanded=bool(search_query or current_comp)):
                st.markdown(
                    '<div class="master-table-filter-hint">Use component filters when you want a deeper formulation view without crowding the main controls.</div>',
                    unsafe_allow_html=True
                )
                selected_components = _render_pill_filter_group(
                    "Components",
                    _filter_multiselect_options(component_cols, search_query, current_comp),
                    "section2_comp_multi",
                    "Choose formulation component columns",
                    "No formulation components match the current search."
                )
                comp_action_col1, comp_action_col2 = st.columns(2)
                with comp_action_col1:
                    if st.button("Select All Components", key="section2_select_all_comp", use_container_width=True):
                        new_selection = list(dict.fromkeys(
                            selected_performance + selected_processing + selected_materials + component_cols
                        ))
                        _set_column_filter_state(
                            'section2',
                            new_selection,
                            performance_filter_options,
                            processing_cols,
                            materials_cols,
                            component_cols
                        )
                        st.rerun()
                with comp_action_col2:
                    if st.button("Clear All Components", key="section2_clear_all_comp", use_container_width=True):
                        new_selection = list(dict.fromkeys(
                            selected_performance + selected_processing + selected_materials
                        ))
                        _set_column_filter_state(
                            'section2',
                            new_selection,
                            performance_filter_options,
                            processing_cols,
                            materials_cols,
                            component_cols
                        )
                        st.rerun()
        else:
            st.markdown(
                '<div class="master-table-filter-hint">No formulation components were found for this project yet.</div>',
                unsafe_allow_html=True
            )
            selected_components = []

        combined_selection = list(dict.fromkeys(
            selected_performance + selected_processing + selected_materials + selected_components
        ))
        if combined_selection and 'Cell Name' in all_columns and 'Cell Name' not in combined_selection:
            combined_selection.insert(0, 'Cell Name')
        if set(combined_selection) != set(st.session_state.section2_selected_columns):
            st.session_state.section2_selected_columns = combined_selection

        if st.session_state.section2_selected_columns:
            active_filters = []
            if search_query:
                active_filters.append(("Search", _truncate_filter_value(search_query)))
            if selected_performance:
                active_filters.append(("Performance", _summarize_filter_values(selected_performance)))
            if selected_processing:
                active_filters.append(("Processing", _summarize_filter_values(selected_processing)))
            if selected_materials:
                active_filters.append(("Materials", _summarize_filter_values(selected_materials)))
            if selected_components:
                active_filters.append(("Components", _summarize_filter_values(selected_components)))
            _render_master_table_active_filters(
                active_filters,
                "Use a preset or pick columns from the groups below."
            )
            st.markdown(
                (
                    f'<div class="master-table-summary-line"><strong>{len(st.session_state.section2_selected_columns)}</strong> '
                    f'of {len(all_columns)} columns selected</div>'
                ),
                unsafe_allow_html=True
            )
            with st.expander("View Selected Columns", expanded=False):
                st.markdown("**Selected:** " + ", ".join(st.session_state.section2_selected_columns))

    if not st.session_state.section2_selected_columns:
        st.error("No columns selected. Choose a preset or add at least one column group to show the table.")
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
        
        # Get flags for this cell
        from cell_flags import format_flags_for_display
        cell_flags_display = ""
        if all_flags and cell['cell_name'] in all_flags:
            cell_flags_display = format_flags_for_display(all_flags[cell['cell_name']])
        
        row = {
            'Experiment': cell.get('experiment_name', np.nan),
            'Cell Name': cell['cell_name'],
            'Flags': cell_flags_display,
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
            'Fade Rate (%/cyc)': cell.get('fade_rate_per_cycle') if cell.get('fade_rate_per_cycle') is not None else np.nan,
            'Fade Rate (%/100cyc)': cell.get('fade_rate_per_100') if cell.get('fade_rate_per_100') is not None else np.nan,
            'Porosity (%)': f"{cell['porosity']*100:.1f}%" if cell['porosity'] is not None and cell['porosity'] > 0 else "N/A",
            'Cutoff Voltages (V)': f"{cell.get('cutoff_voltage_lower', 'N/A')}-{cell.get('cutoff_voltage_upper', 'N/A')}" if cell.get('cutoff_voltage_lower') is not None and cell.get('cutoff_voltage_upper') is not None else "N/A",
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
    
    # Filter to selected columns and ensure 'Cell Name' is first
    available_columns = [col for col in st.session_state.section2_selected_columns if col in df.columns]
    
    # Ensure 'Cell Name' column is always first (pinned left)
    if 'Cell Name' in available_columns:
        available_columns.remove('Cell Name')
        available_columns.insert(0, 'Cell Name')
    
    df = df[available_columns]
    
    # Display the dataframe with styling and column configuration
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
    if 'Fade Rate (%/cyc)' in df.columns:
        format_dict['Fade Rate (%/cyc)'] = '{:.4f}'
    if 'Fade Rate (%/100cyc)' in df.columns:
        format_dict['Fade Rate (%/100cyc)'] = '{:.2f}'
    
    # Add formatters for component columns
    for component in all_components:
        component_col = f'{component} (%)'
        if component_col in df.columns:
            format_dict[component_col] = lambda x: 'N/A' if pd.isna(x) else f"{x:.1f}"
    
    if format_dict:
        styled_df = styled_df.format(format_dict, na_rep='N/A')
    
    # Configure column settings with pinned 'Cell Name' column
    column_config = {}
    if 'Cell Name' in df.columns:
        column_config['Cell Name'] = st.column_config.TextColumn(
            "Cell Name",
            help="Cell identifier (pinned to left)",
            width="medium",
        )
    
    st.dataframe(
        styled_df, 
        use_container_width=True,
        column_config=column_config,
        hide_index=True
    )

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


def display_cell_flags_summary(all_flags):
    """Display a summary banner of all detected flags across all cells."""
    from cell_flags import get_flag_summary_stats
    
    if not any(all_flags.values()):
        st.success("✅ No anomalies or issues detected across all cells")
        return
    
    stats = get_flag_summary_stats(all_flags)
    
    # Summary banner with metrics
    st.markdown("### 🚩 Automated Anomaly Detection Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Flags", stats['total_flags'])
    
    with col2:
        delta_text = "Needs attention" if stats['critical_count'] > 0 else None
        st.metric("🚨 Critical Issues", stats['critical_count'], delta=delta_text, delta_color="inverse")
    
    with col3:
        st.metric("⚠️ Warnings", stats['warning_count'])
    
    with col4:
        st.metric("Cells Flagged", f"{stats['cells_with_flags']}/{len(all_flags)}")
    
    # Quick breakdown by category
    if stats['category_counts']:
        st.markdown("**Issues by Category:**")
        cols = st.columns(len(stats['category_counts']))
        for idx, (category, count) in enumerate(stats['category_counts'].items()):
            with cols[idx]:
                st.caption(f"{category}: {count}")


def display_detailed_flags_section(all_flags):
    """Display detailed flag information in an expandable section."""
    from cell_flags import FlagSeverity
    
    if not any(all_flags.values()):
        return
    
    with st.expander("🔍 Detailed Flag Information & Recommendations", expanded=False):
        st.info("💡 **Tip**: Cell names below correspond to cells in **Section 2: All Individual Cells Data**. "
                "Use the 'Flags' column in Section 2 to quickly identify which cells have issues, then expand details here.")
        
        # Quick reference list of flagged cells
        flagged_cells = [cell_name for cell_name, flags in all_flags.items() if flags]
        if flagged_cells:
            st.markdown(f"**📋 Cells with Flags ({len(flagged_cells)}):** {', '.join(sorted(flagged_cells)[:10])}" + 
                       (f" and {len(flagged_cells)-10} more..." if len(flagged_cells) > 10 else ""))
        
        st.markdown("---")
        
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            show_severity = st.multiselect(
                "Filter by Severity",
                ["Critical", "Warning", "Info"],
                default=["Critical", "Warning", "Info"],
                key="flag_severity_filter"
            )
        
        with col2:
            show_categories = st.multiselect(
                "Filter by Category",
                ["Performance", "Quality Assurance", "Data Integrity", "Electrochemistry"],
                default=["Performance", "Quality Assurance", "Data Integrity", "Electrochemistry"],
                key="flag_category_filter"
            )
        
        st.markdown("---")
        
        # Sort cells by severity (most critical first)
        def get_cell_max_severity(flags):
            if not flags:
                return 3
            severity_order = {FlagSeverity.CRITICAL: 0, FlagSeverity.WARNING: 1, FlagSeverity.INFO: 2}
            return min(severity_order.get(f.severity, 3) for f in flags)
        
        sorted_cells = sorted(all_flags.items(), key=lambda x: get_cell_max_severity(x[1]))
        
        # Display flags by cell
        for cell_name, flags in sorted_cells:
            if not flags:
                continue
            
            # Filter flags based on user selection
            severity_map = {"Critical": FlagSeverity.CRITICAL, "Warning": FlagSeverity.WARNING, "Info": FlagSeverity.INFO}
            filtered_flags = [
                f for f in flags
                if f.severity.name.title() in show_severity and f.category.value in show_categories
            ]
            
            if not filtered_flags:
                continue
            
            # Determine icon based on most severe flag
            severity_order = {FlagSeverity.CRITICAL: 0, FlagSeverity.WARNING: 1, FlagSeverity.INFO: 2}
            max_severity = min(filtered_flags, key=lambda f: severity_order[f.severity]).severity
            icon = max_severity.value
            
            with st.expander(f"{icon} **{cell_name}** — {len(filtered_flags)} issue{'s' if len(filtered_flags) != 1 else ''}", expanded=False):
                for flag in filtered_flags:
                    # Flag header
                    st.markdown(f"#### {flag.severity.value} {flag.flag_type}")
                    
                    # Description
                    st.markdown(f"**Description:** {flag.description}")
                    
                    # Details in columns
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.caption(f"**Category:** {flag.category.value}")
                    with col2:
                        st.caption(f"**Confidence:** {flag.confidence:.0%}")
                    with col3:
                        if flag.cycle:
                            st.caption(f"**Cycle:** {flag.cycle}")
                    
                    # Recommendation
                    if flag.recommendation:
                        st.info(f"💡 **Recommendation:** {flag.recommendation}")
                    
                    st.markdown("---")


def add_flags_to_individual_cells_table(df_data, all_flags):
    """Add flags column to individual cells table data."""
    from cell_flags import format_flags_for_display
    
    for row in df_data:
        cell_name = row.get('Cell Name', '')
        flags = all_flags.get(cell_name, [])
        row['Flags'] = format_flags_for_display(flags)
    
    return df_data


def add_flags_to_experiment_summaries_table(df_data, all_flags):
    """Add flags summary to experiment summaries (aggregate from cells in experiment)."""
    from cell_flags import format_flags_for_display
    
    for row in df_data:
        exp_name = row.get('Experiment', '')
        
        # Find all flags for cells in this experiment
        exp_flags = []
        for cell_name, flags in all_flags.items():
            # Check if cell belongs to this experiment
            # (We'll match on experiment name prefix or exact match)
            if exp_name in cell_name or cell_name.startswith(exp_name):
                exp_flags.extend(flags)
        
        row['Flags'] = format_flags_for_display(exp_flags) if exp_flags else ""
    
    return df_data
