# data_processing.py
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
import io
import re

def extract_cutoff_voltages_from_mti(file_obj) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract cutoff voltages from MTI XLSX file 'Ch info' tab.
    
    Returns:
        Tuple of (lower_voltage, upper_voltage) or (None, None) if not found
    """
    try:
        # Try to read 'Ch info' sheet
        ch_info_df = pd.read_excel(file_obj, sheet_name='Ch info')
        
        # Look for cutoff voltages in column C (index 2)
        # MTI files typically have protocol information in this column
        if len(ch_info_df.columns) < 3:
            return None, None
        
        # Get column C data
        column_c = ch_info_df.iloc[:, 2].astype(str)
        
        # Look for voltage patterns (e.g., "3.0V", "4.2V", "3.0-4.2V", etc.)
        lower_voltage = None
        upper_voltage = None
        
        for value in column_c:
            if pd.isna(value) or value == 'nan':
                continue
            
            # Try to find voltage patterns
            # Pattern 1: Range format like "3.0-4.2V" or "3.0 - 4.2 V"
            range_match = re.search(r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*V?', value, re.IGNORECASE)
            if range_match:
                try:
                    v1 = float(range_match.group(1))
                    v2 = float(range_match.group(2))
                    lower_voltage = min(v1, v2)
                    upper_voltage = max(v1, v2)
                    break
                except ValueError:
                    continue
            
            # Pattern 2: Individual voltages like "Lower: 3.0V" or "Upper: 4.2V"
            if 'lower' in value.lower() or 'min' in value.lower() or 'discharge' in value.lower():
                voltage_match = re.search(r'(\d+\.?\d*)\s*V?', value)
                if voltage_match and lower_voltage is None:
                    try:
                        lower_voltage = float(voltage_match.group(1))
                    except ValueError:
                        pass
            
            if 'upper' in value.lower() or 'max' in value.lower() or 'charge' in value.lower():
                voltage_match = re.search(r'(\d+\.?\d*)\s*V?', value)
                if voltage_match and upper_voltage is None:
                    try:
                        upper_voltage = float(voltage_match.group(1))
                    except ValueError:
                        pass
        
        # Validate voltages are in reasonable range (0.1V to 10V)
        if lower_voltage is not None and (lower_voltage < 0.1 or lower_voltage > 10):
            lower_voltage = None
        if upper_voltage is not None and (upper_voltage < 0.1 or upper_voltage > 10):
            upper_voltage = None
        
        return lower_voltage, upper_voltage
        
    except Exception as e:
        print(f"Warning: Could not extract cutoff voltages from MTI file: {e}")
        return None, None

def extract_cutoff_voltages_from_neware(file_obj) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract cutoff voltages from Neware XLSX file 'test' tab column G.
    
    Returns:
        Tuple of (lower_voltage, upper_voltage) or (None, None) if not found
    """
    try:
        # Try to read 'test' sheet
        test_df = pd.read_excel(file_obj, sheet_name='test')
        
        # Look for cutoff voltages in column G (index 6)
        if len(test_df.columns) < 7:
            return None, None
        
        # Get column G data
        column_g = test_df.iloc[:, 6].astype(str)
        
        # Look for voltage patterns
        lower_voltage = None
        upper_voltage = None
        
        for value in column_g:
            if pd.isna(value) or value == 'nan':
                continue
            
            # Try to find voltage patterns
            # Pattern 1: Range format like "3.0-4.2V" or "3.0 - 4.2 V"
            range_match = re.search(r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*V?', value, re.IGNORECASE)
            if range_match:
                try:
                    v1 = float(range_match.group(1))
                    v2 = float(range_match.group(2))
                    lower_voltage = min(v1, v2)
                    upper_voltage = max(v1, v2)
                    break
                except ValueError:
                    continue
            
            # Pattern 2: Look for "End Voltage" or "Cutoff" keywords
            if 'end' in value.lower() or 'cutoff' in value.lower() or 'limit' in value.lower():
                voltage_match = re.search(r'(\d+\.?\d*)\s*V?', value)
                if voltage_match:
                    try:
                        voltage = float(voltage_match.group(1))
                        # Determine if it's upper or lower based on magnitude
                        if voltage < 3.0 and lower_voltage is None:
                            lower_voltage = voltage
                        elif voltage > 3.0 and upper_voltage is None:
                            upper_voltage = voltage
                    except ValueError:
                        pass
        
        # Validate voltages are in reasonable range (0.1V to 10V)
        if lower_voltage is not None and (lower_voltage < 0.1 or lower_voltage > 10):
            lower_voltage = None
        if upper_voltage is not None and (upper_voltage < 0.1 or upper_voltage > 10):
            upper_voltage = None
        
        return lower_voltage, upper_voltage
        
    except Exception as e:
        print(f"Warning: Could not extract cutoff voltages from Neware file: {e}")
        return None, None

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
    """Detect if the file is a Biologic CSV, Neware XLSX, or MTI XLSX based on content."""
    # Reset file position
    file_obj.seek(0)
    
    # Read first few bytes to check for XLSX signature
    first_bytes = file_obj.read(4)
    file_obj.seek(0)
    
    # XLSX files start with PK\x03\x04 (ZIP format)
    if first_bytes == b'PK\x03\x04':
        # It's an XLSX file - need to determine if it's Neware or MTI
        try:
            # Try to load the workbook to check sheet names
            import openpyxl
            wb = openpyxl.load_workbook(file_obj, read_only=True)
            sheet_names = wb.sheetnames
            wb.close()
            
            # Reset file position after checking
            file_obj.seek(0)
            
            # MTI files have a sheet called 'Cycle List1'
            if 'Cycle List1' in sheet_names:
                return 'mti_xlsx'
            # Neware files have a sheet called 'cycle'
            elif 'cycle' in sheet_names:
                return 'neware_xlsx'
            else:
                # Default to Neware if we can't determine
                return 'neware_xlsx'
        except Exception as e:
            # If we can't read the workbook, default to Neware
            file_obj.seek(0)
            return 'neware_xlsx'
    else:
        return 'biologic_csv'

def parse_biologic_csv(file_obj, dataset: Dict[str, Any], project_type: str = "Full Cell") -> Tuple[pd.DataFrame, Optional[float], Optional[float]]:
    """Parse Biologic CSV file format.
    
    Returns:
        Tuple of (dataframe, None, None) - Biologic files don't contain cutoff voltages
    """
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
        
        # Biologic files don't contain cutoff voltage info - return None
        return df, None, None
        
    except Exception as e:
        raise ValueError(f"Error parsing Biologic CSV file: {str(e)}")

def parse_neware_xlsx(file_obj, dataset: Dict[str, Any], project_type: str = "Full Cell") -> Tuple[pd.DataFrame, Optional[float], Optional[float]]:
    """Parse Neware XLSX file format from the 'cycle' sheet.
    
    Returns:
        Tuple of (dataframe, lower_cutoff_voltage, upper_cutoff_voltage)
    """
    try:
        # Extract cutoff voltages before reading cycle data
        lower_voltage, upper_voltage = extract_cutoff_voltages_from_neware(file_obj)
        
        # Reset file position after extracting voltages
        file_obj.seek(0)
        
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
        
        return processed_df, lower_voltage, upper_voltage
        
    except Exception as e:
        raise ValueError(f"Error parsing Neware XLSX file: {str(e)}")

def parse_mti_xlsx(file_obj, dataset: Dict[str, Any], project_type: str = "Full Cell") -> Tuple[pd.DataFrame, Optional[float], Optional[float]]:
    """Parse MTI XLSX file format from the 'Cycle List1' sheet.
    
    Returns:
        Tuple of (dataframe, lower_cutoff_voltage, upper_cutoff_voltage)
    """
    try:
        # Extract cutoff voltages before reading cycle data
        lower_voltage, upper_voltage = extract_cutoff_voltages_from_mti(file_obj)
        
        # Reset file position after extracting voltages
        file_obj.seek(0)
        
        # Read the 'Cycle List1' sheet from the XLSX file
        df = pd.read_excel(file_obj, sheet_name='Cycle List1')
        
        # Clean column names (remove extra whitespace)
        df.columns = df.columns.str.strip()
        
        # Check if required columns exist
        required_columns = ['Cycle', 'Charge C(mAh)', 'Discharge C(mAh)']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            available_columns = df.columns.tolist()
            raise ValueError(f"Missing required columns: {missing_columns}. Available columns: {available_columns}")
        
        # Create a new DataFrame with the expected column structure
        processed_df = pd.DataFrame()
        
        # Map cycle number
        processed_df['Cycle'] = df['Cycle']
        
        # Map charge capacity (MTI uses mAh, same as expected format)
        processed_df['Q charge (mA.h)'] = df['Charge C(mAh)'].fillna(0)
        
        # Map discharge capacity
        processed_df['Q discharge (mA.h)'] = df['Discharge C(mAh)'].fillna(0)
        
        # Remove rows where both charge and discharge are zero (likely invalid data)
        valid_rows = (processed_df['Q charge (mA.h)'] > 0) | (processed_df['Q discharge (mA.h)'] > 0)
        processed_df = processed_df[valid_rows].reset_index(drop=True)
        
        if len(processed_df) == 0:
            raise ValueError("No valid data found in the file after filtering")
        
        # Calculate gravimetric capacities using user-provided loading and active material
        active_mass = (dataset['loading'] / 1000) * (dataset['active'] / 100)
        if active_mass <= 0:
            raise ValueError("Active mass must be greater than 0. Check loading and active material values.")
        
        processed_df['Q Chg (mAh/g)'] = processed_df['Q charge (mA.h)'] / active_mass
        processed_df['Q Dis (mAh/g)'] = processed_df['Q discharge (mA.h)'] / active_mass
        processed_df['Test Number'] = dataset['testnum']
        
        # Cross-check with file's specific capacity values if they exist
        warnings = []
        if 'ChargeSpecific Capacity(mAh/g)' in df.columns and 'DischargeSpecific Capacity(mAh/g)' in df.columns:
            file_charge_spec = df['ChargeSpecific Capacity(mAh/g)'].fillna(0)
            file_discharge_spec = df['DischargeSpecific Capacity(mAh/g)'].fillna(0)
            
            # Only compare rows where file has non-zero values
            for idx in range(len(processed_df)):
                if idx < len(file_charge_spec) and file_charge_spec.iloc[idx] > 0:
                    calculated_charge = processed_df['Q Chg (mAh/g)'].iloc[idx]
                    file_charge = file_charge_spec.iloc[idx]
                    percent_diff = abs(calculated_charge - file_charge) / file_charge * 100
                    
                    if percent_diff > 5:  # More than 5% difference is a warning
                        warnings.append(
                            f"Cycle {processed_df['Cycle'].iloc[idx]}: Charge capacity mismatch - "
                            f"Calculated: {calculated_charge:.2f} mAh/g, File: {file_charge:.2f} mAh/g "
                            f"(Difference: {percent_diff:.1f}%)"
                        )
                
                if idx < len(file_discharge_spec) and file_discharge_spec.iloc[idx] > 0:
                    calculated_discharge = processed_df['Q Dis (mAh/g)'].iloc[idx]
                    file_discharge = file_discharge_spec.iloc[idx]
                    percent_diff = abs(calculated_discharge - file_discharge) / file_discharge * 100
                    
                    if percent_diff > 5:  # More than 5% difference is a warning
                        warnings.append(
                            f"Cycle {processed_df['Cycle'].iloc[idx]}: Discharge capacity mismatch - "
                            f"Calculated: {calculated_discharge:.2f} mAh/g, File: {file_discharge:.2f} mAh/g "
                            f"(Difference: {percent_diff:.1f}%)"
                        )
            
            # If there are warnings, print them (they'll be visible in the UI)
            if warnings:
                print("\n⚠️  MTI Specific Capacity Cross-Check Warnings:")
                for warning in warnings[:5]:  # Show first 5 warnings
                    print(f"  • {warning}")
                if len(warnings) > 5:
                    print(f"  • ... and {len(warnings) - 5} more warnings")
                print("\nNote: Using calculated values based on your loading and active material inputs.\n")
        
        # Calculate efficiency based on project type
        # MTI provides efficiency in the file, but we'll recalculate for consistency
        processed_df['Efficiency (-)'] = calculate_efficiency_based_on_project_type(
            processed_df['Q charge (mA.h)'], 
            processed_df['Q discharge (mA.h)'], 
            project_type
        ) / 100  # Convert back to decimal for consistency with existing code
        
        return processed_df, lower_voltage, upper_voltage
        
    except Exception as e:
        raise ValueError(f"Error parsing MTI XLSX file: {str(e)}")

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
            df, lower_voltage, upper_voltage = parse_biologic_csv(file_obj, ds, project_type)
        elif file_type == 'neware_xlsx':
            df, lower_voltage, upper_voltage = parse_neware_xlsx(file_obj, ds, project_type)
        elif file_type == 'mti_xlsx':
            df, lower_voltage, upper_voltage = parse_mti_xlsx(file_obj, ds, project_type)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        # Allow manual override of cutoff voltages if provided in dataset
        if 'cutoff_voltage_lower' in ds and ds['cutoff_voltage_lower'] is not None:
            lower_voltage = ds['cutoff_voltage_lower']
        if 'cutoff_voltage_upper' in ds and ds['cutoff_voltage_upper'] is not None:
            upper_voltage = ds['cutoff_voltage_upper']
        
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
            'porosity': porosity,
            'cutoff_voltage_lower': lower_voltage,
            'cutoff_voltage_upper': upper_voltage
        })
    return dfs

def calculate_summary_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate summary statistics for a single cell's dataframe."""
    return {}

def calculate_averages(dfs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate averages across all cells."""
    return {} 