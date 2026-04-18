import sqlite3
import json

db_path = 'cellscope.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT id, formulation_json FROM cell_experiments WHERE formulation_json IS NOT NULL")
rows = cursor.fetchall()

updated_count = 0
for row in rows:
    exp_id, formulation_str = row
    if not formulation_str:
        continue
        
    try:
        formulation = json.loads(formulation_str)
        changed = False
        
        for item in formulation:
            if 'Component' in item:
                if item['Component'] in ['NMC811 DASF', 'NMC811DASF']:
                    item['Component'] = 'NMC811 (BASF)'
                    changed = True
                elif item['Component'] == 'NMC811 MSC':
                    item['Component'] = 'NMC811 (MSE)'
                    changed = True
                    
        if changed:
            new_formulation_str = json.dumps(formulation)
            cursor.execute("UPDATE cell_experiments SET formulation_json = ? WHERE id = ?", (new_formulation_str, exp_id))
            updated_count += 1
            print(f"Updated formulation for experiment ID: {exp_id}")
            
    except json.JSONDecodeError:
        pass

conn.commit()
conn.close()
print(f"Finished. Updated {updated_count} experiments.")
