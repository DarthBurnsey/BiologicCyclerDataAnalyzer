"""
Dashboard UI Components for CellScope

Streamlit components for rendering dashboard sections.
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Optional
from insights_engine import Insight, InsightSeverity
from datetime import date, timedelta


def render_dashboard_header(stats: Dict):
    """
    Render header cards with global statistics.
    
    Args:
        stats: Dictionary with total_projects, total_cells, best_retention_pct, etc.
    """
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📁 Total Projects",
            value=stats.get('total_projects', 0),
            delta=None
        )
    
    with col2:
        st.metric(
            label="🔬 Total Cells Tested",
            value=stats.get('total_cells', 0),
            delta=None
        )
    
    with col3:
        st.metric(
            label="🏆 Best Retention",
            value=f"{stats.get('best_retention_pct', 0):.1f}%",
            delta=None,
            help="Highest capacity retention across all cells"
        )
    
    with col4:
        st.metric(
            label="📉 Avg Degradation",
            value=f"{stats.get('avg_degradation_rate', 0):.2f}%",
            delta=None,
            help="Average fade rate per 100 cycles"
        )
    
    # Show most recent test date if available
    most_recent = stats.get('most_recent_test')
    if most_recent:
        st.caption(f"Most recent test: {most_recent}")


def render_filter_controls() -> Dict:
    """
    Render filter controls and return filter state.
    
    Returns:
        Dictionary with filter parameters
    """
    from database import get_user_projects, TEST_USER_ID
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Dashboard Filters")
    
    # Get all projects for filter
    all_projects = get_user_projects(TEST_USER_ID)
    
    # Project filter
    project_options = {p[0]: p[1] for p in all_projects}  # {id: name}
    
    if project_options:
        selected_project_ids = st.sidebar.multiselect(
            "Filter by Project",
            options=list(project_options.keys()),
            format_func=lambda x: project_options[x],
            default=[],
            help="Leave empty to show all projects"
        )
    else:
        selected_project_ids = []
    
    # Date range filter
    use_date_filter = st.sidebar.checkbox("Filter by Date Range", value=False)
    date_range = None
    
    if use_date_filter:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input(
                "From",
                value=date.today() - timedelta(days=90),
                key="dashboard_start_date"
            )
        with col2:
            end_date = st.date_input(
                "To",
                value=date.today(),
                key="dashboard_end_date"
            )
        date_range = (start_date, end_date)
    
    # Minimum cycles filter
    min_cycles = st.sidebar.slider(
        "Minimum Cycles",
        min_value=0,
        max_value=500,
        value=100,
        step=10,
        help="Only show cells with at least this many cycles"
    )
    
    return {
        'project_ids': selected_project_ids if selected_project_ids else None,
        'date_range': date_range,
        'min_cycles': min_cycles
    }


def render_project_summary_grid(project_summaries: List[Dict]):
    """
    Render project summary cards in a grid layout.
    
    Args:
        project_summaries: List of project summary dicts
    """
    if not project_summaries:
        st.info("No projects found. Create a project in the sidebar to get started!")
        return
    
    # Filter out projects with no cells for cleaner display
    projects_with_data = [p for p in project_summaries if p['cell_count'] > 0]
    
    if not projects_with_data:
        st.info("No project data available yet. Upload experiment data to see project summaries.")
        return
    
    # Create 2-column grid
    num_cols = 2
    cols_per_row = st.columns(num_cols)
    
    for idx, project in enumerate(projects_with_data):
        col = cols_per_row[idx % num_cols]
        
        with col:
            # Status emoji
            status_emoji = {
                'good': '🟢',
                'medium': '🟡',
                'bad': '🔴'
            }.get(project['status'], '⚪')
            
            # Card container
            with st.container():
                st.markdown(
                    f"""
                    <div style="
                        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
                        border: 2px solid #e2e8f0;
                        border-radius: 12px;
                        padding: 1.25rem;
                        margin-bottom: 1rem;
                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
                    ">
                        <h3 style="margin: 0 0 0.5rem 0; color: #1e293b;">
                            {status_emoji} {project['project_name']}
                        </h3>
                        <p style="margin: 0.25rem 0; color: #64748b; font-size: 0.875rem;">
                            <b>Type:</b> {project['project_type']}
                        </p>
                        <p style="margin: 0.25rem 0; color: #64748b; font-size: 0.875rem;">
                            <b>Cells Tested:</b> {project['cell_count']}
                        </p>
                        <p style="margin: 0.25rem 0; color: #64748b; font-size: 0.875rem;">
                            <b>Latest Cycle:</b> {project['latest_cycle']}
                        </p>
                        <p style="margin: 0.25rem 0; color: #64748b; font-size: 0.875rem;">
                            <b>Best Cell:</b> {project['best_cell_id']} ({project['best_retention_pct']:.1f}% retention)
                        </p>
                        <p style="margin: 0.25rem 0; color: #64748b; font-size: 0.875rem;">
                            <b>Avg Fade Rate:</b> {project['avg_fade_rate']:.2f}% / 100 cycles
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


def render_top_performers_table(top_cells_df: pd.DataFrame):
    """
    Render a styled table of top performing cells.
    
    Args:
        top_cells_df: DataFrame with top cell data
    """
    if top_cells_df.empty:
        st.info("No cells meet the minimum cycle criteria. Adjust filters to see more cells.")
        return
    
    # Add rank column
    top_cells_df = top_cells_df.copy()
    top_cells_df.insert(0, 'Rank', range(1, len(top_cells_df) + 1))
    
    # Add medal emojis for top 3
    medals = {1: '🥇', 2: '🥈', 3: '🥉'}
    top_cells_df['Rank'] = top_cells_df['Rank'].apply(lambda x: f"{medals.get(x, '')} {x}".strip())
    
    # Select columns to display
    display_df = top_cells_df[[
        'Rank', 'cell_id', 'project_name', 'cycles_tested',
        'retention_pct', 'fade_rate', 'initial_capacity'
    ]].copy()
    
    # Rename columns
    display_df.columns = [
        'Rank', 'Cell ID', 'Project', 'Cycles',
        'Retention (%)', 'Fade Rate (%/100cyc)', 'Initial Cap (mAh)'
    ]
    
    # Format numeric columns
    display_df['Retention (%)'] = display_df['Retention (%)'].apply(lambda x: f"{x:.2f}")
    display_df['Fade Rate (%/100cyc)'] = display_df['Fade Rate (%/100cyc)'].apply(lambda x: f"{x:.3f}")
    display_df['Initial Cap (mAh)'] = display_df['Initial Cap (mAh)'].apply(lambda x: f"{x:.2f}")
    
    # Display as table
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )


def render_insights_alerts(insights: List[Insight]):
    """
    Render actionable insights as styled alerts.
    
    Args:
        insights: List of Insight objects
    """
    if not insights:
        st.success("✅ All systems looking good! No critical issues detected.")
        return
    
    for insight in insights:
        # Map severity to Streamlit alert type
        if insight.severity == InsightSeverity.SUCCESS:
            with st.success(insight.title):
                st.markdown(insight.message)
                if insight.action_items:
                    st.markdown("**Suggested Actions:**")
                    for action in insight.action_items:
                        st.markdown(f"- {action}")
        
        elif insight.severity == InsightSeverity.WARNING:
            with st.warning(insight.title):
                st.markdown(insight.message)
                if insight.action_items:
                    st.markdown("**Suggested Actions:**")
                    for action in insight.action_items:
                        st.markdown(f"- {action}")
        
        elif insight.severity == InsightSeverity.ERROR:
            with st.error(insight.title):
                st.markdown(insight.message)
                if insight.action_items:
                    st.markdown("**Suggested Actions:**")
                    for action in insight.action_items:
                        st.markdown(f"- {action}")
        
        else:  # INFO
            with st.info(insight.title):
                st.markdown(insight.message)
                if insight.action_items:
                    st.markdown("**Suggested Actions:**")
                    for action in insight.action_items:
                        st.markdown(f"- {action}")
