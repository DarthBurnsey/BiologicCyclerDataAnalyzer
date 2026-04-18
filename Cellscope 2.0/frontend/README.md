# CellScope 2.0 Frontend

This is a dependency-light first test shell for the CellScope 2.0 FastAPI backend.

## What it covers

- Live dashboard
- Mapping review queue + resolve action
- Run detail, provenance, and metrics
- Ontology batch lookup with lineage/descendants

## Start the backend first

```bash
cd "/Users/bradyburns/Projects/CellScope/Cellscope 2.0/backend"
uvicorn app.main:app --reload --port 8000
```

If `8000` is already being used by another local CellScope service, run the 2.0 backend on a dedicated port instead:

```bash
cd "/Users/bradyburns/Projects/CellScope/Cellscope 2.0/backend"
uvicorn app.main:app --reload --port 8001
```

Optional worker processes for richer live data:

```bash
cd "/Users/bradyburns/Projects/CellScope/Cellscope 2.0/backend"
python3 run_collector.py
python3 run_reporter.py
```

## Start the frontend

```bash
cd "/Users/bradyburns/Projects/CellScope/Cellscope 2.0/frontend"
npm start
```

The frontend serves on `http://localhost:5173` and proxies `/api/*` to `http://localhost:8000` by default.

If your backend is on a different host or port:

```bash
cd "/Users/bradyburns/Projects/CellScope/Cellscope 2.0/frontend"
BACKEND_ORIGIN=http://localhost:8001 npm start
```

If the health check works but `/api/live/dashboard` returns `404`, the frontend is probably talking to the wrong local API. Point `BACKEND_ORIGIN` at the dedicated 2.0 backend port and restart the frontend server.
