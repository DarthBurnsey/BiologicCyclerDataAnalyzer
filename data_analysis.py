import pandas as pd
import numpy as np


def _calculate_post_formation_ce(df, formation_cycles, project_type="Full Cell"):
    """Average valid post-formation CE values without stopping on capacity fade."""
    n_cycles = len(df)
    if n_cycles == 0:
        return None

    start_idx = formation_cycles if n_cycles > formation_cycles else 0
    ceff_values = []

    try:
        if 'Q charge (mA.h)' in df.columns and 'Q discharge (mA.h)' in df.columns:
            from data_processing import calculate_efficiency_based_on_project_type
            corrected_efficiency = calculate_efficiency_based_on_project_type(
                pd.to_numeric(df['Q charge (mA.h)'], errors='coerce'),
                pd.to_numeric(df['Q discharge (mA.h)'], errors='coerce'),
                project_type
            ) / 100
            ceff_values = [
                float(val) * 100
                for val in corrected_efficiency.iloc[start_idx:n_cycles]
                if pd.notna(val) and float(val) > 0
            ]
        elif 'Efficiency (-)' in df.columns:
            eff_series = pd.to_numeric(df['Efficiency (-)'], errors='coerce')
            ceff_values = [
                float(val) * 100
                for val in eff_series.iloc[start_idx:n_cycles]
                if pd.notna(val) and float(val) > 0
            ]
    except Exception:
        return None

    return sum(ceff_values) / len(ceff_values) if ceff_values else None

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
        if 'Q charge (mA.h)' in df.columns and 'Q discharge (mA.h)' in df.columns:
            # Always use consistent efficiency calculation based on project type
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
        elif 'Efficiency (-)' in df.columns and not df['Efficiency (-)'].empty:
            # Fallback to DataFrame efficiency if charge/discharge data not available
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
            cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series, formation_cycles)
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
            ceff_avg = _calculate_post_formation_ce(df, formation_cycles, project_type)
        except:
            pass
        
        # Calculate N/P ratio if Full Cell data is available
        np_ratio = None
        if cell_data.get('anode_mass') and cell_data.get('cathode_mass'):
            np_ratio = calculate_np_ratio_from_formation(
                df,
                formation_cycles=formation_cycles,
                anode_mass=cell_data.get('anode_mass'),
                cathode_mass=cell_data.get('cathode_mass')
            )
        
        # Capacity Fade Rate (%/cycle and %/100 cycles)
        fade_rate_per_cycle = None
        fade_rate_per_100 = None
        try:
            fade_result = calculate_capacity_fade_rate(df, formation_cycles)
            if fade_result is not None:
                fade_rate_per_cycle = fade_result['fade_rate_per_cycle']
                fade_rate_per_100 = fade_result['fade_rate_per_100']
        except Exception:
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
            'porosity': cell_data.get('porosity', None),
            'np_ratio': np_ratio,
            'overhang_ratio': cell_data.get('overhang_ratio', None),
            'fade_rate_per_cycle': fade_rate_per_cycle,
            'fade_rate_per_100': fade_rate_per_100,
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
            'porosity': None,
            'np_ratio': None,
            'overhang_ratio': None,
            'fade_rate_per_cycle': None,
            'fade_rate_per_100': None,
        }

def calculate_experiment_average(experiment_cells, exp_name, exp_date):
    """Calculate average values for an experiment."""
    if not experiment_cells:
        return None
    
    # Calculate averages for numeric fields
    numeric_fields = ['first_discharge', 'first_efficiency', 'cycle_life_80', 'areal_capacity', 'reversible_capacity', 'coulombic_efficiency', 'porosity', 'fade_rate_per_cycle', 'fade_rate_per_100']
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

def calculate_cycle_life_80(qdis_series, cycle_index_series, formation_cycles=4):
    """Calculate cycle life at 80% capacity retention."""
    # Use max of cycles 3 and 4 as initial, or last available if <4 cycles
    if len(qdis_series) >= 4:
        initial_qdis = max(qdis_series.iloc[2], qdis_series.iloc[3])
        # Determine the reference cycle index (0-based)
        reference_cycle_idx = 3 if qdis_series.iloc[3] >= qdis_series.iloc[2] else 2
    elif len(qdis_series) > 0:
        initial_qdis = qdis_series.iloc[-1]
        reference_cycle_idx = len(qdis_series) - 1
    else:
        return None
    
    threshold = 0.8 * initial_qdis
    
    # Only check for degradation AFTER the reference cycle (formation period)
    # Start checking from the cycle after our reference cycle
    start_checking_idx = max(reference_cycle_idx + 1, formation_cycles)
    
    if start_checking_idx >= len(qdis_series):
        # Not enough post-formation data
        return int(cycle_index_series.iloc[-1])
    
    # Get the subset of data after formation cycles
    post_formation_qdis = qdis_series.iloc[start_checking_idx:]
    post_formation_cycles = cycle_index_series.iloc[start_checking_idx:]
    
    # Check for capacity below threshold in post-formation data
    below_threshold = post_formation_qdis <= threshold
    if below_threshold.any():
        # Find the first cycle where capacity drops below threshold
        first_below_indices = below_threshold[below_threshold].index
        if len(first_below_indices) > 0:
            first_below_idx = first_below_indices[0]
            # Get the corresponding cycle number
            cycle_position = qdis_series.index.get_loc(first_below_idx)
            return int(cycle_index_series.iloc[cycle_position])
    
    # If capacity never drops below 80% after formation, return the last cycle number
    return int(cycle_index_series.iloc[-1])

def calculate_capacity_fade_rate(df, formation_cycles=4, min_linear_cycles=10):
    """
    Calculate the capacity fade rate from the linear degradation region
    after formation but before the rapid 'death valley' collapse.

    Returns a dict with fade_rate_per_cycle (%/cyc), fade_rate_per_100
    (%/100 cyc), and r_squared, or None if a reliable fit cannot be made.
    """
    try:
        qdis = df['Q Dis (mAh/g)'].values.astype(float)
        cycles = df[df.columns[0]].values.astype(float)

        if len(qdis) <= formation_cycles + min_linear_cycles:
            return None

        post_cap = qdis[formation_cycles:]
        post_cycles = cycles[formation_cycles:]

        initial_cap = post_cap[0]
        if initial_cap <= 0 or np.isnan(initial_cap):
            return None

        cap_pct = (post_cap / initial_cap) * 100.0

        # --- Detect death-valley onset via rolling-slope analysis ---
        changes = np.diff(cap_pct)
        window = min(20, max(5, len(changes) // 3))

        if len(changes) >= window:
            rolling_med = pd.Series(changes).rolling(window, center=True).median().values
            overall_median = np.nanmedian(changes)

            if overall_median < 0:
                threshold = 3.0 * abs(overall_median)
            else:
                threshold = 1.0

            death_valley_indices = np.where(rolling_med < -threshold)[0]

            if len(death_valley_indices) > 0:
                end_idx = int(death_valley_indices[0])
            else:
                end_idx = len(cap_pct)
        else:
            end_idx = len(cap_pct)

        linear_cap = cap_pct[:end_idx]
        linear_cycles = post_cycles[:end_idx]

        if len(linear_cap) < min_linear_cycles:
            return None

        # --- Linear regression on the identified region ---
        slope, intercept = np.polyfit(linear_cycles, linear_cap, 1)

        predicted = slope * linear_cycles + intercept
        ss_res = np.sum((linear_cap - predicted) ** 2)
        ss_tot = np.sum((linear_cap - np.mean(linear_cap)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        if r_squared < 0.7:
            return None

        fade_per_cycle = abs(slope)
        fade_per_100 = fade_per_cycle * 100.0

        return {
            'fade_rate_per_cycle': round(fade_per_cycle, 4),
            'fade_rate_per_100': round(fade_per_100, 2),
            'r_squared': round(r_squared, 4),
        }
    except Exception:
        return None


def get_qdis_series(df_cell):
    """Extract discharge capacity series from cell data."""
    qdis_raw = df_cell['Q Dis (mAh/g)']
    if pd.api.types.is_scalar(qdis_raw):
        return pd.Series([qdis_raw]).dropna()
    else:
        return pd.Series(qdis_raw).dropna()


def calculate_np_ratio_from_formation(df, formation_cycles=4, anode_mass=None, cathode_mass=None):
    """
    Calculate N/P ratio from formation cycle capacities.
    
    N/P Ratio = (Anode Capacity) / (Cathode Capacity)
    
    For Full Cells:
    - Anode Capacity = Discharge capacity of first formation cycle * anode mass
    - Cathode Capacity = Charge capacity of first formation cycle * cathode mass
    
    Args:
        df: DataFrame with cycling data
        formation_cycles: Number of formation cycles (default 4)
        anode_mass: Mass of anode active material (mg), if available
        cathode_mass: Mass of cathode active material (mg), if available
    
    Returns:
        float: N/P ratio, or None if calculation fails
    """
    try:
        if len(df) < 1:
            return None
        
        # Get first formation cycle data (typically cycle 1 or 2)
        # Use the cycle with highest discharge capacity in first few cycles
        formation_data = df.head(min(formation_cycles, len(df)))
        
        # Find cycle with max discharge capacity (represents full formation)
        max_discharge_idx = formation_data['Q Dis (mAh/g)'].idxmax()
        formation_cycle = df.loc[max_discharge_idx]
        
        # Get discharge and charge capacities for this cycle
        discharge_capacity = pd.to_numeric(formation_cycle['Q Dis (mAh/g)'], errors='coerce')
        charge_capacity = pd.to_numeric(formation_cycle['Q Chg (mAh/g)'], errors='coerce')
        
        if pd.isna(discharge_capacity) or pd.isna(charge_capacity):
            return None
        
        if discharge_capacity <= 0 or charge_capacity <= 0:
            return None
        
        # Calculate N/P ratio
        # For Full Cell: N/P = Anode Capacity / Cathode Capacity
        # Assuming anode is lithiated during discharge and cathode during charge
        # N/P = (Discharge capacity * anode utilization) / (Charge capacity * cathode utilization)
        
        # Simplified calculation: Use ratio of discharge to charge capacities
        # This gives an approximate N/P ratio
        np_ratio = discharge_capacity / charge_capacity
        
        # If electrode masses are provided, calculate more accurate N/P ratio
        if anode_mass and cathode_mass and anode_mass > 0 and cathode_mass > 0:
            # More accurate: N/P = (anode_mass * specific_capacity_anode) / (cathode_mass * specific_capacity_cathode)
            # Using measured formation capacities as proxy for specific capacities
            anode_capacity_total = discharge_capacity * anode_mass  # mAh
            cathode_capacity_total = charge_capacity * cathode_mass  # mAh
            np_ratio = anode_capacity_total / cathode_capacity_total
        
        return float(np_ratio)
    
    except Exception as e:
        return None


def validate_np_ratio(np_ratio):
    """
    Validate N/P ratio and return warning level.
    
    Args:
        np_ratio: N/P ratio value
    
    Returns:
        tuple: (warning_level, message)
            warning_level: 'critical', 'warning', 'safe', or None
            message: Warning message string
    """
    if np_ratio is None:
        return (None, "N/P ratio not available")
    
    if np_ratio < 1.0:
        return ('critical', f"🚨 CRITICAL: N/P ratio {np_ratio:.3f} < 1.0 - High lithium plating risk!")
    elif np_ratio < 1.05:
        return ('warning', f"⚠️ WARNING: N/P ratio {np_ratio:.3f} < 1.05 - Low safety margin")
    elif np_ratio < 1.10:
        return ('safe', f"✅ N/P ratio {np_ratio:.3f} is acceptable (1.05-1.10 range)")
    else:
        return ('safe', f"✅ N/P ratio {np_ratio:.3f} is in safe range (>1.10)")
