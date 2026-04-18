import os
import sys
import pandas as pd
from export import export_powerpoint

# Mock data
dfs = [{
    'testnum': 'N12b',
    'project_name': 'NMC Cathode',
    'active_material': 'NMC811(Half)',
    'formulation': [
        {'Component': 'NMC811(BASF)', 'Value': 94},
        {'Component': 'PVDF', 'Value': 3},
        {'Component': 'Super P', 'Value': 3}
    ],
    'loading': 7.61,
    'pressed_thickness': 49,
    'substrate': 'Al',
    'electrolyte': '1M LiPF6 1:1:1, 5% FEC, 2% VC',
    'separator': 'CC, 2+12+2µm',
    'cutoff_voltage_lower': 3.0,
    'cutoff_voltage_upper': 4.2,
    'formation_cycles': 3,
    'df': pd.DataFrame({
        'Cycle Number': range(1, 21),
        'Q Dis (mAh/g)': [201.3] + [191.4] * 19,
        'Efficiency (-)': [0.9014] + [0.9993] * 19
    })
}]

try:
    pptx_bytes, filename = export_powerpoint(
        dfs=dfs,
        show_averages=False,
        experiment_name='N12b',
        show_lines={'N12b': True},
        show_efficiency_lines={'N12b': True},
        remove_last_cycle=False,
        experiment_notes="Active material successfully increased.\nCapacity could be pushed with higher cutoff voltages."
    )
    with open('test_output.pptx', 'wb') as f:
        f.write(pptx_bytes.getbuffer())
    print(f"Generated successfully: {filename}")
except Exception as e:
    import traceback
    traceback.print_exc()
