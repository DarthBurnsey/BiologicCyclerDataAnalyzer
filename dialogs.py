import streamlit as st
from database import get_user_projects, delete_project, delete_cell_experiment, TEST_USER_ID

@st.dialog("⚠️ Confirm Project Deletion")
def confirm_delete_project():
    project_id = st.session_state['confirm_delete_project']
    user_projects = get_user_projects(TEST_USER_ID)
    project_name = next((p[1] for p in user_projects if p[0] == project_id), "this project")
    
    st.markdown(f"Are you sure you want to **permanently delete** the project **{project_name}**?")
    st.markdown("⚠️ This action cannot be undone and will delete all experiments in this project.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Yes, Delete", type="primary", use_container_width=True):
            try:
                delete_project(project_id)
                # Clear current project if it was deleted
                if st.session_state.get('current_project_id') == project_id:
                    st.session_state['current_project_id'] = None
                    st.session_state['current_project_name'] = None
                st.session_state['confirm_delete_project'] = None
                st.success(f"✅ Successfully deleted project '{project_name}'!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error deleting project: {str(e)}")
    
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.session_state['confirm_delete_project'] = None
            st.rerun()

@st.dialog("⚠️ Confirm Experiment Deletion")
def confirm_delete_experiment():
    experiment_id, experiment_name = st.session_state['confirm_delete_experiment']
    
    st.markdown(f"Are you sure you want to **permanently delete** the experiment **{experiment_name}**?")
    st.markdown("⚠️ This action cannot be undone.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Yes, Delete", type="primary", use_container_width=True):
            try:
                delete_cell_experiment(experiment_id)
                # Clear loaded experiment if it was deleted
                if (st.session_state.get('loaded_experiment') and 
                    st.session_state['loaded_experiment'].get('experiment_id') == experiment_id):
                    st.session_state['loaded_experiment'] = None
                st.session_state['confirm_delete_experiment'] = None
                st.success(f"✅ Successfully deleted experiment '{experiment_name}'!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error deleting experiment: {str(e)}")
    
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.session_state['confirm_delete_experiment'] = None
            st.rerun()

def show_delete_dialogs():
    """Show delete confirmation dialogs when triggered."""
    if st.session_state.get('confirm_delete_project'):
        confirm_delete_project()

    if st.session_state.get('confirm_delete_experiment'):
        confirm_delete_experiment()
