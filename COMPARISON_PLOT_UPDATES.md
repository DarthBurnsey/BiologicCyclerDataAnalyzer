# Comparison Plot Average Line Filtering - Implementation Summary

## Overview
Updated the Comparison Page to include filtering controls for average plot lines with enhanced user control and a "Show Averages" mode.

## Changes Made

### 1. UI Components (`ui_components.py`)
**Location:** `render_comparison_plot_options()` function (lines 876-925)

**Added:**
- Individual filter toggles for each average line:
  - ✅ Average Q Dis
  - ✅ Average Q Chg  
  - ✅ Average Efficiency

**Behavior:**
- When "Show Averages" checkbox is enabled, a new section appears with three toggle controls
- Updated help text to indicate that individual cell traces are hidden when averages are shown
- Added informational message explaining the filtering behavior
- Each toggle can be independently controlled without affecting others

### 2. Plotting Function (`plotting.py`)
**Location:** `plot_comparison_capacity_graph()` function (lines 624-673)

**Modified:**
- Wrapped individual cell plotting in a conditional: `if not show_average_performance:`
- When "Show Averages" is enabled, individual cell traces are automatically hidden
- Only average lines are plotted based on the toggle states
- Existing `avg_line_toggles` dictionary controls which average lines appear

## Feature Specifications

### Individual Filter Toggles
- **Average Q Dis** (📊): Controls discharge capacity average line
- **Average Q Chg** (⚡): Controls charge capacity average line
- **Average Efficiency** (🎯): Controls efficiency average line
- All toggles default to `True` (shown) when "Show Averages" is enabled
- Users can show/hide each line independently

### "Show Averages" Mode
When the "Show Averages" checkbox is enabled:
1. **Hides all individual cell traces** automatically
2. **Shows only average plot lines** (those toggled on)
3. **Filter selections still apply** - users can toggle individual averages on/off
4. Example: If only "Average Q Dis" is toggled on, only that line shows

### Default Behavior
When "Show Averages" is NOT enabled:
- Individual cell traces remain visible (based on user selection)
- Average lines can still be toggled on/off if desired
- Both individual and average lines can coexist on the same plot

## Technical Implementation Details

### Integration
- ✅ Clean integration with existing matplotlib plotting mechanisms
- ✅ Uses existing `avg_line_toggles` dictionary structure
- ✅ No changes required to function signatures or return values
- ✅ Backward compatible with existing code

### Styling
- Average lines maintain consistent styling:
  - **Color:** Matches experiment color scheme
  - **Line width:** 3 (thicker than individual traces)
  - **Markers:** Diamond style when markers are enabled
  - **Line styles:** Solid for Q Dis, dashed for Q Chg, dotted for Efficiency

### Legend Behavior
- Legend dynamically updates based on visible lines
- Only shows entries for plotted data
- Positioned at upper right with bbox adjustment for clarity

### Immediate Effect
- All toggles use Streamlit's reactive framework
- Changes apply immediately without manual refresh
- Session state properly managed via unique keys

## User Experience

### Workflow Example 1: Compare Only Averages
1. Enable "Show Averages" checkbox
2. All individual cell traces disappear
3. Three toggle controls appear
4. Toggle on desired averages (e.g., only Q Dis)
5. Plot shows only selected average lines

### Workflow Example 2: Mixed View
1. Leave "Show Averages" disabled
2. Select specific individual cells to compare
3. Average filter toggles are not shown
4. Plot shows selected individual traces

### Workflow Example 3: Single Metric Focus
1. Enable "Show Averages"
2. Disable "Average Q Chg" and "Average Efficiency"
3. Keep only "Average Q Dis" enabled
4. Clean plot showing just discharge capacity averages across experiments

## Testing Recommendations

1. **Test with single experiment:**
   - Verify averages calculate correctly
   - Confirm individual traces hide when "Show Averages" is on

2. **Test with multiple experiments:**
   - Verify each experiment gets correct color
   - Confirm all experiments' averages can be independently filtered

3. **Test edge cases:**
   - Single cell experiments (averages should not appear)
   - Missing data in some cycles
   - All toggles off (plot should be empty except axes)

4. **Test interaction with other controls:**
   - Cycle filtering
   - Remove last cycle option
   - Remove markers option
   - Hide legend option

## Files Modified

1. `ui_components.py` - Added average line filter controls UI
2. `plotting.py` - Updated plotting logic to hide individual traces when showing averages

## No Breaking Changes
- All existing functionality preserved
- Default behavior unchanged for users not using new features
- Backward compatible with existing saved preferences




