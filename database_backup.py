import sqlite3
import json
from contextlib import contextmanager
import logging
import time
import random
import os

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

def save_cell_experiment(project_id, cell_name, file_name, loading, active_material, formation_cycles, test_number, df, electrolyte=None, substrate=None, group_assignment=None, max_retries=3):
    """Simple, reliable cell experiment saving with minimal complexity."""
    for attempt in range(max_retries):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Convert DataFrame to JSON for storage
                data_json = df.to_json()
                
                # Simple single transaction
                cursor.execute('''
                    INSERT INTO cell_experiments 
                    (project_id, cell_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, group_assignment, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (project_id, cell_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, group_assignment, data_json))
                
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
            ('formulation_json', 'ALTER TABLE cell_experiments ADD COLUMN formulation_json TEXT'),
            ('solids_content', 'ALTER TABLE cell_experiments ADD COLUMN solids_content REAL'),
            ('pressed_thickness', 'ALTER TABLE cell_experiments ADD COLUMN pressed_thickness REAL'),
            ('experiment_notes', 'ALTER TABLE cell_experiments ADD COLUMN experiment_notes TEXT'),
            ('porosity', 'ALTER TABLE cell_experiments ADD COLUMN porosity REAL'),
        ]
        for column_name, migration_sql in migrations:
            if column_name not in columns:
                try:
                    cursor.execute(migration_sql)
                    print(f"Added {column_name} column to cell_experiments table")
                except sqlite3.OperationalError as e:
                    print(f"Error adding {column_name} column: {e}")
        
        # Check if project_type column exists in projects table
        cursor.execute("PRAGMA table_info(projects)")
        project_columns = [column[1] for column in cursor.fetchall()]
        
        if 'project_type' not in project_columns:
            try:
                cursor.execute('ALTER TABLE projects ADD COLUMN project_type TEXT DEFAULT "Full Cell"')
                print("Added project_type column to projects table")
            except sqlite3.OperationalError as e:
                print(f"Error adding project_type column: {e}")
        
        conn.commit()

def get_project_components(project_id):
    """Get all unique components used in formulations within a project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT formulation_json, data_json FROM cell_experiments 
            WHERE project_id = ? AND (formulation_json IS NOT NULL OR data_json IS NOT NULL)
        ''', (project_id,))
        results = cursor.fetchall()
        
        components = set()
        
        for formulation_json, data_json in results:
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

def update_cell_experiment(experiment_id, cell_name, file_name, loading, active_material, formation_cycles, test_number, df, project_id, electrolyte=None, substrate=None, group_assignment=None):
    """Update an existing cell experiment in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Convert DataFrame to JSON for storage
        data_json = df.to_json()
        
        cursor.execute('''
            UPDATE cell_experiments 
            SET cell_name = ?, file_name = ?, loading = ?, active_material = ?, 
                formation_cycles = ?, test_number = ?, electrolyte = ?, substrate = ?, data_json = ?
            WHERE id = ?
        ''', (cell_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, data_json, experiment_id))
        
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
            SELECT id, cell_name, file_name, data_json, created_date
            FROM cell_experiments 
            WHERE project_id = ? 
            ORDER BY created_date DESC
        ''', (project_id,))
        return cursor.fetchall()

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
                   formation_cycles, test_number, electrolyte, substrate, data_json, created_date
            FROM cell_experiments 
            WHERE id = ?
        ''', (experiment_id,))
        return cursor.fetchone()

def delete_cell_experiment(experiment_id):
    """Delete a cell experiment from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
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
    """Rename a project in the database."""
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

def save_experiment(project_id, experiment_name, experiment_date, disc_diameter_mm, group_assignments, group_names, cells_data, solids_content=None, pressed_thickness=None, experiment_notes=None, porosity=None):
    """Save a complete experiment with new experiment-level fields."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Create the main experiment record
        cursor.execute('''
            INSERT INTO cell_experiments 
            (project_id, cell_name, file_name, data_json, solids_content, pressed_thickness, experiment_notes, porosity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, experiment_name, f"{experiment_name}.json", json.dumps({
            'experiment_date': experiment_date.isoformat() if experiment_date else None,
            'disc_diameter_mm': disc_diameter_mm,
            'group_assignments': group_assignments,
            'group_names': group_names,
            'cells': cells_data,
            'solids_content': solids_content,
            'pressed_thickness': pressed_thickness,
            'experiment_notes': experiment_notes,
            'porosity': porosity,
        }), solids_content, pressed_thickness, experiment_notes, porosity))
        experiment_id = cursor.lastrowid
        conn.commit()
        return experiment_id

def update_experiment(experiment_id, project_id, experiment_name, experiment_date, disc_diameter_mm, group_assignments, group_names, cells_data, solids_content=None, pressed_thickness=None, experiment_notes=None, porosity=None):
    """Update an existing experiment with new experiment-level fields."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Update the experiment record
        cursor.execute('''
            UPDATE cell_experiments 
            SET cell_name = ?, file_name = ?, data_json = ?, solids_content = ?, pressed_thickness = ?, experiment_notes = ?, porosity = ?
            WHERE id = ?
        ''', (experiment_name, f"{experiment_name}.json", json.dumps({
            'experiment_date': experiment_date.isoformat() if experiment_date else None,
            'disc_diameter_mm': disc_diameter_mm,
            'group_assignments': group_assignments,
            'group_names': group_names,
            'cells': cells_data,
            'solids_content': solids_content,
            'pressed_thickness': pressed_thickness,
            'experiment_notes': experiment_notes,
            'porosity': porosity,
        }), solids_content, pressed_thickness, experiment_notes, porosity, experiment_id))
        conn.commit()

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
                   test_number, electrolyte, formulation_json, data_json, created_date
            FROM cell_experiments 
            WHERE project_id = ? 
            ORDER BY created_date DESC
        ''', (project_id,))
        return cursor.fetchall()

# Initialize database when module is imported
init_database()
migrate_database()
