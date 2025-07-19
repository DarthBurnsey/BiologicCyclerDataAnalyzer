import streamlit as st
import pandas as pd
import io
from openpyxl import load_workbook
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, date
import re

def extract_date_from_filename(filename):
    match = re.search(r'(\d{6})', filename)
    if match:
        yymmdd = match.group(1)
        try:
            parsed_date = datetime.strptime(yymmdd, "%y%m%d").date()
            return parsed_date
        except ValueError:
            return None
    return None
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

# =============================
# Battery Data Gravimetric Capacity Calculator App
# =============================

# --- Sidebar ---
with st.sidebar:
    # Logo section - use local logo file if available, otherwise placeholder
    try:
        st.image("logo.png", width=150)
    except:
        st.image("https://placehold.co/150x80?text=Logo", width=150)
    st.title("CellScope")
    st.markdown("---")
    # Move experiment name input above file upload
    experiment_name = st.text_input('Experiment Name (optional)', placeholder='Enter experiment name for file naming and summary tab')
    st.markdown("#### Upload Data")
    datasets = render_cell_inputs()
    default_date = None
    if datasets and datasets[0]['file'] is not None:
        parsed = extract_date_from_filename(datasets[0]['file'].name)
        if parsed:
            default_date = parsed
    # Move disc diameter input here
    disc_diameter_mm = st.number_input('Disc Diameter (mm) for Areal Capacity Calculation', min_value=1, max_value=50, value=15, step=1, key='disc_diameter_mm')
    experiment_date = st.date_input(
        "Experiment Date (optional)", 
        value=default_date if default_date else date.today(),
        help="Date associated with this experiment. Parsed from filename if possible."
    )
    st.markdown("---")
    st.markdown("#### Global Options")
    # Grouping and averages toggles (move from main area)
    enable_grouping = False
    show_averages = False
    group_assignments = None
    group_names = ["Group A", "Group B", "Group C"]
    if datasets and len(datasets) > 1:
        enable_grouping = st.checkbox('Assign Cells into Groups?')
        if enable_grouping:
            with st.expander('Cell Group Assignment', expanded=True):
                group_names[0] = st.text_input('Name for Group A', value='Group A', key='group_name_a')
                group_names[1] = st.text_input('Name for Group B', value='Group B', key='group_name_b')
                group_names[2] = st.text_input('Name for Group C', value='Group C', key='group_name_c')
                group_assignments = []
                for i, cell in enumerate(datasets):
                    group = st.radio(
                        f"Assign {cell['testnum'] or f'Cell {i+1}'} to group:",
                        [group_names[0], group_names[1], group_names[2], "Exclude"],
                        key=f"group_assignment_{i}",
                        horizontal=True
                    )
                    group_assignments.append(group)
            show_averages = st.checkbox("Show Group Averages", value=True)
    st.markdown("---")
    st.markdown("**About:** This app analyzes battery cycling data and generates summary tables, plots, and exportable reports.")

# --- Main Area: Tabs Layout ---
tab1, tab2, tab3 = st.tabs(["📊 Summary", "📈 Plots", "📤 Export"])

# --- Data Preprocessing Section ---
valid_datasets = []
for ds in datasets:
    if ds['file'] and ds['loading'] > 0 and 0 < ds['active'] <= 100:
        valid_datasets.append(ds)
ready = len(valid_datasets) > 0
if ready:
    disc_area_cm2 = np.pi * (disc_diameter_mm / 2 / 10) ** 2
    dfs = load_and_preprocess_data(valid_datasets)
    # After loading and preprocessing, re-attach the latest formation_cycles to each dfs entry
    for i, d in enumerate(dfs):
        d['formation_cycles'] = valid_datasets[i]['formation_cycles']
    # --- Group Average Curve Calculation for Plotting ---
    group_curves = []
    if enable_grouping and group_assignments is not None:
        group_dfs = [[], [], []]
        for idx, name in enumerate(group_names):
            group_dfs[idx] = [df for df, g in zip(dfs, group_assignments) if g == name]
        def compute_group_avg_curve(group_dfs):
            if not group_dfs:
                return None, None, None, None
            dfs_trimmed = [d['df'] for d in group_dfs]
            x_col = dfs_trimmed[0].columns[0]
            common_cycles = set(dfs_trimmed[0][x_col])
            for df in dfs_trimmed[1:]:
                common_cycles = common_cycles & set(df[x_col])
            common_cycles = sorted(list(common_cycles))
            if not common_cycles:
                return None, None, None, None
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
            return common_cycles, avg_qdis, avg_qchg, avg_eff
        group_curves = [compute_group_avg_curve(group_dfs[idx]) for idx in range(3)]
    # --- Main Tabs Content ---
    with tab1:
        st.header("📊 Summary Tables")
        st.markdown("---")
        # Add toggle for showing average column
        show_average_col = False
        if len(dfs) > 1:
            show_average_col = st.toggle("Show average column", value=True, key="show_average_col_toggle")
        st.markdown("#### Summary Table")
        display_summary_stats(dfs, disc_area_cm2, show_average_col, group_assignments, group_names)
    with tab2:
        st.header("📈 Main Plot")
        st.markdown("---")
        show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers, hide_legend, group_plot_toggles = render_toggle_section(dfs, enable_grouping=enable_grouping)
        fig = plot_capacity_graph(
            dfs, show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, experiment_name,
            show_average_performance, avg_line_toggles, remove_markers, hide_legend,
            group_a_curve=(group_curves[0][0], group_curves[0][1]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][1] and group_plot_toggles.get("Group Q Dis", False) else None,
            group_b_curve=(group_curves[1][0], group_curves[1][1]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][1] and group_plot_toggles.get("Group Q Dis", False) else None,
            group_c_curve=(group_curves[2][0], group_curves[2][1]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][1] and group_plot_toggles.get("Group Q Dis", False) else None,
            group_a_qchg=(group_curves[0][0], group_curves[0][2]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][2] and group_plot_toggles.get("Group Q Chg", False) else None,
            group_b_qchg=(group_curves[1][0], group_curves[1][2]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][2] and group_plot_toggles.get("Group Q Chg", False) else None,
            group_c_qchg=(group_curves[2][0], group_curves[2][2]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][2] and group_plot_toggles.get("Group Q Chg", False) else None,
            group_a_eff=(group_curves[0][0], group_curves[0][3]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][3] and group_plot_toggles.get("Group Efficiency", False) else None,
            group_b_eff=(group_curves[1][0], group_curves[1][3]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][3] and group_plot_toggles.get("Group Efficiency", False) else None,
            group_c_eff=(group_curves[2][0], group_curves[2][3]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][3] and group_plot_toggles.get("Group Efficiency", False) else None,
            group_names=group_names
        )
        st.pyplot(fig)
    with tab3:
        st.header("📤 Export & Download")
        st.markdown("---")
        # PowerPoint and Excel export logic (move from main area)
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN
        from pptx.dml.color import RGBColor
        import tempfile
        # Only show export buttons if data is ready
        if ready:
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
                    show_average_performance, avg_line_toggles, remove_markers, hide_legend
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
                st.download_button(f'Download PowerPoint: {pptx_file_name}', data=pptx_bytes, file_name=pptx_file_name, mime='application/vnd.openxmlformats-officedocument.presentationml.presentation', key='download_pptx_single')
                
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
                headers = ["Cell", "1st Cycle Discharge Capacity (mAh/g)", "First Cycle Efficiency (%)", "Cycle Life (80%)", "Initial Areal Capacity (mAh/cm²)", "Reversible Capacity (mAh/g)", "Coulombic Efficiency (post-formation)"]
                table_data.append(headers)
                
                # Individual cells
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
                            try:
                                pq = float(prev_qdis)
                                cq = float(curr_qdis)
                                pe = float(prev_eff)
                                ce = float(curr_eff)
                                if pq > 0 and (cq < 0.95 * pq or ce < 0.95 * pe):
                                    break
                                ceff_values.append(ce)
                                prev_qdis = cq
                                prev_eff = ce
                            except (ValueError, TypeError):
                                # Skip this cycle if any value is not numeric
                                continue
                    if ceff_values:
                        ceff_str = f"{sum(ceff_values)/len(ceff_values)*100:.2f}%"
                    else:
                        ceff_str = "N/A"
                    table_data.append([cell_name, qdis_str, eff_str, cycle_life_str, areal_str, reversible_str, ceff_str])
                # Prepare group summary rows (A, B, C) to insert before the average row
                group_summary_rows = []
                if enable_grouping and group_assignments is not None:
                    for group_idx, group_name in enumerate(group_names):
                        group_dfs = [df for df, g in zip(dfs, group_assignments) if g == group_name]
                        if len(group_dfs) > 1:
                            avg_qdis_values = []
                            avg_eff_values = []
                            avg_cycle_life_values = []
                            avg_areal_capacity_values = []
                            avg_reversible_capacities = []
                            avg_ceff_values = []
                            for d in group_dfs:
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
                            group_summary_rows.append([
                                group_name + " (Group Avg)",
                                f"{avg_qdis:.1f}",
                                f"{avg_eff:.1f}%",
                                f"{avg_cycle_life:.0f}",
                                f"{avg_areal:.3f}",
                                f"{avg_reversible:.1f}" if avg_reversible is not None else "N/A",
                                f"{avg_ceff:.2f}%" if avg_ceff is not None else "N/A"
                            ])
                # Add average row for all cells at the end of the PowerPoint table
                # Calculate averages for each parameter
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
                    qdis_series = get_qdis_series(df_cell)
                    cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
                    cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
                    if cycle_life_80 is not None:
                        avg_cycle_life_values.append(cycle_life_80)
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
                        for i in range(formation_cycles+1, n_cycles):
                            curr_qdis = df_cell[qdis_col].iloc[i]
                            curr_eff = df_cell[eff_col].iloc[i]
                            try:
                                pq = float(prev_qdis)
                                cq = float(curr_qdis)
                                pe = float(prev_eff)
                                ce = float(curr_eff)
                                if pq > 0 and (cq < 0.95 * pq or ce < 0.95 * pe):
                                    break
                                ceff_values.append(ce)
                                prev_qdis = cq
                                prev_eff = ce
                            except (ValueError, TypeError):
                                continue
                    if ceff_values:
                        avg_ceff = sum(ceff_values) / len(ceff_values) * 100
                        avg_ceff_values.append(avg_ceff)
                avg_qdis = sum(avg_qdis_values) / len(avg_qdis_values) if avg_qdis_values else 0
                avg_eff = sum(avg_eff_values) / len(avg_eff_values) if avg_eff_values else 0
                avg_cycle_life = sum(avg_cycle_life_values) / len(avg_cycle_life_values) if avg_cycle_life_values else 0
                avg_areal = sum(avg_areal_capacity_values) / len(avg_areal_capacity_values) if avg_areal_capacity_values else 0
                avg_reversible = sum(avg_reversible_capacities) / len(avg_reversible_capacities) if avg_reversible_capacities else None
                avg_ceff = sum(avg_ceff_values) / len(avg_ceff_values) if avg_ceff_values else None
                table_data.append([
                    "AVERAGE",
                    f"{avg_qdis:.1f}",
                    f"{avg_eff:.1f}%",
                    f"{avg_cycle_life:.0f}",
                    f"{avg_areal:.3f}",
                    f"{avg_reversible:.1f}" if avg_reversible is not None else "N/A",
                    f"{avg_ceff:.2f}%" if avg_ceff is not None else "N/A"
                ])
                
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
                        elif i == len(table_data) - 1:
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
                    show_average_performance, avg_line_toggles, remove_markers, hide_legend,
                    group_a_curve=(group_curves[0][0], group_curves[0][1]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][1] else None,
                    group_b_curve=(group_curves[1][0], group_curves[1][1]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][1] else None,
                    group_c_curve=(group_curves[2][0], group_curves[2][1]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][1] else None,
                    group_a_qchg=(group_curves[0][0], group_curves[0][2]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][2] else None,
                    group_b_qchg=(group_curves[1][0], group_curves[1][2]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][2] else None,
                    group_c_qchg=(group_curves[2][0], group_curves[2][2]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][2] else None,
                    group_a_eff=(group_curves[0][0], group_curves[0][3]) if enable_grouping and group_curves and group_curves[0][0] and group_curves[0][3] else None,
                    group_b_eff=(group_curves[1][0], group_curves[1][3]) if enable_grouping and group_curves and group_curves[1][0] and group_curves[1][3] else None,
                    group_c_eff=(group_curves[2][0], group_curves[2][3]) if enable_grouping and group_curves and group_curves[2][0] and group_curves[2][3] else None,
                    group_names=group_names
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
                st.download_button(f'Download PowerPoint: {pptx_file_name}', data=pptx_bytes, file_name=pptx_file_name, mime='application/vnd.openxmlformats-officedocument.presentationml.presentation', key='download_pptx_multiple')

            # --- Excel Export ---
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
                ws['A1'] = 'Total loading (mg)'
                ws['B1'] = d['loading']
                ws['A2'] = 'Active material loading (mg)'
                ws['B2'] = d['loading'] * (d['active'] / 100)
                first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
                max_qdis = max(first_three_qdis) if first_three_qdis else None
                if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
                    first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
                    eff_pct = first_cycle_eff * 100
                else:
                    eff_pct = None
                qdis_series = get_qdis_series(df_cell)
                cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
                cycle_life_80 = calculate_cycle_life_80(qdis_series, cycle_index_series)
                ws['P1'] = '1st Cycle Discharge Capacity (mAh/g)'
                ws['Q1'] = f"{max_qdis:.1f}" if isinstance(max_qdis, (int, float)) and max_qdis is not None else ''
                ws['P2'] = 'First Cycle Efficiency (%)'
                ws['Q2'] = f"{eff_pct:.1f}" if isinstance(eff_pct, (int, float)) and eff_pct is not None else ''
                ws['P3'] = 'Cycle Life (80%)'
                ws['Q3'] = cycle_life_80 if cycle_life_80 is not None else ''
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

            # Add summary worksheet if multiple cells
            if len(dfs) > 1:
                summary_sheet_name = f"{experiment_name} Summary" if experiment_name else "Summary"
                summary_sheet_name = summary_sheet_name[:31]  # Excel sheet names limited to 31 characters
                ws_summary = wb.create_sheet(summary_sheet_name)
                # Move summary sheet to the first position (leftmost tab)
                wb._sheets.insert(0, wb._sheets.pop(wb._sheets.index(ws_summary)))
                # Write headers
                ws_summary['A1'] = 'Cell'
                ws_summary['B1'] = '1st Cycle Discharge Capacity (mAh/g)'
                ws_summary['C1'] = 'First Cycle Efficiency (%)'
                ws_summary['D1'] = 'Cycle Life (80%)'
                ws_summary['E1'] = 'Initial Areal Capacity (mAh/cm²)'
                ws_summary['F1'] = 'Reversible Capacity (mAh/g)'
                ws_summary['G1'] = 'Coulombic Efficiency (post-formation)'
                # Write data for each cell
                for i, d in enumerate(dfs):
                    df_cell = d['df']
                    cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                    # Calculate summary values (same as in your summary table)
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
                            try:
                                pq = float(prev_qdis)
                                cq = float(curr_qdis)
                                pe = float(prev_eff)
                                ce = float(curr_eff)
                                if pq > 0 and (cq < 0.95 * pq or ce < 0.95 * pe):
                                    break
                                ceff_values.append(ce)
                                prev_qdis = cq
                                prev_eff = ce
                            except (ValueError, TypeError):
                                # Skip this cycle if any value is not numeric
                                continue
                    if ceff_values:
                        ceff_str = f"{sum(ceff_values)/len(ceff_values)*100:.2f}%"
                    else:
                        ceff_str = "N/A"
                    ws_summary[f'A{i+2}'] = cell_name
                    ws_summary[f'B{i+2}'] = qdis_str
                    ws_summary[f'C{i+2}'] = eff_str
                    ws_summary[f'D{i+2}'] = cycle_life_str
                    ws_summary[f'E{i+2}'] = areal_str
                    ws_summary[f'F{i+2}'] = reversible_str
                    ws_summary[f'G{i+2}'] = ceff_str
                # Optionally, add group/average rows as well
                if enable_grouping and group_assignments is not None:
                    for group_idx, group_name in enumerate(group_names):
                        group_dfs = [df for df, g in zip(dfs, group_assignments) if g == group_name]
                        if len(group_dfs) > 1:
                            avg_qdis_values = []
                            avg_eff_values = []
                            avg_cycle_life_values = []
                            avg_areal_capacity_values = []
                            avg_reversible_capacities = []
                            avg_ceff_values = []
                            for d in group_dfs:
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
                            ws_summary.append([
                                group_name + " (Group Avg)",
                                f"{avg_qdis:.1f}",
                                f"{avg_eff:.1f}%",
                                f"{avg_cycle_life:.0f}",
                                f"{avg_areal:.3f}",
                                f"{avg_reversible:.1f}" if avg_reversible is not None else "N/A",
                                f"{avg_ceff:.2f}%" if avg_ceff is not None else "N/A"
                            ])
            # Save the updated workbook
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
            st.download_button(f'Download XLSX: {file_name}', data=output2, file_name=file_name, mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key='download_xlsx_final')

else:
    st.info('Please upload a file and enter valid disc loading and % active material.')   