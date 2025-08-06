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
    update_project_type, get_project_by_id
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
from ui_components import render_toggle_section, display_summary_stats, display_averages, render_cell_inputs, get_initial_areal_capacity, render_formulation_table, render_retention_display_options, get_substrate_options
from plotting import plot_capacity_graph, plot_capacity_retention_graph

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
                
                # Update the experiment with current data
                update_experiment(
                    experiment_id=experiment_id,
                    project_id=project_id,
# Show delete confirmation dialogs when triggered
                    group_assignments=current_group_assignments,
                    group_names=current_group_names,
                    cells_data=experiment_data['cells']  # Keep original cell data
                )
                st.success("✅ Changes saved!")
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
    st.markdown("#### 📁 Projects")
    user_projects = get_user_projects(TEST_USER_ID)
    if user_projects:
        for p in user_projects:
            project_id, project_name, project_desc, project_type, created_date, last_modified = p
            project_expanded = st.session_state.get(f'project_expanded_{project_id}', False)
            
            # Project row with dropdown arrow and three dots
            project_cols = st.columns([0.1, 0.7, 0.2])
            with project_cols[0]:
                # Dropdown arrow
                arrow = "▼" if project_expanded else "▶"
                if st.button(arrow, key=f'project_toggle_{project_id}', help="Expand/Collapse"):
                    st.session_state[f'project_expanded_{project_id}'] = not project_expanded
                    st.rerun()
            
            with project_cols[1]:
                # Project name button with type indicator
                project_display_name = f"{project_name} ({project_type})"
                if st.button(project_display_name, key=f'project_select_{project_id}', use_container_width=True):
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
                    
                    st.session_state['current_project_id'] = project_id
                    st.session_state['current_project_name'] = project_name
                    st.session_state[f'project_expanded_{project_id}'] = True
                    st.rerun()
            
            with project_cols[2]:
                menu_open = st.session_state.get(f'project_menu_open_{project_id}', False)
                if st.button('⋯', key=f'project_menu_btn_{project_id}', help="Project options"):
                    # Close all other menus
                    for p2 in user_projects:
                        st.session_state[f'project_menu_open_{p2[0]}'] = False
                    st.session_state[f'project_menu_open_{project_id}'] = not menu_open
                    st.rerun()
                # Simple vertical dropdown menu
                if menu_open:
                    with st.container():
                        if st.button('New Experiment', key=f'project_new_exp_{project_id}_menu', use_container_width=True):
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
                            
                            st.session_state[f'project_menu_open_{project_id}'] = False
                            st.session_state['show_cell_inputs_prompt'] = True
                            st.rerun()
                        if st.button('Rename', key=f'project_rename_{project_id}_menu', use_container_width=True):
                            st.session_state[f'renaming_project_{project_id}'] = True
                            st.session_state[f'project_menu_open_{project_id}'] = False
                            st.rerun()
                        if st.button('Change Type', key=f'project_change_type_{project_id}_menu', use_container_width=True):
                            st.session_state[f'changing_project_type_{project_id}'] = True
                            st.session_state[f'project_menu_open_{project_id}'] = False
                            st.rerun()
                        if st.button('Delete', key=f'project_delete_{project_id}_menu', use_container_width=True):
                            st.session_state['confirm_delete_project'] = project_id
                            st.session_state[f'project_menu_open_{project_id}'] = False
                            st.rerun()
            
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
            
            # Show experiments if project is expanded and selected
            if (project_expanded and st.session_state.get('current_project_id') == project_id):
                existing_experiments = get_project_experiments(project_id)
                if existing_experiments:
                    st.markdown("##### 🧪 Experiments")
                    for experiment in existing_experiments:
                        experiment_id, experiment_name, file_name, data_json, created_date = experiment
                        
                        # Experiment row with indentation and three dots
                        exp_cols = st.columns([0.1, 0.7, 0.2])
                        with exp_cols[0]:
                            st.markdown("&nbsp;&nbsp;📊", unsafe_allow_html=True)
                        
                        with exp_cols[1]:
                            if st.button(experiment_name, key=f'exp_select_{experiment_id}', use_container_width=True):
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
                                
                                st.session_state['loaded_experiment'] = {
                                    'experiment_id': experiment_id,
                                    'experiment_name': experiment_name,
                                    'project_id': project_id,
                                    'experiment_data': json.loads(data_json)
                                }
                                st.rerun()
                        
                        with exp_cols[2]:
                            exp_menu_open = st.session_state.get(f'exp_menu_open_{experiment_id}', False)
                            if st.button('⋯', key=f'exp_menu_btn_{experiment_id}', help="Experiment options"):
                                for e2 in existing_experiments:
                                    st.session_state[f'exp_menu_open_{e2[0]}'] = False
                                st.session_state[f'exp_menu_open_{experiment_id}'] = not exp_menu_open
                                st.rerun()
                            if exp_menu_open:
                                with st.container():
                                    if st.button('Rename', key=f'exp_rename_{experiment_id}_menu', use_container_width=True):
                                        st.session_state[f'renaming_experiment_{experiment_id}'] = True
                                        st.session_state[f'exp_menu_open_{experiment_id}'] = False
                                        st.rerun()
                                    if st.button('Delete', key=f'exp_delete_{experiment_id}_menu', use_container_width=True):
                                        st.session_state['confirm_delete_experiment'] = (experiment_id, experiment_name)
                                        st.session_state[f'exp_menu_open_{experiment_id}'] = False
                                        st.rerun()
                        
                        # Inline rename for experiment
                        if st.session_state.get(f'renaming_experiment_{experiment_id}', False):
                            exp_rename_cols = st.columns([0.1, 0.7, 0.2])
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
                    st.markdown("&nbsp;&nbsp;&nbsp;&nbsp;*No experiments in this project*", unsafe_allow_html=True)
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
    st.markdown("#### 📁 Project Contents")
    # (Optional: Show currently loaded experiment status here)

    st.markdown("#### ℹ️ Quick Start")
    st.markdown("1. **Create or select a project** above")
    st.markdown("2. **Go to Cell Inputs tab** to upload data or edit experiments") 
    st.markdown("3. **View results** in Summary, Plots, and Export tabs")

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
    tab_inputs, tab1, tab2, tab3, tab_comparison, tab_master = st.tabs(["🧪 Cell Inputs", "📊 Summary", "📈 Plots", "📤 Export", "🔄 Comparison", "📋 Master Table"])
else:
    tab_inputs, tab1, tab2, tab3 = st.tabs(["🧪 Cell Inputs", "📊 Summary", "📈 Plots", "📤 Export"])
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
        st.info(f"📊 Editing experiment: **{loaded_experiment['experiment_name']}**")
        experiment_data = loaded_experiment['experiment_data']
        
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
                'formulation': cell_data.get('formulation', [])
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
            placeholder='Enter experiment name for file naming and summary tab',
            key="main_experiment_name"
        )
    
    with col2:
        experiment_date_input = st.date_input(
            "Experiment Date", 
            value=current_experiment_date,
            help="Date associated with this experiment"
        )
    
    disc_diameter_input = st.number_input(
        'Disc Diameter (mm) for Areal Capacity Calculation', 
        min_value=1, 
        max_value=50, 
        value=current_disc_diameter, 
        step=1
    )
    
    st.markdown("---")
    
    # Cell inputs section
    if loaded_experiment:
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
                
                # Electrolyte and Substrate selection
                electrolyte_options = ['1M LiPF6 1:1:1', '1M LiTFSI 3:7 +10% FEC']
                substrate_options = get_substrate_options()
                
                col3, col4 = st.columns(2)
                with col3:
                    electrolyte_0 = st.selectbox(
                        f'Electrolyte for Cell 1', 
                        electrolyte_options,
                        index=electrolyte_options.index(datasets[0]["electrolyte"]) if datasets[0]["electrolyte"] in electrolyte_options else 0,
                        key=f'edit_electrolyte_0'
                    )
                with col4:
                    substrate_0 = st.selectbox(
                        f'Substrate for Cell 1', 
                        substrate_options,
                        index=substrate_options.index(datasets[0].get("substrate", "Copper")) if datasets[0].get("substrate") in substrate_options else 0,
                        key=f'edit_substrate_0'
                    )
                
                # Formulation table
                st.markdown("**Formulation:**")
                from ui_components import render_formulation_table
                # Initialize formulation data if needed
                formulation_key = f'formulation_data_edit_0_loaded'
                if formulation_key not in st.session_state:
                    st.session_state[formulation_key] = datasets[0]["formulation"] if datasets[0]["formulation"] else [{'Component': '', 'Dry Mass Fraction (%)': 0.0}]
                formulation_0 = render_formulation_table(f'edit_0_loaded', project_id, get_project_components)
                
                assign_all = st.checkbox('Assign values to all cells', key='assign_all_cells_loaded')
            # Update all datasets with new values
            edited_datasets = []
            for i, dataset in enumerate(datasets):
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
                        'formulation': formulation_0
                    }
                else:
                    with st.expander(f'Cell {i+1}: {dataset["testnum"] or f"Cell {i+1}"}', expanded=False):
                        col1, col2 = st.columns(2)
                        if assign_all:
                            loading = loading_0
                            formation_cycles = formation_cycles_0
                            active_material = active_material_0
                            electrolyte = electrolyte_0
                            substrate = substrate_0
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
                            
                            # Electrolyte and Substrate selection
                            electrolyte_options = ['1M LiPF6 1:1:1', '1M LiTFSI 3:7 +10% FEC']
                            substrate_options = get_substrate_options()
                            
                            col3, col4 = st.columns(2)
                            with col3:
                                electrolyte = st.selectbox(
                                    f'Electrolyte for Cell {i+1}', 
                                    electrolyte_options,
                                    index=electrolyte_options.index(dataset['electrolyte']) if dataset['electrolyte'] in electrolyte_options else 0,
                                    key=f'edit_electrolyte_{i}'
                                )
                            with col4:
                                substrate = st.selectbox(
                                    f'Substrate for Cell {i+1}', 
                                    substrate_options,
                                    index=substrate_options.index(dataset.get('substrate', 'Copper')) if dataset.get('substrate') in substrate_options else 0,
                                    key=f'edit_substrate_{i}'
                                )
                            
                            # Formulation table
                            st.markdown("**Formulation:**")
                            from ui_components import render_formulation_table
                            # Initialize formulation data if needed
                            formulation_key = f'formulation_data_edit_{i}_loaded'
                            if formulation_key not in st.session_state:
                                st.session_state[formulation_key] = dataset['formulation'] if dataset['formulation'] else [{'Component': '', 'Dry Mass Fraction (%)': 0.0}]
                            formulation = render_formulation_table(f'edit_{i}_loaded', project_id, get_project_components)
                            
                        with col2:
                            # Always preserve original file object, only update other fields
                            edited_dataset = {
                                'file': dataset['file'],  # Always preserve original file object
                                'loading': loading,
                                'active': active_material,
                                'testnum': test_number,
                                'formation_cycles': formation_cycles,
                                'electrolyte': electrolyte,
                                'substrate': substrate,
                                'formulation': formulation
                            }
                edited_datasets.append(edited_dataset)
            datasets = edited_datasets
            st.session_state['datasets'] = datasets
        else:
            # Only one cell
            for i, dataset in enumerate(datasets):
                with st.expander(f'Cell {i+1}: {dataset["testnum"] or f"Cell {i+1}"}', expanded=False):
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
                    
                    # Electrolyte and Substrate selection
                    electrolyte_options = ['1M LiPF6 1:1:1', '1M LiTFSI 3:7 +10% FEC']
                    substrate_options = get_substrate_options()
                    
                    col3, col4 = st.columns(2)
                    with col3:
                        electrolyte = st.selectbox(
                            f'Electrolyte for Cell {i+1}', 
                            electrolyte_options,
                            index=electrolyte_options.index(dataset['electrolyte']) if dataset['electrolyte'] in electrolyte_options else 0,
                            key=f'edit_single_electrolyte_{i}'
                        )
                    with col4:
                        substrate = st.selectbox(
                            f'Substrate for Cell {i+1}', 
                            substrate_options,
                            index=substrate_options.index(dataset.get('substrate', 'Copper')) if dataset.get('substrate') in substrate_options else 0,
                            key=f'edit_single_substrate_{i}'
                        )
                    
                    # Formulation table
                    st.markdown("**Formulation:**")
                    from ui_components import render_formulation_table
                    # Initialize formulation data if needed
                    formulation_key = f'formulation_data_edit_single_{i}_loaded'
                    if formulation_key not in st.session_state:
                        st.session_state[formulation_key] = dataset['formulation'] if dataset['formulation'] else [{'Component': '', 'Dry Mass Fraction (%)': 0.0}]
                    formulation = render_formulation_table(f'edit_single_{i}_loaded', project_id, get_project_components)
                    
                    # Always preserve original file object, only update other fields
                    edited_dataset = {
                        'file': dataset['file'],  # Always preserve original file object
                        'loading': loading,
                        'active': active_material,
                        'testnum': test_number,
                        'formation_cycles': formation_cycles,
                        'electrolyte': electrolyte,
                        'substrate': substrate,
                        'formulation': formulation
                    }
                dataset.update(edited_dataset)
    else:
        # New experiment flow - use unified render_cell_inputs
        st.markdown("#### 📁 Upload Cell Data Files")
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
    st.session_state['current_disc_diameter_mm'] = disc_diameter_input
    st.session_state['current_group_assignments'] = group_assignments
    st.session_state['current_group_names'] = group_names
    
    # Save/Update experiment button
    st.markdown("---")
    if loaded_experiment:
        if st.button("💾 Update Experiment", type="primary", use_container_width=True):
            # Update the loaded experiment with new values
            experiment_id = loaded_experiment['experiment_id']
            project_id = loaded_experiment['project_id']
            
            # Prepare updated cells data
            updated_cells_data = []
            for i, dataset in enumerate(datasets):
                if i < len(experiment_data.get('cells', [])):
                    original_cell = experiment_data['cells'][i]
                    updated_cell = original_cell.copy()
                    updated_cell.update({
                        'loading': dataset['loading'],
                        'active_material': dataset['active'],
                        'formation_cycles': dataset['formation_cycles'],
                        'test_number': dataset['testnum'],
                        'cell_name': dataset['testnum'],
                        'electrolyte': dataset.get('electrolyte', '1M LiPF6 1:1:1'),
                        'formulation': dataset.get('formulation', [])
                    })
                    updated_cells_data.append(updated_cell)
            
            try:
                update_experiment(
                    experiment_id=experiment_id,
                    project_id=project_id,
                    experiment_name=experiment_name_input,
                    experiment_date=experiment_date_input,
                    disc_diameter_mm=disc_diameter_input,
                    group_assignments=group_assignments,
                    group_names=group_names,
                    cells_data=updated_cells_data,
                    solids_content=solids_content,
                    pressed_thickness=pressed_thickness,
                    experiment_notes=experiment_notes
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
                
                st.success("✅ Experiment updated successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error updating experiment: {str(e)}")
    
    elif is_new_experiment:
        # Save new experiment (only if we have valid data and a selected project)
        valid_datasets = [ds for ds in datasets if ds.get('file') and ds.get('loading', 0) > 0 and 0 < ds.get('active', 0) <= 100]
        
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
                                'formulation': ds.get('formulation', []),
                                'data_json': df.to_json()
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
                            update_experiment(
                                experiment_id=experiment_id,
                                project_id=current_project_id,
                                experiment_name=exp_name,
                                experiment_date=experiment_date_input,
                                disc_diameter_mm=disc_diameter_input,
                                group_assignments=group_assignments,
                                group_names=group_names,
                                cells_data=cells_data,
                                solids_content=solids_content,
                                pressed_thickness=pressed_thickness,
                                experiment_notes=experiment_notes
                            )
                            st.success(f"🔄 Updated experiment '{exp_name}' in project '{current_project_name}'!")
                        else:
                            save_experiment(
                                project_id=current_project_id,
                                experiment_name=exp_name,
                                experiment_date=experiment_date_input,
                                disc_diameter_mm=disc_diameter_input,
                                group_assignments=group_assignments,
                                group_names=group_names,
                                cells_data=cells_data,
                                solids_content=solids_content,
                                pressed_thickness=pressed_thickness,
                                experiment_notes=experiment_notes
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
    
    for cell_data in cells_data:
        cell_name = cell_data.get('cell_name', 'Unknown')
        try:
            df = pd.read_json(cell_data['data_json'])
            
            # Get project type for efficiency recalculation
            project_type = "Full Cell"  # Default
            if st.session_state.get('current_project_id'):
                current_project_id = st.session_state['current_project_id']
                project_info = get_project_by_id(current_project_id)
                if project_info:
                    project_type = project_info[3]  # project_type is the 4th field
            
            # Recalculate efficiency based on project type if this is an anode project
            if project_type == "Anode" and 'Q charge (mA.h)' in df.columns and 'Q discharge (mA.h)' in df.columns:
                # Recalculate efficiency for anode projects
                df['Efficiency (-)'] = calculate_efficiency_based_on_project_type(
                    df['Q charge (mA.h)'], 
                    df['Q discharge (mA.h)'], 
                    project_type
                ) / 100  # Convert to decimal for consistency
            
            loaded_dfs.append({
                'df': df,
                'testnum': cell_data.get('test_number'),
                'loading': cell_data.get('loading'),
                'active': cell_data.get('active_material'),
                'formation_cycles': cell_data.get('formation_cycles'),
                'project_type': project_type
            })
        except Exception as e:
            st.error(f"Error loading data for {cell_name}: {str(e)}")
    
    if loaded_dfs:
        # Use loaded data for analysis
        dfs = loaded_dfs
        ready = True
        st.success(f"✅ Loaded {len(loaded_dfs)} cell(s) from saved experiment")
        
        # Display experiment metadata
        if experiment_data.get('experiment_date'):
            st.info(f"📅 Experiment Date: {experiment_data['experiment_date']}")
        if experiment_data.get('disc_diameter_mm'):
            st.info(f"🔘 Disc Diameter: {experiment_data['disc_diameter_mm']} mm")
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
        st.header("📊 Summary Tables")
        st.markdown("---")
        # Add toggle for showing average column
        show_average_col = False
        if len(dfs) > 1:
            show_average_col = st.toggle("Show average column", value=True, key="show_average_col_toggle")
        # Only one summary table should be rendered:
        from ui_components import display_summary_stats
        display_summary_stats(dfs, disc_area_cm2, show_average_col, group_assignments, group_names)
    with tab2:
        st.header("📈 Plots")
        st.markdown("---")
        
        # Get formation cycles for reference cycle calculation
        formation_cycles = st.session_state.get('current_formation_cycles', 4)
        if ready and datasets:
            # Try to get formation cycles from the first dataset
            if 'formation_cycles' in datasets[0]:
                formation_cycles = datasets[0]['formation_cycles']
        
        # Shared Data Series Controls (affects both plots)
        st.subheader("🎛️ Data Series Selection")
        st.markdown("*These controls apply to both the Main Capacity Plot and Capacity Retention Plot below*")
        show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers, hide_legend, group_plot_toggles = render_toggle_section(dfs, enable_grouping=enable_grouping)
        
        st.markdown("---")
        
        # Main Capacity Plot Section
        st.subheader("📊 Main Capacity Plot")
        
        # Main plot specific display options
        with st.expander("🎨 Main Plot Display Options", expanded=False):
            st.markdown("### Main Plot Customization")
            
            main_display_col1, main_display_col2, main_display_col3 = st.columns(3)
            
            with main_display_col1:
                st.markdown("**Data Display**")
                main_remove_markers = st.checkbox(
                    '🔘 Remove markers', 
                    value=remove_markers,
                    key='main_remove_markers',
                    help="Hide data point markers on the main plot for cleaner lines"
                )
                main_show_title = st.checkbox(
                    '📝 Show graph title', 
                    value=show_graph_title,
                    key='main_show_title',
                    help="Display the main plot title"
                )
            
            with main_display_col2:
                st.markdown("**Legend & Labels**")
                main_hide_legend = st.checkbox(
                    '🏷️ Hide legend', 
                    value=hide_legend,
                    key='main_hide_legend',
                    help="Remove the plot legend (useful for single-cell data or cleaner visuals)"
                )
                
            with main_display_col3:
                st.markdown("**Data Processing**")
                main_remove_last = st.checkbox(
                    '🔄 Remove last cycle', 
                    value=remove_last_cycle,
                    key='main_remove_last',
                    help="Exclude the last cycle from the main plot (useful for incomplete data)"
                )
        
        # Generate main capacity plot
        fig = plot_capacity_graph(
            dfs, show_lines, show_efficiency_lines, main_remove_last, main_show_title, experiment_name,
            show_average_performance, avg_line_toggles, main_remove_markers, main_hide_legend,
            group_a_curve=(group_curves[0][0], group_curves[0][1]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][1] and group_plot_toggles.get("Group Q Dis", False) else None,
            group_b_curve=(group_curves[1][0], group_curves[1][1]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][1] and group_plot_toggles.get("Group Q Dis", False) else None,
            group_c_curve=(group_curves[2][0], group_curves[2][1]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][1] and group_plot_toggles.get("Group Q Dis", False) else None,
            group_a_qchg=(group_curves[0][0], group_curves[0][2]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][2] and group_plot_toggles.get("Group Q Chg", False) else None,
            group_b_qchg=(group_curves[1][0], group_curves[1][2]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][2] and group_plot_toggles.get("Group Q Chg", False) else None,
            group_c_qchg=(group_curves[2][0], group_curves[2][2]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][2] and group_plot_toggles.get("Group Q Chg", False) else None,
            group_a_eff=(group_curves[0][0], group_curves[0][3]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][3] and group_plot_toggles.get("Group Efficiency", False) else None,
            group_b_eff=(group_curves[1][0], group_curves[1][3]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][3] and group_plot_toggles.get("Group Efficiency", False) else None,
            group_c_eff=(group_curves[2][0], group_curves[2][3]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][3] and group_plot_toggles.get("Group Efficiency", False) else None,
            group_names=group_names
        )
        st.pyplot(fig)
        
        st.markdown("---")
        
        # Capacity Retention Plot Section
        st.subheader("📉 Capacity Retention Plot")
        
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
                        "🎯 Reference Cycle (100% baseline)",
                        min_value=int(min_cycle),
                        max_value=int(max_cycle),
                        value=int(default_ref_cycle),
                        step=1,
                        help=f"Select which cycle to use as the 100% reference point. Default is cycle {formation_cycles + 1} (first cycle after {formation_cycles} formation cycles)."
                    )
                
                with col2:
                    st.metric("Formation Cycles", formation_cycles)
                
                with col3:
                    st.metric("Available Cycles", f"{int(min_cycle)} - {int(max_cycle)}")
                
                # Advanced retention plot controls
                st.markdown("#### 🔧 Advanced Plot Controls")
                
                # Controls in columns for better layout
                control_col1, control_col2, control_col3 = st.columns([1, 1, 1])
                
                with control_col1:
                    retention_threshold = st.slider(
                        "📏 Retention Threshold (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=80.0,
                        step=5.0,
                        help="Set the threshold line for capacity retention analysis. Common values: 80% (standard), 70% (aggressive)."
                    )
                
                with control_col2:
                    # Y-axis scaling options
                    y_axis_preset = st.selectbox(
                        "📊 Y-Axis Range",
                        options=["Full Range (0-110%)", "Focused View (70-110%)", "Standard View (50-110%)", "Custom Range"],
                        index=0,
                        help="Choose the Y-axis range for better visualization of retention data."
                    )
                
                with control_col3:
                    # If custom range is selected, show input fields
                    if y_axis_preset == "Custom Range":
                        custom_min = st.number_input(
                            "Min Y (%)", 
                            min_value=0.0, 
                            max_value=100.0, 
                            value=0.0,
                            step=5.0,
                            help="Set custom minimum Y-axis value"
                        )
                        custom_max = st.number_input(
                            "Max Y (%)", 
                            min_value=50.0, 
                            max_value=200.0, 
                            value=110.0,
                            step=5.0,
                            help="Set custom maximum Y-axis value"
                        )
                        y_axis_min, y_axis_max = custom_min, custom_max
                    else:
                        # Set Y-axis range based on preset
                        if y_axis_preset == "Full Range (0-110%)":
                            y_axis_min, y_axis_max = 0.0, 110.0
                        elif y_axis_preset == "Focused View (70-110%)":
                            y_axis_min, y_axis_max = 70.0, 110.0
                        elif y_axis_preset == "Standard View (50-110%)":
                            y_axis_min, y_axis_max = 50.0, 110.0
                        
                        # Show current range as metric
                        st.metric("Y-Axis Range", f"{y_axis_min:.0f}% - {y_axis_max:.0f}%")
                
                # Retention plot display options
                retention_remove_markers, retention_hide_legend, retention_show_title, show_baseline_line, show_threshold_line = render_retention_display_options()
                
                # Info box explaining the reference cycle and synchronization
                st.info(f"ℹ️ **Current Reference:** Cycle {reference_cycle} is set as 100% capacity. All other cycles show retention relative to this reference.")
                st.info("🔗 **Synchronized Data:** This plot uses the same data series selection as the main plot above. Only the selected discharge and charge capacity lines are shown.")
                
                # Generate capacity retention plot with shared filter settings
                retention_fig = plot_capacity_retention_graph(
                    dfs, show_lines, reference_cycle, formation_cycles, main_remove_last, 
                    retention_show_title, experiment_name, show_average_performance, 
                    avg_line_toggles, retention_remove_markers, retention_hide_legend,
                    group_a_curve=None,  # Can be extended later for group retention
                    group_b_curve=None,
                    group_c_curve=None,
                    group_names=group_names,
                    retention_threshold=retention_threshold,
                    y_axis_min=y_axis_min,
                    y_axis_max=y_axis_max,
                    show_baseline_line=show_baseline_line,
                    show_threshold_line=show_threshold_line
                )
                st.pyplot(retention_fig)
                
                # Additional information and controls summary
                with st.expander("📖 Capacity Retention Information", expanded=False):
                    st.markdown(f"""
                    **How Capacity Retention is Calculated:**
                    - The selected reference cycle capacity is set to 100%
                    - Each cycle's retention = (Current Cycle Capacity / Reference Cycle Capacity) × 100%
                    - Reference lines are shown at 100% (baseline) and {retention_threshold}% (user-defined threshold)
                    - The green vertical line indicates the current reference cycle
                    
                    **Current Settings:**
                    - 🎯 **Reference Cycle:** {reference_cycle} (set as 100% baseline)
                    - 📏 **Retention Threshold:** {retention_threshold}% (red dashed line)
                    - 📊 **Y-Axis Range:** {y_axis_min:.0f}% - {y_axis_max:.0f}%
                    
                    **Key Features:**
                    - 🎯 **Reference Cycle:** Change which cycle serves as the 100% baseline
                    - 📏 **Adjustable Threshold:** Set custom retention threshold line (default: 80%)
                    - 📊 **Y-Axis Scaling:** Choose from preset ranges or set custom range for better visualization
                    - 🎨 **Display Controls:** Show/hide markers, legend, title, and reference lines
                    - 🔗 **Synchronized Data:** Uses the same data series selection as the main plot
                    - 🔄 **Real-time Updates:** All plots update automatically when settings change
                    - 🔄 **Interactive:** Hover over data points for detailed information
                    - 📈 **Enhanced Visualization:** Focus on specific retention ranges for detailed analysis
                    """)
                    
                    # Show threshold and scaling tips
                    st.markdown("#### 💡 Usage Tips:")
                    st.markdown(f"""
                    - **Data Synchronization:** Both plots show the same data series. Change selections in the "Data Series Selection" section above to filter both plots simultaneously.
                    - **Threshold at {retention_threshold}%:** {"Standard degradation benchmark" if retention_threshold == 80 else "Custom degradation benchmark"} {"(Hidden)" if not show_threshold_line else "(Visible)"}
                    - **Y-Axis Range:** {"Full view - good for complete retention analysis" if y_axis_preset == "Full Range (0-110%)" else "Focused view - better for detailed capacity changes analysis"}
                    - **Reference Cycle {reference_cycle}:** {"First cycle after formation" if reference_cycle == formation_cycles + 1 else "Custom baseline cycle"}
                    - **Display Options:** {"Markers hidden" if retention_remove_markers else "Markers shown"}, {"Legend hidden" if retention_hide_legend else "Legend shown"}, {"Title hidden" if not retention_show_title else "Title shown"}
                    - **Reference Lines:** {"100% baseline hidden" if not show_baseline_line else "100% baseline shown"}, {"Threshold line hidden" if not show_threshold_line else "Threshold line shown"}
                    - **Remove Last Cycle:** {"Applied to both plots" if main_remove_last else "Not applied"}
                    """)
            else:
                st.warning("⚠️ No cycle data available for capacity retention analysis. Please upload data files first.")
        else:
            st.info("📈 Upload and process data files to see capacity retention analysis.")
            st.markdown("""
            **Capacity Retention Plot Features:**
            - Shows how capacity changes relative to a reference cycle
            - Default reference is the first cycle after formation
            - Interactive reference cycle selection
            - Real-time plot updates
            - Visual guidelines at 100% and 80% retention levels
            """)
    with tab3:
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
                        value=False,
                        key="export_notes",
                        help="Include experiment notes from the Cell Input page"
                    )
                    include_electrode_data = st.checkbox(
                        "Electrode data group",
                        value=False,
                        key="export_electrode_group",
                        help="Include electrode-related data"
                    )
            
            # Electrode Data Sub-toggles
            if include_electrode_data:
                with st.expander("🔬 Electrode Data Details", expanded=True):
                    electrode_col1, electrode_col2 = st.columns(2)
                    
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
            else:
                include_porosity = False
                include_thickness = False
            
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
                if electrode_items:
                    content_items.append(f"✅ Electrode data: {', '.join(electrode_items)}")
            
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
                        experiment_notes=stored_experiment_notes,
                        # Retention plot parameters (use session state from Plots tab)
                        retention_threshold=st.session_state.get('retention_threshold', 80.0),
                        reference_cycle=st.session_state.get('reference_cycle', 5),
                        formation_cycles=dfs[0].get('formation_cycles', 4) if dfs and len(dfs) > 0 else st.session_state.get('current_formation_cycles', 4),
                        retention_show_lines=show_lines,  # Use same lines as main plot
                        retention_remove_markers=st.session_state.get('retention_remove_markers', False),
                        retention_hide_legend=st.session_state.get('retention_hide_legend', False),
                        retention_show_title=st.session_state.get('retention_show_title', True),
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
        st.header("🔄 Experiment Comparison")
        current_project_name = st.session_state.get('current_project_name', 'Selected Project')
        st.markdown(f"**Project:** {current_project_name}")
        st.markdown("---")
        
        # Get all experiments data for this project
        all_experiments_data = get_all_project_experiments_data(current_project_id)
        
        if not all_experiments_data:
            st.info("📊 No experiments found in this project. Create experiments to see comparison data.")
        else:
            # Extract experiment names for selection
            experiment_options = []
            experiment_dict = {}
            
            for exp_data in all_experiments_data:
                exp_id, exp_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, formulation_json, data_json, created_date, porosity, experiment_notes = exp_data
                experiment_options.append(exp_name)
                experiment_dict[exp_name] = exp_data
            
            # Experiment Selection
            st.subheader("📋 Select Experiments to Compare")
            selected_experiments = st.multiselect(
                "Choose two or more experiments:",
                options=experiment_options,
                default=[],
                help="Select multiple experiments to compare their performance metrics"
            )
            
            if len(selected_experiments) < 2:
                st.warning("⚠️ Please select at least 2 experiments to enable comparison.")
            else:
                st.success(f"✅ Comparing {len(selected_experiments)} experiments")
                
                # Process selected experiments data
                comparison_data = []
                individual_cells_comparison = []
                
                for exp_name in selected_experiments:
                    exp_data = experiment_dict[exp_name]
                    exp_id, exp_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, formulation_json, data_json, created_date, porosity, experiment_notes = exp_data
                    
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
                                try:
                                    df = pd.read_json(StringIO(cell_data['data_json']))
                                    cell_summary = calculate_cell_summary(df, cell_data, disc_area_cm2)
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
                            cell_summary = calculate_cell_summary(df, {
                                'cell_name': test_number or exp_name,
                                'loading': loading,
                                'active_material': active_material,
                                'formation_cycles': formation_cycles,
                                'test_number': test_number
                            }, np.pi * (15 / 2 / 10) ** 2)  # Default disc size
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
                        st.subheader("📊 Comparison Visualization")
                        
                        # Plot selection
                        plot_type = st.selectbox(
                            "Select comparison metric:",
                            ["Reversible Capacity", "Coulombic Efficiency", "First Discharge Capacity", 
                             "First Cycle Efficiency", "Cycle Life (80%)", "Areal Capacity"],
                            help="Choose which metric to visualize for comparison"
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
                                label="📥 Download Plot",
                                data=buf,
                                file_name=f"comparison_{plot_type.lower().replace(' ', '_')}.png",
                                mime="image/png"
                            )
                        else:
                            st.warning(f"No data available for {plot_type} comparison.")
                    
                    with col2:
                        st.subheader("📋 Quick Stats")
                        
                        # Show experiment count
                        st.metric("Experiments Selected", len(selected_experiments))
                        st.metric("Total Cells", len(individual_cells_comparison))
                        
                        # Show best performer for selected metric
                        if values and exp_names:
                            best_idx = np.argmax(values)
                            best_exp = exp_names[best_idx]
                            best_value = values[best_idx]
                            st.metric(
                                f"Best {plot_type}",
                                f"{best_value:.2f} {unit}",
                                delta=None,
                                help=f"Experiment: {best_exp}"
                            )
                    
                    # Summary comparison table
                    st.subheader("📊 Comparison Summary Table")
                    
                    # Table filter options
                    with st.expander("🔧 Table Options", expanded=False):
                        show_columns = st.multiselect(
                            "Select metrics to display:",
                            ["Experiment", "Reversible Capacity (mAh/g)", "Coulombic Efficiency (%)", 
                             "First Discharge (mAh/g)", "First Efficiency (%)", 
                             "Cycle Life (80%)", "Areal Capacity (mAh/cm²)", "Active Material (%)", "Date"],
                            default=["Experiment", "Reversible Capacity (mAh/g)", "Coulombic Efficiency (%)", 
                                   "First Discharge (mAh/g)", "Cycle Life (80%)"],
                            help="Choose which columns to display in the comparison table"
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
                                'Active Material (%)': exp.get('active_material', 'N/A'),
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
                                label="📥 Download Table (CSV)",
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
                        with st.expander("🔬 Individual Cells Detailed Comparison", expanded=False):
                            st.markdown("**All individual cells from selected experiments:**")
                            
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
                                label="📥 Download Individual Cells (CSV)",
                                data=individual_csv,
                                file_name="individual_cells_comparison.csv",
                                mime="text/csv"
                            )
else:
                    st.error("No valid data found for selected experiments.")

# --- Master Table Tab ---
if tab_master and current_project_id:
    with tab_master:
        st.header("📋 Master Table")
        current_project_name = st.session_state.get('current_project_name', 'Selected Project')
        st.markdown(f"**Project:** {current_project_name}")
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
                exp_id, exp_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, formulation_json, data_json, created_date, porosity, experiment_notes = exp_data
                
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
                            try:
                                df = pd.read_json(StringIO(cell_data['data_json']))
                                cell_summary = calculate_cell_summary(df, cell_data, disc_area_cm2)
                                cell_summary['experiment_name'] = exp_name
                                cell_summary['experiment_date'] = parsed_data.get('experiment_date', created_date)
                                # Add pressed thickness data from experiment
                                cell_summary['pressed_thickness'] = parsed_data.get('pressed_thickness')
                                # Add disc diameter data from experiment
                                cell_summary['disc_diameter_mm'] = disc_diameter
                                # Add formulation data to cell summary
                                if 'formulation' in cell_data:
                                    cell_summary['formulation_json'] = json.dumps(cell_data['formulation'])
                                # Add porosity data from cell_data if available
                                if 'porosity' in cell_data:
                                    cell_summary['porosity'] = cell_data['porosity']
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
                            # Add experiment notes to experiment summary
                            exp_summary['experiment_notes'] = experiment_notes
                            experiment_summaries.append(exp_summary)
                    
                    else:
                        # Legacy single cell experiment
                        df = pd.read_json(StringIO(data_json))
                        cell_summary = calculate_cell_summary(df, {
                            'cell_name': test_number or exp_name,
                            'loading': loading,
                            'active_material': active_material,
                            'formation_cycles': formation_cycles,
                            'test_number': test_number
                        }, np.pi * (15 / 2 / 10) ** 2)  # Default disc size
                        cell_summary['experiment_name'] = exp_name
                        cell_summary['experiment_date'] = created_date
                        # Add formulation data to cell summary
                        if formulation_json:
                            cell_summary['formulation_json'] = formulation_json
                        # Add porosity data from database if available
                        if porosity is not None:
                            cell_summary['porosity'] = porosity
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
                        # Add porosity data from database if available
                        if porosity is not None:
                            exp_summary['porosity'] = porosity
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