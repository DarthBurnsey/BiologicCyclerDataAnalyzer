"""
Interactive Plotting Module for CellScope

Provides Plotly-based interactive alternatives to matplotlib plots.
These plots offer zoom, pan, hover tooltips, and export capabilities.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional


def plot_interactive_capacity(
    dfs: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    show_efficiency_lines: Dict[str, bool],
    remove_last_cycle: bool,
    experiment_name: str,
    show_average: bool = False,
    avg_line_toggles: Optional[Dict[str, bool]] = None,
    group_names: Optional[list] = None,
    custom_colors: Optional[Dict[str, str]] = None
) -> go.Figure:
    """
    Create interactive capacity/efficiency plot using Plotly.
    
    Returns a Plotly Figure with hover tooltips, zoom, and pan capabilities.
    """
    if avg_line_toggles is None:
        avg_line_toggles = {"Average Q Dis": True, "Average Q Chg": True, "Average Efficiency": True}
    if group_names is None:
        group_names = ["Group A", "Group B", "Group C"]
    if custom_colors is None:
        custom_colors = {}
    
    # Check if efficiency is needed
    any_efficiency = any(show_efficiency_lines.values())
    
    # Default Plotly color palette
    plotly_colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
    ]
    
    if any_efficiency:
        # Create subplot with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Plot capacity lines
        for i, d in enumerate(dfs):
            try:
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_dis = f"{cell_name} Q Dis"
                label_chg = f"{cell_name} Q Chg"
                
                color = custom_colors.get(cell_name, plotly_colors[i % len(plotly_colors)])
                
                plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                x_col = plot_df.columns[0]
                
                # Plot discharge capacity
                if show_lines.get(label_dis, False) and 'Q Dis (mAh/g)' in plot_df.columns:
                    qdis_data = pd.to_numeric(plot_df['Q Dis (mAh/g)'], errors='coerce')
                    valid_mask = ~qdis_data.isna()
                    
                    if valid_mask.any():
                        fig.add_trace(
                            go.Scatter(
                                x=plot_df[x_col][valid_mask],
                                y=qdis_data[valid_mask],
                                name=label_dis,
                                mode='lines+markers',
                                line=dict(color=color),
                                marker=dict(size=4),
                                hovertemplate=(
                                    f"<b>{cell_name}</b><br>"
                                    "Cycle: %{x}<br>"
                                    "Q Dis: %{y:.2f} mAh/g<br>"
                                    "<extra></extra>"
                                )
                            ),
                            secondary_y=False
                        )
                
                # Plot charge capacity
                if show_lines.get(label_chg, False) and 'Q Chg (mAh/g)' in plot_df.columns:
                    qchg_data = pd.to_numeric(plot_df['Q Chg (mAh/g)'], errors='coerce')
                    valid_mask = ~qchg_data.isna()
                    
                    if valid_mask.any():
                        fig.add_trace(
                            go.Scatter(
                                x=plot_df[x_col][valid_mask],
                                y=qchg_data[valid_mask],
                                name=label_chg,
                                mode='lines+markers',
                                line=dict(color=color, dash='dash'),
                                marker=dict(size=4),
                                hovertemplate=(
                                    f"<b>{cell_name}</b><br>"
                                    "Cycle: %{x}<br>"
                                    "Q Chg: %{y:.2f} mAh/g<br>"
                                    "<extra></extra>"
                                )
                            ),
                            secondary_y=False
                        )
            except Exception:
                pass
        
        # Plot efficiency lines
        for i, d in enumerate(dfs):
            try:
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_eff = f"{cell_name} Efficiency"
                
                color = custom_colors.get(cell_name, plotly_colors[i % len(plotly_colors)])
                
                plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                x_col = plot_df.columns[0]
                
                if show_efficiency_lines.get(label_eff, False) and 'Efficiency (-)' in plot_df.columns:
                    eff_data = pd.to_numeric(plot_df['Efficiency (-)'], errors='coerce') * 100
                    valid_mask = ~eff_data.isna()
                    
                    if valid_mask.any():
                        fig.add_trace(
                            go.Scatter(
                                x=plot_df[x_col][valid_mask],
                                y=eff_data[valid_mask],
                                name=f'{cell_name} Eff',
                                mode='lines+markers',
                                line=dict(color=color, dash='dot'),
                                marker=dict(size=3, symbol='square'),
                                opacity=0.7,
                                hovertemplate=(
                                    f"<b>{cell_name}</b><br>"
                                    "Cycle: %{x}<br>"
                                    "Efficiency: %{y:.2f}%<br>"
                                    "<extra></extra>"
                                )
                            ),
                            secondary_y=True
                        )
            except Exception:
                pass
        
        # Update axes
        fig.update_xaxes(title_text="Cycle Number")
        fig.update_yaxes(title_text="Capacity (mAh/g)", secondary_y=False, color='blue')
        fig.update_yaxes(title_text="Efficiency (%)", secondary_y=True, color='red')
        
    else:
        # Single y-axis plot
        fig = go.Figure()
        
        for i, d in enumerate(dfs):
            try:
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_dis = f"{cell_name} Q Dis"
                label_chg = f"{cell_name} Q Chg"
                
                color = custom_colors.get(cell_name, plotly_colors[i % len(plotly_colors)])
                
                plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                x_col = plot_df.columns[0]
                
                # Plot discharge capacity
                if show_lines.get(label_dis, False) and 'Q Dis (mAh/g)' in plot_df.columns:
                    qdis_data = pd.to_numeric(plot_df['Q Dis (mAh/g)'], errors='coerce')
                    valid_mask = ~qdis_data.isna()
                    
                    if valid_mask.any():
                        fig.add_trace(
                            go.Scatter(
                                x=plot_df[x_col][valid_mask],
                                y=qdis_data[valid_mask],
                                name=label_dis,
                                mode='lines+markers',
                                line=dict(color=color),
                                marker=dict(size=4),
                                hovertemplate=(
                                    f"<b>{cell_name}</b><br>"
                                    "Cycle: %{x}<br>"
                                    "Q Dis: %{y:.2f} mAh/g<br>"
                                    "<extra></extra>"
                                )
                            )
                        )
                
                # Plot charge capacity
                if show_lines.get(label_chg, False) and 'Q Chg (mAh/g)' in plot_df.columns:
                    qchg_data = pd.to_numeric(plot_df['Q Chg (mAh/g)'], errors='coerce')
                    valid_mask = ~qchg_data.isna()
                    
                    if valid_mask.any():
                        fig.add_trace(
                            go.Scatter(
                                x=plot_df[x_col][valid_mask],
                                y=qchg_data[valid_mask],
                                name=label_chg,
                                mode='lines+markers',
                                line=dict(color=color, dash='dash'),
                                marker=dict(size=4),
                                hovertemplate=(
                                    f"<b>{cell_name}</b><br>"
                                    "Cycle: %{x}<br>"
                                    "Q Chg: %{y:.2f} mAh/g<br>"
                                    "<extra></extra>"
                                )
                            )
                        )
            except Exception:
                pass
        
        fig.update_xaxes(title_text="Cycle Number")
        fig.update_yaxes(title_text="Capacity (mAh/g)")
    
    # Update layout
    title = f"{experiment_name} - Capacity vs. Cycle" if experiment_name else "Capacity vs. Cycle"
    fig.update_layout(
        title=title,
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
    
    return fig


def plot_interactive_retention(
    dfs: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    reference_cycle: int,
    remove_last_cycle: bool,
    experiment_name: str,
    show_average: bool = False,
    custom_colors: Optional[Dict[str, str]] = None,
    retention_threshold: float = 80.0
) -> go.Figure:
    """
    Create interactive capacity retention plot using Plotly.
    """
    if custom_colors is None:
        custom_colors = {}
    
    # Default Plotly color palette
    plotly_colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
    ]
    
    fig = go.Figure()
    
    # Plot individual cells
    for i, d in enumerate(dfs):
        try:
            cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
            color = custom_colors.get(cell_name, plotly_colors[i % len(plotly_colors)])
            
            plot_df = d['df'][:-1] if remove_last_cycle else d['df']
            x_col = plot_df.columns[0]
            
            # Calculate retention for discharge capacity
            if show_lines.get(f"{cell_name} Q Dis", False) and 'Q Dis (mAh/g)' in plot_df.columns:
                qdis_data = pd.to_numeric(plot_df['Q Dis (mAh/g)'], errors='coerce')
                valid_mask = ~qdis_data.isna()
                
                if valid_mask.any():
                    # Find reference capacity
                    ref_data = plot_df[plot_df[x_col] == reference_cycle]
                    if not ref_data.empty:
                        ref_capacity = pd.to_numeric(ref_data['Q Dis (mAh/g)'].iloc[0], errors='coerce')
                        if not pd.isna(ref_capacity) and ref_capacity > 0:
                            retention_data = (qdis_data / ref_capacity) * 100
                            
                            fig.add_trace(
                                go.Scatter(
                                    x=plot_df[x_col][valid_mask],
                                    y=retention_data[valid_mask],
                                    name=f"{cell_name}",
                                    mode='lines+markers',
                                    line=dict(color=color),
                                    marker=dict(size=4),
                                    hovertemplate=(
                                        f"<b>{cell_name}</b><br>"
                                        "Cycle: %{x}<br>"
                                        "Retention: %{y:.2f}%<br>"
                                        "<extra></extra>"
                                    )
                                )
                            )
        except Exception:
            pass
    
    # Add reference lines
    fig.add_hline(
        y=100,
        line_dash="solid",
        line_color="black",
        opacity=0.3,
        annotation_text="100% Baseline",
        annotation_position="right"
    )
    
    fig.add_hline(
        y=retention_threshold,
        line_dash="dash",
        line_color="red",
        opacity=0.7,
        annotation_text=f"{retention_threshold}% Threshold",
        annotation_position="right"
    )
    
    fig.add_vline(
        x=reference_cycle,
        line_dash="dot",
        line_color="green",
        opacity=0.7,
        annotation_text=f"Ref Cycle ({reference_cycle})",
        annotation_position="top"
    )
    
    # Update layout
    title = f"{experiment_name} - Capacity Retention" if experiment_name else "Capacity Retention"
    fig.update_layout(
        title=title,
        xaxis_title="Cycle Number",
        yaxis_title="Capacity Retention (%)",
        hovermode='closest',
        template='plotly_white',
        height=600,
        yaxis=dict(range=[0, 110]),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
            bgcolor="rgba(255, 255, 255, 0.8)"
        )
    )
    
    return fig
