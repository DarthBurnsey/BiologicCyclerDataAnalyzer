# CellScope 2.0 Backend

This backend now supports three runtime modes:

- `uvicorn app.main:app --reload --port 8000` for the API
- `python3 run_collector.py` for watched-folder collection
- `python3 run_reporter.py` for daily report scheduling

## Live Cycler Workflow

The live backend adds:

- `cycler_sources` and `cycler_channels` for watched export folders and cell mappings
- `test_runs` and `cycle_points` for normalized live cycling data
- `anomaly_events` for rule-based and operational alerts
- `daily_report_runs` and `notification_targets` for in-app + email reporting

BioLogic/BT-Test and BT-Analysis are handled in v1 through **watched auto-exported files**. The collector reuses the existing CellScope parser and anomaly logic from the root app.

## Quick Start

```bash
cd "Cellscope 2.0/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd "Cellscope 2.0/backend"
source .venv/bin/activate
python3 run_collector.py
```

And for the scheduled daily report worker:

```bash
cd "Cellscope 2.0/backend"
source .venv/bin/activate
python3 run_reporter.py
```

## Key Environment Variables

- `DATABASE_URL` default: `sqlite+aiosqlite:///./cellscope2.db`
- `REPORT_TIMEZONE` default: `America/Chicago`
- `REPORT_HOUR` default: `7`
- `REPORT_MINUTE` default: `0`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `REPORT_SENDER`

## Useful API Endpoints

- `GET /api/live/dashboard`
- `GET/POST /api/live/sources`
- `GET/POST /api/live/channels`
- `GET /api/live/runs`
- `GET /api/live/anomalies`
- `POST /api/live/collector/run-once`
- `GET /api/live/reports`
- `POST /api/live/reports/run`

## Tests

```bash
cd "Cellscope 2.0/backend"
PYTHONPYCACHEPREFIX=/tmp/cellscope_pycache python3 -m pytest tests/test_live_ops.py -q
```
