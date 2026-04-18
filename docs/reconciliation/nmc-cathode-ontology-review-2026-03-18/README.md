# NMC Cathode Ontology Reconciliation

- Source workbook: `/Users/bradyburns/Projects/CellScope/NMC Cathode Formulations 2025.xlsx`
- Legacy database: `/Users/bradyburns/Projects/CellScope/cellscope.db`
- Comparison workbook: `None`

## Counts

- Parent batches: 16
- Variant batches: 36
- Materials: 8
- Review items: 23
- Mismatch items: 23

## What Needs Reconciliation

- Confirm highlighted parent-sheet inputs that were intentionally skipped.
- Resolve workbook-only and legacy-only experiment aliases before persistence.
- Review real data disagreements where workbook and DB both exist.

## Files

- `ontology_import_preview.json`: full preview payload
- `ontology_import_issues.csv`: flattened review + mismatch issues
- `ontology_import_parent_batches.json`: parent batch preview
- `ontology_import_variant_batches.json`: variant batch preview
- `ontology_import_cell_builds.json`: proposed cell-build lineage preview
