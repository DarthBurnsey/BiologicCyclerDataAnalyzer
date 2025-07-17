# plotting.py
import matplotlib.pyplot as plt
import pandas as pd
from typing import List, Dict, Any
from matplotlib.figure import Figure

def plot_capacity_graph(
    dfs: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    show_efficiency_lines: Dict[str, bool],
    remove_last_cycle: bool,
    show_graph_title: bool,
    experiment_name: str,
    show_average_performance: bool = False
) -> Figure:
    """Plot the main capacity/efficiency graph and return the matplotlib figure."""
    x_col = 'Cycle'  # default
    if dfs:
        x_col = dfs[0]['df'].columns[0]
    any_efficiency = any(show_efficiency_lines.values())
    if any_efficiency:
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
                    ax1.plot(plot_df[dataset_x_col], plot_df['Q Dis (mAh/g)'], label=label_dis, marker='o')
                if show_lines.get(label_chg, False):
                    ax1.plot(plot_df[dataset_x_col], plot_df['Q Chg (mAh/g)'], label=label_chg, marker='o')
            except Exception:
                pass
        for i, d in enumerate(dfs):
            try:
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_eff = f"{cell_name} Efficiency"
                plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                dataset_x_col = plot_df.columns[0]
                if show_efficiency_lines.get(label_eff, False) and 'Efficiency (-)' in plot_df.columns and not plot_df['Efficiency (-)'].empty:
                    efficiency_pct = plot_df['Efficiency (-)'] * 100
                    ax2.plot(plot_df[dataset_x_col], efficiency_pct, label=f'{cell_name} Efficiency (%)', linestyle='--', marker='s', alpha=0.7)
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
                                qdis_vals.append(row['Q Dis (mAh/g)'].values[0])
                            if 'Q Chg (mAh/g)' in row:
                                qchg_vals.append(row['Q Chg (mAh/g)'].values[0])
                            if 'Efficiency (-)' in row and not pd.isnull(row['Efficiency (-)'].values[0]):
                                eff_vals.append(row['Efficiency (-)'].values[0] * 100)
                    avg_qdis.append(sum(qdis_vals)/len(qdis_vals) if qdis_vals else None)
                    avg_qchg.append(sum(qchg_vals)/len(qchg_vals) if qchg_vals else None)
                    avg_eff.append(sum(eff_vals)/len(eff_vals) if eff_vals else None)
                avg_label_prefix = f"{experiment_name} " if experiment_name else ""
                ax1.plot(common_cycles, avg_qdis, label=f'{avg_label_prefix}Average Q Dis', color='black', linewidth=2, marker='D')
                ax1.plot(common_cycles, avg_qchg, label=f'{avg_label_prefix}Average Q Chg', color='gray', linewidth=2, marker='D')
                ax2.plot(common_cycles, avg_eff, label=f'{avg_label_prefix}Average Efficiency (%)', color='orange', linewidth=2, linestyle='--', marker='D', alpha=0.7)
        ax1.set_xlabel(x_col)
        ax1.set_ylabel('Capacity (mAh/g)', color='blue')
        ax2.set_ylabel('Efficiency (%)', color='red')
        if show_graph_title:
            if experiment_name:
                ax1.set_title(f'{experiment_name} - Gravimetric Capacity and Efficiency vs. ' + x_col)
            else:
                ax1.set_title('Gravimetric Capacity and Efficiency vs. ' + x_col)
        ax1.tick_params(axis='y', labelcolor='blue')
        ax2.tick_params(axis='y', labelcolor='red')
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
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
                    ax.plot(plot_df[dataset_x_col], plot_df['Q Dis (mAh/g)'], label=label_dis, marker='o')
                if show_lines.get(label_chg, False):
                    ax.plot(plot_df[dataset_x_col], plot_df['Q Chg (mAh/g)'], label=label_chg, marker='o')
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
                                qdis_vals.append(row['Q Dis (mAh/g)'].values[0])
                            if 'Q Chg (mAh/g)' in row:
                                qchg_vals.append(row['Q Chg (mAh/g)'].values[0])
                    avg_qdis.append(sum(qdis_vals)/len(qdis_vals) if qdis_vals else None)
                    avg_qchg.append(sum(qchg_vals)/len(qchg_vals) if qchg_vals else None)
                avg_label_prefix = f"{experiment_name} " if experiment_name else ""
                ax.plot(common_cycles, avg_qdis, label=f'{avg_label_prefix}Average Q Dis', color='black', linewidth=2, marker='D')
                ax.plot(common_cycles, avg_qchg, label=f'{avg_label_prefix}Average Q Chg', color='gray', linewidth=2, marker='D')
        ax.set_xlabel(x_col)
        ax.set_ylabel('Capacity (mAh/g)')
        if show_graph_title:
            if experiment_name:
                ax.set_title(f'{experiment_name} - Gravimetric Capacity vs. ' + x_col)
            else:
                ax.set_title('Gravimetric Capacity vs. ' + x_col)
        ax.legend()
        return fig 