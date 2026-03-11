import { getConfig } from '../src/config.js';
import { initDatabase } from '../src/db/connection.js';

const config = getConfig();
const db = initDatabase(config.dbPath);
const version = db.prepare('PRAGMA user_version').get().user_version;
db.close();

console.log(`Migration complete.`);
console.log(`DB path: ${config.dbPath}`);
console.log(`Schema version: ${version}`);
