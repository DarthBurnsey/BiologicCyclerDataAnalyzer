"""
Interactive Plotting Module for CellScope

Provides Plotly-based interactive alternatives to matplotlib plots.
These plots offer zoom, pan, hover tooltips, and export capabilities.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple


def _filter_dfs_by_cycle_range(
    dfs: List[Dict[str, Any]],
    cycle_filter: str = "1-*"
) -> List[Dict[str, Any]]:
    """Apply the same cycle-range filtering used by the static plots."""
    try:
        from ui_components import parse_cycle_filter
    except ImportError:
        def parse_cycle_filter(cf, max_cycle):
            return list(range(1, max_cycle + 1))

    filtered_dfs = []
    for d in dfs:
        df = d['df'].copy()
        if not df.empty:
            max_cycle = int(df.iloc[:, 0].max()) if not df.empty else 1
            cycles_to_include = parse_cycle_filter(cycle_filter, max_cycle)
            cycle_col = df.columns[0]
            df_filtered = df[df[cycle_col].isin(cycles_to_include)]
            if not df_filtered.empty:
                filtered_dfs.append({**d, 'df': df_filtered})
        else:
            filtered_dfs.append(d)

    return filtered_dfs


def plot_interactive_capacity(
    dfs: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    show_efficiency_lines: Dict[str, bool],
    remove_last_cycle: bool,
    experiment_name: str,
    show_average: bool = False,
    avg_line_toggles: Optional[Dict[str, bool]] = None,
    group_names: Optional[list] = None,
    custom_colors: Optional[Dict[str, str]] = None,
    excluded_from_average: Optional[List[str]] = None,
    cycle_filter: str = "1-*",
    y_axis_limits: Optional[Tuple[float, float]] = None
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
    if excluded_from_average is None:
        excluded_from_average = []

    dfs = _filter_dfs_by_cycle_range(dfs, cycle_filter)
        
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
    
    # Plot average if requested
    if show_average and len(dfs) > 1:
        # Filter dfs based on excluded_from_average
        included_dfs = []
        for i, d in enumerate(dfs):
            cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
            if cell_name not in excluded_from_average:
                included_dfs.append(d)
        
        if len(included_dfs) > 0:
            dfs_trimmed = [d['df'][:-1] if remove_last_cycle else d['df'] for d in included_dfs]
            x_col = dfs_trimmed[0].columns[0]
            common_cycles = set(dfs_trimmed[0][x_col])
            for df in dfs_trimmed[1:]:
                common_cycles = common_cycles & set(df[x_col])
            common_cycles = sorted(list(common_cycles))
            
            if common_cycles:
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
                                try:
                                    qdis_vals.append(float(row['Q Dis (mAh/g)'].values[0]))
                                except Exception: pass
                            if 'Q Chg (mAh/g)' in row:
                                try:
                                    qchg_vals.append(float(row['Q Chg (mAh/g)'].values[0]))
                                except Exception: pass
                            if 'Efficiency (-)' in row:
                                try:
                                    eff_vals.append(float(row['Efficiency (-)'].values[0]) * 100)
                                except Exception: pass
                    
                    avg_qdis.append(sum(qdis_vals)/len(qdis_vals) if qdis_vals else None)
                    avg_qchg.append(sum(qchg_vals)/len(qchg_vals) if qchg_vals else None)
                    avg_eff.append(sum(eff_vals)/len(eff_vals) if eff_vals else None)
                
                avg_label_prefix = f"{experiment_name} " if experiment_name else ""
                avg_color = custom_colors.get("Average", "black")
                
                # Plot averages
                if avg_line_toggles.get("Average Q Dis", True):
                    # We have to handle `secondary_y` arg properly if we are in make_subplots mode
                    trace_args = dict(secondary_y=False) if any_efficiency else dict()
                    fig.add_trace(go.Scatter(
                        x=common_cycles, y=avg_qdis, name=f'{avg_label_prefix}Avg Q Dis',
                        mode='lines+markers', line=dict(color=avg_color, width=3),
                        marker=dict(symbol='diamond', size=6),
                        hovertemplate="<b>%{name}</b><br>Cycle: %{x}<br>Q Dis: %{y:.2f} mAh/g<extra></extra>"
                    ), **trace_args)
                
                if avg_line_toggles.get("Average Q Chg", True):
                    trace_args = dict(secondary_y=False) if any_efficiency else dict()
                    fig.add_trace(go.Scatter(
                        x=common_cycles, y=avg_qchg, name=f'{avg_label_prefix}Avg Q Chg',
                        mode='lines+markers', line=dict(color='gray', width=3, dash='dash'),
                        marker=dict(symbol='diamond', size=6),
                        hovertemplate="<b>%{name}</b><br>Cycle: %{x}<br>Q Chg: %{y:.2f} mAh/g<extra></extra>"
                    ), **trace_args)
                
                if any_efficiency and avg_line_toggles.get("Average Efficiency", True):
                    fig.add_trace(go.Scatter(
                        x=common_cycles, y=avg_eff, name=f'{avg_label_prefix}Avg Eff (%)',
                        mode='lines+markers', line=dict(color='orange', width=3, dash='dot'),
                        marker=dict(symbol='diamond', size=6),
                        hovertemplate="<b>%{name}</b><br>Cycle: %{x}<br>Eff: %{y:.2f}%<extra></extra>"
                    ), secondary_y=True)
    
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

    if y_axis_limits is not None and y_axis_limits != (None, None):
        y_min, y_max = y_axis_limits
        if y_min is not None and y_max is not None:
            if any_efficiency:
                fig.update_yaxes(range=[y_min, y_max], secondary_y=False)
            else:
                fig.update_yaxes(range=[y_min, y_max])
    
    return fig


def plot_interactive_retention(
    dfs: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    reference_cycle: int,
    remove_last_cycle: bool,
    experiment_name: str,
    show_average: bool = False,
    custom_colors: Optional[Dict[str, str]] = None,
    retention_threshold: float = 80.0,
    cycle_filter: str = "1-*",
    y_axis_min: Optional[float] = 0.0,
    y_axis_max: Optional[float] = 110.0
) -> go.Figure:
    """
    Create interactive capacity retention plot using Plotly.
    """
    if custom_colors is None:
        custom_colors = {}

    dfs = _filter_dfs_by_cycle_range(dfs, cycle_filter)
    
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
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
            bgcolor="rgba(255, 255, 255, 0.8)"
        )
    )

    if y_axis_min is not None and y_axis_max is not None:
        fig.update_yaxes(range=[y_axis_min, y_axis_max])
    
    return fig


def plot_interactive_comparison_capacity(
    experiments_data: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    show_efficiency_lines: Dict[str, bool],
    remove_last_cycle: bool,
    show_graph_title: bool,
    show_average_performance: bool = False,
    avg_line_toggles: Optional[Dict[str, bool]] = None,
    hide_legend: bool = False,
    cycle_filter: str = "1-*",
    custom_colors: Optional[Dict[str, str]] = None,
    y_axis_limits: Optional[tuple] = None,
    custom_names: Optional[Dict[str, str]] = None,
    custom_title: str = "Capacity Data Comparison",
    excluded_from_average: Optional[List[str]] = None
) -> go.Figure:
    """
    Create interactive comparison capacity/efficiency plot using Plotly.
    """
    if avg_line_toggles is None:
        avg_line_toggles = {"Average Q Dis": True, "Average Q Chg": True, "Average Efficiency": True}
    if custom_colors is None:
        custom_colors = {}
    if custom_names is None:
        custom_names = {}
    if excluded_from_average is None:
        excluded_from_average = []
        
    # Apply cycle filtering to all experiments
    # Local import is fine here or rely on the filter logic
    try:
        from ui_components import parse_cycle_filter
    except ImportError:
        def parse_cycle_filter(cf, max_cycle): return list(range(1, max_cycle + 1))

    filtered_experiments_data = []
    for exp_data in experiments_data:
        filtered_dfs = []
        for d in exp_data['dfs']:
            df = d['df'].copy()
            if not df.empty:
                max_cycle = int(df.iloc[:, 0].max()) if not df.empty else 1
                cycles_to_include = parse_cycle_filter(cycle_filter, max_cycle)
                cycle_col = df.columns[0]
                df_filtered = df[df[cycle_col].isin(cycles_to_include)]
                if not df_filtered.empty:
                    filtered_dfs.append({**d, 'df': df_filtered})
            else:
                filtered_dfs.append(d)
        filtered_experiments_data.append({**exp_data, 'dfs': filtered_dfs})
    experiments_data = filtered_experiments_data

    # Check if any efficiency lines should be shown
    any_efficiency = any(show_efficiency_lines.values())
    avg_eff_on = show_average_performance and avg_line_toggles and avg_line_toggles.get("Average Efficiency", False)

    # Base colors for experiments
    plotly_colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
    ]

    if any_efficiency or avg_eff_on:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    else:
        fig = go.Figure()
        
    x_col = 'Cycle'
    if experiments_data and experiments_data[0]['dfs']:
        x_col = experiments_data[0]['dfs'][0]['df'].columns[0]

    for exp_idx, exp_data in enumerate(experiments_data):
        exp_name = exp_data['experiment_name']
        dfs = exp_data['dfs']
        default_exp_color = plotly_colors[exp_idx % len(plotly_colors)]
        
        if not show_average_performance:
            for cell_idx, d in enumerate(dfs):
                try:
                    cell_name = d['testnum'] if d['testnum'] else f'Cell {cell_idx+1}'
                    # Keep dataset_label as is for indexing custom attributes
                    dataset_label = f"{exp_name} - {cell_name}"
                    display_base_label = custom_names.get(dataset_label, cell_name)
                    
                    label_dis = f"{exp_name} - {cell_name} Q Dis"
                    label_chg = f"{exp_name} - {cell_name} Q Chg"
                    label_eff = f"{exp_name} - {cell_name} Efficiency"
                    
                    disp_label_dis = f"{display_base_label} Q Dis"
                    disp_label_chg = f"{display_base_label} Q Chg"
                    disp_label_eff = f"{display_base_label} Efficiency"
                    
                    cell_color = custom_colors.get(dataset_label, default_exp_color)
                    
                    plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                    dataset_x_col = plot_df.columns[0]
                    
                    if show_lines.get(label_dis, False) and 'Q Dis (mAh/g)' in plot_df.columns:
                        qdis_data = pd.to_numeric(plot_df['Q Dis (mAh/g)'], errors='coerce')
                        valid_mask = ~qdis_data.isna()
                        if valid_mask.any():
                            trace = go.Scatter(
                                x=plot_df[dataset_x_col][valid_mask],
                                y=qdis_data[valid_mask],
                                name=disp_label_dis,
                                mode='lines+markers',
                                line=dict(color=cell_color),
                                marker=dict(size=4),
                                opacity=0.7,
                                hovertemplate=(
                                    f"<b>{display_base_label}</b><br>"
                                    "Cycle: %{x}<br>Q Dis: %{y:.2f} mAh/g<br><extra></extra>"
                                )
                            )
                            if any_efficiency or avg_eff_on:
                                fig.add_trace(trace, secondary_y=False)
                            else:
                                fig.add_trace(trace)
                    
                    if show_lines.get(label_chg, False) and 'Q Chg (mAh/g)' in plot_df.columns:
                        qchg_data = pd.to_numeric(plot_df['Q Chg (mAh/g)'], errors='coerce')
                        valid_mask = ~qchg_data.isna()
                        if valid_mask.any():
                            trace = go.Scatter(
                                x=plot_df[dataset_x_col][valid_mask],
                                y=qchg_data[valid_mask],
                                name=disp_label_chg,
                                mode='lines+markers',
                                line=dict(color=cell_color, dash='dash'),
                                marker=dict(size=4),
                                opacity=0.7,
                                hovertemplate=(
                                    f"<b>{display_base_label}</b><br>"
                                    "Cycle: %{x}<br>Q Chg: %{y:.2f} mAh/g<br><extra></extra>"
                                )
                            )
                            if any_efficiency or avg_eff_on:
                                fig.add_trace(trace, secondary_y=False)
                            else:
                                fig.add_trace(trace)
                                
                    if (any_efficiency or avg_eff_on) and show_efficiency_lines.get(label_eff, False) and 'Efficiency (-)' in plot_df.columns:
                        efficiency_pct = pd.to_numeric(plot_df['Efficiency (-)'], errors='coerce') * 100
                        valid_mask = ~efficiency_pct.isna()
                        if valid_mask.any():
                            fig.add_trace(
                                go.Scatter(
                                    x=plot_df[dataset_x_col][valid_mask],
                                    y=efficiency_pct[valid_mask],
                                    name=disp_label_eff,
                                    mode='lines+markers',
                                    line=dict(color=cell_color, dash='dot'),
                                    marker=dict(size=3, symbol='square'),
                                    opacity=0.5,
                                    hovertemplate=(
                                        f"<b>{display_base_label}</b><br>"
                                        "Cycle: %{x}<br>Efficiency: %{y:.2f}%<br><extra></extra>"
                                    )
                                ),
                                secondary_y=True
                            )
                except Exception:
                    pass

        if show_average_performance and len(dfs) >= 1:
            try:
                included_dfs = []
                for i, d in enumerate(dfs):
                    cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                    dataset_label = f"{exp_name} - {cell_name}"
                    if dataset_label not in excluded_from_average:
                        included_dfs.append(d)
                
                if len(included_dfs) > 0:
                    dfs_trimmed = [d['df'][:-1] if remove_last_cycle else d['df'] for d in included_dfs]
                    exp_x_col = dfs_trimmed[0].columns[0] if not dfs_trimmed[0].empty else x_col
                
                common_cycles = set(dfs_trimmed[0][exp_x_col])
                for df in dfs_trimmed[1:]:
                    common_cycles = common_cycles & set(df[exp_x_col])
                common_cycles = sorted(list(common_cycles))
                
                if common_cycles:
                    avg_qdis, avg_qchg, avg_eff = [], [], []
                    for cycle in common_cycles:
                        qdis_vals, qchg_vals, eff_vals = [], [], []
                        for df in dfs_trimmed:
                            row = df[df[exp_x_col] == cycle]
                            if not row.empty:
                                if 'Q Dis (mAh/g)' in row:
                                    try: qdis_vals.append(float(row['Q Dis (mAh/g)'].values[0]))
                                    except: pass
                                if 'Q Chg (mAh/g)' in row:
                                    try: qchg_vals.append(float(row['Q Chg (mAh/g)'].values[0]))
                                    except: pass
                                if 'Efficiency (-)' in row and pd.notnull(row['Efficiency (-)'].values[0]):
                                    try: eff_vals.append(float(row['Efficiency (-)'].values[0]) * 100)
                                    except: pass
                        
                        avg_qdis.append(sum(qdis_vals)/len(qdis_vals) if qdis_vals else None)
                        avg_qchg.append(sum(qchg_vals)/len(qchg_vals) if qchg_vals else None)
                        avg_eff.append(sum(eff_vals)/len(eff_vals) if eff_vals else None)
                    
                    if len(dfs) == 1:
                        avg_label = f"{exp_name}"
                        label_suffix = ""
                    else:
                        avg_label = f"{exp_name} - Average"
                        label_suffix = " - Average"
                    
                    display_avg_label = custom_names.get(avg_label, f"{exp_name}{label_suffix}")
                    
                    avg_color = custom_colors.get(avg_label, default_exp_color)
                    
                    if avg_line_toggles.get("Average Q Dis", True):
                        trace = go.Scatter(
                            x=common_cycles, y=avg_qdis,
                            name=f'{display_avg_label} Q Dis',
                            mode='lines+markers',
                            line=dict(color=avg_color, width=3),
                            marker=dict(size=6, symbol='diamond'),
                            hovertemplate=f"<b>{display_avg_label}</b><br>Cycle: %{{x}}<br>Q Dis: %{{y:.2f}} mAh/g<br><extra></extra>"
                        )
                        if any_efficiency or avg_eff_on:
                            fig.add_trace(trace, secondary_y=False)
                        else:
                            fig.add_trace(trace)
                            
                    if avg_line_toggles.get("Average Q Chg", True):
                        trace = go.Scatter(
                            x=common_cycles, y=avg_qchg,
                            name=f'{display_avg_label} Q Chg',
                            mode='lines+markers',
                            line=dict(color=avg_color, width=3, dash='dash'),
                            marker=dict(size=6, symbol='diamond'),
                            hovertemplate=f"<b>{display_avg_label}</b><br>Cycle: %{{x}}<br>Q Chg: %{{y:.2f}} mAh/g<br><extra></extra>"
                        )
                        if any_efficiency or avg_eff_on:
                            fig.add_trace(trace, secondary_y=False)
                        else:
                            fig.add_trace(trace)
                            
                    if (any_efficiency or avg_eff_on) and avg_line_toggles.get("Average Efficiency", True):
                        fig.add_trace(
                            go.Scatter(
                                x=common_cycles, y=avg_eff,
                                name=f'{display_avg_label} Efficiency (%)',
                                mode='lines+markers',
                                line=dict(color=avg_color, width=3, dash='dot'),
                                marker=dict(size=5, symbol='diamond'),
                                opacity=0.8,
                                hovertemplate=f"<b>{display_avg_label}</b><br>Cycle: %{{x}}<br>Efficiency: %{{y:.2f}}%<br><extra></extra>"
                            ),
                            secondary_y=True
                        )
            except Exception as e:
                pass

    if any_efficiency or avg_eff_on:
        fig.update_xaxes(title_text=x_col)
        fig.update_yaxes(title_text="Capacity (mAh/g)", secondary_y=False, color='blue')
        fig.update_yaxes(title_text="Efficiency (%)", secondary_y=True, color='red')
    else:
        fig.update_xaxes(title_text=x_col)
        fig.update_yaxes(title_text="Capacity (mAh/g)")

    # Use custom_title if show_graph_title is True, otherwise use a default or no title
    if show_graph_title:
        title_text = custom_title
        if any_efficiency or avg_eff_on:
            title_text += " and Efficiency"
    else:
        title_text = "Capacity Comparison" # Default if show_graph_title is False

    layout_args = dict(
        title=title_text,
        hovermode='closest',
        template='plotly_white',
        height=600,
        showlegend=not hide_legend
    )
    if not hide_legend:
        layout_args['legend'] = dict(
            orientation="v", yanchor="top", y=0.99, xanchor="right", x=0.99, bgcolor="rgba(255, 255, 255, 0.8)"
        )
    
    fig.update_layout(**layout_args)
    if y_axis_limits is not None and y_axis_limits != (None, None):
        y_min, y_max = y_axis_limits
        if y_min is not None and y_max is not None:
            if any_efficiency or avg_eff_on:
                fig.update_yaxes(range=[y_min, y_max], secondary_y=False)
            else:
                fig.update_yaxes(range=[y_min, y_max])

    return fig


def plot_interactive_comparison_metrics(
    comparison_data: List[Dict[str, Any]],
    selected_metrics: List[str],
    plot_mapping: Dict[str, Tuple[str, str]],
    custom_names: Optional[Dict[str, str]] = None
) -> go.Figure:
    """
    Create a multi-metric interactive comparison bar chart using Plotly.
    
    Args:
        comparison_data: List of dictionary summaries for each experiment/cell
        selected_metrics: List of metric names to plot
        plot_mapping: Dictionary mapping display names to (data_key, unit)
        custom_names: Dictionary mapping original dataset labels to customized labels
        
    Returns:
        Plotly Figure object
    """
    if custom_names is None:
        custom_names = {}
        
    if not comparison_data or not selected_metrics:
        fig = go.Figure()
        fig.add_annotation(
            text="No data or metrics selected for comparison.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )
        fig.update_layout(template='plotly_white', height=500, xaxis=dict(visible=False), yaxis=dict(visible=False))
        return fig

    # Determine units to see if we need secondary y-axis
    units = [plot_mapping[m][1] for m in selected_metrics]
    unique_units = list(dict.fromkeys(units)) # preserve order
    
    has_secondary_y = len(unique_units) > 1
    
    if has_secondary_y:
        # Create subplots with secondary y axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    else:
        fig = go.Figure()
        
    # Standard color cycle
    plotly_colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
    ]
    
    # Process x-axis labels
    x_labels = []
    hover_labels = []
    
    for exp in comparison_data:
        # For individual cell
        if 'cell_name' in exp and "Single Cell" not in exp['cell_name'] and exp['cell_name'] != exp.get('experiment_name'):
            # This is a specific cell
            # Try to build the standard label format "ExpName - CellName" to check against custom names
            exp_name = exp.get('experiment_name', '')
            cell_name = exp.get('cell_name', '')
            dataset_label = f"{exp_name} - {cell_name}" if exp_name and cell_name else cell_name
        else:
            # This is an experiment average or single cell experiment
            exp_name = exp.get('experiment_name', 'Unknown')
            dataset_label = exp_name
            # If it's an average of a multi-cell experiment, the standard label often has " - Average"
            # But in comparison_data it might just be the exp_name or 'exp_name (Single Cell)'
            if "Single Cell" in exp.get('cell_name', ''):
                dataset_label = exp_name
            elif exp.get('cell_name') == "Average" or exp.get('cell_name') == f"{exp_name} - Average":
                dataset_label = f"{exp_name} - Average"
                
        display_label = custom_names.get(dataset_label, dataset_label)
        
        x_labels.append(display_label)
        hover_labels.append(dataset_label) # keep original for hover if needed
        
    # Add traces for each metric
    primary_unit = unique_units[0] if unique_units else ""
    secondary_unit = unique_units[1] if len(unique_units) > 1 else ""
    
    for i, metric in enumerate(selected_metrics):
        data_key, unit = plot_mapping[metric]
        
        y_values = []
        hover_texts = []
        
        for j, exp in enumerate(comparison_data):
            val = exp.get(data_key)
            y_values.append(val)
            
            # Format hover text smartly
            val_str = f"{val:.2f}" if val is not None and isinstance(val, (int, float)) else "N/A"
            hover_text = f"<b>{x_labels[j]}</b><br>{metric}: {val_str} {unit}"
            hover_texts.append(hover_text)
            
        color = plotly_colors[i % len(plotly_colors)]
        
        # Determine which axis to use
        is_secondary = has_secondary_y and unit == secondary_unit
        
        trace = go.Bar(
            name=metric,
            x=x_labels,
            y=y_values,
            text=[f"{v:.1f}" if v is not None else "" for v in y_values],
            textposition='auto',
            marker_color=color,
            offsetgroup=str(i),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts
        )
        
        if has_secondary_y:
            fig.add_trace(trace, secondary_y=is_secondary)
        else:
            fig.add_trace(trace)
            
    # Layout updates
    fig.update_layout(
        barmode='group',
        title="Multi-Metric Comparison",
        xaxis_title="Dataset",
        hovermode="closest",
        template="plotly_white",
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Configure axes
    if unique_units:
        # Primary axis color match first metric color
        primary_color = plotly_colors[0]
        metric_names_primary = [m for m in selected_metrics if plot_mapping[m][1] == primary_unit]
        primary_title = f"{', '.join(metric_names_primary)} ({primary_unit})"
        
        # If there's only one metric on primary, color-code the axis
        if has_secondary_y:
            if len(metric_names_primary) == 1:
                fig.update_yaxes(title_text=primary_title, title_font_color=primary_color, tickfont_color=primary_color, secondary_y=False)
            else:
                fig.update_yaxes(title_text=primary_title, secondary_y=False)
        else:
            if len(metric_names_primary) == 1:
                fig.update_yaxes(title_text=primary_title, title_font_color=primary_color, tickfont_color=primary_color)
            else:
                fig.update_yaxes(title_text=primary_title)
            
        if has_secondary_y:
            # Secondary axis color match first metric assigned to secondary
            secondary_metric_idx = next(i for i, m in enumerate(selected_metrics) if plot_mapping[m][1] == secondary_unit)
            secondary_color = plotly_colors[secondary_metric_idx % len(plotly_colors)]
            
            metric_names_secondary = [m for m in selected_metrics if plot_mapping[m][1] == secondary_unit]
            secondary_title = f"{', '.join(metric_names_secondary)} ({secondary_unit})"
            
            if len(metric_names_secondary) == 1:
                fig.update_yaxes(title_text=secondary_title, title_font_color=secondary_color, tickfont_color=secondary_color, secondary_y=True)
            else:
                fig.update_yaxes(title_text=secondary_title, secondary_y=True)

    return fig
