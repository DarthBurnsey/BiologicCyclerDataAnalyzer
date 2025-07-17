import streamlit as st
import pandas as pd
import io
from openpyxl import load_workbook
import matplotlib.pyplot as plt
import numpy as np
# --- Helper function for cycle life calculation ---
def calculate_cycle_life_80(qdis_series, cycle_index_series):
    # Use max of cycles 3 and 4 as initial, or last available if <4 cycles
    if len(qdis_series) >= 4:
        initial_qdis = max(qdis_series.iloc[2], qdis_series.iloc[3])
    elif len(qdis_series) > 0:
        initial_qdis = qdis_series.iloc[-1]
    else:
        return None
    threshold = 0.8 * initial_qdis
    below_threshold = qdis_series <= threshold
    if below_threshold.any():
        first_below_idx = below_threshold.idxmin()
        return int(cycle_index_series.iloc[first_below_idx])
    else:
        return int(cycle_index_series.iloc[-1])

def get_qdis_series(df_cell):
    qdis_raw = df_cell['Q Dis (mAh/g)']
    if pd.api.types.is_scalar(qdis_raw):
        return pd.Series([qdis_raw]).dropna()
    else:
        return pd.Series(qdis_raw).dropna()
from data_processing import load_and_preprocess_data
from ui_components import render_toggle_section, display_summary_stats, display_averages, render_cell_inputs, get_initial_areal_capacity
from plotting import plot_capacity_graph

st.title('Battery Data Gravimetric Capacity Calculator')
st.write('Upload your Biologic-style CSV file, enter disc loading and % active material, and download the processed XLSX file.')

# Experiment name input
experiment_name = st.text_input('Experiment Name (optional)', placeholder='Enter experiment name for file naming and summary tab')

# Track number of datasets in session state
if 'num_datasets' not in st.session_state:
    st.session_state['num_datasets'] = 1

# Track which cells are present in session state
if 'cell_indices' not in st.session_state:
    st.session_state['cell_indices'] = [0]
if 'next_cell_idx' not in st.session_state:
    st.session_state['next_cell_idx'] = 1

# Add/remove buttons and cell headers
cols = st.columns(len(st.session_state['cell_indices']) + 1)
header_cols = st.columns(len(st.session_state['cell_indices']))

# Store all dataset info
datasets = render_cell_inputs()

# Process and plot if at least one dataset is ready
valid_datasets = []
for ds in datasets:
    if ds['file'] and ds['loading'] > 0 and 0 < ds['active'] <= 100:
        valid_datasets.append(ds)

ready = len(valid_datasets) > 0
if ready:
    # Disc diameter input (mm) for areal capacity calculation, with plus/minus buttons
    disc_diameter_mm = st.number_input('Disc Diameter (mm) for Areal Capacity Calculation', min_value=1, max_value=50, value=15, step=1, key='disc_diameter_mm')
    disc_area_cm2 = np.pi * (disc_diameter_mm / 2 / 10) ** 2  # convert mm to cm, then area
    
    dfs = load_and_preprocess_data(valid_datasets)
    show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers = render_toggle_section(dfs)
    fig = plot_capacity_graph(
        dfs, show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, experiment_name,
        show_average_performance, avg_line_toggles, remove_markers
    )
    st.pyplot(fig)
    display_summary_stats(dfs, disc_area_cm2)
    # Average comparison cells toggle (only show when multiple cells)
    show_averages = False
    if len(dfs) > 1:
        show_averages = st.checkbox('Average the comparison cells', value=True)
    display_averages(dfs, show_averages, disc_area_cm2)

    # --- PowerPoint Export ---
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    import tempfile

    if dfs and len(dfs) > 0:
        # Create PowerPoint
        prs = Presentation()
        
        if len(dfs) == 1:
            # Single cell - use bullet points format
            df_cell = dfs[0]['df']
            testnum = dfs[0]['testnum'] if dfs[0]['testnum'] else 'Cell 1'
            
            # Calculate summary values
            first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
            max_qdis = max(first_three_qdis) if first_three_qdis else None
            if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
                first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
                eff_pct = first_cycle_eff * 100
            else:
                eff_pct = None
            
            # Cycle Life (80%) calculation
            qdis_series = get_qdis_series(df_cell)
            cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
            cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
            
            # Safe formatting for summary values
            qdis_str = f"{max_qdis:.1f}" if isinstance(max_qdis, (int, float)) else "N/A"
            eff_str = f"{eff_pct:.1f}%" if isinstance(eff_pct, (int, float)) else "N/A"
            cycle_life_str = str(cycle_life_80) if isinstance(cycle_life_80, (int, float)) else "N/A"
            
            # Create slide with bullet points
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            title_shape = slide.shapes.title
            if title_shape is not None:
                if experiment_name:
                    title_shape.text = f"{experiment_name} - {testnum} Summary"
                else:
                    title_shape.text = f"{testnum} Summary"
            if hasattr(title_shape, 'text_frame') and getattr(title_shape, 'text_frame', None) is not None:
                title_shape.text_frame.paragraphs[0].font.size = Pt(30)
            
            # Echem header
            echem_header_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(3.5), Inches(0.5))
            echem_header_tf = echem_header_box.text_frame
            echem_header_tf.clear()
            echem_header_p = echem_header_tf.add_paragraph()
            echem_header_p.text = "Echem"
            echem_header_p.level = 0
            echem_header_p.font.size = Pt(24)
            echem_header_p.font.bold = True
            echem_header_p.font.color.rgb = RGBColor(0, 0, 0)
            echem_header_p.font.italic = False
            
            # Summary bullets
            content = slide.placeholders[1]
            if hasattr(content, 'text'):
                content.text = ""
            if hasattr(content, 'text_frame') and getattr(content, 'text_frame', None) is not None:
                p1 = content.text_frame.add_paragraph()
                p1.text = f"1st Cycle Discharge Capacity: {qdis_str} mAh/g"
                p1.level = 0
                p1.font.size = Pt(18)
                p2 = content.text_frame.add_paragraph()
                p2.text = f"First Cycle Efficiency: {eff_str}"
                p2.level = 0
                p2.font.size = Pt(18)
                p3 = content.text_frame.add_paragraph()
                p3.text = f"Cycle Life (80%): {cycle_life_str}"
                p3.level = 0
                p3.font.size = Pt(18)
            
            # Create graph for single cell
            # Use plot_capacity_graph with show_graph_title as set by the user
            fig = plot_capacity_graph(
                [dfs[0]], show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, experiment_name,
                show_average_performance, avg_line_toggles, remove_markers
            )
            img_bytes = io.BytesIO()
            fig.savefig(img_bytes, format='png', bbox_inches='tight')
            plt.close(fig)
            img_bytes.seek(0)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_img:
                tmp_img.write(img_bytes.read())
                img_path = tmp_img.name
            slide.shapes.add_picture(img_path, Inches(5.5), Inches(1.2), width=Inches(4.5))
            
            # Download button
            pptx_bytes = io.BytesIO()
            prs.save(pptx_bytes)
            pptx_bytes.seek(0)
            # Update PowerPoint file name to include experiment name
            if experiment_name:
                pptx_file_name = f'{experiment_name} {testnum} Summary.pptx'
            else:
                pptx_file_name = f'{testnum} Summary.pptx'
            st.download_button(f'Download PowerPoint: {pptx_file_name}', data=pptx_bytes, file_name=pptx_file_name, mime='application/vnd.openxmlformats-officedocument.presentationml.presentation')
            
        else:
            # Multiple cells - use table format
            slide = prs.slides.add_slide(prs.slide_layouts[1])  # Title and Content layout
            title_shape = slide.shapes.title
            if title_shape is not None:
                if experiment_name:
                    title_shape.text = f"{experiment_name} - Cell Comparison Summary"
                else:
                    title_shape.text = "Cell Comparison Summary"
            if hasattr(title_shape, 'text_frame') and getattr(title_shape, 'text_frame', None) is not None:
                title_shape.text_frame.paragraphs[0].font.size = Pt(30)
            
            # Echem header
            echem_header_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(3.5), Inches(0.5))
            echem_header_tf = echem_header_box.text_frame
            echem_header_tf.clear()
            echem_header_p = echem_header_tf.add_paragraph()
            echem_header_p.text = "Echem"
            echem_header_p.level = 0
            echem_header_p.font.size = Pt(24)
            echem_header_p.font.bold = True
            echem_header_p.font.color.rgb = RGBColor(0, 0, 0)
            echem_header_p.font.italic = False
            
            # Calculate summary data for all cells
            table_data = []
            headers = ["Cell", "1st Cycle Discharge Capacity (mAh/g)", "First Cycle Efficiency (%)", "Cycle Life (80%)", "Initial Areal Capacity (mAh/cm²)", "Reversible Capacity (mAh/g)", "Coulombic Efficiency (post-formation, %)"]
            table_data.append(headers)
            
            for i, d in enumerate(dfs):
                df_cell = d['df']
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                # Calculate values
                first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
                max_qdis = max(first_three_qdis) if first_three_qdis else None
                qdis_str = f"{max_qdis:.1f}" if isinstance(max_qdis, (int, float)) else "N/A"
                if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
                    first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
                    eff_pct = first_cycle_eff * 100
                    eff_str = f"{eff_pct:.1f}%"
                else:
                    eff_str = "N/A"
                # Cycle Life (80%)
                qdis_series = get_qdis_series(df_cell)
                cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
                cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
                cycle_life_str = str(cycle_life_80) if isinstance(cycle_life_80, (int, float)) else "N/A"
                # Initial Areal Capacity (mAh/cm²)
                areal_capacity, chosen_cycle, diff_pct, eff_val = get_initial_areal_capacity(df_cell, disc_area_cm2)
                if areal_capacity is None:
                    areal_str = "N/A"
                else:
                    areal_str = f"{areal_capacity:.3f}"
                # Reversible Capacity (mAh/g)
                formation_cycles = d.get('formation_cycles', 4)
                if len(df_cell) > formation_cycles:
                    reversible_capacity = df_cell['Q Dis (mAh/g)'].iloc[formation_cycles]
                    reversible_str = f"{reversible_capacity:.1f}"
                else:
                    reversible_str = "N/A"
                # Coulombic Efficiency (post-formation, %)
                eff_col = 'Efficiency (-)'
                qdis_col = 'Q Dis (mAh/g)'
                n_cycles = len(df_cell)
                ceff_values = []
                if eff_col in df_cell.columns and qdis_col in df_cell.columns and n_cycles > formation_cycles+1:
                    prev_qdis = df_cell[qdis_col].iloc[formation_cycles]
                    prev_eff = df_cell[eff_col].iloc[formation_cycles]
                    for j in range(formation_cycles+1, n_cycles):
                        curr_qdis = df_cell[qdis_col].iloc[j]
                        curr_eff = df_cell[eff_col].iloc[j]
                        if prev_qdis > 0 and (curr_qdis < 0.95 * prev_qdis or curr_eff < 0.95 * prev_eff):
                            break
                        ceff_values.append(curr_eff)
                        prev_qdis = curr_qdis
                        prev_eff = curr_eff
                if ceff_values:
                    ceff_str = f"{sum(ceff_values)/len(ceff_values)*100:.2f}"
                else:
                    ceff_str = "N/A"
                table_data.append([cell_name, qdis_str, eff_str, cycle_life_str, areal_str, reversible_str, ceff_str])
            
            # Add average row if requested
            if show_averages:
                avg_qdis_values = []
                avg_eff_values = []
                avg_cycle_life_values = []
                avg_areal_capacity_values = []
                avg_reversible_capacities = []
                avg_ceff_values = []
                for d in dfs:
                    df_cell = d['df']
                    first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
                    max_qdis = max(first_three_qdis) if first_three_qdis else None
                    if max_qdis is not None:
                        avg_qdis_values.append(max_qdis)
                    if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
                        first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
                        eff_pct = first_cycle_eff * 100
                        avg_eff_values.append(eff_pct)
                    try:
                        qdis_series = get_qdis_series(df_cell)
                        cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
                        cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
                        avg_cycle_life_values.append(cycle_life_80)
                    except Exception:
                        pass
                    areal_capacity, chosen_cycle, diff_pct, eff_val = get_initial_areal_capacity(df_cell, disc_area_cm2)
                    if areal_capacity is not None:
                        avg_areal_capacity_values.append(areal_capacity)
                    formation_cycles = d.get('formation_cycles', 4)
                    if len(df_cell) > formation_cycles:
                        reversible_capacity = df_cell['Q Dis (mAh/g)'].iloc[formation_cycles]
                        avg_reversible_capacities.append(reversible_capacity)
                    # Coulombic Efficiency (post-formation, %)
                    eff_col = 'Efficiency (-)'
                    qdis_col = 'Q Dis (mAh/g)'
                    n_cycles = len(df_cell)
                    ceff_values = []
                    if eff_col in df_cell.columns and qdis_col in df_cell.columns and n_cycles > formation_cycles+1:
                        prev_qdis = df_cell[qdis_col].iloc[formation_cycles]
                        prev_eff = df_cell[eff_col].iloc[formation_cycles]
                        for j in range(formation_cycles+1, n_cycles):
                            curr_qdis = df_cell[qdis_col].iloc[j]
                            curr_eff = df_cell[eff_col].iloc[j]
                            if prev_qdis > 0 and (curr_qdis < 0.95 * prev_qdis or curr_eff < 0.95 * prev_eff):
                                break
                            ceff_values.append(curr_eff)
                            prev_qdis = curr_qdis
                            prev_eff = curr_eff
                    if ceff_values:
                        avg_ceff_values.append(sum(ceff_values)/len(ceff_values)*100)
                avg_qdis = sum(avg_qdis_values) / len(avg_qdis_values) if avg_qdis_values else 0
                avg_eff = sum(avg_eff_values) / len(avg_eff_values) if avg_eff_values else 0
                avg_cycle_life = sum(avg_cycle_life_values) / len(avg_cycle_life_values) if avg_cycle_life_values else 0
                avg_areal = sum(avg_areal_capacity_values) / len(avg_areal_capacity_values) if avg_areal_capacity_values else 0
                avg_reversible = sum(avg_reversible_capacities) / len(avg_reversible_capacities) if avg_reversible_capacities else None
                avg_ceff = sum(avg_ceff_values) / len(avg_ceff_values) if avg_ceff_values else None
                table_data.append(["AVERAGE", f"{avg_qdis:.1f}", f"{avg_eff:.1f}%", f"{avg_cycle_life:.0f}", f"{avg_areal:.3f}", f"{avg_reversible:.1f}" if avg_reversible is not None else "N/A", f"{avg_ceff:.2f}" if avg_ceff is not None else "N/A"])
            
            # Create table - centered on slide
            rows, cols = len(table_data), len(table_data[0])
            table_width = 7  # inches
            table_height = 2.5  # inches
            # Center the table: (slide width - table width) / 2 = (10 - 7) / 2 = 1.5 inches from left
            table_left = 1.5
            table = slide.shapes.add_table(rows, cols, Inches(table_left), Inches(2.0), Inches(table_width), Inches(table_height)).table
            
            # Populate table
            for i, row_data in enumerate(table_data):
                for j, cell_data in enumerate(row_data):
                    cell = table.cell(i, j)
                    cell.text = str(cell_data)
                    
                    # Format header row
                    if i == 0:
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = RGBColor(68, 114, 196)
                        for paragraph in cell.text_frame.paragraphs:
                            paragraph.font.color.rgb = RGBColor(255, 255, 255)
                            paragraph.font.bold = True
                            paragraph.font.size = Pt(12)
                    # Format average row
                    elif show_averages and i == len(table_data) - 1:
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = RGBColor(146, 208, 80)
                        for paragraph in cell.text_frame.paragraphs:
                            paragraph.font.bold = True
                            paragraph.font.size = Pt(12)
                    else:
                        for paragraph in cell.text_frame.paragraphs:
                            paragraph.font.size = Pt(11)
            
            # Create comparison graph
            # Use the same plot as the main display, including average line if toggled, with show_graph_title as set by the user
            fig = plot_capacity_graph(
                dfs, show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, experiment_name,
                show_average_performance, avg_line_toggles, remove_markers
            )
            img_bytes = io.BytesIO()
            fig.savefig(img_bytes, format='png', bbox_inches='tight', dpi=300)
            plt.close(fig)
            img_bytes.seek(0)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_img:
                tmp_img.write(img_bytes.read())
                img_path = tmp_img.name
            # Set graph width to 11cm and calculate height to maintain aspect ratio
            slide_width_cm = 11  # cm
            slide_width_inches = slide_width_cm / 2.54  # convert cm to inches
            aspect_ratio = 8/5  # width/height from figsize
            slide_height_inches = slide_width_inches / aspect_ratio
            slide.shapes.add_picture(img_path, Inches(14/2.54), Inches(12/2.54), width=Inches(slide_width_inches), height=Inches(slide_height_inches))
            
            # Download button
            pptx_bytes = io.BytesIO()
            prs.save(pptx_bytes)
            pptx_bytes.seek(0)
            # Update PowerPoint file name to include experiment name
            if experiment_name:
                pptx_file_name = f'{experiment_name} Cell Comparison Summary.pptx'
            else:
                pptx_file_name = 'Cell Comparison Summary.pptx'
            st.download_button(f'Download PowerPoint: {pptx_file_name}', data=pptx_bytes, file_name=pptx_file_name, mime='application/vnd.openxmlformats-officedocument.presentationml.presentation')

    # --- Excel Export ---
    # Prepare XLSX for download with multiple sheets
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for d in dfs:
            df_cell = d['df']
            sheet_name = d['testnum'] if d['testnum'] else f'Cell {dfs.index(d)+1}'
            df_cell.to_excel(writer, index=False, startrow=4, sheet_name=sheet_name)
    output.seek(0)

    # Add summary values and native Excel chart to each sheet
    from openpyxl import load_workbook
    from openpyxl.chart import LineChart, Reference
    output.seek(0)
    wb = load_workbook(output)
    for d in dfs:
        ws = wb[d['testnum'] if d['testnum'] else f'Cell {dfs.index(d)+1}']
        df_cell = d['df']
        # Total loading and active material loading
        ws['A1'] = 'Total loading (mg)'
        ws['B1'] = d['loading']
        ws['A2'] = 'Active material loading (mg)'
        ws['B2'] = d['loading'] * (d['active'] / 100)
        # Summary values
        first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
        max_qdis = max(first_three_qdis) if first_three_qdis else None
        if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
            first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
            eff_pct = first_cycle_eff * 100
        else:
            eff_pct = None
        # Cycle Life (80%) calculation
        qdis_series = get_qdis_series(df_cell)
        cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
        cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
        # Write to Excel
        ws['P1'] = '1st Cycle Discharge Capacity (mAh/g)'
        ws['Q1'] = f"{max_qdis:.1f}" if isinstance(max_qdis, (int, float)) and max_qdis is not None else ''
        ws['P2'] = 'First Cycle Efficiency (%)'
        ws['Q2'] = f"{eff_pct:.1f}" if isinstance(eff_pct, (int, float)) and eff_pct is not None else ''
        ws['P3'] = 'Cycle Life (80%)'
        ws['Q3'] = cycle_life_80 if cycle_life_80 is not None else ''
        # Native Excel chart
        data_start_row = 6
        data_end_row = data_start_row + len(df_cell) - 1
        headers = list(df_cell.columns)
        x_col_idx = 1
        q_dis_col = headers.index('Q Dis (mAh/g)') + 1
        q_chg_col = headers.index('Q Chg (mAh/g)') + 1
        chart = LineChart()
        chart.title = 'Gravimetric Capacity vs. ' + df_cell.columns[0]
        chart.y_axis.title = 'Capacity (mAh/g)'
        chart.x_axis.title = df_cell.columns[0]
        chart.x_axis.majorTickMark = 'in'
        chart.y_axis.majorTickMark = 'in'
        chart.width = 20
        chart.height = 12
        # Ensure axes and gridlines are visible
        chart.x_axis.majorGridlines = None
        chart.y_axis.majorGridlines = None
        # Ensure axes are visible on Mac and PC
        chart.x_axis.crosses = 'autoZero'
        chart.y_axis.crosses = 'autoZero'
        data = Reference(ws, min_col=min(q_dis_col, q_chg_col), max_col=max(q_dis_col, q_chg_col), min_row=data_start_row-1, max_row=data_end_row)
        chart.add_data(data, titles_from_data=True)
        cats = Reference(ws, min_col=x_col_idx, min_row=data_start_row, max_row=data_end_row)
        chart.set_categories(cats)
        ws.add_chart(chart, 'S5')
    
    # Add summary tab for multiple cells
    if len(dfs) > 1:
        # Create summary worksheet
        summary_sheet_name = f"{experiment_name} Summary" if experiment_name else "Summary"
        # Ensure sheet name is valid (Excel has restrictions)
        summary_sheet_name = summary_sheet_name[:31]  # Excel sheet names limited to 31 characters
        ws_summary = wb.create_sheet(summary_sheet_name)
        
        # Create summary table headers
        ws_summary['A1'] = 'Cell'
        ws_summary['B1'] = '1st Cycle Discharge Capacity (mAh/g)'
        ws_summary['C1'] = 'First Cycle Efficiency (%)'
        ws_summary['D1'] = 'Cycle Life (80%)'
        ws_summary['E1'] = 'Initial Areal Capacity (mAh/cm²)'
        ws_summary['F1'] = 'Reversible Capacity (mAh/g)'
        ws_summary['G1'] = 'Coulombic Efficiency (post-formation, %)'
        
        # Calculate disc area (cm^2) from selected diameter
        disc_area_cm2 = np.pi * (disc_diameter_mm / 2 / 10) ** 2
        
        # Add data for each cell
        for i, d in enumerate(dfs):
            df_cell = d['df']
            cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
            
            # Calculate summary values
            first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
            max_qdis = max(first_three_qdis) if first_three_qdis else None
            if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
                first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
                eff_pct = first_cycle_eff * 100
            else:
                eff_pct = None
            # Cycle Life (80%) calculation
            qdis_series = get_qdis_series(df_cell)
            cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
            cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
            # 1st Cycle Areal Capacity (Excel summary)
            areal_capacity, chosen_cycle, diff_pct, eff_val = get_initial_areal_capacity(df_cell, disc_area_cm2)
            if areal_capacity is None:
                areal_capacity = ''
            # Reversible Capacity (mAh/g)
            formation_cycles = d.get('formation_cycles', 4)
            if len(df_cell) > formation_cycles:
                reversible_capacity = df_cell['Q Dis (mAh/g)'].iloc[formation_cycles]
                reversible_str = f"{reversible_capacity:.1f}"
            else:
                reversible_str = "N/A"
            # Coulombic Efficiency (post-formation, %)
            eff_col = 'Efficiency (-)'
            qdis_col = 'Q Dis (mAh/g)'
            n_cycles = len(df_cell)
            ceff_values = []
            if eff_col in df_cell.columns and qdis_col in df_cell.columns and n_cycles > formation_cycles+1:
                prev_qdis = df_cell[qdis_col].iloc[formation_cycles]
                prev_eff = df_cell[eff_col].iloc[formation_cycles]
                for j in range(formation_cycles+1, n_cycles):
                    curr_qdis = df_cell[qdis_col].iloc[j]
                    curr_eff = df_cell[eff_col].iloc[j]
                    if prev_qdis > 0 and (curr_qdis < 0.95 * prev_qdis or curr_eff < 0.95 * prev_eff):
                        break
                    ceff_values.append(curr_eff)
                    prev_qdis = curr_qdis
                    prev_eff = curr_eff
            if ceff_values:
                ceff_str = f"{sum(ceff_values)/len(ceff_values)*100:.2f}"
            else:
                ceff_str = "N/A"
            # Write to summary sheet
            row = i + 2  # Start from row 2 (row 1 is headers)
            ws_summary[f'A{row}'] = cell_name
            ws_summary[f'B{row}'] = max_qdis if isinstance(max_qdis, (int, float)) and max_qdis is not None else ''
            ws_summary[f'C{row}'] = eff_pct if isinstance(eff_pct, (int, float)) and eff_pct is not None else ''
            ws_summary[f'D{row}'] = cycle_life_80 if cycle_life_80 is not None else ''
            ws_summary[f'E{row}'] = areal_capacity if areal_capacity != '' else ''
            ws_summary[f'F{row}'] = reversible_str if reversible_str != "N/A" else ''
            ws_summary[f'G{row}'] = ceff_str if ceff_str != "N/A" else ''
            # Add note if out of range
            if areal_capacity != '' and (areal_capacity < 0 or areal_capacity > 10):
                ws_summary[f'H{row}'] = 'Warning: Areal capacity out of 0-10 mAh/cm² range'
        
        # Add average row if show_averages is True
        if show_averages:
            avg_qdis_values = []
            avg_eff_values = []
            avg_cycle_life_values = []
            avg_areal_capacity_values = []
            avg_reversible_capacities = []
            avg_ceff_values = []
            for d in dfs:
                df_cell = d['df']
                # 1st Cycle Discharge Capacity
                first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
                max_qdis = max(first_three_qdis) if first_three_qdis else None
                if max_qdis is not None:
                    avg_qdis_values.append(max_qdis)
                # First Cycle Efficiency
                if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
                    first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
                    eff_pct = first_cycle_eff * 100
                    avg_eff_values.append(eff_pct)
                # Cycle Life (80%)
                try:
                    qdis_series = get_qdis_series(df_cell)
                    cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
                    cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
                    avg_cycle_life_values.append(cycle_life_80)
                except Exception:
                    pass
                # 1st Cycle Areal Capacity (Excel summary)
                areal_capacity, chosen_cycle, diff_pct, eff_val = get_initial_areal_capacity(df_cell, disc_area_cm2)
                if areal_capacity is not None:
                    avg_areal_capacity_values.append(areal_capacity)
                # Reversible Capacity (mAh/g)
                formation_cycles = d.get('formation_cycles', 4)
                if len(df_cell) > formation_cycles:
                    reversible_capacity = df_cell['Q Dis (mAh/g)'].iloc[formation_cycles]
                    avg_reversible_capacities.append(reversible_capacity)
                # Coulombic Efficiency (post-formation, %)
                eff_col = 'Efficiency (-)'
                qdis_col = 'Q Dis (mAh/g)'
                n_cycles = len(df_cell)
                ceff_values = []
                if eff_col in df_cell.columns and qdis_col in df_cell.columns and n_cycles > formation_cycles+1:
                    prev_qdis = df_cell[qdis_col].iloc[formation_cycles]
                    prev_eff = df_cell[eff_col].iloc[formation_cycles]
                    for j in range(formation_cycles+1, n_cycles):
                        curr_qdis = df_cell[qdis_col].iloc[j]
                        curr_eff = df_cell[eff_col].iloc[j]
                        if prev_qdis > 0 and (curr_qdis < 0.95 * prev_qdis or curr_eff < 0.95 * prev_eff):
                            break
                        ceff_values.append(curr_eff)
                        prev_qdis = curr_qdis
                        prev_eff = curr_eff
                if ceff_values:
                    avg_ceff_values.append(sum(ceff_values)/len(ceff_values)*100)
            # Add average row
            avg_row = len(dfs) + 2
            ws_summary[f'A{avg_row}'] = 'Average'
            ws_summary[f'B{avg_row}'] = sum(avg_qdis_values) / len(avg_qdis_values) if avg_qdis_values else ''
            ws_summary[f'C{avg_row}'] = sum(avg_eff_values) / len(avg_eff_values) if avg_eff_values else ''
            ws_summary[f'D{avg_row}'] = sum(avg_cycle_life_values) / len(avg_cycle_life_values) if avg_cycle_life_values else ''
            ws_summary[f'E{avg_row}'] = sum(avg_areal_capacity_values) / len(avg_areal_capacity_values) if avg_areal_capacity_values else ''
            ws_summary[f'F{avg_row}'] = sum(avg_reversible_capacities) / len(avg_reversible_capacities) if avg_reversible_capacities else ''
            ws_summary[f'G{avg_row}'] = sum(avg_ceff_values) / len(avg_ceff_values) if avg_ceff_values else ''
            # Add note if out of range for average
            avg_areal = ws_summary[f'E{avg_row}'].value
            if avg_areal != '' and (avg_areal < 0 or avg_areal > 10):
                ws_summary[f'H{avg_row}'] = 'Warning: Areal capacity out of 0-10 mAh/cm² range'
        
        # Move summary tab to the leftmost position
        try:
            wb.move_sheet(ws_summary, offset=-wb.index(ws_summary))
        except Exception:
            # Fallback for openpyxl versions without move_sheet
            wb._sheets.insert(0, wb._sheets.pop(wb._sheets.index(ws_summary)))
    
    # Add average cell performance sheet if toggled
    if show_average_performance and len(dfs) > 1:
        # Find common cycles
        dfs_trimmed = [d['df'][:-1] if remove_last_cycle else d['df'] for d in dfs]
        x_col = dfs_trimmed[0].columns[0]
        common_cycles = set(dfs_trimmed[0][x_col])
        for df in dfs_trimmed[1:]:
            common_cycles = common_cycles & set(df[x_col])
        common_cycles = sorted(list(common_cycles))
        if common_cycles:
            avg_qdis = []
            avg_qchg = []
            avg_eff = []
            for cycle in common_cycles:
                qdis_vals = []
                qchg_vals = []
                eff_vals = []
                for df in dfs_trimmed:
                    row = df[df[x_col] == cycle]
                    if not row.empty:
                        if 'Q Dis (mAh/g)' in row:
                            qdis_vals.append(row['Q Dis (mAh/g)'].values[0])
                        if 'Q Chg (mAh/g)' in row:
                            qchg_vals.append(row['Q Chg (mAh/g)'].values[0])
                        if 'Efficiency (-)' in row and not pd.isnull(row['Efficiency (-)'].values[0]):
                            eff_vals.append(row['Efficiency (-)'].values[0] * 100)
                avg_qdis.append(sum(qdis_vals)/len(qdis_vals) if qdis_vals else None)
                avg_qchg.append(sum(qchg_vals)/len(qchg_vals) if qchg_vals else None)
                avg_eff.append(sum(eff_vals)/len(eff_vals) if eff_vals else None)
            avg_data = [
                [cycle, qd, qc, eff] for cycle, qd, qc, eff in zip(common_cycles, avg_qdis, avg_qchg, avg_eff)
            ]
            avg_sheet_name = f"{experiment_name} Average" if experiment_name else "Average"
            avg_sheet_name = avg_sheet_name[:31]  # Excel sheet name limit
            ws_avg = wb.create_sheet(avg_sheet_name)
            ws_avg.append([str(x_col), 'Average Q Dis (mAh/g)', 'Average Q Chg (mAh/g)', 'Average Efficiency (%)'])
            for row in avg_data:
                ws_avg.append(list(row))
    output2 = io.BytesIO()
    wb.save(output2)
    output2.seek(0)

    # Update file name to include experiment name
    if experiment_name:
        if len(dfs) > 1:
            file_name = f'{experiment_name} Comparison Cycling data.xlsx'
        else:
            file_name = f'{experiment_name} {datasets[0]["testnum"]} Cycling data.xlsx' if datasets[0]["testnum"] else f'{experiment_name} Cycling data.xlsx'
    else:
        file_name = 'Comparison Cycling data.xlsx' if len(dfs) > 1 else f'{datasets[0]["testnum"]} Cycling data.xlsx' if datasets[0]["testnum"] else 'Cycling data.xlsx'
    
    st.success('Processing complete!')
    st.download_button(f'Download XLSX: {file_name}', data=output2, file_name=file_name, mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

else:
    st.info('Please upload a file and enter valid disc loading and % active material.') 