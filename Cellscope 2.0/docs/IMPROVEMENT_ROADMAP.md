# CellScope 2.0 — UX Improvement Roadmap

Living document tracking planned UX/feature improvements to the CellScope 2.0
frontend and supporting backend. Organized by effort/value tier. See
`CHANGELOG.md` for what has actually landed.

Last updated: 2026-04-17

---

## Tier 1 — High Value, Low Effort (~1–2 sessions each)

### 1.1 Enrich Search & Filter sidebar
- **Date Range filter** with From/To inputs (filters by experiment start date
  — `experiment_date` on cohort records).
- **AND/OR operator toggle per filter section** (currently always AND across
  sections, OR within). Toggle would flip within-section logic.
- **Item count badges** next to each checkbox label (`NMC Half Cells (12)`),
  reflecting how many records match *after* other filters are applied.
- **Search-within-filter** input inside each long checkbox list (Projects,
  Batches, Electrolytes, Tracking status).
- Files: `frontend/index.html` (per-accordion section HTML),
  `frontend/src/main.js` (`populateSfFilters`, `applySfFilters`,
  `renderSfResults`), `frontend/styles.css`.

### 1.2 Results table column config
- Gear/columns button in the toolbar opens a dropdown/popover.
- Toggle visibility of: Cells, Retention %, Cycle Life, Fade Rate,
  Electrolyte, Parent batch, Project, Status.
- Persist selection in `localStorage` (key: `cs2.sfColumns`).
- Files: `frontend/src/main.js` (`renderSfResults`), `frontend/styles.css`.

### 1.3 Workspace list improvements
- Add `Description`, `Share Status` (Private/Shared), `Last modified`
  columns to the workspace list table.
- Add `Archive` action (moves workspace out of active list).
- Files: `frontend/src/main.js` (workspace list render),
  `backend/app/api/cells.py` / `backend/app/services/workspaces.py`
  (extra fields + `archived` flag).

## Tier 2 — Medium Complexity (~2–3 sessions each)

### 2.1 Widget: Normalization & Transforms
- Normalization section in Manage Widgets sidebar.
- Options: **Normalize to cycle 1**, **Normalize by capacity**,
  **Normalize by active mass**.
- Apply server-side or client-side before generating the chart.
- Files: `frontend/index.html`, `frontend/src/main.js` (`generateActiveWidget`),
  backend widget service.

### 2.2 Widget: Cycle Selector
- Add Cycle Selector to Manage Widgets: pick specific cycles (1, 10, 50, 100)
  or a range.
- Essential for time-series overlays and formation analysis.
- Files: `frontend/index.html`, `frontend/src/main.js`.

### 2.3 Widget: Groups & Categories
- Add `Add Grouping` button — split traces by an attribute (e.g. group by
  Electrolyte → separate colored series per electrolyte).
- Unlocks real comparative analysis across material variants.
- Files: `frontend/src/main.js` (`generateActiveWidget`, chart render logic).

### 2.4 Saved filter tabs
- `Save this filter` button in Search & Filter toolbar.
- Saved filters appear as named chips/tabs above the results panel.
- Persist in backend as named cohort filter presets.
- Files: new UI pattern in `wsPaneSearch`, backend endpoint.

## Tier 3 — Larger Features (~3–5 sessions each)

### 3.1 Time Series widget data type
- Widgets that plot voltage-vs-time or current-vs-time (raw cycler data),
  not just per-cycle summaries.
- Requires streaming/paginating raw cycle data from backend.
  Voltaiq calls this "Per-Cycle Metrics" (current) vs "Time Series" (raw).
- Files: backend parquet reads, `frontend/src/main.js` widget generation,
  Plotly trace builder.

### 3.2 Experiment detail view
- Clicking an experiment row in Search & Filter opens a detail panel with:
  - Metadata table (all fields, custom attributes)
  - Quick sparkline of retention-over-cycles
  - Links to open in workspace
- Mirrors Voltaiq's test record metadata view.
- Files: new side-panel in `frontend/index.html`,
  `frontend/src/main.js` detail load function.

### 3.3 Workspace Templates
- Save a workspace as a Template (strips data, keeps widget config).
- Apply a template to any new cohort → instantly get a pre-configured set
  of widgets.
- Files: backend workspace model (add `is_template` flag), frontend
  template picker in workspace create flow.

---

## Quick-win priority (first implementation pass)

The three items below were implemented as the opening pass because they are
purely frontend and ship high UX value with low risk:

1. **Item counts in filter checkboxes** — `populateSfFilters` already has the
   data, just needed to count records per value post-filters and render the
   count next to each label.
2. **Date Range filter** — two date inputs in the sidebar filter
   `state.cohortRecords` by `experiment_date` client-side.
3. **Column picker for results table** — gear-icon popover that toggles which
   columns `renderSfResults` includes, persisted in `localStorage`.

In the same pass we also shipped **search-within-filter** for each long
checkbox list, since it is trivial once the per-section render is
parameterized.

See `CHANGELOG.md` for the exact landing history.
