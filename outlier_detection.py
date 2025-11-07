"""
Outlier detection module for battery cell data analysis.

This module provides functionality to detect and filter outlier data points
in battery cell performance metrics using reasonable bounds and statistical methods.
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional

# Define reasonable bounds for battery cell metrics
BATTERY_DATA_BOUNDS = {
    'first_discharge': {
        'description': '1st Cycle Discharge Capacity (mAh/g)',
        'min_value': 50,      # Very low discharge capacity
        'max_value': 400,     # Exceptionally high discharge capacity
        'typical_min': 100,   # Typical minimum for good cells
        'typical_max': 300,   # Typical maximum for good cells
        'unit': 'mAh/g'
    },
    'first_efficiency': {
        'description': 'First Cycle Efficiency (%)',
        'min_value': 30,      # Very poor first cycle efficiency
        'max_value': 100,     # Perfect efficiency (theoretical max)
        'typical_min': 70,    # Typical minimum for decent cells
        'typical_max': 95,    # Typical maximum for good cells
        'unit': '%'
    },
    'reversible_capacity': {
        'description': 'Reversible Capacity (mAh/g)',
        'min_value': 50,      # Very low reversible capacity
        'max_value': 350,     # Exceptionally high reversible capacity
        'typical_min': 100,   # Typical minimum for good cells
        'typical_max': 280,   # Typical maximum for good cells
        'unit': 'mAh/g'
    },
    'coulombic_efficiency': {
        'description': 'Coulombic Efficiency (%)',
        'min_value': 85,      # Poor coulombic efficiency
        'max_value': 100,     # Perfect efficiency (theoretical max)
        'typical_min': 95,    # Typical minimum for decent cells
        'typical_max': 99.8,  # Typical maximum for excellent cells
        'unit': '%'
    },
    'areal_capacity': {
        'description': 'Areal Capacity (mAh/cm²)',
        'min_value': 0.1,     # Very low areal capacity
        'max_value': 10,      # Very high areal capacity
        'typical_min': 0.5,   # Typical minimum
        'typical_max': 5,     # Typical maximum
        'unit': 'mAh/cm²'
    },
    'cycle_life_80': {
        'description': 'Cycle Life (80% retention)',
        'min_value': 10,      # Very poor cycle life
        'max_value': 5000,    # Exceptional cycle life
        'typical_min': 100,   # Typical minimum for decent cells
        'typical_max': 2000,  # Typical maximum for good cells
        'unit': 'cycles'
    }
}

def detect_outliers_hard_bounds(cell: Dict[str, Any], field: str) -> Tuple[bool, str]:
    """
    Detect if a cell's value for a specific field is an outlier based on hard bounds.
    
    Args:
        cell: Dictionary containing cell data
        field: Field name to check for outliers
        
    Returns:
        Tuple of (is_outlier: bool, reason: str)
    """
    if field not in BATTERY_DATA_BOUNDS:
        return False, "Field not in bounds definition"
    
    value = cell.get(field)
    if value is None:
        return False, "No value for field"
    
    bounds = BATTERY_DATA_BOUNDS[field]
    
    # Check against hard bounds
    if value < bounds['min_value']:
        return True, f"Below minimum ({bounds['min_value']} {bounds['unit']})"
    elif value > bounds['max_value']:
        return True, f"Above maximum ({bounds['max_value']} {bounds['unit']})"
    
    return False, "Within acceptable range"

def detect_outliers_statistical(cells: List[Dict[str, Any]], field: str, 
                               method: str = 'iqr', threshold: float = 1.5) -> List[Dict[str, Any]]:
    """
    Detect outliers using statistical methods.
    
    Args:
        cells: List of cell dictionaries
        field: Field name to analyze
        method: 'iqr' for interquartile range, 'zscore' for z-score
        threshold: Threshold for outlier detection
        
    Returns:
        List of outlier dictionaries with details
    """
    # Extract valid values for the field
    valid_data = []
    for cell in cells:
        value = cell.get(field)
        if value is not None and not np.isnan(value):
            valid_data.append({
                'cell': cell,
                'value': value,
                'cell_name': cell.get('cell_name', 'Unknown'),
                'experiment_name': cell.get('experiment_name', 'Unknown')
            })
    
    if len(valid_data) < 4:  # Need at least 4 points for statistical analysis
        return []
    
    values = [d['value'] for d in valid_data]
    outliers = []
    
    if method == 'iqr':
        # Interquartile Range method
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        lower_bound = q1 - threshold * iqr
        upper_bound = q3 + threshold * iqr
        
        for data in valid_data:
            if data['value'] < lower_bound or data['value'] > upper_bound:
                reason = f"Statistical outlier (IQR method, threshold={threshold})"
                outliers.append({
                    'cell_name': data['cell_name'],
                    'experiment_name': data['experiment_name'],
                    'value': data['value'],
                    'outlier_reasons': [reason],
                    'bounds': f"[{lower_bound:.2f}, {upper_bound:.2f}]"
                })
    
    elif method == 'zscore':
        # Z-score method
        mean_val = np.mean(values)
        std_val = np.std(values)
        if std_val > 0:
            for data in valid_data:
                zscore = abs((data['value'] - mean_val) / std_val)
                if zscore > threshold:
                    reason = f"Statistical outlier (Z-score={zscore:.2f}, threshold={threshold})"
                    outliers.append({
                        'cell_name': data['cell_name'],
                        'experiment_name': data['experiment_name'],
                        'value': data['value'],
                        'outlier_reasons': [reason],
                        'zscore': zscore
                    })
    
    return outliers

def get_outlier_detection_ui_settings(individual_cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create UI controls for outlier detection settings.
    
    Args:
        individual_cells: List of individual cell data
        
    Returns:
        Dictionary containing outlier detection settings
    """
    st.markdown("##### 🔧 Outlier Detection Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        enable_hard_bounds = st.checkbox(
            "Enable Hard Bounds Filtering", 
            value=True,
            help="Remove cells with values outside reasonable physical limits"
        )
        
        enable_statistical = st.checkbox(
            "Enable Statistical Filtering", 
            value=False,
            help="Remove statistical outliers based on the dataset distribution"
        )
    
    with col2:
        if enable_statistical:
            stat_method = st.selectbox(
                "Statistical Method",
                options=['iqr', 'zscore'],
                index=0,
                help="IQR: Interquartile Range, Z-score: Standard deviation based"
            )
            
            if stat_method == 'iqr':
                stat_threshold = st.slider(
                    "IQR Threshold", 
                    min_value=1.0, 
                    max_value=3.0, 
                    value=1.5, 
                    step=0.1,
                    help="Higher values = less aggressive filtering"
                )
            else:
                stat_threshold = st.slider(
                    "Z-Score Threshold", 
                    min_value=1.0, 
                    max_value=4.0, 
                    value=2.0, 
                    step=0.1,
                    help="Higher values = less aggressive filtering"
                )
        else:
            stat_method = 'iqr'
            stat_threshold = 1.5
    
    # Manual exclusion interface
    st.markdown("##### 📝 Manual Cell Exclusion")
    available_cells = [f"{cell.get('cell_name', 'Unknown')} ({cell.get('experiment_name', 'Unknown')})" 
                      for cell in individual_cells]
    
    manual_exclusions = st.multiselect(
        "Select cells to exclude from analysis",
        options=available_cells,
        default=[],
        help="Manually exclude specific cells from the analysis"
    )
    
    # Extract just the cell names for processing
    manual_exclusion_names = []
    for exclusion in manual_exclusions:
        # Extract cell name from "Cell Name (Experiment Name)" format
        if " (" in exclusion:
            cell_name = exclusion.split(" (")[0]
            manual_exclusion_names.append(cell_name)
    
    return {
        'enable_hard_bounds': enable_hard_bounds,
        'enable_statistical': enable_statistical,
        'statistical_method': stat_method,
        'statistical_threshold': stat_threshold,
        'manual_exclusions': manual_exclusion_names
    }

def filter_outliers(individual_cells: List[Dict[str, Any]], 
                   outlier_settings: Dict[str, Any],
                   manual_exclusion_names: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """
    Filter outliers from individual cell data based on settings.
    
    Args:
        individual_cells: List of individual cell data dictionaries
        outlier_settings: Settings from get_outlier_detection_ui_settings
        manual_exclusion_names: List of cell names to manually exclude
        
    Returns:
        Tuple of (filtered_cells, outlier_summary)
    """
    filtered_cells = []
    outlier_summary = {}
    
    # Fields to check for outliers
    fields_to_check = ['first_discharge', 'first_efficiency', 'reversible_capacity', 
                      'coulombic_efficiency', 'areal_capacity', 'cycle_life_80']
    
    for cell in individual_cells:
        cell_name = cell.get('cell_name', 'Unknown')
        
        # Check manual exclusions first
        if cell_name in manual_exclusion_names:
            continue
        
        # Track if this cell should be excluded
        exclude_cell = False
        cell_outlier_reasons = []
        
        # Check each field for outliers
        for field in fields_to_check:
            field_outliers = []
            
            # Hard bounds check
            if outlier_settings.get('enable_hard_bounds', True):
                is_outlier, reason = detect_outliers_hard_bounds(cell, field)
                if is_outlier:
                    field_outliers.append({
                        'cell_name': cell_name,
                        'experiment_name': cell.get('experiment_name', 'Unknown'),
                        'value': cell.get(field, 'N/A'),
                        'outlier_reasons': [f"Hard bounds: {reason}"],
                        'field': field
                    })
            
            # Statistical outlier check (if enabled)
            if outlier_settings.get('enable_statistical', False):
                stat_outliers = detect_outliers_statistical(
                    individual_cells, 
                    field,
                    method=outlier_settings.get('statistical_method', 'iqr'),
                    threshold=outlier_settings.get('statistical_threshold', 1.5)
                )
                
                # Check if current cell is in statistical outliers
                for outlier in stat_outliers:
                    if outlier['cell_name'] == cell_name:
                        field_outliers.append(outlier)
            
            # Add to summary if outliers found for this field
            if field_outliers:
                if field not in outlier_summary:
                    outlier_summary[field] = []
                outlier_summary[field].extend(field_outliers)
                
                # Mark cell for exclusion if it has outliers in critical fields
                critical_fields = ['first_discharge', 'reversible_capacity', 'cycle_life_80']
                if field in critical_fields:
                    exclude_cell = True
                    cell_outlier_reasons.extend([f"{field}: {outlier['outlier_reasons'][0]}" for outlier in field_outliers])
        
        # Only include cell if it's not excluded
        if not exclude_cell:
            filtered_cells.append(cell)
    
    return filtered_cells, outlier_summary





