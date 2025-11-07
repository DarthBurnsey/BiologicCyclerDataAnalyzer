# data_processing.py
import pandas as pd
from typing import List, Dict, Any
import io

def calculate_efficiency_based_on_project_type(charge_capacity, discharge_capacity, project_type="Full Cell"):
    """
    Calculate efficiency based on project type.
    
    Standard efficiency = (Discharge capacity) / (Charge capacity) * 100%
    For 'Anode' projects: Efficiency = 100 / (reported efficiency) as percentage
    
    Args:
        charge_capacity: Charge capacity values
        discharge_capacity: Discharge capacity values  
        project_type: Project type ('Cathode', 'Anode', 'Full Cell')
    
    Returns:
        Efficiency values as percentages
    """
    # Avoid division by zero
    valid_mask = (charge_capacity > 0) & (discharge_capacity > 0)
    efficiency = pd.Series(0.0, index=charge_capacity.index)
    
    if project_type == "Anode":
        # For anode projects, calculate standard efficiency first, then invert
        standard_efficiency = discharge_capacity / charge_capacity
        # Invert the efficiency: Efficiency = 100 / (reported efficiency)
        efficiency.loc[valid_mask] = 100 / standard_efficiency.loc[valid_mask]
    else:
        # Standard efficiency calculation for Cathode and Full Cell projects
        efficiency.loc[valid_mask] = (discharge_capacity.loc[valid_mask] / 
                                    charge_capacity.loc[valid_mask]) * 100
    
    return efficiency

def detect_file_type(file_obj) -> str:
    """Detect if the file is a Biologic CSV or Neware XLSX based on content."""
    # Reset file position
    file_obj.seek(0)
    
    # Read first few bytes to check for XLSX signature
    first_bytes = file_obj.read(4)
    file_obj.seek(0)
    
    # XLSX files start with PK\x03\x04 (ZIP format)
    if first_bytes == b'PK\x03\x04':
        return 'neware_xlsx'
    else:
        return 'biologic_csv'

def parse_biologic_csv(file_obj, dataset: Dict[str, Any], project_type: str = "Full Cell") -> pd.DataFrame:
    """Parse Biologic CSV file format."""
    try:
        # Try to detect the delimiter automatically by trying common delimiters
        file_obj.seek(0)
        first_line = file_obj.readline()
        file_obj.seek(0)
        
        # Determine delimiter based on which one appears more in the header
        if isinstance(first_line, bytes):
            first_line = first_line.decode('utf-8', errors='ignore')
        
        semicolon_count = first_line.count(';')
        comma_count = first_line.count(',')
        
        # Use the delimiter that appears more frequently
        delimiter = ';' if semicolon_count > comma_count else ','
        
        df = pd.read_csv(file_obj, delimiter=delimiter)
        
        # Check if required columns exist
        required_columns = ['Q charge (mA.h)', 'Q discharge (mA.h)']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            available_columns = df.columns.tolist()
            raise ValueError(f"Missing required columns: {missing_columns}. Available columns: {available_columns}")
        
        # Handle potential NaN values
        df['Q charge (mA.h)'] = df['Q charge (mA.h)'].fillna(0)
        df['Q discharge (mA.h)'] = df['Q discharge (mA.h)'].fillna(0)
        
        # Remove rows where both charge and discharge are zero (likely invalid data)
        valid_rows = (df['Q charge (mA.h)'] > 0) | (df['Q discharge (mA.h)'] > 0)
        df = df[valid_rows].reset_index(drop=True)
        
        if len(df) == 0:
            raise ValueError("No valid data found in the file after filtering")
        
        # Calculate gravimetric capacities
        active_mass = (dataset['loading'] / 1000) * (dataset['active'] / 100)
        if active_mass <= 0:
            raise ValueError("Active mass must be greater than 0. Check loading and active material values.")
        
        df['Q Chg (mAh/g)'] = df['Q charge (mA.h)'] / active_mass
        df['Q Dis (mAh/g)'] = df['Q discharge (mA.h)'] / active_mass
        df['Test Number'] = dataset['testnum']
        
        # Calculate efficiency based on project type (was missing for Biologic CSV!)
        df['Efficiency (-)'] = calculate_efficiency_based_on_project_type(
            df['Q charge (mA.h)'], 
            df['Q discharge (mA.h)'], 
            project_type
        ) / 100  # Convert back to decimal for consistency with existing code
        
        return df
        
    except Exception as e:
        raise ValueError(f"Error parsing Biologic CSV file: {str(e)}")

def parse_neware_xlsx(file_obj, dataset: Dict[str, Any], project_type: str = "Full Cell") -> pd.DataFrame:
    """Parse Neware XLSX file format from the 'cycle' sheet."""
    try:
        # Read the 'cycle' sheet from the XLSX file
        df = pd.read_excel(file_obj, sheet_name='cycle')
        
        # Clean column names (remove extra whitespace and newlines)
        df.columns = df.columns.str.strip().str.replace('\n', '')
        
        # Check if required columns exist
        required_columns = ['Chg. Cap.(mAh)', 'DChg. Cap.(mAh)']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            available_columns = df.columns.tolist()
            raise ValueError(f"Missing required columns: {missing_columns}. Available columns: {available_columns}")
        
        # Map Neware columns to expected format
        # Neware: 'Cycle Index', 'Chg. Cap.(mAh)', 'DChg. Cap.(mAh)'
        # Expected: 'Cycle', 'Q charge (mA.h)', 'Q discharge (mA.h)'
        
        # Create a new DataFrame with the expected column structure
        processed_df = pd.DataFrame()
        
        # Map cycle index
        if 'Cycle Index' in df.columns:
            processed_df['Cycle'] = df['Cycle Index']
        else:
            # If no cycle index, create one based on row number
            processed_df['Cycle'] = range(1, len(df) + 1)
        
        # Map charge capacity and handle potential NaN values
        processed_df['Q charge (mA.h)'] = df['Chg. Cap.(mAh)'].fillna(0)
        
        # Map discharge capacity and handle potential NaN values
        processed_df['Q discharge (mA.h)'] = df['DChg. Cap.(mAh)'].fillna(0)
        
        # Remove rows where both charge and discharge are zero (likely invalid data)
        valid_rows = (processed_df['Q charge (mA.h)'] > 0) | (processed_df['Q discharge (mA.h)'] > 0)
        processed_df = processed_df[valid_rows].reset_index(drop=True)
        
        if len(processed_df) == 0:
            raise ValueError("No valid data found in the file after filtering")
        
        # Calculate gravimetric capacities
        active_mass = (dataset['loading'] / 1000) * (dataset['active'] / 100)
        if active_mass <= 0:
            raise ValueError("Active mass must be greater than 0. Check loading and active material values.")
        
        processed_df['Q Chg (mAh/g)'] = processed_df['Q charge (mA.h)'] / active_mass
        processed_df['Q Dis (mAh/g)'] = processed_df['Q discharge (mA.h)'] / active_mass
        processed_df['Test Number'] = dataset['testnum']
        
        # Calculate efficiency based on project type
        processed_df['Efficiency (-)'] = calculate_efficiency_based_on_project_type(
            processed_df['Q charge (mA.h)'], 
            processed_df['Q discharge (mA.h)'], 
            project_type
        ) / 100  # Convert back to decimal for consistency with existing code
        
        return processed_df
        
    except Exception as e:
        raise ValueError(f"Error parsing Neware XLSX file: {str(e)}")

def load_and_preprocess_data(datasets: List[Dict[str, Any]], project_type: str = "Full Cell") -> List[Dict[str, Any]]:
    """
    Load CSVs or XLSX files, calculate columns, and return list of dicts for each cell.
    
    Args:
        datasets: List of dataset dictionaries with file objects and parameters
        project_type: Project type ('Cathode', 'Anode', 'Full Cell') for efficiency calculation
    """
    dfs = []
    for ds in datasets:
        file_obj = ds['file']
        
        # Reset file position before processing
        try:
            file_obj.seek(0)
        except (AttributeError, OSError):
            # Handle case where file object doesn't support seek or is closed
            pass
        
        file_type = detect_file_type(file_obj)
        
        # Reset file position again before parsing
        try:
            file_obj.seek(0)
        except (AttributeError, OSError):
            pass
        
        if file_type == 'biologic_csv':
            df = parse_biologic_csv(file_obj, ds, project_type)
        elif file_type == 'neware_xlsx':
            df = parse_neware_xlsx(file_obj, ds, project_type)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        # Add electrode data if available in session state
        pressed_thickness = None
        solids_content = None
        porosity = None
        
        # Try to get electrode data from session state (for new experiments)
        try:
            import streamlit as st
            pressed_thickness = st.session_state.get('pressed_thickness', None)
            solids_content = st.session_state.get('solids_content', None)
            
            # Calculate porosity if we have the required data
            if (pressed_thickness and pressed_thickness > 0 and 
                ds.get('formulation') and 
                st.session_state.get('current_disc_diameter_mm')):
                
                try:
                    from porosity_calculations import calculate_porosity_from_experiment_data
                    porosity_data = calculate_porosity_from_experiment_data(
                        disc_mass_mg=ds['loading'],
                        disc_diameter_mm=st.session_state.get('current_disc_diameter_mm', 15),
                        pressed_thickness_um=pressed_thickness,
                        formulation=ds['formulation']
                    )
                    porosity = porosity_data['porosity']
                except Exception as e:
                    print(f"Error calculating porosity for {ds['testnum']}: {e}")
                    porosity = None
        except ImportError:
            # streamlit not available (e.g., in testing)
            pass
        
        dfs.append({
            'df': df,
            'testnum': ds['testnum'],
            'loading': ds['loading'],
            'active': ds['active'],
            'file_type': file_type,
            'project_type': project_type,
            'pressed_thickness': pressed_thickness,
            'solids_content': solids_content,
            'porosity': porosity
        })
    return dfs

def calculate_summary_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate summary statistics for a single cell's dataframe."""
    return {}

def calculate_averages(dfs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate averages across all cells."""
    return {} 