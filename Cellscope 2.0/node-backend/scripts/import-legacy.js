import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { DatabaseSync } from 'node:sqlite';

import { getConfig } from '../src/config.js';
import { initDatabase } from '../src/db/connection.js';

function safeParseJson(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  if (typeof value !== 'string') {
    return value;
  }
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function pick(...values) {
  for (const value of values) {
    if (value !== null && value !== undefined && value !== '') {
      return value;
    }
  }
  return null;
}

function toNumberOrNull(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function toIntegerOrDefault(value, defaultValue = 4) {
  if (value === null || value === undefined || value === '') {
    return defaultValue;
  }
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : defaultValue;
}

function normalizeTimestamp(value) {
  if (value === null || value === undefined || value === '') {
    return new Date().toISOString();
  }
  return String(value);
}

function normalizeProjectType(projectType) {
  const value = String(projectType ?? '').trim();
  if (value === 'Cathode' || value === 'Anode' || value === 'Full Cell') {
    return value;
  }
  return 'Full Cell';
}

function normalizeGroupNames(parsed, row) {
  const parsedGroupNames = parsed?.group_names;
  if (Array.isArray(parsedGroupNames)) {
    const names = parsedGroupNames.map((item) => String(item).trim()).filter(Boolean);
    return names.length ? names : null;
  }

  const assignments = parsed?.group_assignments;
  if (assignments && typeof assignments === 'object' && !Array.isArray(assignments)) {
    const names = [...new Set(Object.values(assignments).map((value) => String(value).trim()).filter(Boolean))];
    return names.length ? names : null;
  }

  const nestedCells = Array.isArray(parsed?.cells) ? parsed.cells : null;
  if (nestedCells?.length) {
    const names = [...new Set(
      nestedCells
        .map((cell) => cell?.group_assignment)
        .filter((value) => value !== null && value !== undefined && value !== '')
        .map((value) => String(value).trim()),
    )];

    if (names.length) {
      return names;
    }
  }

  if (row.group_assignment) {
    return [String(row.group_assignment).trim()];
  }

  return null;
}

function deriveExperimentName(row, group, parsed) {
  const fromGroup = group?.experiment_name;
  if (fromGroup) {
    return String(fromGroup).trim();
  }

  const fromParsed = parsed?.experiment_name;
  if (fromParsed) {
    return String(fromParsed).trim();
  }

  if (row.file_name) {
    return String(row.file_name).replace(/\.[^.]+$/, '').trim();
  }

  if (row.cell_name) {
    return String(row.cell_name).trim();
  }

  return `Experiment ${row.id}`;
}

function serializeFormulation(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }

  if (typeof value === 'string') {
    const parsed = safeParseJson(value);
    if (parsed !== null) {
      return JSON.stringify(parsed);
    }
    return JSON.stringify(value);
  }

  return JSON.stringify(value);
}

function extractCellEntries(row, parsedData) {
  if (parsedData && Array.isArray(parsedData.cells) && parsedData.cells.length > 0) {
    return parsedData.cells.map((cell, index) => ({
      source: cell,
      nestedIndex: index,
      isNested: true,
    }));
  }

  return [{ source: row, nestedIndex: 0, isNested: false }];
}

function buildCellPayload(row, source, createdAt) {
  return {
    cell_name: String(pick(source.cell_name, source.name, row.cell_name, `Cell ${row.id}`)).trim(),
    file_name: pick(source.file_name, row.file_name),
    loading: toNumberOrNull(pick(source.loading, row.loading)),
    active_material_pct: toNumberOrNull(
      pick(source.active_material_pct, source.active_material, row.active_material),
    ),
    formation_cycles: toIntegerOrDefault(pick(source.formation_cycles, row.formation_cycles), 4),
    test_number: pick(source.test_number, row.test_number),
    electrolyte: pick(source.electrolyte, row.electrolyte),
    substrate: pick(source.substrate, row.substrate),
    separator: pick(source.separator, row.separator),
    formulation_json: serializeFormulation(pick(source.formulation, row.formulation_json)),
    group_assignment: pick(source.group_assignment, row.group_assignment),
    excluded: source.excluded ? 1 : 0,
    porosity: toNumberOrNull(pick(source.porosity, row.porosity)),
    cutoff_voltage_lower: toNumberOrNull(pick(source.cutoff_voltage_lower, row.cutoff_voltage_lower)),
    cutoff_voltage_upper: toNumberOrNull(pick(source.cutoff_voltage_upper, row.cutoff_voltage_upper)),
    anode_mass: toNumberOrNull(pick(source.anode_mass, row.anode_mass)),
    cathode_mass: toNumberOrNull(pick(source.cathode_mass, row.cathode_mass)),
    anode_loading: toNumberOrNull(pick(source.anode_loading, row.anode_loading)),
    cathode_loading: toNumberOrNull(pick(source.cathode_loading, row.cathode_loading)),
    anode_thickness: toNumberOrNull(pick(source.anode_thickness, row.anode_thickness)),
    cathode_thickness: toNumberOrNull(pick(source.cathode_thickness, row.cathode_thickness)),
    anode_area: toNumberOrNull(pick(source.anode_area, row.anode_area)),
    cathode_area: toNumberOrNull(pick(source.cathode_area, row.cathode_area)),
    np_ratio: toNumberOrNull(pick(source.np_ratio, row.np_ratio)),
    overhang_ratio: toNumberOrNull(pick(source.overhang_ratio, row.overhang_ratio)),
    created_at: createdAt,
    updated_at: createdAt,
  };
}

function buildDataSources(row, source, parsedData, isNested) {
  const sources = [];

  const parquetPath = pick(source.parquet_path, row.parquet_path);
  if (parquetPath) {
    sources.push({
      source_type: 'parquet',
      path: String(parquetPath),
      payload_json: null,
      metadata_json: null,
    });
  }

  const nestedDataJson = source?.data_json;
  if (nestedDataJson) {
    sources.push({
      source_type: 'legacy_json',
      path: null,
      payload_json: typeof nestedDataJson === 'string' ? nestedDataJson : JSON.stringify(nestedDataJson),
      metadata_json: null,
    });
  } else if (!isNested && row.data_json) {
    const parsed = safeParseJson(row.data_json);
    const rowContainsNestedCells = parsed && Array.isArray(parsed.cells);
    if (!rowContainsNestedCells) {
      sources.push({
        source_type: 'legacy_json',
        path: null,
        payload_json: String(row.data_json),
        metadata_json: null,
      });
    }
  }

  if (!sources.length && parsedData && !isNested && parsedData !== null) {
    sources.push({
      source_type: 'legacy_json',
      path: null,
      payload_json: JSON.stringify(parsedData),
      metadata_json: JSON.stringify({ imported_from: 'cell_experiments.data_json' }),
    });
  }

  return sources;
}

function getTargetCount(db) {
  const row = db.prepare('SELECT COUNT(*) AS count FROM projects').get();
  return Number(row?.count ?? 0);
}

function legacyPathFromArgs() {
  const maybePathArg = process.argv[2] && !process.argv[2].startsWith('--')
    ? process.argv[2]
    : '../../cellscope.db';

  return path.resolve(process.cwd(), maybePathArg);
}

function hasFlag(flagName) {
  return process.argv.includes(flagName);
}

const config = getConfig();
const legacyDbPath = legacyPathFromArgs();
const allowAppend = hasFlag('--append');

if (!fs.existsSync(legacyDbPath)) {
  throw new Error(`Legacy database not found: ${legacyDbPath}`);
}

const targetDb = initDatabase(config.dbPath);
const existingCount = getTargetCount(targetDb);
if (existingCount > 0 && !allowAppend) {
  targetDb.close();
  throw new Error(
    [
      `Target DB already has data (${existingCount} project rows).`,
      'Run with --append to import into a non-empty target database.',
      `Target DB: ${config.dbPath}`,
    ].join('\n'),
  );
}

const legacyDb = new DatabaseSync(legacyDbPath);

const stats = {
  projects: 0,
  experiments: 0,
  cells: 0,
  data_sources: 0,
  preferences: 0,
};

const insertProject = targetDb.prepare(`
  INSERT INTO projects (
    legacy_project_id,
    user_id,
    name,
    description,
    project_type,
    created_at,
    updated_at
  )
  VALUES (?, ?, ?, ?, ?, ?, ?)
  ON CONFLICT(legacy_project_id) DO UPDATE SET
    user_id = excluded.user_id,
    name = excluded.name,
    description = excluded.description,
    project_type = excluded.project_type,
    created_at = excluded.created_at,
    updated_at = excluded.updated_at
`);

const selectMappedProject = targetDb.prepare('SELECT id FROM projects WHERE legacy_project_id = ?');

const insertExperiment = targetDb.prepare(`
  INSERT INTO experiments (
    legacy_experiment_id,
    project_id,
    name,
    experiment_date,
    disc_diameter_mm,
    solids_content,
    pressed_thickness,
    notes,
    group_names_json,
    metadata_json,
    created_at,
    updated_at
  )
  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
`);

const insertCell = targetDb.prepare(`
  INSERT INTO cells (
    legacy_cell_id,
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
    overhang_ratio,
    created_at,
    updated_at
  )
  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
`);

const insertDataSource = targetDb.prepare(`
  INSERT INTO cell_data_sources (cell_id, source_type, path, payload_json, metadata_json)
  VALUES (?, ?, ?, ?, ?)
`);

const insertPreference = targetDb.prepare(`
  INSERT INTO project_preferences (project_id, preference_key, preference_value, created_at, updated_at)
  VALUES (?, ?, ?, ?, ?)
  ON CONFLICT(project_id, preference_key) DO UPDATE SET
    preference_value = excluded.preference_value,
    updated_at = excluded.updated_at
`);

const projectIdMap = new Map();
const experimentIdMap = new Map();

try {
  targetDb.exec('BEGIN');

  const legacyProjects = legacyDb.prepare(`
    SELECT id, user_id, name, description, project_type, created_date, last_modified
    FROM projects
    ORDER BY id ASC
  `).all();

  for (const legacyProject of legacyProjects) {
    insertProject.run(
      legacyProject.id,
      legacyProject.user_id ?? 'admin',
      legacyProject.name,
      legacyProject.description,
      normalizeProjectType(legacyProject.project_type),
      normalizeTimestamp(legacyProject.created_date),
      normalizeTimestamp(legacyProject.last_modified ?? legacyProject.created_date),
    );

    const mappedProject = selectMappedProject.get(legacyProject.id);
    if (!mappedProject) {
      continue;
    }

    projectIdMap.set(legacyProject.id, mappedProject.id);
    stats.projects += 1;
  }

  const legacyPreferences = legacyDb.prepare(`
    SELECT project_id, preference_key, preference_value, created_date, updated_date
    FROM project_preferences
  `).all();

  for (const preference of legacyPreferences) {
    const mappedProjectId = projectIdMap.get(preference.project_id);
    if (!mappedProjectId) {
      continue;
    }

    insertPreference.run(
      mappedProjectId,
      preference.preference_key,
      preference.preference_value,
      normalizeTimestamp(preference.created_date),
      normalizeTimestamp(preference.updated_date ?? preference.created_date),
    );
    stats.preferences += 1;
  }

  const legacyGroups = legacyDb.prepare(`
    SELECT id, project_id, experiment_name, experiment_date, disc_diameter_mm
    FROM experiment_groups
  `).all();

  const groupById = new Map(legacyGroups.map((group) => [group.id, group]));

  const legacyRows = legacyDb.prepare('SELECT * FROM cell_experiments ORDER BY id ASC').all();
  for (const legacyRow of legacyRows) {
    const mappedProjectId = projectIdMap.get(legacyRow.project_id);
    if (!mappedProjectId) {
      continue;
    }

    const parsedData = safeParseJson(legacyRow.data_json);
    const group = legacyRow.experiment_group_id
      ? groupById.get(legacyRow.experiment_group_id)
      : null;

    const experimentKey = group
      ? `group:${mappedProjectId}:${group.id}`
      : `row:${mappedProjectId}:${legacyRow.id}`;

    let mappedExperimentId = experimentIdMap.get(experimentKey);
    if (!mappedExperimentId) {
      const groupNames = normalizeGroupNames(parsedData, legacyRow);
      const metadata = parsedData && typeof parsedData === 'object'
        ? {
            imported_from_legacy: true,
            group_assignments: parsedData.group_assignments ?? null,
            cell_format: parsedData.cell_format ?? null,
          }
        : null;

      const experimentInsert = insertExperiment.run(
        legacyRow.id,
        mappedProjectId,
        deriveExperimentName(legacyRow, group, parsedData),
        pick(parsedData?.experiment_date, group?.experiment_date),
        toNumberOrNull(pick(parsedData?.disc_diameter_mm, group?.disc_diameter_mm)),
        toNumberOrNull(pick(legacyRow.solids_content, parsedData?.solids_content)),
        toNumberOrNull(pick(legacyRow.pressed_thickness, parsedData?.pressed_thickness)),
        pick(legacyRow.experiment_notes, parsedData?.experiment_notes),
        groupNames ? JSON.stringify(groupNames) : null,
        metadata ? JSON.stringify(metadata) : null,
        normalizeTimestamp(legacyRow.created_date),
        normalizeTimestamp(legacyRow.created_date),
      );

      mappedExperimentId = Number(experimentInsert.lastInsertRowid);
      experimentIdMap.set(experimentKey, mappedExperimentId);
      stats.experiments += 1;
    }

    const cells = extractCellEntries(legacyRow, parsedData);
    for (const entry of cells) {
      const cellPayload = buildCellPayload(
        legacyRow,
        entry.source,
        normalizeTimestamp(legacyRow.created_date),
      );

      const cellInsert = insertCell.run(
        legacyRow.id,
        mappedExperimentId,
        cellPayload.cell_name,
        cellPayload.file_name,
        cellPayload.loading,
        cellPayload.active_material_pct,
        cellPayload.formation_cycles,
        cellPayload.test_number,
        cellPayload.electrolyte,
        cellPayload.substrate,
        cellPayload.separator,
        cellPayload.formulation_json,
        cellPayload.group_assignment,
        cellPayload.excluded,
        cellPayload.porosity,
        cellPayload.cutoff_voltage_lower,
        cellPayload.cutoff_voltage_upper,
        cellPayload.anode_mass,
        cellPayload.cathode_mass,
        cellPayload.anode_loading,
        cellPayload.cathode_loading,
        cellPayload.anode_thickness,
        cellPayload.cathode_thickness,
        cellPayload.anode_area,
        cellPayload.cathode_area,
        cellPayload.np_ratio,
        cellPayload.overhang_ratio,
        normalizeTimestamp(cellPayload.created_at),
        normalizeTimestamp(cellPayload.updated_at),
      );

      const mappedCellId = Number(cellInsert.lastInsertRowid);
      stats.cells += 1;

      const sources = buildDataSources(legacyRow, entry.source, parsedData, entry.isNested);
      for (const source of sources) {
        insertDataSource.run(
          mappedCellId,
          source.source_type,
          source.path,
          source.payload_json,
          source.metadata_json,
        );
        stats.data_sources += 1;
      }
    }
  }

  targetDb.exec('COMMIT');
} catch (error) {
  targetDb.exec('ROLLBACK');
  legacyDb.close();
  targetDb.close();
  throw error;
}

legacyDb.close();
targetDb.close();

console.log('Legacy import complete.');
console.log(`Legacy DB: ${legacyDbPath}`);
console.log(`Target DB: ${config.dbPath}`);
console.log(`Projects imported: ${stats.projects}`);
console.log(`Experiments imported: ${stats.experiments}`);
console.log(`Cells imported: ${stats.cells}`);
console.log(`Data sources imported: ${stats.data_sources}`);
console.log(`Preferences imported: ${stats.preferences}`);
