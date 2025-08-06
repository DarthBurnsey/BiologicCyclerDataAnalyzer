import pandas as pd
import numpy as np

def calculate_cell_summary(df, cell_data, disc_area_cm2, project_type="Full Cell"):
    """Calculate summary statistics for a single cell."""
    try:
        # Basic cell info
        cell_name = cell_data.get('test_number') or cell_data.get('cell_name', 'Unknown')
        loading = cell_data.get('loading', 0)
        active_material = cell_data.get('active_material', 0)
        formation_cycles = cell_data.get('formation_cycles', 4)
        
        # 1st Cycle Discharge Capacity (mAh/g)
        first_three_qdis = df['Q Dis (mAh/g)'].head(3).tolist()
        max_qdis = max(first_three_qdis) if first_three_qdis else None
        
        # First Cycle Efficiency (%)
        eff_pct = None
        if 'Efficiency (-)' in df.columns and not df['Efficiency (-)'].empty:
            # Use corrected efficiency calculation for anode projects
            if project_type == "Anode" and 'Q charge (mA.h)' in df.columns and 'Q discharge (mA.h)' in df.columns:
                # Recalculate efficiency using corrected method for anode projects
                from data_processing import calculate_efficiency_based_on_project_type
                corrected_efficiency = calculate_efficiency_based_on_project_type(
                    df['Q charge (mA.h)'], 
                    df['Q discharge (mA.h)'], 
                    project_type
                ) / 100  # Convert to decimal for consistency
                
                # Use corrected efficiency for first cycle
                first_cycle_eff = corrected_efficiency.iloc[0]
                try:
                    eff_pct = float(first_cycle_eff) * 100
                except (ValueError, TypeError):
                    eff_pct = None
            else:
                # Use original efficiency calculation for non-anode projects
                first_cycle_eff = df['Efficiency (-)'].iloc[0]
                try:
                    eff_pct = float(first_cycle_eff) * 100
                except (ValueError, TypeError):
                    eff_pct = None
        
        # Cycle Life (80%)
        cycle_life_80 = None
        try:
            qdis_series = df['Q Dis (mAh/g)'].dropna()
            cycle_index_series = df[df.columns[0]].iloc[qdis_series.index]
            cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
        except:
            pass
        
        # Initial Areal Capacity (mAh/cm²)
        areal_capacity = None
        try:
            from ui_components import get_initial_areal_capacity
            areal_capacity, _, _, _ = get_initial_areal_capacity(df, disc_area_cm2)
        except:
            pass
        
        # Reversible Capacity (mAh/g)
        reversible_capacity = None
        if len(df) > formation_cycles:
            reversible_capacity = df['Q Dis (mAh/g)'].iloc[formation_cycles]
        
        # Coulombic Efficiency (post-formation, %)
        ceff_avg = None
        try:
            eff_col = 'Efficiency (-)'
            qdis_col = 'Q Dis (mAh/g)'
            n_cycles = len(df)
            ceff_values = []
            if eff_col in df.columns and qdis_col in df.columns and n_cycles > formation_cycles+1:
                # Use corrected efficiency calculation for anode projects
                if project_type == "Anode" and 'Q charge (mA.h)' in df.columns and 'Q discharge (mA.h)' in df.columns:
                    # Recalculate efficiency using corrected method for anode projects
                    from data_processing import calculate_efficiency_based_on_project_type
                    corrected_efficiency = calculate_efficiency_based_on_project_type(
                        df['Q charge (mA.h)'], 
                        df['Q discharge (mA.h)'], 
                        project_type
                    ) / 100  # Convert to decimal for consistency
                    
                    # Use corrected efficiency values for coulombic efficiency calculation
                    prev_qdis = df[qdis_col].iloc[formation_cycles]
                    prev_eff = corrected_efficiency.iloc[formation_cycles]
                    for i in range(formation_cycles+1, n_cycles):
                        curr_qdis = df[qdis_col].iloc[i]
                        curr_eff = corrected_efficiency.iloc[i]
                        try:
                            pq = float(prev_qdis)
                            cq = float(curr_qdis)
                            pe = float(prev_eff)
                            ce = float(curr_eff)
                            if pq > 0 and (cq < 0.95 * pq or ce < 0.95 * pe):
                                break
                            ceff_values.append(ce)
                            prev_qdis = cq
                            prev_eff = ce
                        except (ValueError, TypeError):
                            continue
                else:
                    # Use original efficiency calculation for non-anode projects
                    prev_qdis = df[qdis_col].iloc[formation_cycles]
                    prev_eff = df[eff_col].iloc[formation_cycles]
                    for i in range(formation_cycles+1, n_cycles):
                        curr_qdis = df[qdis_col].iloc[i]
                        curr_eff = df[eff_col].iloc[i]
                        try:
                            pq = float(prev_qdis)
                            cq = float(curr_qdis)
                            pe = float(prev_eff)
                            ce = float(curr_eff)
                            if pq > 0 and (cq < 0.95 * pq or ce < 0.95 * pe):
                                break
                            ceff_values.append(ce)
                            prev_qdis = cq
                            prev_eff = ce
                        except (ValueError, TypeError):
                            continue
            if ceff_values:
                ceff_avg = sum(ceff_values) / len(ceff_values) * 100
        except:
            pass
        
        return {
            'cell_name': cell_name,
            'loading': loading,
            'active_material': active_material,
            'formation_cycles': formation_cycles,
            'first_discharge': max_qdis,
            'first_efficiency': eff_pct,
            'cycle_life_80': cycle_life_80,
            'areal_capacity': areal_capacity,
            'reversible_capacity': reversible_capacity,
            'coulombic_efficiency': ceff_avg,
            'porosity': cell_data.get('porosity', None)
        }
    except Exception as e:
        # Return basic info if calculation fails
        return {
            'cell_name': cell_data.get('test_number') or cell_data.get('cell_name', 'Unknown'),
            'loading': cell_data.get('loading', 0),
            'active_material': cell_data.get('active_material', 0),
            'formation_cycles': cell_data.get('formation_cycles', 4),
            'first_discharge': None,
            'first_efficiency': None,
            'cycle_life_80': None,
            'areal_capacity': None,
            'reversible_capacity': None,
            'coulombic_efficiency': None,
            'porosity': None
        }

def calculate_experiment_average(experiment_cells, exp_name, exp_date):
    """Calculate average values for an experiment."""
    if not experiment_cells:
        return None
    
    # Calculate averages for numeric fields
    numeric_fields = ['first_discharge', 'first_efficiency', 'cycle_life_80', 'areal_capacity', 'reversible_capacity', 'coulombic_efficiency', 'porosity']
    averages = {}
    
    for field in numeric_fields:
        values = [cell[field] for cell in experiment_cells if cell[field] is not None]
        averages[field] = sum(values) / len(values) if values else None
    
    # Calculate average active material percentage
    active_material_values = [cell['active_material'] for cell in experiment_cells if cell['active_material'] is not None]
    avg_active_material = sum(active_material_values) / len(active_material_values) if active_material_values else None
    
    return {
        'cell_name': f"{exp_name} (Avg)",
        'experiment_name': exp_name,
        'experiment_date': exp_date,
        'cell_count': len(experiment_cells),
        'loading': sum(cell['loading'] for cell in experiment_cells) / len(experiment_cells),
        'active_material': avg_active_material,  # Use calculated average
        'formation_cycles': int(sum(cell['formation_cycles'] for cell in experiment_cells) / len(experiment_cells)),
        **averages
    }

def calculate_cycle_life_80(qdis_series, cycle_index_series):
    """Calculate cycle life at 80% capacity retention."""
    # Use max of cycles 3 and 4 as initial, or last available if <4 cycles
    if len(qdis_series) >= 4:
        initial_qdis = max(qdis_series.iloc[2], qdis_series.iloc[3])
    elif len(qdis_series) > 0:
        initial_qdis = qdis_series.iloc[-1]
    else:
        return None
    threshold = 0.8 * initial_qdis
    below_threshold = qdis_series <= threshold
    if below_threshold.any():
        first_below_idx = below_threshold.idxmin()
        return int(cycle_index_series.iloc[first_below_idx])
    else:
        return int(cycle_index_series.iloc[-1])

def get_qdis_series(df_cell):
    """Extract discharge capacity series from cell data."""
    qdis_raw = df_cell['Q Dis (mAh/g)']
    if pd.api.types.is_scalar(qdis_raw):
        return pd.Series([qdis_raw]).dropna()
    else:
        return pd.Series(qdis_raw).dropna()
