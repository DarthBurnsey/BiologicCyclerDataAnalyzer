# CellScope 2.0 Changelog

All notable changes to the CellScope 2.0 frontend and backend are tracked
here. Keep entries terse — one bullet per user-visible change — and link to
`docs/IMPROVEMENT_ROADMAP.md` items when applicable.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **Search & Filter — item count badges.** Each filter checkbox now shows
  `(N)` reflecting how many records would match if that value were selected,
  respecting the other currently-active filters. (Roadmap 1.1)
- **Search & Filter — Date Range filter.** New From/To inputs in a new
  `Experiment date` accordion section; filters `state.cohortRecords` by
  `experiment_date` client-side. (Roadmap 1.1)
- **Search & Filter — search-within-filter.** Long checkbox lists (Projects,
  Parent batch, Electrolyte, Tracking status) now have a small search input
  that filters visible rows as you type. (Roadmap 1.1)
- **Search & Filter — column picker.** New gear button in the results
  toolbar opens a popover to toggle visible columns (Project, Electrolyte,
  Parent batch, Cells, Retention %, Cycle life, Status). Selection persists
  in `localStorage` under `cs2.sfColumns`. (Roadmap 1.2)

### Changed
- `populateSfFilters` now re-runs on each filter change so count badges stay
  live against the current filtered set.
- `renderSfResults` column definitions are now gated by `state.sfColumnsVisible`
  and can be reordered/toggled at runtime.

### Fixed
- **Widgets showed "No data" for every per-cycle chart.** The backend ships
  each cell's cycling data as a raw pandas `to_json()` string (columns
  orient, with column names like `Cycle` and `Q Dis (mAh/g)`), but the
  widget renderer was looking for pre-extracted `cell.cycles`,
  `cell.discharge_capacity`, `cell.retention`, `cell.coulombic_efficiency`
  arrays that were never populated. Added `hydrateCellCycles` /
  `hydrateCellsData` in `frontend/src/main.js` that runs once per cell to
  parse `data_json`, extract cycle + capacity arrays, auto-scale
  Coulombic efficiency from fraction to percent when needed, and derive
  capacity retention from discharge capacity when the backend does not
  ship it. `renderWorkspaceCanvas` and `renderPerCycleWidget` now call
  the hydration path before reading arrays.
- **Per-cycle widget cell names fell through to "Cell N".** The render
  loop and `buildGroupMap` only checked `cell.cell_name` / `cell.name`,
  neither of which is set by the backend. Added `getCellDisplayName` and
  rewired both to prefer `cell_id` / `test_number`, so traces show
  meaningful labels and grouping works.
- **Null/NaN cycle points broke Plotly traces.** Added a
  `Number.isFinite` filter on the `(x, y)` pairs before plotting so a
  stray null in either series no longer blanks the whole line.
- **Manage Widgets drawer squeezed the widget canvas.** Moved
  `.manage-widgets-sidebar` from inline `position: sticky` to a fixed
  right-edge drawer (`position: fixed; right: 18px`), so the widget grid
  renders full-width behind it. Widget grid min column width lowered
  from 460px to 360px so charts still flow cleanly in narrow panels.
  Added `schedulePlotlyResize` to reflow Plotly charts when the drawer
  opens/closes.
- **Raw members table crowded the workspace.** The table that dumped the
  first 8 raw snake_case keys now uses a curated column map
  (`Experiment`, `Project`, `Type`, `Electrolyte`, `Parent batch`,
  `Status`, `Experiment date`, `Created`) and is wrapped in a
  `<details>` collapsed by default.

- **App boot / tab navigation.** Moved `SF_COLUMN_DEFS`,
  `SF_COLUMNS_STORAGE_KEY`, `defaultSfColumnsVisible`, and
  `loadSfColumnsVisible` above the top-level `state = {…}` initializer in
  `frontend/src/main.js`. They were previously declared further down, which
  meant the state initializer hit a temporal-dead-zone error on
  `SF_COLUMN_DEFS`, the module failed to import, `DOMContentLoaded` never
  bound handlers, and view-tab / sub-tab navigation appeared dead.

### Documentation
- Added `docs/IMPROVEMENT_ROADMAP.md` tracking the full Tier 1–3 plan.
- Added this changelog.
