import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';

import { schemaStatements } from './schema.js';

function ensureParentDirectory(filePath) {
  const parentDir = path.dirname(filePath);
  fs.mkdirSync(parentDir, { recursive: true });
}

export function createDatabase(dbPath) {
  ensureParentDirectory(dbPath);
  const db = new DatabaseSync(dbPath);

  db.exec(`
    PRAGMA foreign_keys = ON;
    PRAGMA journal_mode = WAL;
    PRAGMA synchronous = NORMAL;
    PRAGMA busy_timeout = 5000;
    PRAGMA temp_store = MEMORY;
    PRAGMA cache_size = -20000;
  `);

  return db;
}

export function migrateDatabase(db) {
  db.exec('BEGIN');
  try {
    for (const statement of schemaStatements) {
      db.exec(statement);
    }
    db.exec('PRAGMA user_version = 2');
    db.exec('COMMIT');
  } catch (error) {
    db.exec('ROLLBACK');
    throw error;
  }
}

export function initDatabase(dbPath) {
  const db = createDatabase(dbPath);
  migrateDatabase(db);
  return db;
}
