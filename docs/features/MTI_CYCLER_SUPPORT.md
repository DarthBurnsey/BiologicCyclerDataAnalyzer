# MTI Cycler File Support

## Overview

CellScope now supports MTI cycler output files in addition to Biologic and Neware formats. MTI files are XLSX files with cycling data organized in a specific sheet structure.

## File Format

MTI cycler files should be XLSX format with the following characteristics:

### Required Sheet

- **Sheet Name**: `Cycle List1`

### Required Columns

The following columns must be present in the `Cycle List1` sheet:

1. **Cycle** - Cycle number (integer)
2. **Charge C(mAh)** - Charge capacity in mAh
3. **Discharge C(mAh)** - Discharge capacity in mAh

### Optional Columns

These columns are optional but will be used for cross-checking if present:

- **ChargeSpecific Capacity(mAh/g)** - Specific charge capacity in mAh/g
- **DischargeSpecific Capacity(mAh/g)** - Specific discharge capacity in mAh/g
- **Chg/Dis Efficiency(%)** - Efficiency percentage

## Usage

### Uploading MTI Files

1. Navigate to the experiment creation page
2. Use the file uploader to select your MTI XLSX file(s)
3. Enter the required parameters:
   - **Loading** (mg): Electrode disc mass in milligrams
   - **Active Material %**: Percentage of active material in the electrode
4. The system will automatically detect the MTI file format

### Data Processing

The MTI parser will:

1. **Read Data**: Extract cycling data from the `Cycle List1` sheet
2. **Calculate Specific Capacities**: Compute gravimetric capacities using the formula:
   ```
   Active Mass (g) = (Loading in mg / 1000) × (Active % / 100)
   Specific Capacity (mAh/g) = Capacity (mAh) / Active Mass (g)
   ```
3. **Calculate Efficiency**: Compute coulombic efficiency based on project type
4. **Cross-Check** (if applicable): Compare calculated values with file's specific capacity columns

## Cross-Check Feature

If the MTI file contains `ChargeSpecific Capacity(mAh/g)` and `DischargeSpecific Capacity(mAh/g)` columns with non-zero values, the parser will perform a cross-check:

### What is Checked

The system compares:
- Your calculated charge specific capacity vs. the file's charge specific capacity
- Your calculated discharge specific capacity vs. the file's discharge specific capacity

### Warning Threshold

Warnings are displayed if the difference exceeds **5%** between calculated and file values.

### Example Warning

```
⚠️  MTI Specific Capacity Cross-Check Warnings:
  • Cycle 1: Charge capacity mismatch - Calculated: 500.00 mAh/g, File: 592.10 mAh/g (Difference: 15.6%)
  • Cycle 1: Discharge capacity mismatch - Calculated: 422.22 mAh/g, File: 500.00 mAh/g (Difference: 15.6%)

Note: Using calculated values based on your loading and active material inputs.
```

### Why Cross-Check?

This feature helps ensure data consistency by:
1. Verifying that your entered loading and active material % are correct
2. Detecting potential unit mismatches
3. Identifying if the file was generated with different parameters

### What to Do if Warnings Appear

If you see cross-check warnings:

1. **Verify your inputs**: Double-check the loading (mg) and active material (%) you entered
2. **Check file parameters**: The MTI file may have been generated with different loading/active material values
3. **Unit consistency**: Ensure your loading is in mg (not g or μg)
4. **Note**: The system will always use **your entered values** for calculations, not the file's values

## File Type Detection

The system automatically detects MTI files by:

1. Checking if the file is XLSX format (ZIP signature: `PK\x03\x04`)
2. Looking for the `Cycle List1` sheet in the workbook
3. If found, the file is identified as `mti_xlsx`

## Data Structure

After processing, MTI files are converted to the same internal format as Biologic and Neware files:

| Column | Description |
|--------|-------------|
| Cycle | Cycle number |
| Q charge (mA.h) | Charge capacity in mAh |
| Q discharge (mA.h) | Discharge capacity in mAh |
| Q Chg (mAh/g) | Specific charge capacity |
| Q Dis (mAh/g) | Specific discharge capacity |
| Efficiency (-) | Coulombic efficiency (decimal, 0-1) |
| Test Number | Cell identifier |

## Example File Structure

Here's what a valid MTI file should look like:

```
Sheet: Cycle List1

| Cycle | Charge C(mAh) | Discharge C(mAh) | ChargeSpecific Capacity(mAh/g) | DischargeSpecific Capacity(mAh/g) | Chg/Dis Efficiency(%) |
|-------|---------------|------------------|--------------------------------|-----------------------------------|-----------------------|
| 1     | 4.737         | 4.042            | 526.38                         | 449.06                            | 85.31                 |
| 2     | 4.069         | 4.051            | 452.07                         | 450.06                            | 99.56                 |
| 3     | 4.120         | 4.022            | 457.74                         | 446.92                            | 97.63                 |
| ...   | ...           | ...              | ...                            | ...                               | ...                   |
```

## Testing

To test MTI file parsing, you can run the included test scripts:

### Basic Parsing Test
```bash
python test_mti_parsing.py
```

This tests:
- File type detection
- Data parsing
- Calculation accuracy
- Integration with data processing pipeline

### Cross-Check Test
```bash
python test_mti_crosscheck.py
```

This demonstrates:
- Cross-checking with matching parameters (no warnings)
- Cross-checking with mismatching parameters (warnings displayed)
- Proper handling of specific capacity columns

## Implementation Details

### File: `data_processing.py`

#### Function: `parse_mti_xlsx(file_obj, dataset, project_type)`

Parses MTI XLSX files from the 'Cycle List1' sheet.

**Parameters:**
- `file_obj`: File object containing the MTI XLSX file
- `dataset`: Dictionary with keys 'testnum', 'loading', 'active'
- `project_type`: String - 'Full Cell', 'Cathode', or 'Anode'

**Returns:**
- pandas DataFrame with standardized columns

**Raises:**
- `ValueError`: If required columns are missing or data is invalid

#### Function: `detect_file_type(file_obj)`

Updated to detect MTI files by checking for the 'Cycle List1' sheet.

**Returns:**
- `'mti_xlsx'` for MTI files
- `'neware_xlsx'` for Neware files
- `'biologic_csv'` for Biologic files

## Compatibility

MTI file support is fully compatible with all existing features:

- ✅ Plotting (capacity, retention, efficiency)
- ✅ Export to Excel
- ✅ Export to PowerPoint
- ✅ Summary metrics calculation
- ✅ Cycle life analysis
- ✅ Formulation comparison
- ✅ Experiment comparison
- ✅ Average performance calculations
- ✅ Multi-cell experiments
- ✅ Project type support (Full Cell, Cathode, Anode)

## Troubleshooting

### "Missing required columns" error

**Problem**: The file doesn't have the expected columns.

**Solution**: 
- Verify the file has a sheet named `Cycle List1` (exact spelling)
- Check that columns `Cycle`, `Charge C(mAh)`, and `Discharge C(mAh)` exist
- Column names are case-sensitive

### Cross-check warnings appearing

**Problem**: Calculated values differ from file's specific capacity values.

**Solution**:
- This is usually not an error - just a notification
- Verify your loading and active material inputs are correct
- The system will use YOUR inputs for all calculations

### File not detected as MTI

**Problem**: File is treated as Neware instead of MTI.

**Solution**:
- Ensure the file is in XLSX format (not XLS or CSV)
- Verify the sheet is named exactly `Cycle List1`
- Check that the file is not corrupted

## Version History

- **v1.0** (January 2026): Initial MTI file support implementation
  - Auto-detection of MTI XLSX files
  - Parsing from 'Cycle List1' sheet
  - Cross-check feature for specific capacity validation
  - Full integration with existing CellScope features


