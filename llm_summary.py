# llm_summary.py
"""
Generate token-efficient summaries of experimental data for LLM analysis.
Focuses on experiment-level information with capacity vs cycle plots.
"""
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from io import StringIO, BytesIO
import base64
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from database import get_experiment_by_id, get_project_by_id
from data_analysis import calculate_cell_summary


def format_formulation_compact(formulation: List[Dict]) -> str:
    """Format formulation as compact string."""
    if not formulation:
        return "N/A"
    parts = []
    for comp in formulation:
        name = comp.get('Component', 'Unknown')
        pct = comp.get('Dry Mass Fraction (%)', 0)
        parts.append(f"{name}:{pct:.1f}%")
    return "|".join(parts)


def extract_curve_characteristics(df: pd.DataFrame, formation_cycles: int = 4) -> Dict[str, Any]:
    """
    Extract key characteristics from capacity vs cycle curve.
    Returns statistical descriptors instead of raw data.
    """
    if df.empty or 'Q Dis (mAh/g)' not in df.columns:
        return {}
    
    qdis = pd.to_numeric(df['Q Dis (mAh/g)'], errors='coerce').dropna()
    if len(qdis) < formation_cycles + 2:
        return {}
    
    cycle_col = df.columns[0]
    cycles = pd.to_numeric(df[cycle_col], errors='coerce').dropna()
    
    # Post-formation data
    post_formation = qdis.iloc[formation_cycles:]
    post_formation_cycles = cycles.iloc[formation_cycles:]
    
    if len(post_formation) < 2:
        return {}
    
    initial_capacity = post_formation.iloc[0]
    final_capacity = post_formation.iloc[-1]
    total_cycles = len(post_formation)
    
    # Degradation rate (% per cycle)
    if total_cycles > 1 and initial_capacity > 0:
        degradation_rate = ((initial_capacity - final_capacity) / initial_capacity) / total_cycles * 100
    else:
        degradation_rate = 0
    
    # Stability (coefficient of variation)
    stability = (post_formation.std() / post_formation.mean() * 100) if post_formation.mean() > 0 else None
    
    # Check for sudden drops (failure indicators)
    capacity_drops = []
    for i in range(1, len(post_formation)):
        if post_formation.iloc[i-1] > 0:
            drop_pct = ((post_formation.iloc[i-1] - post_formation.iloc[i]) / post_formation.iloc[i-1]) * 100
            if drop_pct > 5:  # >5% drop in one cycle
                capacity_drops.append({
                    'cycle': int(post_formation_cycles.iloc[i]) if i < len(post_formation_cycles) else None,
                    'drop_pct': round(drop_pct, 2)
                })
    
    # Formation behavior
    formation_data = qdis.iloc[:formation_cycles] if len(qdis) >= formation_cycles else qdis
    if len(formation_data) > 1:
        formation_trend = "increasing" if formation_data.iloc[-1] > formation_data.iloc[0] else "decreasing"
    else:
        formation_trend = "stable"
    
    # Capacity retention at key points
    retention_50 = None
    retention_100 = None
    if len(qdis) > formation_cycles + 50:
        retention_50 = (qdis.iloc[formation_cycles + 50] / initial_capacity * 100) if initial_capacity > 0 else None
    if len(qdis) > formation_cycles + 100:
        retention_100 = (qdis.iloc[formation_cycles + 100] / initial_capacity * 100) if initial_capacity > 0 else None
    
    return {
        'initial_capacity': round(initial_capacity, 1),
        'final_capacity': round(final_capacity, 1),
        'total_cycles': total_cycles,
        'degradation_rate': round(degradation_rate, 3),  # % per cycle
        'stability_cv': round(stability, 2) if stability else None,  # Coefficient of variation
        'capacity_drops': capacity_drops,  # Sudden drops >5%
        'formation_trend': formation_trend,
        'retention_50cyc': round(retention_50, 1) if retention_50 else None,
        'retention_100cyc': round(retention_100, 1) if retention_100 else None
    }


def generate_capacity_plot_image(experiment_data: Dict[str, Any], project_type: str = "Full Cell") -> Optional[str]:
    """
    Generate a compact capacity vs cycle plot and return as base64 string.
    Shows discharge capacity for all cells in the experiment.
    """
    try:
        cells_data = experiment_data.get('cells', [])
        if not cells_data:
            return None
        
        # Create compact plot
        fig, ax = plt.subplots(figsize=(8, 5))
        
        colors = plt.cm.tab10(np.linspace(0, 1, min(len(cells_data), 10)))
        
        plotted_cells = 0
        for i, cell_data in enumerate(cells_data):
            try:
                # Load cell cycle data
                if 'data_json' not in cell_data:
                    continue
                
                df = pd.read_json(StringIO(cell_data['data_json']))
                if df.empty or 'Q Dis (mAh/g)' not in df.columns:
                    continue
                
                cycle_col = df.columns[0]
                qdis = pd.to_numeric(df['Q Dis (mAh/g)'], errors='coerce')
                
                # Filter out NaN values
                valid_mask = ~qdis.isna()
                if not valid_mask.any():
                    continue
                
                cycles = pd.to_numeric(df[cycle_col], errors='coerce')[valid_mask]
                qdis_valid = qdis[valid_mask]
                
                if len(cycles) == 0 or len(qdis_valid) == 0:
                    continue
                
                cell_name = cell_data.get('test_number') or cell_data.get('cell_name', f'Cell {i+1}')
                color = colors[i % len(colors)]
                
                ax.plot(cycles, qdis_valid, marker='o', markersize=3, label=cell_name, 
                       color=color, linewidth=1.5, alpha=0.8)
                plotted_cells += 1
                
            except Exception as e:
                print(f"Error plotting cell {i}: {e}")
                continue
        
        # Only return plot if we actually plotted something
        if plotted_cells == 0:
            plt.close(fig)
            return None
        
        ax.set_xlabel('Cycle Number', fontsize=11)
        ax.set_ylabel('Discharge Capacity (mAh/g)', fontsize=11)
        ax.set_title(f"{experiment_data.get('experiment_name', 'Experiment')} - Capacity vs Cycle", 
                    fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        if plotted_cells > 0:
            ax.legend(loc='best', fontsize=9, framealpha=0.9)
        
        plt.tight_layout()
        
        # Save to base64
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        
        return img_base64
    except Exception as e:
        print(f"Error generating plot: {e}")
        return None


def generate_experiment_summary(experiment_id: int) -> Tuple[str, Optional[str], Dict[str, Any]]:
    """
    Generate a token-efficient summary of a single experiment for LLM analysis.
    
    Returns:
        (summary_text, plot_image_base64, stats_dict)
    """
    # Get experiment data from database
    exp_data = get_experiment_by_id(experiment_id)
    if not exp_data:
        return "Experiment not found.", None, {}
    
    exp_id, project_id, cell_name, file_name, loading, active_material, \
    formation_cycles, test_number, electrolyte, substrate, separator, \
    formulation_json, data_json, solids_content, pressed_thickness, \
    experiment_notes, created_date, porosity = exp_data
    
    # Get project type
    project_info = get_project_by_id(project_id)
    project_type = project_info[3] if project_info else "Full Cell"
    
    # Parse experiment data
    experiment_data = {}
    cells_data = []
    
    if data_json:
        try:
            experiment_data = json.loads(data_json)
            cells_data = experiment_data.get('cells', [])
        except:
            pass
    
    # Parse formulation
    formulation = []
    if formulation_json:
        try:
            formulation = json.loads(formulation_json)
        except:
            pass
    
    # Calculate metrics for each cell
    cell_summaries = []
    disc_diameter_mm = experiment_data.get('disc_diameter_mm', 15)
    disc_area_cm2 = np.pi * (disc_diameter_mm / 20) ** 2
    
    for cell_data in cells_data:
        try:
            if 'data_json' in cell_data:
                df = pd.read_json(StringIO(cell_data['data_json']))
                if not df.empty:
                    cell_metrics = calculate_cell_summary(
                        df, cell_data, disc_area_cm2, project_type
                    )
                    curve_chars = extract_curve_characteristics(
                        df, cell_data.get('formation_cycles', formation_cycles or 4)
                    )
                    cell_summaries.append({
                        'cell_name': cell_data.get('test_number') or cell_data.get('cell_name', 'Unknown'),
                        'metrics': cell_metrics,
                        'curve': curve_chars,
                        'formulation': cell_data.get('formulation', []),
                        'loading': cell_data.get('loading'),
                        'active_material': cell_data.get('active_material'),
                        'porosity': cell_data.get('porosity')
                    })
        except Exception as e:
            print(f"Error processing cell: {e}")
            continue
    
    # Generate summary text
    lines = []
    
    # Experiment header
    lines.append(f"EXPERIMENT: {cell_name}")
    if created_date:
        lines.append(f"Date: {str(created_date)[:10]}")
    lines.append(f"Cells: {len(cell_summaries)}")
    lines.append("")
    
    # Experiment-level parameters
    lines.append("EXPERIMENT PARAMETERS:")
    if loading:
        lines.append(f"  Loading: {loading:.1f} mg/cm²")
    if active_material:
        lines.append(f"  Active Material: {active_material:.1f}%")
    if formation_cycles:
        lines.append(f"  Formation Cycles: {formation_cycles}")
    if disc_diameter_mm:
        lines.append(f"  Disc Diameter: {disc_diameter_mm:.1f} mm")
    if pressed_thickness:
        lines.append(f"  Pressed Thickness: {pressed_thickness:.1f} μm")
    if solids_content:
        lines.append(f"  Solids Content: {solids_content:.1f}%")
    if porosity:
        lines.append(f"  Average Porosity: {porosity:.1f}%")
    if electrolyte:
        lines.append(f"  Electrolyte: {electrolyte}")
    if substrate:
        lines.append(f"  Substrate: {substrate}")
    if separator:
        lines.append(f"  Separator: {separator}")
    lines.append("")
    
    # Formulation
    if formulation:
        lines.append("FORMULATION:")
        for comp in formulation:
            comp_name = comp.get('Component', 'Unknown')
            comp_pct = comp.get('Dry Mass Fraction (%)', 0)
            lines.append(f"  {comp_name}: {comp_pct:.1f}%")
        lines.append("")
    
    # Experiment notes
    if experiment_notes:
        lines.append(f"NOTES: {experiment_notes}")
        lines.append("")
    
    # Cell-level summaries
    lines.append("CELL PERFORMANCE:")
    
    # Calculate averages
    numeric_fields = ['reversible_capacity', 'first_discharge', 'first_efficiency', 
                     'cycle_life_80', 'coulombic_efficiency', 'areal_capacity']
    cell_averages = {}
    cell_mins = {}
    cell_maxs = {}
    
    for field in numeric_fields:
        values = [c['metrics'].get(field) for c in cell_summaries if c['metrics'].get(field) is not None]
        if values:
            cell_averages[field] = np.mean(values)
            cell_mins[field] = np.min(values)
            cell_maxs[field] = np.max(values)
    
    # Average performance
    if cell_averages:
        lines.append("  Average Performance:")
        if 'reversible_capacity' in cell_averages:
            rc_avg = cell_averages['reversible_capacity']
            rc_min = cell_mins.get('reversible_capacity', rc_avg)
            rc_max = cell_maxs.get('reversible_capacity', rc_avg)
            lines.append(f"    Reversible Capacity: {rc_avg:.1f} mAh/g (range: {rc_min:.1f}-{rc_max:.1f})")
        if 'first_efficiency' in cell_averages:
            fe_avg = cell_averages['first_efficiency']
            lines.append(f"    First Efficiency: {fe_avg:.1f}%")
        if 'cycle_life_80' in cell_averages:
            cl_avg = cell_averages['cycle_life_80']
            lines.append(f"    Cycle Life (80%): {cl_avg:.0f} cycles")
        if 'coulombic_efficiency' in cell_averages:
            ce_avg = cell_averages['coulombic_efficiency']
            lines.append(f"    Avg Coulombic Efficiency: {ce_avg:.1f}%")
        lines.append("")
    
    # Individual cell details
    for i, cell in enumerate(cell_summaries, 1):
        lines.append(f"  Cell {i}: {cell['cell_name']}")
        
        m = cell['metrics']
        perf_parts = []
        if m.get('reversible_capacity'):
            perf_parts.append(f"RC:{m['reversible_capacity']:.1f}mAh/g")
        if m.get('first_efficiency'):
            perf_parts.append(f"FE:{m['first_efficiency']:.1f}%")
        if m.get('cycle_life_80'):
            perf_parts.append(f"CL:{m['cycle_life_80']:.0f}cyc")
        if perf_parts:
            lines.append(f"    Performance: {', '.join(perf_parts)}")
        
        # Curve characteristics
        curve = cell['curve']
        if curve:
            curve_parts = []
            if curve.get('degradation_rate') is not None:
                curve_parts.append(f"DegRate:{curve['degradation_rate']:.3f}%/cyc")
            if curve.get('stability_cv'):
                curve_parts.append(f"Stability:{curve['stability_cv']:.2f}%CV")
            if curve.get('retention_50cyc'):
                curve_parts.append(f"R50:{curve['retention_50cyc']:.1f}%")
            if curve.get('capacity_drops'):
                curve_parts.append(f"Drops:{len(curve['capacity_drops'])}")
            if curve_parts:
                lines.append(f"    Curve: {', '.join(curve_parts)}")
        
        lines.append("")
    
    # Generate plot image
    plot_image_base64 = None
    if cells_data:
        experiment_data_for_plot = {
            'experiment_name': cell_name,
            'cells': cells_data
        }
        plot_image_base64 = generate_capacity_plot_image(experiment_data_for_plot, project_type)
    
    summary_text = "\n".join(lines)
    
    # Calculate stats
    stats = {
        'token_estimate': len(summary_text) // 4,  # Rough estimate
        'char_count': len(summary_text),
        'line_count': len(summary_text.split('\n')),
        'num_cells': len(cell_summaries),
        'has_plot': plot_image_base64 is not None
    }
    
    return summary_text, plot_image_base64, stats


def estimate_token_count(text: str) -> int:
    """Rough estimate of token count (1 token ≈ 4 characters)."""
    return len(text) // 4

