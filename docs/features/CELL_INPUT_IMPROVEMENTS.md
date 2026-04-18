# Cell Input Improvements

## Overview

This document describes the improvements made to the Cell Inputs functionality to fix bugs and enhance usability.

**Implementation Date:** January 8, 2026

## Changes Made

### 1. Bug Fix: Clear Cell Inputs on New Experiment ✅

**Problem:**
When starting a new experiment in a project, previously entered values and uploaded files from a recent experiment in that project were being shown on the Cell Inputs page, instead of a clean slate.

**Root Cause:**
Session state variables for cell inputs (loading, active material, test numbers, electrolytes, substrates, separators, and formulations) were not being completely cleared when starting a new experiment. Some keys like `separator_` and `use_same_formulation_` were missing from the cleanup list.

**Solution:**
Enhanced the session state cleanup in `app.py` when `start_new_experiment` is True:

**File Modified:** `app.py` (lines 827-852)

Added missing keys to the cleanup list:
- `separator_*` - Separator selections for each cell
- `use_same_formulation_*` - Toggle for using same formulation across cells

**Code Changes:**
```python
# Clear any remaining cell input session state variables
keys_to_clear = []
for key in st.session_state.keys():
    # Clear cell-specific input fields that might have been missed
    if (key.startswith('loading_') or 
        key.startswith('active_') or 
        key.startswith('testnum_') or 
        key.startswith('formation_cycles_') or
        key.startswith('electrolyte_') or
        key.startswith('substrate_') or
        key.startswith('separator_') or  # ADDED
        key.startswith('formulation_data_') or 
        key.startswith('formulation_saved_') or
        key.startswith('component_dropdown_') or
        key.startswith('component_text_') or
        key.startswith('fraction_') or
        key.startswith('add_row_') or
        key.startswith('delete_row_') or
        key.startswith('multi_file_upload_') or
        key.startswith('assign_all_cells_') or
        key.startswith('use_same_formulation_') or  # ADDED
        key == 'datasets' or
        key == 'processed_data_cache' or
        key == 'cache_key'):
        keys_to_clear.append(key)

# Remove the keys
for key in keys_to_clear:
    del st.session_state[key]
```

**Result:**
When clicking "New Experiment", the Cell Inputs page is now completely blank with no residual data from previous experiments.

---

### 2. Feature: Auto-Naming Cells with Roman Numerals ✅

**Feature Request:**
Automatically generate cell names using the experiment name followed by a roman numeral (e.g., "Test Experiment i", "Test Experiment ii", "Test Experiment iii") instead of generic names like "Cell 1", "Cell 2", "Cell 3".

**Benefits:**
- Better organization and traceability
- Clear association between cells and their parent experiment
- Professional naming convention
- Users can still edit names if desired

**Implementation:**

#### A. Roman Numeral Converter Function

**File:** `ui_components.py`

Added a new utility function to convert integers to lowercase roman numerals:

```python
def int_to_roman(num: int) -> str:
    """Convert an integer to lowercase roman numeral."""
    val = [
        1000, 900, 500, 400,
        100, 90, 50, 40,
        10, 9, 5, 4,
        1
    ]
    syms = [
        'm', 'cm', 'd', 'cd',
        'c', 'xc', 'l', 'xl',
        'x', 'ix', 'v', 'iv',
        'i'
    ]
    roman_num = ''
    i = 0
    while num > 0:
        for _ in range(num // val[i]):
            roman_num += syms[i]
            num -= val[i]
        i += 1
    return roman_num
```

**Examples:**
- 1 → i
- 2 → ii
- 3 → iii
- 4 → iv
- 5 → v
- 10 → x
- 12 → xii
- 20 → xx

#### B. Updated `render_cell_inputs` Function

**File:** `ui_components.py`

Updated the function signature to accept an optional `experiment_name` parameter:

```python
def render_cell_inputs(context_key=None, project_id=None, get_components_func=None, experiment_name=None):
    """Render multi-file upload and per-file inputs for each cell. Returns datasets list.
    
    Args:
        context_key: Unique key for this render context
        project_id: ID of the project for defaults
        get_components_func: Function to get formulation components
        experiment_name: Name of experiment for auto-generating cell names (e.g., "Test i", "Test ii")
    """
```

#### C. Updated Test Number Default Values

**File:** `ui_components.py`

Updated three locations where test number defaults are set:

**1. First cell in multi-cell upload (line ~1140):**
```python
# Auto-generate cell name using experiment name + roman numeral
default_cell_name = f"{experiment_name} {int_to_roman(1)}" if experiment_name else 'Cell 1'
test_number_0 = st.text_input(f'Test Number for Cell 1', value=default_cell_name, key=f'testnum_0')
```

**2. Subsequent cells in multi-cell upload (line ~1292):**
```python
# Test number is always individual (not assigned to all)
with col2:
    # Auto-generate cell name using experiment name + roman numeral
    default_test_num = f"{experiment_name} {int_to_roman(i+1)}" if experiment_name else f'Cell {i+1}'
    test_number = st.text_input(f'Test Number for Cell {i+1}', value=default_test_num, key=f'testnum_{i}')
```

**3. Single cell upload (line ~1332):**
```python
# Auto-generate cell name using experiment name + roman numeral
default_cell_name = f"{experiment_name} {int_to_roman(1)}" if experiment_name else 'Cell 1'
test_number = st.text_input(f'Test Number for Cell 1', value=default_cell_name, key=f'testnum_0')
```

#### D. Updated Function Call in app.py

**File:** `app.py` (line ~1503)

Updated the call to `render_cell_inputs` to pass the experiment name:

```python
current_project_id = st.session_state.get('current_project_id')
# Pass experiment name for auto-generating cell names with roman numerals
# Use experiment_name_input directly (defined above) for real-time updates
datasets = render_cell_inputs(
    context_key='main_cell_inputs', 
    project_id=current_project_id, 
    get_components_func=get_project_components,
    experiment_name=experiment_name_input if experiment_name_input else ''
)
st.session_state['datasets'] = datasets
```

**Key Design Decision:**
We use `experiment_name_input` directly (which is defined earlier in the code at line 956) rather than getting it from session state. This ensures the cell names update in real-time as the user types the experiment name.

---

## User Experience

### Before Changes:

**Starting New Experiment:**
- Cell Inputs page showed previous experiment's data
- Loading values from previous experiment
- Electrolyte/substrate/separator selections from previous cells
- Uploaded files appeared to be present (but were actually stale references)

**Cell Naming:**
- Cell 1
- Cell 2
- Cell 3
- etc.

### After Changes:

**Starting New Experiment:**
- ✅ Completely blank Cell Inputs page
- ✅ No residual data from previous experiments
- ✅ Fresh start for all input fields
- ✅ Clean file uploader with no stale references

**Cell Naming:**
If experiment name is "Battery Test":
- Battery Test i
- Battery Test ii
- Battery Test iii
- Battery Test iv
- etc.

If no experiment name is entered yet:
- Cell 1 (falls back to generic name)
- Cell 2
- Cell 3
- etc.

**Editing Names:**
Users can still freely edit the auto-generated names in the text input fields. The auto-generation only sets the initial default value.

---

## Technical Details

### Session State Management

When starting a new experiment (`start_new_experiment` = True), the following session state keys are cleared:

| Key Pattern | Description |
|-------------|-------------|
| `loading_*` | Disc loading values for each cell |
| `active_*` | Active material percentages |
| `testnum_*` | Test numbers/cell names |
| `formation_cycles_*` | Formation cycle counts |
| `electrolyte_*` | Electrolyte selections |
| `substrate_*` | Substrate selections |
| `separator_*` | Separator selections (newly added) |
| `formulation_data_*` | Formulation table data |
| `formulation_saved_*` | Formulation save flags |
| `component_dropdown_*` | Component dropdown selections |
| `component_text_*` | Component text inputs |
| `fraction_*` | Mass fraction values |
| `add_row_*` | Add row button states |
| `delete_row_*` | Delete row button states |
| `multi_file_upload_*` | File uploader states |
| `assign_all_cells_*` | Assign-to-all checkbox states |
| `use_same_formulation_*` | Same formulation toggle (newly added) |
| `datasets` | Dataset list |
| `processed_data_cache` | Cached processed data |
| `cache_key` | Cache key for data processing |

### Real-Time Updates

The cell names update in real-time as the user types the experiment name because:

1. The experiment name input field is rendered first (before cell inputs)
2. The `render_cell_inputs` function is called with `experiment_name_input` directly
3. Streamlit's reactivity ensures the page re-renders when the experiment name changes
4. The default values for test numbers are recalculated on each render

This provides immediate visual feedback to users as they enter the experiment name.

---

## Testing

### Manual Testing Checklist

- ✅ Start new experiment in a project with existing experiments
- ✅ Verify Cell Inputs page is completely blank
- ✅ No loading values from previous experiments
- ✅ No electrolyte/substrate/separator selections from previous experiments
- ✅ No formulation data from previous experiments
- ✅ File uploader is empty with no stale references
- ✅ Enter experiment name "Test"
- ✅ Upload multiple files
- ✅ Verify cells are auto-named "Test i", "Test ii", "Test iii", etc.
- ✅ Edit a cell name to verify editability
- ✅ Clear experiment name
- ✅ Verify cells fall back to "Cell 1", "Cell 2", "Cell 3"
- ✅ Roman numerals work correctly for numbers 1-20+

### Edge Cases Handled

1. **No experiment name entered:** Falls back to "Cell 1", "Cell 2", etc.
2. **Empty experiment name:** Same as above
3. **Long experiment names:** No truncation, full name is used
4. **Special characters in name:** Supported (e.g., "Test-A i", "Test_B ii")
5. **Large cell numbers:** Roman numerals work for any positive integer
6. **User edits cell name:** Edit is preserved, not overwritten
7. **Loaded experiments:** Auto-naming only applies to new experiments, not when loading existing ones

---

## Backward Compatibility

✅ **Fully backward compatible**

- Existing experiments maintain their original cell names
- Loaded experiments are not affected by the auto-naming feature
- If users prefer the old "Cell 1", "Cell 2" naming, they can simply clear the experiment name
- All existing functionality remains unchanged

---

## Future Enhancements (Optional)

Potential future improvements:
1. Configurable naming pattern (e.g., letters instead of roman numerals)
2. Option to disable auto-naming in project preferences
3. Batch rename cells after experiment creation
4. Custom suffixes or prefixes per project

---

## Files Modified

1. **app.py**
   - Enhanced session state cleanup for new experiments
   - Updated `render_cell_inputs` call to pass experiment name

2. **ui_components.py**
   - Added `int_to_roman()` utility function
   - Updated `render_cell_inputs()` signature to accept experiment name
   - Updated test number default values in three locations

---

## Code Quality

- ✅ No linter errors
- ✅ Consistent code style
- ✅ Clear variable names
- ✅ Comprehensive comments
- ✅ Proper function documentation
- ✅ Backward compatible
- ✅ Edge cases handled

---

## Summary

These improvements significantly enhance the user experience when creating new experiments:

1. **Bug Fix:** Clean slate for new experiments with no residual data
2. **Auto-Naming:** Professional cell naming with roman numerals
3. **Real-Time Updates:** Cell names update as experiment name is typed
4. **User Control:** Names remain editable by the user
5. **Backward Compatible:** No impact on existing experiments

The changes are production-ready and require no additional setup or configuration.


