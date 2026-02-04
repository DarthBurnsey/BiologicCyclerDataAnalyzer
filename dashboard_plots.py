"""
Dashboard Visualization Functions for CellScope

Interactive plots using Plotly for battery performance analysis.
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import List, Dict, Optional


def plot_multi_project_retention(
    cells_data: List[Dict],
    group_by: str = 'project',
    show_average: bool = True,
    max_cells_per_group: int = 10
) -> go.Figure:
    """
    Create interactive capacity retention curves for multiple cells.
    
    Args:
        cells_data: List of cell data dicts with cycling info
        group_by: 'project', 'cell', or 'none'
        show_average: Whether to show average line per group
        max_cells_per_group: Limit cells plotted per project
    
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    if not cells_data:
        fig.add_annotation(
            text="No cycling data available. Upload experiment data to see performance trends.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            template='plotly_white',
            height=600,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig
    
    # Color palette
    colors = px.colors.qualitative.Set2
    project_colors = {}
    color_idx = 0
    
    # Group cells
    if group_by == 'project':
        grouped = {}
        for cell in cells_data:
            project = cell.get('project_name', 'Unknown')
            if project not in grouped:
                grouped[project] = []
            grouped[project].append(cell)
    else:
        grouped = {'All Cells': cells_data}
    
    # Plot each group
    for group_name, cells in grouped.items():
        # Assign color
        if group_name not in project_colors:
            project_colors[group_name] = colors[color_idx % len(colors)]
            color_idx += 1
        
        base_color = project_colors[group_name]
        
        # Limit cells per group
        cells = cells[:max_cells_per_group]
        
        # Plot individual cells
        all_cycles = []
        all_retentions = []
        
        for i, cell in enumerate(cells):
            try:
                df = pd.read_json(cell['data_json'])
                
                # Detect column names
                cap_col = None
                if 'Qdis' in df.columns:
                    cap_col = 'Qdis'
                elif 'Q discharge (mA.h)' in df.columns:
                    cap_col = 'Q discharge (mA.h)'
                elif 'Q Dis (mAh/g)' in df.columns:
                    cap_col = 'Q Dis (mAh/g)'
                
                cycle_col = None
                if 'Cycle' in df.columns:
                    cycle_col = 'Cycle'
                elif 'Cycle number' in df.columns:
                    cycle_col = 'Cycle number'
                
                # Calculate retention
                if cap_col and cycle_col:
                    valid_data = df[df[cap_col] > 0].copy()
                    if len(valid_data) < 2:
                        continue
                    
                    initial_cap = valid_data[cap_col].iloc[0]
                    valid_data['retention'] = (valid_data[cap_col] / initial_cap) * 100
                    
                    cycles = valid_data[cycle_col].values
                    retention = valid_data['retention'].values
                    
                    all_cycles.append(cycles)
                    all_retentions.append(retention)
                    
                    # Plot line
                    fig.add_trace(go.Scatter(
                        x=cycles,
                        y=retention,
                        mode='lines',
                        name=f"{cell.get('cell_id', 'Cell')} ({group_name})",
                        line=dict(color=base_color, width=1.5),
                        opacity=0.6,
                        hovertemplate=(
                            f"<b>{cell.get('cell_id', 'Cell')}</b><br>"
                            f"Project: {group_name}<br>"
                            "Cycle: %{x}<br>"
                            "Retention: %{y:.2f}%<br>"
                            "<extra></extra>"
                        ),
                        legendgroup=group_name,
                        showlegend=(i == 0)  # Only show first cell of group in legend
                    ))
            except Exception:
                continue
        
        # Plot average if requested
        if show_average and all_cycles:
            try:
                # Interpolate to common cycle grid
                max_cycle = max(c[-1] for c in all_cycles if len(c) > 0)
                common_cycles = np.arange(0, max_cycle + 1, 10)
                
                interpolated_retentions = []
                for cycles, retention in zip(all_cycles, all_retentions):
                    interp_ret = np.interp(common_cycles, cycles, retention)
                    interpolated_retentions.append(interp_ret)
                
                avg_retention = np.mean(interpolated_retentions, axis=0)
                
                fig.add_trace(go.Scatter(
                    x=common_cycles,
                    y=avg_retention,
                    mode='lines',
                    name=f"{group_name} (Average)",
                    line=dict(color=base_color, width=3, dash='dash'),
                    hovertemplate=(
                        f"<b>{group_name} Average</b><br>"
                        "Cycle: %{x}<br>"
                        "Avg Retention: %{y:.2f}%<br>"
                        "<extra></extra>"
                    ),
                    legendgroup=group_name,
                    showlegend=True
                ))
            except Exception:
                pass
    
    # Add reference line at 80% retention
    fig.add_hline(
        y=80,
        line_dash="dot",
        line_color="red",
        opacity=0.5,
        annotation_text="80% Target",
        annotation_position="right"
    )
    
    # Layout
    fig.update_layout(
        title="Capacity Retention vs. Cycle Number",
        xaxis_title="Cycle Number",
        yaxis_title="Capacity Retention (%)",
        hovermode='closest',
        template='plotly_white',
        height=600,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
            bgcolor="rgba(255, 255, 255, 0.8)"
        )
    )
    
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray', range=[70, 105])
    
    return fig


def plot_fade_rate_scatter(
    cells_data: List[Dict],
    x_axis: str = 'initial_capacity',
    color_by: str = 'project'
) -> go.Figure:
    """
    Create scatter plot of fade rate vs. another variable.
    
    Args:
        cells_data: List of cell data dicts
        x_axis: 'initial_capacity', 'temperature', or 'c_rate'
        color_by: 'project' or 'chemistry'
    
    Returns:
        Plotly Figure object
    """
    # Prepare data
    from dashboard_analytics import calculate_fade_rate
    
    plot_data = []
    
    for cell in cells_data:
        try:
            df = pd.read_json(cell['data_json'])
            
            # Detect column names
            cap_col = None
            if 'Qdis' in df.columns:
                cap_col = 'Qdis'
            elif 'Q discharge (mA.h)' in df.columns:
                cap_col = 'Q discharge (mA.h)'
            elif 'Q Dis (mAh/g)' in df.columns:
                cap_col = 'Q Dis (mAh/g)'
            
            cycle_col = None
            if 'Cycle' in df.columns:
                cycle_col = 'Cycle'
            elif 'Cycle number' in df.columns:
                cycle_col = 'Cycle number'
            
            # Calculate fade rate
            if cap_col and cycle_col:
                fade_rate = calculate_fade_rate(df)
                
                if fade_rate is None:
                    continue
                
                # Get x-axis value
                if x_axis == 'initial_capacity':
                    x_val = df[cap_col].iloc[0] if len(df) > 0 else None
                elif x_axis == 'temperature':
                    x_val = cell.get('temperature', 25)  # Default 25C
                elif x_axis == 'c_rate':
                    x_val = cell.get('c_rate', 1.0)  # Default 1C
                else:
                    x_val = None
                
                if x_val is None or x_val <= 0:
                    continue
                
                # Calculate retention for hover info
                valid_caps = df[df[cap_col] > 0][cap_col]
                if len(valid_caps) < 2:
                    retention = 0
                else:
                    retention = (valid_caps.iloc[-1] / valid_caps.iloc[0]) * 100
                
                cycles_tested = df[cycle_col].max()
                
                plot_data.append({
                    'cell_id': cell.get('cell_id', 'Unknown'),
                    'project': cell.get('project_name', 'Unknown'),
                    'x_value': x_val,
                    'fade_rate': fade_rate,
                    'retention': retention,
                    'cycles': cycles_tested
                })
        except Exception:
            continue
    
    if not plot_data:
        # Return empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for fade rate analysis. Cells need at least 10 cycles with discharge capacity data.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            template='plotly_white',
            height=500,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig
    
    df_plot = pd.DataFrame(plot_data)
    
    # Create scatter plot
    fig = px.scatter(
        df_plot,
        x='x_value',
        y='fade_rate',
        color='project' if color_by == 'project' else 'cell_id',
        size='cycles',
        hover_data={
            'cell_id': True,
            'project': True,
            'retention': ':.2f',
            'cycles': True,
            'x_value': ':.2f',
            'fade_rate': ':.3f'
        },
        labels={
            'x_value': 'Initial Capacity (mAh)' if x_axis == 'initial_capacity' else x_axis.replace('_', ' ').title(),
            'fade_rate': 'Fade Rate (% / 100 cycles)',
            'project': 'Project'
        },
        title=f"Fade Rate vs. {x_axis.replace('_', ' ').title()}"
    )
    
    # Add trend line
    try:
        from scipy.stats import linregress
        slope, intercept, r_value, p_value, std_err = linregress(df_plot['x_value'], df_plot['fade_rate'])
        
        x_trend = np.linspace(df_plot['x_value'].min(), df_plot['x_value'].max(), 100)
        y_trend = slope * x_trend + intercept
        
        fig.add_trace(go.Scatter(
            x=x_trend,
            y=y_trend,
            mode='lines',
            name=f'Trend (R²={r_value**2:.3f})',
            line=dict(color='black', dash='dash', width=2),
            hovertemplate="<extra></extra>"
        ))
    except:
        pass
    
    # Layout
    fig.update_layout(
        template='plotly_white',
        height=500,
        hovermode='closest'
    )
    
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    
    return fig


def plot_project_comparison_bar(project_summaries: List[Dict]) -> go.Figure:
    """
    Create bar chart comparing average metrics across projects.
    
    Args:
        project_summaries: List of project summary dicts
    
    Returns:
        Plotly Figure object
    """
    df = pd.DataFrame(project_summaries)
    
    if df.empty or len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No project data available. Create a project and upload experiments to see comparisons.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            template='plotly_white',
            height=400,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig
    
    # Filter projects with cells
    df = df[df['cell_count'] > 0]
    
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No projects with cell data. Upload cycling data to enable comparisons.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            template='plotly_white',
            height=400,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig
    
    # Sort by best retention
    df = df.sort_values('best_retention_pct', ascending=True)
    
    # Color code by status
    colors = df['status'].map({
        'good': '#10b981',   # green
        'medium': '#f59e0b', # yellow
        'bad': '#ef4444'     # red
    })
    
    # Create bar chart
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['best_retention_pct'],
        y=df['project_name'],
        orientation='h',
        marker=dict(color=colors),
        text=df['best_retention_pct'].apply(lambda x: f"{x:.1f}%"),
        textposition='outside',
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Best Retention: %{x:.2f}%<br>"
            "Cells Tested: %{customdata[0]}<br>"
            "Avg Fade Rate: %{customdata[1]:.3f}%/100cyc<br>"
            "<extra></extra>"
        ),
        customdata=df[['cell_count', 'avg_fade_rate']].values
    ))
    
    # Layout
    fig.update_layout(
        title="Project Performance Comparison (Best Retention)",
        xaxis_title="Best Capacity Retention (%)",
        yaxis_title="Project",
        template='plotly_white',
        height=max(400, len(df) * 40),
        showlegend=False
    )
    
    fig.update_xaxes(range=[0, 105])
    
    return fig


def plot_activity_timeline(activity_data: List[Dict]) -> go.Figure:
    """
    Create timeline bar chart of experiment activity.
    
    Args:
        activity_data: List of dicts with 'date' and 'count'
    
    Returns:
        Plotly Figure object
    """
    df = pd.DataFrame(activity_data)
    
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No recent activity in the last 30 days.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            template='plotly_white',
            height=300,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig
    
    df['date'] = pd.to_datetime(df['date'])
    
    # Create bar chart
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['date'],
        y=df['count'],
        marker=dict(
            color=df['count'],
            colorscale='Blues',
            showscale=True,
            colorbar=dict(title="Uploads")
        ),
        hovertemplate=(
            "Date: %{x|%Y-%m-%d}<br>"
            "Experiments: %{y}<br>"
            "<extra></extra>"
        )
    ))
    
    # Layout
    fig.update_layout(
        title="Experiment Upload Activity (Last 30 Days)",
        xaxis_title="Date",
        yaxis_title="Number of Experiments",
        template='plotly_white',
        height=300,
        showlegend=False
    )
    
    return fig
