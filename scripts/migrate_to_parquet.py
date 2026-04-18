import sqlite3
import pandas as pd
import json
import os
import uuid
from pathlib import Path
from io import StringIO
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("migration")

DATABASE_PATH = 'cellscope.db'
DATA_DIR = Path('data/experiments')
DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_db_connection():
    return sqlite3.connect(DATABASE_PATH)

def _save_df_to_parquet(df, prefix="exp"):
    if df is None or df.empty:
        return None
    
    filename = f"{prefix}_{uuid.uuid4().hex}.parquet"
    filepath = DATA_DIR / filename
    
    try:
        df.to_parquet(filepath, engine='pyarrow', index=False)
        return str(filepath)
    except Exception as e:
        logger.error(f"Failed to save parquet file: {e}")
        return None

def migrate():
    logger.info("Starting migration to Parquet...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Ensure schema has parquet_path
    try:
        cursor.execute("ALTER TABLE cell_experiments ADD COLUMN parquet_path TEXT")
        logger.info("Added parquet_path column.")
    except sqlite3.OperationalError:
        logger.info("parquet_path column already exists.")
    
    # 2. Fetch all experiments with data
    cursor.execute("SELECT id, cell_name, data_json FROM cell_experiments WHERE data_json IS NOT NULL")
    experiments = cursor.fetchall()
    
    logger.info(f"Found {len(experiments)} experiments to process.")
    
    migrated_count = 0
    error_count = 0
    
    for exp_id, cell_name, data_json_str in experiments:
        if not data_json_str:
            continue
            
        try:
            # Check if it's already migrated (unlikely if we selected valid data_json, unless we run twice on partially migrated)
            # Actually if we set data_json to NULL, query won't pick it up.
            pass
            
            is_multi_cell = False
            updated_data_json = None
            parquet_path = None
            
            # Try to parse JSON
            try:
                data = json.loads(data_json_str)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON for experiment {exp_id} ({cell_name})")
                error_count += 1
                continue
            
            # Determine if Single or Multi Cell
            # Single cell data_json usually has structure {"Voltage": {...}, ...}
            # Multi cell has {"cells": [...], ...}
            
            if isinstance(data, dict) and 'cells' in data:
                is_multi_cell = True
                
                # Process each cell
                cells = data['cells']
                modified = False
                for cell in cells:
                    c_data_json = cell.get('data_json')
                    if c_data_json and not cell.get('parquet_path'):
                        # Convert
                        try:
                            df = pd.read_json(StringIO(c_data_json)) if isinstance(c_data_json, str) else pd.DataFrame(c_data_json)
                            if not df.empty:
                                p_path = _save_df_to_parquet(df, prefix="cell_multi")
                                if p_path:
                                    cell['parquet_path'] = p_path
                                    cell['data_json'] = None
                                    modified = True
                        except Exception as e:
                            logger.error(f"Error converting cell in experiment {exp_id}: {e}")
                
                if modified:
                    updated_data_json = json.dumps(data)
            
            else:
                # Single Cell
                try:
                    df = pd.read_json(StringIO(data_json_str)) if isinstance(data_json_str, str) else pd.DataFrame(data)
                    if not df.empty:
                        parquet_path = _save_df_to_parquet(df, prefix="cell_single")
                except Exception as e:
                    logger.error(f"Error loading single cell dataframe {exp_id}: {e}")
            
            # Update DB
            if is_multi_cell and updated_data_json:
                cursor.execute("UPDATE cell_experiments SET data_json = ? WHERE id = ?", (updated_data_json, exp_id))
                migrated_count += 1
                
            elif parquet_path:
                cursor.execute("UPDATE cell_experiments SET parquet_path = ?, data_json = NULL WHERE id = ?", (parquet_path, exp_id))
                migrated_count += 1
                
            if migrated_count % 10 == 0:
                conn.commit()
                logger.info(f"Processed {migrated_count} experiments...")
                
        except Exception as e:
            logger.error(f"Unexpected error processing experiment {exp_id}: {e}")
            error_count += 1
    
    conn.commit()
    
    # 3. Vacuum to reclaim space
    logger.info("Vacuuming database...")
    cursor.execute("VACUUM")
    
    conn.close()
    logger.info(f"Migration complete. Migrated: {migrated_count}, Errors: {error_count}")

if __name__ == "__main__":
    migrate()
