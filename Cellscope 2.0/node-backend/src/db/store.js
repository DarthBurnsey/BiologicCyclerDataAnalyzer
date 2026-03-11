function normalizeCursor(cursor) {
  return cursor ?? Number.MAX_SAFE_INTEGER;
}

function pageFromRows(rows, limit) {
  const hasMore = rows.length > limit;
  const items = hasMore ? rows.slice(0, limit) : rows;
  return {
    items,
    nextCursor: hasMore ? items.at(-1).id : null,
  };
}

function stringifyOrNull(value) {
  if (value === undefined || value === null) {
    return null;
  }
  return JSON.stringify(value);
}

function nullIfUndefined(value) {
  return value === undefined ? null : value;
}

function mapSources(dataSources = []) {
  if (!Array.isArray(dataSources)) {
    return [];
  }

  return dataSources
    .map((source) => {
      if (!source || typeof source !== 'object') {
        return null;
      }

      const sourceType = source.source_type ? String(source.source_type) : 'parquet';
      const path = source.path ? String(source.path) : null;
      const payload = source.payload_json ?? null;
      const metadata = source.metadata ?? source.metadata_json ?? null;

      if (path === null && payload === null) {
        return null;
      }

      return {
        source_type: sourceType,
        path,
        payload_json: payload === null ? null : stringifyOrNull(payload),
        metadata_json: metadata === null ? null : stringifyOrNull(metadata),
      };
    })
    .filter(Boolean);
}

function insertDataSources(db, cellId, dataSources) {
  const mapped = mapSources(dataSources);
  if (!mapped.length) {
    return;
  }

  const insert = db.prepare(`
    INSERT INTO cell_data_sources (cell_id, source_type, path, payload_json, metadata_json)
    VALUES (?, ?, ?, ?, ?)
  `);

  for (const source of mapped) {
    insert.run(
      cellId,
      source.source_type,
      source.path,
      source.payload_json,
      source.metadata_json,
    );
  }
}

export function createStore(db) {
  return {
    listProjects({ cursor = null, limit = 25 }) {
      const rows = db
        .prepare(`
          SELECT
            p.*,
            COUNT(DISTINCT e.id) AS experiment_count,
            COUNT(c.id) AS cell_count
          FROM projects p
          LEFT JOIN experiments e ON e.project_id = p.id
          LEFT JOIN cells c ON c.experiment_id = e.id
          WHERE p.id < ?
          GROUP BY p.id
          ORDER BY p.id DESC
          LIMIT ?
        `)
        .all(normalizeCursor(cursor), limit + 1);

      return pageFromRows(rows, limit);
    },

    createProject({ user_id, name, description, project_type }) {
      const result = db
        .prepare(`
          INSERT INTO projects (user_id, name, description, project_type)
          VALUES (?, ?, ?, ?)
        `)
        .run(
          user_id ?? 'admin',
          name,
          nullIfUndefined(description),
          project_type ?? 'Full Cell',
        );

      return this.getProject(Number(result.lastInsertRowid));
    },

    getProject(projectId) {
      return db
        .prepare(`
          SELECT
            p.*,
            (SELECT COUNT(*) FROM experiments e WHERE e.project_id = p.id) AS experiment_count,
            (
              SELECT COUNT(*)
              FROM cells c
              JOIN experiments e ON e.id = c.experiment_id
              WHERE e.project_id = p.id
            ) AS cell_count
          FROM projects p
          WHERE p.id = ?
        `)
        .get(projectId);
    },

    updateProject(projectId, updates) {
      const allowedFields = ['name', 'description', 'project_type'];
      const fields = allowedFields.filter((field) => updates[field] !== undefined);

      if (!fields.length) {
        return this.getProject(projectId);
      }

      const setClause = fields.map((field) => `${field} = ?`).join(', ');
      const values = fields.map((field) => updates[field]);

      const result = db
        .prepare(`UPDATE projects SET ${setClause} WHERE id = ?`)
        .run(...values, projectId);

      if (!result.changes) {
        return null;
      }

      return this.getProject(projectId);
    },

    deleteProject(projectId) {
      const result = db.prepare('DELETE FROM projects WHERE id = ?').run(projectId);
      return result.changes > 0;
    },

    listExperiments(projectId, { cursor = null, limit = 25 }) {
      const rows = db
        .prepare(`
          SELECT
            e.*,
            COUNT(c.id) AS cell_count
          FROM experiments e
          LEFT JOIN cells c ON c.experiment_id = e.id
          WHERE e.project_id = ?
            AND e.id < ?
          GROUP BY e.id
          ORDER BY e.id DESC
          LIMIT ?
        `)
        .all(projectId, normalizeCursor(cursor), limit + 1);

      return pageFromRows(rows, limit);
    },

    createExperiment(projectId, payload) {
      const result = db
        .prepare(`
          INSERT INTO experiments (
            project_id,
            name,
            experiment_date,
            disc_diameter_mm,
            solids_content,
            pressed_thickness,
            notes,
            group_names_json,
            metadata_json
          )
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        `)
        .run(
          projectId,
          payload.name,
          nullIfUndefined(payload.experiment_date),
          nullIfUndefined(payload.disc_diameter_mm),
          nullIfUndefined(payload.solids_content),
          nullIfUndefined(payload.pressed_thickness),
          nullIfUndefined(payload.notes),
          stringifyOrNull(payload.group_names),
          stringifyOrNull(payload.metadata),
        );

      return this.getExperiment(Number(result.lastInsertRowid));
    },

    getExperiment(experimentId) {
      return db
        .prepare(`
          SELECT
            e.*,
            COUNT(c.id) AS cell_count
          FROM experiments e
          LEFT JOIN cells c ON c.experiment_id = e.id
          WHERE e.id = ?
          GROUP BY e.id
        `)
        .get(experimentId);
    },

    updateExperiment(experimentId, updates) {
      const fieldMap = {
        name: 'name',
        experiment_date: 'experiment_date',
        disc_diameter_mm: 'disc_diameter_mm',
        solids_content: 'solids_content',
        pressed_thickness: 'pressed_thickness',
        notes: 'notes',
        group_names: 'group_names_json',
        metadata: 'metadata_json',
      };

      const fields = [];
      const values = [];

      for (const [inputField, dbField] of Object.entries(fieldMap)) {
        if (updates[inputField] !== undefined) {
          fields.push(`${dbField} = ?`);
          if (inputField === 'group_names' || inputField === 'metadata') {
            values.push(stringifyOrNull(updates[inputField]));
          } else {
            values.push(updates[inputField]);
          }
        }
      }

      if (!fields.length) {
        return this.getExperiment(experimentId);
      }

      const result = db
        .prepare(`UPDATE experiments SET ${fields.join(', ')} WHERE id = ?`)
        .run(...values, experimentId);

      if (!result.changes) {
        return null;
      }

      return this.getExperiment(experimentId);
    },

    deleteExperiment(experimentId) {
      const result = db
        .prepare('DELETE FROM experiments WHERE id = ?')
        .run(experimentId);
      return result.changes > 0;
    },

    listCells(experimentId, { cursor = null, limit = 25 }) {
      const rows = db
        .prepare(`
          SELECT
            c.*,
            (
              SELECT COUNT(*)
              FROM cell_data_sources ds
              WHERE ds.cell_id = c.id
            ) AS data_source_count
          FROM cells c
          WHERE c.experiment_id = ?
            AND c.id < ?
          ORDER BY c.id DESC
          LIMIT ?
        `)
        .all(experimentId, normalizeCursor(cursor), limit + 1);

      return pageFromRows(rows, limit);
    },

    createCell(experimentId, payload) {
      db.exec('BEGIN');
      try {
        const result = db
          .prepare(`
            INSERT INTO cells (
              experiment_id,
              cell_name,
              file_name,
              loading,
              active_material_pct,
              formation_cycles,
              test_number,
              electrolyte,
              substrate,
              separator,
              formulation_json,
              group_assignment,
              excluded,
              porosity,
              cutoff_voltage_lower,
              cutoff_voltage_upper,
              anode_mass,
              cathode_mass,
              anode_loading,
              cathode_loading,
              anode_thickness,
              cathode_thickness,
              anode_area,
              cathode_area,
              np_ratio,
              overhang_ratio
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          `)
          .run(
            experimentId,
            payload.cell_name,
            nullIfUndefined(payload.file_name),
            nullIfUndefined(payload.loading),
            nullIfUndefined(payload.active_material_pct),
            payload.formation_cycles ?? 4,
            nullIfUndefined(payload.test_number),
            nullIfUndefined(payload.electrolyte),
            nullIfUndefined(payload.substrate),
            nullIfUndefined(payload.separator),
            stringifyOrNull(payload.formulation),
            nullIfUndefined(payload.group_assignment),
            payload.excluded ? 1 : 0,
            nullIfUndefined(payload.porosity),
            nullIfUndefined(payload.cutoff_voltage_lower),
            nullIfUndefined(payload.cutoff_voltage_upper),
            nullIfUndefined(payload.anode_mass),
            nullIfUndefined(payload.cathode_mass),
            nullIfUndefined(payload.anode_loading),
            nullIfUndefined(payload.cathode_loading),
            nullIfUndefined(payload.anode_thickness),
            nullIfUndefined(payload.cathode_thickness),
            nullIfUndefined(payload.anode_area),
            nullIfUndefined(payload.cathode_area),
            nullIfUndefined(payload.np_ratio),
            nullIfUndefined(payload.overhang_ratio),
          );

        const cellId = Number(result.lastInsertRowid);
        insertDataSources(db, cellId, payload.data_sources);
        db.exec('COMMIT');

        return this.getCell(cellId);
      } catch (error) {
        db.exec('ROLLBACK');
        throw error;
      }
    },

    getCell(cellId) {
      const cell = db
        .prepare(`
          SELECT
            c.*,
            (
              SELECT COUNT(*)
              FROM cell_data_sources ds
              WHERE ds.cell_id = c.id
            ) AS data_source_count
          FROM cells c
          WHERE c.id = ?
        `)
        .get(cellId);

      if (!cell) {
        return null;
      }

      const dataSources = db
        .prepare(`
          SELECT id, cell_id, source_type, path, payload_json, metadata_json, created_at
          FROM cell_data_sources
          WHERE cell_id = ?
          ORDER BY id DESC
        `)
        .all(cellId);

      return { cell, dataSources };
    },

    updateCell(cellId, updates) {
      db.exec('BEGIN');
      try {
        const existing = db.prepare('SELECT id FROM cells WHERE id = ?').get(cellId);
        if (!existing) {
          db.exec('ROLLBACK');
          return null;
        }

        const fieldMap = {
          cell_name: 'cell_name',
          file_name: 'file_name',
          loading: 'loading',
          active_material_pct: 'active_material_pct',
          formation_cycles: 'formation_cycles',
          test_number: 'test_number',
          electrolyte: 'electrolyte',
          substrate: 'substrate',
          separator: 'separator',
          formulation: 'formulation_json',
          group_assignment: 'group_assignment',
          excluded: 'excluded',
          porosity: 'porosity',
          cutoff_voltage_lower: 'cutoff_voltage_lower',
          cutoff_voltage_upper: 'cutoff_voltage_upper',
          anode_mass: 'anode_mass',
          cathode_mass: 'cathode_mass',
          anode_loading: 'anode_loading',
          cathode_loading: 'cathode_loading',
          anode_thickness: 'anode_thickness',
          cathode_thickness: 'cathode_thickness',
          anode_area: 'anode_area',
          cathode_area: 'cathode_area',
          np_ratio: 'np_ratio',
          overhang_ratio: 'overhang_ratio',
        };

        const fields = [];
        const values = [];

        for (const [inputField, dbField] of Object.entries(fieldMap)) {
          if (updates[inputField] !== undefined) {
            fields.push(`${dbField} = ?`);
            if (inputField === 'formulation') {
              values.push(stringifyOrNull(updates[inputField]));
            } else if (inputField === 'excluded') {
              values.push(updates[inputField] ? 1 : 0);
            } else {
              values.push(updates[inputField]);
            }
          }
        }

        if (fields.length) {
          db.prepare(`UPDATE cells SET ${fields.join(', ')} WHERE id = ?`).run(...values, cellId);
        }

        if (updates.data_sources !== undefined) {
          db.prepare('DELETE FROM cell_data_sources WHERE cell_id = ?').run(cellId);
          insertDataSources(db, cellId, updates.data_sources);
        }

        db.exec('COMMIT');
        return this.getCell(cellId);
      } catch (error) {
        db.exec('ROLLBACK');
        throw error;
      }
    },

    deleteCell(cellId) {
      const result = db.prepare('DELETE FROM cells WHERE id = ?').run(cellId);
      return result.changes > 0;
    },

    listProjectPreferences(projectId) {
      return db
        .prepare(`
          SELECT preference_key, preference_value, created_at, updated_at
          FROM project_preferences
          WHERE project_id = ?
          ORDER BY preference_key ASC
        `)
        .all(projectId);
    },

    upsertProjectPreference(projectId, preferenceKey, preferenceValue) {
      db.prepare(`
        INSERT INTO project_preferences (project_id, preference_key, preference_value)
        VALUES (?, ?, ?)
        ON CONFLICT(project_id, preference_key)
        DO UPDATE SET
          preference_value = excluded.preference_value,
          updated_at = CURRENT_TIMESTAMP
      `).run(projectId, preferenceKey, preferenceValue);

      return db
        .prepare(`
          SELECT preference_key, preference_value, created_at, updated_at
          FROM project_preferences
          WHERE project_id = ? AND preference_key = ?
        `)
        .get(projectId, preferenceKey);
    },
  };
}
