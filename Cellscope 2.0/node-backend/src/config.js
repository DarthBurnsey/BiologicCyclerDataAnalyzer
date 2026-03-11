import path from 'node:path';
import process from 'node:process';

const DEFAULT_PORT = 8080;
const DEFAULT_DB_FILE = './data/cellscope2-node.db';

function parsePort(value) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0 || parsed > 65535) {
    return DEFAULT_PORT;
  }
  return parsed;
}

export function getConfig(overrides = {}) {
  const port = parsePort(overrides.port ?? process.env.PORT ?? DEFAULT_PORT);
  const dbPathInput = overrides.dbPath ?? process.env.CELLSCOPE2_DB_PATH ?? DEFAULT_DB_FILE;

  return {
    appName: 'CellScope 2.0 Node API',
    version: '0.1.0',
    port,
    corsOrigin: overrides.corsOrigin ?? process.env.CORS_ORIGIN ?? '*',
    dbPath: path.resolve(process.cwd(), dbPathInput),
  };
}
