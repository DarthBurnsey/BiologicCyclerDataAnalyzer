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
    group_names: Optional[list] = None
) -> Figure:
    """Plot the main capacity/efficiency graph and return the matplotlib figure. If remove_markers is True, lines will have no markers. If hide_legend is True, the legend will not be shown. Optionally plot group average curves for Group A, B, and C."""
    if avg_line_toggles is None:
        avg_line_toggles = {"Average Q Dis": True, "Average Q Chg": True, "Average Efficiency": True}
    if group_names is None:
        group_names = ["Group A", "Group B", "Group C"]
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
                plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                dataset_x_col = plot_df.columns[0]
                if show_lines.get(label_dis, False):
                    try:
                        # Convert to numeric, handling any string values
                        qdis_data = pd.to_numeric(plot_df['Q Dis (mAh/g)'], errors='coerce')
                        valid_mask = ~qdis_data.isna()
                        if valid_mask.any():
                            ax1.plot(plot_df[dataset_x_col][valid_mask], qdis_data[valid_mask], label=label_dis, marker=marker_style)
                    except Exception:
                        pass
                if show_lines.get(label_chg, False):
                    try:
                        # Convert to numeric, handling any string values
                        qchg_data = pd.to_numeric(plot_df['Q Chg (mAh/g)'], errors='coerce')
                        valid_mask = ~qchg_data.isna()
                        if valid_mask.any():
                            ax1.plot(plot_df[dataset_x_col][valid_mask], qchg_data[valid_mask], label=label_chg, marker=marker_style)
                    except Exception:
                        pass
            except Exception:
                pass
        for i, d in enumerate(dfs):
            try:
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_eff = f"{cell_name} Efficiency"
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
                                   label=f'{cell_name} Efficiency (%)', linestyle='--', marker=eff_marker_style, alpha=0.7)
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
                if avg_line_toggles.get("Average Q Dis", True):
                    ax1.plot(common_cycles, avg_qdis, label=f'{avg_label_prefix}Average Q Dis', color='black', linewidth=2, marker=avg_marker_style)
                if avg_line_toggles.get("Average Q Chg", True):
                    ax1.plot(common_cycles, avg_qchg, label=f'{avg_label_prefix}Average Q Chg', color='gray', linewidth=2, marker=avg_marker_style)
                if avg_line_toggles.get("Average Efficiency", True):
                    ax2.plot(common_cycles, avg_eff, label=f'{avg_label_prefix}Average Efficiency (%)', color='orange', linewidth=2, linestyle='--', marker=avg_marker_style, alpha=0.7)
        # --- Plot group averages if provided ---
        if group_a_curve is not None:
            cycles, avg_qdis = group_a_curve
            if cycles and avg_qdis:
                ax1.plot(cycles, avg_qdis, label=f'{group_names[0]} Avg Q Dis', color='blue', linewidth=2, linestyle='-', marker='x')
        if group_b_curve is not None:
            cycles, avg_qdis = group_b_curve
            if cycles and avg_qdis:
                ax1.plot(cycles, avg_qdis, label=f'{group_names[1]} Avg Q Dis', color='red', linewidth=2, linestyle='-', marker='x')
        if group_c_curve is not None:
            cycles, avg_qdis = group_c_curve
            if cycles and avg_qdis:
                ax1.plot(cycles, avg_qdis, label=f'{group_names[2]} Avg Q Dis', color='green', linewidth=2, linestyle='-', marker='x')
        if group_a_qchg is not None:
            cycles, avg_qchg = group_a_qchg
            if cycles and avg_qchg:
                ax1.plot(cycles, avg_qchg, label=f'{group_names[0]} Avg Q Chg', color='blue', linewidth=2, linestyle='--', marker='x')
        if group_b_qchg is not None:
            cycles, avg_qchg = group_b_qchg
            if cycles and avg_qchg:
                ax1.plot(cycles, avg_qchg, label=f'{group_names[1]} Avg Q Chg', color='red', linewidth=2, linestyle='--', marker='x')
        if group_c_qchg is not None:
            cycles, avg_qchg = group_c_qchg
            if cycles and avg_qchg:
                ax1.plot(cycles, avg_qchg, label=f'{group_names[2]} Avg Q Chg', color='green', linewidth=2, linestyle='--', marker='x')
        if group_a_eff is not None:
            cycles, avg_eff = group_a_eff
            if cycles and avg_eff:
                ax2.plot(cycles, avg_eff, label=f'{group_names[0]} Avg Efficiency (%)', color='blue', linewidth=2, linestyle='--', marker='x', alpha=0.7)
        if group_b_eff is not None:
            cycles, avg_eff = group_b_eff
            if cycles and avg_eff:
                ax2.plot(cycles, avg_eff, label=f'{group_names[1]} Avg Efficiency (%)', color='red', linewidth=2, linestyle='--', marker='x', alpha=0.7)
        if group_c_eff is not None:
            cycles, avg_eff = group_c_eff
            if cycles and avg_eff:
                ax2.plot(cycles, avg_eff, label=f'{group_names[2]} Avg Efficiency (%)', color='green', linewidth=2, linestyle='--', marker='x', alpha=0.7)
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
        return fig
    else:
        fig, ax = plt.subplots()
        for i, d in enumerate(dfs):
            try:
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_dis = f"{cell_name} Q Dis"
                label_chg = f"{cell_name} Q Chg"
                plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                dataset_x_col = plot_df.columns[0]
                if show_lines.get(label_dis, False):
                    try:
                        # Convert to numeric, handling any string values
                        qdis_data = pd.to_numeric(plot_df['Q Dis (mAh/g)'], errors='coerce')
                        valid_mask = ~qdis_data.isna()
                        if valid_mask.any():
                            ax.plot(plot_df[dataset_x_col][valid_mask], qdis_data[valid_mask], label=label_dis, marker=marker_style)
                    except Exception:
                        pass
                if show_lines.get(label_chg, False):
                    try:
                        # Convert to numeric, handling any string values
                        qchg_data = pd.to_numeric(plot_df['Q Chg (mAh/g)'], errors='coerce')
                        valid_mask = ~qchg_data.isna()
                        if valid_mask.any():
                            ax.plot(plot_df[dataset_x_col][valid_mask], qchg_data[valid_mask], label=label_chg, marker=marker_style)
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
                if avg_line_toggles.get("Average Q Dis", True):
                    ax.plot(common_cycles, avg_qdis, label=f'{avg_label_prefix}Average Q Dis', color='black', linewidth=2, marker=avg_marker_style)
                if avg_line_toggles.get("Average Q Chg", True):
                    ax.plot(common_cycles, avg_qchg, label=f'{avg_label_prefix}Average Q Chg', color='gray', linewidth=2, marker=avg_marker_style)
        # --- Plot group averages if provided ---
        if group_a_curve is not None:
            cycles, avg_qdis = group_a_curve
            if cycles and avg_qdis:
                ax.plot(cycles, avg_qdis, label=f'{group_names[0]} Avg Q Dis', color='blue', linewidth=2, linestyle='-', marker='x')
        if group_b_curve is not None:
            cycles, avg_qdis = group_b_curve
            if cycles and avg_qdis:
                ax.plot(cycles, avg_qdis, label=f'{group_names[1]} Avg Q Dis', color='red', linewidth=2, linestyle='-', marker='x')
        if group_c_curve is not None:
            cycles, avg_qdis = group_c_curve
            if cycles and avg_qdis:
                ax.plot(cycles, avg_qdis, label=f'{group_names[2]} Avg Q Dis', color='green', linewidth=2, linestyle='-', marker='x')
        if group_a_qchg is not None:
            cycles, avg_qchg = group_a_qchg
            if cycles and avg_qchg:
                ax.plot(cycles, avg_qchg, label=f'{group_names[0]} Avg Q Chg', color='blue', linewidth=2, linestyle='--', marker='x')
        if group_b_qchg is not None:
            cycles, avg_qchg = group_b_qchg
            if cycles and avg_qchg:
                ax.plot(cycles, avg_qchg, label=f'{group_names[1]} Avg Q Chg', color='red', linewidth=2, linestyle='--', marker='x')
        if group_c_qchg is not None:
            cycles, avg_qchg = group_c_qchg
            if cycles and avg_qchg:
                ax.plot(cycles, avg_qchg, label=f'{group_names[2]} Avg Q Chg', color='green', linewidth=2, linestyle='--', marker='x')
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
        return fig 