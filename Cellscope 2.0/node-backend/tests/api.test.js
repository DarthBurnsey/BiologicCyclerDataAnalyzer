import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { initDatabase } from '../src/db/connection.js';
import { createStore } from '../src/db/store.js';

function createTempStore() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cellscope2-node-test-'));
  const dbPath = path.join(tempDir, 'test.db');
  const db = initDatabase(dbPath);
  const store = createStore(db);
  return { db, store };
}

test('store supports project -> experiment -> cell lifecycle', () => {
  const { db, store } = createTempStore();

  const project = store.createProject({
    user_id: 'admin',
    name: 'Silicon Anode Program',
    description: 'Migration test project',
    project_type: 'Anode',
  });

  assert.equal(project.name, 'Silicon Anode Program');
  assert.equal(project.project_type, 'Anode');

  const experiment = store.createExperiment(project.id, {
    name: 'Exp-001',
    experiment_date: '2026-02-24',
    disc_diameter_mm: 15,
    solids_content: 42,
    pressed_thickness: 48,
    notes: 'Baseline trial',
    group_names: ['Group A', 'Group B'],
    metadata: { imported: false },
  });

  assert.equal(experiment.project_id, project.id);
  assert.equal(experiment.name, 'Exp-001');

  const createdCell = store.createCell(experiment.id, {
    cell_name: 'Cell-1',
    file_name: 'cell-1.json',
    loading: 5.1,
    active_material_pct: 92,
    formation_cycles: 3,
    test_number: 'T-001',
    electrolyte: '1M LiPF6 EC:DMC',
    substrate: 'Copper',
    separator: 'PP',
    formulation: [
      { Component: 'NMC811', 'Dry Mass Fraction (%)': 90 },
      { Component: 'PVDF', 'Dry Mass Fraction (%)': 5 },
    ],
    group_assignment: 'Group A',
    excluded: false,
    cutoff_voltage_lower: 2.8,
    cutoff_voltage_upper: 4.3,
    data_sources: [
      {
        source_type: 'parquet',
        path: 'data/experiments/cell_001.parquet',
      },
    ],
  });

  assert.equal(createdCell.cell.cell_name, 'Cell-1');
  assert.equal(createdCell.dataSources.length, 1);

  const fetchedExperiment = store.getExperiment(experiment.id);
  assert.equal(fetchedExperiment.cell_count, 1);

  const cellsPage = store.listCells(experiment.id, { limit: 10, cursor: null });
  assert.equal(cellsPage.items.length, 1);

  const projectAfter = store.getProject(project.id);
  assert.equal(projectAfter.experiment_count, 1);
  assert.equal(projectAfter.cell_count, 1);

  db.close();
});

test('store cursor pagination returns stable pages', () => {
  const { db, store } = createTempStore();

  for (let i = 0; i < 5; i += 1) {
    store.createProject({
      user_id: 'admin',
      name: `Project ${i + 1}`,
      description: null,
      project_type: 'Full Cell',
    });
  }

  const pageOne = store.listProjects({ limit: 2, cursor: null });
  assert.equal(pageOne.items.length, 2);
  assert.ok(pageOne.nextCursor);

  const pageTwo = store.listProjects({ limit: 2, cursor: pageOne.nextCursor });
  assert.equal(pageTwo.items.length, 2);

  const pageThree = store.listProjects({ limit: 2, cursor: pageTwo.nextCursor });
  assert.equal(pageThree.items.length, 1);
  assert.equal(pageThree.nextCursor, null);

  db.close();
});
