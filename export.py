# export.py
from typing import List, Dict, Any, Tuple, Optional
import io
import json
import logging
import tempfile
import os
import traceback
from openpyxl import load_workbook
from openpyxl.chart import LineChart, Reference
import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np

# Set up comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def safe_cycle_life_calculation(df_cell: pd.DataFrame, formation_cycles: int = 4) -> Optional[int]:
    """
    Calculate cycle life using the same logic as the main application.
    Returns the cycle number where capacity drops below 80% of initial capacity.
    """
    try:
        logger.debug(f"Calculating cycle life for cell with {len(df_cell)} cycles, formation_cycles={formation_cycles}")
        
        # Get discharge capacity series, excluding formation cycles
        if len(df_cell) <= formation_cycles:
            logger.warning(f"Not enough cycles for cycle life calculation: {len(df_cell)} <= {formation_cycles}")
            return None
            
        # Get the first cycle after formation as reference
        post_formation_data = df_cell.iloc[formation_cycles:]
        if post_formation_data.empty:
            logger.warning("No post-formation data available")
            return None
            
        # Get discharge capacity data
        qdis_col = 'Q Dis (mAh/g)'
        if qdis_col not in df_cell.columns:
            logger.warning(f"Discharge capacity column '{qdis_col}' not found in data")
            return None
            
        qdis_data = pd.to_numeric(post_formation_data[qdis_col], errors='coerce')
        qdis_data = qdis_data.dropna()
        
        if qdis_data.empty:
            logger.warning("No valid discharge capacity data found")
            return None
            
        # Use the first post-formation cycle as reference
        initial_capacity = qdis_data.iloc[0]
        if initial_capacity <= 0:
            logger.warning(f"Invalid initial capacity: {initial_capacity}")
            return None
            
        threshold = 0.8 * initial_capacity
        logger.debug(f"Initial capacity: {initial_capacity}, threshold: {threshold}")
        
        # Find first cycle below threshold
        below_threshold = qdis_data < threshold
        if below_threshold.any():
            first_below_idx = below_threshold.idxmax()
            # Get the actual cycle number from the original dataframe
            cycle_number = df_cell.iloc[first_below_idx][df_cell.columns[0]]
            logger.info(f"Cycle life calculated: {int(cycle_number)} cycles")
            return int(cycle_number)
        else:
            # If no cycle below threshold, return the last cycle
            last_cycle = df_cell.iloc[-1][df_cell.columns[0]]
            logger.info(f"No cycle below threshold, using last cycle: {int(last_cycle)}")
            return int(last_cycle)
            
    except Exception as e:
        logger.error(f"Error calculating cycle life: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def get_cell_metrics(df_cell: pd.DataFrame, formation_cycles: int = 4) -> Dict[str, Any]:
    """
    Calculate all cell metrics using the same logic as the main application.
    """
    metrics = {}
    
    try:
        logger.debug(f"Calculating metrics for cell with {len(df_cell)} cycles")
        
        # 1st Cycle Discharge Capacity (max of first 3 cycles)
        first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
        max_qdis = max(first_three_qdis) if first_three_qdis else None
        metrics['max_qdis'] = max_qdis
        metrics['qdis_str'] = f"{max_qdis:.1f}" if isinstance(max_qdis, (int, float)) else "N/A"
        
        # First Cycle Efficiency
        if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
            first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
            try:
                eff_pct = float(first_cycle_eff) * 100
                metrics['eff_pct'] = eff_pct
                metrics['eff_str'] = f"{eff_pct:.1f}%"
            except (ValueError, TypeError):
                metrics['eff_pct'] = None
                metrics['eff_str'] = "N/A"
        else:
            metrics['eff_pct'] = None
            metrics['eff_str'] = "N/A"
        
        # Cycle Life (80%)
        cycle_life = safe_cycle_life_calculation(df_cell, formation_cycles)
        metrics['cycle_life'] = cycle_life
        metrics['cycle_life_str'] = f"{cycle_life}" if cycle_life is not None else "N/A"
        
        # Reversible Capacity (first cycle after formation)
        if len(df_cell) > formation_cycles:
            reversible_capacity = df_cell['Q Dis (mAh/g)'].iloc[formation_cycles]
            metrics['reversible_capacity'] = reversible_capacity
            metrics['reversible_str'] = f"{reversible_capacity:.1f}" if isinstance(reversible_capacity, (int, float)) else "N/A"
        else:
            metrics['reversible_capacity'] = None
            metrics['reversible_str'] = "N/A"
        
        # Coulombic Efficiency (average of post-formation cycles)
        eff_col = 'Efficiency (-)'
        qdis_col = 'Q Dis (mAh/g)'
        n_cycles = len(df_cell)
        
        if eff_col in df_cell.columns and qdis_col in df_cell.columns and n_cycles > formation_cycles + 1:
            try:
                # Calculate average efficiency for post-formation cycles
                post_formation_eff = []
                prev_qdis = df_cell[qdis_col].iloc[formation_cycles]
                prev_eff = df_cell[eff_col].iloc[formation_cycles]
                
                for i in range(formation_cycles + 1, n_cycles):
                    try:
                        curr_qdis = df_cell[qdis_col].iloc[i]
                        curr_eff = df_cell[eff_col].iloc[i]
                        
                        if curr_qdis > 0 and prev_qdis > 0:
                            efficiency = (curr_qdis / prev_qdis) * 100
                            post_formation_eff.append(efficiency)
                        
                        prev_qdis = curr_qdis
                        prev_eff = curr_eff
                    except (IndexError, ValueError):
                        continue
                
                if post_formation_eff:
                    avg_eff = np.mean(post_formation_eff)
                    metrics['coulombic_eff'] = avg_eff
                    metrics['coulombic_str'] = f"{avg_eff:.1f}%"
                else:
                    metrics['coulombic_eff'] = None
                    metrics['coulombic_str'] = "N/A"
            except Exception as e:
                logger.warning(f"Error calculating coulombic efficiency: {e}")
                metrics['coulombic_eff'] = None
                metrics['coulombic_str'] = "N/A"
        else:
            metrics['coulombic_eff'] = None
            metrics['coulombic_str'] = "N/A"
        
        logger.debug(f"Metrics calculated successfully: {metrics}")
        return metrics
        
    except Exception as e:
        logger.error(f"Error calculating cell metrics: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Return safe defaults
        return {
            'max_qdis': None, 'qdis_str': "N/A",
            'eff_pct': None, 'eff_str': "N/A",
            'cycle_life': None, 'cycle_life_str': "N/A",
            'reversible_capacity': None, 'reversible_str': "N/A",
            'coulombic_eff': None, 'coulombic_str': "N/A"
        }

def create_main_plot_from_session_state(
    dfs: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    show_efficiency_lines: Dict[str, bool],
    remove_last_cycle: bool,
    show_graph_title: bool,
    experiment_name: str,
    show_average_performance: bool,
    avg_line_toggles: Dict[str, bool],
    remove_markers: bool,
    hide_legend: bool
) -> Figure:
    """
    Create the main capacity plot using the exact same logic as the Plots tab.
    """
    try:
        logger.info("Creating main capacity plot from session state...")
        logger.debug(f"Plot parameters: show_lines={show_lines}, remove_last_cycle={remove_last_cycle}, show_graph_title={show_graph_title}")
        
        # Import the plotting function from plotting.py
        from plotting import plot_capacity_graph
        
        # Create the plot using the same function as the Plots tab
        fig = plot_capacity_graph(
            dfs, show_lines, show_efficiency_lines, remove_last_cycle,
            show_graph_title, experiment_name, show_average_performance,
            avg_line_toggles, remove_markers, hide_legend
        )
        
        logger.info("Main capacity plot created successfully")
        return fig
        
    except Exception as e:
        logger.error(f"Error creating main capacity plot: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Fallback: create a simple error plot
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, 'Main plot generation failed', ha='center', va='center', transform=ax.transAxes)
        ax.set_xlabel('Cycle')
        ax.set_ylabel('Capacity (mAh/g)')
        ax.set_title('Capacity Plot (Error)')
        return fig

def create_retention_plot_from_session_state(
    dfs: List[Dict[str, Any]],
    show_lines: Dict[str, bool],
    reference_cycle: int,
    formation_cycles: int,
    remove_last_cycle: bool,
    show_title: bool,
    experiment_name: str,
    retention_threshold: float,
    y_axis_min: float,
    y_axis_max: float,
    show_baseline_line: bool,
    show_threshold_line: bool,
    remove_markers: bool,
    hide_legend: bool
) -> Figure:
    """
    Create the capacity retention plot using the exact same logic as the Plots tab.
    """
    try:
        logger.info("Creating capacity retention plot from session state...")
        logger.debug(f"Retention plot parameters: reference_cycle={reference_cycle}, retention_threshold={retention_threshold}, y_axis_min={y_axis_min}, y_axis_max={y_axis_max}")
        
        # Validate input data
        if not dfs:
            logger.error("No dataframes provided for retention plot")
            raise ValueError("No dataframes provided for retention plot")
        
        # Check if reference cycle exists in data
        for i, d in enumerate(dfs):
            df = d['df']
            if reference_cycle not in df[df.columns[0]].values:
                logger.warning(f"Reference cycle {reference_cycle} not found in cell {i+1}")
        
        # Import the plotting function from plotting.py
        from plotting import plot_capacity_retention_graph
        
        # Create the plot using the same function as the Plots tab
        fig = plot_capacity_retention_graph(
            dfs, show_lines, reference_cycle, formation_cycles, remove_last_cycle,
            show_title, experiment_name, False, {}, remove_markers, hide_legend,
            None, None, None, None, retention_threshold, y_axis_min, y_axis_max,
            show_baseline_line, show_threshold_line
        )
        
        logger.info("Capacity retention plot created successfully")
        return fig
        
    except Exception as e:
        logger.error(f"Error creating capacity retention plot: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Fallback: create a simple error plot
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, 'Retention plot generation failed', ha='center', va='center', transform=ax.transAxes)
        ax.set_xlabel('Cycle')
        ax.set_ylabel('Capacity Retention (%)')
        ax.set_title('Capacity Retention Plot (Error)')
        return fig

def save_figure_to_temp_file(fig: Figure, dpi: int = 300) -> str:
    """
    Save a matplotlib figure to a temporary file and return the path.
    Handles cleanup and error logging.
    """
    temp_file = None
    try:
        logger.debug("Saving figure to temporary file...")
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        temp_path = temp_file.name
        temp_file.close()
        
        # Save figure with high quality settings
        fig.savefig(temp_path, format='png', bbox_inches='tight', dpi=dpi, 
                   facecolor='white', edgecolor='none', pad_inches=0.1)
        
        # Explicitly close all matplotlib resources to prevent memory issues
        plt.close(fig)
        plt.close('all')  # Close any remaining figures
        
        # Verify file was created and has content
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            logger.info(f"Figure saved successfully to: {temp_path} ({os.path.getsize(temp_path)} bytes)")
            return temp_path
        else:
            raise ValueError("Figure file was not created or is empty")
        
    except Exception as e:
        logger.error(f"Error saving figure to temp file: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if temp_file:
            temp_file.close()
        raise

def add_picture_to_slide_safely(slide, image_path: str, left: float, top: float, width: float, height: float) -> bool:
    """
    Safely add a picture to a slide with comprehensive error handling.
    """
    try:
        logger.debug(f"Adding image to slide: {image_path}")
        
        # Validate file exists and has content
        if not os.path.exists(image_path):
            logger.error(f"Image file does not exist: {image_path}")
            return False
        
        file_size = os.path.getsize(image_path)
        if file_size == 0:
            logger.error(f"Image file is empty: {image_path}")
            return False
        
        logger.debug(f"Image file size: {file_size} bytes")
        
        # Add picture to slide
        slide.shapes.add_picture(image_path, Inches(left), Inches(top), width=Inches(width), height=Inches(height))
        logger.info(f"Successfully added image to slide: {image_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding image to slide: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def cleanup_temp_files(temp_files: List[str]):
    """
    Clean up temporary files with error handling.
    """
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
                logger.debug(f"Cleaned up temp file: {temp_file}")
        except Exception as e:
            logger.error(f"Error cleaning up temp file {temp_file}: {e}")

def add_formatted_table_to_slide(slide, table_data, left, top, width, height, header_color=None, avg_row_color=None):
    """
    Add a formatted table to a slide with proper styling.
    """
    try:
        rows = len(table_data)
        cols = len(table_data[0]) if table_data else 0
        if rows == 0 or cols == 0:
            return None
        
        # Calculate dynamic height based on number of rows
        row_height = max(0.3, min(0.5, height / rows))
        table_height = max(height, row_height * rows)
        
        table_shape = slide.shapes.add_table(rows, cols, Inches(left), Inches(top), Inches(width), Inches(table_height))
        table = table_shape.table
        
        # Set column widths
        col_width = width / cols
        for col_idx in range(cols):
            table.columns[col_idx].width = Inches(col_width)
        
        # Populate table with data
        for i, row_data in enumerate(table_data):
            for j, cell_data in enumerate(row_data):
                if j < cols:  # Safety check
                    cell = table.cell(i, j)
                    cell.text = str(cell_data)
                    
                    # Set vertical alignment
                    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                    
                    # Format paragraphs
                    for para in cell.text_frame.paragraphs:
                        para.alignment = PP_ALIGN.CENTER
                        for run in para.runs:
                            run.font.size = Pt(11)
                            run.font.name = 'Calibri'
                    
                    # Header row styling
                    if i == 0:
                        cell.fill.solid()
                        header_color_rgb = header_color if header_color else RGBColor(68, 114, 196)
                        cell.fill.fore_color.rgb = header_color_rgb
                        for para in cell.text_frame.paragraphs:
                            for run in para.runs:
                                run.font.color.rgb = RGBColor(255, 255, 255)
                                run.font.bold = True
                                run.font.size = Pt(12)
                    
                    # Average row styling (if exists and avg_row_color provided)
                    elif avg_row_color and i == len(table_data) - 1 and "AVERAGE" in str(cell_data).upper():
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = avg_row_color
                        for para in cell.text_frame.paragraphs:
                            for run in para.runs:
                                run.font.bold = True
                                run.font.size = Pt(11)
        
        return table
    except Exception as e:
        logger.error(f"Error adding formatted table: {e}")
        return None

def add_formulation_table_to_slide(slide, formulation_data, left, top, width, height):
    """
    Add a formulation component table to a slide.
    Handles multiple key variations for legacy data compatibility.
    """
    try:
        if not formulation_data or len(formulation_data) == 0:
            logger.warning("No formulation data provided")
            return None
        
        # Prepare table data
        table_data = [["Component", "Dry Mass Fraction (%)"]]
        
        for item in formulation_data:
            if not isinstance(item, dict):
                logger.warning(f"Skipping non-dict item in formulation data: {item}")
                continue
            
            # Try multiple key variations for component (handle legacy data)
            component = (item.get('Component') or 
                        item.get('component') or 
                        item.get('Component Name') or
                        item.get('component_name') or
                        '')
            
            # Try multiple key variations for dry mass fraction (handle legacy data)
            dry_mass_fraction = (item.get('Dry Mass Fraction (%)') or
                                item.get('dry_mass_fraction') or
                                item.get('Value') or
                                item.get('value') or
                                item.get('Dry Mass Fraction') or
                                item.get('dry_mass_fraction_pct') or
                                None)
            
            # Handle None, empty string, or invalid values
            if dry_mass_fraction is None or dry_mass_fraction == '':
                dry_mass_fraction_str = 'N/A'
            elif isinstance(dry_mass_fraction, (int, float)):
                # Ensure it's a valid number
                if dry_mass_fraction < 0 or dry_mass_fraction > 100:
                    logger.warning(f"Invalid dry mass fraction value: {dry_mass_fraction}, using as-is")
                dry_mass_fraction_str = f"{dry_mass_fraction:.1f}"
            elif isinstance(dry_mass_fraction, str):
                # Try to parse string values (e.g., "50.0", "50.0%", "None")
                dry_mass_fraction_clean = dry_mass_fraction.strip().rstrip('%')
                if dry_mass_fraction_clean.lower() in ('none', 'null', '', 'n/a'):
                    dry_mass_fraction_str = 'N/A'
                else:
                    try:
                        # Try to convert to float and format
                        fraction_float = float(dry_mass_fraction_clean)
                        dry_mass_fraction_str = f"{fraction_float:.1f}"
                    except (ValueError, TypeError):
                        # If conversion fails, use the string as-is
                        logger.warning(f"Could not convert dry mass fraction '{dry_mass_fraction}' to number, using as string")
                        dry_mass_fraction_str = dry_mass_fraction_clean
            else:
                # Fallback for any other type
                dry_mass_fraction_str = str(dry_mass_fraction) if dry_mass_fraction else 'N/A'
            
            # Only add row if component is not empty
            if component:
                table_data.append([component, dry_mass_fraction_str])
                logger.debug(f"Added formulation row: {component} = {dry_mass_fraction_str}")
            else:
                logger.warning(f"Skipping row with empty component: {item}")
        
        if len(table_data) <= 1:
            logger.warning("No valid formulation components found after processing")
            return None
        
        # Calculate table height
        rows = len(table_data)
        row_height = 0.4
        table_height = max(height, row_height * rows)
        
        # Add table
        table = add_formatted_table_to_slide(
            slide, table_data, left, top, width, table_height,
            header_color=RGBColor(68, 114, 196)
        )
        
        logger.info(f"Formulation table added with {rows} rows (including header)")
        return table
        
    except Exception as e:
        logger.error(f"Error adding formulation table: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def validate_powerpoint_structure(prs: Presentation) -> bool:
    """
    Validate that the PowerPoint presentation has the expected structure.
    """
    try:
        if not prs.slides:
            logger.error("PowerPoint has no slides")
            return False
        
        slide = prs.slides[0]
        if not slide.shapes:
            logger.error("PowerPoint slide has no shapes")
            return False
        
        logger.info(f"PowerPoint validation passed: {len(prs.slides)} slides, {len(slide.shapes)} shapes")
        return True
        
    except Exception as e:
        logger.error(f"Error validating PowerPoint structure: {e}")
        return False

def export_powerpoint(
    dfs: List[Dict[str, Any]], 
    show_averages: bool, 
    experiment_name: str, 
    show_lines: Dict[str, bool], 
    show_efficiency_lines: Dict[str, bool], 
    remove_last_cycle: bool,
    # Advanced slide content control
    include_summary_table: bool = True,
    include_main_plot: bool = True,
    include_retention_plot: bool = True,
    include_notes: bool = False,
    include_electrode_data: bool = False,
    include_porosity: bool = False,  # Shows single experiment-level porosity value
    include_thickness: bool = False,  # Shows single experiment-level thickness value
    include_solids_content: bool = False,  # Shows single experiment-level solids content value
    include_formulation: bool = False,  # Shows formulation component table
    experiment_notes: str = "",
    # Parameters for retention plot
    retention_threshold: float = 80.0,
    reference_cycle: int = 5,
    formation_cycles: int = 4,
    retention_show_lines: Dict[str, bool] = None,
    retention_remove_markers: bool = False,
    retention_hide_legend: bool = False,
    retention_show_title: bool = True,
    show_baseline_line: bool = True,
    show_threshold_line: bool = True,
    y_axis_min: float = 0.0,
    y_axis_max: float = 110.0,
    # Plot customization parameters (from session state)
    show_graph_title: bool = True,
    show_average_performance: bool = False,
    avg_line_toggles: Dict[str, bool] = None,
    remove_markers: bool = False,
    hide_legend: bool = False
) -> Tuple[io.BytesIO, str]:
    """
    Enhanced PowerPoint export with comprehensive error handling, logging, and session state consistency.
    
    Note: Electrode data (porosity, thickness, and solids content) are displayed as single experiment-level values
    since all cells in an experiment are typically duplicates from the same electrode batch.
    """
    temp_files = []
    
    try:
        logger.info("=== Starting PowerPoint Export ===")
        logger.info(f"Export parameters: include_main_plot={include_main_plot}, include_retention_plot={include_retention_plot}")
        logger.info(f"Data: {len(dfs)} dataframes, formation_cycles={formation_cycles}")
        logger.info(f"Show lines: {show_lines}")
        logger.info(f"Show efficiency lines: {show_efficiency_lines}")
        logger.info(f"Retention parameters: threshold={retention_threshold}, reference_cycle={reference_cycle}, y_axis=({y_axis_min}, {y_axis_max})")
        
        # Validate input data
        if not dfs:
            raise ValueError("No dataframes provided for export")
        
        # Set defaults
        if retention_show_lines is None:
            retention_show_lines = show_lines
        if avg_line_toggles is None:
            avg_line_toggles = {}
        
        # Create presentation
        logger.info("Creating PowerPoint presentation...")
        prs = Presentation()
        
        # Determine slide title
        if len(dfs) == 1:
            testnum = dfs[0].get('testnum', 'Cell 1') or 'Cell 1'
            if experiment_name:
                slide_title = f"{experiment_name} - {testnum} Summary"
            else:
                slide_title = f"{testnum} Summary"
        else:
            if experiment_name:
                slide_title = f"{experiment_name} - Cell Comparison Summary"
            else:
                slide_title = "Cell Comparison Summary"
        
        # Count content items to determine if we need multiple slides
        content_items_count = 0
        if include_summary_table:
            content_items_count += 1
        if include_notes and experiment_notes.strip():
            content_items_count += 1
        if include_electrode_data and (include_porosity or include_thickness or include_solids_content):
            content_items_count += 1
        if include_formulation:
            content_items_count += 1
        if include_main_plot:
            content_items_count += 1
        if include_retention_plot:
            content_items_count += 1
        
        # Determine if we need a second slide (split if charts, formulation, or content overflow)
        # Always create second slide if main plot is included (moved to slide 2 for better visibility)
        need_second_slide = include_main_plot or include_retention_plot or include_formulation or content_items_count > 5
        
        # Create first slide - use blank layout (6) to avoid default placeholders
        slide1 = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
        
        # Manually add title textbox (no default placeholders)
        title_left, title_top, title_width, title_height = Inches(1), Inches(0.5), Inches(8), Inches(1)
        title_box = slide1.shapes.add_textbox(title_left, title_top, title_width, title_height)
        title_tf = title_box.text_frame
        title_tf.clear()
        title_p = title_tf.add_paragraph()
        title_p.text = slide_title
        title_p.font.size = Pt(24)
        title_p.font.bold = True
        title_p.alignment = PP_ALIGN.LEFT
        title_p.font.name = 'Calibri'
        
        # Initialize position tracking - start below title
        current_y = 1.5  # Start below title (no Echem header)
        left_margin = 1.0
        right_margin = 5.0
        content_width = 4.5
        slide_height_limit = 6.5  # Maximum Y position before needing new slide
        
        # Create second slide if needed - use blank layout (6) to avoid default placeholders
        slide2 = None
        if need_second_slide:
            slide2 = prs.slides.add_slide(prs.slide_layouts[6])
            # Manually add title to second slide (no default placeholders)
            title_box2 = slide2.shapes.add_textbox(title_left, title_top, title_width, title_height)
            title_tf2 = title_box2.text_frame
            title_tf2.clear()
            title_p2 = title_tf2.add_paragraph()
            title_p2.text = f"{slide_title} (Continued)"
            title_p2.font.size = Pt(24)
            title_p2.font.bold = True
            title_p2.alignment = PP_ALIGN.LEFT
            title_p2.font.name = 'Calibri'
        
        # Determine which slide to use for each section
        # Slide 1: Summary, Notes, Electrode Data
        # Slide 2: Formulation, Main Plot, Retention Plot (charts moved to slide 2 for better visibility)
        current_slide = slide1
        slide2_y = 1.5  # Start below title on slide 2 (no Echem header)
        
        # Add summary table/bullets to slide 1
        if include_summary_table:
            logger.info("Adding summary table...")
            if len(dfs) == 1:
                # Single cell - bullet points
                summary_box = slide1.shapes.add_textbox(Inches(left_margin), Inches(current_y), Inches(content_width), Inches(2.0))
                summary_tf = summary_box.text_frame
                summary_tf.clear()
                
                # Summary header
                header_p = summary_tf.add_paragraph()
                header_p.text = "Summary Metrics"
                header_p.font.size = Pt(16)
                header_p.font.bold = True
                header_p.font.name = 'Calibri'
                
                # Calculate metrics using the same logic as the app
                df_cell = dfs[0]['df']
                metrics = get_cell_metrics(df_cell, formation_cycles)
                
                # Add bullet points
                bullet_points = [
                    f"1st Cycle Discharge Capacity: {metrics['qdis_str']} mAh/g",
                    f"First Cycle Efficiency: {metrics['eff_str']}",
                    f"Cycle Life (80%): {metrics['cycle_life_str']}"
                ]
                
                for metric in bullet_points:
                    p = summary_tf.add_paragraph()
                    p.text = f"• {metric}"
                    p.font.size = Pt(14)
                    p.font.name = 'Calibri'
                    p.level = 1
                
                current_y += 2.2
                
            else:
                # Multiple cells - table format
                logger.info("Creating multi-cell summary table...")
                table_data = []
                headers = ["Cell", "1st Cycle Discharge Capacity (mAh/g)", "First Cycle Efficiency (%)", "Cycle Life (80%)", "Reversible Capacity (mAh/g)", "Coulombic Efficiency (%)"]
                table_data.append(headers)
                
                for i, d in enumerate(dfs):
                    df_cell = d['df']
                    cell_name = d.get('testnum', f'Cell {i+1}') or f'Cell {i+1}'
                    
                    # Calculate metrics using the same logic as the app
                    metrics = get_cell_metrics(df_cell, formation_cycles)
                    
                    table_data.append([
                        cell_name, 
                        metrics['qdis_str'], 
                        metrics['eff_str'], 
                        metrics['cycle_life_str'],
                        metrics['reversible_str'],
                        metrics['coulombic_str']
                    ])
                
                if show_averages and len(dfs) > 1:
                    # Calculate averages
                    avg_metrics = {
                        'max_qdis': [], 'eff_pct': [], 'cycle_life': [],
                        'reversible_capacity': [], 'coulombic_eff': []
                    }
                    
                    for d in dfs:
                        df_cell = d['df']
                        metrics = get_cell_metrics(df_cell, formation_cycles)
                        
                        if metrics['max_qdis'] is not None:
                            avg_metrics['max_qdis'].append(metrics['max_qdis'])
                        if metrics['eff_pct'] is not None:
                            avg_metrics['eff_pct'].append(metrics['eff_pct'])
                        if metrics['cycle_life'] is not None:
                            avg_metrics['cycle_life'].append(metrics['cycle_life'])
                        if metrics['reversible_capacity'] is not None:
                            avg_metrics['reversible_capacity'].append(metrics['reversible_capacity'])
                        if metrics['coulombic_eff'] is not None:
                            avg_metrics['coulombic_eff'].append(metrics['coulombic_eff'])
                    
                    # Calculate final averages
                    avg_row = ["AVERAGE"]
                    avg_row.append(f"{np.mean(avg_metrics['max_qdis']):.1f}" if avg_metrics['max_qdis'] else "N/A")
                    avg_row.append(f"{np.mean(avg_metrics['eff_pct']):.1f}%" if avg_metrics['eff_pct'] else "N/A")
                    avg_row.append(f"{np.mean(avg_metrics['cycle_life']):.0f}" if avg_metrics['cycle_life'] else "N/A")
                    avg_row.append(f"{np.mean(avg_metrics['reversible_capacity']):.1f}" if avg_metrics['reversible_capacity'] else "N/A")
                    avg_row.append(f"{np.mean(avg_metrics['coulombic_eff']):.1f}%" if avg_metrics['coulombic_eff'] else "N/A")
                    
                    table_data.append(avg_row)
                
                # Use helper function to create formatted table
                rows = len(table_data)
                table_height = 1.5 + 0.3 * rows
                add_formatted_table_to_slide(
                    slide1, table_data, left_margin, current_y, 8.5, table_height,
                    header_color=RGBColor(68, 114, 196),
                    avg_row_color=RGBColor(146, 208, 80) if show_averages and len(dfs) > 1 else None
                )
                
                current_y += table_height + 0.2
        
        # Add notes section to slide 1
        if include_notes and experiment_notes.strip():
            logger.info("Adding notes section...")
            notes_box = slide1.shapes.add_textbox(Inches(left_margin), Inches(current_y), Inches(content_width), Inches(1.5))
            notes_tf = notes_box.text_frame
            notes_tf.clear()
            notes_tf.word_wrap = True
            
            # Notes header
            header_p = notes_tf.add_paragraph()
            header_p.text = "Experiment Notes"
            header_p.font.size = Pt(16)
            header_p.font.bold = True
            header_p.font.name = 'Calibri'
            
            # Notes content
            notes_p = notes_tf.add_paragraph()
            notes_p.text = experiment_notes
            notes_p.font.size = Pt(12)
            notes_p.font.name = 'Calibri'
            
            current_y += 1.7
        
        # Add electrode data section to slide 1
        if include_electrode_data and (include_porosity or include_thickness or include_solids_content):
            logger.info("Adding electrode data section...")
            electrode_box = slide1.shapes.add_textbox(Inches(left_margin), Inches(current_y), Inches(content_width), Inches(1.5))
            electrode_tf = electrode_box.text_frame
            electrode_tf.clear()
            
            # Electrode data header
            header_p = electrode_tf.add_paragraph()
            header_p.text = "Electrode Data"
            header_p.font.size = Pt(16)
            header_p.font.bold = True
            header_p.font.name = 'Calibri'
            
            # Add electrode data points with experiment-level values
            electrode_data = []
            
            # Extract experiment-level porosity value
            if include_porosity and dfs:
                porosity = dfs[0].get('porosity', None)
                if porosity is None:
                    for key in ['Porosity', 'porosity_pct', 'porosity_percent']:
                        if key in dfs[0] and dfs[0][key] is not None:
                            porosity = dfs[0][key]
                            break
                if porosity is not None and porosity > 0:
                    porosity_pct = porosity * 100 if porosity <= 1.0 else porosity
                    electrode_data.append(f"• Porosity: {porosity_pct:.1f}%")
                else:
                    electrode_data.append("• Porosity: No data available")
            
            # Extract experiment-level pressed thickness value
            if include_thickness and dfs:
                thickness = dfs[0].get('pressed_thickness', None)
                if thickness is None:
                    for key in ['thickness', 'electrode_thickness', 'pressed_electrode_thickness']:
                        if key in dfs[0] and dfs[0][key] is not None:
                            thickness = dfs[0][key]
                            break
                if thickness is not None and thickness > 0:
                    electrode_data.append(f"• Pressed Electrode Thickness: {thickness:.1f} μm")
                else:
                    electrode_data.append("• Pressed Electrode Thickness: No data available")
            
            # Extract experiment-level solids content value
            if include_solids_content and dfs:
                solids_content = dfs[0].get('solids_content', None)
                if solids_content is None:
                    for key in ['solids', 'solid_content', 'solids_percent']:
                        if key in dfs[0] and dfs[0][key] is not None:
                            solids_content = dfs[0][key]
                            break
                if solids_content is not None and solids_content >= 0:
                    electrode_data.append(f"• Solids Content: {solids_content:.1f}%")
                else:
                    electrode_data.append("• Solids Content: No data available")
            
            # Add the electrode data points to the text frame
            for data_point in electrode_data:
                p = electrode_tf.add_paragraph()
                p.text = data_point
                p.font.size = Pt(12)
                p.font.name = 'Calibri'
                p.level = 1
            
            current_y += 1.7
        
        # Add formulation table (to slide 2 if exists, otherwise slide 1)
        if include_formulation:
            logger.info("Adding formulation table...")
            # Get formulation data from multiple sources
            formulation_data = None
            
            # Try to get from dfs first
            if dfs and len(dfs) > 0:
                formulation_data = dfs[0].get('formulation', [])
            
            # If not in dfs, try to get from session state loaded_experiment
            if not formulation_data or len(formulation_data) == 0:
                try:
                    import streamlit as st
                    loaded_experiment = st.session_state.get('loaded_experiment')
                    if loaded_experiment:
                        experiment_data = loaded_experiment.get('experiment_data', {})
                        cells_data = experiment_data.get('cells', [])
                        if cells_data and len(cells_data) > 0:
                            # Get formulation from first cell
                            formulation_data = cells_data[0].get('formulation', [])
                            
                            # If formulation_data is a string (JSON), parse it
                            if isinstance(formulation_data, str):
                                try:
                                    formulation_data = json.loads(formulation_data)
                                except (json.JSONDecodeError, TypeError):
                                    logger.warning(f"Could not parse formulation JSON string: {formulation_data}")
                                    formulation_data = []
                except ImportError:
                    # streamlit not available (e.g., in testing)
                    pass
            
            # Normalize formulation_data - ensure it's a list
            if formulation_data and not isinstance(formulation_data, list):
                logger.warning(f"Formulation data is not a list: {type(formulation_data)}, converting")
                formulation_data = [formulation_data] if formulation_data else []
            
            # Debug logging - show full data structure
            logger.info(f"Formulation data length: {len(formulation_data) if formulation_data else 0}")
            if formulation_data:
                logger.info(f"Formulation data type: {type(formulation_data)}")
                logger.info(f"Formulation data sample (first 2 items): {formulation_data[:2] if len(formulation_data) > 2 else formulation_data}")
                # Log each item's structure
                for i, item in enumerate(formulation_data[:3]):  # Log first 3 items
                    logger.info(f"  Item {i}: type={type(item)}, keys={list(item.keys()) if isinstance(item, dict) else 'N/A'}, value={item}")
            
            if formulation_data and len(formulation_data) > 0:
                # Determine which slide to use
                target_slide = slide2 if slide2 else slide1
                target_y = slide2_y if slide2 else current_y
                
                # Add header
                if slide2:
                    header_box = slide2.shapes.add_textbox(Inches(left_margin), Inches(target_y - 0.3), Inches(content_width), Inches(0.4))
                    header_tf = header_box.text_frame
                    header_tf.clear()
                    header_p = header_tf.add_paragraph()
                    header_p.text = "Formulation"
                    header_p.font.size = Pt(16)
                    header_p.font.bold = True
                    header_p.font.name = 'Calibri'
                
                # Add formulation table
                table_height = min(3.0, 0.4 * (len(formulation_data) + 2))
                add_formulation_table_to_slide(
                    target_slide, formulation_data, 
                    left_margin, target_y, 4.0, table_height
                )
                
                if slide2:
                    slide2_y += table_height + 0.5
                else:
                    current_y += table_height + 0.5
            else:
                logger.warning("Formulation data not available or empty")
                # Add placeholder text if no data
                target_slide = slide2 if slide2 else slide1
                target_y = slide2_y if slide2 else current_y
                placeholder_box = target_slide.shapes.add_textbox(Inches(left_margin), Inches(target_y), Inches(8), Inches(0.5))
                placeholder_tf = placeholder_box.text_frame
                placeholder_tf.clear()
                placeholder_p = placeholder_tf.add_paragraph()
                placeholder_p.text = "No formulation data available for this experiment."
                placeholder_p.font.size = Pt(12)
                placeholder_p.font.name = 'Calibri'
                placeholder_p.font.italic = True
                if slide2:
                    slide2_y += 0.7
                else:
                    current_y += 0.7
        
        # Add plots to slide 2 (moved from slide 1 for better visibility and cleanliness)
        # Ensure slide 2 exists if plots are included
        if (include_main_plot or include_retention_plot) and not slide2:
            slide2 = prs.slides.add_slide(prs.slide_layouts[6])
            # Add title to second slide
            title_box2 = slide2.shapes.add_textbox(title_left, title_top, title_width, title_height)
            title_tf2 = title_box2.text_frame
            title_tf2.clear()
            title_p2 = title_tf2.add_paragraph()
            title_p2.text = f"{slide_title} (Continued)"
            title_p2.font.size = Pt(24)
            title_p2.font.bold = True
            title_p2.alignment = PP_ALIGN.LEFT
            title_p2.font.name = 'Calibri'
            slide2_y = 1.5
        
        plot_count = 0
        if include_main_plot:
            plot_count += 1
        if include_retention_plot:
            plot_count += 1
        
        # Fixed dimensions for side-by-side plots
        plot_width = 4.0  # Width for each plot (side by side)
        plot_height = 3.0  # Height for each plot
        
        # Calculate plot positions on slide 2
        if slide2:
            # Start plots below formulation table if it exists, otherwise below title
            plot_start_y = slide2_y if slide2_y > 1.5 else 1.5
        else:
            plot_start_y = current_y
        
        # Generate and add main plot (Capacity vs Cycle Number) to slide 2
        if include_main_plot and slide2:
            logger.info("=== Generating Main Capacity Plot (Capacity vs Cycle Number) ===")
            try:
                main_fig = create_main_plot_from_session_state(
                    dfs, show_lines, show_efficiency_lines, remove_last_cycle,
                    show_graph_title, experiment_name, show_average_performance,
                    avg_line_toggles, remove_markers, hide_legend
                )
                
                if main_fig is None:
                    logger.error("Main plot figure is None")
                    raise ValueError("Main plot generation returned None")
                
                main_img_path = save_figure_to_temp_file(main_fig)
                temp_files.append(main_img_path)
                
                # Position first plot on the left
                plot1_left = 1.0
                logger.info(f"Adding main plot to slide 2 at position ({plot1_left}, {plot_start_y})...")
                if add_picture_to_slide_safely(slide2, main_img_path, plot1_left, plot_start_y, plot_width, plot_height):
                    logger.info("Main plot (Capacity vs Cycle Number) added successfully to slide 2")
                else:
                    logger.error("Failed to add main plot to slide")
                    
            except Exception as e:
                logger.error(f"Error generating main plot: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Generate and add retention plot to slide 2
        if include_retention_plot and slide2:
            logger.info("=== Generating Capacity Retention Plot ===")
            logger.info(f"Retention plot parameters: show_lines={retention_show_lines}, reference_cycle={reference_cycle}, threshold={retention_threshold}")
            try:
                retention_fig = create_retention_plot_from_session_state(
                    dfs, retention_show_lines, reference_cycle, formation_cycles, remove_last_cycle,
                    retention_show_title, experiment_name, retention_threshold, y_axis_min, y_axis_max,
                    show_baseline_line, show_threshold_line, retention_remove_markers, retention_hide_legend
                )
                
                if retention_fig is None:
                    logger.error("Retention plot figure is None")
                    raise ValueError("Retention plot generation returned None")
                
                logger.info("Retention plot figure created successfully, saving to temp file...")
                retention_img_path = save_figure_to_temp_file(retention_fig)
                temp_files.append(retention_img_path)
                
                # Position second plot on the right (side by side with first plot)
                plot2_left = 5.5  # Position to the right of first plot
                plot2_y = plot_start_y  # Same Y position as first plot (side by side)
                logger.info(f"Adding retention plot to slide 2 at position ({plot2_left}, {plot2_y})...")
                if add_picture_to_slide_safely(slide2, retention_img_path, plot2_left, plot2_y, plot_width, plot_height):
                    logger.info("Retention plot added successfully to slide 2")
                else:
                    logger.error("Failed to add retention plot to slide")
                
                # Update slide2_y after both plots (use max height + spacing)
                slide2_y = plot_start_y + plot_height + 0.5
                    
            except Exception as e:
                logger.error(f"Error generating retention plot: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Don't raise - continue with export without retention plot
                # If only main plot was added, update position
                if include_main_plot:
                    slide2_y = plot_start_y + plot_height + 0.5
        
        # Validate PowerPoint structure
        if not validate_powerpoint_structure(prs):
            raise ValueError("PowerPoint structure validation failed")
        
        # Save presentation
        logger.info("=== Saving PowerPoint Presentation ===")
        pptx_bytes = io.BytesIO()
        prs.save(pptx_bytes)
        pptx_bytes.seek(0)
        
        # Generate filename
        if experiment_name:
            if len(dfs) == 1:
                testnum = dfs[0].get('testnum', 'Cell 1') or 'Cell 1'
                pptx_file_name = f'{experiment_name} {testnum} Summary.pptx'
            else:
                pptx_file_name = f'{experiment_name} Cell Comparison Summary.pptx'
        else:
            if len(dfs) == 1:
                testnum = dfs[0].get('testnum', 'Cell 1') or 'Cell 1'
                pptx_file_name = f'{testnum} Summary.pptx'
            else:
                pptx_file_name = 'Cell Comparison Summary.pptx'
        
        logger.info(f"=== PowerPoint Export Completed Successfully ===")
        logger.info(f"File: {pptx_file_name}")
        logger.info(f"Size: {len(pptx_bytes.getvalue())} bytes")
        return pptx_bytes, pptx_file_name 
        
    except Exception as e:
        logger.error(f"=== PowerPoint Export Failed ===")
        logger.error(f"Error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise
        
    finally:
        # Clean up temporary files
        logger.info("Cleaning up temporary files...")
        cleanup_temp_files(temp_files)

def export_excel(dfs: List[Dict[str, Any]], show_averages: bool, experiment_name: str) -> Tuple[io.BytesIO, str]:
    """
    Export data to Excel format with charts.
    """
    try:
        logger.info("Starting Excel export...")
        
        # Create Excel workbook
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            headers = ["Cell", "1st Cycle Discharge Capacity (mAh/g)", "First Cycle Efficiency (%)", "Cycle Life (80%)", "Reversible Capacity (mAh/g)", "Coulombic Efficiency (%)"]
            summary_data.append(headers)
            
            for i, d in enumerate(dfs):
                df_cell = d['df']
                cell_name = d.get('testnum', f'Cell {i+1}') or f'Cell {i+1}'
                
                # Calculate metrics using the same logic as the app
                metrics = get_cell_metrics(df_cell, 4)  # Default formation cycles
                
                summary_data.append([
                    cell_name, 
                    metrics['qdis_str'], 
                    metrics['eff_str'], 
                    metrics['cycle_life_str'],
                    metrics['reversible_str'],
                    metrics['coulombic_str']
                ])
            
            if show_averages and len(dfs) > 1:
                # Calculate averages
                avg_metrics = {
                    'max_qdis': [], 'eff_pct': [], 'cycle_life': [],
                    'reversible_capacity': [], 'coulombic_eff': []
                }
                
                for d in dfs:
                    df_cell = d['df']
                    metrics = get_cell_metrics(df_cell, 4)
                    
                    if metrics['max_qdis'] is not None:
                        avg_metrics['max_qdis'].append(metrics['max_qdis'])
                    if metrics['eff_pct'] is not None:
                        avg_metrics['eff_pct'].append(metrics['eff_pct'])
                    if metrics['cycle_life'] is not None:
                        avg_metrics['cycle_life'].append(metrics['cycle_life'])
                    if metrics['reversible_capacity'] is not None:
                        avg_metrics['reversible_capacity'].append(metrics['reversible_capacity'])
                    if metrics['coulombic_eff'] is not None:
                        avg_metrics['coulombic_eff'].append(metrics['coulombic_eff'])
                
                # Calculate final averages
                avg_row = ["AVERAGE"]
                avg_row.append(f"{np.mean(avg_metrics['max_qdis']):.1f}" if avg_metrics['max_qdis'] else "N/A")
                avg_row.append(f"{np.mean(avg_metrics['eff_pct']):.1f}%" if avg_metrics['eff_pct'] else "N/A")
                avg_row.append(f"{np.mean(avg_metrics['cycle_life']):.0f}" if avg_metrics['cycle_life'] else "N/A")
                avg_row.append(f"{np.mean(avg_metrics['reversible_capacity']):.1f}" if avg_metrics['reversible_capacity'] else "N/A")
                avg_row.append(f"{np.mean(avg_metrics['coulombic_eff']):.1f}%" if avg_metrics['coulombic_eff'] else "N/A")
                
                summary_data.append(avg_row)
            
            # Create summary DataFrame
            summary_df = pd.DataFrame(summary_data[1:], columns=summary_data[0])
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Data sheets for each cell
            for i, d in enumerate(dfs):
                df = d['df']
                cell_name = d.get('testnum', f'Cell {i+1}') or f'Cell {i+1}'
                sheet_name = f'Cell_{i+1}' if len(cell_name) > 31 else cell_name
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        output.seek(0)
        
        # Generate filename
        if experiment_name:
            if len(dfs) == 1:
                testnum = dfs[0].get('testnum', 'Cell 1') or 'Cell 1'
                excel_file_name = f'{experiment_name} {testnum} Data.xlsx'
            else:
                excel_file_name = f'{experiment_name} Cell Comparison Data.xlsx'
        else:
            if len(dfs) == 1:
                testnum = dfs[0].get('testnum', 'Cell 1') or 'Cell 1'
                excel_file_name = f'{testnum} Data.xlsx'
            else:
                excel_file_name = 'Cell Comparison Data.xlsx'
        
        logger.info(f"Excel export completed successfully: {excel_file_name}")
        return output, excel_file_name
        
    except Exception as e:
        logger.error(f"Error in Excel export: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise