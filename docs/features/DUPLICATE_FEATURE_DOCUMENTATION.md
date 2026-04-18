# Experiment Duplication Feature - Implementation Summary

## Overview
Successfully implemented a "Duplicate" feature that allows users to create copies of experiments with all metadata preserved but ready for new data uploads.

## Changes Made

### 1. Database Functions (`database.py`)

#### New Functions Added:

**`get_experiment_by_id(experiment_id)`**
- Retrieves complete experiment data by ID
- Returns all fields including metadata and data_json

**`generate_duplicate_experiment_name(project_id, base_name)`**
- Generates unique names for duplicated experiments
- Implements smart numbering: `T23` → `T23 (1)` → `T23 (2)`, etc.
- Prevents name conflicts within the same project

**`duplicate_experiment(experiment_id)`**
- Main duplication function
- Copies all experiment metadata:
  - Formulation data
  - Loading parameters
  - Electrolyte selection
  - Current collector (substrate)
  - Separator type
  - Disc diameter
  - Group assignments and names
  - Solids content
  - Pressed thickness
  - Experiment notes
  - Cell format data (anode/cathode dimensions, can format)
- Creates experiment with **empty cell data** (ready for new uploads)
- Returns tuple: `(new_experiment_id, new_experiment_name)`

### 2. User Interface (`app.py`)

#### Import Updates:
- Added `duplicate_experiment` to database imports

#### Experiment Context Menu:
- Added "📋 Duplicate" button between "Rename" and "Delete" options
- Button triggers duplication workflow when clicked
- Menu closes automatically after selection

#### Duplication Handler:
- Located after delete confirmation handlers (lines 739-750)
- Handles duplication with error handling
- Shows success message: `"✅ Successfully duplicated '{original_name}' as '{new_name}'! You can now upload new data to this experiment."`
- Shows error message if duplication fails
- Automatically refreshes UI to show new experiment

### 3. Test Suite (`test_duplicate_experiment.py`)

Created comprehensive test script that verifies:
- ✅ Duplicate naming logic (suffix numbering)
- ✅ Metadata preservation
- ✅ Empty cell data in duplicates
- ✅ Database integrity

## Feature Behavior

### Duplication Process:
1. User clicks "⋯" menu next to an experiment
2. User selects "📋 Duplicate"
3. System creates new experiment with:
   - Auto-generated name (appends `(1)`, `(2)`, etc.)
   - All metadata copied from original
   - Empty cell data (no uploaded files)
   - Same project assignment
4. New experiment appears in experiment list
5. User can upload new CSV/XLSX files to populate data

### Smart Naming Examples:
- Original: `T23` → Duplicate: `T23 (1)`
- Duplicate again: `T23 (2)`
- Duplicate again: `T23 (3)`
- Works with any name: `Experiment A` → `Experiment A (1)`

### Metadata Preserved:
✓ Formulation (active material, binder, conductive additive, etc.)
✓ Loading (mg)
✓ Active material percentage
✓ Formation cycles
✓ Electrolyte
✓ Current collector (substrate)
✓ Separator
✓ Disc diameter
✓ Group assignments
✓ Group names
✓ Solids content
✓ Pressed thickness
✓ Experiment notes
✓ Cell format data (anode/cathode dimensions, separator thickness, can format)

### What's NOT Copied:
✗ Cell data (uploaded CSV/XLSX files)
✗ Cell names
✗ Test numbers
✗ Porosity calculations (will be recalculated when new data is uploaded)

## Testing Instructions

### Automated Tests:
```bash
cd /Users/bradyburns/Projects/CellScope
python3 test_duplicate_experiment.py
```

### Manual Testing:
1. Open the CellScope app: `streamlit run app.py`
2. Navigate to a project with experiments
3. Click the "⋯" menu button next to an experiment
4. Click "📋 Duplicate"
5. **Verify**: New experiment appears with `(1)` suffix
6. Click on the duplicated experiment to open it
7. **Verify**: Metadata is copied (check electrolyte, formulation, etc.)
8. **Verify**: No cell data is present (should show empty state)
9. **Verify**: You can upload new CSV/XLSX files
10. Duplicate the same original experiment again
11. **Verify**: Creates `(2)` instead of conflicting with `(1)`

## Edge Cases Handled

✓ **Multiple duplicates**: Numbering increments correctly `(1)`, `(2)`, `(3)`, etc.
✓ **Name conflicts**: Function checks all existing names before generating new one
✓ **Missing metadata**: Handles experiments with partial metadata gracefully
✓ **Database errors**: Proper error handling with user-friendly messages
✓ **Transaction safety**: Uses database transactions to prevent partial duplications

## Files Modified

1. `database.py` - Added 3 new functions (~100 lines)
2. `app.py` - Updated imports, added menu button, added handler (~20 lines)
3. `test_duplicate_experiment.py` - New test suite (120 lines)

## Validation Results

✅ All automated tests pass
✅ No linter errors
✅ Database integrity maintained
✅ UI integration seamless
✅ Error handling robust

## Future Enhancements (Optional)

- Add confirmation dialog before duplication (like delete)
- Allow user to customize the duplicate name during creation
- Option to copy cell data (not just metadata)
- Bulk duplication of multiple experiments
- Duplicate across projects

## Notes

- The duplicate experiment acts as a completely new experiment
- Users can rename duplicates using the existing "Rename" feature
- Duplicates are independent - changes don't affect the original
- Project's `last_modified` timestamp is updated when duplicating
- Database uses standard SQLite transactions for data consistency










