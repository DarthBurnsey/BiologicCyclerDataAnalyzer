# CellScope 2.0

A modern rebuild of CellScope focused on smoother performance by separating UI from data APIs.

## Current status

- `backend/`: original FastAPI prototype (kept intact)
- `node-backend/`: new Node.js backend with normalized schema + legacy import path
- `frontend/`: placeholder for the 2.0 web client

This keeps existing work untouched while allowing progressive migration.

## Node Backend (Recommended Path)

```bash
cd "Cellscope 2.0/node-backend"
npm run migrate
npm run start
```

- API base URL: `http://localhost:8080`
- DB default: `Cellscope 2.0/node-backend/data/cellscope2-node.db`

### Import old Streamlit data

```bash
npm run import:legacy
```

See full docs: [`node-backend/README.md`](./node-backend/README.md)

## FastAPI Prototype (Legacy 2.0 work)

If you still want to run the earlier prototype:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`
