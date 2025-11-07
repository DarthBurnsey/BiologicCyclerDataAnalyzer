# plotting.py
import matplotlib.pyplot as plt
import pandas as pd
from typing import List, Dict, Any, Optional
from matplotlib.figure import Figure

def plot_capacity_graph(
    dfs: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    show_efficiency_lines: Dict[str, bool],
    remove_last_cycle: bool,
    show_graph_title: bool,
    experiment_name: str,
    show_average_performance: bool = False,
    avg_line_toggles: Optional[Dict[str, bool]] = None,
    remove_markers: bool = False,
    hide_legend: bool = False,
    group_a_curve: Optional[tuple] = None,
    group_b_curve: Optional[tuple] = None,
    group_c_curve: Optional[tuple] = None,
    group_a_qchg: Optional[tuple] = None,
    group_b_qchg: Optional[tuple] = None,
    group_c_qchg: Optional[tuple] = None,
    group_a_eff: Optional[tuple] = None,
    group_b_eff: Optional[tuple] = None,
    group_c_eff: Optional[tuple] = None,
    group_names: Optional[list] = None,
    cycle_filter: str = "1-*",
    custom_colors: Optional[Dict[str, str]] = None,
    y_axis_limits: Optional[tuple] = None
) -> Figure:
    """Plot the main capacity/efficiency graph and return the matplotlib figure. If remove_markers is True, lines will have no markers. If hide_legend is True, the legend will not be shown. Optionally plot group average curves for Group A, B, and C."""
    if avg_line_toggles is None:
        avg_line_toggles = {"Average Q Dis": True, "Average Q Chg": True, "Average Efficiency": True}
    if group_names is None:
        group_names = ["Group A", "Group B", "Group C"]
    if custom_colors is None:
        custom_colors = {}
    
    # Get matplotlib default color cycle
    default_colors_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    
    # Apply cycle filtering
    from ui_components import parse_cycle_filter
    filtered_dfs = []
    for d in dfs:
        df = d['df'].copy()
        if not df.empty:
            # Get max cycle number
            max_cycle = int(df.iloc[:, 0].max()) if not df.empty else 1
            # Parse cycle filter
            cycles_to_include = parse_cycle_filter(cycle_filter, max_cycle)
            # Filter dataframe to only include specified cycles
            cycle_col = df.columns[0]
            df_filtered = df[df[cycle_col].isin(cycles_to_include)]
            if not df_filtered.empty:
                filtered_dfs.append({**d, 'df': df_filtered})
        else:
            filtered_dfs.append(d)
    dfs = filtered_dfs
    
    x_col = 'Cycle'  # default
    if dfs:
        x_col = dfs[0]['df'].columns[0]
    any_efficiency = any(show_efficiency_lines.values())
    avg_eff_on = show_average_performance and avg_line_toggles and avg_line_toggles.get("Average Efficiency", False)
    any_group_eff = group_a_eff is not None or group_b_eff is not None or group_c_eff is not None
    marker_style = '' if remove_markers else 'o'
    avg_marker_style = '' if remove_markers else 'D'
    eff_marker_style = '' if remove_markers else 's'
    if any_efficiency or avg_eff_on or any_group_eff:
        fig, ax1 = plt.subplots()
        ax2 = ax1.twinx()
        for i, d in enumerate(dfs):
            try:
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_dis = f"{cell_name} Q Dis"
                label_chg = f"{cell_name} Q Chg"
                
                # Get custom color for this cell, or use default from color cycle
                cell_color = custom_colors.get(cell_name, default_colors_cycle[i % len(default_colors_cycle)])
                
                plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                dataset_x_col = plot_df.columns[0]
                if show_lines.get(label_dis, False):
                    try:
                        # Convert to numeric, handling any string values
                        qdis_data = pd.to_numeric(plot_df['Q Dis (mAh/g)'], errors='coerce')
                        valid_mask = ~qdis_data.isna()
                        if valid_mask.any():
                            ax1.plot(plot_df[dataset_x_col][valid_mask], qdis_data[valid_mask], label=label_dis, marker=marker_style, color=cell_color)
                    except Exception:
                        pass
                if show_lines.get(label_chg, False):
                    try:
                        # Convert to numeric, handling any string values
                        qchg_data = pd.to_numeric(plot_df['Q Chg (mAh/g)'], errors='coerce')
                        valid_mask = ~qchg_data.isna()
                        if valid_mask.any():
                            ax1.plot(plot_df[dataset_x_col][valid_mask], qchg_data[valid_mask], label=label_chg, marker=marker_style, color=cell_color)
                    except Exception:
                        pass
            except Exception:
                pass
        for i, d in enumerate(dfs):
            try:
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_eff = f"{cell_name} Efficiency"
                
                # Get custom color for this cell, or use default from color cycle
                cell_color = custom_colors.get(cell_name, default_colors_cycle[i % len(default_colors_cycle)])
                
                plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                dataset_x_col = plot_df.columns[0]
                if show_efficiency_lines.get(label_eff, False) and 'Efficiency (-)' in plot_df.columns and not plot_df['Efficiency (-)'].empty:
                    try:
                        # Convert to numeric, handling any string values
                        efficiency_pct = pd.to_numeric(plot_df['Efficiency (-)'], errors='coerce') * 100
                        # Remove any NaN values
                        valid_mask = ~efficiency_pct.isna()
                        if valid_mask.any():
                            ax2.plot(plot_df[dataset_x_col][valid_mask], efficiency_pct[valid_mask], 
                                   label=f'{cell_name} Efficiency (%)', linestyle='--', marker=eff_marker_style, alpha=0.7, color=cell_color)
                    except Exception:
                        # Skip plotting if there are issues with efficiency data
                        pass
            except Exception:
                pass
        # Plot average if requested
        if show_average_performance and len(dfs) > 1:
            # Find common cycles
            dfs_trimmed = [d['df'][:-1] if remove_last_cycle else d['df'] for d in dfs]
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
                                    qdis_val = float(row['Q Dis (mAh/g)'].values[0])
                                    qdis_vals.append(qdis_val)
                                except (ValueError, TypeError):
                                    # Skip non-numeric discharge capacity values
                                    pass
                            if 'Q Chg (mAh/g)' in row:
                                try:
                                    qchg_val = float(row['Q Chg (mAh/g)'].values[0])
                                    qchg_vals.append(qchg_val)
                                except (ValueError, TypeError):
                                    # Skip non-numeric charge capacity values
                                    pass
                            if 'Efficiency (-)' in row and not pd.isnull(row['Efficiency (-)'].values[0]):
                                try:
                                    eff_val = float(row['Efficiency (-)'].values[0]) * 100
                                    eff_vals.append(eff_val)
                                except (ValueError, TypeError):
                                    # Skip non-numeric efficiency values
                                    pass
                    avg_qdis.append(sum(qdis_vals)/len(qdis_vals) if qdis_vals else None)
                    avg_qchg.append(sum(qchg_vals)/len(qchg_vals) if qchg_vals else None)
                    avg_eff.append(sum(eff_vals)/len(eff_vals) if eff_vals else None)
                avg_label_prefix = f"{experiment_name} " if experiment_name else ""
                # Get custom color for average, or use default colors
                avg_color = custom_colors.get("Average", None)
                qdis_color = avg_color if avg_color else 'black'
                qchg_color = avg_color if avg_color else 'gray'
                eff_color = avg_color if avg_color else 'orange'
                
                if avg_line_toggles.get("Average Q Dis", True):
                    ax1.plot(common_cycles, avg_qdis, label=f'{avg_label_prefix}Average Q Dis', color=qdis_color, linewidth=2, marker=avg_marker_style)
                if avg_line_toggles.get("Average Q Chg", True):
                    ax1.plot(common_cycles, avg_qchg, label=f'{avg_label_prefix}Average Q Chg', color=qchg_color, linewidth=2, marker=avg_marker_style)
                if avg_line_toggles.get("Average Efficiency", True):
                    ax2.plot(common_cycles, avg_eff, label=f'{avg_label_prefix}Average Efficiency (%)', color=eff_color, linewidth=2, linestyle='--', marker=avg_marker_style, alpha=0.7)
        # --- Plot group averages if provided ---
        group_default_colors = ['#0000FF', '#FF0000', '#00FF00']  # Blue, Red, Green
        if group_a_curve is not None:
            cycles, avg_qdis = group_a_curve
            if cycles and avg_qdis:
                group_a_color = custom_colors.get(group_names[0], group_default_colors[0])
                ax1.plot(cycles, avg_qdis, label=f'{group_names[0]} Avg Q Dis', color=group_a_color, linewidth=2, linestyle='-', marker='x')
        if group_b_curve is not None:
            cycles, avg_qdis = group_b_curve
            if cycles and avg_qdis:
                group_b_color = custom_colors.get(group_names[1], group_default_colors[1])
                ax1.plot(cycles, avg_qdis, label=f'{group_names[1]} Avg Q Dis', color=group_b_color, linewidth=2, linestyle='-', marker='x')
        if group_c_curve is not None:
            cycles, avg_qdis = group_c_curve
            if cycles and avg_qdis:
                group_c_color = custom_colors.get(group_names[2], group_default_colors[2])
                ax1.plot(cycles, avg_qdis, label=f'{group_names[2]} Avg Q Dis', color=group_c_color, linewidth=2, linestyle='-', marker='x')
        if group_a_qchg is not None:
            cycles, avg_qchg = group_a_qchg
            if cycles and avg_qchg:
                group_a_color = custom_colors.get(group_names[0], group_default_colors[0])
                ax1.plot(cycles, avg_qchg, label=f'{group_names[0]} Avg Q Chg', color=group_a_color, linewidth=2, linestyle='--', marker='x')
        if group_b_qchg is not None:
            cycles, avg_qchg = group_b_qchg
            if cycles and avg_qchg:
                group_b_color = custom_colors.get(group_names[1], group_default_colors[1])
                ax1.plot(cycles, avg_qchg, label=f'{group_names[1]} Avg Q Chg', color=group_b_color, linewidth=2, linestyle='--', marker='x')
        if group_c_qchg is not None:
            cycles, avg_qchg = group_c_qchg
            if cycles and avg_qchg:
                group_c_color = custom_colors.get(group_names[2], group_default_colors[2])
                ax1.plot(cycles, avg_qchg, label=f'{group_names[2]} Avg Q Chg', color=group_c_color, linewidth=2, linestyle='--', marker='x')
        if group_a_eff is not None:
            cycles, avg_eff = group_a_eff
            if cycles and avg_eff:
                group_a_color = custom_colors.get(group_names[0], group_default_colors[0])
                ax2.plot(cycles, avg_eff, label=f'{group_names[0]} Avg Efficiency (%)', color=group_a_color, linewidth=2, linestyle='--', marker='x', alpha=0.7)
        if group_b_eff is not None:
            cycles, avg_eff = group_b_eff
            if cycles and avg_eff:
                group_b_color = custom_colors.get(group_names[1], group_default_colors[1])
                ax2.plot(cycles, avg_eff, label=f'{group_names[1]} Avg Efficiency (%)', color=group_b_color, linewidth=2, linestyle='--', marker='x', alpha=0.7)
        if group_c_eff is not None:
            cycles, avg_eff = group_c_eff
            if cycles and avg_eff:
                group_c_color = custom_colors.get(group_names[2], group_default_colors[2])
                ax2.plot(cycles, avg_eff, label=f'{group_names[2]} Avg Efficiency (%)', color=group_c_color, linewidth=2, linestyle='--', marker='x', alpha=0.7)
        ax1.set_xlabel(x_col)
        ax1.set_ylabel('Capacity (mAh/g)', color='blue')
        ax2.set_ylabel('Efficiency (%)', color='red')
        if show_graph_title:
            if experiment_name:
                ax1.set_title(f'{experiment_name} - Gravimetric Capacity and Efficiency vs. {x_col}')
            else:
                ax1.set_title(f'Gravimetric Capacity and Efficiency vs. {x_col}')
        ax1.tick_params(axis='y', labelcolor='blue')
        ax2.tick_params(axis='y', labelcolor='red')
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        if not hide_legend:
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
        
        # Apply y-axis limits if specified
        if y_axis_limits is not None and y_axis_limits != (None, None):
            y_min, y_max = y_axis_limits
            if y_min is not None and y_max is not None:
                ax1.set_ylim(y_min, y_max)
        
        return fig
    else:
        fig, ax = plt.subplots()
        for i, d in enumerate(dfs):
            try:
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_dis = f"{cell_name} Q Dis"
                label_chg = f"{cell_name} Q Chg"
                
                # Get custom color for this cell, or use default from color cycle
                cell_color = custom_colors.get(cell_name, default_colors_cycle[i % len(default_colors_cycle)])
                
                plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                dataset_x_col = plot_df.columns[0]
                if show_lines.get(label_dis, False):
                    try:
                        # Convert to numeric, handling any string values
                        qdis_data = pd.to_numeric(plot_df['Q Dis (mAh/g)'], errors='coerce')
                        valid_mask = ~qdis_data.isna()
                        if valid_mask.any():
                            ax.plot(plot_df[dataset_x_col][valid_mask], qdis_data[valid_mask], label=label_dis, marker=marker_style, color=cell_color)
                    except Exception:
                        pass
                if show_lines.get(label_chg, False):
                    try:
                        # Convert to numeric, handling any string values
                        qchg_data = pd.to_numeric(plot_df['Q Chg (mAh/g)'], errors='coerce')
                        valid_mask = ~qchg_data.isna()
                        if valid_mask.any():
                            ax.plot(plot_df[dataset_x_col][valid_mask], qchg_data[valid_mask], label=label_chg, marker=marker_style, color=cell_color)
                    except Exception:
                        pass
            except Exception:
                pass
        # Plot average if requested
        if show_average_performance and len(dfs) > 1:
            dfs_trimmed = [d['df'][:-1] if remove_last_cycle else d['df'] for d in dfs]
            common_cycles = set(dfs_trimmed[0][x_col])
            for df in dfs_trimmed[1:]:
                common_cycles = common_cycles & set(df[x_col])
            common_cycles = sorted(list(common_cycles))
            if common_cycles:
                avg_qdis = []
                avg_qchg = []
                for cycle in common_cycles:
                    qdis_vals = []
                    qchg_vals = []
                    for df in dfs_trimmed:
                        row = df[df[x_col] == cycle]
                        if not row.empty:
                            if 'Q Dis (mAh/g)' in row:
                                try:
                                    qdis_val = float(row['Q Dis (mAh/g)'].values[0])
                                    qdis_vals.append(qdis_val)
                                except (ValueError, TypeError):
                                    # Skip non-numeric discharge capacity values
                                    pass
                            if 'Q Chg (mAh/g)' in row:
                                try:
                                    qchg_val = float(row['Q Chg (mAh/g)'].values[0])
                                    qchg_vals.append(qchg_val)
                                except (ValueError, TypeError):
                                    # Skip non-numeric charge capacity values
                                    pass
                    avg_qdis.append(sum(qdis_vals)/len(qdis_vals) if qdis_vals else None)
                    avg_qchg.append(sum(qchg_vals)/len(qchg_vals) if qchg_vals else None)
                avg_label_prefix = f"{experiment_name} " if experiment_name else ""
                # Get custom color for average, or use default colors
                avg_color = custom_colors.get("Average", None)
                qdis_color = avg_color if avg_color else 'black'
                qchg_color = avg_color if avg_color else 'gray'
                
                if avg_line_toggles.get("Average Q Dis", True):
                    ax.plot(common_cycles, avg_qdis, label=f'{avg_label_prefix}Average Q Dis', color=qdis_color, linewidth=2, marker=avg_marker_style)
                if avg_line_toggles.get("Average Q Chg", True):
                    ax.plot(common_cycles, avg_qchg, label=f'{avg_label_prefix}Average Q Chg', color=qchg_color, linewidth=2, marker=avg_marker_style)
        # --- Plot group averages if provided ---
        if group_a_curve is not None:
            cycles, avg_qdis = group_a_curve
            if cycles and avg_qdis:
                group_a_color = custom_colors.get(group_names[0], group_default_colors[0])
                ax.plot(cycles, avg_qdis, label=f'{group_names[0]} Avg Q Dis', color=group_a_color, linewidth=2, linestyle='-', marker='x')
        if group_b_curve is not None:
            cycles, avg_qdis = group_b_curve
            if cycles and avg_qdis:
                group_b_color = custom_colors.get(group_names[1], group_default_colors[1])
                ax.plot(cycles, avg_qdis, label=f'{group_names[1]} Avg Q Dis', color=group_b_color, linewidth=2, linestyle='-', marker='x')
        if group_c_curve is not None:
            cycles, avg_qdis = group_c_curve
            if cycles and avg_qdis:
                group_c_color = custom_colors.get(group_names[2], group_default_colors[2])
                ax.plot(cycles, avg_qdis, label=f'{group_names[2]} Avg Q Dis', color=group_c_color, linewidth=2, linestyle='-', marker='x')
        if group_a_qchg is not None:
            cycles, avg_qchg = group_a_qchg
            if cycles and avg_qchg:
                group_a_color = custom_colors.get(group_names[0], group_default_colors[0])
                ax.plot(cycles, avg_qchg, label=f'{group_names[0]} Avg Q Chg', color=group_a_color, linewidth=2, linestyle='--', marker='x')
        if group_b_qchg is not None:
            cycles, avg_qchg = group_b_qchg
            if cycles and avg_qchg:
                group_b_color = custom_colors.get(group_names[1], group_default_colors[1])
                ax.plot(cycles, avg_qchg, label=f'{group_names[1]} Avg Q Chg', color=group_b_color, linewidth=2, linestyle='--', marker='x')
        if group_c_qchg is not None:
            cycles, avg_qchg = group_c_qchg
            if cycles and avg_qchg:
                group_c_color = custom_colors.get(group_names[2], group_default_colors[2])
                ax.plot(cycles, avg_qchg, label=f'{group_names[2]} Avg Q Chg', color=group_c_color, linewidth=2, linestyle='--', marker='x')
        # Efficiency lines are not plotted in the non-efficiency axis case
        ax.set_xlabel(x_col)
        ax.set_ylabel('Capacity (mAh/g)')
        if show_graph_title:
            if experiment_name:
                ax.set_title(f'{experiment_name} - Gravimetric Capacity vs. {x_col}')
            else:
                ax.set_title(f'Gravimetric Capacity vs. {x_col}')
        if not hide_legend:
            ax.legend()
        
        # Apply y-axis limits if specified
        if y_axis_limits is not None and y_axis_limits != (None, None):
            y_min, y_max = y_axis_limits
            if y_min is not None and y_max is not None:
                ax.set_ylim(y_min, y_max)
        
        return fig

def plot_capacity_retention_graph(
    dfs: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    reference_cycle: int,
    formation_cycles: int,
    remove_last_cycle: bool,
    show_graph_title: bool,
    experiment_name: str,
    show_average_performance: bool = False,
    avg_line_toggles: Optional[Dict[str, bool]] = None,
    remove_markers: bool = False,
    hide_legend: bool = False,
    group_a_curve: Optional[tuple] = None,
    group_b_curve: Optional[tuple] = None,
    group_c_curve: Optional[tuple] = None,
    group_names: Optional[list] = None,
    retention_threshold: float = 80.0,
    y_axis_min: float = 0.0,
    y_axis_max: float = 110.0,
    show_baseline_line: bool = True,
    show_threshold_line: bool = True,
    cycle_filter: str = "1-*",
    custom_colors: Optional[Dict[str, str]] = None
) -> Figure:
    """Plot capacity retention vs cycle number."""
    if avg_line_toggles is None:
        avg_line_toggles = {"Average Q Dis": True, "Average Q Chg": True}
    if group_names is None:
        group_names = ["Group A", "Group B", "Group C"]
    if custom_colors is None:
        custom_colors = {}
    
    # Get matplotlib default color cycle
    default_colors_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    
    # Apply cycle filtering
    from ui_components import parse_cycle_filter
    filtered_dfs = []
    for d in dfs:
        df = d['df'].copy()
        if not df.empty:
            # Get max cycle number
            max_cycle = int(df.iloc[:, 0].max()) if not df.empty else 1
            # Parse cycle filter
            cycles_to_include = parse_cycle_filter(cycle_filter, max_cycle)
            # Filter dataframe to only include specified cycles
            cycle_col = df.columns[0]
            df_filtered = df[df[cycle_col].isin(cycles_to_include)]
            if not df_filtered.empty:
                filtered_dfs.append({**d, 'df': df_filtered})
        else:
            filtered_dfs.append(d)
    dfs = filtered_dfs
    
    x_col = 'Cycle'  # default
    if dfs:
        x_col = dfs[0]['df'].columns[0]
    
    marker_style = '' if remove_markers else 'o'
    avg_marker_style = '' if remove_markers else 'D'
    
    fig, ax = plt.subplots()
    
    # Plot individual cell capacity retention
    for i, d in enumerate(dfs):
        try:
            cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
            label_dis = f"{cell_name} Q Dis Retention"
            label_chg = f"{cell_name} Q Chg Retention"
            
            # Get custom color for this cell, or use default from color cycle
            cell_color = custom_colors.get(cell_name, default_colors_cycle[i % len(default_colors_cycle)])
            
            plot_df = d['df'][:-1] if remove_last_cycle else d['df']
            dataset_x_col = plot_df.columns[0]
            
            # Calculate retention for discharge capacity
            if show_lines.get(f"{cell_name} Q Dis", False):
                try:
                    qdis_data = pd.to_numeric(plot_df['Q Dis (mAh/g)'], errors='coerce')
                    valid_mask = ~qdis_data.isna()
                    
                    if valid_mask.any():
                        # Find reference capacity
                        ref_data = plot_df[plot_df[dataset_x_col] == reference_cycle]
                        if not ref_data.empty:
                            ref_capacity = pd.to_numeric(ref_data['Q Dis (mAh/g)'].iloc[0], errors='coerce')
                            if not pd.isna(ref_capacity) and ref_capacity > 0:
                                retention_data = (qdis_data / ref_capacity) * 100
                                ax.plot(plot_df[dataset_x_col][valid_mask], retention_data[valid_mask], 
                                       label=label_dis, marker=marker_style, color=cell_color)
                except Exception:
                    pass
            
            # Calculate retention for charge capacity
            if show_lines.get(f"{cell_name} Q Chg", False):
                try:
                    qchg_data = pd.to_numeric(plot_df['Q Chg (mAh/g)'], errors='coerce')
                    valid_mask = ~qchg_data.isna()
                    
                    if valid_mask.any():
                        # Find reference capacity
                        ref_data = plot_df[plot_df[dataset_x_col] == reference_cycle]
                        if not ref_data.empty:
                            ref_capacity = pd.to_numeric(ref_data['Q Chg (mAh/g)'].iloc[0], errors='coerce')
                            if not pd.isna(ref_capacity) and ref_capacity > 0:
                                retention_data = (qchg_data / ref_capacity) * 100
                                ax.plot(plot_df[dataset_x_col][valid_mask], retention_data[valid_mask], 
                                       label=label_chg, marker=marker_style, linestyle='--', color=cell_color)
                except Exception:
                    pass
        except Exception:
            pass
    
    # Plot average retention if requested
    if show_average_performance and len(dfs) > 1:
        dfs_trimmed = [d['df'][:-1] if remove_last_cycle else d['df'] for d in dfs]
        common_cycles = set(dfs_trimmed[0][x_col])
        for df in dfs_trimmed[1:]:
            common_cycles = common_cycles & set(df[x_col])
        common_cycles = sorted(list(common_cycles))
        
        if common_cycles and reference_cycle in common_cycles:
            # Calculate reference capacities for each cell
            ref_qdis_vals = []
            ref_qchg_vals = []
            
            for df in dfs_trimmed:
                ref_row = df[df[x_col] == reference_cycle]
                if not ref_row.empty:
                    try:
                        ref_qdis = float(ref_row['Q Dis (mAh/g)'].values[0])
                        ref_qdis_vals.append(ref_qdis)
                    except (ValueError, TypeError):
                        ref_qdis_vals.append(None)
                    
                    try:
                        ref_qchg = float(ref_row['Q Chg (mAh/g)'].values[0])
                        ref_qchg_vals.append(ref_qchg)
                    except (ValueError, TypeError):
                        ref_qchg_vals.append(None)
                else:
                    ref_qdis_vals.append(None)
                    ref_qchg_vals.append(None)
            
            avg_retention_qdis = []
            avg_retention_qchg = []
            
            for cycle in common_cycles:
                retention_qdis_vals = []
                retention_qchg_vals = []
                
                for i, df in enumerate(dfs_trimmed):
                    row = df[df[x_col] == cycle]
                    if not row.empty and ref_qdis_vals[i] is not None and ref_qdis_vals[i] > 0:
                        try:
                            qdis_val = float(row['Q Dis (mAh/g)'].values[0])
                            retention = (qdis_val / ref_qdis_vals[i]) * 100
                            retention_qdis_vals.append(retention)
                        except (ValueError, TypeError):
                            pass
                    
                    if not row.empty and ref_qchg_vals[i] is not None and ref_qchg_vals[i] > 0:
                        try:
                            qchg_val = float(row['Q Chg (mAh/g)'].values[0])
                            retention = (qchg_val / ref_qchg_vals[i]) * 100
                            retention_qchg_vals.append(retention)
                        except (ValueError, TypeError):
                            pass
                
                avg_retention_qdis.append(sum(retention_qdis_vals)/len(retention_qdis_vals) if retention_qdis_vals else None)
                avg_retention_qchg.append(sum(retention_qchg_vals)/len(retention_qchg_vals) if retention_qchg_vals else None)
            
            avg_label_prefix = f"{experiment_name} " if experiment_name else ""
            # Get custom color for average, or use default colors
            avg_color = custom_colors.get("Average", None)
            qdis_color = avg_color if avg_color else 'black'
            qchg_color = avg_color if avg_color else 'gray'
            
            if avg_line_toggles.get("Average Q Dis", True):
                ax.plot(common_cycles, avg_retention_qdis, 
                       label=f'{avg_label_prefix}Average Q Dis Retention', 
                       color=qdis_color, linewidth=2, marker=avg_marker_style)
            if avg_line_toggles.get("Average Q Chg", True):
                ax.plot(common_cycles, avg_retention_qchg, 
                       label=f'{avg_label_prefix}Average Q Chg Retention', 
                       color=qchg_color, linewidth=2, marker=avg_marker_style, linestyle='--')
    
    # Plot group average retention if provided
    group_default_colors = ['#0000FF', '#FF0000', '#00FF00']  # Blue, Red, Green
    if group_a_curve is not None:
        cycles, avg_retention = group_a_curve
        if cycles and avg_retention:
            group_a_color = custom_colors.get(group_names[0], group_default_colors[0])
            ax.plot(cycles, avg_retention, label=f'{group_names[0]} Avg Retention', 
                   color=group_a_color, linewidth=2, linestyle='-', marker='x')
    if group_b_curve is not None:
        cycles, avg_retention = group_b_curve
        if cycles and avg_retention:
            group_b_color = custom_colors.get(group_names[1], group_default_colors[1])
            ax.plot(cycles, avg_retention, label=f'{group_names[1]} Avg Retention', 
                   color=group_b_color, linewidth=2, linestyle='-', marker='x')
    if group_c_curve is not None:
        cycles, avg_retention = group_c_curve
        if cycles and avg_retention:
            group_c_color = custom_colors.get(group_names[2], group_default_colors[2])
            ax.plot(cycles, avg_retention, label=f'{group_names[2]} Avg Retention', 
                   color=group_c_color, linewidth=2, linestyle='-', marker='x')
    
    # Add horizontal reference lines based on user preferences
    if show_baseline_line:
        ax.axhline(y=100, color='black', linestyle='-', alpha=0.3, linewidth=1, label='100% Baseline')
    if show_threshold_line:
        ax.axhline(y=retention_threshold, color='red', linestyle='--', alpha=0.7, linewidth=2, 
                   label=f'{retention_threshold}% Threshold')
    
    # Add vertical line at reference cycle
    ax.axvline(x=reference_cycle, color='green', linestyle=':', alpha=0.7, linewidth=2, 
               label=f'Reference Cycle ({reference_cycle})')
    
    ax.set_xlabel(x_col)
    ax.set_ylabel('Capacity Retention (%)')
    ax.set_ylim(y_axis_min, y_axis_max)  # Set Y-axis with user-defined range
    
    if show_graph_title:
        if experiment_name:
            ax.set_title(f'{experiment_name} - Capacity Retention vs. {x_col}')
        else:
            ax.set_title(f'Capacity Retention vs. {x_col}')
    
    if not hide_legend:
        ax.legend()
    
    return fig 


def plot_comparison_capacity_graph(
    experiments_data: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    show_efficiency_lines: Dict[str, bool],
    remove_last_cycle: bool,
    show_graph_title: bool,
    show_average_performance: bool = False,
    avg_line_toggles: Optional[Dict[str, bool]] = None,
    remove_markers: bool = False,
    hide_legend: bool = False,
    cycle_filter: str = "1-*",
    custom_colors: Optional[Dict[str, str]] = None,
    y_axis_limits: Optional[tuple] = None
) -> Figure:
    """
    Plot capacity data from multiple experiments on the same axes for comparison.
    
    Args:
        experiments_data: List of experiment data dictionaries containing:
            - 'experiment_name': Name of the experiment
            - 'dfs': List of dataframes for the experiment
        show_lines: Dictionary of which lines to show
        show_efficiency_lines: Dictionary of which efficiency lines to show
        remove_last_cycle: Whether to remove the last cycle from plotting
        show_graph_title: Whether to show the graph title
        show_average_performance: Whether to show average performance lines
        avg_line_toggles: Dictionary controlling which average lines to show
        remove_markers: Whether to remove markers from lines
        hide_legend: Whether to hide the legend
        cycle_filter: Cycle filter string (e.g., "1-*", "1-100")
        custom_colors: Dictionary mapping dataset labels to custom colors (hex format)
    
    Returns:
        matplotlib Figure object
    """
    if avg_line_toggles is None:
        avg_line_toggles = {"Average Q Dis": True, "Average Q Chg": True, "Average Efficiency": True}
    
    if custom_colors is None:
        custom_colors = {}
    
    # Apply cycle filtering to all experiments
    from ui_components import parse_cycle_filter
    filtered_experiments_data = []
    for exp_data in experiments_data:
        filtered_dfs = []
        for d in exp_data['dfs']:
            df = d['df'].copy()
            if not df.empty:
                # Get max cycle number
                max_cycle = int(df.iloc[:, 0].max()) if not df.empty else 1
                # Parse cycle filter
                cycles_to_include = parse_cycle_filter(cycle_filter, max_cycle)
                # Filter dataframe to only include specified cycles
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
    
    # Color palette for different experiments
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    marker_style = '' if remove_markers else 'o'
    avg_marker_style = '' if remove_markers else 'D'
    eff_marker_style = '' if remove_markers else 's'
    
    # Determine if we need dual y-axes for efficiency
    if any_efficiency or avg_eff_on:
        fig, ax1 = plt.subplots(figsize=(12, 8))
        ax2 = ax1.twinx()
    else:
        fig, ax = plt.subplots(figsize=(12, 8))
        ax1 = ax
        ax2 = None
    
    # Get x-axis column name
    x_col = 'Cycle'  # default
    if experiments_data and experiments_data[0]['dfs']:
        x_col = experiments_data[0]['dfs'][0]['df'].columns[0]
    
    # Plot data for each experiment
    for exp_idx, exp_data in enumerate(experiments_data):
        exp_name = exp_data['experiment_name']
        dfs = exp_data['dfs']
        default_exp_color = colors[exp_idx % len(colors)]
        
        # Plot individual cell data only if "Show Averages" is not enabled
        # When "Show Averages" is enabled, we skip individual traces
        if not show_average_performance:
            # Plot individual cell data for this experiment
            for cell_idx, d in enumerate(dfs):
                try:
                    cell_name = d['testnum'] if d['testnum'] else f'Cell {cell_idx+1}'
                    label_dis = f"{exp_name} - {cell_name} Q Dis"
                    label_chg = f"{exp_name} - {cell_name} Q Chg"
                    label_eff = f"{exp_name} - {cell_name} Efficiency"
                    
                    # Get custom color for this dataset, or use default experiment color
                    dataset_label = f"{exp_name} - {cell_name}"
                    cell_color = custom_colors.get(dataset_label, default_exp_color)
                    
                    plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                    dataset_x_col = plot_df.columns[0]
                    
                    # Plot discharge capacity
                    if show_lines.get(label_dis, False):
                        try:
                            qdis_data = pd.to_numeric(plot_df['Q Dis (mAh/g)'], errors='coerce')
                            valid_mask = ~qdis_data.isna()
                            if valid_mask.any():
                                ax1.plot(plot_df[dataset_x_col][valid_mask], qdis_data[valid_mask], 
                                       label=label_dis, marker=marker_style, color=cell_color, alpha=0.7)
                        except Exception:
                            pass
                    
                    # Plot charge capacity
                    if show_lines.get(label_chg, False):
                        try:
                            qchg_data = pd.to_numeric(plot_df['Q Chg (mAh/g)'], errors='coerce')
                            valid_mask = ~qchg_data.isna()
                            if valid_mask.any():
                                ax1.plot(plot_df[dataset_x_col][valid_mask], qchg_data[valid_mask], 
                                       label=label_chg, marker=marker_style, color=cell_color, 
                                       alpha=0.7, linestyle='--')
                        except Exception:
                            pass
                    
                    # Plot efficiency on secondary axis if available
                    if ax2 and show_efficiency_lines.get(label_eff, False) and 'Efficiency (-)' in plot_df.columns:
                        try:
                            efficiency_pct = pd.to_numeric(plot_df['Efficiency (-)'], errors='coerce') * 100
                            valid_mask = ~efficiency_pct.isna()
                            if valid_mask.any():
                                ax2.plot(plot_df[dataset_x_col][valid_mask], efficiency_pct[valid_mask], 
                                       label=label_eff, linestyle=':', marker=eff_marker_style, 
                                       color=cell_color, alpha=0.5)
                        except Exception:
                            pass
                except Exception:
                    pass
        
        # Plot experiment averages if requested
        # For single-cell experiments, show the cell data as "average" (same thing for n=1)
        if show_average_performance and len(dfs) >= 1:
            try:
                dfs_trimmed = [d['df'][:-1] if remove_last_cycle else d['df'] for d in dfs]
                
                # Get the x-axis column name for THIS experiment (not global x_col)
                # Each experiment might have a different column name
                exp_x_col = dfs_trimmed[0].columns[0] if not dfs_trimmed[0].empty else x_col
                
                # Find common cycles across all cells in this experiment
                common_cycles = set(dfs_trimmed[0][exp_x_col])
                for df in dfs_trimmed[1:]:
                    common_cycles = common_cycles & set(df[exp_x_col])
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
                            row = df[df[exp_x_col] == cycle]
                            if not row.empty:
                                # Discharge capacity
                                if 'Q Dis (mAh/g)' in row:
                                    try:
                                        qdis_val = float(row['Q Dis (mAh/g)'].values[0])
                                        qdis_vals.append(qdis_val)
                                    except (ValueError, TypeError):
                                        pass
                                
                                # Charge capacity
                                if 'Q Chg (mAh/g)' in row:
                                    try:
                                        qchg_val = float(row['Q Chg (mAh/g)'].values[0])
                                        qchg_vals.append(qchg_val)
                                    except (ValueError, TypeError):
                                        pass
                                
                                # Efficiency
                                if 'Efficiency (-)' in row and not pd.isnull(row['Efficiency (-)'].values[0]):
                                    try:
                                        eff_val = float(row['Efficiency (-)'].values[0]) * 100
                                        eff_vals.append(eff_val)
                                    except (ValueError, TypeError):
                                        pass
                        
                        avg_qdis.append(sum(qdis_vals)/len(qdis_vals) if qdis_vals else None)
                        avg_qchg.append(sum(qchg_vals)/len(qchg_vals) if qchg_vals else None)
                        avg_eff.append(sum(eff_vals)/len(eff_vals) if eff_vals else None)
                    
                    # Get custom color for average, or use default experiment color
                    # For single-cell experiments, don't use "Average" in the label
                    if len(dfs) == 1:
                        avg_label = f"{exp_name}"
                        label_suffix = ""
                    else:
                        avg_label = f"{exp_name} - Average"
                        label_suffix = " - Average"
                    
                    avg_color = custom_colors.get(avg_label, default_exp_color)
                    
                    # Plot averages with thicker lines
                    if avg_line_toggles.get("Average Q Dis", True):
                        ax1.plot(common_cycles, avg_qdis, 
                               label=f'{exp_name}{label_suffix} Q Dis', 
                               color=avg_color, linewidth=3, marker=avg_marker_style)
                    
                    if avg_line_toggles.get("Average Q Chg", True):
                        ax1.plot(common_cycles, avg_qchg, 
                               label=f'{exp_name}{label_suffix} Q Chg', 
                               color=avg_color, linewidth=3, marker=avg_marker_style, 
                               linestyle='--')
                    
                    if ax2 and avg_line_toggles.get("Average Efficiency", True):
                        ax2.plot(common_cycles, avg_eff, 
                               label=f'{exp_name}{label_suffix} Efficiency (%)', 
                               color=avg_color, linewidth=3, linestyle=':', 
                               marker=avg_marker_style, alpha=0.7)
            except Exception as e:
                # Log the error but continue processing other experiments
                print(f"Warning: Could not plot average for experiment '{exp_name}': {str(e)}")
                import traceback
                traceback.print_exc()
                # Continue to next experiment instead of failing silently
                pass
    
    # Set labels and title
    ax1.set_xlabel(x_col)
    ax1.set_ylabel('Capacity (mAh/g)', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')
    
    if ax2:
        ax2.set_ylabel('Efficiency (%)', color='red')
        ax2.tick_params(axis='y', labelcolor='red')
    
    if show_graph_title:
        title = f'Experiment Comparison - Gravimetric Capacity'
        if ax2:
            title += ' and Efficiency'
        title += f' vs. {x_col}'
        ax1.set_title(title)
    
    # Handle legend
    if not hide_legend:
        if ax2:
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right', bbox_to_anchor=(1.15, 1))
        else:
            ax1.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
    
    # Apply y-axis limits if specified
    if y_axis_limits is not None and y_axis_limits != (None, None):
        y_min, y_max = y_axis_limits
        if y_min is not None and y_max is not None:
            ax1.set_ylim(y_min, y_max)
    
    plt.tight_layout()
    return fig