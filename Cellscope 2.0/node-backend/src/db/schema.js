export const schemaStatements = [
  `
  CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    legacy_project_id INTEGER,
    user_id TEXT NOT NULL DEFAULT 'admin',
    name TEXT NOT NULL,
    description TEXT,
    project_type TEXT NOT NULL DEFAULT 'Full Cell'
      CHECK (project_type IN ('Cathode', 'Anode', 'Full Cell')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
  )
  `,
  `
  DROP INDEX IF EXISTS idx_projects_legacy_project_id
  `,
  `
  CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_legacy_project_id
  ON projects(legacy_project_id)
  `,
  `
  CREATE INDEX IF NOT EXISTS idx_projects_user_id
  ON projects(user_id)
  `,
  `
  CREATE INDEX IF NOT EXISTS idx_projects_updated_at
  ON projects(updated_at DESC)
  `,

  `
  CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    legacy_experiment_id INTEGER,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    experiment_date TEXT,
    disc_diameter_mm REAL,
    solids_content REAL,
    pressed_thickness REAL,
    notes TEXT,
    group_names_json TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
  )
  `,
  `
  CREATE INDEX IF NOT EXISTS idx_experiments_project_id
  ON experiments(project_id)
  `,
  `
  CREATE INDEX IF NOT EXISTS idx_experiments_created_at
  ON experiments(created_at DESC)
  `,
  `
  CREATE INDEX IF NOT EXISTS idx_experiments_legacy_experiment_id
  ON experiments(legacy_experiment_id)
  `,

  `
  CREATE TABLE IF NOT EXISTS cells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    legacy_cell_id INTEGER,
    experiment_id INTEGER NOT NULL,
    cell_name TEXT NOT NULL,
    file_name TEXT,
    loading REAL,
    active_material_pct REAL,
    formation_cycles INTEGER NOT NULL DEFAULT 4,
    test_number TEXT,
    electrolyte TEXT,
    substrate TEXT,
    separator TEXT,
    formulation_json TEXT,
    group_assignment TEXT,
    excluded INTEGER NOT NULL DEFAULT 0,
    porosity REAL,
    cutoff_voltage_lower REAL,
    cutoff_voltage_upper REAL,
    anode_mass REAL,
    cathode_mass REAL,
    anode_loading REAL,
    cathode_loading REAL,
    anode_thickness REAL,
    cathode_thickness REAL,
    anode_area REAL,
    cathode_area REAL,
    np_ratio REAL,
    overhang_ratio REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
  )
  `,
  `
  CREATE INDEX IF NOT EXISTS idx_cells_experiment_id
  ON cells(experiment_id)
  `,
  `
  CREATE INDEX IF NOT EXISTS idx_cells_legacy_cell_id
  ON cells(legacy_cell_id)
  `,
  `
  CREATE INDEX IF NOT EXISTS idx_cells_test_number
  ON cells(test_number)
  `,
  `
  CREATE INDEX IF NOT EXISTS idx_cells_group_assignment
  ON cells(group_assignment)
  `,

  `
  CREATE TABLE IF NOT EXISTS cell_data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cell_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    path TEXT,
    payload_json TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(cell_id) REFERENCES cells(id) ON DELETE CASCADE,
    CHECK(path IS NOT NULL OR payload_json IS NOT NULL)
  )
  `,
  `
  CREATE INDEX IF NOT EXISTS idx_cell_data_sources_cell_id
  ON cell_data_sources(cell_id)
  `,
  `
  CREATE INDEX IF NOT EXISTS idx_cell_data_sources_type
  ON cell_data_sources(source_type)
  `,

  `
  CREATE TABLE IF NOT EXISTS project_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    preference_key TEXT NOT NULL,
    preference_value TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, preference_key)
  )
  `,

  `
  CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
  )
  `,
  `
  INSERT INTO schema_meta(key, value)
  VALUES ('schema_version', '2')
  ON CONFLICT(key) DO UPDATE SET value = excluded.value
  `,

  `
  CREATE TRIGGER IF NOT EXISTS trg_projects_updated_at
  AFTER UPDATE ON projects
  FOR EACH ROW
  WHEN NEW.updated_at = OLD.updated_at
  BEGIN
    UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
  END
  `,
  `
  CREATE TRIGGER IF NOT EXISTS trg_experiments_updated_at
  AFTER UPDATE ON experiments
  FOR EACH ROW
  WHEN NEW.updated_at = OLD.updated_at
  BEGIN
    UPDATE experiments SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
  END
  `,
  `
  CREATE TRIGGER IF NOT EXISTS trg_cells_updated_at
  AFTER UPDATE ON cells
  FOR EACH ROW
  WHEN NEW.updated_at = OLD.updated_at
  BEGIN
    UPDATE cells SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
  END
  `,
  `
  CREATE TRIGGER IF NOT EXISTS trg_project_preferences_updated_at
  AFTER UPDATE ON project_preferences
  FOR EACH ROW
  WHEN NEW.updated_at = OLD.updated_at
  BEGIN
    UPDATE project_preferences SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
  END
  `,
];
