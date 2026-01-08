"""
Formulation Analysis Module
Provides functions for analyzing and comparing battery cell formulations.
"""
import json
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from io import StringIO

def extract_formulation_component(formulation_json: str, component_name: str) -> Optional[float]:
    """
    Extract the percentage of a specific component from a formulation.
    
    Args:
        formulation_json: JSON string of the formulation
        component_name: Name of the component to extract
    
    Returns:
        Percentage value or None if not found
    """
    if not formulation_json:
        return None
    
    try:
        formulation = json.loads(formulation_json)
        if isinstance(formulation, list):
            for item in formulation:
                if isinstance(item, dict):
                    component = (item.get('Component') or 
                               item.get('component') or 
                               item.get('Component Name') or '')
                    if component.strip().lower() == component_name.strip().lower():
                        percentage = (item.get('Dry Mass Fraction (%)') or
                                    item.get('dry_mass_fraction') or
                                    item.get('Value') or None)
                        if percentage is not None:
                            try:
                                return float(percentage)
                            except (ValueError, TypeError):
                                return None
    except (json.JSONDecodeError, TypeError):
        pass
    
    return None

def extract_all_formulation_components(formulation_json: str) -> Dict[str, float]:
    """
    Extract all components and their percentages from a formulation.
    
    Returns:
        Dictionary with component names as keys and percentages as values
    """
    components = {}
    
    if not formulation_json:
        return components
    
    try:
        formulation = json.loads(formulation_json)
        if isinstance(formulation, list):
            for item in formulation:
                if isinstance(item, dict):
                    component = (item.get('Component') or 
                               item.get('component') or 
                               item.get('Component Name') or '')
                    if component:
                        percentage = (item.get('Dry Mass Fraction (%)') or
                                    item.get('dry_mass_fraction') or
                                    item.get('Value') or None)
                        if percentage is not None:
                            try:
                                components[component] = float(percentage)
                            except (ValueError, TypeError):
                                continue
    except (json.JSONDecodeError, TypeError):
        pass
    
    return components

def get_formulation_from_experiment(experiment_data: Tuple) -> Optional[str]:
    """
    Extract formulation JSON from experiment data tuple.
    
    Args:
        experiment_data: Tuple from database query (get_experiment_by_id or similar)
    
    Returns:
        Formulation JSON string or None
    """
    # Based on get_experiment_by_id structure:
    # (id, project_id, cell_name, file_name, loading, active_material, 
    #  formation_cycles, test_number, electrolyte, substrate, separator, 
    #  formulation_json, data_json, ...)
    if len(experiment_data) > 11:
        return experiment_data[11]  # formulation_json
    return None

def get_formulation_from_cell_data(cell_data: Dict) -> Optional[str]:
    """
    Extract formulation from cell data dictionary.
    
    Args:
        cell_data: Cell data dictionary from experiment data_json
    
    Returns:
        Formulation JSON string or None
    """
    formulation = cell_data.get('formulation', [])
    if formulation:
        return json.dumps(formulation)
    return None

def compare_formulations(formulation1_json: str, formulation2_json: str) -> Dict[str, Any]:
    """
    Compare two formulations and return differences.
    
    Returns:
        Dictionary with comparison results including:
        - common_components: Components present in both
        - unique_to_1: Components only in formulation 1
        - unique_to_2: Components only in formulation 2
        - differences: Percentage differences for common components
    """
    comp1 = extract_all_formulation_components(formulation1_json)
    comp2 = extract_all_formulation_components(formulation2_json)
    
    common = set(comp1.keys()) & set(comp2.keys())
    unique1 = set(comp1.keys()) - set(comp2.keys())
    unique2 = set(comp2.keys()) - set(comp1.keys())
    
    differences = {}
    for component in common:
        diff = comp1[component] - comp2[component]
        differences[component] = {
            'formulation1': comp1[component],
            'formulation2': comp2[component],
            'difference': diff,
            'percent_change': (diff / comp2[component] * 100) if comp2[component] != 0 else 0
        }
    
    return {
        'common_components': list(common),
        'unique_to_1': list(unique1),
        'unique_to_2': list(unique2),
        'differences': differences
    }

def extract_formulation_component_from_experiment(exp: Tuple, component_name: str) -> Optional[float]:
    """
    Extract component percentage from an experiment tuple, checking both formulation_json and data_json.
    
    Args:
        exp: Experiment data tuple from database
        component_name: Name of the component to extract
    
    Returns:
        Percentage value or None if not found
    """
    formulation_json = exp[11] if len(exp) > 11 else None
    data_json = exp[12] if len(exp) > 12 else None
    
    # First check formulation_json
    component_pct = extract_formulation_component(formulation_json, component_name)
    if component_pct is not None:
        return component_pct
    
    # If not found, check data_json for multi-cell experiments
    if data_json:
        try:
            data = json.loads(data_json)
            if 'cells' in data:
                for cell in data['cells']:
                    formulation = cell.get('formulation', [])
                    if isinstance(formulation, list):
                        for item in formulation:
                            if isinstance(item, dict):
                                component = (item.get('Component') or 
                                           item.get('component') or 
                                           item.get('Component Name') or '')
                                if component.strip().lower() == component_name.strip().lower():
                                    percentage = (item.get('Dry Mass Fraction (%)') or
                                                item.get('dry_mass_fraction') or
                                                item.get('Value') or None)
                                    if percentage is not None:
                                        try:
                                            return float(percentage)
                                        except (ValueError, TypeError):
                                            continue
        except (json.JSONDecodeError, TypeError):
            pass
    
    return None

def create_formulation_comparison_dataframe(experiments_data: List[Tuple], component_name: str) -> pd.DataFrame:
    """
    Create a DataFrame comparing experiments by a specific formulation component.
    
    Args:
        experiments_data: List of experiment data tuples
        component_name: Component to compare (e.g., "Graphite")
    
    Returns:
        DataFrame with experiment names, component percentages, and performance metrics
    """
    rows = []
    
    for exp in experiments_data:
        exp_id, project_id, cell_name, file_name, loading, active_material, \
        formation_cycles, test_number, electrolyte, substrate, separator, \
        formulation_json, data_json, solids_content, pressed_thickness, \
        experiment_notes, created_date, porosity = exp
        
        component_pct = extract_formulation_component_from_experiment(exp, component_name)
        
        if component_pct is not None:
            # Try to extract performance metrics from data_json
            reversible_capacity = None
            cycle_life = None
            first_discharge = None
            first_efficiency = None
            coulombic_efficiency = None
            
            # Initialize loading and active_material from top-level (fallback)
            extracted_loading = loading
            extracted_active_material = active_material
            
            if data_json:
                try:
                    parsed_data = json.loads(data_json)
                    formation_cycles = formation_cycles or 4
                    
                    if 'cells' in parsed_data:
                        # Multi-cell experiment - calculate average
                        cells = parsed_data['cells']
                        capacities = []
                        first_discharges = []
                        first_efficiencies = []
                        cycle_lives = []
                        loadings = []
                        active_materials = []
                        
                        for cell in cells:
                            if cell.get('excluded', False):
                                continue
                            
                            # Extract loading and active_material from cell data
                            cell_loading = cell.get('loading')
                            cell_active_material = cell.get('active_material')
                            if cell_loading is not None:
                                loadings.append(cell_loading)
                            if cell_active_material is not None:
                                active_materials.append(cell_active_material)
                            
                            if 'data_json' in cell:
                                try:
                                    df = pd.read_json(StringIO(cell['data_json']))
                                    
                                    # Get first discharge capacity (max of first 3 cycles)
                                    if 'Q Dis (mAh/g)' in df.columns:
                                        first_three = df['Q Dis (mAh/g)'].head(3).tolist()
                                        if first_three:
                                            first_discharges.append(max(first_three))
                                        
                                        # Get first post-formation cycle (reversible capacity)
                                        if len(df) > formation_cycles:
                                            capacities.append(df['Q Dis (mAh/g)'].iloc[formation_cycles])
                                    
                                    # Get first cycle efficiency
                                    if 'Efficiency (-)' in df.columns and len(df) > 0:
                                        first_eff = df['Efficiency (-)'].iloc[0]
                                        if first_eff is not None:
                                            try:
                                                first_efficiencies.append(float(first_eff) * 100)
                                            except (ValueError, TypeError):
                                                pass
                                    
                                    # Calculate cycle life (80% threshold)
                                    if 'Q Dis (mAh/g)' in df.columns and len(df) > formation_cycles:
                                        post_formation = df.iloc[formation_cycles:]
                                        if not post_formation.empty:
                                            initial_capacity = post_formation['Q Dis (mAh/g)'].iloc[0]
                                            if initial_capacity > 0:
                                                threshold = 0.8 * initial_capacity
                                                below_threshold = post_formation[post_formation['Q Dis (mAh/g)'] < threshold]
                                                if not below_threshold.empty:
                                                    cycle_life = int(post_formation.index[below_threshold.index[0]])
                                                    cycle_lives.append(cycle_life)
                                except Exception:
                                    pass
                        
                        if capacities:
                            reversible_capacity = np.mean(capacities)
                        if first_discharges:
                            first_discharge = np.mean(first_discharges)
                        if first_efficiencies:
                            first_efficiency = np.mean(first_efficiencies)
                        if cycle_lives:
                            cycle_life = np.mean(cycle_lives)
                        
                        # Use average loading and active_material from cells if available
                        if loadings:
                            extracted_loading = np.mean(loadings)
                        if active_materials:
                            extracted_active_material = np.mean(active_materials)
                    else:
                        # Legacy single cell experiment
                        try:
                            df = pd.read_json(StringIO(data_json))
                            formation_cycles = formation_cycles or 4
                            
                            if 'Q Dis (mAh/g)' in df.columns:
                                # First discharge (max of first 3)
                                first_three = df['Q Dis (mAh/g)'].head(3).tolist()
                                if first_three:
                                    first_discharge = max(first_three)
                                
                                # Reversible capacity
                                if len(df) > formation_cycles:
                                    reversible_capacity = df['Q Dis (mAh/g)'].iloc[formation_cycles]
                            
                            # First cycle efficiency
                            if 'Efficiency (-)' in df.columns and len(df) > 0:
                                first_eff = df['Efficiency (-)'].iloc[0]
                                if first_eff is not None:
                                    try:
                                        first_efficiency = float(first_eff) * 100
                                    except (ValueError, TypeError):
                                        pass
                            
                            # Cycle life
                            if 'Q Dis (mAh/g)' in df.columns and len(df) > formation_cycles:
                                post_formation = df.iloc[formation_cycles:]
                                if not post_formation.empty:
                                    initial_capacity = post_formation['Q Dis (mAh/g)'].iloc[0]
                                    if initial_capacity > 0:
                                        threshold = 0.8 * initial_capacity
                                        below_threshold = post_formation[post_formation['Q Dis (mAh/g)'] < threshold]
                                        if not below_threshold.empty:
                                            cycle_life = int(post_formation.index[below_threshold.index[0]])
                        except Exception:
                            pass
                except Exception:
                    pass
            
            rows.append({
                'Experiment': cell_name,
                'Component %': component_pct,
                'Reversible Capacity (mAh/g)': reversible_capacity,
                'Cycle Life': cycle_life,
                'First Discharge (mAh/g)': first_discharge,
                'First Efficiency (%)': first_efficiency,
                'Loading (mg)': extracted_loading,
                'Active Material (%)': extracted_active_material,
                'Porosity (%)': porosity * 100 if porosity else None,
                'Date': created_date
            })
    
    if rows:
        return pd.DataFrame(rows).sort_values('Component %')
    return pd.DataFrame()

def group_experiments_by_formulation_range(experiments_data: List[Tuple], 
                                          component_name: str, 
                                          range_size: float = 5.0) -> Dict[str, List[Tuple]]:
    """
    Group experiments by formulation component percentage ranges.
    
    Args:
        experiments_data: List of experiment data tuples
        component_name: Component to group by
        range_size: Size of each range (default 5%)
    
    Returns:
        Dictionary with range labels as keys and lists of experiments as values
    """
    grouped = {}
    
    for exp in experiments_data:
        component_pct = extract_formulation_component_from_experiment(exp, component_name)
        
        if component_pct is not None:
            # Create range label (e.g., "85-90%")
            range_start = int((component_pct // range_size) * range_size)
            range_end = range_start + range_size
            range_label = f"{range_start:.0f}-{range_end:.0f}%"
            
            if range_label not in grouped:
                grouped[range_label] = []
            grouped[range_label].append(exp)
    
    return grouped

