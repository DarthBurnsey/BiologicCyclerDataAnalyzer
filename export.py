# export.py
from typing import List, Dict, Any, Tuple, Optional
import io
import logging
import tempfile
import os
import traceback
from openpyxl import load_workbook
from openpyxl.chart import LineChart, Reference
import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
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
            retention_show_title, experiment_name, False, {}, remove_markers, hide_legend,
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
        plt.close(fig)  # Close to free memory
        
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
    include_porosity: bool = False,
    include_thickness: bool = False,
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
    """
    temp_files = []
    
    try:
        logger.info("=== Starting PowerPoint Export ===")
        logger.info(f"Export parameters: include_main_plot={include_main_plot}, include_retention_plot={include_retention_plot}")
        logger.info(f"Data: {len(dfs)} dataframes, formation_cycles={formation_cycles}")
        
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
        slide = prs.slides.add_slide(prs.slide_layouts[5])  # Blank layout
        
        # Set title with sanitization
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.1), Inches(9), Inches(0.8))
        title_tf = title_box.text_frame
        title_tf.clear()
        title_p = title_tf.add_paragraph()
        
        if len(dfs) == 1:
            testnum = dfs[0].get('testnum', 'Cell 1') or 'Cell 1'
            if experiment_name:
                title_p.text = f"{experiment_name} - {testnum} Summary"
            else:
                title_p.text = f"{testnum} Summary"
        else:
            if experiment_name:
                title_p.text = f"{experiment_name} - Cell Comparison Summary"
            else:
                title_p.text = "Cell Comparison Summary"
        
        title_p.font.size = Pt(30)
        title_p.font.bold = True
        title_p.alignment = PP_ALIGN.CENTER
        
        # Add Echem header
        echem_header_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.0), Inches(3.5), Inches(0.5))
        echem_header_tf = echem_header_box.text_frame
        echem_header_tf.clear()
        echem_header_p = echem_header_tf.add_paragraph()
        echem_header_p.text = "Echem"
        echem_header_p.font.size = Pt(24)
        echem_header_p.font.bold = True
        echem_header_p.font.color.rgb = RGBColor(0, 0, 0)
        
        # Calculate layout positions
        current_y = 1.6
        left_width = 4.5
        right_x = 5.0
        right_width = 4.5
        
        # Content sections based on toggles
        sections_to_add = []
        
        # Plan layout based on enabled toggles
        plot_count = 0
        if include_main_plot:
            plot_count += 1
        if include_retention_plot:
            plot_count += 1
        
        logger.info(f"Plot count: {plot_count} (main: {include_main_plot}, retention: {include_retention_plot})")
        
        # Summary Table Section
        if include_summary_table:
            sections_to_add.append("summary")
        
        # Notes Section
        if include_notes and experiment_notes.strip():
            sections_to_add.append("notes")
        
        # Electrode Data Section
        if include_electrode_data and (include_porosity or include_thickness):
            sections_to_add.append("electrode")
        
        # Add summary table/bullets
        if "summary" in sections_to_add:
            logger.info("Adding summary table...")
            if len(dfs) == 1:
                # Single cell - bullet points
                summary_box = slide.shapes.add_textbox(Inches(0.5), current_y, left_width, Inches(2.0))
                summary_tf = summary_box.text_frame
                summary_tf.clear()
                
                # Summary header
                header_p = summary_tf.add_paragraph()
                header_p.text = "Summary Metrics"
                header_p.font.size = Pt(16)
                header_p.font.bold = True
                
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
                
                # Create table
                rows, cols = len(table_data), len(table_data[0])
                table = slide.shapes.add_table(rows, cols, Inches(0.5), current_y, Inches(8.5), Inches(1.5 + 0.3 * rows)).table
                
                for i, row_data in enumerate(table_data):
                    for j, cell_data in enumerate(row_data):
                        cell = table.cell(i, j)
                        cell.text = str(cell_data)
                        if i == 0:  # Header
                            cell.fill.solid()
                            cell.fill.fore_color.rgb = RGBColor(68, 114, 196)
                            for paragraph in cell.text_frame.paragraphs:
                                paragraph.font.color.rgb = RGBColor(255, 255, 255)
                                paragraph.font.bold = True
                                paragraph.font.size = Pt(11)
                        elif show_averages and i == len(table_data) - 1:  # Average row
                            cell.fill.solid()
                            cell.fill.fore_color.rgb = RGBColor(146, 208, 80)
                            for paragraph in cell.text_frame.paragraphs:
                                paragraph.font.bold = True
                                paragraph.font.size = Pt(11)
                        else:
                            for paragraph in cell.text_frame.paragraphs:
                                paragraph.font.size = Pt(10)
                
                current_y += 2.0 + 0.3 * rows
        
        # Add notes section
        if "notes" in sections_to_add:
            logger.info("Adding notes section...")
            notes_box = slide.shapes.add_textbox(Inches(0.5), current_y, left_width, Inches(1.0))
            notes_tf = notes_box.text_frame
            notes_tf.clear()
            
            # Notes header
            header_p = notes_tf.add_paragraph()
            header_p.text = "Experiment Notes"
            header_p.font.size = Pt(16)
            header_p.font.bold = True
            
            # Notes content
            notes_p = notes_tf.add_paragraph()
            notes_p.text = experiment_notes
            notes_p.font.size = Pt(12)
            
            current_y += 1.2
        
        # Add electrode data section
        if "electrode" in sections_to_add:
            logger.info("Adding electrode data section...")
            electrode_box = slide.shapes.add_textbox(Inches(0.5), current_y, left_width, Inches(1.5))
            electrode_tf = electrode_box.text_frame
            electrode_tf.clear()
            
            # Electrode data header
            header_p = electrode_tf.add_paragraph()
            header_p.text = "Electrode Data"
            header_p.font.size = Pt(16)
            header_p.font.bold = True
            
            # Add electrode data points
            electrode_data = []
            if include_porosity:
                electrode_data.append("• Porosity: Available (see data)")
            if include_thickness:
                electrode_data.append("• Pressed Electrode Thickness: Available (see data)")
            
            for data_point in electrode_data:
                p = electrode_tf.add_paragraph()
                p.text = data_point
                p.font.size = Pt(12)
                p.level = 1
        
        # Add plots
        plot_y = 1.6 if not sections_to_add else current_y + 0.3
        plot_width = 4.0
        plot_height = 2.8
        
        if plot_count == 2:
            # Both plots - side by side
            main_plot_x = 0.5
            retention_plot_x = 5.0
        elif plot_count == 1:
            # Single plot - centered
            main_plot_x = 2.75
            retention_plot_x = 2.75
        
        # Generate and add main plot
        if include_main_plot:
            logger.info("=== Generating Main Capacity Plot ===")
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
                
                if add_picture_to_slide_safely(slide, main_img_path, main_plot_x, plot_y, plot_width, plot_height):
                    logger.info("Main plot added successfully to slide")
                else:
                    logger.error("Failed to add main plot to slide")
                    
            except Exception as e:
                logger.error(f"Error generating main plot: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Generate and add retention plot
        if include_retention_plot:
            logger.info("=== Generating Capacity Retention Plot ===")
            try:
                retention_fig = create_retention_plot_from_session_state(
                    dfs, retention_show_lines, reference_cycle, formation_cycles, remove_last_cycle,
                    retention_show_title, experiment_name, retention_threshold, y_axis_min, y_axis_max,
                    show_baseline_line, show_threshold_line, retention_remove_markers, retention_hide_legend
                )
                
                if retention_fig is None:
                    logger.error("Retention plot figure is None")
                    raise ValueError("Retention plot generation returned None")
                
                retention_img_path = save_figure_to_temp_file(retention_fig)
                temp_files.append(retention_img_path)
                
                if add_picture_to_slide_safely(slide, retention_img_path, retention_plot_x, plot_y, plot_width, plot_height):
                    logger.info("Retention plot added successfully to slide")
                else:
                    logger.error("Failed to add retention plot to slide")
                    
            except Exception as e:
                logger.error(f"Error generating retention plot: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
        
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