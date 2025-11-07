# Fix for Duplicate Experiment Save Issue

## Problem
When uploading CSV/XLSX files to a duplicated experiment and clicking "Update Experiment", the newly uploaded cell data was not being saved. The experiment would remain empty even after successful uploads.

## Root Cause
The update experiment logic (lines 1577-1677) only processed cells that already existed in the `experiment_data['cells']` array:

```python
for i, dataset in enumerate(datasets):
    if i < len(experiment_data.get('cells', [])):
        # Process existing cell
```

For a duplicated experiment:
- `experiment_data['cells']` is an empty list (length 0)
- The condition `if i < 0` is never true
- Newly uploaded files are never processed
- `updated_cells_data` remains empty
- The update saves an empty cell list

## Solution

### Changes Made in `app.py`:

#### 1. Added Project Type Lookup (lines 1577-1582)
Moved project type determination outside the loop so it's available for both existing and new cells:

```python
# Get project type for efficiency calculation
project_type = "Full Cell"  # Default
if project_id:
    project_info = get_project_by_id(project_id)
    if project_info:
        project_type = project_info[3]
```

#### 2. Enhanced Update Logic (lines 1588-1730)
Added an `else` clause to handle new cells being added to experiments with no existing cells:

```python
for i, dataset in enumerate(datasets):
    if i < len(existing_cells):
        # Update existing cell (existing code)
        ...
    else:
        # NEW: Process new cell being added (e.g., uploading to duplicate)
        cell_name = dataset['testnum'] if dataset['testnum'] else f'Cell {i+1}'
        file_name = dataset['file'].name if dataset.get('file') else f'cell_{i+1}.csv'
        
        try:
            # Process the data to get DataFrame
            temp_dfs = load_and_preprocess_data([dataset], project_type)
            if temp_dfs and len(temp_dfs) > 0:
                df = temp_dfs[0]['df']
                
                new_cell = {
                    'cell_name': cell_name,
                    'file_name': file_name,
                    'loading': dataset['loading'],
                    'active_material': dataset['active'],
                    'formation_cycles': dataset['formation_cycles'],
                    'test_number': dataset['testnum'],
                    'electrolyte': dataset.get('electrolyte', '1M LiPF6 1:1:1'),
                    'substrate': dataset.get('substrate', 'Copper'),
                    'separator': dataset.get('separator', '25um PP'),
                    'formulation': dataset.get('formulation', []),
                    'data_json': df.to_json(),
                    'excluded': dataset.get('excluded', False)
                }
                
                # Calculate porosity if available
                if (pressed_thickness and pressed_thickness > 0 and 
                    dataset.get('formulation') and 
                    disc_diameter_input):
                    try:
                        from porosity_calculations import calculate_porosity_from_experiment_data
                        porosity_data = calculate_porosity_from_experiment_data(
                            disc_mass_mg=dataset['loading'],
                            disc_diameter_mm=disc_diameter_input,
                            pressed_thickness_um=pressed_thickness,
                            formulation=dataset['formulation']
                        )
                        new_cell['porosity'] = porosity_data['porosity']
                        st.info(f"   🔬 Calculated porosity for {cell_name}: {porosity_data['porosity']*100:.1f}%")
                    except Exception as e:
                        st.warning(f"   ⚠️ Could not calculate porosity for {cell_name}: {str(e)}")
                
                updated_cells_data.append(new_cell)
                st.info(f"✅ Processed new cell: {cell_name}")
        except Exception as e:
            st.error(f"❌ Error processing {cell_name}: {str(e)}")
            continue
```

## Behavior Now

### When Uploading to a Duplicated Experiment:

1. **Before**: Duplicate experiment "T23 (1)" has no cells
2. **Upload**: User uploads 2 CSV files
3. **Fill Data**: User enters loading, active material, etc. (defaults pre-filled)
4. **Click**: "💾 Update Experiment"
5. **Processing**:
   - ✅ Files are parsed with `load_and_preprocess_data()`
   - ✅ DataFrames are created with gravimetric capacities
   - ✅ Cell metadata is stored (loading, active, electrolyte, etc.)
   - ✅ Porosity is calculated if applicable
   - ✅ Data is saved to database
   - ✅ Success message: "✅ Processed new cell: Cell 1"
6. **Result**: Experiment now has 2 cells with full data

### When Updating an Existing Experiment:

The original update logic still works correctly:
- Existing cells are updated (existing path)
- Parameters can be modified
- Gravimetric capacities are recalculated if loading/active changes
- Porosity is recalculated if loading changes

### Mixed Scenario (Advanced):

If you have an experiment with 2 cells and upload a 3rd file:
- Cells 1-2: Updated using existing logic
- Cell 3: Added using new logic
- All 3 cells are saved correctly

## Testing

### Manual Test Workflow:

1. **Setup**:
   - Create an experiment with data (e.g., "T23")
   - Duplicate it to create "T23 (1)"

2. **Upload to Duplicate**:
   - Click on "T23 (1)"
   - See: "📝 Setting up experiment: **T23 (1)** (ready for data upload)"
   - Upload 2 CSV files
   - Fill in loading, active material (should have defaults)
   - Click "💾 Update Experiment"

3. **Verify**:
   - ✅ See: "✅ Processed new cell: Cell 1"
   - ✅ See: "✅ Processed new cell: Cell 2"
   - ✅ No errors appear
   - ✅ Page reloads automatically

4. **Check Data**:
   - Go to Summary tab
   - ✅ See 2 cells with data
   - ✅ Capacities are calculated
   - ✅ Efficiency values are present

5. **Check Plots**:
   - Go to Plots tab
   - ✅ See capacity vs cycle plots
   - ✅ Data looks correct

6. **Verify Original**:
   - Click on original "T23"
   - ✅ Original data is unchanged
   - ✅ Duplicate is independent

## Edge Cases Handled

✅ **Empty duplicate** - New cells are processed correctly
✅ **Existing experiment** - Updates work as before  
✅ **Mixed update** - Can add new cells to existing experiment
✅ **Error handling** - Failed uploads show appropriate messages
✅ **Porosity calculation** - Works for new cells when data is available
✅ **Project type** - Efficiency calculated correctly based on project type

## Files Modified

- `app.py` - Lines 1577-1730 (~60 lines added/modified)

## Related Issues

- Original duplicate feature: `DUPLICATE_FEATURE_DOCUMENTATION.md`
- Upload interface fix: `DUPLICATE_UPLOAD_FIX.md`
- Default values fix: `DUPLICATE_DEFAULT_VALUES_FIX.md`
- **This completes the duplicate experiment feature** ✅

## Summary

The duplicate experiment feature now works end-to-end:
1. ✅ Duplicate creates empty experiment with metadata
2. ✅ Default values are pre-populated from original
3. ✅ Upload interface appears correctly
4. ✅ **Data saves successfully** (this fix)
5. ✅ Experiment functions normally after save

The feature is now fully functional! 🎉





