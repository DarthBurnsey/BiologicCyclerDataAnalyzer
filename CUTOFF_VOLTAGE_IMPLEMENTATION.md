# Cutoff Voltage Feature Implementation

## Overview

Successfully added comprehensive cutoff voltage tracking to CellScope. This feature allows tracking of upper and lower cutoff voltages for battery cell testing, with automatic extraction from MTI and Neware cycler files and manual entry support for Biologic files.

## Implementation Date

January 20, 2026

## Features

### 1. Automatic Extraction
- **MTI Files**: Cutoff voltages are automatically extracted from the 'Ch info' tab, column C
  - Supports various voltage formats (e.g., "3.0-4.2V", "3.0 - 4.2 V")
  - Pattern matching for protocol-based voltage identification
- **Neware Files**: Cutoff voltages are automatically extracted from the 'test' tab, column G
  - Supports range formats and individual voltage specifications
  - Smart voltage magnitude-based classification (< 3.0V = lower, > 3.0V = upper)

### 2. Manual Entry
- **Biologic Files**: Manual input fields provided on Cell Inputs page
- Input fields with validation (0.0V to 10.0V range)
- Defaults to common values (2.5V lower, 4.2V upper)
- Editable for all file types if auto-extraction fails or needs override

### 3. Database Storage
- New columns: `cutoff_voltage_lower` and `cutoff_voltage_upper` (REAL type)
- Stored at experiment level in `cell_experiments` table
- Automatically migrated to existing databases

### 4. Master Table Display
- New column: "Cutoff Voltages (V)"
- Display format: "2.5-4.2" (lower-upper)
- Available in both experiment summary and individual cells tables
- Included in column filter options

## Files Modified

### 1. `database.py`
**Changes:**
- Added `cutoff_voltage_lower` and `cutoff_voltage_upper` columns to migration
- Updated `save_experiment()` to store cutoff voltages
- Updated `update_experiment()` to store cutoff voltages
- Updated `get_all_project_experiments_data()` to retrieve cutoff voltages

### 2. `data_processing.py`
**Changes:**
- Added `extract_cutoff_voltages_from_mti()` function
- Added `extract_cutoff_voltages_from_neware()` function
- Updated `parse_biologic_csv()` to return (df, None, None)
- Updated `parse_neware_xlsx()` to extract and return cutoff voltages
- Updated `parse_mti_xlsx()` to extract and return cutoff voltages
- Updated `load_and_preprocess_data()` to handle cutoff voltage data and allow manual overrides

### 3. `ui_components.py`
**Changes:**
- Added cutoff voltage input fields to `render_cell_inputs()`
- Two number input fields: Lower Cutoff Voltage (V) and Upper Cutoff Voltage (V)
- Added for both single-cell and multi-cell upload scenarios
- Added to "assign all" functionality for batch cell entry
- Cutoff voltages included in datasets dictionary

### 4. `display_components.py`
**Changes:**
- Added "Cutoff Voltages (V)" to column definitions in both tables
- Updated `display_experiment_summaries_table()` to format and display cutoff voltages
- Updated `display_individual_cells_table()` to format and display cutoff voltages
- Format: "lower-upper" (e.g., "2.5-4.2")
- Shows "N/A" when values are not available

### 5. `app.py`
**Changes:**
- Updated data unpacking to include `cutoff_voltage_lower` and `cutoff_voltage_upper`
- Added cutoff voltage data to cell summaries for multi-cell experiments
- Added cutoff voltage data to experiment summaries
- Added cutoff voltage data to legacy single-cell experiments

## Usage

### For MTI Files
1. Upload MTI XLSX file in Cell Inputs
2. Cutoff voltages automatically extracted from 'Ch info' tab, column C
3. Values pre-populated in input fields
4. Can be manually overridden if needed

### For Neware Files
1. Upload Neware XLSX file in Cell Inputs
2. Cutoff voltages automatically extracted from 'test' tab, column G
3. Values pre-populated in input fields
4. Can be manually overridden if needed

### For Biologic Files
1. Upload Biologic CSV file in Cell Inputs
2. Manually enter lower and upper cutoff voltages
3. Defaults provided (2.5V and 4.2V)

### Viewing in Master Table
1. Navigate to Master Table tab
2. Open Column Filter
3. Select "Cutoff Voltages (V)" column
4. View in format "lower-upper" (e.g., "2.5-4.2")

## Technical Details

### Voltage Extraction Logic

#### MTI Files
```python
# Reads 'Ch info' sheet, column C
# Pattern matching for:
# - Range format: "3.0-4.2V"
# - Individual keywords: "lower", "upper", "min", "max"
# - Validates range: 0.1V to 10V
```

#### Neware Files
```python
# Reads 'test' sheet, column G
# Pattern matching for:
# - Range format: "3.0-4.2V"
# - End voltage keywords
# - Smart classification by magnitude (< 3.0V = lower, > 3.0V = upper)
# - Validates range: 0.1V to 10V
```

### Display Format
- Format: `f"{lower}-{upper}"` (e.g., "2.5-4.2")
- Shows "N/A" when either value is None
- Both values required for display

### Database Schema
```sql
ALTER TABLE cell_experiments ADD COLUMN cutoff_voltage_lower REAL;
ALTER TABLE cell_experiments ADD COLUMN cutoff_voltage_upper REAL;
```

## Benefits

1. **Better Cell Understanding**: Cutoff voltages indicate how hard cells were pushed during testing
2. **Automatic Data Capture**: No manual entry needed for MTI/Neware files
3. **Consistency**: Standardized format across all experiments
4. **Flexibility**: Manual override available when needed
5. **Historical Data**: Integrated with existing Master Table display

## Testing Recommendations

1. Test with MTI files to verify 'Ch info' extraction
2. Test with Neware files to verify 'test' tab extraction
3. Test with Biologic files to verify manual entry
4. Verify display in Master Table shows correct format
5. Test with existing experiments (should show "N/A" for missing data)
6. Test column filtering in Master Table

## Notes

- Existing experiments without cutoff voltage data will display "N/A"
- Cutoff voltages are optional fields (can be NULL in database)
- Extraction uses regex patterns - may need adjustment for different file formats
- Values are validated to be between 0.1V and 10V during extraction
