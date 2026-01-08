# Fix for Duplicate Experiment Default Values

## Problem
When duplicating an experiment and uploading new data files, the default values for Disc Loading (mg) and % Active Material were not being pre-populated with the values from the original experiment. Users had to manually re-enter these values for each new upload.

## Root Cause
The `duplicate_experiment()` function was creating an empty experiment with all experiment-level metadata (disc diameter, electrolyte, etc.) but was not preserving the cell-level default values (loading, active material, formation cycles, etc.) from the original experiment's cells. 

When the file upload interface was shown for the duplicated experiment, it had no information about what default values to use.

## Solution

### Changes Made:

#### 1. Database Layer (`database.py` - lines 658-684)
Enhanced the `duplicate_experiment()` function to extract and store default cell values from the first cell of the original experiment:

```python
# Extract default cell values from the first cell of the original experiment
cells = data_json.get('cells', [])
default_cell_values = {}
if cells and len(cells) > 0:
    first_cell = cells[0]
    default_cell_values = {
        'loading': first_cell.get('loading', 20.0),
        'active_material': first_cell.get('active_material', 90.0),
        'formation_cycles': first_cell.get('formation_cycles', 4),
        'electrolyte': first_cell.get('electrolyte', '1M LiPF6 1:1:1'),
        'substrate': first_cell.get('substrate', 'Copper'),
        'separator': first_cell.get('separator', '25um PP'),
        'formulation': first_cell.get('formulation', [])
    }

# Store in experiment data
new_experiment_data = {
    # ... other fields ...
    'default_cell_values': default_cell_values
}
```

#### 2. Application Layer (`app.py` - lines 1444-1467)
Updated the file upload section to pre-populate session state with default values when loading a duplicated experiment:

```python
# For duplicated experiments, pre-populate defaults from original experiment
if loaded_experiment:
    experiment_data = loaded_experiment['experiment_data']
    default_cell_values = experiment_data.get('default_cell_values', {})
    
    if default_cell_values:
        st.info("ℹ️ Using default values from the original experiment. You can modify these as needed.")
        # Pre-populate session state with default values
        if 'loading_0' not in st.session_state:
            st.session_state['loading_0'] = default_cell_values.get('loading', 20.0)
        if 'active_0' not in st.session_state:
            st.session_state['active_0'] = default_cell_values.get('active_material', 90.0)
        # ... and all other fields ...
```

## Behavior Now

### When You Duplicate an Experiment:

1. Click "⋯" → "Duplicate" on an experiment (e.g., "T23")
2. New experiment created: "T23 (1)"
3. Click on "T23 (1)" to open it
4. See message: "📝 Setting up experiment: **T23 (1)** (ready for data upload)"
5. See info: "ℹ️ Using default values from the original experiment. You can modify these as needed."
6. **Upload CSV/XLSX files**
7. **Default values are pre-populated**:
   - ✅ Disc Loading (mg) - from original first cell
   - ✅ % Active Material - from original first cell
   - ✅ Formation Cycles - from original first cell
   - ✅ Electrolyte - from original first cell
   - ✅ Substrate - from original first cell
   - ✅ Separator - from original first cell
   - ✅ Formulation - from original first cell
8. Modify values if needed
9. Upload and save

### Default Values Used:

The duplication function intelligently extracts defaults from the **first cell** of the original experiment. This makes sense because:
- In most experiments, all cells have similar parameters
- The first cell is typically representative of the experiment setup
- Users can modify these defaults for each new file uploaded

### What if Original Had No Cells?

If you duplicate an experiment that itself had no cells (e.g., duplicating a duplicate), the system falls back to:
- Project preferences (if set)
- Hard-coded defaults (loading: 20.0 mg, active: 90.0%, etc.)

## Example Workflow

### Original Experiment "T23":
- Cell 1: Loading = 18.5 mg, Active = 95.0%
- Cell 2: Loading = 18.7 mg, Active = 95.0%
- Electrolyte: "1M LiTFSI 3:7 +10% FEC"

### After Duplication "T23 (1)":
When you upload new files:
- **Disc Loading** defaults to: **18.5 mg** ✅
- **% Active Material** defaults to: **95.0%** ✅
- **Electrolyte** defaults to: **"1M LiTFSI 3:7 +10% FEC"** ✅
- **Formation Cycles** defaults to: (from original) ✅
- **Formulation** defaults to: (from original) ✅

## Files Modified

1. `database.py` - Enhanced `duplicate_experiment()` function (~25 lines changed)
2. `app.py` - Added default value pre-population logic (~25 lines added)

## Testing

### Manual Test:
1. Open existing experiment with data
2. Note the loading/active values (e.g., 18.5 mg, 95%)
3. Duplicate the experiment
4. Click on duplicate to open it
5. Upload a new CSV file
6. **Verify**: Loading defaults to 18.5 mg ✅
7. **Verify**: Active defaults to 95% ✅
8. **Verify**: Electrolyte matches original ✅
9. **Verify**: All other values match original ✅

## Related Issues

- Original duplicate feature: `DUPLICATE_FEATURE_DOCUMENTATION.md`
- Upload interface fix: `DUPLICATE_UPLOAD_FIX.md`
- This completes the duplicate experiment feature with full usability










