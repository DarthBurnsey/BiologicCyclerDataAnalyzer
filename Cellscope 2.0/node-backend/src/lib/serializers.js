import { parseJsonText } from './http.js';

function asBoolean(value) {
  return Boolean(value);
}

function asNumberOrNull(value) {
  if (value === null || value === undefined) {
    return null;
  }
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

export function serializeProject(row) {
  if (!row) {
    return null;
  }

  return {
    id: row.id,
    user_id: row.user_id,
    name: row.name,
    description: row.description,
    project_type: row.project_type,
    created_at: row.created_at,
    updated_at: row.updated_at,
    experiment_count: Number(row.experiment_count ?? 0),
    cell_count: Number(row.cell_count ?? 0),
  };
}

export function serializeExperiment(row) {
  if (!row) {
    return null;
  }

  return {
    id: row.id,
    project_id: row.project_id,
    name: row.name,
    experiment_date: row.experiment_date,
    disc_diameter_mm: asNumberOrNull(row.disc_diameter_mm),
    solids_content: asNumberOrNull(row.solids_content),
    pressed_thickness: asNumberOrNull(row.pressed_thickness),
    notes: row.notes,
    group_names: parseJsonText(row.group_names_json, []),
    metadata: parseJsonText(row.metadata_json, null),
    created_at: row.created_at,
    updated_at: row.updated_at,
    cell_count: Number(row.cell_count ?? 0),
  };
}

export function serializeCell(row) {
  if (!row) {
    return null;
  }

  return {
    id: row.id,
    experiment_id: row.experiment_id,
    cell_name: row.cell_name,
    file_name: row.file_name,
    loading: asNumberOrNull(row.loading),
    active_material_pct: asNumberOrNull(row.active_material_pct),
    formation_cycles: Number(row.formation_cycles ?? 0),
    test_number: row.test_number,
    electrolyte: row.electrolyte,
    substrate: row.substrate,
    separator: row.separator,
    formulation: parseJsonText(row.formulation_json, null),
    group_assignment: row.group_assignment,
    excluded: asBoolean(row.excluded),
    porosity: asNumberOrNull(row.porosity),
    cutoff_voltage_lower: asNumberOrNull(row.cutoff_voltage_lower),
    cutoff_voltage_upper: asNumberOrNull(row.cutoff_voltage_upper),
    anode_mass: asNumberOrNull(row.anode_mass),
    cathode_mass: asNumberOrNull(row.cathode_mass),
    anode_loading: asNumberOrNull(row.anode_loading),
    cathode_loading: asNumberOrNull(row.cathode_loading),
    anode_thickness: asNumberOrNull(row.anode_thickness),
    cathode_thickness: asNumberOrNull(row.cathode_thickness),
    anode_area: asNumberOrNull(row.anode_area),
    cathode_area: asNumberOrNull(row.cathode_area),
    np_ratio: asNumberOrNull(row.np_ratio),
    overhang_ratio: asNumberOrNull(row.overhang_ratio),
    created_at: row.created_at,
    updated_at: row.updated_at,
    data_source_count: Number(row.data_source_count ?? 0),
  };
}

export function serializeDataSource(row) {
  if (!row) {
    return null;
  }

  return {
    id: row.id,
    cell_id: row.cell_id,
    source_type: row.source_type,
    path: row.path,
    payload_json: parseJsonText(row.payload_json, row.payload_json),
    metadata: parseJsonText(row.metadata_json, null),
    created_at: row.created_at,
  };
}
