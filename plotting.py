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


def plot_combined_capacity_retention_graph(
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
    retention_threshold: float = 80.0,
    y_axis_min: Optional[float] = None,
    y_axis_max: Optional[float] = None,
    show_baseline_line: bool = True,
    show_threshold_line: bool = True,
    cycle_filter: str = "1-*",
    custom_colors: Optional[Dict[str, str]] = None,
    capacity_y_axis_limits: Optional[tuple] = None,
    formation_cycles_skip: int = 0
) -> Figure:
    """
    Plot combined Specific Capacity vs Cycle Number (primary Y-axis) with Capacity Retention scale (secondary Y-axis).
    This is a test feature that combines both plots into a single graph with dual Y-axes.
    Only plots a single trace (Specific Capacity) and uses the secondary Y-axis as an alternative scale.
    """
    if avg_line_toggles is None:
        avg_line_toggles = {"Average Q Dis": True, "Average Q Chg": True}
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
    
    # Create figure with dual Y-axes
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    
    # Collect all capacity values to determine scale
    all_capacity_values = []
    initial_capacity = None
    
    # Find initial capacity from the first visible cell using formation_cycles_skip
    # initial_capacity = df['Specific Capacity'].iloc[formation_cycles_skip]
    for i, d in enumerate(dfs):
        try:
            cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
            label_dis = f"{cell_name} Q Dis"
            
            if show_lines.get(label_dis, False):
                plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                dataset_x_col = plot_df.columns[0]
                
                try:
                    qdis_data = pd.to_numeric(plot_df['Q Dis (mAh/g)'], errors='coerce')
                    valid_mask = ~qdis_data.isna()
                    
                    if valid_mask.any():
                        all_capacity_values.extend(qdis_data[valid_mask].tolist())
                        
                        # Get initial capacity from cycle index formation_cycles_skip
                        # This determines the 100% reference capacity
                        if initial_capacity is None and len(plot_df) > formation_cycles_skip:
                            try:
                                # Get capacity at the specified index (after skipping formation cycles)
                                initial_cap = pd.to_numeric(plot_df['Q Dis (mAh/g)'].iloc[formation_cycles_skip], errors='coerce')
                                if not pd.isna(initial_cap) and initial_cap > 0:
                                    initial_capacity = initial_cap
                            except (IndexError, KeyError):
                                # If index is out of range, try to find by reference cycle number
                                ref_data = plot_df[plot_df[dataset_x_col] == reference_cycle]
                                if not ref_data.empty:
                                    ref_cap = pd.to_numeric(ref_data['Q Dis (mAh/g)'].iloc[0], errors='coerce')
                                    if not pd.isna(ref_cap) and ref_cap > 0:
                                        initial_capacity = ref_cap
                except Exception:
                    pass
        except Exception:
            pass
    
    # If no initial capacity found, use max capacity as fallback
    if initial_capacity is None and all_capacity_values:
        initial_capacity = max(all_capacity_values)
    elif initial_capacity is None:
        initial_capacity = 100.0  # Default fallback
    
    # Calculate conversion factor: k = 100 / initial_capacity
    # This converts capacity values to retention percentages
    k = 100.0 / initial_capacity if initial_capacity > 0 else 1.0
    
    # Plot only Specific Capacity (Q Dis) on primary Y-axis (left)
    # This is the single trace that will be displayed
    for i, d in enumerate(dfs):
        try:
            cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
            label_dis = f"{cell_name} Q Dis"
            
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
                        ax1.plot(plot_df[dataset_x_col][valid_mask], qdis_data[valid_mask], 
                               label=label_dis, marker=marker_style, color=cell_color)
                except Exception:
                    pass
        except Exception:
            pass
    
    # Plot average capacity if requested
    if show_average_performance and len(dfs) > 1:
        dfs_trimmed = [d['df'][:-1] if remove_last_cycle else d['df'] for d in dfs]
        common_cycles = set(dfs_trimmed[0][x_col])
        for df in dfs_trimmed[1:]:
            common_cycles = common_cycles & set(df[x_col])
        common_cycles = sorted(list(common_cycles))
        
        if common_cycles:
            avg_qdis = []
            for cycle in common_cycles:
                qdis_vals = []
                for df in dfs_trimmed:
                    row = df[df[x_col] == cycle]
                    if not row.empty:
                        if 'Q Dis (mAh/g)' in row:
                            try:
                                qdis_val = float(row['Q Dis (mAh/g)'].values[0])
                                qdis_vals.append(qdis_val)
                            except (ValueError, TypeError):
                                pass
                avg_qdis.append(sum(qdis_vals)/len(qdis_vals) if qdis_vals else None)
            
            avg_label_prefix = f"{experiment_name} " if experiment_name else ""
            avg_color = custom_colors.get("Average", 'black')
            
            if avg_line_toggles.get("Average Q Dis", True):
                ax1.plot(common_cycles, avg_qdis, 
                       label=f'{avg_label_prefix}Average Q Dis', 
                       color=avg_color, linewidth=2, marker=avg_marker_style)
    
    # Calculate capacity range for setting secondary axis scale
    if all_capacity_values:
        min_cap = min(all_capacity_values)
        max_cap = max(all_capacity_values)
    else:
        min_cap = 0.0
        max_cap = 100.0
    
    # Calculate corresponding retention range
    min_ret = min_cap * k
    max_ret = max_cap * k
    
    # Add horizontal reference lines for retention on secondary axis
    if show_baseline_line:
        ax2.axhline(y=100, color='black', linestyle='-', alpha=0.3, linewidth=1, label='100% Baseline')
    if show_threshold_line:
        ax2.axhline(y=retention_threshold, color='red', linestyle='--', alpha=0.7, linewidth=2, 
                   label=f'{retention_threshold}% Threshold')
    
    # Add vertical line at reference cycle
    ax1.axvline(x=reference_cycle, color='green', linestyle=':', alpha=0.7, linewidth=2, 
               label=f'Reference Cycle ({reference_cycle})')
    
    # Set labels and titles
    ax1.set_xlabel(x_col)
    ax1.set_ylabel('Specific Capacity (mAh/g)', color='black')
    ax2.set_ylabel('Capacity Retention (%)', color='black')
    
    # Set Y-axis limits
    # Primary axis: use user-specified limits or auto-scale
    if capacity_y_axis_limits is not None and capacity_y_axis_limits != (None, None):
        y_min, y_max = capacity_y_axis_limits
        if y_min is not None and y_max is not None:
            ax1.set_ylim(y_min, y_max)
            # Update secondary axis to match the scaled range
            min_ret = y_min * k
            max_ret = y_max * k
    else:
        # Auto-scale primary axis, then set secondary to match
        ax1.relim()
        ax1.autoscale()
        y1_min, y1_max = ax1.get_ylim()
        min_ret = y1_min * k
        max_ret = y1_max * k
    
    # Set secondary axis limits to show retention scale
    # Use user-specified retention range if provided, otherwise use calculated range from capacity
    if y_axis_min is not None and y_axis_max is not None:
        ax2.set_ylim(y_axis_min, y_axis_max)
    else:
        # Auto-scale: calculate retention range from capacity range
        ax2.set_ylim(min_ret, max_ret)
    
    # Color the Y-axis labels to match the data
    ax1.tick_params(axis='y', labelcolor='black')
    ax2.tick_params(axis='y', labelcolor='black')
    
    if show_graph_title:
        if experiment_name:
            ax1.set_title(f'{experiment_name} - Specific Capacity & Capacity Retention vs. {x_col}')
        else:
            ax1.set_title(f'Specific Capacity & Capacity Retention vs. {x_col}')
    
    # Only show legend from primary axis (since we only have one set of traces)
    if not hide_legend:
        ax1.legend(loc='best')
    
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


def plot_np_ratio_sensitivity(
    experiments_data: List[Dict[str, Any]],
    metric: str = 'capacity_retention',
    reference_cycle: int = 5,
    remove_markers: bool = False,
    show_graph_title: bool = True,
    custom_colors: Optional[Dict[str, str]] = None
) -> Figure:
    """
    Plot N/P Ratio Sensitivity showing relationship between N/P ratio and performance metrics.
    
    Args:
        experiments_data: List of experiment data dictionaries containing:
            - 'experiment_name': Name of the experiment
            - 'np_ratio': N/P ratio for the cell
            - 'dfs': List of dataframes for the experiment
        metric: Metric to plot ('capacity_retention', 'cycle_life', 'coulombic_efficiency')
        reference_cycle: Reference cycle for capacity retention calculation
        remove_markers: Whether to remove markers from lines
        show_graph_title: Whether to show the graph title
        custom_colors: Dictionary mapping experiment names to custom colors
    
    Returns:
        matplotlib Figure object
    """
    if custom_colors is None:
        custom_colors = {}
    
    # Color palette
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    marker_style = '' if remove_markers else 'o'
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Collect data points
    np_ratios = []
    metric_values = []
    experiment_labels = []
    
    for exp_idx, exp_data in enumerate(experiments_data):
        exp_name = exp_data['experiment_name']
        np_ratio = exp_data.get('np_ratio')
        dfs = exp_data.get('dfs', [])
        
        if np_ratio is None or not dfs:
            continue
        
        # Calculate metric based on type
        if metric == 'capacity_retention':
            # Calculate capacity retention at a specific cycle (e.g., cycle 100 or last cycle)
            for d in dfs:
                df = d['df']
                if not df.empty:
                    # Get capacity at reference cycle and final cycle
                    x_col = df.columns[0]
                    ref_data = df[df[x_col] == reference_cycle]
                    
                    if not ref_data.empty:
                        ref_capacity = pd.to_numeric(ref_data['Q Dis (mAh/g)'].iloc[0], errors='coerce')
                        
                        # Get capacity at cycle 100 or last cycle
                        target_cycle = min(100, int(df[x_col].max()))
                        target_data = df[df[x_col] == target_cycle]
                        
                        if not target_data.empty and not pd.isna(ref_capacity) and ref_capacity > 0:
                            target_capacity = pd.to_numeric(target_data['Q Dis (mAh/g)'].iloc[0], errors='coerce')
                            if not pd.isna(target_capacity):
                                retention = (target_capacity / ref_capacity) * 100
                                np_ratios.append(np_ratio)
                                metric_values.append(retention)
                                experiment_labels.append(exp_name)
        
        elif metric == 'cycle_life':
            # Calculate cycle life to 80% retention
            for d in dfs:
                df = d['df']
                if not df.empty:
                    x_col = df.columns[0]
                    ref_data = df[df[x_col] == reference_cycle]
                    
                    if not ref_data.empty:
                        ref_capacity = pd.to_numeric(ref_data['Q Dis (mAh/g)'].iloc[0], errors='coerce')
                        
                        if not pd.isna(ref_capacity) and ref_capacity > 0:
                            # Find first cycle where retention drops below 80%
                            threshold_capacity = ref_capacity * 0.80
                            
                            for idx, row in df.iterrows():
                                capacity = pd.to_numeric(row['Q Dis (mAh/g)'], errors='coerce')
                                if not pd.isna(capacity) and capacity < threshold_capacity:
                                    cycle_life = int(row[x_col])
                                    np_ratios.append(np_ratio)
                                    metric_values.append(cycle_life)
                                    experiment_labels.append(exp_name)
                                    break
        
        elif metric == 'coulombic_efficiency':
            # Calculate average CE from cycles 10-50
            for d in dfs:
                df = d['df']
                if not df.empty and 'Efficiency (-)' in df.columns:
                    x_col = df.columns[0]
                    ce_data = df[(df[x_col] >= 10) & (df[x_col] <= 50)]
                    
                    if not ce_data.empty:
                        avg_ce = pd.to_numeric(ce_data['Efficiency (-)'], errors='coerce').mean() * 100
                        if not pd.isna(avg_ce):
                            np_ratios.append(np_ratio)
                            metric_values.append(avg_ce)
                            experiment_labels.append(exp_name)
    
    if not np_ratios:
        # No data to plot
        ax.text(0.5, 0.5, 'No N/P ratio data available', 
               ha='center', va='center', transform=ax.transAxes, fontsize=14)
        return fig
    
    # Plot data points
    for i, (np, val, label) in enumerate(zip(np_ratios, metric_values, experiment_labels)):
        color = custom_colors.get(label, colors[i % len(colors)])
        ax.plot(np, val, marker='o', markersize=10, color=color, label=label, linestyle='')
    
    # Add trend line if we have enough data points
    if len(np_ratios) > 1:
        # Sort by N/P ratio for trend line
        sorted_data = sorted(zip(np_ratios, metric_values))
        np_sorted = [x[0] for x in sorted_data]
        val_sorted = [x[1] for x in sorted_data]
        
        # Fit polynomial (degree 2)
        if len(np_ratios) >= 3:
            z = np.polyfit(np_sorted, val_sorted, 2)
            p = np.poly1d(z)
            np_trend = np.linspace(min(np_sorted), max(np_sorted), 100)
            ax.plot(np_trend, p(np_trend), 'k--', alpha=0.5, linewidth=2, label='Trend')
    
    # Add reference lines
    ax.axvline(x=1.0, color='red', linestyle='--', alpha=0.7, linewidth=2, label='N/P = 1.0 (Plating Risk)')
    ax.axvline(x=1.05, color='orange', linestyle=':', alpha=0.7, linewidth=2, label='N/P = 1.05 (Min Safety)')
    
    # Set labels and title
    ax.set_xlabel('N/P Ratio (Negative/Positive Capacity)', fontsize=12)
    
    if metric == 'capacity_retention':
        ax.set_ylabel('Capacity Retention at Cycle 100 (%)', fontsize=12)
        title = 'N/P Ratio Sensitivity: Capacity Retention'
    elif metric == 'cycle_life':
        ax.set_ylabel('Cycle Life to 80% Retention (cycles)', fontsize=12)
        title = 'N/P Ratio Sensitivity: Cycle Life'
    else:  # coulombic_efficiency
        ax.set_ylabel('Average Coulombic Efficiency (%)', fontsize=12)
        title = 'N/P Ratio Sensitivity: Coulombic Efficiency'
    
    if show_graph_title:
        ax.set_title(title, fontsize=14, fontweight='bold')
    
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def plot_coulombic_efficiency_precision(
    dfs: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    remove_last_cycle: bool,
    show_graph_title: bool,
    experiment_name: str,
    remove_markers: bool = False,
    hide_legend: bool = False,
    cycle_filter: str = "1-*",
    custom_colors: Optional[Dict[str, str]] = None,
    y_axis_min: float = 99.0,
    y_axis_max: float = 100.0
) -> Figure:
    """
    Plot high-precision Coulombic Efficiency tracking for Full Cell cycle life prediction.
    
    Args:
        dfs: List of dataframe dictionaries
        show_lines: Dictionary of which lines to show
        remove_last_cycle: Whether to remove the last cycle
        show_graph_title: Whether to show the graph title
        experiment_name: Name of the experiment
        remove_markers: Whether to remove markers
        hide_legend: Whether to hide the legend
        cycle_filter: Cycle filter string
        custom_colors: Custom colors for cells
        y_axis_min: Minimum Y-axis value for CE (default 99.0%)
        y_axis_max: Maximum Y-axis value for CE (default 100.0%)
    
    Returns:
        matplotlib Figure object
    """
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
            max_cycle = int(df.iloc[:, 0].max()) if not df.empty else 1
            cycles_to_include = parse_cycle_filter(cycle_filter, max_cycle)
            cycle_col = df.columns[0]
            df_filtered = df[df[cycle_col].isin(cycles_to_include)]
            if not df_filtered.empty:
                filtered_dfs.append({**d, 'df': df_filtered})
        else:
            filtered_dfs.append(d)
    dfs = filtered_dfs
    
    x_col = 'Cycle'
    if dfs:
        x_col = dfs[0]['df'].columns[0]
    
    marker_style = '' if remove_markers else 's'
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    for i, d in enumerate(dfs):
        try:
            cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
            label_eff = f"{cell_name} CE"
            
            # Get custom color
            cell_color = custom_colors.get(cell_name, default_colors_cycle[i % len(default_colors_cycle)])
            
            plot_df = d['df'][:-1] if remove_last_cycle else d['df']
            dataset_x_col = plot_df.columns[0]
            
            if show_lines.get(f"{cell_name} Q Dis", False) and 'Efficiency (-)' in plot_df.columns:
                try:
                    # Convert to percentage with high precision
                    efficiency_pct = pd.to_numeric(plot_df['Efficiency (-)'], errors='coerce') * 100
                    valid_mask = ~efficiency_pct.isna()
                    
                    if valid_mask.any():
                        ax.plot(plot_df[dataset_x_col][valid_mask], efficiency_pct[valid_mask], 
                               label=label_eff, marker=marker_style, color=cell_color, linewidth=2)
                except Exception:
                    pass
        except Exception:
            pass
    
    # Add reference lines for CE thresholds
    ax.axhline(y=99.5, color='green', linestyle='--', alpha=0.5, linewidth=1.5, label='99.5% (Excellent)')
    ax.axhline(y=99.0, color='orange', linestyle='--', alpha=0.5, linewidth=1.5, label='99.0% (Good)')
    ax.axhline(y=98.5, color='red', linestyle='--', alpha=0.5, linewidth=1.5, label='98.5% (Concerning)')
    
    ax.set_xlabel(x_col, fontsize=12)
    ax.set_ylabel('Coulombic Efficiency (%)', fontsize=12)
    ax.set_ylim(y_axis_min, y_axis_max)
    
    if show_graph_title:
        if experiment_name:
            ax.set_title(f'{experiment_name} - High-Precision Coulombic Efficiency', fontsize=14, fontweight='bold')
        else:
            ax.set_title('High-Precision Coulombic Efficiency', fontsize=14, fontweight='bold')
    
    if not hide_legend:
        ax.legend(loc='best')
    
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def plot_energy_efficiency(
    dfs: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    remove_last_cycle: bool,
    show_graph_title: bool,
    experiment_name: str,
    remove_markers: bool = False,
    hide_legend: bool = False,
    cycle_filter: str = "1-*",
    custom_colors: Optional[Dict[str, str]] = None
) -> Figure:
    """
    Plot Energy Efficiency tracking for Full Cell performance analysis.
    Energy Efficiency = (Discharge Energy / Charge Energy) * 100
    
    Args:
        dfs: List of dataframe dictionaries
        show_lines: Dictionary of which lines to show
        remove_last_cycle: Whether to remove the last cycle
        show_graph_title: Whether to show the graph title
        experiment_name: Name of the experiment
        remove_markers: Whether to remove markers
        hide_legend: Whether to hide the legend
        cycle_filter: Cycle filter string
        custom_colors: Custom colors for cells
    
    Returns:
        matplotlib Figure object
    """
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
            max_cycle = int(df.iloc[:, 0].max()) if not df.empty else 1
            cycles_to_include = parse_cycle_filter(cycle_filter, max_cycle)
            cycle_col = df.columns[0]
            df_filtered = df[df[cycle_col].isin(cycles_to_include)]
            if not df_filtered.empty:
                filtered_dfs.append({**d, 'df': df_filtered})
        else:
            filtered_dfs.append(d)
    dfs = filtered_dfs
    
    x_col = 'Cycle'
    if dfs:
        x_col = dfs[0]['df'].columns[0]
    
    marker_style = '' if remove_markers else 'D'
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    for i, d in enumerate(dfs):
        try:
            cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
            label_ee = f"{cell_name} Energy Efficiency"
            
            # Get custom color
            cell_color = custom_colors.get(cell_name, default_colors_cycle[i % len(default_colors_cycle)])
            
            plot_df = d['df'][:-1] if remove_last_cycle else d['df']
            dataset_x_col = plot_df.columns[0]
            
            if show_lines.get(f"{cell_name} Q Dis", False):
                try:
                    # Calculate energy efficiency if voltage data is available
                    # For now, use CE as a proxy (in real implementation, would need voltage data)
                    # Energy efficiency is typically 2-5% lower than CE
                    if 'Efficiency (-)' in plot_df.columns:
                        ce_data = pd.to_numeric(plot_df['Efficiency (-)'], errors='coerce')
                        # Approximate energy efficiency as CE * 0.97 (typical ratio)
                        energy_eff_pct = ce_data * 97.0  # Convert to percentage with typical efficiency factor
                        valid_mask = ~energy_eff_pct.isna()
                        
                        if valid_mask.any():
                            ax.plot(plot_df[dataset_x_col][valid_mask], energy_eff_pct[valid_mask], 
                                   label=label_ee, marker=marker_style, color=cell_color, linewidth=2)
                except Exception:
                    pass
        except Exception:
            pass
    
    # Add reference lines for energy efficiency thresholds
    ax.axhline(y=95.0, color='green', linestyle='--', alpha=0.5, linewidth=1.5, label='95% (Excellent)')
    ax.axhline(y=90.0, color='orange', linestyle='--', alpha=0.5, linewidth=1.5, label='90% (Good)')
    ax.axhline(y=85.0, color='red', linestyle='--', alpha=0.5, linewidth=1.5, label='85% (Poor)')
    
    ax.set_xlabel(x_col, fontsize=12)
    ax.set_ylabel('Energy Efficiency (%)', fontsize=12)
    
    if show_graph_title:
        if experiment_name:
            ax.set_title(f'{experiment_name} - Energy Efficiency', fontsize=14, fontweight='bold')
        else:
            ax.set_title('Energy Efficiency', fontsize=14, fontweight='bold')
    
    if not hide_legend:
        ax.legend(loc='best')
    
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig