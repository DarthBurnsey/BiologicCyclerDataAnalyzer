import streamlit as st
import pandas as pd
import io
from openpyxl import load_workbook
import matplotlib.pyplot as plt

st.title('Battery Data Gravimetric Capacity Calculator')
st.write('Upload your Biologic-style CSV file, enter disc loading and % active material, and download the processed XLSX file.')

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
for i, idx in enumerate(st.session_state['cell_indices']):
    with header_cols[i]:
        col_head = st.columns([8,1])
        with col_head[0]:
            st.markdown(f'**Cell {i+1}**')
        with col_head[1]:
            if i > 0:
                if st.button('➖', key=f'remove_{idx}'):
                    st.session_state['cell_indices'].remove(idx)
                    st.rerun()
with cols[-1]:
    if len(st.session_state['cell_indices']) < 6:
        if st.button('➕ Add Comparison'):
            st.session_state['cell_indices'].append(st.session_state['next_cell_idx'])
            st.session_state['next_cell_idx'] += 1
            st.rerun()

# Store all dataset info
datasets = []
for i, idx in enumerate(st.session_state['cell_indices']):
    with cols[i]:
        uploaded_file = st.file_uploader(f'Upload CSV file for Cell {i+1}', type=['csv'], key=f'file_{idx}')
        disc_loading = st.number_input(f'Disc loading (mg) for Cell {i+1}', min_value=0.0, step=1.0, value=20.0, key=f'loading_{idx}')
        active_material = st.number_input(f'% Active material for Cell {i+1}', min_value=0.0, max_value=100.0, step=0.01, value=90.0, key=f'active_{idx}')
        test_number = st.text_input(f'Test Number for Cell {i+1}', key=f'testnum_{idx}')
        datasets.append({'file': uploaded_file, 'loading': disc_loading, 'active': active_material, 'testnum': test_number})

# Process and plot if at least the first dataset is ready
ready = datasets[0]['file'] and datasets[0]['loading'] > 0 and 0 < datasets[0]['active'] <= 100
if ready:
    dfs = []
    for idx, ds in enumerate(datasets):
        if ds['file'] and ds['loading'] > 0 and 0 < ds['active'] <= 100:
            df = pd.read_csv(ds['file'], delimiter=';')
            active_mass = (ds['loading'] / 1000) * (ds['active'] / 100)
            df['Q Chg (mAh/g)'] = df['Q charge (mA.h)'] / active_mass
            df['Q Dis (mAh/g)'] = df['Q discharge (mA.h)'] / active_mass
            df['Test Number'] = ds['testnum']
            dfs.append({'df': df, 'testnum': ds['testnum']})
        else:
            dfs.append(None)

    # Prepare XLSX for download with multiple sheets
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for idx, d in enumerate(dfs):
            if d is not None:
                df_cell = d['df']
                sheet_name = d['testnum'] if d['testnum'] else f'Cell {idx+1}'
                df_cell.to_excel(writer, index=False, startrow=4, sheet_name=sheet_name)
    output.seek(0)

    # Add summary values and native Excel chart to each sheet
    from openpyxl import load_workbook
    from openpyxl.chart import LineChart, Reference
    output.seek(0)
    wb = load_workbook(output)
    for idx, d in enumerate(dfs):
        if d is not None:
            ws = wb[d['testnum'] if d['testnum'] else f'Cell {idx+1}']
            df_cell = d['df']
            # Total loading and active material loading
            ws['A1'] = 'Total loading (mg)'
            ws['B1'] = datasets[idx]['loading']
            ws['A2'] = 'Active material loading (mg)'
            ws['B2'] = datasets[idx]['loading'] * (datasets[idx]['active'] / 100)
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
            if not df_cell['Q Dis (mAh/g)'].empty:
                initial_qdis = df_cell['Q Dis (mAh/g)'].iloc[0]
                threshold = 0.8 * initial_qdis
                below_80 = df_cell[df_cell['Q Dis (mAh/g)'] <= threshold]
                if not below_80.empty:
                    cycle_life_80 = int(below_80.iloc[0][df_cell.columns[0]])
                else:
                    cycle_life_80 = int(df_cell[df_cell.columns[0]].iloc[-1])
            # Write to Excel
            ws['P1'] = '1st Cycle Discharge Capacity (mAh/g)'
            ws['Q1'] = f"{max_qdis:.1f}" if max_qdis is not None else ''
            ws['P2'] = 'First Cycle Efficiency (%)'
            ws['Q2'] = f"{eff_pct:.1f}" if eff_pct is not None else ''
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
    output2 = io.BytesIO()
    wb.save(output2)
    output2.seek(0)

    file_name = 'Comparison Cycling data.xlsx' if len(dfs) > 1 else f'{datasets[0]["testnum"]} Cycling data.xlsx' if datasets[0]["testnum"] else 'Cycling data.xlsx'
    st.success('Processing complete!')
    st.download_button(f'Download XLSX: {file_name}', data=output2, file_name=file_name, mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # Filtering options for the plot
    # Remove the initial two filters for the graph (Show Discharge Capacity and Show Charge Capacity)
    # (No code for st.checkbox('Show Discharge Capacity', ...) or st.checkbox('Show Charge Capacity', ...))

    # Build all possible line labels
    line_labels = []
    for d in dfs:
        if d is not None:
            label_dis = f"{d['testnum']} Q Dis" if d['testnum'] else 'Q Dis'
            label_chg = f"{d['testnum']} Q Chg" if d['testnum'] else 'Q Chg'
            line_labels.append(label_dis)
            line_labels.append(label_chg)

    # Create a checkbox for each line label
    show_lines = {}
    for label in line_labels:
        show_lines[label] = st.checkbox(f"Show {label}", value=True)

    # Checkbox to remove last cycle from graph
    remove_last_cycle = st.checkbox('Remove last cycle from graph', value=False)

    # Plotting all datasets with individual line toggles
    x_col = df.columns[0]
    fig, ax = plt.subplots()
    for d in dfs:
        if d is not None:
            label_dis = f"{d['testnum']} Q Dis" if d['testnum'] else 'Q Dis'
            label_chg = f"{d['testnum']} Q Chg" if d['testnum'] else 'Q Chg'
            plot_df = d['df'][:-1] if remove_last_cycle else d['df']
            if show_lines.get(label_dis, False):
                ax.plot(plot_df[x_col], plot_df['Q Dis (mAh/g)'], label=label_dis, marker='o')
            if show_lines.get(label_chg, False):
                ax.plot(plot_df[x_col], plot_df['Q Chg (mAh/g)'], label=label_chg, marker='o')
    ax.set_xlabel(x_col)
    ax.set_ylabel('Capacity (mAh/g)')
    ax.set_title('Gravimetric Capacity vs. ' + x_col)
    ax.legend()
    st.pyplot(fig)

    # Display 1st cycle discharge capacity, first cycle efficiency, and cycle life (80%) for all cells side by side
    summary_cols = st.columns(len(dfs))
    for idx, d in enumerate(dfs):
        with summary_cols[idx]:
            if d is not None:
                df_cell = d['df']
                first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
                max_qdis = max(first_three_qdis) if first_three_qdis else None
                if max_qdis is not None:
                    st.info(f"1st Cycle Discharge Capacity (mAh/g): {max_qdis:.1f}")
                else:
                    st.warning('Not enough data for 1st cycle discharge capacity.')
                if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
                    first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
                    eff_pct = first_cycle_eff * 100
                    st.info(f"First Cycle Efficiency: {eff_pct:.1f}%")
                else:
                    st.warning('Efficiency (-) column not found in data.')
                # Cycle Life (80%)
                cycle_life_80 = None
                if not df_cell['Q Dis (mAh/g)'].empty:
                    initial_qdis = df_cell['Q Dis (mAh/g)'].iloc[0]
                    threshold = 0.8 * initial_qdis
                    below_80 = df_cell[df_cell['Q Dis (mAh/g)'] <= threshold]
                    if not below_80.empty:
                        cycle_life_80 = int(below_80.iloc[0][df_cell.columns[0]])
                    else:
                        cycle_life_80 = int(df_cell[df_cell.columns[0]].iloc[-1])
                st.info(f"Cycle Life (80%): {cycle_life_80 if cycle_life_80 is not None else 'N/A'}")

    # --- PowerPoint Export for First Cell ---
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    import tempfile

    if dfs and dfs[0] is not None:
        df_cell = dfs[0]['df']
        testnum = datasets[0]['testnum'] if datasets[0]['testnum'] else 'Cell 1'
        # Summary values
        first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
        max_qdis = max(first_three_qdis) if first_three_qdis else None
        if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
            first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
            eff_pct = first_cycle_eff * 100
        else:
            eff_pct = None
        # Cycle Life (80%) calculation for PowerPoint
        cycle_life_80 = None
        if not df_cell['Q Dis (mAh/g)'].empty:
            initial_qdis = df_cell['Q Dis (mAh/g)'].iloc[0]
            threshold = 0.8 * initial_qdis
            below_80 = df_cell[df_cell['Q Dis (mAh/g)'] <= threshold]
            if not below_80.empty:
                cycle_life_80 = int(below_80.iloc[0][df_cell.columns[0]])
            else:
                cycle_life_80 = int(df_cell[df_cell.columns[0]].iloc[-1])
        # Safe formatting for summary values
        if isinstance(max_qdis, (int, float)):
            qdis_str = f"{max_qdis:.1f}"
        else:
            qdis_str = "N/A"
        if isinstance(eff_pct, (int, float)):
            eff_str = f"{eff_pct:.1f}%"
        else:
            eff_str = "N/A"
        if isinstance(cycle_life_80, (int, float)):
            cycle_life_str = str(cycle_life_80)
        else:
            cycle_life_str = "N/A"
        # Create PowerPoint
        prs = Presentation()
        # Use a Title and Content layout for the slide
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        # Set the title
        slide.shapes.title.text = f"{testnum} Summary"
        # Echem header as a separate textbox
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
        # Use the content placeholder for summary bullets
        content = slide.placeholders[1]
        content.text = ""  # Clear any default text
        p1 = content.text_frame.add_paragraph()
        p1.text = f"1st Cycle Discharge Capacity: {qdis_str} mAh/g"
        p1.level = 0  # Bullet
        p1.font.size = Pt(18)
        p2 = content.text_frame.add_paragraph()
        p2.text = f"First Cycle Efficiency: {eff_str}"
        p2.level = 0  # Bullet
        p2.font.size = Pt(18)
        p3 = content.text_frame.add_paragraph()
        p3.text = f"Cycle Life (80%): {cycle_life_str}"
        p3.level = 0  # Bullet
        p3.font.size = Pt(18)
        # Matplotlib graph for PowerPoint should match current filters
        plot_df = df_cell[:-1] if remove_last_cycle else df_cell
        fig, ax = plt.subplots()
        label_dis = f"{testnum} Q Dis" if testnum else 'Q Dis'
        label_chg = f"{testnum} Q Chg" if testnum else 'Q Chg'
        if show_lines.get(label_dis, False):
            ax.plot(plot_df[x_col], plot_df['Q Dis (mAh/g)'], label=label_dis, marker='o')
        if show_lines.get(label_chg, False):
            ax.plot(plot_df[x_col], plot_df['Q Chg (mAh/g)'], label=label_chg, marker='o')
        ax.set_xlabel(x_col)
        ax.set_ylabel('Capacity (mAh/g)')
        ax.set_title('Gravimetric Capacity vs. ' + x_col)
        ax.legend()
        img_bytes = io.BytesIO()
        fig.savefig(img_bytes, format='png', bbox_inches='tight')
        plt.close(fig)
        img_bytes.seek(0)
        # Save image to temp file for pptx
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_img:
            tmp_img.write(img_bytes.read())
            img_path = tmp_img.name
        slide.shapes.add_picture(img_path, Inches(5.5), Inches(1.2), width=Inches(4.5))
        # Download button for pptx
        pptx_bytes = io.BytesIO()
        prs.save(pptx_bytes)
        pptx_bytes.seek(0)
        st.download_button('Download PowerPoint Summary', data=pptx_bytes, file_name=f'{testnum} Summary.pptx', mime='application/vnd.openxmlformats-officedocument.presentationml.presentation')

else:
    st.info('Please upload a file and enter valid disc loading and % active material.') 