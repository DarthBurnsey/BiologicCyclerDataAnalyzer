import streamlit as st
import pandas as pd
import io
from openpyxl import load_workbook
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, date
import re
import sqlite3
import json
import os
from pathlib import Path
from io import StringIO

# Import our modular components
from database import (
    get_db_connection, init_database, migrate_database, get_project_components,
    get_user_projects, create_project, save_cell_experiment, update_cell_experiment,
    get_experiment_by_name_and_file, get_project_experiments, check_experiment_exists,
    get_experiment_data, delete_cell_experiment, delete_project, rename_project,
    rename_experiment, save_experiment, update_experiment, check_experiment_name_exists,
    get_experiment_by_name, get_all_project_experiments_data, TEST_USER_ID,
    update_project_type, get_project_by_id, duplicate_experiment,
    get_experiments_by_formulation_component, get_formulation_summary,
    get_experiments_grouped_by_formulation
)
from data_analysis import (
    calculate_cell_summary, calculate_experiment_average,
    calculate_cycle_life_80, get_qdis_series
)
from display_components import (
    display_experiment_summaries_table, display_individual_cells_table,
    display_best_performers_analysis
)
from file_processing import extract_date_from_filename
from data_processing import load_and_preprocess_data, calculate_efficiency_based_on_project_type
from dialogs import confirm_delete_project, confirm_delete_experiment, show_delete_dialogs

# Initialize database
init_database()
migrate_database()
from ui_components import render_toggle_section, display_summary_stats, display_averages, render_cell_inputs, get_initial_areal_capacity, render_formulation_table, get_substrate_options, render_hybrid_electrolyte_input, render_hybrid_separator_input, render_comparison_plot_options, render_experiment_color_customization, render_comparison_color_customization
from plotting import plot_capacity_graph, plot_capacity_retention_graph, plot_comparison_capacity_graph, plot_combined_capacity_retention_graph
from llm_summary import generate_experiment_summary
from preference_components import render_preferences_sidebar, render_formulation_editor_modal, get_default_values_for_experiment, render_default_indicator
from formulation_analysis import (
    extract_formulation_component, extract_all_formulation_components,
    compare_formulations, create_formulation_comparison_dataframe,
    group_experiments_by_formulation_range, extract_formulation_component_from_experiment
)

# =============================
# Battery Data Gravimetric Capacity Calculator App
# =============================

# --- Top Bar ---
with st.container():
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.title("🔋 CellScope")
    
    with col2:
        # Show current experiment status
        loaded_experiment = st.session_state.get('loaded_experiment')
        if loaded_experiment:
            st.info(f"📊 {loaded_experiment['experiment_name']}")
    
    with col3:
        # Save button for loaded experiments
        if loaded_experiment:
            if st.button("💾 Save", key="save_changes_btn"):
                # Get current experiment data
                experiment_data = loaded_experiment['experiment_data']
                experiment_id = loaded_experiment['experiment_id']
                project_id = loaded_experiment['project_id']
                
                # Get current values from session state or use loaded values
                current_experiment_date = st.session_state.get('current_experiment_date', experiment_data.get('experiment_date'))
                current_disc_diameter = st.session_state.get('current_disc_diameter_mm', experiment_data.get('disc_diameter_mm'))
                current_group_assignments = st.session_state.get('current_group_assignments', experiment_data.get('group_assignments'))
                current_group_names = st.session_state.get('current_group_names', experiment_data.get('group_names'))
                
                # Convert date string to date object if needed
                if isinstance(current_experiment_date, str):
                    try:
                        current_experiment_date = datetime.fromisoformat(current_experiment_date).date()
                    except:
                        current_experiment_date = date.today()
                
                # Get updated cells data from session state (includes exclude changes)
                current_datasets = st.session_state.get('datasets', [])
                updated_cells_data = []
                recalculated_cells = []
                
                for i, dataset in enumerate(current_datasets):
                    # Get original cell data
                    original_cell = experiment_data['cells'][i] if i < len(experiment_data['cells']) else {}
                    
                    # Read current input values from session state widgets
                    # These might be more recent than the dataset values
                    widget_loading = st.session_state.get(f'edit_loading_{i}')
                    widget_active = st.session_state.get(f'edit_active_{i}')
                    widget_formation = st.session_state.get(f'edit_formation_{i}')
                    widget_testnum = st.session_state.get(f'edit_testnum_{i}')
                    
                    # Use widget values if available, otherwise use dataset values
                    new_loading = widget_loading if widget_loading is not None else dataset.get('loading', 0)
                    new_active = widget_active if widget_active is not None else dataset.get('active', 0)
                    new_formation = widget_formation if widget_formation is not None else dataset.get('formation_cycles', 4)
                    new_testnum = widget_testnum if widget_testnum is not None else dataset.get('testnum', f'Cell {i+1}')
                    
                    # Check if loading or active material has changed
                    original_loading = original_cell.get('loading', 0)
                    original_active = original_cell.get('active_material', 0)
                    
                    # Recalculate gravimetric capacities if loading or active material changed
                    updated_data_json = original_cell.get('data_json', '{}')
                    if (new_loading != original_loading or new_active != original_active) and updated_data_json:
                        try:
                            # Parse the original DataFrame
                            original_df = pd.read_json(StringIO(updated_data_json))
                            
                            # Recalculate gravimetric capacities
                            updated_df = recalculate_gravimetric_capacities(original_df, new_loading, new_active)
                            
                            # Update the data JSON with recalculated values
                            updated_data_json = updated_df.to_json()
                            recalculated_cells.append(new_testnum)
                        except Exception as e:
                            # If recalculation fails, keep original data
                            pass
                    
                    # Recalculate porosity if loading changed and we have the required data
                    porosity = original_cell.get('porosity')
                    if (new_loading != original_loading and 
                        pressed_thickness and pressed_thickness > 0 and 
                        dataset.get('formulation') and 
                        current_disc_diameter):
                        try:
                            from porosity_calculations import calculate_porosity_from_experiment_data
                            porosity_data = calculate_porosity_from_experiment_data(
                                disc_mass_mg=new_loading,
                                disc_diameter_mm=current_disc_diameter,
                                pressed_thickness_um=pressed_thickness,
                                formulation=dataset['formulation']
                            )
                            porosity = porosity_data['porosity']
                        except Exception:
                            pass
                    
                    # Read other widget values too
                    widget_electrolyte = st.session_state.get(f'edit_electrolyte_{i}') or st.session_state.get(f'edit_single_electrolyte_{i}')
                    widget_substrate = st.session_state.get(f'edit_substrate_{i}') or st.session_state.get(f'edit_single_substrate_{i}')
                    widget_separator = st.session_state.get(f'edit_separator_{i}') or st.session_state.get(f'edit_single_separator_{i}')
                    
                    # Convert session state dataset back to cells data format
                    updated_cell = {
                        'loading': new_loading,
                        'active_material': new_active,
                        'formation_cycles': new_formation,
                        'test_number': new_testnum,
                        'cell_name': new_testnum,
                        'electrolyte': widget_electrolyte if widget_electrolyte is not None else dataset.get('electrolyte', '1M LiPF6 1:1:1'),
                        'substrate': widget_substrate if widget_substrate is not None else dataset.get('substrate', 'Copper'),
                        'separator': widget_separator if widget_separator is not None else dataset.get('separator', '25um PP'),
                        'formulation': dataset.get('formulation', []),
                        'excluded': dataset.get('excluded', False),
                        'data_json': updated_data_json,
                        'porosity': porosity
                    }
                    updated_cells_data.append(updated_cell)

                # Get additional experiment data
                solids_content = st.session_state.get('solids_content', experiment_data.get('solids_content'))
                pressed_thickness = st.session_state.get('pressed_thickness', experiment_data.get('pressed_thickness'))
                experiment_notes = st.session_state.get('experiment_notes', experiment_data.get('experiment_notes'))
                
                # Prepare cell format data if it's a Full Cell project
                project_type = "Full Cell"  # Default
                if project_id:
                    project_info = get_project_by_id(project_id)
                    if project_info:
                        project_type = project_info[3]
                
                cell_format_data = {}
                if project_type == "Full Cell":
                    cell_format = st.session_state.get('current_cell_format', experiment_data.get('cell_format', 'Coin'))
                    cell_format_data['cell_format'] = cell_format
                    if cell_format == "Pouch":
                        cell_format_data['cathode_length'] = st.session_state.get('current_cathode_length', experiment_data.get('cathode_length', 50.0))
                        cell_format_data['cathode_width'] = st.session_state.get('current_cathode_width', experiment_data.get('cathode_width', 50.0))
                        cell_format_data['num_stacked_cells'] = st.session_state.get('current_num_stacked_cells', experiment_data.get('num_stacked_cells', 1))

                # Update the experiment with current data including exclude changes
                update_experiment(
                    experiment_id=experiment_id,
                    project_id=project_id,
                    experiment_name=loaded_experiment['experiment_name'],
                    experiment_date=current_experiment_date,
                    disc_diameter_mm=current_disc_diameter,
                    group_assignments=current_group_assignments,
                    group_names=current_group_names,
                    cells_data=updated_cells_data,  # Use updated data with exclude changes
                    solids_content=solids_content,
                    pressed_thickness=pressed_thickness,
                    experiment_notes=experiment_notes,
                    cell_format_data=cell_format_data
                )
                
                # Update the loaded experiment in session state with all current changes
                st.session_state['loaded_experiment']['experiment_data'].update({
                    'experiment_date': current_experiment_date.isoformat(),
                    'disc_diameter_mm': current_disc_diameter,
                    'group_assignments': current_group_assignments,
                    'group_names': current_group_names,
                    'cells': updated_cells_data,
                    'solids_content': solids_content,
                    'pressed_thickness': pressed_thickness,
                    'experiment_notes': experiment_notes
                })
                
                # Add cell format data if applicable
                if cell_format_data:
                    st.session_state['loaded_experiment']['experiment_data'].update(cell_format_data)
                
                # Clear any cached processed data to force recalculation
                if 'processed_data_cache' in st.session_state:
                    del st.session_state['processed_data_cache']
                if 'cache_key' in st.session_state:
                    del st.session_state['cache_key']
                
                # Set flag to indicate calculations have been updated
                st.session_state['calculations_updated'] = True
                st.session_state['update_timestamp'] = datetime.now()
                
                st.success("✅ Changes saved!")
                if recalculated_cells:
                    st.info(f"🔄 Recalculated specific capacity values for {len(recalculated_cells)} cell(s): {', '.join(recalculated_cells)}")
                st.rerun()

st.markdown("---")
# Show delete confirmation dialogs when triggered
show_delete_dialogs()

# --- Sidebar ---
with st.sidebar:
    # Restore logo at the top
    try:
        st.image("logo.png", width=150)
    except:
        st.image("https://placehold.co/150x80?text=Logo", width=150)
    st.markdown("---")
    st.markdown("### Projects")
    
    # Minimalistic CSS for sidebar
    st.markdown("""
        <style>
        /* Compact sidebar styling */
        .sidebar-project {
            margin-bottom: 8px;
        }
        .sidebar-experiment {
            margin: 2px 0px;
        }
        /* Reduce button margins and padding for cleaner look */
        div[data-testid="stButton"] > button {
            margin: 0px !important;
            padding: 0.25rem 0.5rem !important;
            font-size: 0.9rem !important;
        }
        /* Compact selectbox */
        div[data-testid="stSelectbox"] > div {
            padding: 0.25rem 0.5rem !important;
        }
        /* Reduce spacing in sidebar */
        .element-container {
            margin-bottom: 0.5rem !important;
        }
        </style>
    """, unsafe_allow_html=True)
    user_projects = get_user_projects(TEST_USER_ID)
    if user_projects:
        for p in user_projects:
            project_id, project_name, project_desc, project_type, created_date, last_modified = p
            project_expanded = st.session_state.get(f'project_expanded_{project_id}', False)
            
            # Compact project row
            project_cols = st.columns([0.1, 0.75, 0.15])
            with project_cols[0]:
                # Dropdown arrow with better styling
                arrow = "▼" if project_expanded else "▶"
                button_type = "primary" if project_expanded else "secondary"
                if st.button(arrow, key=f'project_toggle_{project_id}', 
                           help="Show/Hide experiments", type=button_type):
                    st.session_state[f'project_expanded_{project_id}'] = not project_expanded
                    st.rerun()
            
            with project_cols[1]:
                # Project name button - minimalistic
                is_current_project = st.session_state.get('current_project_id') == project_id
                button_type = "primary" if is_current_project else "secondary"
                if st.button(project_name, key=f'project_select_{project_id}', 
                           use_container_width=True, type=button_type):
                    # Clear any existing experiment data when switching projects
                    if 'loaded_experiment' in st.session_state:
                        del st.session_state['loaded_experiment']
                    
                    # Clear cell input session state when switching projects
                    keys_to_clear = []
                    for key in st.session_state.keys():
                        # Clear cell-specific input fields
                        if (key.startswith('loading_') or 
                            key.startswith('active_') or 
                            key.startswith('testnum_') or 
                            key.startswith('formation_cycles_') or
                            key.startswith('electrolyte_') or
                            key.startswith('substrate_') or
                            key.startswith('formulation_data_') or 
                            key.startswith('formulation_saved_') or
                            key.startswith('component_dropdown_') or
                            key.startswith('component_text_') or
                            key.startswith('component_') or  # Add autocomplete input keys
                            key.startswith('fraction_') or
                            key.endswith('_query') or  # Autocomplete query keys
                            key.endswith('_suggestions') or  # Autocomplete suggestions keys
                            key.endswith('_selected') or  # Autocomplete selected keys
                            key.endswith('_show_suggestions') or  # Autocomplete show suggestions keys
                            key.endswith('_input') or  # Autocomplete input keys
                            key.endswith('_clear') or  # Autocomplete clear keys
                            key.startswith('component_') and key.endswith('_suggestion_') or  # Autocomplete suggestion button keys
                            key.startswith('add_row_') or
                            key.startswith('delete_row_') or
                            key.startswith('multi_file_upload_') or
                            key.startswith('assign_all_cells_') or
                            key == 'datasets' or
                            key == 'processed_data_cache' or
                            key == 'cache_key'):
                            keys_to_clear.append(key)
                    
                    # Remove the keys
                    for key in keys_to_clear:
                        del st.session_state[key]
                    
                    st.session_state['current_project_id'] = project_id
                    st.session_state['current_project_name'] = project_name
                    # Auto-expand when selecting project
                    st.session_state[f'project_expanded_{project_id}'] = True
                    st.rerun()
            
            with project_cols[2]:
                menu_open = st.session_state.get(f'project_menu_open_{project_id}', False)
                if st.button('⋯', key=f'project_menu_btn_{project_id}', 
                           help="Options", type="secondary"):
                    # Close all other menus
                    for p2 in user_projects:
                        st.session_state[f'project_menu_open_{p2[0]}'] = False
                    st.session_state[f'project_menu_open_{project_id}'] = not menu_open
                    st.rerun()
                # Project menu with better styling
                if menu_open:
                    with st.container():
                        st.markdown("---")
                        if st.button('🆕 New Experiment', key=f'project_new_exp_{project_id}_menu', use_container_width=True):
                            st.session_state['current_project_id'] = project_id
                            st.session_state['current_project_name'] = project_name
                            st.session_state['start_new_experiment'] = True
                            if 'loaded_experiment' in st.session_state:
                                del st.session_state['loaded_experiment']
                            
                            # Clear all cell input session state variables
                            keys_to_clear = []
                            for key in st.session_state.keys():
                                # Clear cell-specific input fields
                                if (key.startswith('loading_') or 
                                    key.startswith('active_') or 
                                    key.startswith('testnum_') or 
                                    key.startswith('formation_cycles_') or
                                    key.startswith('electrolyte_') or
                                    key.startswith('substrate_') or
                                    key.startswith('formulation_data_') or 
                                    key.startswith('formulation_saved_') or
                                    key.startswith('component_dropdown_') or
                                    key.startswith('component_text_') or
                                    key.startswith('component_') or  # Add autocomplete input keys
                                    key.startswith('fraction_') or
                                    key.endswith('_query') or  # Autocomplete query keys
                                    key.endswith('_suggestions') or  # Autocomplete suggestions keys
                                    key.endswith('_selected') or  # Autocomplete selected keys
                                    key.endswith('_show_suggestions') or  # Autocomplete show suggestions keys
                                    key.endswith('_input') or  # Autocomplete input keys
                                    key.endswith('_clear') or  # Autocomplete clear keys
                                    key.startswith('component_') and key.endswith('_suggestion_') or  # Autocomplete suggestion button keys
                                    key.startswith('add_row_') or
                                    key.startswith('delete_row_') or
                                    key.startswith('multi_file_upload_') or
                                    key.startswith('assign_all_cells_') or
                                    key == 'datasets' or
                                    key == 'processed_data_cache' or
                                    key == 'cache_key'):
                                    keys_to_clear.append(key)
                            
                            # Remove the keys
                            for key in keys_to_clear:
                                del st.session_state[key]
                            
                            st.session_state[f'project_menu_open_{project_id}'] = False
                            st.session_state['show_cell_inputs_prompt'] = True
                            st.rerun()
                        if st.button('✏️ Rename', key=f'project_rename_{project_id}_menu', use_container_width=True):
                            st.session_state[f'renaming_project_{project_id}'] = True
                            st.session_state[f'project_menu_open_{project_id}'] = False
                            st.rerun()
                        if st.button('🔄 Change Type', key=f'project_change_type_{project_id}_menu', use_container_width=True):
                            st.session_state[f'changing_project_type_{project_id}'] = True
                            st.session_state[f'project_menu_open_{project_id}'] = False
                            st.rerun()
                        if st.button('🗑️ Delete', key=f'project_delete_{project_id}_menu', use_container_width=True, type="secondary"):
                            st.session_state['confirm_delete_project'] = project_id
                            st.session_state[f'project_menu_open_{project_id}'] = False
                            st.rerun()
                        st.markdown("---")
            
            # Inline rename for project
            if st.session_state.get(f'renaming_project_{project_id}', False):
                rename_cols = st.columns([0.8, 0.2])
                with rename_cols[0]:
                    new_name = st.text_input("New name:", value=project_name, key=f'rename_input_project_{project_id}', label_visibility="collapsed")
                with rename_cols[1]:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button('✅', key=f'confirm_rename_project_{project_id}', help="Confirm rename"):
                            if new_name and new_name.strip() != project_name:
                                try:
                                    rename_project(project_id, new_name.strip())
                                    # Update current project name if it's the selected one
                                    if st.session_state.get('current_project_id') == project_id:
                                        st.session_state['current_project_name'] = new_name.strip()
                                    st.session_state[f'renaming_project_{project_id}'] = False
                                    st.success(f"✅ Renamed to '{new_name.strip()}'!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error: {str(e)}")
                            else:
                                st.warning("Please enter a different name.")
                    with col2:
                        if st.button('❌', key=f'cancel_rename_project_{project_id}', help="Cancel rename"):
                            st.session_state[f'renaming_project_{project_id}'] = False
                            st.rerun()
            
            # Inline project type editing
            if st.session_state.get(f'changing_project_type_{project_id}', False):
                type_cols = st.columns([0.8, 0.2])
                with type_cols[0]:
                    project_type_options = ["Cathode", "Anode", "Full Cell"]
                    new_project_type = st.selectbox(
                        "Project Type:",
                        options=project_type_options,
                        index=project_type_options.index(project_type),
                        key=f'type_input_project_{project_id}',
                        label_visibility="collapsed"
                    )
                with type_cols[1]:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button('✅', key=f'confirm_type_project_{project_id}', help="Confirm type change"):
                            if new_project_type != project_type:
                                try:
                                    update_project_type(project_id, new_project_type)
                                    st.session_state[f'changing_project_type_{project_id}'] = False
                                    st.success(f"✅ Changed type to '{new_project_type}'!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error: {str(e)}")
                            else:
                                st.warning("Please select a different type.")
                    with col2:
                        if st.button('❌', key=f'cancel_type_project_{project_id}', help="Cancel type change"):
                            st.session_state[f'changing_project_type_{project_id}'] = False
                            st.rerun()
            
            # Show experiments if project is expanded
            if project_expanded:
                existing_experiments = get_project_experiments(project_id)
                if existing_experiments:
                    # Sort experiments based on user preference
                    sort_key = f'experiment_sort_{project_id}'
                    default_sort = st.session_state.get(sort_key, 'name')  # Default to name sorting (reverse alphabetical)
                    
                    # Minimalistic sort selector - compact design
                    sort_cols = st.columns([0.7, 0.3])
                    with sort_cols[0]:
                        st.markdown("&nbsp;&nbsp;&nbsp;**Experiments**", unsafe_allow_html=True)
                    with sort_cols[1]:
                        sort_option = st.selectbox(
                            "",
                            options=['name', 'date'],
                            format_func=lambda x: 'Z-A' if x == 'name' else 'Date',
                            index=0 if default_sort == 'name' else 1,
                            key=f'sort_select_{project_id}',
                            label_visibility="collapsed"
                        )
                        if sort_option != default_sort:
                            st.session_state[sort_key] = sort_option
                            st.rerun()
                    
                    # Sort experiments
                    if default_sort == 'name':
                        # Sort by name (reverse alphabetical - Z to A) so T33 comes before T32
                        sorted_experiments = sorted(existing_experiments, key=lambda x: x[1].lower(), reverse=True)
                    else:
                        # Sort by date (newest first)
                        sorted_experiments = sorted(existing_experiments, key=lambda x: x[4] if x[4] else '', reverse=True)
                    
                    for experiment in sorted_experiments:
                        experiment_id, experiment_name, file_name, data_json, created_date = experiment
                        loaded_exp = st.session_state.get('loaded_experiment')
                        is_current_experiment = (loaded_exp and loaded_exp.get('experiment_id') == experiment_id)
                        
                        # Minimalistic experiment row - cleaner layout
                        with st.container():
                            exp_cols = st.columns([0.8, 0.2])
                            
                            with exp_cols[0]:
                                button_type = "primary" if is_current_experiment else "secondary"
                                if st.button(experiment_name, key=f'exp_select_{experiment_id}', 
                                           use_container_width=True, type=button_type):
                                    # Clear all formulation-related session state keys before loading new experiment
                                    keys_to_clear = []
                                    for key in st.session_state.keys():
                                        if (key.startswith('formulation_data_') or 
                                            key.startswith('formulation_saved_') or
                                            key.startswith('component_dropdown_') or
                                            key.startswith('component_text_') or
                                            key.startswith('fraction_') or
                                            key.startswith('add_row_') or
                                            key.startswith('delete_row_')):
                                            keys_to_clear.append(key)
                                    
                                    # Remove the formulation keys
                                    for key in keys_to_clear:
                                        del st.session_state[key]
                                    
                                    # Set current project if switching
                                    st.session_state['current_project_id'] = project_id
                                    st.session_state['current_project_name'] = project_name
                                    
                                    st.session_state['loaded_experiment'] = {
                                        'experiment_id': experiment_id,
                                        'experiment_name': experiment_name,
                                        'project_id': project_id,
                                        'experiment_data': json.loads(data_json)
                                    }
                                    st.rerun()
                            
                            with exp_cols[1]:
                                exp_menu_open = st.session_state.get(f'exp_menu_open_{experiment_id}', False)
                                if st.button('⋯', key=f'exp_menu_btn_{experiment_id}', 
                                           help="Options", type="secondary"):
                                    for e2 in existing_experiments:
                                        st.session_state[f'exp_menu_open_{e2[0]}'] = False
                                    st.session_state[f'exp_menu_open_{experiment_id}'] = not exp_menu_open
                                    st.rerun()
                                
                                if exp_menu_open:
                                    with st.container():
                                        if st.button('✏️ Rename', key=f'exp_rename_{experiment_id}_menu', use_container_width=True):
                                            st.session_state[f'renaming_experiment_{experiment_id}'] = True
                                            st.session_state[f'exp_menu_open_{experiment_id}'] = False
                                            st.rerun()
                                        if st.button('📋 Duplicate', key=f'exp_duplicate_{experiment_id}_menu', use_container_width=True):
                                            st.session_state['duplicate_experiment'] = (experiment_id, experiment_name)
                                            st.session_state[f'exp_menu_open_{experiment_id}'] = False
                                            st.rerun()
                                        if st.button('🗑️ Delete', key=f'exp_delete_{experiment_id}_menu', use_container_width=True, type="secondary"):
                                            st.session_state['confirm_delete_experiment'] = (experiment_id, experiment_name)
                                            st.session_state[f'exp_menu_open_{experiment_id}'] = False
                                            st.rerun()
                        
                        # Inline rename for experiment with better layout
                        if st.session_state.get(f'renaming_experiment_{experiment_id}', False):
                            exp_rename_cols = st.columns([0.12, 0.68, 0.20])
                            with exp_rename_cols[1]:
                                new_exp_name = st.text_input("New name:", value=experiment_name, key=f'rename_input_experiment_{experiment_id}', label_visibility="collapsed")
                            with exp_rename_cols[2]:
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button('✅', key=f'confirm_rename_experiment_{experiment_id}', help="Confirm rename"):
                                        if new_exp_name and new_exp_name.strip() != experiment_name:
                                            try:
                                                rename_experiment(experiment_id, new_exp_name.strip())
                                                # Update loaded experiment name if it's the selected one
                                                if (st.session_state.get('loaded_experiment') and 
                                                    st.session_state['loaded_experiment'].get('experiment_id') == experiment_id):
                                                    st.session_state['loaded_experiment']['experiment_name'] = new_exp_name.strip()
                                                st.session_state[f'renaming_experiment_{experiment_id}'] = False
                                                st.success(f"✅ Renamed to '{new_exp_name.strip()}'!")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"❌ Error: {str(e)}")
                                        else:
                                            st.warning("Please enter a different name.")
                                with col2:
                                    if st.button('❌', key=f'cancel_rename_experiment_{experiment_id}', help="Cancel rename"):
                                        st.session_state[f'renaming_experiment_{experiment_id}'] = False
                                        st.rerun()
                else:
                    st.markdown("&nbsp;&nbsp;&nbsp;&nbsp;<small>*No experiments*</small>", unsafe_allow_html=True)
            
            # Minimal spacing between projects
            st.markdown("")
    else:
        st.info("No projects found. Create your first project below.")

    # Create new project
    with st.expander("➕ Create New Project", expanded=False):
        new_project_name = st.text_input("Project Name", key="new_project_name")
        new_project_description = st.text_area("Description (optional)", key="new_project_description")
        
        # Project type selection
        project_type_options = ["Cathode", "Anode", "Full Cell"]
        new_project_type = st.selectbox(
            "Project Type", 
            options=project_type_options,
            index=2,  # Default to "Full Cell"
            key="new_project_type",
            help="Select the type of battery component this project will focus on"
        )
        
        if st.button("Create Project", key="create_project_btn"):
            if new_project_name:
                project_id = create_project(TEST_USER_ID, new_project_name, new_project_description, new_project_type)
                st.success(f"Project '{new_project_name}' ({new_project_type}) created successfully!")
                st.rerun()
            else:
                st.error("Please enter a project name.")

    st.markdown("---")
    
    # Show currently loaded experiment status
    loaded_experiment = st.session_state.get('loaded_experiment')
    if loaded_experiment:
        st.markdown("**Active:** " + loaded_experiment.get('experiment_name', 'Unknown'))
    
    st.markdown("---")
    st.markdown("### Quick Start")
    st.markdown("1. Create or select a project")
    st.markdown("2. Go to **Cell Inputs** tab")
    st.markdown("3. View results in **Summary** and **Plots**")
    
    # Render project preferences sidebar if a project is selected
    if st.session_state.get('current_project_id'):
        render_preferences_sidebar(st.session_state['current_project_id'])

# --- Dropdown CSS and Global State Management ---
# Add CSS for Gmail-style popup dropdown
st.markdown(
    """
    <style>
    /* Container for the three dots and popup */
    .dropdown-container {
        position: relative;
        display: inline-block;
    }
    
    /* Three dots button styling */
    .three-dots-btn {
        background: none;
        border: none;
        font-size: 18px;
        cursor: pointer;
        padding: 4px 8px;
        border-radius: 4px;
        color: #666;
        transition: background-color 0.2s;
    }
    
    .three-dots-btn:hover {
        background-color: #f0f0f0;
    }
    
    /* Gmail-style popup menu */
    .popup-menu {
        position: absolute;
        right: 0;
        top: 100%;
        background-color: white;
        border: 1px solid #ddd;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        z-index: 1000;
        min-width: 120px;
        margin-top: 4px;
        padding: 4px 0;
        display: none;
    }
    
    /* Show popup when active */
    .popup-menu.show {
        display: block;
    }
    
    /* Popup menu items */
    .popup-item {
        display: block;
        width: 100%;
        padding: 8px 16px;
        text-align: left;
        background: none;
        border: none;
        cursor: pointer;
        font-size: 14px;
        color: #333;
        transition: background-color 0.2s;
        white-space: nowrap;
    }
    
    .popup-item:hover {
        background-color: #f5f5f5;
    }
    
    .popup-item.delete {
        color: #d32f2f;
    }
    
    .popup-item.delete:hover {
        background-color: #ffebee;
    }
    
    /* Arrow pointing up to the three dots */
    .popup-menu::before {
        content: '';
        position: absolute;
        top: -6px;
        right: 12px;
        width: 0;
        height: 0;
        border-left: 6px solid transparent;
        border-right: 6px solid transparent;
        border-bottom: 6px solid white;
        z-index: 1001;
    }
    
    .popup-menu::after {
        content: '';
        position: absolute;
        top: -7px;
        right: 12px;
        width: 0;
        height: 0;
        border-left: 6px solid transparent;
        border-right: 6px solid transparent;
        border-bottom: 6px solid #ddd;
        z-index: 1000;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Show delete confirmation dialogs when triggered
if st.session_state.get("confirm_delete_project"):
    confirm_delete_project()
else:
    pass

if st.session_state.get("confirm_delete_experiment"):
    confirm_delete_experiment()
else:
    pass

# Handle experiment duplication
if st.session_state.get("duplicate_experiment"):
    experiment_id, experiment_name = st.session_state["duplicate_experiment"]
    try:
        new_experiment_id, new_experiment_name = duplicate_experiment(experiment_id)
        st.success(f"✅ Successfully duplicated '{experiment_name}' as '{new_experiment_name}'! You can now upload new data to this experiment.")
        # Clear the duplication state
        del st.session_state["duplicate_experiment"]
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error duplicating experiment: {str(e)}")
        del st.session_state["duplicate_experiment"]

if 'datasets' not in st.session_state:
    st.session_state['datasets'] = []
datasets = st.session_state.get('datasets', [])
disc_diameter_mm = st.session_state.get('disc_diameter_mm', 15)
experiment_date = st.session_state.get('experiment_date', date.today())
# Ensure experiment_name is always defined
experiment_name = st.session_state.get('sidebar_experiment_name', '') or ''

# Tab selection state
if 'active_main_tab' not in st.session_state:
    st.session_state['active_main_tab'] = 0

# Remove unsupported arguments from st.tabs
# If 'show_cell_inputs_prompt' is set, show a message at the top
if 'show_cell_inputs_prompt' not in st.session_state:
    st.session_state['show_cell_inputs_prompt'] = False

if st.session_state.get('show_cell_inputs_prompt'):
    st.warning('Please click the "🧪 Cell Inputs" tab above to start your new experiment.')
    st.session_state['show_cell_inputs_prompt'] = False

# Create tabs - include Master Table and Comparison tabs if a project is selected
current_project_id = st.session_state.get('current_project_id')
if current_project_id:
    tab_inputs, tab1, tab2, tab_comparison, tab_master = st.tabs(["🧪 Cell Inputs", "📈 Plots", "📤 Export", "🔄 Comparison", "📋 Master Table"])
else:
    tab_inputs, tab1, tab2 = st.tabs(["🧪 Cell Inputs", "📈 Plots", "📤 Export"])
    tab_comparison = None
    tab_master = None

# --- Cell Inputs Tab ---
with tab_inputs:
    # If user started a new experiment, clear cell input state
    if st.session_state.get('start_new_experiment'):
        # Clear experiment-level session state
        st.session_state['datasets'] = []
        st.session_state['current_experiment_name'] = ''
        st.session_state['current_experiment_date'] = date.today()
        st.session_state['current_disc_diameter_mm'] = 15
        st.session_state['current_group_assignments'] = None
        st.session_state['current_group_names'] = ["Group A", "Group B", "Group C"]
        
        # Clear any remaining cell input session state variables
        keys_to_clear = []
        for key in st.session_state.keys():
            # Clear cell-specific input fields that might have been missed
            if (key.startswith('loading_') or 
                key.startswith('active_') or 
                key.startswith('testnum_') or 
                key.startswith('formation_cycles_') or
                key.startswith('electrolyte_') or
                key.startswith('substrate_') or
                key.startswith('formulation_data_') or 
                key.startswith('formulation_saved_') or
                key.startswith('component_dropdown_') or
                key.startswith('component_text_') or
                key.startswith('fraction_') or
                key.startswith('add_row_') or
                key.startswith('delete_row_') or
                key.startswith('multi_file_upload_') or
                key.startswith('assign_all_cells_') or
                key == 'datasets' or
                key == 'processed_data_cache' or
                key == 'cache_key'):
                keys_to_clear.append(key)
        
        # Remove the keys
        for key in keys_to_clear:
            del st.session_state[key]
        
        st.session_state['start_new_experiment'] = False
    st.header("🧪 Cell Inputs & Experiment Setup")
    st.markdown("---")
    
    # Check if we have a loaded experiment
    loaded_experiment = st.session_state.get('loaded_experiment')
    
    # If a new experiment is being started, always allow editing
    is_new_experiment = not loaded_experiment and st.session_state.get('current_project_id')
    
    if loaded_experiment:
        experiment_data = loaded_experiment['experiment_data']
        cells_data = experiment_data.get('cells', [])
        
        # Show different message for experiments with no cells (e.g., duplicates)
        if len(cells_data) == 0:
            st.info(f"📝 Setting up experiment: **{loaded_experiment['experiment_name']}** (ready for data upload)")
        else:
            st.info(f"📊 Editing experiment: **{loaded_experiment['experiment_name']}**")
        
        # Load existing values from the experiment
        current_experiment_name = loaded_experiment['experiment_name']
        current_experiment_date = experiment_data.get('experiment_date')
        if isinstance(current_experiment_date, str):
            try:
                current_experiment_date = datetime.fromisoformat(current_experiment_date).date()
            except:
                current_experiment_date = date.today()
        elif current_experiment_date is None:
            current_experiment_date = date.today()
        current_disc_diameter = experiment_data.get('disc_diameter_mm', 15)
        current_group_assignments = experiment_data.get('group_assignments')
        current_group_names = experiment_data.get('group_names', ["Group A", "Group B", "Group C"])
        # --- Load experiment-level fields from experiment data ---
        st.session_state['solids_content'] = experiment_data.get('solids_content', 0.0)
        st.session_state['pressed_thickness'] = experiment_data.get('pressed_thickness', 0.0)
        st.session_state['experiment_notes'] = experiment_data.get('experiment_notes', '')
        
        # --- Load cell format data from experiment ---
        st.session_state['current_cell_format'] = experiment_data.get('cell_format', 'Coin')
        if experiment_data.get('cathode_length'):
            st.session_state['current_cathode_length'] = experiment_data.get('cathode_length', 50.0)
        if experiment_data.get('cathode_width'):
            st.session_state['current_cathode_width'] = experiment_data.get('cathode_width', 50.0)
        if experiment_data.get('num_stacked_cells'):
            st.session_state['current_num_stacked_cells'] = experiment_data.get('num_stacked_cells', 1)
        # Convert loaded cells data back to datasets format for editing
        cells_data = experiment_data.get('cells', [])
        loaded_datasets = []
        for cell_data in cells_data:
            # Create a mock file object for display purposes
            mock_file = type('MockFile', (), {
                'name': cell_data.get('file_name', 'loaded_data.csv'),
                'type': 'text/csv'
            })()
            
            loaded_datasets.append({
                'file': mock_file,
                'loading': cell_data.get('loading', 20.0),
                'active': cell_data.get('active_material', 90.0),
                'testnum': cell_data.get('test_number', cell_data.get('cell_name', '')),
                'formation_cycles': cell_data.get('formation_cycles', 4),
                'electrolyte': cell_data.get('electrolyte', '1M LiPF6 1:1:1'),
                'substrate': cell_data.get('substrate', 'Copper'),
                'separator': cell_data.get('separator', '25um PP'),
                'formulation': cell_data.get('formulation', []),
                'excluded': cell_data.get('excluded', False)  # Add this line
            })
        
        # Use loaded datasets as starting point
        datasets = loaded_datasets
        st.session_state['datasets'] = datasets
        
    elif is_new_experiment:
        st.info(f"📝 Creating a new experiment in project: **{st.session_state['current_project_name']}**")
        current_experiment_name = ""
        current_experiment_date = date.today()
        current_disc_diameter = 15
        current_group_assignments = None
        current_group_names = ["Group A", "Group B", "Group C"]
        # --- Reset experiment-level fields for new experiment ---
        st.session_state['solids_content'] = 0.0
        st.session_state['pressed_thickness'] = 0.0
        st.session_state['experiment_notes'] = ''
    else:
        st.info("📝 Create a new experiment or load an existing one from the sidebar")
        current_experiment_name = ""
        current_experiment_date = date.today()
        current_disc_diameter = 15
        current_group_assignments = None
        current_group_names = ["Group A", "Group B", "Group C"]
        # --- Reset experiment-level fields for no experiment ---
        st.session_state['solids_content'] = 0.0
        st.session_state['pressed_thickness'] = 0.0
        st.session_state['experiment_notes'] = ''
    
    # Experiment metadata inputs
    col1, col2 = st.columns(2)
    with col1:
        experiment_name_input = st.text_input(
            'Experiment Name', 
            value=current_experiment_name if loaded_experiment else experiment_name,
            placeholder='Enter experiment name for file naming',
            key="main_experiment_name"
        )
    
    with col2:
        experiment_date_input = st.date_input(
            "Experiment Date", 
            value=current_experiment_date,
            help="Date associated with this experiment"
        )
    
    # Get current project type to determine input fields
    current_project_id = st.session_state.get('current_project_id')
    project_type = "Full Cell"  # Default
    if current_project_id:
        project_info = get_project_by_id(current_project_id)
        if project_info:
            project_type = project_info[3]  # project_type is the 4th field
    
    # Enhanced Full Cell format selection
    if project_type == "Full Cell":
        st.markdown("#### 🔋 Cell Configuration")
        
        # Cell format dropdown
        format_options = ["Coin", "Pouch", "Cylindrical", "Prismatic"]
        current_format = st.session_state.get('current_cell_format', 'Coin')
        
        cell_format = st.selectbox(
            'Cell Format',
            options=format_options,
            index=format_options.index(current_format) if current_format in format_options else 0,
            key='cell_format_input',
            help="Select the physical format of the battery cell"
        )
        
        # Store format in session state
        st.session_state['current_cell_format'] = cell_format
        
        if cell_format == "Coin":
            # Show traditional disc diameter input
            disc_diameter_input = st.number_input(
                'Disc Diameter (mm) for Areal Capacity Calculation', 
                min_value=1, 
                max_value=50, 
                value=current_disc_diameter, 
                step=1,
                help="Diameter of the coin cell disc for areal capacity calculations"
            )
            
        elif cell_format == "Pouch":
            # Show pouch-specific inputs
            st.markdown("##### Pouch Cell Dimensions")
            col1, col2 = st.columns(2)
            
            with col1:
                cathode_length = st.number_input(
                    'Cathode Length (mm)',
                    min_value=1.0,
                    max_value=500.0,
                    value=st.session_state.get('current_cathode_length', 50.0),
                    step=0.1,
                    key='cathode_length_input',
                    help="Length of the cathode active area"
                )
                
                cathode_width = st.number_input(
                    'Cathode Width (mm)',
                    min_value=1.0,
                    max_value=500.0,
                    value=st.session_state.get('current_cathode_width', 50.0),
                    step=0.1,
                    key='cathode_width_input',
                    help="Width of the cathode active area"
                )
            
            with col2:
                num_stacked_cells = st.number_input(
                    'Number of Stacked Cells',
                    min_value=1,
                    max_value=100,
                    value=st.session_state.get('current_num_stacked_cells', 1),
                    step=1,
                    key='num_stacked_cells_input',
                    help="Number of cells stacked in the pouch configuration"
                )
                
                # Calculate and display total area
                total_area_cm2 = (cathode_length * cathode_width * num_stacked_cells) / 100  # Convert mm² to cm²
                st.metric(
                    label="Total Active Area", 
                    value=f"{total_area_cm2:.2f} cm²",
                    help="Total cathode active area for all stacked cells"
                )
            
            # Store pouch values in session state
            st.session_state['current_cathode_length'] = cathode_length
            st.session_state['current_cathode_width'] = cathode_width
            st.session_state['current_num_stacked_cells'] = num_stacked_cells
            
            # Set disc_diameter_input to None since we're using area calculations instead
            disc_diameter_input = None
            
        elif cell_format in ["Cylindrical", "Prismatic"]:
            # Under construction message
            st.info(f"🚧 **{cell_format} Cell Format - Under Construction**")
            st.markdown(
                f"The {cell_format.lower()} cell format configuration is currently being developed. "
                "Please select 'Coin' or 'Pouch' format for now, or check back in a future update!"
            )
            # Use default disc diameter for now
            disc_diameter_input = current_disc_diameter
            
    else:
        # For non-Full Cell projects (Cathode/Anode), show traditional disc diameter input
        disc_diameter_input = st.number_input(
            'Disc Diameter (mm) for Areal Capacity Calculation', 
            min_value=1, 
            max_value=50, 
            value=current_disc_diameter, 
            step=1,
            help="Diameter of the electrode disc for areal capacity calculations"
        )
    
    st.markdown("---")
    
    # Cell inputs section
    # Show file upload for new experiments OR loaded experiments with no cells (e.g., duplicates)
    has_cells = loaded_experiment and len(datasets) > 0
    
    if loaded_experiment and has_cells:
        # For loaded experiments, show the cell input fields for editing
        if len(datasets) > 1:
            with st.expander(f'Cell 1: {datasets[0]["testnum"] or "Cell 1"}', expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    loading_0 = st.number_input(
                        f'Disc loading (mg) for Cell 1', 
                        min_value=0.0, 
                        step=1.0, 
                        value=float(datasets[0]["loading"]),
                        key=f'edit_loading_0'
                    )
                    formation_cycles_0 = st.number_input(
                        f'Formation Cycles for Cell 1', 
                        min_value=0, 
                        step=1, 
                        value=int(datasets[0]["formation_cycles"]),
                        key=f'edit_formation_0'
                    )
                with col2:
                    active_material_0 = st.number_input(
                        f'% Active material for Cell 1', 
                        min_value=0.0, 
                        max_value=100.0, 
                        step=1.0, 
                        value=float(datasets[0]["active"]),
                        key=f'edit_active_0'
                    )
                    test_number_0 = st.text_input(
                        f'Test Number for Cell 1', 
                        value=datasets[0]["testnum"] or "Cell 1",
                        key=f'edit_testnum_0'
                    )
                
                # Electrolyte, Substrate, and Separator selection
                substrate_options = get_substrate_options()
                
                col3, col4, col5 = st.columns(3)
                with col3:
                    from ui_components import render_hybrid_electrolyte_input
                    electrolyte_0 = render_hybrid_electrolyte_input(
                        f'Electrolyte for Cell 1', 
                        default_value=datasets[0]["electrolyte"],
                        key=f'edit_electrolyte_0'
                    )
                with col4:
                    substrate_0 = st.selectbox(
                        f'Substrate for Cell 1', 
                        substrate_options,
                        index=substrate_options.index(datasets[0].get("substrate", "Copper")) if datasets[0].get("substrate") in substrate_options else 0,
                        key=f'edit_substrate_0'
                    )
                with col5:
                    from ui_components import render_hybrid_separator_input
                    separator_0 = render_hybrid_separator_input(
                        f'Separator for Cell 1', 
                        default_value=datasets[0].get("separator", "25um PP"),
                        key=f'edit_separator_0'
                    )
                
                # Formulation table
                st.markdown("**Formulation:**")
                from ui_components import render_formulation_table
                # Initialize formulation data if needed
                formulation_key = f'formulation_data_edit_0_loaded'
                if formulation_key not in st.session_state:
                    st.session_state[formulation_key] = datasets[0]["formulation"] if datasets[0]["formulation"] else [{'Component': '', 'Dry Mass Fraction (%)': 0.0}]
                formulation_0 = render_formulation_table(f'edit_0_loaded', project_id, get_project_components)
                
                # Add two buttons: Exclude and Remove
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    exclude_button_disabled = datasets[0].get('excluded', False)
                    if st.button("🚫 Exclude Cell", key=f'exclude_cell_loaded_0', disabled=exclude_button_disabled):
                        datasets[0]['excluded'] = True
                        st.session_state['datasets'] = datasets  # Save to session state
                        st.rerun()
                
                with col_btn2:
                    if st.button("🗑️ Remove Cell", key=f'remove_cell_loaded_0'):
                        st.session_state[f'confirm_remove_cell_loaded_0'] = True

                # Show excluded status
                if datasets[0].get('excluded', False):
                    st.warning("⚠️ This cell is excluded from analysis")
                    if st.button("✅ Include Cell", key=f'include_cell_loaded_0'):
                        datasets[0]['excluded'] = False
                        st.session_state['datasets'] = datasets  # Save to session state
                        st.rerun()

                if st.session_state.get(f'confirm_remove_cell_loaded_0', False):
                    st.error("⚠️ **PERMANENT DELETION** - This will permanently delete the cell data and cannot be undone!")
                    col_confirm1, col_confirm2 = st.columns(2)
                    with col_confirm1:
                        if st.button("🗑️ Delete Permanently", key=f'confirm_yes_loaded_0', type="primary"):
                            # Actually remove the cell from the datasets
                            datasets.pop(0)
                            st.session_state[f'confirm_remove_cell_loaded_0'] = False
                            st.rerun()
                    with col_confirm2:
                        if st.button("Cancel", key=f'confirm_no_loaded_0'):
                            st.session_state[f'confirm_remove_cell_loaded_0'] = False
                            st.rerun()

                assign_all = st.checkbox('Assign values to all cells', key='assign_all_cells_loaded')
            # Update all datasets with new values
            edited_datasets = []
            for i, dataset in enumerate(datasets):
                # Don't skip excluded cells - still render them but with visual indication
                
                if i == 0:
                    # First cell: preserve original file object and update other fields
                    edited_dataset = {
                        'file': dataset['file'],  # Always preserve original file object
                        'loading': loading_0,
                        'active': active_material_0,
                        'testnum': test_number_0,
                        'formation_cycles': formation_cycles_0,
                        'electrolyte': electrolyte_0,
                        'substrate': substrate_0,
                        'separator': separator_0,
                        'formulation': formulation_0,
                        'excluded': dataset.get('excluded', False)  # Add this line
                    }
                else:
                    is_excluded = dataset.get('excluded', False)
                    cell_title = f'Cell {i+1}: {dataset["testnum"] or f"Cell {i+1}"}'
                    if is_excluded:
                        cell_title += " ⚠️ EXCLUDED"
                    
                    with st.expander(cell_title, expanded=False):
                        col1, col2 = st.columns(2)
                        if assign_all:
                            loading = loading_0
                            formation_cycles = formation_cycles_0
                            active_material = active_material_0
                            electrolyte = electrolyte_0
                            substrate = substrate_0
                            separator = separator_0
                            formulation = formulation_0
                            # Test number should remain individual (not assigned to all)
                            test_number = dataset['testnum'] or f'Cell {i+1}'
                        else:
                            with col1:
                                loading = st.number_input(
                                    f'Disc loading (mg) for Cell {i+1}', 
                                    min_value=0.0, 
                                    step=1.0, 
                                    value=float(dataset['loading']),
                                    key=f'edit_loading_{i}'
                                )
                                formation_cycles = st.number_input(
                                    f'Formation Cycles for Cell {i+1}', 
                                    min_value=0, 
                                    step=1, 
                                    value=int(dataset['formation_cycles']),
                                    key=f'edit_formation_{i}'
                                )
                            with col2:
                                active_material = st.number_input(
                                    f'% Active material for Cell {i+1}', 
                                    min_value=0.0, 
                                    max_value=100.0, 
                                    step=1.0, 
                                    value=float(dataset['active']),
                                    key=f'edit_active_{i}'
                                )
                                test_number = st.text_input(
                                    f'Test Number for Cell {i+1}', 
                                    value=dataset['testnum'] or f'Cell {i+1}',
                                    key=f'edit_testnum_{i}'
                                )
                            
                            # Electrolyte, Substrate, and Separator selection
                            substrate_options = get_substrate_options()
                            
                            col3, col4, col5 = st.columns(3)
                            with col3:
                                electrolyte = render_hybrid_electrolyte_input(
                                    f'Electrolyte for Cell {i+1}', 
                                    default_value=dataset['electrolyte'],
                                    key=f'edit_electrolyte_{i}'
                                )
                            with col4:
                                substrate = st.selectbox(
                                    f'Substrate for Cell {i+1}', 
                                    substrate_options,
                                    index=substrate_options.index(dataset.get('substrate', 'Copper')) if dataset.get('substrate') in substrate_options else 0,
                                    key=f'edit_substrate_{i}'
                                )
                            with col5:
                                separator = render_hybrid_separator_input(
                                    f'Separator for Cell {i+1}', 
                                    default_value=dataset.get('separator', '25um PP'),
                                    key=f'edit_separator_{i}'
                                )
                            
                            # Formulation table
                            st.markdown("**Formulation:**")
                            from ui_components import render_formulation_table
                            # Initialize formulation data if needed
                            formulation_key = f'formulation_data_edit_{i}_loaded'
                            if formulation_key not in st.session_state:
                                st.session_state[formulation_key] = dataset['formulation'] if dataset['formulation'] else [{'Component': '', 'Dry Mass Fraction (%)': 0.0}]
                            formulation = render_formulation_table(f'edit_{i}_loaded', project_id, get_project_components)
                            
                            # Add two buttons: Exclude and Remove
                            col_btn1, col_btn2 = st.columns(2)
                            
                            with col_btn1:
                                exclude_button_disabled = dataset.get('excluded', False)
                                if st.button("🚫 Exclude Cell", key=f'exclude_cell_loaded_{i}', disabled=exclude_button_disabled):
                                    datasets[i]['excluded'] = True
                                    st.session_state['datasets'] = datasets  # Save to session state
                                    st.rerun()
                            
                            with col_btn2:
                                if st.button("🗑️ Remove Cell", key=f'remove_cell_loaded_{i}'):
                                    st.session_state[f'confirm_remove_cell_loaded_{i}'] = True

                            # Show excluded status
                            if dataset.get('excluded', False):
                                st.warning("⚠️ This cell is excluded from analysis")
                                if st.button("✅ Include Cell", key=f'include_cell_loaded_{i}'):
                                    datasets[i]['excluded'] = False
                                    st.session_state['datasets'] = datasets  # Save to session state
                                    st.rerun()

                            if st.session_state.get(f'confirm_remove_cell_loaded_{i}', False):
                                st.error("⚠️ **PERMANENT DELETION** - This will permanently delete the cell data and cannot be undone!")
                                col_confirm1, col_confirm2 = st.columns(2)
                                with col_confirm1:
                                    if st.button("🗑️ Delete Permanently", key=f'confirm_yes_loaded_{i}', type="primary"):
                                        # Actually remove the cell from the datasets
                                        datasets.pop(i)
                                        st.session_state[f'confirm_remove_cell_loaded_{i}'] = False
                                        st.rerun()
                                with col_confirm2:
                                    if st.button("Cancel", key=f'confirm_no_loaded_{i}'):
                                        st.session_state[f'confirm_remove_cell_loaded_{i}'] = False
                                        st.rerun()
                        
                        # Always preserve original file object, only update other fields
                        edited_dataset = {
                            'file': dataset['file'],  # Always preserve original file object
                            'loading': loading,
                            'active': active_material,
                            'testnum': test_number,
                            'formation_cycles': formation_cycles,
                            'electrolyte': electrolyte,
                            'substrate': substrate,
                            'separator': separator,
                            'formulation': formulation,
                            'excluded': dataset.get('excluded', False)
                        }

                edited_datasets.append(edited_dataset)
            datasets = edited_datasets
            st.session_state['datasets'] = datasets
        else:
            # Only one cell
            for i, dataset in enumerate(datasets):
                # Don't skip excluded cells - still render them but with visual indication
                
                is_excluded = dataset.get('excluded', False)
                cell_title = f'Cell {i+1}: {dataset["testnum"] or f"Cell {i+1}"}'
                if is_excluded:
                    cell_title += " ⚠️ EXCLUDED"
                
                with st.expander(cell_title, expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        loading = st.number_input(
                            f'Disc loading (mg) for Cell {i+1}', 
                            min_value=0.0, 
                            step=1.0, 
                            value=float(dataset['loading']),
                            key=f'edit_loading_{i}'
                        )
                        formation_cycles = st.number_input(
                            f'Formation Cycles for Cell {i+1}', 
                            min_value=0, 
                            step=1, 
                            value=int(dataset['formation_cycles']),
                            key=f'edit_formation_{i}'
                        )
                    with col2:
                        active_material = st.number_input(
                            f'% Active material for Cell {i+1}', 
                            min_value=0.0, 
                            max_value=100.0, 
                            step=1.0, 
                            value=float(dataset['active']),
                            key=f'edit_active_{i}'
                        )
                        test_number = st.text_input(
                            f'Test Number for Cell {i+1}', 
                            value=dataset['testnum'] or f'Cell {i+1}',
                            key=f'edit_testnum_{i}'
                        )
                    
                    # Electrolyte, Substrate, and Separator selection
                    substrate_options = get_substrate_options()
                    
                    col3, col4, col5 = st.columns(3)
                    with col3:
                        electrolyte = render_hybrid_electrolyte_input(
                            f'Electrolyte for Cell {i+1}', 
                            default_value=dataset['electrolyte'],
                            key=f'edit_single_electrolyte_{i}'
                        )
                    with col4:
                        substrate = st.selectbox(
                            f'Substrate for Cell {i+1}', 
                            substrate_options,
                            index=substrate_options.index(dataset.get('substrate', 'Copper')) if dataset.get('substrate') in substrate_options else 0,
                            key=f'edit_single_substrate_{i}'
                        )
                    with col5:
                        separator = render_hybrid_separator_input(
                            f'Separator for Cell {i+1}', 
                            default_value=dataset.get('separator', '25um PP'),
                            key=f'edit_single_separator_{i}'
                        )
                    
                    # Formulation table
                    st.markdown("**Formulation:**")
                    from ui_components import render_formulation_table
                    # Initialize formulation data if needed
                    formulation_key = f'formulation_data_edit_single_{i}_loaded'
                    if formulation_key not in st.session_state:
                        st.session_state[formulation_key] = dataset['formulation'] if dataset['formulation'] else [{'Component': '', 'Dry Mass Fraction (%)': 0.0}]
                    formulation = render_formulation_table(f'edit_single_{i}_loaded', project_id, get_project_components)
                    
                    # Add two buttons: Exclude and Remove
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        exclude_button_disabled = dataset.get('excluded', False)
                        if st.button("🚫 Exclude Cell", key=f'exclude_cell_single_{i}', disabled=exclude_button_disabled):
                            datasets[i]['excluded'] = True
                            st.session_state['datasets'] = datasets  # Save to session state
                            st.rerun()
                    
                    with col_btn2:
                        if st.button("🗑️ Remove Cell", key=f'remove_cell_single_{i}'):
                            st.session_state[f'confirm_remove_cell_single_{i}'] = True

                    # Show excluded status
                    if dataset.get('excluded', False):
                        st.warning("⚠️ This cell is excluded from analysis")
                        if st.button("✅ Include Cell", key=f'include_cell_single_{i}'):
                            datasets[i]['excluded'] = False
                            st.session_state['datasets'] = datasets  # Save to session state
                            st.rerun()

                    if st.session_state.get(f'confirm_remove_cell_single_{i}', False):
                        st.error("⚠️ **PERMANENT DELETION** - This will permanently delete the cell data and cannot be undone!")
                        col_confirm1, col_confirm2 = st.columns(2)
                        with col_confirm1:
                            if st.button("🗑️ Delete Permanently", key=f'confirm_yes_single_{i}', type="primary"):
                                # Actually remove the cell from the datasets  
                                datasets.pop(i)
                                st.session_state[f'confirm_remove_cell_single_{i}'] = False
                                st.rerun()
                        with col_confirm2:
                            if st.button("Cancel", key=f'confirm_no_single_{i}'):
                                st.session_state[f'confirm_remove_cell_single_{i}'] = False
                                st.rerun()

                    # Always preserve original file object, only update other fields
                    edited_dataset = {
                        'file': dataset['file'],  # Always preserve original file object
                        'loading': loading,
                        'active': active_material,
                        'testnum': test_number,
                        'formation_cycles': formation_cycles,
                        'electrolyte': electrolyte,
                        'substrate': substrate,
                        'separator': separator,
                        'formulation': formulation,
                        'excluded': dataset.get('excluded', False)
                    }
                    dataset.update(edited_dataset)
    else:
        # New experiment flow - use unified render_cell_inputs
        st.markdown("#### 📁 Upload Cell Data Files")
        
        # For duplicated experiments, pre-populate defaults from original experiment
        if loaded_experiment:
            experiment_data = loaded_experiment['experiment_data']
            default_cell_values = experiment_data.get('default_cell_values', {})
            
            if default_cell_values:
                st.info("ℹ️ Using default values from the original experiment. You can modify these as needed.")
                # Pre-populate session state with default values from the original experiment
                if 'loading_0' not in st.session_state:
                    st.session_state['loading_0'] = default_cell_values.get('loading', 20.0)
                if 'active_0' not in st.session_state:
                    st.session_state['active_0'] = default_cell_values.get('active_material', 90.0)
                if 'formation_cycles_0' not in st.session_state:
                    st.session_state['formation_cycles_0'] = default_cell_values.get('formation_cycles', 4)
                if 'electrolyte_0' not in st.session_state:
                    st.session_state['electrolyte_0'] = default_cell_values.get('electrolyte', '1M LiPF6 1:1:1')
                if 'substrate_0' not in st.session_state:
                    st.session_state['substrate_0'] = default_cell_values.get('substrate', 'Copper')
                if 'separator_0' not in st.session_state:
                    st.session_state['separator_0'] = default_cell_values.get('separator', '25um PP')
                # Pre-populate formulation data
                if 'formulation_data_0_main_cell_inputs' not in st.session_state:
                    formulation = default_cell_values.get('formulation', [])
                    if formulation:
                        st.session_state['formulation_data_0_main_cell_inputs'] = formulation
        
        current_project_id = st.session_state.get('current_project_id')
        datasets = render_cell_inputs(context_key='main_cell_inputs', project_id=current_project_id, get_components_func=get_project_components)
        st.session_state['datasets'] = datasets
        # Store original uploaded files separately to prevent loss
        if datasets:
            st.session_state['original_uploaded_files'] = [ds['file'] for ds in datasets if ds.get('file')]
    
    # Group assignment section (if multiple cells)
    enable_grouping = False
    show_averages = False
    group_assignments = current_group_assignments
    group_names = current_group_names
    
    # --- New experiment-level fields ---
    st.markdown('---')
    st.subheader('Experiment Parameters')
    solids_content = st.number_input(
        'Solids Content (%)',
        min_value=0.0, max_value=100.0, step=0.1,
        value=st.session_state.get('solids_content', 0.0),
        help='Percentage solids in the slurry formulation when the electrode was made.'
    )
    pressed_thickness = st.number_input(
        'Pressed Thickness (um)',
        min_value=0.0, step=0.1,
        value=st.session_state.get('pressed_thickness', 0.0),
        help='Pressed electrode thickness in microns (um).'
    )
    experiment_notes = st.text_area(
        'Experiment Notes',
        value=st.session_state.get('experiment_notes', ''),
        help='Basic notes associated with this experiment.'
    )
    st.session_state['solids_content'] = solids_content
    st.session_state['pressed_thickness'] = pressed_thickness
    st.session_state['experiment_notes'] = experiment_notes
    
    if datasets and len([d for d in datasets if d.get('file') or loaded_experiment or is_new_experiment]) > 1:
        st.markdown("---")
        st.markdown("#### 👥 Group Assignment (Optional)")
        enable_grouping = st.checkbox('Assign Cells into Groups?', value=bool(current_group_assignments))
        
        if enable_grouping:
            col1, col2, col3 = st.columns(3)
            with col1:
                group_names[0] = st.text_input('Group A Name', value=group_names[0], key='main_group_name_a')
            with col2:
                group_names[1] = st.text_input('Group B Name', value=group_names[1], key='main_group_name_b')
            with col3:
                group_names[2] = st.text_input('Group C Name', value=group_names[2], key='main_group_name_c')
            
            st.markdown("**Assign each cell to a group:**")
            group_assignments = []
            for i, cell in enumerate(datasets):
                if cell.get('file') or loaded_experiment or is_new_experiment:
                    cell_name = cell['testnum'] or f'Cell {i+1}'
                    default_group = current_group_assignments[i] if (current_group_assignments and i < len(current_group_assignments)) else group_names[0]
                    group = st.radio(
                        f"Assign {cell_name} to group:",
                        [group_names[0], group_names[1], group_names[2], "Exclude"],
                        index=[group_names[0], group_names[1], group_names[2], "Exclude"].index(default_group) if default_group in [group_names[0], group_names[1], group_names[2], "Exclude"] else 0,
                        key=f"main_group_assignment_{i}",
                        horizontal=True
                    )
                    group_assignments.append(group)
            
            show_averages = st.checkbox("Show Group Averages", value=True)
    
    # Update session state with current values
    st.session_state['current_experiment_name'] = experiment_name_input
    st.session_state['current_experiment_date'] = experiment_date_input
    
    # Handle different cell formats for Full Cell projects
    if project_type == "Full Cell":
        cell_format = st.session_state.get('current_cell_format', 'Coin')
        if cell_format == "Coin":
            st.session_state['current_disc_diameter_mm'] = disc_diameter_input
        elif cell_format == "Pouch":
            # For pouch cells, we'll store area instead of diameter
            cathode_length = st.session_state.get('current_cathode_length', 50.0)
            cathode_width = st.session_state.get('current_cathode_width', 50.0)
            num_stacked_cells = st.session_state.get('current_num_stacked_cells', 1)
            # Calculate equivalent diameter for backwards compatibility
            total_area_cm2 = (cathode_length * cathode_width * num_stacked_cells) / 100
            equivalent_diameter = 2 * (total_area_cm2 / np.pi) ** 0.5 * 10  # Convert back to mm
            st.session_state['current_disc_diameter_mm'] = equivalent_diameter
        else:
            # For other formats, use current or default value
            st.session_state['current_disc_diameter_mm'] = disc_diameter_input or current_disc_diameter
    else:
        # For non-Full Cell projects, use traditional disc diameter
        st.session_state['current_disc_diameter_mm'] = disc_diameter_input
    
    st.session_state['current_group_assignments'] = group_assignments
    st.session_state['current_group_names'] = group_names
    
    # Render formulation editor modal if needed
    render_formulation_editor_modal()
    
    # Save/Update experiment button
    st.markdown("---")
    if loaded_experiment:
        if st.button("💾 Update Experiment", type="primary", use_container_width=True):
            # Update the loaded experiment with new values
            experiment_id = loaded_experiment['experiment_id']
            project_id = loaded_experiment['project_id']
            
            # Get project type for efficiency calculation
            project_type = "Full Cell"  # Default
            if project_id:
                project_info = get_project_by_id(project_id)
                if project_info:
                    project_type = project_info[3]  # project_type is the 4th field
            
            # Prepare updated cells data with recalculated gravimetric capacities
            updated_cells_data = []
            existing_cells = experiment_data.get('cells', [])
            
            for i, dataset in enumerate(datasets):
                # Check if this is an existing cell or a new one
                if i < len(existing_cells):
                    # Update existing cell
                    original_cell = existing_cells[i]
                    
                    # Read current input values from session state widgets (they have the latest values)
                    widget_loading = st.session_state.get(f'edit_loading_{i}') or st.session_state.get(f'edit_single_loading_{i}')
                    widget_active = st.session_state.get(f'edit_active_{i}') or st.session_state.get(f'edit_single_active_{i}')
                    widget_formation = st.session_state.get(f'edit_formation_{i}') or st.session_state.get(f'edit_single_formation_{i}')
                    widget_testnum = st.session_state.get(f'edit_testnum_{i}') or st.session_state.get(f'edit_single_testnum_{i}')
                    
                    # Use widget values if available, otherwise use dataset values
                    new_loading = widget_loading if widget_loading is not None else dataset.get('loading', 0)
                    new_active = widget_active if widget_active is not None else dataset.get('active', 0)
                    new_formation = widget_formation if widget_formation is not None else dataset.get('formation_cycles', 4)
                    new_testnum = widget_testnum if widget_testnum is not None else dataset.get('testnum', f'Cell {i+1}')
                    
                    # Check if loading or active material has changed
                    original_loading = original_cell.get('loading', 0)
                    original_active = original_cell.get('active_material', 0)
                    
                    # Recalculate gravimetric capacities if loading or active material changed
                    updated_data_json = original_cell.get('data_json', '{}')
                    if (new_loading != original_loading or new_active != original_active) and updated_data_json:
                        try:
                            # Parse the original DataFrame - fix deprecation warning
                            original_df = pd.read_json(StringIO(updated_data_json))
                            
                            # Recalculate gravimetric capacities
                            updated_df = recalculate_gravimetric_capacities(original_df, new_loading, new_active)
                            
                            # Update the data JSON with recalculated values
                            updated_data_json = updated_df.to_json()
                            
                            # Show before/after comparison of first few values
                            if len(updated_df) > 0:
                                try:
                                    first_qdis_old = original_df['Q Dis (mAh/g)'].iloc[0] if 'Q Dis (mAh/g)' in original_df.columns else 'N/A'
                                    first_qdis_new = updated_df['Q Dis (mAh/g)'].iloc[0] if 'Q Dis (mAh/g)' in updated_df.columns else 'N/A'
                                    st.info(f"🔄 Recalculated gravimetric capacities for {new_testnum}")
                                    st.info(f"   📊 Changes: Loading: {original_loading}→{new_loading}mg, Active: {original_active}→{new_active}%")
                                    if isinstance(first_qdis_old, (int, float)) and isinstance(first_qdis_new, (int, float)):
                                        st.info(f"   📈 First Cycle Q Dis: {first_qdis_old:.2f}→{first_qdis_new:.2f} mAh/g")
                                    else:
                                        st.info(f"   📈 First Cycle Q Dis: {first_qdis_old}→{first_qdis_new} mAh/g")
                                except Exception:
                                    st.info(f"🔄 Recalculated gravimetric capacities for {new_testnum}")
                        except Exception as e:
                            st.warning(f"⚠️ Could not recalculate capacities for {new_testnum}: {str(e)}")
                    
                    updated_cell = original_cell.copy()
                    
                    # Recalculate porosity if loading changed and we have the required data
                    if (new_loading != original_loading and 
                        pressed_thickness and pressed_thickness > 0 and 
                        dataset.get('formulation') and 
                        disc_diameter_input):
                        try:
                            from porosity_calculations import calculate_porosity_from_experiment_data
                            porosity_data = calculate_porosity_from_experiment_data(
                                disc_mass_mg=new_loading,
                                disc_diameter_mm=disc_diameter_input,
                                pressed_thickness_um=pressed_thickness,
                                formulation=dataset['formulation']
                            )
                            updated_cell['porosity'] = porosity_data['porosity']
                            st.info(f"   🔬 Recalculated porosity: {porosity_data['porosity']*100:.1f}%")
                        except Exception as e:
                            st.warning(f"   ⚠️ Could not recalculate porosity for {new_testnum}: {str(e)}")
                    
                    # Read other widget values too
                    widget_electrolyte = st.session_state.get(f'edit_electrolyte_{i}') or st.session_state.get(f'edit_single_electrolyte_{i}')
                    widget_substrate = st.session_state.get(f'edit_substrate_{i}') or st.session_state.get(f'edit_single_substrate_{i}')
                    widget_separator = st.session_state.get(f'edit_separator_{i}') or st.session_state.get(f'edit_single_separator_{i}')
                    
                    updated_cell.update({
                        'loading': new_loading,
                        'active_material': new_active,
                        'formation_cycles': new_formation,
                        'test_number': new_testnum,
                        'cell_name': new_testnum,
                        'electrolyte': widget_electrolyte if widget_electrolyte is not None else dataset.get('electrolyte', '1M LiPF6 1:1:1'),
                        'substrate': widget_substrate if widget_substrate is not None else dataset.get('substrate', 'Copper'),
                        'separator': widget_separator if widget_separator is not None else dataset.get('separator', '25um PP'),
                        'formulation': dataset.get('formulation', []),
                        'data_json': updated_data_json,  # Updated with recalculated values
                        'excluded': dataset.get('excluded', False)  # Add this line
                    })
                    updated_cells_data.append(updated_cell)
                else:
                    # This is a new cell being added to the experiment (e.g., uploading to a duplicate)
                    cell_name = dataset['testnum'] if dataset['testnum'] else f'Cell {i+1}'
                    file_name = dataset['file'].name if dataset.get('file') else f'cell_{i+1}.csv'
                    
                    try:
                        # Process the data to get DataFrame
                        temp_dfs = load_and_preprocess_data([dataset], project_type)
                        if temp_dfs and len(temp_dfs) > 0:
                            df = temp_dfs[0]['df']
                            
                            new_cell = {
                                'cell_name': cell_name,
                                'file_name': file_name,
                                'loading': dataset['loading'],
                                'active_material': dataset['active'],
                                'formation_cycles': dataset['formation_cycles'],
                                'test_number': dataset['testnum'],
                                'electrolyte': dataset.get('electrolyte', '1M LiPF6 1:1:1'),
                                'substrate': dataset.get('substrate', 'Copper'),
                                'separator': dataset.get('separator', '25um PP'),
                                'formulation': dataset.get('formulation', []),
                                'data_json': df.to_json(),
                                'excluded': dataset.get('excluded', False)
                            }
                            
                            # Calculate porosity if we have the required data
                            if (pressed_thickness and pressed_thickness > 0 and 
                                dataset.get('formulation') and 
                                disc_diameter_input):
                                try:
                                    from porosity_calculations import calculate_porosity_from_experiment_data
                                    porosity_data = calculate_porosity_from_experiment_data(
                                        disc_mass_mg=dataset['loading'],
                                        disc_diameter_mm=disc_diameter_input,
                                        pressed_thickness_um=pressed_thickness,
                                        formulation=dataset['formulation']
                                    )
                                    new_cell['porosity'] = porosity_data['porosity']
                                    st.info(f"   🔬 Calculated porosity for {cell_name}: {porosity_data['porosity']*100:.1f}%")
                                except Exception as e:
                                    st.warning(f"   ⚠️ Could not calculate porosity for {cell_name}: {str(e)}")
                            
                            updated_cells_data.append(new_cell)
                            st.info(f"✅ Processed new cell: {cell_name}")
                        else:
                            st.warning(f"⚠️ Failed to process data for {cell_name}. Skipping this cell.")
                    except Exception as e:
                        st.error(f"❌ Error processing {cell_name}: {str(e)}")
                        continue
            
            try:
                # Prepare cell format data for Full Cell projects
                cell_format_data = {}
                if project_type == "Full Cell":
                    cell_format = st.session_state.get('current_cell_format', 'Coin')
                    cell_format_data['cell_format'] = cell_format
                    if cell_format == "Pouch":
                        cell_format_data['cathode_length'] = st.session_state.get('current_cathode_length', 50.0)
                        cell_format_data['cathode_width'] = st.session_state.get('current_cathode_width', 50.0)
                        cell_format_data['num_stacked_cells'] = st.session_state.get('current_num_stacked_cells', 1)
                
                update_experiment(
                    experiment_id=experiment_id,
                    project_id=project_id,
                    experiment_name=experiment_name_input,
                    experiment_date=experiment_date_input,
                    disc_diameter_mm=st.session_state.get('current_disc_diameter_mm', current_disc_diameter),
                    group_assignments=group_assignments,
                    group_names=group_names,
                    cells_data=updated_cells_data,
                    solids_content=solids_content,
                    pressed_thickness=pressed_thickness,
                    experiment_notes=experiment_notes,
                    cell_format_data=cell_format_data
                )
                
                # Update the loaded experiment in session state
                st.session_state['loaded_experiment']['experiment_name'] = experiment_name_input
                st.session_state['loaded_experiment']['experiment_data'].update({
                    'experiment_date': experiment_date_input.isoformat(),
                    'disc_diameter_mm': disc_diameter_input,
                    'group_assignments': group_assignments,
                    'group_names': group_names,
                    'cells': updated_cells_data,
                    'solids_content': solids_content,
                    'pressed_thickness': pressed_thickness,
                    'experiment_notes': experiment_notes
                })
                
                # Clear any cached processed data to force recalculation
                if 'processed_data_cache' in st.session_state:
                    del st.session_state['processed_data_cache']
                if 'cache_key' in st.session_state:
                    del st.session_state['cache_key']
                
                # Reload the experiment from database to get the updated data
                try:
                    updated_experiment_data = get_experiment_data(experiment_id)
                    if updated_experiment_data:
                        # get_experiment_data returns: id, project_id, cell_name, file_name, loading, active_material, 
                        # formation_cycles, test_number, electrolyte, substrate, separator, data_json, created_date
                        # data_json is at index 11
                        st.session_state['loaded_experiment'] = {
                            'experiment_id': experiment_id,
                            'project_id': project_id,
                            'experiment_name': experiment_name_input,
                            'experiment_data': json.loads(updated_experiment_data[11])  # data_json is at index 11
                        }
                        # Set a flag to indicate that calculations have been updated
                        st.session_state['calculations_updated'] = True
                        st.session_state['update_timestamp'] = datetime.now()
                        st.success("✅ Experiment updated successfully! All calculated values have been refreshed.")
                        st.info("🔄 Summary tables, plots, and Master Table will reflect the updated values.")
                    else:
                        st.success("✅ Experiment updated successfully!")
                except Exception as reload_error:
                    st.warning(f"⚠️ Experiment updated but failed to reload data: {str(reload_error)}")
                    st.success("✅ Experiment updated successfully!")
                
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error updating experiment: {str(e)}")
    
    elif is_new_experiment:
        # Save new experiment (only if we have valid data and a selected project)
        valid_datasets = [ds for ds in datasets if not ds.get('excluded', False) and ds.get('file') and ds.get('loading', 0) > 0 and 0 < ds.get('active', 0) <= 100]
        
        if valid_datasets and st.session_state.get('current_project_id'):
            if st.button("💾 Save New Experiment", type="primary", use_container_width=True):
                current_project_id = st.session_state['current_project_id']
                current_project_name = st.session_state['current_project_name']
                
                # Use experiment name from input or generate one
                exp_name = experiment_name_input if experiment_name_input else f"Experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Prepare cells data
                cells_data = []
                for i, ds in enumerate(valid_datasets):
                    cell_name = ds['testnum'] if ds['testnum'] else f'Cell {i+1}'
                    file_name = ds['file'].name if ds['file'] else f'cell_{i+1}.csv'
                    
                    try:
                        # Get project type for efficiency calculation
                        project_type = "Full Cell"  # Default
                        if st.session_state.get('current_project_id'):
                            current_project_id = st.session_state['current_project_id']
                            project_info = get_project_by_id(current_project_id)
                            if project_info:
                                project_type = project_info[3]  # project_type is the 4th field
                        
                        # Process the data to get DataFrame
                        temp_dfs = load_and_preprocess_data([ds], project_type)
                        if temp_dfs and len(temp_dfs) > 0:
                            df = temp_dfs[0]['df']
                            
                            cells_data.append({
                                'cell_name': cell_name,
                                'file_name': file_name,
                                'loading': ds['loading'],
                                'active_material': ds['active'],
                                'formation_cycles': ds['formation_cycles'],
                                'test_number': ds['testnum'],
                                'electrolyte': ds.get('electrolyte', '1M LiPF6 1:1:1'),
                                'substrate': ds.get('substrate', 'Copper'),
                                'separator': ds.get('separator', '25um PP'),
                                'formulation': ds.get('formulation', []),
                                'data_json': df.to_json(),
                                'excluded': ds.get('excluded', False)  # Add this line
                            })
                        else:
                            st.warning(f"⚠️ Failed to process data for {cell_name}. Skipping this cell.")
                    except Exception as e:
                        st.error(f"❌ Error processing {cell_name}: {str(e)}")
                        continue
                
                # Save the experiment
                if cells_data:
                    try:
                        if check_experiment_name_exists(current_project_id, exp_name):
                            experiment_id = get_experiment_by_name(current_project_id, exp_name)
                            # Prepare cell format data for Full Cell projects
                            cell_format_data = {}
                            if project_type == "Full Cell":
                                cell_format = st.session_state.get('current_cell_format', 'Coin')
                                cell_format_data['cell_format'] = cell_format
                                if cell_format == "Pouch":
                                    cell_format_data['cathode_length'] = st.session_state.get('current_cathode_length', 50.0)
                                    cell_format_data['cathode_width'] = st.session_state.get('current_cathode_width', 50.0)
                                    cell_format_data['num_stacked_cells'] = st.session_state.get('current_num_stacked_cells', 1)
                            
                            update_experiment(
                                experiment_id=experiment_id,
                                project_id=current_project_id,
                                experiment_name=exp_name,
                                experiment_date=experiment_date_input,
                                disc_diameter_mm=st.session_state.get('current_disc_diameter_mm', 15),
                                group_assignments=group_assignments,
                                group_names=group_names,
                                cells_data=cells_data,
                                solids_content=solids_content,
                                pressed_thickness=pressed_thickness,
                                experiment_notes=experiment_notes,
                                cell_format_data=cell_format_data
                            )
                            st.success(f"🔄 Updated experiment '{exp_name}' in project '{current_project_name}'!")
                        else:
                            # Prepare cell format data for Full Cell projects
                            cell_format_data = {}
                            if project_type == "Full Cell":
                                cell_format = st.session_state.get('current_cell_format', 'Coin')
                                cell_format_data['cell_format'] = cell_format
                                if cell_format == "Pouch":
                                    cell_format_data['cathode_length'] = st.session_state.get('current_cathode_length', 50.0)
                                    cell_format_data['cathode_width'] = st.session_state.get('current_cathode_width', 50.0)
                                    cell_format_data['num_stacked_cells'] = st.session_state.get('current_num_stacked_cells', 1)
                            
                            save_experiment(
                                project_id=current_project_id,
                                experiment_name=exp_name,
                                experiment_date=experiment_date_input,
                                disc_diameter_mm=st.session_state.get('current_disc_diameter_mm', 15),
                                group_assignments=group_assignments,
                                group_names=group_names,
                                cells_data=cells_data,
                                solids_content=solids_content,
                                pressed_thickness=pressed_thickness,
                                experiment_notes=experiment_notes,
                                cell_format_data=cell_format_data
                            )
                            st.success(f"✅ Saved experiment '{exp_name}' with {len(cells_data)} cells in project '{current_project_name}'!")
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to save experiment: {str(e)}")
                else:
                    st.error("❌ No valid cell data to save. Please check your files and try again.")
        
        elif valid_datasets and not st.session_state.get('current_project_id'):
            st.warning("⚠️ Please select a project in the sidebar before saving the experiment.")
        elif not valid_datasets:
            st.info("ℹ️ Upload cell data files and enter valid parameters to save an experiment.")

# --- Data Preprocessing Section ---
# This section is now handled in the Cell Inputs tab
# Data processing now happens in the Cell Inputs tab

# Check if we have loaded experiment data to display
loaded_experiment = st.session_state.get('loaded_experiment')
if loaded_experiment:
    st.markdown("---")
    st.markdown(f"### 📊 Loaded Experiment: {loaded_experiment['experiment_name']}")
    
    # Convert saved JSON data back to DataFrames
    loaded_dfs = []
    experiment_data = loaded_experiment['experiment_data']
    cells_data = experiment_data.get('cells', [])
    
    for i, cell_data in enumerate(cells_data):
        cell_name = cell_data.get('cell_name', 'Unknown')
        try:
            # Fix the deprecation warning by using StringIO
            df = pd.read_json(StringIO(cell_data['data_json']))
            
            # Get project type for efficiency recalculation
            project_type = "Full Cell"  # Default
            if st.session_state.get('current_project_id'):
                current_project_id = st.session_state['current_project_id']
                project_info = get_project_by_id(current_project_id)
                if project_info:
                    project_type = project_info[3]  # project_type is the 4th field
            
            # Check if loading or active material have been changed in session state
            # Check both multi-cell and single-cell widget keys
            widget_loading = st.session_state.get(f'edit_loading_{i}') or st.session_state.get(f'edit_single_loading_{i}')
            widget_active = st.session_state.get(f'edit_active_{i}') or st.session_state.get(f'edit_single_active_{i}')
            
            db_loading = cell_data.get('loading', 0)
            db_active = cell_data.get('active_material', 0)
            
            # Use widget values if available, otherwise use database values
            current_loading = widget_loading if widget_loading is not None else db_loading
            current_active = widget_active if widget_active is not None else db_active
            
            # Recalculate gravimetric capacities if loading or active material changed
            if (current_loading != db_loading or current_active != db_active):
                try:
                    df = recalculate_gravimetric_capacities(df, current_loading, current_active)
                except Exception as e:
                    print(f"Error recalculating gravimetric capacities for {cell_name}: {e}")
            
            # Recalculate efficiency based on project type for all projects (was previously only for Anode)
            if 'Q charge (mA.h)' in df.columns and 'Q discharge (mA.h)' in df.columns:
                # Recalculate efficiency for all project types to ensure correctness
                df['Efficiency (-)'] = calculate_efficiency_based_on_project_type(
                    df['Q charge (mA.h)'], 
                    df['Q discharge (mA.h)'], 
                    project_type
                ) / 100  # Convert to decimal for consistency
            
            # Extract electrode data from experiment
            pressed_thickness = experiment_data.get('pressed_thickness', None)
            solids_content = experiment_data.get('solids_content', None)
            porosity = cell_data.get('porosity', None)
            
            # If porosity is not available in cell data, try to calculate it
            if porosity is None or porosity <= 0:
                try:
                    from porosity_calculations import calculate_porosity_from_experiment_data
                    if (cell_data.get('loading') and 
                        experiment_data.get('disc_diameter_mm') and 
                        pressed_thickness and 
                        cell_data.get('formulation')):
                        
                        porosity_data = calculate_porosity_from_experiment_data(
                            disc_mass_mg=cell_data['loading'],
                            disc_diameter_mm=experiment_data['disc_diameter_mm'],
                            pressed_thickness_um=pressed_thickness,
                            formulation=cell_data['formulation']
                        )
                        porosity = porosity_data['porosity']
                except Exception as e:
                    print(f"Error calculating porosity for {cell_name}: {e}")
                    porosity = None
            
            # Get formulation data from cell_data
            formulation = cell_data.get('formulation', [])
            
            loaded_dfs.append({
                'df': df,
                'testnum': cell_data.get('test_number', cell_data.get('cell_name', 'Unknown')),
                'loading': current_loading,  # Use current loading (may be updated from widget)
                'active': current_active,  # Use current active material (may be updated from widget)
                'formation_cycles': cell_data.get('formation_cycles'),
                'project_type': project_type,
                'excluded': cell_data.get('excluded', False),
                # Add electrode data for export functionality
                'pressed_thickness': pressed_thickness,
                'solids_content': solids_content,
                'porosity': porosity,
                # Add formulation data for export functionality
                'formulation': formulation
            })
            
            # Debug info for electrode data loading (can be removed after testing)
            if pressed_thickness or porosity or solids_content:
                print(f"DEBUG: Loaded electrode data for {cell_name}:")
                print(f"  - Pressed thickness: {pressed_thickness}")
                print(f"  - Solids content: {solids_content}")
                print(f"  - Porosity: {porosity}")
        except Exception as e:
            st.error(f"Error loading data for {cell_name}: {str(e)}")
    
    if loaded_dfs:
        # Use loaded data for analysis
        dfs = loaded_dfs
        ready = True
        st.success(f"✅ Loaded {len(loaded_dfs)} cell(s) from saved experiment")
        
        # Update datasets in session state to reflect any widget changes
        # This ensures Summary tables and other components also show updated values
        for i, df_data in enumerate(loaded_dfs):
            if i < len(st.session_state.get('datasets', [])):
                st.session_state['datasets'][i]['loading'] = df_data['loading']
                st.session_state['datasets'][i]['active'] = df_data['active']
        
        # Display experiment metadata
        if experiment_data.get('experiment_date'):
            st.info(f"📅 Experiment Date: {experiment_data['experiment_date']}")
        if experiment_data.get('disc_diameter_mm'):
            st.info(f"🔘 Disc Diameter: {experiment_data['disc_diameter_mm']} mm")
        
        # LLM Summary Section
        experiment_id = loaded_experiment.get('experiment_id')
        with st.expander("🤖 Generate LLM-Ready Summary", expanded=False):
            st.markdown("""
            Generate a token-efficient summary of this experiment optimized for LLM analysis.
            Includes experiment parameters, cell performance metrics, curve characteristics, 
            and a capacity vs cycle plot image.
            """)
            
            if st.button("📋 Generate Summary", type="primary", use_container_width=True, 
                         key=f'llm_summary_btn_{experiment_id}'):
                with st.spinner("Generating summary and plot..."):
                    try:
                        summary_text, plot_image_base64, stats = generate_experiment_summary(experiment_id)
                        
                        # Display statistics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Estimated Tokens", f"{stats.get('token_estimate', 0):,}")
                        with col2:
                            st.metric("Characters", f"{stats.get('char_count', 0):,}")
                        with col3:
                            st.metric("Lines", f"{stats.get('line_count', 0):,}")
                        with col4:
                            st.metric("Cells", f"{stats.get('num_cells', 0)}")
                        
                        # Display plot image if available
                        if plot_image_base64:
                            st.markdown("### Capacity vs Cycle Plot")
                            st.markdown("*This plot image can be included in your LLM prompt for visual analysis.*")
                            # Decode and display image
                            import base64
                            from io import BytesIO
                            from PIL import Image
                            img_data = base64.b64decode(plot_image_base64)
                            img = Image.open(BytesIO(img_data))
                            st.image(img, caption=f"{loaded_experiment['experiment_name']} - Capacity vs Cycle", 
                                   use_container_width=True)
                            
                            # Download button for plot
                            st.download_button(
                                label="📥 Download Plot Image",
                                data=img_data,
                                file_name=f"{loaded_experiment['experiment_name']}_capacity_plot.png",
                                mime="image/png",
                                key=f'download_plot_{experiment_id}'
                            )
                        
                        # Display summary text in text area for easy copying
                        st.markdown("### Summary Text (Copy for LLM)")
                        st.text_area(
                            "Experiment Summary",
                            value=summary_text,
                            height=400,
                            key=f'llm_summary_textarea_{experiment_id}',
                            help="Copy this text and paste it into your LLM prompt for analysis. Include the plot image above if using a vision model."
                        )
                        
                        # Copy button using streamlit's clipboard functionality
                        st.code(summary_text, language=None)
                        
                        # Save to session state for later viewing (use different key than widget)
                        st.session_state[f'llm_summary_text_{experiment_id}'] = summary_text
                        st.session_state[f'llm_summary_plot_{experiment_id}'] = plot_image_base64
                        st.session_state[f'llm_summary_stats_{experiment_id}'] = stats
                        
                        st.success("✅ Summary generated! Copy the text above to use with your LLM.")
                        
                    except Exception as e:
                        st.error(f"Error generating summary: {str(e)}")
                        st.exception(e)
            
            # Show cached summary if available
            cached_summary = st.session_state.get(f'llm_summary_text_{experiment_id}')
            if cached_summary:
                if st.button("📄 View Last Summary", key=f'view_summary_{experiment_id}'):
                    cached_stats = st.session_state.get(f'llm_summary_stats_{experiment_id}', {})
                    cached_plot = st.session_state.get(f'llm_summary_plot_{experiment_id}')
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Estimated Tokens", f"{cached_stats.get('token_estimate', 0):,}")
                    with col2:
                        st.metric("Characters", f"{cached_stats.get('char_count', 0):,}")
                    with col3:
                        st.metric("Lines", f"{cached_stats.get('line_count', 0):,}")
                    with col4:
                        st.metric("Cells", f"{cached_stats.get('num_cells', 0)}")
                    
                    if cached_plot:
                        st.markdown("### Capacity vs Cycle Plot")
                        import base64
                        from io import BytesIO
                        from PIL import Image
                        img_data = base64.b64decode(cached_plot)
                        img = Image.open(BytesIO(img_data))
                        st.image(img, caption=f"{loaded_experiment['experiment_name']} - Capacity vs Cycle", 
                               use_container_width=True)
                    
                    st.text_area(
                        "Experiment Summary",
                        value=cached_summary,
                        height=400,
                        key=f'llm_summary_view_textarea_{experiment_id}'
                    )
                    st.code(cached_summary, language=None)
    else:
        st.error("❌ Failed to load experiment data")
        ready = False

# Determine if we have data ready for analysis
if loaded_experiment:
    ready = len(loaded_dfs) > 0
else:
    # For new experiments, check if we have valid uploaded data
    datasets = st.session_state.get('datasets', [])
    # Only include datasets with a real uploaded file for processing
    valid_datasets = []
    for ds in datasets:
        file_obj = ds.get('file')
        if (file_obj and 
            hasattr(file_obj, 'read') and 
            hasattr(file_obj, 'name') and 
            hasattr(file_obj, 'type') and
            ds.get('loading', 0) > 0 and 
            0 < ds.get('active', 0) <= 100):
            # Additional check: ensure it's a real Streamlit UploadedFile, not a mock object
            try:
                # Try to access the file's size property (real uploaded files have this)
                if hasattr(file_obj, 'size') and file_obj.size is not None and file_obj.size > 0:
                    valid_datasets.append(ds)
            except (AttributeError, TypeError):
                # Skip files that don't have proper size attribute or other issues
                continue
    
    # Process uploaded data if we have valid datasets
    if valid_datasets:
        # Create a cache key based on file names and parameters
        cache_key = []
        for ds in valid_datasets:
            if ds.get('file'):
                file_info = f"{ds['file'].name}_{ds['loading']}_{ds['active']}_{ds['formation_cycles']}"
                cache_key.append(file_info)
        cache_key_str = "_".join(cache_key)
        
        # Check if we have cached processed data
        if ('processed_data_cache' in st.session_state and 
            st.session_state.get('cache_key') == cache_key_str):
            dfs = st.session_state['processed_data_cache']
        else:
            # Process data and cache it
            # Final safety check before processing
            safe_datasets = []
            for ds in valid_datasets:
                try:
                    # Test that we can actually read from the file
                    file_obj = ds['file']
                    current_pos = file_obj.tell() if hasattr(file_obj, 'tell') else 0
                    file_obj.seek(0)
                    # Try to read a small sample to verify it's readable
                    sample = file_obj.read(10)
                    file_obj.seek(current_pos)  # Reset position
                    if sample:  # File has content
                        safe_datasets.append(ds)
                except Exception as e:
                    st.warning(f"⚠️ Skipping invalid file: {ds.get('file', {}).get('name', 'Unknown')} - {str(e)}")
                    continue
            
            if safe_datasets:
                # Get project type for efficiency calculation
                project_type = "Full Cell"  # Default
                if st.session_state.get('current_project_id'):
                    current_project_id = st.session_state['current_project_id']
                    project_info = get_project_by_id(current_project_id)
                    if project_info:
                        project_type = project_info[3]  # project_type is the 4th field
                
                dfs = load_and_preprocess_data(safe_datasets, project_type)
                # After loading and preprocessing, re-attach the latest formation_cycles to each dfs entry
                for i, d in enumerate(dfs):
                    if i < len(safe_datasets):
                        d['formation_cycles'] = safe_datasets[i]['formation_cycles']
                
                # Display file type information
                file_types = [d.get('file_type', 'Unknown') for d in dfs]
                biologic_count = file_types.count('biologic_csv')
                neware_count = file_types.count('neware_xlsx')
                
                if biologic_count > 0 and neware_count > 0:
                    st.info(f"📁 Processed {len(dfs)} files: {biologic_count} Biologic CSV file(s) and {neware_count} Neware XLSX file(s)")
                elif biologic_count > 0:
                    st.info(f"📁 Processed {biologic_count} Biologic CSV file(s)")
                elif neware_count > 0:
                    st.info(f"📁 Processed {neware_count} Neware XLSX file(s)")
            else:
                dfs = []
                st.error("❌ No valid files found for processing.")
            
            # Cache the processed data
            st.session_state['processed_data_cache'] = dfs
            st.session_state['cache_key'] = cache_key_str
        
        ready = len(dfs) > 0
    else:
        ready = False

if ready:
    # Use values from Cell Inputs tab
    disc_diameter_mm = st.session_state.get('current_disc_diameter_mm', 15)
    experiment_name = st.session_state.get('current_experiment_name', '')
    group_assignments = st.session_state.get('current_group_assignments')
    group_names = st.session_state.get('current_group_names', ["Group A", "Group B", "Group C"])
    enable_grouping = bool(group_assignments)
    show_averages = enable_grouping
    datasets = st.session_state.get('datasets', [])
    disc_area_cm2 = np.pi * (disc_diameter_mm / 2 / 10) ** 2
    
    # Filter out excluded cells from dfs
    if loaded_experiment:
        dfs = [d for d in loaded_dfs if not d.get('excluded', False)]
    else:
        # For new experiments, we need to filter the processed dfs, not the raw valid_datasets
        # The processed dfs are already cached in st.session_state['processed_data_cache']
        processed_dfs = st.session_state.get('processed_data_cache', [])
        valid_datasets = st.session_state.get('datasets', [])
        
        # Create a mapping of file names to excluded status
        excluded_files = {}
        for ds in valid_datasets:
            if ds.get('file') and hasattr(ds['file'], 'name'):
                excluded_files[ds['file'].name] = ds.get('excluded', False)
        
        # Filter processed dfs based on excluded status
        dfs = []
        for d in processed_dfs:
            # Check if this processed data corresponds to an excluded file
            file_name = d.get('file_name', '')
            if not excluded_files.get(file_name, False):
                dfs.append(d)

    # --- Group Average Curve Calculation for Plotting ---
    group_curves = []
    if enable_grouping and group_assignments is not None:
        group_dfs = [[], [], []]
        for idx, name in enumerate(group_names):
            group_dfs[idx] = [df for df, g in zip(dfs, group_assignments) if g == name]
        def compute_group_avg_curve(group_dfs):
            if not group_dfs:
                return None, None, None, None
            dfs_trimmed = [d['df'] for d in group_dfs]
            x_col = dfs_trimmed[0].columns[0]
            common_cycles = set(dfs_trimmed[0][x_col])
            for df in dfs_trimmed[1:]:
                common_cycles = common_cycles & set(df[x_col])
            common_cycles = sorted(list(common_cycles))
            if not common_cycles:
                return None, None, None, None
            avg_qdis = []
            avg_qchg = []
            avg_eff = []
            for cycle in common_cycles:
                qdis_vals = []
                qchg_vals = []
                eff_vals = []
                for df in dfs_trimmed:
                    row = df[df[x_col] == cycle]
                    if not row.empty:
                        if 'Q Dis (mAh/g)' in row:
                            qdis_vals.append(row['Q Dis (mAh/g)'].values[0])
                        if 'Q Chg (mAh/g)' in row:
                            qchg_vals.append(row['Q Chg (mAh/g)'].values[0])
                        if 'Efficiency (-)' in row and not pd.isnull(row['Efficiency (-)'].values[0]):
                            eff_vals.append(row['Efficiency (-)'].values[0] * 100)
                avg_qdis.append(sum(qdis_vals)/len(qdis_vals) if qdis_vals else None)
                avg_qchg.append(sum(qchg_vals)/len(qchg_vals) if qchg_vals else None)
                avg_eff.append(sum(eff_vals)/len(eff_vals) if eff_vals else None)
            return common_cycles, avg_qdis, avg_qchg, avg_eff
        group_curves = [compute_group_avg_curve(group_dfs[idx]) for idx in range(3)]
    # --- Main Tabs Content ---
    with tab1:
        # Get formation cycles for reference cycle calculation
        formation_cycles = st.session_state.get('current_formation_cycles', 4)
        if ready and datasets:
            # Try to get formation cycles from the first dataset
            if 'formation_cycles' in datasets[0]:
                formation_cycles = datasets[0]['formation_cycles']
        
        # Plot Controls
        show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers, hide_legend, group_plot_toggles, cycle_filter, y_axis_limits = render_toggle_section(dfs, enable_grouping=enable_grouping)
        
        # Color customization UI
        custom_colors = render_experiment_color_customization(
            dfs, experiment_name, show_average_performance, 
            enable_grouping, group_names
        )
        
        # Combined plot toggle
        show_combined_plot = st.checkbox(
            "Show Capacity Retention on Secondary Y-Axis",
            value=False,
            key="show_combined_capacity_retention",
            help="Combine Specific Capacity and Capacity Retention into a single graph with dual Y-axes."
        )
        
        # Conditionally show combined plot or separate plots based on toggle
        if show_combined_plot and ready and dfs:
            # Get reference cycle settings
            all_cycles = []
            for d in dfs:
                try:
                    df = d['df']
                    if not df.empty:
                        cycles = df[df.columns[0]].tolist()
                        all_cycles.extend(cycles)
                except:
                    pass
            
            if all_cycles:
                min_cycle = min(all_cycles)
                max_cycle = max(all_cycles)
                
                # Get maximum data length for formation cycles skip limit
                max_data_length = 0
                for d in dfs:
                    try:
                        df = d['df']
                        if not df.empty:
                            max_data_length = max(max_data_length, len(df))
                    except:
                        pass
                
                # Combined Plot Configuration
                config_col1, config_col2 = st.columns([1, 1])
                
                with config_col1:
                    max_skip = max(0, max_data_length - 1) if max_data_length > 0 else 0
                    formation_cycles_skip = st.number_input(
                        "Formation Cycles to Skip",
                        min_value=0,
                        max_value=max_skip,
                        value=0,
                        step=1,
                        key="combined_formation_cycles_skip",
                        help=f"Number of initial cycles to skip when determining the 100% reference capacity."
                    )
                
                with config_col2:
                    retention_threshold = st.slider(
                        "Retention Threshold (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=80.0,
                        step=5.0,
                        key="combined_retention_threshold",
                        help="Set the threshold line for capacity retention analysis."
                    )
                
                baseline_col1, baseline_col2 = st.columns(2)
                with baseline_col1:
                    show_baseline_100 = st.checkbox('Show 100% baseline', value=True, key='combined_show_baseline_100')
                with baseline_col2:
                    show_baseline_80 = st.checkbox(f'Show {retention_threshold:.0f}% threshold', value=True, key='combined_show_baseline_80')
                
                # Calculate reference cycle based on formation cycles skip
                # The reference cycle index will be formation_cycles_skip (0-based index)
                # But we need the actual cycle number from the data
                reference_cycle_index = formation_cycles_skip
                
                # Get the actual cycle number from the first visible cell
                reference_cycle = None
                for d in dfs:
                    try:
                        df = d['df']
                        if not df.empty and len(df) > reference_cycle_index:
                            cycle_col = df.columns[0]
                            reference_cycle = int(df.iloc[reference_cycle_index][cycle_col])
                            break
                    except:
                        pass
                
                # Fallback to default if not found
                if reference_cycle is None:
                    default_ref_cycle = formation_cycles + 1
                    if default_ref_cycle < min_cycle:
                        default_ref_cycle = min_cycle
                    elif default_ref_cycle > max_cycle:
                        default_ref_cycle = max_cycle
                    reference_cycle = int(default_ref_cycle)
                
                y_axis_preset = st.selectbox(
                    "Retention Y-Axis Range",
                    options=["Auto-scale", "Full Range (0-110%)", "Focused View (70-110%)", "Standard View (50-110%)", "Custom Range"],
                    index=0,
                    key="combined_y_axis_preset"
                )
                
                # Set Y-axis range based on preset
                if y_axis_preset == "Auto-scale":
                    y_axis_min, y_axis_max = None, None  # Will be calculated from capacity range
                elif y_axis_preset == "Full Range (0-110%)":
                    y_axis_min, y_axis_max = 0.0, 110.0
                elif y_axis_preset == "Focused View (70-110%)":
                    y_axis_min, y_axis_max = 70.0, 110.0
                elif y_axis_preset == "Standard View (50-110%)":
                    y_axis_min, y_axis_max = 50.0, 110.0
                else:
                    custom_col1, custom_col2 = st.columns(2)
                    with custom_col1:
                        y_axis_min = st.number_input("Min Y (%)", min_value=0.0, max_value=100.0, value=0.0, step=5.0, key="combined_retention_y_axis_min")
                    with custom_col2:
                        y_axis_max = st.number_input("Max Y (%)", min_value=50.0, max_value=200.0, value=110.0, step=5.0, key="combined_retention_y_axis_max")
                
                # Generate combined plot
                combined_fig = plot_combined_capacity_retention_graph(
                    dfs, show_lines, reference_cycle, formation_cycles, remove_last_cycle,
                    show_graph_title, experiment_name, show_average_performance,
                    avg_line_toggles, remove_markers, hide_legend,
                    retention_threshold=retention_threshold,
                    y_axis_min=y_axis_min,
                    y_axis_max=y_axis_max,
                    show_baseline_line=show_baseline_100,
                    show_threshold_line=show_baseline_80,
                    cycle_filter=cycle_filter,
                    custom_colors=custom_colors,
                    capacity_y_axis_limits=y_axis_limits,
                    formation_cycles_skip=formation_cycles_skip
                )
                st.pyplot(combined_fig)
                
                st.caption(f"Combined view: Specific Capacity (left Y-axis) and Capacity Retention (right Y-axis). Reference: cycle {reference_cycle}.")
            else:
                st.warning("No cycle data available. Please upload data files first.")
        else:
            # Separate plots (when combined toggle is disabled)
            fig = plot_capacity_graph(
                dfs, show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, experiment_name,
                show_average_performance, avg_line_toggles, remove_markers, hide_legend,
                group_a_curve=(group_curves[0][0], group_curves[0][1]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][1] and group_plot_toggles.get("Group Q Dis", False) else None,
                group_b_curve=(group_curves[1][0], group_curves[1][1]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][1] and group_plot_toggles.get("Group Q Dis", False) else None,
                group_c_curve=(group_curves[2][0], group_curves[2][1]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][1] and group_plot_toggles.get("Group Q Dis", False) else None,
                group_a_qchg=(group_curves[0][0], group_curves[0][2]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][2] and group_plot_toggles.get("Group Q Chg", False) else None,
                group_b_qchg=(group_curves[1][0], group_curves[1][2]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][2] and group_plot_toggles.get("Group Q Chg", False) else None,
                group_c_qchg=(group_curves[2][0], group_curves[2][2]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][2] and group_plot_toggles.get("Group Q Chg", False) else None,
                group_a_eff=(group_curves[0][0], group_curves[0][3]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][3] and group_plot_toggles.get("Group Efficiency", False) else None,
                group_b_eff=(group_curves[1][0], group_curves[1][3]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][3] and group_plot_toggles.get("Group Efficiency", False) else None,
                group_c_eff=(group_curves[2][0], group_curves[2][3]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][3] and group_plot_toggles.get("Group Efficiency", False) else None,
                group_names=group_names,
                cycle_filter=cycle_filter,
                custom_colors=custom_colors,
                y_axis_limits=y_axis_limits
            )
            st.pyplot(fig)
            
            if ready and dfs:
                # Get available cycles from the data to determine valid range for reference cycle
                all_cycles = []
                for d in dfs:
                    try:
                        df = d['df']
                        if not df.empty:
                            cycles = df[df.columns[0]].tolist()
                            all_cycles.extend(cycles)
                    except:
                        pass
                
                if all_cycles:
                    min_cycle = min(all_cycles)
                    max_cycle = max(all_cycles)
                    default_ref_cycle = formation_cycles + 1
                    
                    # Ensure default reference cycle is within valid range
                    if default_ref_cycle < min_cycle:
                        default_ref_cycle = min_cycle
                    elif default_ref_cycle > max_cycle:
                        default_ref_cycle = max_cycle
                    
                    # Reference cycle input controls
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        reference_cycle = st.number_input(
                            "Reference Cycle (100% baseline)",
                            min_value=int(min_cycle),
                            max_value=int(max_cycle),
                            value=int(default_ref_cycle),
                            step=1,
                            key="reference_cycle",
                            help=f"Select which cycle to use as the 100% reference point."
                        )
                    
                    with col2:
                        st.metric("Formation Cycles", formation_cycles)
                    
                    with col3:
                        st.metric("Available Cycles", f"{int(min_cycle)} - {int(max_cycle)}")
                    
                    # Retention plot controls
                    control_col1, control_col2, control_col3 = st.columns([1, 1, 1])
                    
                    with control_col1:
                        retention_threshold = st.slider(
                            "Retention Threshold (%)",
                            min_value=0.0,
                            max_value=100.0,
                            value=80.0,
                            step=5.0,
                            key="retention_threshold"
                        )
                    
                    with control_col2:
                        y_axis_preset = st.selectbox(
                            "Y-Axis Range",
                            options=["Full Range (0-110%)", "Focused View (70-110%)", "Standard View (50-110%)", "Custom Range"],
                            index=0,
                            key="y_axis_preset"
                        )
                    
                    with control_col3:
                        if y_axis_preset == "Custom Range":
                            custom_min = st.number_input("Min Y (%)", min_value=0.0, max_value=100.0, value=st.session_state.get('retention_y_axis_min', 0.0), step=5.0, key="retention_y_axis_min")
                            custom_max = st.number_input("Max Y (%)", min_value=50.0, max_value=200.0, value=st.session_state.get('retention_y_axis_max', 110.0), step=5.0, key="retention_y_axis_max")
                            y_axis_min, y_axis_max = custom_min, custom_max
                        else:
                            if y_axis_preset == "Full Range (0-110%)":
                                y_axis_min, y_axis_max = 0.0, 110.0
                            elif y_axis_preset == "Focused View (70-110%)":
                                y_axis_min, y_axis_max = 70.0, 110.0
                            elif y_axis_preset == "Standard View (50-110%)":
                                y_axis_min, y_axis_max = 50.0, 110.0
                            st.metric("Y-Axis Range", f"{y_axis_min:.0f}% - {y_axis_max:.0f}%")
                    
                    # Retention plot specific options
                        retention_col1, retention_col2 = st.columns(2)
                        with retention_col1:
                            show_baseline_line = st.checkbox(
                            'Show baseline (100%)',
                                value=True,
                            key='retention_baseline'
                            )
                        with retention_col2:
                            show_threshold_line = st.checkbox(
                            f'Show threshold ({retention_threshold:.0f}%)',
                                value=True,
                            key='retention_threshold_line'
                            )
                    
                    # Generate capacity retention plot using unified settings
                    retention_fig = plot_capacity_retention_graph(
                        dfs, show_lines, reference_cycle, formation_cycles, remove_last_cycle, 
                        show_graph_title, experiment_name, show_average_performance, 
                        avg_line_toggles, remove_markers, hide_legend,
                        group_a_curve=None,  # Can be extended later for group retention
                        group_b_curve=None,
                        group_c_curve=None,
                        group_names=group_names,
                        retention_threshold=retention_threshold,
                        y_axis_min=y_axis_min,
                        y_axis_max=y_axis_max,
                        show_baseline_line=show_baseline_line,
                        show_threshold_line=show_threshold_line,
                        cycle_filter=cycle_filter,
                        custom_colors=custom_colors
                    )
                    st.pyplot(retention_fig)
                else:
                    st.warning("No cycle data available. Please upload data files first.")
            else:
                st.info("Upload and process data files to see capacity retention analysis.")
        
        # Summary Table Section at the bottom
        if ready and dfs:
            st.markdown("---")
            st.subheader("Summary Statistics")
            
            # Show update notification if calculations were recently updated
            if st.session_state.get('calculations_updated', False):
                update_time = st.session_state.get('update_timestamp')
                if update_time:
                    time_str = update_time.strftime("%H:%M:%S")
                    st.success(f"Values updated at {time_str} - All calculations have been refreshed!")
                    st.session_state['calculations_updated'] = False
            
            # Add toggle for showing average column
            show_average_col = False
            if len(dfs) > 1:
                show_average_col = st.toggle("Show average column", value=True, key="show_average_col_toggle")
            
            # Display summary statistics table
            from ui_components import display_summary_stats
            display_summary_stats(dfs, disc_area_cm2, show_average_col, group_assignments, group_names)
    with tab2:
        st.header("📤 Export & Download")
        st.markdown("---")
        
        # Only show export options if data is ready
        if ready:
            st.subheader("🔧 PowerPoint Export Options")
            st.markdown("*Configure what to include in your PowerPoint slide*")
            
            # Toggle Controls for Slide Content
            with st.expander("📋 Slide Content Selection", expanded=True):
                content_col1, content_col2, content_col3 = st.columns(3)
                
                with content_col1:
                    st.markdown("**📊 Data & Tables**")
                    include_summary_table = st.checkbox(
                        "Main summary table",
                        value=True,
                        key="export_summary_table",
                        help="Include the main summary table with key metrics"
                    )
                    
                with content_col2:
                    st.markdown("**📈 Plots**")
                    include_main_plot = st.checkbox(
                        "Capacity comparison plot",
                        value=True,
                        key="export_main_plot",
                        help="Include the main capacity vs cycle plot"
                    )
                    include_retention_plot = st.checkbox(
                        "Capacity retention plot",
                        value=True,
                        key="export_retention_plot",
                        help="Include the capacity retention plot"
                    )
                    
                with content_col3:
                    st.markdown("**📝 Additional Data**")
                    include_notes = st.checkbox(
                        "Experiment notes",
                        value=True,
                        key="export_notes",
                        help="Include experiment notes from the Cell Input page"
                    )
                    include_electrode_data = st.checkbox(
                        "Electrode data group",
                        value=True,
                        key="export_electrode_group",
                        help="Include electrode-related data"
                    )
                    include_formulation = st.checkbox(
                        "Formulation table",
                        value=True,
                        key="export_formulation",
                        help="Include formulation component table"
                    )
            
            # Electrode Data Sub-toggles
            if include_electrode_data:
                with st.expander("🔬 Electrode Data Details", expanded=True):
                    electrode_col1, electrode_col2, electrode_col3 = st.columns(3)
                    
                    with electrode_col1:
                        include_porosity = st.checkbox(
                            "Porosity",
                            value=True,
                            key="export_porosity",
                            help="Include porosity calculations"
                        )
                    
                    with electrode_col2:
                        include_thickness = st.checkbox(
                            "Pressed electrode thickness",
                            value=True,
                            key="export_thickness",
                            help="Include electrode thickness data"
                        )
                    
                    with electrode_col3:
                        include_solids_content = st.checkbox(
                            "Solids content",
                            value=True,
                            key="export_solids_content",
                            help="Include solids content percentage"
                        )
            else:
                include_porosity = False
                include_thickness = False
                include_solids_content = False
            
            # Get stored experiment notes from the current experiment
            stored_experiment_notes = ""
            if include_notes and dfs:
                # Get experiment notes from the first dataset (they should be the same for all cells in an experiment)
                if 'experiment_notes' in dfs[0]:
                    stored_experiment_notes = dfs[0]['experiment_notes'] or ""
                else:
                    # Try to get from session state as fallback
                    stored_experiment_notes = st.session_state.get('experiment_notes', "")
            
            st.markdown("---")
            
            # Note: Retention plot settings are automatically synchronized with the Plots tab
            if include_retention_plot:
                st.info("ℹ️ **Retention plot settings are automatically synchronized with the Plots tab**")
                st.info("Configure retention plot parameters in the Plots tab, and they will be used in the export.")
            
            st.markdown("---")
            
            # Generate Preview Summary
            st.subheader("📋 Slide Content Preview")
            
            content_items = []
            if include_summary_table:
                content_items.append("✅ Main summary table")
            if include_main_plot:
                content_items.append("✅ Capacity comparison plot")
            if include_retention_plot:
                # Get current settings from session state
                current_ref_cycle = st.session_state.get('reference_cycle', 5)
                current_threshold = st.session_state.get('retention_threshold', 80.0)
                content_items.append(f"✅ Capacity retention plot (ref: cycle {current_ref_cycle}, threshold: {current_threshold}%)")
            if include_notes and stored_experiment_notes.strip():
                content_items.append("✅ Experiment notes (from Cell Input page)")
            if include_electrode_data:
                electrode_items = []
                if include_porosity:
                    electrode_items.append("Porosity")
                if include_thickness:
                    electrode_items.append("Thickness")
                if include_solids_content:
                    electrode_items.append("Solids Content")
                if electrode_items:
                    content_items.append(f"✅ Electrode data: {', '.join(electrode_items)}")
            if include_formulation:
                content_items.append("✅ Formulation table")
                # Debug: Check formulation data availability
                formulation_data = None
                if dfs and len(dfs) > 0:
                    formulation_data = dfs[0].get('formulation', [])
                if not formulation_data or len(formulation_data) == 0:
                    loaded_experiment = st.session_state.get('loaded_experiment')
                    if loaded_experiment:
                        experiment_data = loaded_experiment.get('experiment_data', {})
                        cells_data = experiment_data.get('cells', [])
                        if cells_data and len(cells_data) > 0:
                            formulation_data = cells_data[0].get('formulation', [])
                
                # Enhanced debug output
                with st.expander("🔍 Debug: Formulation Data", expanded=False):
                    st.write(f"**Formulation data length:** {len(formulation_data) if formulation_data else 0}")
                    if formulation_data:
                        st.write(f"**Data type:** {type(formulation_data)}")
                        st.write(f"**First item:** {formulation_data[0] if len(formulation_data) > 0 else 'N/A'}")
                        st.write(f"**Full data:** {formulation_data}")
                        # Show keys if it's a dict
                        if formulation_data and len(formulation_data) > 0 and isinstance(formulation_data[0], dict):
                            st.write(f"**Keys in first item:** {list(formulation_data[0].keys())}")
                    else:
                        st.warning("⚠️ No formulation data found in dfs or loaded_experiment")
            
            # Debug: Show summary table data and averages
            if include_summary_table and len(dfs) > 1:
                with st.expander("🔍 Debug: Summary Table & Averages", expanded=False):
                    import pandas as pd
                    from export import get_cell_metrics
                    
                    # Create a DataFrame-like structure for display
                    debug_data = []
                    for i, d in enumerate(dfs):
                        df_cell = d['df']
                        cell_name = d.get('testnum', f'Cell {i+1}') or f'Cell {i+1}'
                        metrics = get_cell_metrics(df_cell, dfs[0].get('formation_cycles', 4))
                        debug_data.append({
                            'Cell': cell_name,
                            '1st Cycle Discharge Capacity (mAh/g)': metrics.get('max_qdis'),
                            'First Cycle Efficiency (%)': metrics.get('eff_pct'),
                            'Cycle Life (80%)': metrics.get('cycle_life'),
                            'Reversible Capacity (mAh/g)': metrics.get('reversible_capacity'),
                            'Coulombic Efficiency (%)': metrics.get('coulombic_eff')
                        })
                    
                    debug_df = pd.DataFrame(debug_data)
                    st.write("**Cell Data:**")
                    st.dataframe(debug_df)
                    st.write("**DataFrame Statistics:**")
                    st.write(debug_df.describe())
                    
                    # Calculate and show averages
                    avg_row = {
                        'Cell': 'Average Performance',
                        '1st Cycle Discharge Capacity (mAh/g)': debug_df['1st Cycle Discharge Capacity (mAh/g)'].mean() if '1st Cycle Discharge Capacity (mAh/g)' in debug_df.columns else None,
                        'First Cycle Efficiency (%)': debug_df['First Cycle Efficiency (%)'].mean() if 'First Cycle Efficiency (%)' in debug_df.columns else None,
                        'Cycle Life (80%)': debug_df['Cycle Life (80%)'].mean() if 'Cycle Life (80%)' in debug_df.columns else None,
                        'Reversible Capacity (mAh/g)': debug_df['Reversible Capacity (mAh/g)'].mean() if 'Reversible Capacity (mAh/g)' in debug_df.columns else None,
                        'Coulombic Efficiency (%)': debug_df['Coulombic Efficiency (%)'].mean() if 'Coulombic Efficiency (%)' in debug_df.columns else None
                    }
                    st.write("**Average Performance Row:**")
                    st.write(avg_row)
            
            if content_items:
                for item in content_items:
                    st.markdown(f"- {item}")
            else:
                st.warning("⚠️ No content selected for export")
            
            st.markdown("---")
            
            # PowerPoint Export
            st.subheader("📤 Generate PowerPoint")
            
            if content_items:  # Only show export if something is selected
                from export import export_powerpoint
                
                # Generate PowerPoint with selected options
                try:
                    pptx_bytes, pptx_file_name = export_powerpoint(
                        dfs=dfs,
                        show_averages=show_average_performance,
                        experiment_name=experiment_name,
                        show_lines=show_lines,
                        show_efficiency_lines=show_efficiency_lines,
                        remove_last_cycle=remove_last_cycle,
                        # Advanced slide content control
                        include_summary_table=include_summary_table,
                        include_main_plot=include_main_plot,
                        include_retention_plot=include_retention_plot,
                        include_notes=include_notes,
                        include_electrode_data=include_electrode_data,
                        include_porosity=include_porosity,
                        include_thickness=include_thickness,
                        include_solids_content=include_solids_content,
                        include_formulation=include_formulation,
                        experiment_notes=stored_experiment_notes,
                        # Retention plot parameters (use session state from Plots tab)
                        retention_threshold=st.session_state.get('retention_threshold', 80.0),
                        reference_cycle=st.session_state.get('reference_cycle', 5),
                        formation_cycles=dfs[0].get('formation_cycles', 4) if dfs and len(dfs) > 0 else st.session_state.get('current_formation_cycles', 4),
                        retention_show_lines=show_lines,  # Use same lines as main plot
                        retention_remove_markers=remove_markers,
                        retention_hide_legend=hide_legend,
                        retention_show_title=show_graph_title,
                        show_baseline_line=st.session_state.get('retention_show_baseline', True),
                        show_threshold_line=st.session_state.get('retention_show_threshold', True),
                        y_axis_min=st.session_state.get('y_axis_min', 0.0),
                        y_axis_max=st.session_state.get('y_axis_max', 110.0),
                        # Plot customization parameters (from session state)
                        show_graph_title=st.session_state.get('show_graph_title', True),
                        show_average_performance=show_average_performance,
                        avg_line_toggles=st.session_state.get('avg_line_toggles', {}),
                        remove_markers=st.session_state.get('remove_markers', False),
                        hide_legend=st.session_state.get('hide_legend', False)
                    )
                    
                    st.success("✅ PowerPoint generated successfully!")
                    st.download_button(
                        f"📥 Download PowerPoint: {pptx_file_name}",
                        data=pptx_bytes,
                        file_name=pptx_file_name,
                        mime='application/vnd.openxmlformats-officedocument.presentationml.presentation',
                        key='download_enhanced_pptx',
                        use_container_width=True
                    )
                    
                    # Show file details
                    st.info(f"📄 **File:** {pptx_file_name}")
                    
                except Exception as e:
                    st.error(f"❌ Error generating PowerPoint: {str(e)}")
                    st.error("Please check your data and settings, then try again.")
            else:
                st.info("👆 Please select at least one content item to include in the PowerPoint slide.")
            
            st.markdown("---")
            
            # Project-Level Export Section
            if current_project_id:
                st.markdown("---")
                st.subheader("📦 Export Entire Project")
                st.markdown("*Export all experiments in the current project to a single PowerPoint file*")
                
                if st.button("🚀 Export Entire Project", type="secondary", use_container_width=True):
                    try:
                        from database import get_all_project_experiments_data, get_project_by_id
                        from export import export_powerpoint
                        from io import BytesIO
                        from pptx import Presentation
                        from pptx.util import Inches, Pt
                        from pptx.enum.text import PP_ALIGN
                        import json
                        from io import StringIO
                        from data_processing import calculate_efficiency_based_on_project_type
                        
                        # Get all experiments for the project, sorted by creation date
                        all_experiments_data = get_all_project_experiments_data(current_project_id)
                        
                        if not all_experiments_data:
                            st.error("❌ No experiments found in this project.")
                        else:
                            # Sort by creation date (chronologically)
                            # Handle None values by using a far-future date for sorting
                            from datetime import datetime
                            def get_sort_key(exp_data):
                                created_date = exp_data[13] if len(exp_data) > 13 else None  # created_date is index 13
                                if created_date is None:
                                    return datetime.max  # Put None dates at the end
                                # If it's already a datetime, use it directly
                                if isinstance(created_date, datetime):
                                    return created_date
                                # If it's a string, try to parse it
                                if isinstance(created_date, str):
                                    try:
                                        return datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                                    except:
                                        return datetime.max
                                return datetime.max
                            
                            all_experiments_data.sort(key=get_sort_key)
                            
                            st.info(f"📊 Found {len(all_experiments_data)} experiment(s). Generating slides...")
                            
                            # Create a new presentation for the project
                            project_prs = Presentation()
                            project_prs.slide_layouts[6]  # Blank layout
                            
                            # Get project info
                            project_info = get_project_by_id(current_project_id)
                            project_name = project_info[1] if project_info else "Project"
                            project_type = project_info[3] if project_info and len(project_info) > 3 else "Full Cell"
                            
                            # Process each experiment
                            experiments_processed = 0
                            for exp_data in all_experiments_data:
                                exp_id, exp_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, separator, formulation_json, data_json, created_date, porosity, experiment_notes = exp_data
                                
                                try:
                                    # Parse experiment data
                                    parsed_data = json.loads(data_json)
                                    
                                    # Load cells data
                                    cells_data = parsed_data.get('cells', [])
                                    if not cells_data:
                                        # Single cell experiment
                                        cells_data = [{
                                            'data_json': data_json,
                                            'cell_name': exp_name,
                                            'test_number': test_number,
                                            'loading': loading,
                                            'active_material': active_material,
                                            'formation_cycles': formation_cycles,
                                            'formulation': json.loads(formulation_json) if formulation_json else []
                                        }]
                                    
                                    # Build dfs structure for this experiment
                                    exp_dfs = []
                                    for cell_data in cells_data:
                                        if cell_data.get('excluded', False):
                                            continue
                                        
                                        cell_data_json = cell_data.get('data_json', '')
                                        if not cell_data_json:
                                            continue
                                        
                                        df = pd.read_json(StringIO(cell_data_json))
                                        
                                        # Recalculate efficiency based on project type
                                        if 'Q charge (mA.h)' in df.columns and 'Q discharge (mA.h)' in df.columns:
                                            df['Efficiency (-)'] = calculate_efficiency_based_on_project_type(
                                                df['Q charge (mA.h)'], 
                                                df['Q discharge (mA.h)'], 
                                                project_type
                                            ) / 100
                                        
                                        # Get formulation
                                        formulation = cell_data.get('formulation', [])
                                        if not formulation and formulation_json:
                                            try:
                                                formulation = json.loads(formulation_json)
                                            except:
                                                formulation = []
                                        
                                        exp_dfs.append({
                                            'df': df,
                                            'testnum': cell_data.get('test_number', cell_data.get('cell_name', 'Unknown')),
                                            'loading': cell_data.get('loading', loading),
                                            'active': cell_data.get('active_material', active_material),
                                            'formation_cycles': cell_data.get('formation_cycles', formation_cycles),
                                            'project_type': project_type,
                                            'excluded': False,
                                            'pressed_thickness': parsed_data.get('pressed_thickness'),
                                            'solids_content': parsed_data.get('solids_content'),
                                            'porosity': cell_data.get('porosity', porosity),
                                            'formulation': formulation
                                        })
                                    
                                    if not exp_dfs:
                                        st.warning(f"⚠️ Skipping {exp_name}: No valid cell data found.")
                                        continue
                                    
                                    # Add slides for this experiment to the project presentation
                                    export_powerpoint(
                                        dfs=exp_dfs,
                                        show_averages=True,
                                        experiment_name=exp_name,
                                        show_lines=show_lines,
                                        show_efficiency_lines=show_efficiency_lines,
                                        remove_last_cycle=remove_last_cycle,
                                        include_summary_table=include_summary_table,
                                        include_main_plot=include_main_plot,
                                        include_retention_plot=include_retention_plot,
                                        include_notes=include_notes,
                                        include_electrode_data=include_electrode_data,
                                        include_porosity=include_porosity,
                                        include_thickness=include_thickness,
                                        include_solids_content=include_solids_content,
                                        include_formulation=include_formulation,
                                        experiment_notes=experiment_notes or "",
                                        retention_threshold=st.session_state.get('retention_threshold', 80.0),
                                        reference_cycle=st.session_state.get('reference_cycle', 5),
                                        formation_cycles=formation_cycles or 4,
                                        retention_show_lines=show_lines,
                                        retention_remove_markers=remove_markers,
                                        retention_hide_legend=hide_legend,
                                        retention_show_title=show_graph_title,
                                        show_baseline_line=st.session_state.get('retention_show_baseline', True),
                                        show_threshold_line=st.session_state.get('retention_show_threshold', True),
                                        y_axis_min=st.session_state.get('y_axis_min', 0.0),
                                        y_axis_max=st.session_state.get('y_axis_max', 110.0),
                                        show_graph_title=st.session_state.get('show_graph_title', True),
                                        show_average_performance=show_average_performance,
                                        avg_line_toggles=st.session_state.get('avg_line_toggles', {}),
                                        remove_markers=st.session_state.get('remove_markers', False),
                                        hide_legend=st.session_state.get('hide_legend', False),
                                        existing_prs=project_prs  # Append to project presentation
                                    )
                                    
                                    experiments_processed += 1
                                    
                                except Exception as e:
                                    st.warning(f"⚠️ Error processing experiment {exp_name}: {str(e)}")
                                    import logging
                                    logging.error(f"Error processing experiment {exp_name}: {e}")
                                    continue
                            
                            if experiments_processed > 0:
                                # Save project presentation
                                project_bio = BytesIO()
                                project_prs.save(project_bio)
                                project_bio.seek(0)
                                
                                st.success(f"✅ Project export completed! Processed {experiments_processed} experiment(s).")
                                st.download_button(
                                    "📥 Download Project PowerPoint",
                                    data=project_bio,
                                    file_name="project_summary.pptx",
                                    mime='application/vnd.openxmlformats-officedocument.presentationml.presentation',
                                    key='download_project_pptx',
                                    use_container_width=True
                                )
                            else:
                                st.error("❌ No experiments could be processed for export.")
                    
                    except Exception as e:
                        st.error(f"❌ Error exporting project: {str(e)}")
                        import traceback
                        st.error(traceback.format_exc())
            
            st.markdown("---")
            
            # Excel Export Section
            st.subheader("📊 Excel Export")
            st.markdown("*Download detailed data in Excel format*")
            
            from export import export_excel
            
            try:
                excel_bytes, excel_file_name = export_excel(dfs, show_average_performance, experiment_name)
                
                st.success("✅ Excel file ready for download!")
                st.download_button(
                    f"📥 Download Excel: {excel_file_name}",
                    data=excel_bytes,
                    file_name=excel_file_name,
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    key='download_enhanced_excel',
                    use_container_width=True
                )
                
                st.info(f"📄 **File:** {excel_file_name}")
                
            except Exception as e:
                st.error(f"❌ Error generating Excel file: {str(e)}")
                st.error("Please check your data and try again.")
        else:
            st.info("📈 Upload and process data files to access export options.")
            st.markdown("""
            **Export Features:**
            - 📊 **PowerPoint:** Customizable slides with toggleable content
            - 📈 **Multiple Plots:** Main capacity plot + retention plot
            - 📝 **Notes & Data:** Include experiment notes and electrode data
            - 📋 **Summary Tables:** Key metrics and comparisons
            - 📊 **Excel:** Detailed data export with charts
            """)

# --- Comparison Tab ---
if tab_comparison and current_project_id:
    with tab_comparison:
        current_project_name = st.session_state.get('current_project_name', 'Selected Project')
        st.caption(f"Project: {current_project_name}")
        
        # Get all experiments data for this project
        all_experiments_data = get_all_project_experiments_data(current_project_id)
        
        if not all_experiments_data:
            st.info("No experiments found in this project. Create experiments to see comparison data.")
        else:
            # Extract experiment names for selection
            experiment_options = []
            experiment_dict = {}
            
            for exp_data in all_experiments_data:
                exp_id, exp_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, separator, formulation_json, data_json, created_date, porosity, experiment_notes = exp_data
                experiment_options.append(exp_name)
                experiment_dict[exp_name] = exp_data
            
            # Experiment Selection
            selected_experiments = st.multiselect(
                "Select experiments to compare",
                options=experiment_options,
                default=[],
                help="Select two or more experiments to compare"
            )
            
            if len(selected_experiments) < 2:
                st.warning("Please select at least 2 experiments to enable comparison.")
            else:
                st.caption(f"Comparing {len(selected_experiments)} experiments")
                
                # Process selected experiments data
                comparison_data = []
                individual_cells_comparison = []
                
                for exp_name in selected_experiments:
                    exp_data = experiment_dict[exp_name]
                    exp_id, exp_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, separator, formulation_json, data_json, created_date, porosity, experiment_notes = exp_data
                    
                    try:
                        parsed_data = json.loads(data_json)
                        
                        # Check if this is a multi-cell experiment or single cell
                        if 'cells' in parsed_data:
                            # Multi-cell experiment
                            cells_data = parsed_data['cells']
                            disc_diameter = parsed_data.get('disc_diameter_mm', 15)
                            disc_area_cm2 = np.pi * (disc_diameter / 2 / 10) ** 2
                            
                            experiment_cells = []
                            for cell_data in cells_data:
                                # Skip excluded cells
                                if cell_data.get('excluded', False):
                                    continue
                                    
                                try:
                                    df = pd.read_json(StringIO(cell_data['data_json']))
                                    
                                    # Get project type for efficiency calculation
                                    project_type = "Full Cell"  # Default
                                    if st.session_state.get('current_project_id'):
                                        current_project_id = st.session_state['current_project_id']
                                        project_info = get_project_by_id(current_project_id)
                                        if project_info:
                                            project_type = project_info[3]  # project_type is the 4th field
                                    
                                    cell_summary = calculate_cell_summary(df, cell_data, disc_area_cm2, project_type)
                                    cell_summary['experiment_name'] = exp_name
                                    cell_summary['experiment_date'] = parsed_data.get('experiment_date', created_date)
                                    # Add formulation data to cell summary
                                    if 'formulation' in cell_data:
                                        cell_summary['formulation_json'] = json.dumps(cell_data['formulation'])
                                    experiment_cells.append(cell_summary)
                                    individual_cells_comparison.append(cell_summary)
                                except Exception as e:
                                    continue
                            
                            # Calculate experiment average
                            if experiment_cells:
                                exp_summary = calculate_experiment_average(experiment_cells, exp_name, parsed_data.get('experiment_date', created_date))
                                # Add formulation data to experiment summary (use first cell's formulation as representative)
                                if experiment_cells and 'formulation_json' in experiment_cells[0]:
                                    exp_summary['formulation_json'] = experiment_cells[0]['formulation_json']
                                # Add porosity data to experiment summary (use average from cells)
                                porosity_values = [cell.get('porosity') for cell in experiment_cells if cell.get('porosity') is not None]
                                if porosity_values:
                                    exp_summary['porosity'] = sum(porosity_values) / len(porosity_values)
                                # Add pressed thickness data to experiment summary
                                exp_summary['pressed_thickness'] = parsed_data.get('pressed_thickness')
                                # Add disc diameter data to experiment summary
                                exp_summary['disc_diameter_mm'] = disc_diameter
                                # Add experiment notes to experiment summary
                                exp_summary['experiment_notes'] = experiment_notes
                                comparison_data.append(exp_summary)
                        else:
                            # Legacy single cell experiment
                            df = pd.read_json(StringIO(data_json))
                            
                            # Get project type for efficiency calculation
                            project_type = "Full Cell"  # Default
                            if st.session_state.get('current_project_id'):
                                current_project_id = st.session_state['current_project_id']
                                project_info = get_project_by_id(current_project_id)
                                if project_info:
                                    project_type = project_info[3]  # project_type is the 4th field
                            
                            cell_summary = calculate_cell_summary(df, {
                                'cell_name': test_number or exp_name,
                                'loading': loading,
                                'active_material': active_material,
                                'formation_cycles': formation_cycles,
                                'test_number': test_number
                            }, np.pi * (15 / 2 / 10) ** 2, project_type)  # Default disc size
                            cell_summary['experiment_name'] = exp_name
                            cell_summary['experiment_date'] = created_date
                            # Add formulation data to cell summary
                            if formulation_json:
                                cell_summary['formulation_json'] = formulation_json
                            individual_cells_comparison.append(cell_summary)
                            
                            # Also add as experiment summary (since it's a single cell)
                            exp_summary = cell_summary.copy()
                            exp_summary['cell_name'] = f"{exp_name} (Single Cell)"
                            comparison_data.append(exp_summary)
                            
                    except Exception as e:
                        st.error(f"Error processing experiment {exp_name}: {str(e)}")
                        continue
                
                # Generate comparison visualizations and tables
                if comparison_data:
                    # Create two columns for better layout
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.subheader("Comparison Visualization")
                        
                        # Plot selection
                        plot_type = st.selectbox(
                            "Metric",
                            ["Reversible Capacity", "Coulombic Efficiency", "First Discharge Capacity", 
                             "First Cycle Efficiency", "Cycle Life (80%)", "Areal Capacity"]
                        )
                        
                        # Create comparison plot
                        fig, ax = plt.subplots(figsize=(10, 6))
                        
                        # Map plot types to data keys
                        plot_mapping = {
                            "Reversible Capacity": ("reversible_capacity", "mAh/g"),
                            "Coulombic Efficiency": ("coulombic_efficiency", "%"),
                            "First Discharge Capacity": ("first_discharge", "mAh/g"),
                            "First Cycle Efficiency": ("first_efficiency", "%"),
                            "Cycle Life (80%)": ("cycle_life_80", "cycles"),
                            "Areal Capacity": ("areal_capacity", "mAh/cm²")
                        }
                        
                        data_key, unit = plot_mapping[plot_type]
                        
                        # Extract data for plotting
                        exp_names = []
                        values = []
                        colors = plt.cm.Set3(np.linspace(0, 1, len(comparison_data)))
                        
                        for i, exp in enumerate(comparison_data):
                            value = exp.get(data_key)
                            if value is not None:
                                exp_names.append(exp['experiment_name'])
                                values.append(value)
                        
                        if values:
                            bars = ax.bar(exp_names, values, color=colors[:len(values)], alpha=0.7, edgecolor='black', linewidth=1)
                            ax.set_ylabel(f"{plot_type} ({unit})")
                            ax.set_title(f"{plot_type} Comparison")
                            ax.tick_params(axis='x', rotation=45)
                            
                            # Add value labels on bars
                            for bar, value in zip(bars, values):
                                height = bar.get_height()
                                ax.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                                       f'{value:.2f}', ha='center', va='bottom', fontweight='bold')
                            
                            plt.tight_layout()
                            st.pyplot(fig)
                            
                            # Export option for plot
                            buf = io.BytesIO()
                            plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
                            buf.seek(0)
                            st.download_button(
                                label="Download Plot",
                                data=buf,
                                file_name=f"comparison_{plot_type.lower().replace(' ', '_')}.png",
                                mime="image/png"
                            )
                        else:
                            st.warning(f"No data available for {plot_type} comparison.")
                    
                    with col2:
                        st.subheader("Quick Stats")
                        
                        st.metric("Experiments", len(selected_experiments))
                        st.metric("Total Cells", len(individual_cells_comparison))
                        
                        # Show best performer for selected metric
                        if values and exp_names:
                            best_idx = np.argmax(values)
                            best_exp = exp_names[best_idx]
                            best_value = values[best_idx]
                            st.metric(f"Best {plot_type}", f"{best_value:.2f} {unit}")
                    
                    # Capacity comparison plot section
                    st.subheader("Capacity Data Comparison")
                    
                    # Prepare experiment data for plotting
                    experiments_plot_data = []
                    for exp_name in selected_experiments:
                        exp_data = experiment_dict[exp_name]
                        exp_id, exp_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, separator, formulation_json, data_json, created_date, porosity, experiment_notes = exp_data
                        
                        try:
                            parsed_data = json.loads(data_json)
                            dfs = []
                            
                            # Check if this is a multi-cell experiment or single cell
                            if 'cells' in parsed_data:
                                # Multi-cell experiment - cells_data is a list
                                cells_data = parsed_data['cells']
                                
                                # Process each cell in the experiment
                                for cell_data in cells_data:
                                    if cell_data.get('excluded', False):
                                        continue  # Skip excluded cells
                                    
                                    if 'data_json' in cell_data:
                                        df = pd.read_json(StringIO(cell_data['data_json']))
                                        test_num = cell_data.get('test_number', cell_data.get('testnum', f'Cell {len(dfs)+1}'))
                                        dfs.append({
                                            'df': df,
                                            'testnum': test_num,
                                            'loading': cell_data.get('loading', loading),
                                            'active_material': cell_data.get('active_material', active_material)
                                        })
                            else:
                                # Single cell experiment - data_json is at the top level
                                df = pd.read_json(StringIO(data_json))
                                test_num = test_number or f'Cell 1'
                                dfs.append({
                                    'df': df,
                                    'testnum': test_num,
                                    'loading': loading,
                                    'active_material': active_material
                                })
                            
                            if dfs:  # Only add if we have valid data
                                experiments_plot_data.append({
                                    'experiment_name': exp_name,
                                    'dfs': dfs
                                })
                        except Exception as e:
                            st.warning(f"Could not load plotting data for {exp_name}: {str(e)}")
                            # Add debug info
                            st.info(f"Debug info for {exp_name}: data_json type = {type(data_json)}, length = {len(str(data_json)) if data_json else 'None'}")
                            continue
                    
                    if len(experiments_plot_data) >= 1:
                        # Render plot options
                        show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers, hide_legend, cycle_filter, y_axis_limits = render_comparison_plot_options(experiments_plot_data)
                        
                        # Render color customization UI
                        custom_colors = render_comparison_color_customization(
                            experiments_plot_data, 
                            show_average_performance
                        )
                        
                        # Generate the comparison plot
                        try:
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
                                custom_colors,
                                y_axis_limits
                            )
                            
                            # Display the plot
                            st.pyplot(comparison_fig)
                            
                            # Export option for the comparison plot
                            buf = io.BytesIO()
                            comparison_fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
                            buf.seek(0)
                            st.download_button(
                                label="Download Plot",
                                data=buf,
                                file_name="capacity_comparison_plot.png",
                                mime="image/png"
                            )
                            
                        except Exception as e:
                            st.error(f"Error generating comparison plot: {str(e)}")
                    else:
                        st.warning("No valid experiment data available for capacity plotting.")
                    
                    # Summary comparison table
                    st.subheader("Comparison Summary Table")
                    
                    # Table filter options
                    with st.expander("Table Options", expanded=False):
                        show_columns = st.multiselect(
                            "Select metrics to display",
                            ["Experiment", "Reversible Capacity (mAh/g)", "Coulombic Efficiency (%)", 
                             "First Discharge (mAh/g)", "First Efficiency (%)", 
                             "Cycle Life (80%)", "Areal Capacity (mAh/cm²)", "Active Material (%)", "Date"],
                            default=["Experiment", "Reversible Capacity (mAh/g)", "Coulombic Efficiency (%)", 
                                   "First Discharge (mAh/g)", "Cycle Life (80%)"]
                        )
                    
                    if show_columns:
                        # Create comparison DataFrame
                        comparison_df_data = []
                        for exp in comparison_data:
                            row = {
                                'Experiment': exp['experiment_name'],
                                'Reversible Capacity (mAh/g)': exp.get('reversible_capacity', 'N/A'),
                                'Coulombic Efficiency (%)': exp.get('coulombic_efficiency', 'N/A'),
                                'First Discharge (mAh/g)': exp.get('first_discharge', 'N/A'),
                                'First Efficiency (%)': exp.get('first_efficiency', 'N/A'),
                                'Cycle Life (80%)': exp.get('cycle_life_80', 'N/A'),
                                'Areal Capacity (mAh/cm²)': exp.get('areal_capacity', 'N/A'),
                                'Active Material (%)': f"{exp.get('active_material', 'N/A'):.1f}" if exp.get('active_material') is not None and exp.get('active_material') != 'N/A' else 'N/A',
                                'Date': exp.get('experiment_date', 'N/A')
                            }
                            comparison_df_data.append(row)
                        
                        comparison_df = pd.DataFrame(comparison_df_data)
                        
                        # Filter to selected columns
                        available_columns = [col for col in show_columns if col in comparison_df.columns]
                        if available_columns:
                            filtered_df = comparison_df[available_columns]
                            st.dataframe(filtered_df, use_container_width=True)
                            
                            # Export option for table
                            csv_data = filtered_df.to_csv(index=False)
                            st.download_button(
                                label="Download Table (CSV)",
                                data=csv_data,
                                file_name="experiment_comparison.csv",
                                mime="text/csv"
                            )
                        else:
                            st.warning("No valid columns selected for display.")
                    else:
                        st.warning("Please select at least one column to display.")
                    
                    # Individual cells comparison (optional detailed view)
                    if individual_cells_comparison:
                        with st.expander("Individual Cells Detailed Comparison", expanded=False):
                            
                            # Create individual cells DataFrame
                            individual_df_data = []
                            for cell in individual_cells_comparison:
                                row = {
                                    'Experiment': cell.get('experiment_name', 'Unknown'),
                                    'Cell Name': cell['cell_name'],
                                    'Reversible Capacity (mAh/g)': cell.get('reversible_capacity', 'N/A'),
                                    'Coulombic Efficiency (%)': cell.get('coulombic_efficiency', 'N/A'),
                                    'First Discharge (mAh/g)': cell.get('first_discharge', 'N/A'),
                                    'First Efficiency (%)': cell.get('first_efficiency', 'N/A'),
                                    'Cycle Life (80%)': cell.get('cycle_life_80', 'N/A'),
                                    'Areal Capacity (mAh/cm²)': cell.get('areal_capacity', 'N/A'),
                                    'Loading (mg)': cell.get('loading', 'N/A')
                                }
                                individual_df_data.append(row)
                            
                            individual_df = pd.DataFrame(individual_df_data)
                            st.dataframe(individual_df, use_container_width=True)
                            
                            # Export option for individual cells
                            individual_csv = individual_df.to_csv(index=False)
                            st.download_button(
                                label="Download Individual Cells (CSV)",
                                data=individual_csv,
                                file_name="individual_cells_comparison.csv",
                                mime="text/csv"
                            )
                    else:
                        st.error("No valid data found for selected experiments.")
            
            # Formulation-Based Comparison Section
            st.subheader("Formulation-Based Comparison")
            
            # Get formulation summary for the project
            formulation_summary = get_formulation_summary(current_project_id)
            
            if not formulation_summary:
                st.info("No formulation data found in this project. Add formulations to your experiments to enable formulation-based comparisons.")
            else:
                # Component selection
                component_names = sorted(list(formulation_summary.keys()))
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    selected_component = st.selectbox(
                        "Select formulation component",
                        options=component_names
                    )
                
                with col2:
                    if selected_component:
                        stats = formulation_summary[selected_component]
                        st.metric(f"{selected_component} Range", f"{stats['min']:.1f} - {stats['max']:.1f}%")
                
                if selected_component:
                    # Get experiments with this component
                    matching_experiments = get_experiments_by_formulation_component(
                        current_project_id, selected_component
                    )
                    
                    if not matching_experiments:
                        st.warning(f"No experiments found with {selected_component} in their formulation.")
                    else:
                        # Filter options
                        with st.expander("Filter Options", expanded=False):
                            filter_col1, filter_col2 = st.columns(2)
                            with filter_col1:
                                min_pct = st.number_input(f"Minimum {selected_component} %", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
                            with filter_col2:
                                max_pct = st.number_input(f"Maximum {selected_component} %", min_value=0.0, max_value=100.0, value=100.0, step=0.5)
                        
                        # Apply filters
                        if min_pct > 0 or max_pct < 100:
                            filtered_experiments = get_experiments_by_formulation_component(
                                current_project_id, selected_component,
                                min_percentage=min_pct if min_pct > 0 else None,
                                max_percentage=max_pct if max_pct < 100 else None
                            )
                        else:
                            filtered_experiments = matching_experiments
                        
                        if filtered_experiments:
                            st.caption(f"Found {len(filtered_experiments)} experiments")
                            
                            # Create comparison DataFrame
                            comparison_df = create_formulation_comparison_dataframe(
                                filtered_experiments, selected_component
                            )
                            
                            if not comparison_df.empty:
                                # Initialize excluded metric values in session state
                                # Store as set of tuples: (experiment_name, metric_name)
                                exclusion_key = f'formulation_excluded_{selected_component}_{current_project_id}'
                                if exclusion_key not in st.session_state:
                                    st.session_state[exclusion_key] = set()
                                
                                excluded_values = st.session_state[exclusion_key]
                                
                                # Initialize overwritten values in session state
                                # Store as dict: {(experiment_name, metric_name): overwritten_value}
                                overwrite_key = f'formulation_overwritten_{selected_component}_{current_project_id}'
                                if overwrite_key not in st.session_state:
                                    st.session_state[overwrite_key] = {}
                                
                                overwritten_values = st.session_state[overwrite_key]
                                
                                # Visualization: Performance vs Component Percentage
                                st.subheader(f"Performance vs {selected_component} Percentage")
                                
                                # Metric selection for Y-axis
                                metric_options = {
                                'Reversible Capacity (mAh/g)': 'Reversible Capacity (mAh/g)',
                                'First Discharge (mAh/g)': 'First Discharge (mAh/g)',
                                'First Efficiency (%)': 'First Efficiency (%)',
                                'Cycle Life': 'Cycle Life',
                                'Porosity (%)': 'Porosity (%)'
                                }
                                
                                selected_metric = st.selectbox("Performance metric", options=list(metric_options.keys()))
                                
                                metric_col = metric_options[selected_metric]
                                
                                # Create a copy for plotting with overwritten values applied
                                plot_df = comparison_df.copy()
                                
                                # Apply overwritten values
                                for idx, row in plot_df.iterrows():
                                    exp_name = row['Experiment']
                                    overwrite_key_tuple = (exp_name, metric_col)
                                    if overwrite_key_tuple in overwritten_values:
                                        plot_df.at[idx, metric_col] = overwritten_values[overwrite_key_tuple]
                                
                                # Filter out excluded metric values and rows with missing data
                                def is_excluded(exp_name, metric):
                                    return (exp_name, metric) in excluded_values
                                
                                plot_df = plot_df[
                                    (~plot_df.apply(lambda row: is_excluded(row['Experiment'], metric_col), axis=1)) &
                                    plot_df[metric_col].notna() & 
                                    (plot_df[metric_col] != 'N/A')
                                ].copy()
                                
                                if not plot_df.empty:
                                    # Convert metric column to numeric if needed
                                    plot_df[metric_col] = pd.to_numeric(plot_df[metric_col], errors='coerce')
                                    plot_df = plot_df.dropna(subset=[metric_col, 'Component %'])
                                    
                                    if not plot_df.empty:
                                        # Create scatter plot
                                        fig, ax = plt.subplots(figsize=(10, 6))
                                        
                                        scatter = ax.scatter(
                                            plot_df['Component %'],
                                            plot_df[metric_col],
                                            s=100,
                                            alpha=0.6,
                                            c=plot_df['Component %'],
                                            cmap='viridis',
                                            edgecolors='black',
                                            linewidths=1
                                        )
                                        
                                        # Add trend line
                                        z = np.polyfit(plot_df['Component %'], plot_df[metric_col], 1)
                                        p = np.poly1d(z)
                                        ax.plot(
                                            plot_df['Component %'],
                                            p(plot_df['Component %']),
                                            "r--",
                                            alpha=0.5,
                                            label=f'Trend: y = {z[0]:.2f}x + {z[1]:.2f}'
                                        )
                                        
                                        ax.set_xlabel(f'{selected_component} (%)', fontsize=12, fontweight='bold')
                                        ax.set_ylabel(selected_metric, fontsize=12, fontweight='bold')
                                        ax.set_title(f'{selected_metric} vs {selected_component} Percentage', fontsize=14, fontweight='bold')
                                        ax.grid(True, alpha=0.3)
                                        ax.legend()
                                        
                                        # Add colorbar
                                        cbar = plt.colorbar(scatter, ax=ax)
                                        cbar.set_label(f'{selected_component} (%)', fontsize=10)
                                        
                                        plt.tight_layout()
                                        st.pyplot(fig)
                                        
                                        # Export plot
                                        buf = io.BytesIO()
                                        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
                                        buf.seek(0)
                                        st.download_button(
                                            label=f"Download Plot",
                                            data=buf,
                                            file_name=f"{selected_metric.replace(' ', '_')}_vs_{selected_component.replace(' ', '_')}.png",
                                            mime="image/png"
                                        )
                                    else:
                                        st.warning(f"No valid data points for {selected_metric} comparison.")
                                else:
                                    st.warning(f"No data available for {selected_metric} in the selected experiments.")
                                
                                # Simple comparison table - clean and user-friendly
                                st.subheader("Detailed Comparison Table")

                                # Table options
                                with st.expander("🔧 Table Options", expanded=False):
                                    show_columns = st.multiselect(
                                        "Select metrics to display:",
                                        ['Experiment', 'Component %', 'Reversible Capacity (mAh/g)',
                                         'First Discharge (mAh/g)', 'First Efficiency (%)',
                                         'Cycle Life', 'Loading (mg)', 'Active Material (%)',
                                         'Porosity (%)', 'Date'],
                                        default=['Experiment', 'Component %', 'Reversible Capacity (mAh/g)',
                                                'First Discharge (mAh/g)', 'Cycle Life'],
                                        help="Choose which columns to display in the comparison table"
                                    )

                                if show_columns:
                                    # Filter to selected columns and sort by component percentage
                                    available_columns = [col for col in show_columns if col in comparison_df.columns]
                                    if available_columns:
                                        filtered_df = comparison_df[available_columns].sort_values('Component %')
                                        st.dataframe(filtered_df, use_container_width=True)

                                        # Export option for table
                                        csv_data = filtered_df.to_csv(index=False)
                                        st.download_button(
                                            label="📥 Download Table (CSV)",
                                            data=csv_data,
                                            file_name=f"{selected_component.replace(' ', '_')}_comparison.csv",
                                            mime="text/csv"
                                        )
                                    else:
                                        st.warning("No valid columns selected for display.")
                                else:
                                    st.warning("Please select at least one column to display.")

                                # Optional individual cells comparison
                                with st.expander("🔬 Individual Cells Detailed Comparison", expanded=False):
                                    st.markdown("**All individual cells from selected experiments:**")

                                    # Create individual cells DataFrame
                                    individual_df_data = []
                                    for exp in filtered_experiments:
                                        exp_id, project_id, cell_name, file_name, loading, active_material, \
                                        formation_cycles, test_number, electrolyte, substrate, separator, \
                                        formulation_json, data_json, solids_content, pressed_thickness, \
                                        experiment_notes, created_date, porosity = exp
                                        
                                        exp_name = cell_name
                                        component_pct = extract_formulation_component_from_experiment(exp, selected_component)

                                        # Extract cell data from data_json
                                        reversible_capacity = None
                                        first_discharge = None
                                        first_efficiency = None
                                        cycle_life = None
                                        cell_loading = loading
                                        cell_active_material = active_material
                                        
                                        if data_json:
                                            try:
                                                parsed_data = json.loads(data_json)
                                                formation_cycles = formation_cycles or 4
                                                
                                                if 'cells' in parsed_data:
                                                    # Multi-cell experiment - process each cell
                                                    for cell in parsed_data['cells']:
                                                        if cell.get('excluded', False):
                                                            continue
                                                        
                                                        # Reset metrics for each cell
                                                        cell_reversible_capacity = None
                                                        cell_first_discharge = None
                                                        cell_first_efficiency = None
                                                        cell_cycle_life = None
                                                        cell_loading = loading  # Start with experiment-level loading
                                                        cell_active_material = active_material  # Start with experiment-level active_material
                                                        
                                                        # Extract loading and active_material from cell data
                                                        if cell.get('loading') is not None:
                                                            cell_loading = cell.get('loading')
                                                        if cell.get('active_material') is not None:
                                                            cell_active_material = cell.get('active_material')
                                                        
                                                        if 'data_json' in cell:
                                                            try:
                                                                df = pd.read_json(StringIO(cell['data_json']))
                                                                
                                                                # Get first discharge capacity (max of first 3 cycles)
                                                                if 'Q Dis (mAh/g)' in df.columns:
                                                                    first_three = df['Q Dis (mAh/g)'].head(3).tolist()
                                                                    if first_three:
                                                                        cell_first_discharge = max(first_three)
                                                                    
                                                                    # Get first post-formation cycle (reversible capacity)
                                                                    if len(df) > formation_cycles:
                                                                        cell_reversible_capacity = df['Q Dis (mAh/g)'].iloc[formation_cycles]
                                                                
                                                                # Get first cycle efficiency
                                                                if 'Efficiency (-)' in df.columns and len(df) > 0:
                                                                    first_eff = df['Efficiency (-)'].iloc[0]
                                                                    if first_eff is not None:
                                                                        try:
                                                                            cell_first_efficiency = float(first_eff) * 100
                                                                        except (ValueError, TypeError):
                                                                            pass
                                                                
                                                                # Calculate cycle life (80% threshold)
                                                                if 'Q Dis (mAh/g)' in df.columns and len(df) > formation_cycles:
                                                                    post_formation = df.iloc[formation_cycles:]
                                                                    if not post_formation.empty:
                                                                        initial_capacity = post_formation['Q Dis (mAh/g)'].iloc[0]
                                                                        if initial_capacity > 0:
                                                                            threshold = 0.8 * initial_capacity
                                                                            below_threshold = post_formation[post_formation['Q Dis (mAh/g)'] < threshold]
                                                                            if not below_threshold.empty:
                                                                                cell_cycle_life = int(post_formation.index[below_threshold.index[0]])
                                                            except Exception:
                                                                pass
                                                        
                                                        # Add row for this cell
                                                        row = {
                                                            'Experiment': exp_name,
                                                            'Component %': f"{component_pct:.1f}%" if component_pct else 'N/A',
                                                            'Reversible Capacity (mAh/g)': cell_reversible_capacity if cell_reversible_capacity is not None else 'N/A',
                                                            'First Discharge (mAh/g)': cell_first_discharge if cell_first_discharge is not None else 'N/A',
                                                            'First Efficiency (%)': f"{cell_first_efficiency:.2f}%" if cell_first_efficiency is not None else 'N/A',
                                                            'Cycle Life': cell_cycle_life if cell_cycle_life is not None else 'N/A',
                                                            'Loading (mg)': cell_loading if cell_loading is not None else 'N/A',
                                                            'Active Material (%)': cell_active_material if cell_active_material is not None else 'N/A',
                                                            'Porosity (%)': f"{porosity * 100:.2f}%" if porosity is not None else 'N/A'
                                                        }
                                                        individual_df_data.append(row)
                                                else:
                                                    # Legacy single cell experiment
                                                    try:
                                                        df = pd.read_json(StringIO(data_json))
                                                        formation_cycles = formation_cycles or 4
                                                        
                                                        if 'Q Dis (mAh/g)' in df.columns:
                                                            # First discharge (max of first 3)
                                                            first_three = df['Q Dis (mAh/g)'].head(3).tolist()
                                                            if first_three:
                                                                first_discharge = max(first_three)
                                                            
                                                            # Reversible capacity
                                                            if len(df) > formation_cycles:
                                                                reversible_capacity = df['Q Dis (mAh/g)'].iloc[formation_cycles]
                                                        
                                                        # First cycle efficiency
                                                        if 'Efficiency (-)' in df.columns and len(df) > 0:
                                                            first_eff = df['Efficiency (-)'].iloc[0]
                                                            if first_eff is not None:
                                                                try:
                                                                    first_efficiency = float(first_eff) * 100
                                                                except (ValueError, TypeError):
                                                                    pass
                                                        
                                                        # Cycle life
                                                        if 'Q Dis (mAh/g)' in df.columns and len(df) > formation_cycles:
                                                            post_formation = df.iloc[formation_cycles:]
                                                            if not post_formation.empty:
                                                                initial_capacity = post_formation['Q Dis (mAh/g)'].iloc[0]
                                                                if initial_capacity > 0:
                                                                    threshold = 0.8 * initial_capacity
                                                                    below_threshold = post_formation[post_formation['Q Dis (mAh/g)'] < threshold]
                                                                    if not below_threshold.empty:
                                                                        cycle_life = int(post_formation.index[below_threshold.index[0]])
                                                    except Exception:
                                                        pass
                                                    
                                                    # Add row for single cell experiment
                                                    row = {
                                                        'Experiment': exp_name,
                                                        'Component %': f"{component_pct:.1f}%" if component_pct else 'N/A',
                                                        'Reversible Capacity (mAh/g)': reversible_capacity if reversible_capacity is not None else 'N/A',
                                                        'First Discharge (mAh/g)': first_discharge if first_discharge is not None else 'N/A',
                                                        'First Efficiency (%)': f"{first_efficiency:.2f}%" if first_efficiency is not None else 'N/A',
                                                        'Cycle Life': cycle_life if cycle_life is not None else 'N/A',
                                                        'Loading (mg)': cell_loading if cell_loading is not None else 'N/A',
                                                        'Active Material (%)': cell_active_material if cell_active_material is not None else 'N/A',
                                                        'Porosity (%)': f"{porosity * 100:.2f}%" if porosity is not None else 'N/A'
                                                    }
                                                    individual_df_data.append(row)
                                            except Exception:
                                                # If data_json parsing fails, still add a row with available data
                                                row = {
                                                    'Experiment': exp_name,
                                                    'Component %': f"{component_pct:.1f}%" if component_pct else 'N/A',
                                                    'Reversible Capacity (mAh/g)': 'N/A',
                                                    'First Discharge (mAh/g)': 'N/A',
                                                    'First Efficiency (%)': 'N/A',
                                                    'Cycle Life': 'N/A',
                                                    'Loading (mg)': cell_loading if cell_loading is not None else 'N/A',
                                                    'Active Material (%)': cell_active_material if cell_active_material is not None else 'N/A',
                                                    'Porosity (%)': f"{porosity * 100:.2f}%" if porosity is not None else 'N/A'
                                                }
                                                individual_df_data.append(row)
                                        else:
                                            # No data_json available, add row with available data
                                            row = {
                                                'Experiment': exp_name,
                                                'Component %': f"{component_pct:.1f}%" if component_pct else 'N/A',
                                                'Reversible Capacity (mAh/g)': 'N/A',
                                                'First Discharge (mAh/g)': 'N/A',
                                                'First Efficiency (%)': 'N/A',
                                                'Cycle Life': 'N/A',
                                                'Loading (mg)': cell_loading if cell_loading is not None else 'N/A',
                                                'Active Material (%)': cell_active_material if cell_active_material is not None else 'N/A',
                                                'Porosity (%)': f"{porosity * 100:.2f}%" if porosity is not None else 'N/A'
                                        }
                                        individual_df_data.append(row)

                                    if individual_df_data:
                                        individual_df = pd.DataFrame(individual_df_data)
                                        st.dataframe(individual_df, use_container_width=True)

                                        # Export option for individual cells
                                        individual_csv = individual_df.to_csv(index=False)
                                        st.download_button(
                                            label="📥 Download Individual Cells (CSV)",
                                            data=individual_csv,
                                            file_name=f"{selected_component.replace(' ', '_')}_individual_cells.csv",
                                            mime="text/csv"
                                        )
                                    else:
                                        st.info("No individual cell data available for the selected experiments.")

                                # Grouped analysis
                                st.subheader("Grouped Analysis")
                                st.caption(f"Experiments grouped by {selected_component} percentage ranges")

                                grouped = group_experiments_by_formulation_range(
                                    filtered_experiments, selected_component, range_size=5.0
                                )

                                if grouped:
                                    for range_label in sorted(grouped.keys(), key=lambda x: float(x.split('-')[0])):
                                        experiments_in_range = grouped[range_label]
                                        with st.expander(f"{range_label} ({len(experiments_in_range)} experiments)"):
                                            for exp in experiments_in_range:
                                                exp_name = exp[2]  # cell_name
                                                component_pct = extract_formulation_component_from_experiment(exp, selected_component)
                                                st.write(f"• **{exp_name}**: {component_pct:.1f}% {selected_component}")
                            else:
                                st.warning("Could not create comparison table. Check that experiments have valid formulation and performance data.")
                        else:
                            st.warning(f"No experiments found with {selected_component} in the specified range ({min_pct:.1f}% - {max_pct:.1f}%).")

# --- Master Table Tab ---
if tab_master and current_project_id:
    with tab_master:
        st.header("📋 Master Table")
        current_project_name = st.session_state.get('current_project_name', 'Selected Project')
        st.markdown(f"**Project:** {current_project_name}")
        
        # Show update notification if calculations were recently updated
        if st.session_state.get('calculations_updated', False):
            update_time = st.session_state.get('update_timestamp')
            if update_time:
                time_str = update_time.strftime("%H:%M:%S")
                st.info(f"🔄 Data refreshed at {time_str} - Master table shows updated calculations!")
        
        st.markdown("---")
        
        # Get all experiments data for this project
        all_experiments_data = get_all_project_experiments_data(current_project_id)
        
        if not all_experiments_data:
            st.info("📊 No experiments found in this project. Create experiments to see master table data.")
        else:
            # Process experiment data
            experiment_summaries = []
            individual_cells = []
            
            for exp_data in all_experiments_data:
                exp_id, exp_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, separator, formulation_json, data_json, created_date, porosity, experiment_notes = exp_data
                
                # If substrate or separator are None from database, we'll extract them from JSON data
                extracted_substrate = substrate
                extracted_separator = separator
                
                try:
                    parsed_data = json.loads(data_json)
                    
                    # Check if this is a multi-cell experiment or single cell
                    if 'cells' in parsed_data:
                        # Multi-cell experiment
                        cells_data = parsed_data['cells']
                        disc_diameter = parsed_data.get('disc_diameter_mm', 15)
                        disc_area_cm2 = np.pi * (disc_diameter / 2 / 10) ** 2
                        
                        experiment_cells = []
                        for cell_data in cells_data:
                            if cell_data.get('excluded', False):
                                continue
                            try:
                                df = pd.read_json(StringIO(cell_data['data_json']))
                                
                                # Get project type for efficiency calculation
                                project_type = "Full Cell"  # Default
                                if st.session_state.get('current_project_id'):
                                    current_project_id = st.session_state['current_project_id']
                                    project_info = get_project_by_id(current_project_id)
                                    if project_info:
                                        project_type = project_info[3]  # project_type is the 4th field
                                
                                cell_summary = calculate_cell_summary(df, cell_data, disc_area_cm2, project_type)
                                cell_summary['experiment_name'] = exp_name
                                cell_summary['experiment_date'] = parsed_data.get('experiment_date', created_date)
                                # Add pressed thickness data from experiment
                                cell_summary['pressed_thickness'] = parsed_data.get('pressed_thickness')
                                # Add disc diameter data from experiment
                                cell_summary['disc_diameter_mm'] = disc_diameter
                                # Add electrolyte, substrate, and separator data to cell summary
                                cell_summary['electrolyte'] = cell_data.get('electrolyte', 'N/A')
                                cell_summary['substrate'] = cell_data.get('substrate', 'N/A')
                                cell_summary['separator'] = cell_data.get('separator', 'N/A')
                                # Add formulation data to cell summary
                                if 'formulation' in cell_data:
                                    cell_summary['formulation_json'] = json.dumps(cell_data['formulation'])
                                # Add porosity data from cell_data if available, or recalculate if missing
                                if 'porosity' in cell_data and cell_data['porosity'] is not None and cell_data['porosity'] > 0:
                                    cell_summary['porosity'] = cell_data['porosity']
                                else:
                                    # Recalculate porosity if missing or invalid
                                    try:
                                        from porosity_calculations import calculate_porosity_from_experiment_data
                                        if (cell_data.get('loading') and 
                                            disc_diameter and 
                                            parsed_data.get('pressed_thickness') and 
                                            cell_data.get('formulation')):
                                            
                                            porosity_data = calculate_porosity_from_experiment_data(
                                                disc_mass_mg=cell_data['loading'],
                                                disc_diameter_mm=disc_diameter,
                                                pressed_thickness_um=parsed_data['pressed_thickness'],
                                                formulation=cell_data['formulation']
                                            )
                                            cell_summary['porosity'] = porosity_data['porosity']
                                        else:
                                            cell_summary['porosity'] = None
                                    except Exception:
                                        cell_summary['porosity'] = None
                                experiment_cells.append(cell_summary)
                                individual_cells.append(cell_summary)
                            except Exception as e:
                                continue
                        
                        # Calculate experiment average
                        if experiment_cells:
                            exp_summary = calculate_experiment_average(experiment_cells, exp_name, parsed_data.get('experiment_date', created_date))
                            # Add formulation data to experiment summary (use first cell's formulation as representative)
                            if experiment_cells and 'formulation_json' in experiment_cells[0]:
                                exp_summary['formulation_json'] = experiment_cells[0]['formulation_json']
                            # Add porosity data to experiment summary (use average from cells)
                            porosity_values = [cell.get('porosity') for cell in experiment_cells if cell.get('porosity') is not None]
                            if porosity_values:
                                exp_summary['porosity'] = sum(porosity_values) / len(porosity_values)
                            # Add pressed thickness data to experiment summary
                            exp_summary['pressed_thickness'] = parsed_data.get('pressed_thickness')
                            # Add disc diameter data to experiment summary
                            exp_summary['disc_diameter_mm'] = disc_diameter
                            # Add electrolyte, substrate, and separator data to experiment summary (use first cell's values as representative)
                            if experiment_cells:
                                exp_summary['electrolyte'] = experiment_cells[0].get('electrolyte', 'N/A')
                                exp_summary['substrate'] = experiment_cells[0].get('substrate', 'N/A')
                                exp_summary['separator'] = experiment_cells[0].get('separator', 'N/A')
                            # Add experiment notes to experiment summary
                            exp_summary['experiment_notes'] = experiment_notes
                            experiment_summaries.append(exp_summary)
                    
                    else:
                        # Legacy single cell experiment
                        df = pd.read_json(StringIO(data_json))
                        
                        # Get project type for efficiency calculation
                        project_type = "Full Cell"  # Default
                        if st.session_state.get('current_project_id'):
                            current_project_id = st.session_state['current_project_id']
                            project_info = get_project_by_id(current_project_id)
                            if project_info:
                                project_type = project_info[3]  # project_type is the 4th field
                        
                        cell_summary = calculate_cell_summary(df, {
                            'cell_name': test_number or exp_name,
                            'loading': loading,
                            'active_material': active_material,
                            'formation_cycles': formation_cycles,
                            'test_number': test_number
                        }, np.pi * (15 / 2 / 10) ** 2, project_type)  # Default disc size
                        cell_summary['experiment_name'] = exp_name
                        cell_summary['experiment_date'] = created_date
                        # Add electrolyte, substrate, and separator data to cell summary
                        cell_summary['electrolyte'] = electrolyte if electrolyte else 'N/A'
                        cell_summary['substrate'] = extracted_substrate if extracted_substrate else 'N/A'
                        cell_summary['separator'] = extracted_separator if extracted_separator else 'N/A'
                        # Add formulation data to cell summary
                        if formulation_json:
                            cell_summary['formulation_json'] = formulation_json
                        # Add porosity data from database if available, or recalculate if missing
                        if porosity is not None and porosity > 0:
                            cell_summary['porosity'] = porosity
                        else:
                            # Recalculate porosity for legacy experiments if missing or invalid
                            try:
                                from porosity_calculations import calculate_porosity_from_experiment_data
                                if (loading and 
                                    disc_diameter and 
                                    formulation_json):
                                    
                                    # Parse formulation data
                                    formulation_data = json.loads(formulation_json)
                                    
                                    # Get pressed thickness from database
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute('SELECT pressed_thickness FROM cell_experiments WHERE id = ?', (exp_id,))
                                    result = cursor.fetchone()
                                    conn.close()
                                    pressed_thickness = result[0] if result and result[0] is not None else None
                                    
                                    if pressed_thickness:
                                        porosity_data = calculate_porosity_from_experiment_data(
                                            disc_mass_mg=loading,
                                            disc_diameter_mm=disc_diameter,
                                            pressed_thickness_um=pressed_thickness,
                                            formulation=formulation_data
                                        )
                                        cell_summary['porosity'] = porosity_data['porosity']
                                    else:
                                        cell_summary['porosity'] = None
                                else:
                                    cell_summary['porosity'] = None
                            except Exception:
                                cell_summary['porosity'] = None
                        # Add pressed thickness data from database if available
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute('SELECT pressed_thickness FROM cell_experiments WHERE id = ?', (exp_id,))
                        result = cursor.fetchone()
                        conn.close()
                        if result and result[0] is not None:
                            cell_summary['pressed_thickness'] = result[0]
                        # Add disc diameter data (default to 15mm for legacy experiments)
                        cell_summary['disc_diameter_mm'] = 15
                        individual_cells.append(cell_summary)
                        
                        # Also add as experiment summary (since it's a single cell)
                        exp_summary = cell_summary.copy()
                        exp_summary['cell_name'] = f"{exp_name} (Single Cell)"
                        # Add electrolyte, substrate, and separator data to experiment summary
                        exp_summary['electrolyte'] = electrolyte if electrolyte else 'N/A'
                        exp_summary['substrate'] = extracted_substrate if extracted_substrate else 'N/A'
                        exp_summary['separator'] = extracted_separator if extracted_separator else 'N/A'
                        # Add porosity data from database if available, or recalculate if missing
                        if porosity is not None and porosity > 0:
                            exp_summary['porosity'] = porosity
                        else:
                            # Recalculate porosity for legacy experiments if missing or invalid
                            try:
                                from porosity_calculations import calculate_porosity_from_experiment_data
                                if (loading and 
                                    disc_diameter and 
                                    formulation_json):
                                    
                                    # Parse formulation data
                                    formulation_data = json.loads(formulation_json)
                                    
                                    # Get pressed thickness from database
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute('SELECT pressed_thickness FROM cell_experiments WHERE id = ?', (exp_id,))
                                    result = cursor.fetchone()
                                    conn.close()
                                    pressed_thickness = result[0] if result and result[0] is not None else None
                                    
                                    if pressed_thickness:
                                        porosity_data = calculate_porosity_from_experiment_data(
                                            disc_mass_mg=loading,
                                            disc_diameter_mm=disc_diameter,
                                            pressed_thickness_um=pressed_thickness,
                                            formulation=formulation_data
                                        )
                                        exp_summary['porosity'] = porosity_data['porosity']
                                    else:
                                        exp_summary['porosity'] = None
                                else:
                                    exp_summary['porosity'] = None
                            except Exception:
                                exp_summary['porosity'] = None
                        # Add pressed thickness data from database if available
                        # For legacy experiments, we need to get this from the database
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute('SELECT pressed_thickness FROM cell_experiments WHERE id = ?', (exp_id,))
                        result = cursor.fetchone()
                        conn.close()
                        if result and result[0] is not None:
                            exp_summary['pressed_thickness'] = result[0]
                        # Add disc diameter data (default to 15mm for legacy experiments)
                        exp_summary['disc_diameter_mm'] = 15
                        # Add experiment notes to experiment summary
                        exp_summary['experiment_notes'] = experiment_notes
                        experiment_summaries.append(exp_summary)
                        
                except Exception as e:
                    st.error(f"Error processing experiment {exp_name}: {str(e)}")
                    continue
            
            # Section 1: Average Cell Data per Experiment
            with st.expander("### 📊 Section 1: Average Cell Data per Experiment", expanded=True):
                if experiment_summaries:
                    display_experiment_summaries_table(experiment_summaries)
                else:
                    st.info("No experiment summary data available.")
            
            st.markdown("---")
            
            # Section 2: All Individual Cells Data
            with st.expander("### 🧪 Section 2: All Individual Cells Data", expanded=False):
                if individual_cells:
                    display_individual_cells_table(individual_cells)
                else:
                    st.info("No individual cell data available.")
            
            st.markdown("---")
            
            # Section 3: Best Performing Cells Analysis
            with st.expander("### 🏅 Section 3: Best Performing Cells Analysis", expanded=True):
                display_best_performers_analysis(individual_cells)

# --- Data Preprocessing Section ---

# Add this function after the imports at the top of the file
def recalculate_gravimetric_capacities(df, new_loading, new_active_material):
    """
    Recalculate gravimetric capacities when loading or active material values change.
    Returns a new DataFrame with updated Q Chg (mAh/g) and Q Dis (mAh/g) values.
    """
    try:
        # Create a copy of the DataFrame to avoid modifying the original
        updated_df = df.copy()
        
        # Calculate new active mass
        active_mass = (new_loading / 1000) * (new_active_material / 100)
        if active_mass <= 0:
            raise ValueError("Active mass must be greater than 0. Check loading and active material values.")
        
        # Recalculate gravimetric capacities
        if 'Q charge (mA.h)' in updated_df.columns:
            updated_df['Q Chg (mAh/g)'] = updated_df['Q charge (mA.h)'] / active_mass
        if 'Q discharge (mA.h)' in updated_df.columns:
            updated_df['Q Dis (mAh/g)'] = updated_df['Q discharge (mA.h)'] / active_mass
        
        return updated_df
    except Exception as e:
        st.error(f"Error recalculating gravimetric capacities: {str(e)}")
        return df  # Return original DataFrame if calculation fails