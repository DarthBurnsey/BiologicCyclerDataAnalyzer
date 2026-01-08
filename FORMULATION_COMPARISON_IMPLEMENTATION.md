# Formulation-Based Comparison Feature Implementation

## Overview
This document describes the implementation of a comprehensive formulation-based comparison system for the CellScope battery database application. This feature allows users to compare experiments based on their formulation components (e.g., graphite percentage, additives) and analyze how formulation changes affect cell performance.

## Database Structure

### New Database Functions (`database.py`)

1. **`get_experiments_by_formulation_component(project_id, component_name, min_percentage=None, max_percentage=None)`**
   - Queries experiments containing a specific formulation component
   - Supports filtering by percentage range
   - Returns experiment data tuples matching the criteria

2. **`get_formulation_summary(project_id)`**
   - Analyzes all formulations in a project
   - Returns statistics for each component (min, max, average, count)
   - Helps identify available components for comparison

3. **`get_experiments_grouped_by_formulation(project_id, component_name)`**
   - Groups experiments by component percentage
   - Useful for batch analysis and visualization

## Formulation Analysis Module (`formulation_analysis.py`)

### Key Functions

1. **`extract_formulation_component(formulation_json, component_name)`**
   - Extracts percentage of a specific component from formulation JSON
   - Handles multiple JSON key variations for legacy compatibility

2. **`extract_all_formulation_components(formulation_json)`**
   - Extracts all components and their percentages
   - Returns dictionary mapping component names to percentages

3. **`compare_formulations(formulation1_json, formulation2_json)`**
   - Compares two formulations
   - Identifies common components, unique components, and differences

4. **`create_formulation_comparison_dataframe(experiments_data, component_name)`**
   - Creates a comprehensive DataFrame for comparison
   - Extracts performance metrics (capacity, efficiency, cycle life, etc.)
   - Handles both multi-cell and single-cell experiments

5. **`group_experiments_by_formulation_range(experiments_data, component_name, range_size=5.0)`**
   - Groups experiments into percentage ranges
   - Useful for statistical analysis and visualization

## User Interface (`app.py` - Comparison Tab)

### Formulation-Based Comparison Section

The new section is integrated into the existing Comparison tab and includes:

#### 1. Component Selection
- Dropdown to select formulation component (e.g., "Graphite")
- Displays component statistics (min, max, average, count)
- Only shows components that exist in the project

#### 2. Filtering Options
- Minimum and maximum percentage filters
- Allows focusing on specific formulation ranges
- Real-time filtering of experiments

#### 3. Performance Visualization
- **Scatter Plot**: Performance metric vs. component percentage
  - Selectable metrics: Reversible Capacity, First Discharge, First Efficiency, Cycle Life, Porosity
  - Trend line with equation
  - Color-coded by component percentage
  - Downloadable as PNG

#### 4. Detailed Comparison Table
- Comprehensive table with all metrics
- Sortable by component percentage
- Includes: Experiment name, Component %, Performance metrics, Loading, Active Material, Porosity, Date
- Exportable as CSV

#### 5. Grouped Analysis
- Experiments grouped by percentage ranges (5% increments)
- Expandable sections for each range
- Quick overview of experiments in each range

## Usage Example

### Comparing Graphite Percentage Effects

1. Navigate to the **Comparison** tab
2. Scroll to the **Formulation-Based Comparison** section
3. Select "Graphite" from the component dropdown
4. Optionally set filters (e.g., 85-95% graphite)
5. Select a performance metric (e.g., "Reversible Capacity")
6. View the scatter plot showing capacity vs. graphite percentage
7. Review the detailed comparison table
8. Export data or plots as needed

### Use Cases

- **Formulation Optimization**: Identify optimal component percentages for best performance
- **Trend Analysis**: Understand how formulation changes affect specific metrics
- **Batch Comparison**: Compare multiple experiments with similar formulations
- **Quality Control**: Identify outliers or unexpected results

## Database Schema

The implementation uses the existing database schema:
- `cell_experiments.formulation_json`: Stores formulation data as JSON
- `cell_experiments.data_json`: Stores experiment data including cell-level formulations
- Formulation format: `[{"Component": "Graphite", "Dry Mass Fraction (%)": 90.0}, ...]`

## Performance Considerations

- Efficient JSON parsing with error handling
- Caching of formulation summaries
- Optimized database queries with proper indexing
- Handles both legacy and new data formats

## Future Enhancements

Potential improvements:
1. Multi-component analysis (e.g., graphite + binder combinations)
2. Statistical analysis (correlation coefficients, significance testing)
3. Formulation similarity scoring
4. Automated formulation recommendations
5. Integration with DOE (Design of Experiments) tools

## Deployment

The feature is ready for deployment with the existing Streamlit application:

1. **Local Deployment**: Run `streamlit run app.py`
2. **Streamlit Cloud**: Push to repository and deploy via Streamlit Cloud
3. **Docker**: Use existing Docker setup (if available)
4. **Server**: Deploy on any server with Python and Streamlit installed

### Requirements
- All dependencies are in `requirements.txt`
- No additional packages required
- Compatible with existing database structure

## Testing

To test the feature:
1. Ensure you have experiments with formulation data
2. Navigate to Comparison tab
3. Verify component dropdown shows available components
4. Test filtering and visualization
5. Export data to verify CSV/PNG generation

## Notes

- The feature gracefully handles missing data
- Supports both single-cell and multi-cell experiments
- Compatible with legacy data formats
- All error cases are handled with user-friendly messages





