# Fix for Duplicate Experiment Upload Issue

## Problem
When duplicating an experiment, the new experiment had all metadata copied but no cell data (as intended). However, when users clicked on the duplicated experiment, they couldn't see file upload buttons to add new data.

## Root Cause
The app's logic checked if an experiment was "loaded" to determine whether to show:
- **Edit interface** (for experiments with existing cell data)
- **Upload interface** (for new experiments without cell data)

Duplicated experiments were treated as "loaded experiments" (since they exist in the database), but they had no cells to edit. The code didn't handle this edge case, so neither interface was shown.

## Solution

### Changes Made in `app.py`:

1. **Line 1045-1046**: Added logic to check if a loaded experiment has cells:
```python
# Show file upload for new experiments OR loaded experiments with no cells (e.g., duplicates)
has_cells = loaded_experiment and len(datasets) > 0
```

2. **Line 1048**: Updated condition to only show edit interface when experiment has cells:
```python
if loaded_experiment and has_cells:
```

3. **Lines 837-841**: Added informative message for empty experiments:
```python
# Show different message for experiments with no cells (e.g., duplicates)
if len(cells_data) == 0:
    st.info(f"📝 Setting up experiment: **{loaded_experiment['experiment_name']}** (ready for data upload)")
else:
    st.info(f"📊 Editing experiment: **{loaded_experiment['experiment_name']}**")
```

## Behavior Now

### For Duplicated Experiments:
1. User clicks on duplicated experiment (e.g., "T23 (1)")
2. App shows: "📝 Setting up experiment: **T23 (1)** (ready for data upload)"
3. File upload interface is displayed (same as new experiments)
4. User can upload CSV/XLSX files
5. After upload, experiment functions normally

### For Existing Experiments:
1. User clicks on existing experiment with data
2. App shows: "📊 Editing experiment: **T23**"
3. Edit interface is displayed with existing cell data
4. User can modify parameters, exclude cells, etc.

### For New Experiments:
1. User creates new experiment in a project
2. App shows: "📝 Creating a new experiment in project: **ProjectName**"
3. File upload interface is displayed
4. User can upload CSV/XLSX files

## Testing

### Manual Test Steps:
1. Open CellScope app
2. Navigate to a project with an experiment
3. Duplicate an existing experiment (click ⋯ → Duplicate)
4. Click on the duplicated experiment (e.g., "T23 (1)")
5. **Verify**: Message shows "Setting up experiment: T23 (1) (ready for data upload)"
6. **Verify**: File upload interface is visible
7. Upload a CSV or XLSX file
8. **Verify**: File uploads successfully and data is processed
9. Click on the original experiment
10. **Verify**: Edit interface is shown (not upload interface)

### Edge Cases Handled:
✅ Duplicated experiment with no cells → Shows upload interface
✅ Existing experiment with cells → Shows edit interface  
✅ New experiment (not in database) → Shows upload interface
✅ Deleted all cells from loaded experiment → Would show upload interface

## Files Modified
- `app.py` - Lines 837-841, 1045-1048 (8 lines changed)

## Related Issues
- Original duplicate feature implementation: `DUPLICATE_FEATURE_DOCUMENTATION.md`
- This fix completes the duplicate experiment workflow





