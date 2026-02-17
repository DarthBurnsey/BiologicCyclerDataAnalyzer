import sqlite3
import json
from contextlib import contextmanager
import logging
import time
import random
import os
import uuid
import pandas as pd
from pathlib import Path

DATABASE_PATH = 'cellscope.db'
SQLITE_TIMEOUT = 60

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database")

@contextmanager
def get_db_connection():
    """Simple, reliable SQLite connection context manager."""
    conn = None
    try:
        # Simple connection with minimal configuration for maximum reliability
        conn = sqlite3.connect(DATABASE_PATH, timeout=SQLITE_TIMEOUT)
        
        # Only essential pragmas
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = DELETE')  # Use default DELETE mode instead of WAL
        conn.execute('PRAGMA synchronous = FULL')     # Maximum safety
        
        yield conn
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        logger.error(f"Database error: {e}")
        raise
        
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


DATA_DIR = Path('data/experiments')
DATA_DIR.mkdir(parents=True, exist_ok=True)

def _save_df_to_parquet(df, prefix="exp"):
    """Helper to save DataFrame to Parquet and return path."""
    if df is None or df.empty:
        return None
    
    filename = f"{prefix}_{uuid.uuid4().hex}.parquet"
    filepath = DATA_DIR / filename
    
    # Ensure columns are compatible (convert complex types to string if needed)
    # Parquet handles most types well, but mixed types can be tricky.
    # We'll save using pyarrow engine.
    try:
        df.to_parquet(filepath, engine='pyarrow', index=False)
        return str(filepath)
    except Exception as e:
        logger.error(f"Failed to save parquet file: {e}")
        # Fallback or re-raise? Re-raise to prevent data loss mock-save
        raise e

def _load_df_from_parquet(filepath):
    """Helper to load DataFrame from Parquet."""
    if not filepath or not os.path.exists(filepath):
        return None
    return pd.read_parquet(filepath)

def hydrate_data_json(d_json, p_path, row_id=None):
    """Helper to hydrate data_json from parquet path(s)."""
    # Hydrate from main parquet
    if p_path and os.path.exists(p_path):
         try:
             df = _load_df_from_parquet(p_path)
             if df is not None:
                 return df.to_json()
         except Exception as e:
             if row_id:
                 logger.error(f"Error hydrating parquet data for {row_id}: {e}")
             # fall through to check d_json or return existing d_json

    # Hydrate embedded parquet (multi-cell)
    if d_json:
        try:
             # Fast check: does it contain "parquet_path"?
             if "parquet_path" in d_json:
                 data = json.loads(d_json)
                 if isinstance(data, dict) and 'cells' in data:
                     modified = False
                     for cell in data['cells']:
                         if cell.get('parquet_path') and os.path.exists(cell.get('parquet_path')):
                              try:
                                  cell_df = _load_df_from_parquet(cell['parquet_path'])
                                  if cell_df is not None:
                                      cell['data_json'] = cell_df.to_json()
                                      modified = True
                              except:
                                  pass
                     if modified:
                         return json.dumps(data)
        except:
             pass
    
    return d_json

def save_cell_experiment(project_id, cell_name, file_name, loading, active_material, formation_cycles, test_number, df, electrolyte=None, substrate=None, separator=None, group_assignment=None, formulation_json=None, max_retries=3):
    """Simple, reliable cell experiment saving with minimal complexity."""
    for attempt in range(max_retries):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Save to Parquet
                parquet_path = _save_df_to_parquet(df, prefix="cell")
                data_json = None # Clear data_json to save space
                
                # Simple single transaction
                cursor.execute('''
                    INSERT INTO cell_experiments 
                    (project_id, cell_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, separator, group_assignment, formulation_json, data_json, parquet_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (project_id, cell_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, separator, group_assignment, formulation_json, data_json, parquet_path))
                
                experiment_id = cursor.lastrowid
                
                # Update project in same transaction
                cursor.execute('''
                    UPDATE projects 
                    SET last_modified = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (project_id,))
                
                # Commit happens automatically when context manager exits successfully
                conn.commit()
                
                logger.info(f"Successfully saved experiment {cell_name}")
                return experiment_id
                
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e).lower() or 'database is busy' in str(e).lower():
                if attempt < max_retries - 1:
                    delay = 1.0 + (attempt * 0.5) + random.uniform(0.1, 0.3)
                    logger.warning(f"Database busy, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    logger.error("Database remains locked after all retries")
                    raise sqlite3.OperationalError("Database is currently busy. Please wait a moment and try again.")
            else:
                logger.error(f"SQLite error: {e}")
                raise
                
        except Exception as e:
            logger.error(f"Error saving experiment: {e}")
            raise
    
    raise sqlite3.OperationalError("Failed to save after all retries")

def init_database():
    """Initialize the database and create tables if they don't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                project_type TEXT DEFAULT 'Full Cell',
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create cell experiments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cell_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                cell_name TEXT NOT NULL,
                file_name TEXT,
                loading REAL,
                active_material REAL,
                formation_cycles INTEGER,
                test_number TEXT,
                electrolyte TEXT,
                substrate TEXT,
                formulation_json TEXT,
                data_json TEXT,
                solids_content REAL,
                pressed_thickness REAL,
                experiment_notes TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
        ''')
        
        # Create cell recipes table (for future use)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cell_recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                recipe_name TEXT NOT NULL,
                recipe_data TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
        ''')
        
        # Create project preferences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                preference_key TEXT NOT NULL,
                preference_value TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id),
                UNIQUE(project_id, preference_key)
            )
        ''')
        
        conn.commit()

def migrate_database():
    """Migrate database to add missing columns if they don't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check if columns exist in cell_experiments table
        cursor.execute("PRAGMA table_info(cell_experiments)")
        columns = [column[1] for column in cursor.fetchall()]
        
        migrations = [
            ('electrolyte', 'ALTER TABLE cell_experiments ADD COLUMN electrolyte TEXT'),
            ('substrate', 'ALTER TABLE cell_experiments ADD COLUMN substrate TEXT'),
            ('separator', 'ALTER TABLE cell_experiments ADD COLUMN separator TEXT'),
            ('formulation_json', 'ALTER TABLE cell_experiments ADD COLUMN formulation_json TEXT'),
            ('solids_content', 'ALTER TABLE cell_experiments ADD COLUMN solids_content REAL'),
            ('pressed_thickness', 'ALTER TABLE cell_experiments ADD COLUMN pressed_thickness REAL'),
            ('experiment_notes', 'ALTER TABLE cell_experiments ADD COLUMN experiment_notes TEXT'),
            ("porosity", "ALTER TABLE cell_experiments ADD COLUMN porosity REAL"),
            ('cutoff_voltage_lower', 'ALTER TABLE cell_experiments ADD COLUMN cutoff_voltage_lower REAL'),
            ('cutoff_voltage_upper', 'ALTER TABLE cell_experiments ADD COLUMN cutoff_voltage_upper REAL'),
            # Full Cell specific columns
            ('anode_mass', 'ALTER TABLE cell_experiments ADD COLUMN anode_mass REAL'),
            ('cathode_mass', 'ALTER TABLE cell_experiments ADD COLUMN cathode_mass REAL'),
            ('anode_loading', 'ALTER TABLE cell_experiments ADD COLUMN anode_loading REAL'),
            ('cathode_loading', 'ALTER TABLE cell_experiments ADD COLUMN cathode_loading REAL'),
            ('anode_thickness', 'ALTER TABLE cell_experiments ADD COLUMN anode_thickness REAL'),
            ('cathode_thickness', 'ALTER TABLE cell_experiments ADD COLUMN cathode_thickness REAL'),
            ('anode_area', 'ALTER TABLE cell_experiments ADD COLUMN anode_area REAL'),
            ('cathode_area', 'ALTER TABLE cell_experiments ADD COLUMN cathode_area REAL'),
            ('np_ratio', 'ALTER TABLE cell_experiments ADD COLUMN np_ratio REAL'),
            ('overhang_ratio', 'ALTER TABLE cell_experiments ADD COLUMN overhang_ratio REAL'),
        ]
        for column_name, migration_sql in migrations:
            if column_name not in columns:
                try:
                    cursor.execute(migration_sql)
                    print(f"Added {column_name} column to cell_experiments table")
                except sqlite3.OperationalError as e:
                    print(f"Error adding {column_name} column: {e}")

        # Add parquet_path column if it doesn't exist
        if 'parquet_path' not in columns:
            try:
                cursor.execute('ALTER TABLE cell_experiments ADD COLUMN parquet_path TEXT')
                print("Added parquet_path column to cell_experiments table")
            except sqlite3.OperationalError as e:
                print(f"Error adding parquet_path column: {e}")
        
        # Check if project_type column exists in projects table
        cursor.execute("PRAGMA table_info(projects)")
        project_columns = [column[1] for column in cursor.fetchall()]
        
        if 'project_type' not in project_columns:
            try:
                cursor.execute('ALTER TABLE projects ADD COLUMN project_type TEXT DEFAULT "Full Cell"')
                print("Added project_type column to projects table")
            except sqlite3.OperationalError as e:
                print(f"Error adding project_type column: {e}")
        
        # Check if project_preferences table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_preferences'")
        if not cursor.fetchone():
            try:
                cursor.execute('''
                    CREATE TABLE project_preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        preference_key TEXT NOT NULL,
                        preference_value TEXT,
                        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES projects (id),
                        UNIQUE(project_id, preference_key)
                    )
                ''')
                print("Created project_preferences table")
            except sqlite3.OperationalError as e:
                print(f"Error creating project_preferences table: {e}")
        
        conn.commit()

def get_project_components(project_id):
    """Get all unique components used in formulations within a project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT formulation_json, data_json, parquet_path, id FROM cell_experiments 
            WHERE project_id = ? AND (formulation_json IS NOT NULL OR data_json IS NOT NULL OR parquet_path IS NOT NULL)
        ''', (project_id,))
        results = cursor.fetchall()
        
        components = set()
        
        for formulation_json, data_json, p_path, exp_id in results:
            d_json = _hydrate_data_json(data_json, p_path, exp_id)
            data_json = d_json
            
            # Check formulation_json field first
            if formulation_json:
                try:
                    formulation_data = json.loads(formulation_json)
                    if isinstance(formulation_data, list):
                        for item in formulation_data:
                            if isinstance(item, dict) and item.get('Component'):
                                components.add(item['Component'].strip())
                except (json.JSONDecodeError, AttributeError):
                    pass
            
            # Check formulation data within data_json (for multi-cell experiments)
            if data_json:
                try:
                    data = json.loads(data_json)
                    if 'cells' in data:
                        for cell in data['cells']:
                            formulation = cell.get('formulation', [])
                            if isinstance(formulation, list):
                                for item in formulation:
                                    if isinstance(item, dict) and item.get('Component'):
                                        components.add(item['Component'].strip())
                except (json.JSONDecodeError, AttributeError):
                    pass
        
        return sorted([comp for comp in components if comp])

# Test user (for now)
TEST_USER_ID = "admin"

def get_user_projects(user_id):
    """Get all projects for a user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, description, project_type, created_date, last_modified 
            FROM projects 
            WHERE user_id = ? 
            ORDER BY last_modified DESC
        ''', (user_id,))
        return cursor.fetchall()

def create_project(user_id, name, description="", project_type="Full Cell"):
    """Create a new project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, project_type) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, name, description, project_type))
        project_id = cursor.lastrowid
        conn.commit()
        return project_id

def update_cell_experiment(experiment_id, cell_name, file_name, loading, active_material, formation_cycles, test_number, df, project_id, electrolyte=None, substrate=None, separator=None, group_assignment=None, formulation_json=None):
    """Update an existing cell experiment in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Save to Parquet
        parquet_path = _save_df_to_parquet(df, prefix="cell")
        data_json = None

        cursor.execute('''
            UPDATE cell_experiments 
            SET cell_name = ?, file_name = ?, loading = ?, active_material = ?, 
                formation_cycles = ?, test_number = ?, electrolyte = ?, substrate = ?, separator = ?, formulation_json = ?, data_json = ?, parquet_path = ?
            WHERE id = ?
        ''', (cell_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, separator, formulation_json, data_json, parquet_path, experiment_id))
        
        # Update project last_modified
        cursor.execute('''
            UPDATE projects 
            SET last_modified = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (project_id,))
        
        conn.commit()

def get_experiment_by_name_and_file(project_id, cell_name, file_name):
    """Get experiment ID by cell name and file name."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM cell_experiments 
            WHERE project_id = ? AND cell_name = ? AND file_name = ?
            LIMIT 1
        ''', (project_id, cell_name, file_name))
        result = cursor.fetchone()
        return result[0] if result else None

def get_project_experiments(project_id):
    """Get all experiments for a project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, cell_name, file_name, data_json, created_date, parquet_path
            FROM cell_experiments 
            WHERE project_id = ? 
            ORDER BY created_date DESC
        ''', (project_id,))
        results = cursor.fetchall()
        
        # Hydrate
        hydrated_results = []
        for row in results:
            exp_id, cname, fname, d_json, cdate, p_path = row
            d_json = hydrate_data_json(d_json, p_path, exp_id)
            hydrated_results.append((exp_id, cname, fname, d_json, cdate))
            
        return hydrated_results

def check_experiment_exists(project_id, cell_name, file_name):
    """Check if an experiment already exists in the project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT EXISTS(
                SELECT 1 FROM cell_experiments 
                WHERE project_id = ? AND cell_name = ? AND file_name = ?
            )
        ''', (project_id, cell_name, file_name))
        return bool(cursor.fetchone()[0])

def get_experiment_data(experiment_id):
    """Get detailed data for a specific experiment."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, project_id, cell_name, file_name, loading, active_material, 
                   formation_cycles, test_number, electrolyte, substrate, separator, data_json, created_date, parquet_path
            FROM cell_experiments 
            WHERE id = ?
        ''', (experiment_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
            
        # Unpack row
        row_id, pid, cname, fname, loading, active, form, testnum, elec, sub, sep, d_json, cdate, p_path = row
        
        # Hydrate
        d_json = hydrate_data_json(d_json, p_path, row_id)
        
        return (row_id, pid, cname, fname, loading, active, form, testnum, elec, sub, sep, d_json, cdate)

def delete_cell_experiment(experiment_id):
    """Delete a cell experiment from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get file paths to delete
        cursor.execute('''
            SELECT parquet_path, data_json FROM cell_experiments WHERE id = ?
        ''', (experiment_id,))
        result = cursor.fetchone()
        
        if result:
            p_path, d_json = result
            # Delete primary parquet file
            if p_path and os.path.exists(p_path):
                try:
                    os.remove(p_path)
                except OSError as e:
                    logger.error(f"Error deleting parquet file {p_path}: {e}")
            
            # Check for embedded parquet files in multi-cell experiments
            if d_json:
                try:
                    data = json.loads(d_json)
                    if isinstance(data, dict) and 'cells' in data:
                        for cell in data['cells']:
                            cell_p_path = cell.get('parquet_path')
                            if cell_p_path and os.path.exists(cell_p_path):
                                try:
                                    os.remove(cell_p_path)
                                except OSError:
                                    pass
                except Exception:
                    pass

        # Get project_id before deleting
        cursor.execute('''
            SELECT project_id FROM cell_experiments WHERE id = ?
        ''', (experiment_id,))
        result = cursor.fetchone()
        project_id = result[0] if result else None
        
        # Delete the experiment
        cursor.execute('DELETE FROM cell_experiments WHERE id = ?', (experiment_id,))
        
        # Update project last_modified if project exists
        if project_id:
            cursor.execute('''
                UPDATE projects 
                SET last_modified = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (project_id,))
        
        conn.commit()

def delete_project(project_id):
    """Delete a project and all its experiments from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Delete all experiments for this project first
        cursor.execute('DELETE FROM cell_experiments WHERE project_id = ?', (project_id,))
        
        # Delete the project
        cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
        
        conn.commit()

def rename_project(project_id, new_name):
    """Rename a project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE projects 
            SET name = ?, last_modified = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (new_name, project_id))
        conn.commit()

def update_project_type(project_id, project_type):
    """Update the project type."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE projects 
            SET project_type = ?, last_modified = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (project_type, project_id))
        conn.commit()

def get_project_by_id(project_id):
    """Get project details by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, description, project_type, created_date, last_modified 
            FROM projects 
            WHERE id = ?
        ''', (project_id,))
        return cursor.fetchone()

def rename_experiment(experiment_id, new_name):
    """Rename an experiment in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE cell_experiments 
            SET cell_name = ?, file_name = ? 
            WHERE id = ?
        ''', (new_name, f"{new_name}.json", experiment_id))
        conn.commit()

def save_experiment(project_id, experiment_name, experiment_date, disc_diameter_mm, group_assignments, group_names, cells_data, solids_content=None, pressed_thickness=None, experiment_notes=None, cell_format_data=None):
    """Save a complete experiment with porosity calculation."""
    try:
        from porosity_calculations import calculate_porosity_from_experiment_data
        
        # Calculate porosity for each cell
        for cell_data in cells_data:
            if (cell_data.get("loading") and 
                disc_diameter_mm and 
                pressed_thickness and 
                cell_data.get("formulation")):
                
                porosity_data = calculate_porosity_from_experiment_data(
                    disc_mass_mg=cell_data["loading"],
                    disc_diameter_mm=disc_diameter_mm,
                    pressed_thickness_um=pressed_thickness,
                    formulation=cell_data["formulation"]
                )
                
                # Add porosity data to cell_data
                cell_data["porosity"] = porosity_data["porosity"]
                cell_data["electrode_density"] = porosity_data["electrode_density"]
                cell_data["theoretical_density"] = porosity_data["theoretical_density"]
    except ImportError:
        # If porosity_calculations module is not available, skip porosity calculation
        pass
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Create the main experiment record
        # Extract representative electrolyte, substrate, and separator values from first cell
        representative_electrolyte = cells_data[0].get('electrolyte', '1M LiPF6 1:1:1') if cells_data else '1M LiPF6 1:1:1'
        representative_substrate = cells_data[0].get('substrate', 'Copper') if cells_data else 'Copper'
        representative_separator = cells_data[0].get('separator', '25um PP') if cells_data else '25um PP'
        
        # Extract cutoff voltages from first cell
        cutoff_voltage_lower = cells_data[0].get('cutoff_voltage_lower') if cells_data else None
        cutoff_voltage_upper = cells_data[0].get('cutoff_voltage_upper') if cells_data else None
        
        # Extract formulation from first cell for formulation_json field
        representative_formulation = None
        if cells_data and cells_data[0].get('formulation'):
            representative_formulation = json.dumps(cells_data[0]['formulation'])
        
        # Process cells to extract data to parquet
        if cells_data:
            for cell in cells_data:
                d_json = cell.get('data_json')
                # If d_json is present and substantial (looks like a dataframe json)
                if d_json and len(str(d_json)) > 100: 
                    try:
                        # Convert to DF and save
                        df = pd.read_json(StringIO(d_json)) if isinstance(d_json, str) else pd.DataFrame(d_json)
                        if not df.empty:
                            path = _save_df_to_parquet(df, prefix="cell_multi")
                            cell['parquet_path'] = path
                            cell['data_json'] = None # Clear embedded data
                    except Exception as e:
                        logger.error(f"Error converting cell data to parquet: {e}")

        # Prepare experiment data including cell format information
        experiment_data = {
            'experiment_date': experiment_date.isoformat() if experiment_date else None,
            'disc_diameter_mm': disc_diameter_mm,
            'group_assignments': group_assignments,
            'group_names': group_names,
            'cells': cells_data,
            'solids_content': solids_content,
            'pressed_thickness': pressed_thickness,
            'experiment_notes': experiment_notes
        }
        
        # Add cell format data if provided
        if cell_format_data:
            experiment_data.update(cell_format_data)
        
        cursor.execute('''
            INSERT INTO cell_experiments 
            (project_id, cell_name, file_name, electrolyte, substrate, separator, formulation_json, data_json, solids_content, pressed_thickness, experiment_notes, porosity, cutoff_voltage_lower, cutoff_voltage_upper)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, experiment_name, f"{experiment_name}.json", representative_electrolyte, representative_substrate, representative_separator, representative_formulation, json.dumps(experiment_data), solids_content, pressed_thickness, experiment_notes, 
        # Calculate average porosity only from cells with valid porosity values
        sum(cell.get("porosity", 0) for cell in cells_data if cell.get("porosity") is not None and cell.get("porosity") > 0) / 
        len([cell for cell in cells_data if cell.get("porosity") is not None and cell.get("porosity") > 0]) 
        if cells_data and any(cell.get("porosity") is not None and cell.get("porosity") > 0 for cell in cells_data) else 0, cutoff_voltage_lower, cutoff_voltage_upper))
        # Update project last_modified
        cursor.execute('''
            UPDATE projects 
            SET last_modified = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (project_id,))
        experiment_id = cursor.lastrowid
        conn.commit()
        return experiment_id

def update_experiment(experiment_id, project_id, experiment_name, experiment_date, disc_diameter_mm, group_assignments, group_names, cells_data, solids_content=None, pressed_thickness=None, experiment_notes=None, cell_format_data=None):
    """Update an existing experiment with new experiment-level fields."""
    try:
        from porosity_calculations import calculate_porosity_from_experiment_data
        
        # Calculate porosity for each cell if we have the required data
        for cell_data in cells_data:
            if (cell_data.get("loading") and 
                disc_diameter_mm and 
                pressed_thickness and 
                cell_data.get("formulation")):
                
                porosity_data = calculate_porosity_from_experiment_data(
                    disc_mass_mg=cell_data["loading"],
                    disc_diameter_mm=disc_diameter_mm,
                    pressed_thickness_um=pressed_thickness,
                    formulation=cell_data["formulation"]
                )
                
                # Add porosity data to cell_data
                cell_data["porosity"] = porosity_data["porosity"]
                cell_data["electrode_density"] = porosity_data["electrode_density"]
                cell_data["theoretical_density"] = porosity_data["theoretical_density"]
    except ImportError:
        # If porosity_calculations module is not available, skip porosity calculation
        pass
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Update the experiment record
        # Extract representative electrolyte, substrate, and separator values from first cell
        representative_electrolyte = cells_data[0].get('electrolyte', '1M LiPF6 1:1:1') if cells_data else '1M LiPF6 1:1:1'
        representative_substrate = cells_data[0].get('substrate', 'Copper') if cells_data else 'Copper'
        representative_separator = cells_data[0].get('separator', '25um PP') if cells_data else '25um PP'
        
        # Extract cutoff voltages from first cell
        cutoff_voltage_lower = cells_data[0].get('cutoff_voltage_lower') if cells_data else None
        cutoff_voltage_upper = cells_data[0].get('cutoff_voltage_upper') if cells_data else None
        
        # Extract formulation from first cell for formulation_json field
        representative_formulation = None
        if cells_data and cells_data[0].get('formulation'):
            representative_formulation = json.dumps(cells_data[0]['formulation'])
        
        # Prepare experiment data including cell format information
        experiment_data = {
            'experiment_date': experiment_date.isoformat() if experiment_date else None,
            'disc_diameter_mm': disc_diameter_mm,
            'group_assignments': group_assignments,
            'group_names': group_names,
            'cells': cells_data,
            'solids_content': solids_content,
            'pressed_thickness': pressed_thickness,
            'experiment_notes': experiment_notes
        }
        
        # Add cell format data if provided
        if cell_format_data:
            experiment_data.update(cell_format_data)
        
        # Process cells to extract data to parquet
        if cells_data:
            for cell in cells_data:
                d_json = cell.get('data_json')
                if d_json and len(str(d_json)) > 100:
                    try:
                         # Check if it's already a path? No, assuming input is full data from frontend
                         # But wait, if we load -> edit -> save, 
                         # 'data_json' from frontend might be a huge JSON string.
                         
                         df = pd.read_json(StringIO(d_json)) if isinstance(d_json, str) else pd.DataFrame(d_json)
                         if not df.empty:
                            path = _save_df_to_parquet(df, prefix="cell_multi")
                            cell['parquet_path'] = path
                            cell['data_json'] = None
                            
                            # Clean up old file if there was one? 
                            # Hard to track unless we kept the old path in the cell data passed from frontend.
                            # The frontend hydrates it, so 'parquet_path' key might be lost/overwritten?
                            # If frontend preserves unknown keys, 'parquet_path' might be there.
                            # If we overwrite it, we orphan the old file. Minimal issue for now.
                    except Exception as e:
                        logger.error(f"Error in update_experiment parquet conversion: {e}")

        cursor.execute('''
            UPDATE cell_experiments 
            SET cell_name = ?, file_name = ?, electrolyte = ?, substrate = ?, separator = ?, formulation_json = ?, data_json = ?, solids_content = ?, pressed_thickness = ?, experiment_notes = ?, porosity = ?, cutoff_voltage_lower = ?, cutoff_voltage_upper = ?
            WHERE id = ?
        ''', (experiment_name, f"{experiment_name}.json", representative_electrolyte, representative_substrate, representative_separator, representative_formulation, json.dumps(experiment_data), solids_content, pressed_thickness, experiment_notes, 
        # Calculate average porosity only from cells with valid porosity values
        sum(cell.get("porosity", 0) for cell in cells_data if cell.get("porosity") is not None and cell.get("porosity") > 0) / 
        len([cell for cell in cells_data if cell.get("porosity") is not None and cell.get("porosity") > 0]) 
        if cells_data and any(cell.get("porosity") is not None and cell.get("porosity") > 0 for cell in cells_data) else 0, cutoff_voltage_lower, cutoff_voltage_upper, experiment_id))
        # Update project last_modified
        cursor.execute('''
            UPDATE projects 
            SET last_modified = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (project_id,))
        conn.commit()

def get_experiment_by_id(experiment_id):
    """Get experiment data by experiment ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, project_id, cell_name, file_name, loading, active_material, 
                   formation_cycles, test_number, electrolyte, substrate, separator, 
                   formulation_json, data_json, solids_content, pressed_thickness, 
                   experiment_notes, created_date, porosity, parquet_path
            FROM cell_experiments 
            WHERE id = ?
        ''', (experiment_id,))
        row = cursor.fetchone()
        if not row:
            return None
            
        # Unpack up to porosity (first 18 items)
        # We need to handle the tuple carefully.
        # Original caller expects 18 items.
        # We have 19 items in select.
        
        # Hydrate
        # row indexes: 0=id, 12=data_json, 18=parquet_path
        d_json = row[12]
        p_path = row[18]
        
        d_json = hydrate_data_json(d_json, p_path, row[0])
        
        # Return tuple with hydrated d_json, WITHOUT parquet_path appended 
        # to maintain backward compatibility with caller unpacking
        result = list(row[:18])
        result[12] = d_json
        return tuple(result)

def generate_duplicate_experiment_name(project_id, base_name):
    """Generate a unique experiment name for duplication by appending (1), (2), etc."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check if base name already exists
        cursor.execute('''
            SELECT cell_name FROM cell_experiments 
            WHERE project_id = ? AND cell_name = ?
        ''', (project_id, base_name))
        
        if not cursor.fetchone():
            return base_name
        
        # Find all existing names that match the pattern: base_name, base_name (1), base_name (2), etc.
        cursor.execute('''
            SELECT cell_name FROM cell_experiments 
            WHERE project_id = ? AND (cell_name = ? OR cell_name LIKE ?)
        ''', (project_id, base_name, f"{base_name} (%"))
        
        existing_names = {row[0] for row in cursor.fetchall()}
        
        # Find the next available number
        counter = 1
        while True:
            new_name = f"{base_name} ({counter})"
            if new_name not in existing_names:
                return new_name
            counter += 1

def duplicate_experiment(experiment_id):
    """
    Duplicate an experiment with all its metadata.
    The duplicate will have no uploaded data and acts as a new experiment template.
    Returns the new experiment's ID.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get the original experiment data
        cursor.execute('''
            SELECT project_id, cell_name, electrolyte, substrate, separator, 
                   data_json, solids_content, pressed_thickness, experiment_notes
            FROM cell_experiments 
            WHERE id = ?
        ''', (experiment_id,))
        
        original = cursor.fetchone()
        if not original:
            raise ValueError(f"Experiment with ID {experiment_id} not found")
        
        project_id, cell_name, electrolyte, substrate, separator, data_json_str, solids_content, pressed_thickness, experiment_notes = original
        
        # Parse the data_json to extract metadata
        data_json = json.loads(data_json_str) if data_json_str else {}
        
        # Generate a unique name for the duplicate
        new_name = generate_duplicate_experiment_name(project_id, cell_name)
        
        # Extract default cell values from the first cell of the original experiment
        # These will be used as defaults when uploading new files to the duplicate
        cells = data_json.get('cells', [])
        default_cell_values = {}
        if cells and len(cells) > 0:
            first_cell = cells[0]
            default_cell_values = {
                'loading': first_cell.get('loading', 20.0),
                'active_material': first_cell.get('active_material', 90.0),
                'formation_cycles': first_cell.get('formation_cycles', 4),
                'electrolyte': first_cell.get('electrolyte', '1M LiPF6 1:1:1'),
                'substrate': first_cell.get('substrate', 'Copper'),
                'separator': first_cell.get('separator', '25um PP'),
                'formulation': first_cell.get('formulation', [])
            }
        
        # Create new experiment data structure with metadata but no cell data
        new_experiment_data = {
            'experiment_date': data_json.get('experiment_date'),
            'disc_diameter_mm': data_json.get('disc_diameter_mm'),
            'group_assignments': data_json.get('group_assignments'),
            'group_names': data_json.get('group_names'),
            'cells': [],  # Empty - user needs to upload new data
            'solids_content': solids_content,
            'pressed_thickness': pressed_thickness,
            'experiment_notes': experiment_notes,
            'default_cell_values': default_cell_values  # Store defaults for new uploads
        }
        
        # Preserve cell format data if it exists
        for key in ['anode_diameter_mm', 'cathode_diameter_mm', 'anode_thickness_um', 
                    'cathode_thickness_um', 'separator_thickness_um', 'can_format']:
            if key in data_json:
                new_experiment_data[key] = data_json[key]
        
        # Insert the duplicate experiment
        cursor.execute('''
            INSERT INTO cell_experiments 
            (project_id, cell_name, file_name, electrolyte, substrate, separator, 
             data_json, solids_content, pressed_thickness, experiment_notes, porosity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, new_name, f"{new_name}.json", electrolyte, substrate, separator,
              json.dumps(new_experiment_data), solids_content, pressed_thickness, 
              experiment_notes, 0))  # porosity=0 for new experiment
        
        new_experiment_id = cursor.lastrowid
        
        # Update project last_modified
        cursor.execute('''
            UPDATE projects 
            SET last_modified = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (project_id,))
        
        conn.commit()
        logger.info(f"Successfully duplicated experiment '{cell_name}' to '{new_name}' (ID: {new_experiment_id})")
        return new_experiment_id, new_name

def check_experiment_name_exists(project_id, experiment_name):
    """Check if an experiment with this name already exists in the project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT EXISTS(
                SELECT 1 FROM cell_experiments 
                WHERE project_id = ? AND cell_name = ?
            )
        ''', (project_id, experiment_name))
        return bool(cursor.fetchone()[0])

def get_experiment_by_name(project_id, experiment_name):
    """Get experiment ID by experiment name."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM cell_experiments 
            WHERE project_id = ? AND cell_name = ?
            LIMIT 1
        ''', (project_id, experiment_name))
        result = cursor.fetchone()
        return result[0] if result else None

def get_all_project_experiments_data(project_id):
    """Get all experiments data for a project for Master Table analysis."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, cell_name, file_name, loading, active_material, formation_cycles, 
                   test_number, electrolyte, substrate, separator, formulation_json, data_json, created_date, porosity, experiment_notes, cutoff_voltage_lower, cutoff_voltage_upper, parquet_path
            FROM cell_experiments 
            WHERE project_id = ? 
            ORDER BY created_date DESC
        ''', (project_id,))
        results = cursor.fetchall()
        
        hydrated_results = []
        for row in results:
            # row: 0=id, 11=data_json, 17=parquet_path
            d_json = row[11]
            p_path = row[17]
            
            d_json = hydrate_data_json(d_json, p_path, row[0])
            
            # Reconstruct row without parquet_path (length 17)
            new_row = list(row[:17])
            new_row[11] = d_json
            hydrated_results.append(tuple(new_row))
            
        return hydrated_results

def get_project_preferences(project_id):
    """Get all preferences for a project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT preference_key, preference_value
            FROM project_preferences 
            WHERE project_id = ?
            ORDER BY preference_key
        ''', (project_id,))
        return dict(cursor.fetchall())

def save_project_preferences(project_id, preferences):
    """Save preferences for a project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        for key, value in preferences.items():
            if value is not None and value != "":
                cursor.execute('''
                    INSERT OR REPLACE INTO project_preferences 
                    (project_id, preference_key, preference_value, updated_date)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (project_id, key, str(value)))
            else:
                # Remove preference if value is None or empty
                cursor.execute('''
                    DELETE FROM project_preferences 
                    WHERE project_id = ? AND preference_key = ?
                ''', (project_id, key))
        
        conn.commit()

def get_project_preference(project_id, key, default=None):
    """Get a specific preference for a project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT preference_value
            FROM project_preferences 
            WHERE project_id = ? AND preference_key = ?
        ''', (project_id, key))
        result = cursor.fetchone()
        return result[0] if result else default

def get_experiments_by_formulation_component(project_id, component_name, min_percentage=None, max_percentage=None):
    """
    Get experiments that contain a specific formulation component within a percentage range.
    
    Args:
        project_id: The project ID to search within
        component_name: Name of the component to search for (e.g., "Graphite")
        min_percentage: Minimum dry mass fraction percentage (optional)
        max_percentage: Maximum dry mass fraction percentage (optional)
    
    Returns:
        List of experiment data tuples matching the criteria
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, project_id, cell_name, file_name, loading, active_material, 
                   formation_cycles, test_number, electrolyte, substrate, separator, 
                   formulation_json, data_json, solids_content, pressed_thickness, 
                   experiment_notes, created_date, porosity, parquet_path
            FROM cell_experiments 
            WHERE project_id = ? AND (formulation_json IS NOT NULL OR data_json IS NOT NULL OR parquet_path IS NOT NULL)
        ''', (project_id,))
        
        all_experiments = cursor.fetchall()
        matching_experiments = []
        
        for exp in all_experiments:
            # Hydrate first
            # exp: 0=id, 12=data_json, 18=parquet_path
            d_json = exp[12]
            p_path = exp[18]
            d_json = hydrate_data_json(d_json, p_path, exp[0])
            
            # Construct hydrated experiment tuple (18 elements)
            hydrated_exp = list(exp[:18])
            hydrated_exp[12] = d_json
            exp = tuple(hydrated_exp)
            
            formulation_json = exp[11]  # formulation_json is at index 11
            data_json = exp[12]  # data_json is at index 12 (now hydrated)
            formulations_to_check = []
            
            # Check formulation_json field
            if formulation_json:
                try:
                    formulation = json.loads(formulation_json)
                    if isinstance(formulation, list):
                        formulations_to_check.append(formulation)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Check data_json for multi-cell experiments
            if data_json:
                try:
                    data = json.loads(data_json)
                    if 'cells' in data:
                        for cell in data['cells']:
                            formulation = cell.get('formulation', [])
                            if isinstance(formulation, list) and formulation:
                                formulations_to_check.append(formulation)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Process each formulation
            found_match = False
            for formulation in formulations_to_check:
                if found_match:
                    break
                for item in formulation:
                    if isinstance(item, dict):
                        component = (item.get('Component') or 
                                   item.get('component') or 
                                   item.get('Component Name') or '')
                        if component.strip().lower() == component_name.strip().lower():
                            percentage = (item.get('Dry Mass Fraction (%)') or
                                        item.get('dry_mass_fraction') or
                                        item.get('Value') or None)
                            
                            if percentage is not None:
                                try:
                                    percentage = float(percentage)
                                    # Check if percentage is within range
                                    if min_percentage is not None and percentage < min_percentage:
                                        continue
                                    if max_percentage is not None and percentage > max_percentage:
                                        continue
                                    matching_experiments.append(exp)
                                    found_match = True
                                    break
                                except (ValueError, TypeError):
                                    continue
        
        return matching_experiments

def get_formulation_summary(project_id):
    """
    Get a summary of all formulation components used in a project.
    
    Returns:
        Dictionary with component names as keys and lists of percentage values as values
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT formulation_json, data_json, parquet_path, id
            FROM cell_experiments 
            WHERE project_id = ?
        ''', (project_id,))
        
        results = cursor.fetchall()
        component_summary = {}
        
        for formulation_json, data_json, p_path, exp_id in results:
            d_json = hydrate_data_json(data_json, p_path, exp_id)
            data_json = d_json
            
            formulations_to_check = []
            
            # Check formulation_json field
            if formulation_json:
                try:
                    formulation = json.loads(formulation_json)
                    if isinstance(formulation, list):
                        formulations_to_check.append(formulation)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Check data_json for multi-cell experiments
            if data_json:
                try:
                    data = json.loads(data_json)
                    if 'cells' in data:
                        for cell in data['cells']:
                            formulation = cell.get('formulation', [])
                            if isinstance(formulation, list) and formulation:
                                formulations_to_check.append(formulation)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Process each formulation
            for formulation in formulations_to_check:
                for item in formulation:
                    if isinstance(item, dict):
                        component = (item.get('Component') or 
                                   item.get('component') or 
                                   item.get('Component Name') or '')
                        if component:
                            percentage = (item.get('Dry Mass Fraction (%)') or
                                        item.get('dry_mass_fraction') or
                                        item.get('Value') or None)
                            
                            if percentage is not None:
                                try:
                                    percentage = float(percentage)
                                    if component not in component_summary:
                                        component_summary[component] = []
                                    component_summary[component].append(percentage)
                                except (ValueError, TypeError):
                                    continue
        
        # Calculate statistics for each component
        component_stats = {}
        for component, percentages in component_summary.items():
            if percentages:
                component_stats[component] = {
                    'values': sorted(set(percentages)),
                    'min': min(percentages),
                    'max': max(percentages),
                    'avg': sum(percentages) / len(percentages),
                    'count': len(percentages)
                }
        
        return component_stats

def get_experiments_grouped_by_formulation(project_id, component_name):
    """
    Group experiments by the percentage of a specific component.
    
    Returns:
        Dictionary with percentage ranges as keys and lists of experiment IDs as values
    """
    experiments = get_experiments_by_formulation_component(project_id, component_name)
    grouped = {}
    
    for exp in experiments:
        formulation_json = exp[11]
        data_json = exp[12]
        formulations_to_check = []
        
        # Check formulation_json field
        if formulation_json:
            try:
                formulation = json.loads(formulation_json)
                if isinstance(formulation, list):
                    formulations_to_check.append(formulation)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Check data_json for multi-cell experiments
        if data_json:
            try:
                data = json.loads(data_json)
                if 'cells' in data:
                    for cell in data['cells']:
                        formulation = cell.get('formulation', [])
                        if isinstance(formulation, list) and formulation:
                            formulations_to_check.append(formulation)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Process each formulation
        found_match = False
        for formulation in formulations_to_check:
            if found_match:
                break
            for item in formulation:
                if isinstance(item, dict):
                    component = (item.get('Component') or 
                               item.get('component') or 
                               item.get('Component Name') or '')
                    if component.strip().lower() == component_name.strip().lower():
                        percentage = (item.get('Dry Mass Fraction (%)') or
                                    item.get('dry_mass_fraction') or
                                    item.get('Value') or None)
                        
                        if percentage is not None:
                            try:
                                percentage = float(percentage)
                                # Round to nearest 0.5 for grouping
                                rounded = round(percentage * 2) / 2
                                if rounded not in grouped:
                                    grouped[rounded] = []
                                grouped[rounded].append(exp[0])  # exp[0] is the experiment ID
                                found_match = True
                                break
                            except (ValueError, TypeError):
                                continue
    
    return grouped

# Initialize database when module is imported
init_database()
migrate_database()
