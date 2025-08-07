# preference_components.py
import streamlit as st
import json

def render_preferences_sidebar(project_id):
    """Render the project preferences sidebar."""
    if not project_id:
        return
    
    # Import database functions inside the function to avoid circular imports
    from database import get_project_preferences, save_project_preferences, get_project_by_id
    
    # Get project name
    project_info = get_project_by_id(project_id)
    project_name = project_info[1] if project_info else "Unknown Project"
    
    st.sidebar.markdown("## ⚙️ Project Preferences")
    st.sidebar.markdown(f"**Project:** {project_name}")
    st.sidebar.markdown("Set default values for new experiments in this project.")
    
    # Get current preferences
    preferences = get_project_preferences(project_id)
    
    with st.sidebar.expander("📋 Default Settings", expanded=False):
        # Electrolyte preference
        electrolyte_options = ['1M LiPF6 1:1:1', '1M LiTFSI 3:7 +10% FEC']
        current_electrolyte = preferences.get('electrolyte', '')
        new_electrolyte = st.selectbox(
            "Electrolyte",
            options=electrolyte_options,
            index=electrolyte_options.index(current_electrolyte) if current_electrolyte in electrolyte_options else 0,
            help="Default electrolyte for new experiments"
        )
        
        # Substrate preference
        from ui_components import get_substrate_options
        substrate_options = get_substrate_options()
        current_substrate = preferences.get('substrate', '')
        new_substrate = st.selectbox(
            "Substrate",
            options=substrate_options,
            index=substrate_options.index(current_substrate) if current_substrate in substrate_options else 0,
            help="Default substrate for new experiments"
        )
        
        # Formation cycles preference
        current_formation_cycles = preferences.get('formation_cycles', '4')
        try:
            formation_default = int(current_formation_cycles) if current_formation_cycles.isdigit() else 4
        except (ValueError, TypeError):
            formation_default = 4
        new_formation_cycles = st.number_input(
            "Formation Cycles",
            min_value=0,
            max_value=20,
            value=formation_default,
            help="Default number of formation cycles for new experiments"
        )
        
        # Formulation preference
        current_formulation = preferences.get('formulation', '')
        try:
            current_formulation_data = json.loads(current_formulation) if current_formulation else []
        except:
            current_formulation_data = []
        
        st.markdown("**Default Formulation**")
        if st.button("Edit Formulation", key="edit_formulation_pref"):
            st.session_state.show_formulation_editor = True
        
        if current_formulation_data:
            st.markdown("Current default formulation:")
            for i, component in enumerate(current_formulation_data):
                if component.get('Component'):  # Only show non-empty components
                    st.markdown(f"• {component.get('Component', 'Unknown')}: {component.get('Dry Mass Fraction (%)', 0)}%")
        else:
            st.markdown("*No default formulation set*")
        
        # Save preferences button
        if st.button("💾 Save Preferences", type="primary"):
            new_preferences = {
                'electrolyte': new_electrolyte,
                'substrate': new_substrate,
                'formation_cycles': str(new_formation_cycles),
                'formulation': current_formulation  # This will be updated when formulation is saved separately
            }
            
            save_project_preferences(project_id, new_preferences)
            st.sidebar.success("✅ Preferences saved!")
            st.rerun()
        
        # Clear preferences button
        if st.button("🗑️ Clear All Preferences"):
            save_project_preferences(project_id, {
                'electrolyte': '',
                'substrate': '',
                'formation_cycles': '',
                'formulation': ''
            })
            st.sidebar.success("✅ Preferences cleared!")
            st.rerun()

def render_formulation_editor_modal():
    """Render the formulation editor modal for preferences."""
    if not st.session_state.get('show_formulation_editor', False):
        return
    
    # Import database functions inside the function to avoid circular imports
    from database import get_project_preferences, save_project_preferences
    from ui_components import render_formulation_table
    
    st.markdown("### Edit Default Formulation")
    st.markdown("Configure the default formulation that will be used for new experiments in this project.")
    
    # Create a unique key for the preference formulation
    pref_formulation_key = "pref_formulation_editor"
    
    # Get current formulation from preferences
    preferences = get_project_preferences(st.session_state.get('current_project_id'))
    current_formulation = preferences.get('formulation', '')
    
    # Initialize formulation in session state if not exists
    if f'formulation_data_{pref_formulation_key}' not in st.session_state:
        if current_formulation:
            try:
                st.session_state[f'formulation_data_{pref_formulation_key}'] = json.loads(current_formulation)
            except:
                st.session_state[f'formulation_data_{pref_formulation_key}'] = [{'Component': '', 'Dry Mass Fraction (%)': 0.0}]
        else:
            st.session_state[f'formulation_data_{pref_formulation_key}'] = [{'Component': '', 'Dry Mass Fraction (%)': 0.0}]
    
    # Render the formulation table using the same component as cell inputs
    # Note: We pass None for get_components_func to avoid duplicate functionality
    formulation = render_formulation_table(pref_formulation_key, st.session_state.get('current_project_id'), None)
    
    # Save/Cancel buttons - only show these, not the internal save button from render_formulation_table
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Save Default Formulation", key="save_pref_formulation", type="primary"):
            if formulation and any(comp.get('Component') for comp in formulation):
                formulation_json = json.dumps(formulation)
                preferences = get_project_preferences(st.session_state.get('current_project_id'))
                preferences['formulation'] = formulation_json
                save_project_preferences(st.session_state.get('current_project_id'), preferences)
                st.session_state.show_formulation_editor = False
                st.success("✅ Default formulation saved!")
                st.rerun()
            else:
                st.error("Please add at least one component to the formulation.")
    
    with col2:
        if st.button("❌ Cancel", key="cancel_pref_formulation"):
            st.session_state.show_formulation_editor = False
            st.rerun()

def get_default_values_for_experiment(project_id):
    """Get default values for a new experiment based on project preferences."""
    # Import database functions inside the function to avoid circular imports
    from database import get_project_preferences
    
    preferences = get_project_preferences(project_id)
    
    defaults = {
        'electrolyte': preferences.get('electrolyte', ''),
        'substrate': preferences.get('substrate', ''),
        'formation_cycles': int(preferences.get('formation_cycles', 4)),
        'formulation': []
    }
    
    # Parse formulation JSON
    formulation_str = preferences.get('formulation', '')
    if formulation_str:
        try:
            defaults['formulation'] = json.loads(formulation_str)
        except:
            defaults['formulation'] = []
    
    return defaults

def render_default_indicator(field_name, value):
    """Render a visual indicator that a field has been auto-populated from preferences."""
    if value:
        st.markdown(f"<small>📋 Default from project preferences</small>", unsafe_allow_html=True) 