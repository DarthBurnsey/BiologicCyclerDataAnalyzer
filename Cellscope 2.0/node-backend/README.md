# CellScope 2.0 Node Backend

Node.js API backend for CellScope 2.0 with a normalized SQLite schema and migration path from the current Streamlit database.

## Why this exists

The Streamlit app rerenders heavily and couples UI + data operations. This backend splits data access into a dedicated API so the frontend can request smaller payloads and update only changed views.

## Stack

- Node.js 24+
- Built-in `node:sqlite` (no external runtime dependencies)
- Built-in `http` server with JSON REST routes

## Quick Start

```bash
cd "Cellscope 2.0/node-backend"
cp .env.example .env
npm run migrate
npm run start
```

By default the API runs on `http://localhost:8080`.

## Environment

- `PORT` (default: `8080`)
- `CELLSCOPE2_DB_PATH` (default: `./data/cellscope2-node.db`)
- `CORS_ORIGIN` (default: `*`)

## Import Existing Legacy Data

Import from the existing Streamlit SQLite database (`../../cellscope.db` by default):

```bash
npm run import:legacy
```

Import from a specific DB path:

```bash
npm run import:legacy -- ../../path/to/cellscope.db
```

If the target database is not empty, the importer aborts by default. Use append mode explicitly:

```bash
npm run import:legacy -- ../../path/to/cellscope.db --append
```

## API Overview

- `GET /api/health`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/:projectId`
- `PATCH /api/projects/:projectId`
- `DELETE /api/projects/:projectId`
- `GET /api/projects/:projectId/experiments`
- `POST /api/projects/:projectId/experiments`
- `GET /api/experiments/:experimentId`
- `PATCH /api/experiments/:experimentId`
- `DELETE /api/experiments/:experimentId`
- `GET /api/experiments/:experimentId/cells`
- `POST /api/experiments/:experimentId/cells`
- `GET /api/cells/:cellId`
- `PATCH /api/cells/:cellId`
- `DELETE /api/cells/:cellId`
- `GET /api/projects/:projectId/preferences`
- `PUT /api/projects/:projectId/preferences/:preferenceKey`

List endpoints use cursor pagination (`limit`, `cursor`) for fast incremental reads.

## Tests

```bash
npm test
```

Tests run on temporary SQLite files and validate API lifecycle + cursor pagination behavior.
