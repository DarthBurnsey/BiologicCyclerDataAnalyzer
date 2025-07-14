import streamlit as st
import pandas as pd
import io
from openpyxl import load_workbook
import matplotlib.pyplot as plt
import numpy as np
from data_processing import load_and_preprocess_data
from ui_components import render_toggle_section, display_summary_stats, display_averages, render_cell_inputs
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
    dfs = load_and_preprocess_data(valid_datasets)
    show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title = render_toggle_section(dfs)
    fig = plot_capacity_graph(dfs, show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, experiment_name)
    st.pyplot(fig)
    display_summary_stats(dfs)
    # Average comparison cells toggle (only show when multiple cells)
    show_averages = False
    if len(dfs) > 1:
        show_averages = st.checkbox('Average the comparison cells', value=True)
    display_averages(dfs, show_averages)

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
            cycle_life_80 = None
            try:
                if not df_cell['Q Dis (mAh/g)'].empty:
                    qdis_raw = df_cell['Q Dis (mAh/g)']
                    if np.isscalar(qdis_raw):
                        qdis_series = pd.Series([qdis_raw]).dropna()
                    else:
                        qdis_series = pd.Series(qdis_raw).dropna()
                    if not qdis_series.empty:
                        initial_qdis = qdis_series.iloc[0]
                        threshold = 0.8 * initial_qdis
                        below_threshold = qdis_series <= threshold
                        if below_threshold.any():
                            first_below_idx = below_threshold.idxmin()
                            cycle_life_80 = int(df_cell.loc[first_below_idx, df_cell.columns[0]])
                        else:
                            cycle_life_80 = int(df_cell[df_cell.columns[0]].iloc[-1])
            except Exception:
                cycle_life_80 = None
            
            # Safe formatting for summary values
            qdis_str = f"{max_qdis:.1f}" if isinstance(max_qdis, (int, float)) else "N/A"
            eff_str = f"{eff_pct:.1f}%" if isinstance(eff_pct, (int, float)) else "N/A"
            cycle_life_str = str(cycle_life_80) if isinstance(cycle_life_80, (int, float)) else "N/A"
            
            # Create slide with bullet points
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = f"{testnum} Summary"
            
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
            content.text = ""
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
            plot_df = df_cell[:-1] if remove_last_cycle else df_cell
            x_col = df_cell.columns[0]
            label_eff = f"{testnum} Efficiency" if testnum else 'Cell 1 Efficiency'
            show_eff_in_ppt = show_efficiency_lines.get(label_eff, False)
            
            if show_eff_in_ppt:
                fig, ax1 = plt.subplots()
                ax2 = ax1.twinx()
                
                label_dis = f"{testnum} Q Dis" if testnum else 'Q Dis'
                label_chg = f"{testnum} Q Chg" if testnum else 'Q Chg'
                if show_lines.get(label_dis, False):
                    ax1.plot(plot_df[x_col], plot_df['Q Dis (mAh/g)'], label=label_dis, marker='o')
                if show_lines.get(label_chg, False):
                    ax1.plot(plot_df[x_col], plot_df['Q Chg (mAh/g)'], label=label_chg, marker='o')
                
                if 'Efficiency (-)' in plot_df.columns and not plot_df['Efficiency (-)'].empty:
                    efficiency_pct = plot_df['Efficiency (-)'] * 100
                    ax2.plot(plot_df[x_col], efficiency_pct, label=f'{testnum} Efficiency (%)' if testnum else 'Cell 1 Efficiency (%)', 
                            linestyle='--', marker='s', alpha=0.7)
                
                ax1.set_xlabel(str(x_col))
                ax1.set_ylabel('Capacity (mAh/g)', color='blue')
                ax2.set_ylabel('Efficiency (%)', color='red')
                ax1.set_title('Gravimetric Capacity and Efficiency vs. ' + str(x_col))
                ax1.tick_params(axis='y', labelcolor='blue')
                ax2.tick_params(axis='y', labelcolor='red')
                lines1, labels1 = ax1.get_legend_handles_labels()
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
            else:
                fig, ax = plt.subplots()
                label_dis = f"{testnum} Q Dis" if testnum else 'Q Dis'
                label_chg = f"{testnum} Q Chg" if testnum else 'Q Chg'
                if show_lines.get(label_dis, False):
                    ax.plot(plot_df[x_col], plot_df['Q Dis (mAh/g)'], label=label_dis, marker='o')
                if show_lines.get(label_chg, False):
                    ax.plot(plot_df[x_col], plot_df['Q Chg (mAh/g)'], label=label_chg, marker='o')
                ax.set_xlabel(str(x_col))
                ax.set_ylabel('Capacity (mAh/g)')
                ax.set_title('Gravimetric Capacity vs. ' + str(x_col))
                ax.legend()
            
            # Add graph to slide
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
            st.download_button('Download PowerPoint Summary', data=pptx_bytes, file_name=pptx_file_name, mime='application/vnd.openxmlformats-officedocument.presentationml.presentation')
            
        else:
            # Multiple cells - use table format
            slide = prs.slides.add_slide(prs.slide_layouts[1])  # Title and Content layout
            slide.shapes.title.text = "Cell Comparison Summary"
            # Set title font size to 30
            slide.shapes.title.text_frame.paragraphs[0].font.size = Pt(30)
            
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
            headers = ["Cell", "1st Cycle Discharge Capacity (mAh/g)", "First Cycle Efficiency (%)", "Cycle Life (80%)"]
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
                cycle_life_80 = None
                try:
                    if not df_cell['Q Dis (mAh/g)'].empty:
                        qdis_raw = df_cell['Q Dis (mAh/g)']
                        if np.isscalar(qdis_raw):
                            qdis_series = pd.Series([qdis_raw]).dropna()
                        else:
                            qdis_series = pd.Series(qdis_raw).dropna()
                        if not qdis_series.empty:
                            initial_qdis = qdis_series.iloc[0]
                            threshold = 0.8 * initial_qdis
                            below_threshold = qdis_series <= threshold
                            if below_threshold.any():
                                first_below_idx = below_threshold.idxmin()
                                cycle_life_80 = int(df_cell.loc[first_below_idx, df_cell.columns[0]])
                            else:
                                cycle_life_80 = int(df_cell[df_cell.columns[0]].iloc[-1])
                except Exception:
                    cycle_life_80 = None
                
                cycle_life_str = str(cycle_life_80) if isinstance(cycle_life_80, (int, float)) else "N/A"
                table_data.append([cell_name, qdis_str, eff_str, cycle_life_str])
            
            # Add average row if requested
            if show_averages:
                avg_qdis_values = []
                avg_eff_values = []
                avg_cycle_life_values = []
                
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
                        if not df_cell['Q Dis (mAh/g)'].empty:
                            qdis_raw = df_cell['Q Dis (mAh/g)']
                            if np.isscalar(qdis_raw):
                                qdis_series = pd.Series([qdis_raw]).dropna()
                            else:
                                qdis_series = pd.Series(qdis_raw).dropna()
                            if not qdis_series.empty:
                                initial_qdis = qdis_series.iloc[0]
                                threshold = 0.8 * initial_qdis
                                below_threshold = qdis_series <= threshold
                                if below_threshold.any():
                                    first_below_idx = below_threshold.idxmin()
                                    cycle_life_80 = int(df_cell.loc[first_below_idx, df_cell.columns[0]])
                                else:
                                    cycle_life_80 = int(df_cell[df_cell.columns[0]].iloc[-1])
                                avg_cycle_life_values.append(cycle_life_80)
                    except Exception:
                        pass
                
                # Calculate averages
                avg_qdis = sum(avg_qdis_values) / len(avg_qdis_values) if avg_qdis_values else 0
                avg_eff = sum(avg_eff_values) / len(avg_eff_values) if avg_eff_values else 0
                avg_cycle_life = sum(avg_cycle_life_values) / len(avg_cycle_life_values) if avg_cycle_life_values else 0
                
                table_data.append(["AVERAGE", f"{avg_qdis:.1f}", f"{avg_eff:.1f}%", f"{avg_cycle_life:.0f}"])
            
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
            fig, ax = plt.subplots(figsize=(8, 5))
            for i, d in enumerate(dfs):
                try:
                    cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                    label_dis = f"{cell_name} Q Dis"
                    label_chg = f"{cell_name} Q Chg"
                    plot_df = d['df'][:-1] if remove_last_cycle else d['df']
                    dataset_x_col = plot_df.columns[0]
                    
                    if show_lines.get(label_dis, False):
                        ax.plot(plot_df[dataset_x_col], plot_df['Q Dis (mAh/g)'], label=label_dis, marker='o')
                    if show_lines.get(label_chg, False):
                        ax.plot(plot_df[dataset_x_col], plot_df['Q Chg (mAh/g)'], label=label_chg, marker='o')
                except Exception as e:
                    st.error(f"Error plotting cell {i+1} for PowerPoint: {str(e)}")
            
            ax.set_xlabel('Cycle')
            ax.set_ylabel('Capacity (mAh/g)')
            ax.set_title('Cell Comparison - Gravimetric Capacity vs. Cycle')
            ax.legend()
            
            # Add graph to slide with proper aspect ratio
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
            st.download_button('Download PowerPoint Summary', data=pptx_bytes, file_name=pptx_file_name, mime='application/vnd.openxmlformats-officedocument.presentationml.presentation')

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
        cycle_life_80 = None
        try:
            if not df_cell['Q Dis (mAh/g)'].empty:
                qdis_raw = df_cell['Q Dis (mAh/g)']
                if np.isscalar(qdis_raw):
                    qdis_series = pd.Series([qdis_raw]).dropna()
                else:
                    qdis_series = pd.Series(qdis_raw).dropna()
                if not qdis_series.empty:
                    initial_qdis = qdis_series.iloc[0]
                    threshold = 0.8 * initial_qdis
                    below_threshold = qdis_series <= threshold
                    if below_threshold.any():
                        first_below_idx = below_threshold.idxmin()
                        cycle_life_80 = int(df_cell.loc[first_below_idx, df_cell.columns[0]])
                    else:
                        cycle_life_80 = int(df_cell[df_cell.columns[0]].iloc[-1])
        except Exception as e:
            cycle_life_80 = None
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
            cycle_life_80 = None
            try:
                if not df_cell['Q Dis (mAh/g)'].empty:
                    qdis_raw = df_cell['Q Dis (mAh/g)']
                    if np.isscalar(qdis_raw):
                        qdis_series = pd.Series([qdis_raw]).dropna()
                    else:
                        qdis_series = pd.Series(qdis_raw).dropna()
                    if not qdis_series.empty:
                        initial_qdis = qdis_series.iloc[0]
                        threshold = 0.8 * initial_qdis
                        below_threshold = qdis_series <= threshold
                        if below_threshold.any():
                            first_below_idx = below_threshold.idxmin()
                            cycle_life_80 = int(df_cell.loc[first_below_idx, df_cell.columns[0]])
                        else:
                            cycle_life_80 = int(df_cell[df_cell.columns[0]].iloc[-1])
            except Exception:
                cycle_life_80 = None
            
            # Write to summary sheet
            row = i + 2  # Start from row 2 (row 1 is headers)
            ws_summary[f'A{row}'] = cell_name
            ws_summary[f'B{row}'] = max_qdis if isinstance(max_qdis, (int, float)) and max_qdis is not None else ''
            ws_summary[f'C{row}'] = eff_pct if isinstance(eff_pct, (int, float)) and eff_pct is not None else ''
            ws_summary[f'D{row}'] = cycle_life_80 if cycle_life_80 is not None else ''
        
        # Add average row if show_averages is True
        if show_averages:
            # Calculate averages
            avg_qdis_values = []
            avg_eff_values = []
            avg_cycle_life_values = []
            
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
                    if not df_cell['Q Dis (mAh/g)'].empty:
                        qdis_raw = df_cell['Q Dis (mAh/g)']
                        if np.isscalar(qdis_raw):
                            qdis_series = pd.Series([qdis_raw]).dropna()
                        else:
                            qdis_series = pd.Series(qdis_raw).dropna()
                        if not qdis_series.empty:
                            initial_qdis = qdis_series.iloc[0]
                            threshold = 0.8 * initial_qdis
                            below_threshold = qdis_series <= threshold
                            if below_threshold.any():
                                first_below_idx = below_threshold.idxmin()
                                cycle_life_80 = int(df_cell.loc[first_below_idx, df_cell.columns[0]])
                            else:
                                cycle_life_80 = int(df_cell[df_cell.columns[0]].iloc[-1])
                            avg_cycle_life_values.append(cycle_life_80)
                except Exception:
                    pass
            
            # Add average row
            avg_row = len(dfs) + 2
            ws_summary[f'A{avg_row}'] = 'Average'
            ws_summary[f'B{avg_row}'] = sum(avg_qdis_values) / len(avg_qdis_values) if avg_qdis_values else ''
            ws_summary[f'C{avg_row}'] = sum(avg_eff_values) / len(avg_eff_values) if avg_eff_values else ''
            ws_summary[f'D{avg_row}'] = sum(avg_cycle_life_values) / len(avg_cycle_life_values) if avg_cycle_life_values else ''
        
        # Move summary tab to the leftmost position
        wb._sheets.insert(0, wb._sheets.pop(wb._sheets.index(ws_summary)))
    
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