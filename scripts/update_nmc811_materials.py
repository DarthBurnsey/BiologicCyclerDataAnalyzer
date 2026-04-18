#!/usr/bin/env python3
"""
Script to update NMC811 materials in CellScope experiments.
- Experiments up to N5: NMC811 -> NMC811 (MSE)
- Experiments from N9 onward: NMC811 -> NMC811 (BASF)
"""

import sqlite3
import json
import sys
import os

# Add the current directory to Python path to import database module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def update_nmc811_materials():
    """Update NMC811 materials in experiment formulations."""

    # Define which experiments get which material
    mse_experiments = [
        'N1a', 'N1b', 'N2a', 'N2a - repaired', 'N4a', 'N4b', 'N4c', 'N5a', 'N5g'
    ]

    basf_experiments = [
        'N9', 'N10a', 'N10e', 'N10n', 'N10d'
    ]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get all experiments with formulations
        cursor.execute('''
            SELECT id, cell_name, formulation_json, data_json
            FROM cell_experiments
            WHERE formulation_json IS NOT NULL OR data_json IS NOT NULL
        ''')

        experiments = cursor.fetchall()
        updated_count = 0

        for exp_id, cell_name, formulation_json, data_json in experiments:
            updated = False

            # Determine which material to use
            if cell_name in mse_experiments:
                new_material = 'NMC811 (MSE)'
            elif cell_name in basf_experiments:
                new_material = 'NMC811 (BASF)'
            else:
                continue  # Skip experiments not in our lists

            print(f"Processing experiment {cell_name} -> {new_material}")

            # Update formulation_json field
            if formulation_json:
                try:
                    formulation = json.loads(formulation_json)
                    if isinstance(formulation, list):
                        for item in formulation:
                            if isinstance(item, dict) and item.get('Component') == 'NMC811':
                                item['Component'] = new_material
                                updated = True

                        if updated:
                            new_formulation_json = json.dumps(formulation)
                            cursor.execute('''
                                UPDATE cell_experiments
                                SET formulation_json = ?
                                WHERE id = ?
                            ''', (new_formulation_json, exp_id))

                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing formulation_json for {cell_name}: {e}")

            # Update formulations in data_json (for multi-cell experiments)
            if data_json:
                try:
                    data = json.loads(data_json)
                    if 'cells' in data:
                        for cell in data['cells']:
                            formulation = cell.get('formulation', [])
                            if isinstance(formulation, list):
                                for item in formulation:
                                    if isinstance(item, dict) and item.get('Component') == 'NMC811':
                                        item['Component'] = new_material
                                        updated = True

                        if updated:
                            new_data_json = json.dumps(data)
                            cursor.execute('''
                                UPDATE cell_experiments
                                SET data_json = ?
                                WHERE id = ?
                            ''', (new_data_json, exp_id))

                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing data_json for {cell_name}: {e}")

            if updated:
                updated_count += 1
                print(f"  Updated {cell_name}")

        # Update project last_modified
        cursor.execute('''
            UPDATE projects
            SET last_modified = CURRENT_TIMESTAMP
        ''')

        conn.commit()
        print(f"\nCompleted! Updated {updated_count} experiments.")

if __name__ == '__main__':
    update_nmc811_materials()