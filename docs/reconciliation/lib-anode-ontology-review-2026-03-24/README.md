# LIB Anode Ontology Reconciliation

- Source workbook: `/Volumes/2TB SSD/Anode Formulations 2024-25.xlsx`
- Legacy database: `/Users/bradyburns/Projects/CellScope/cellscope.db`

## Counts

- Parent batches: 40
- Variant batches: 17
- Materials: 18
- Review items: 4
- Mismatch items: 9

## What Needs Attention

- Confirm workbook fields that are still blank, ambiguous, or split across multiple candidate values.
- Review legacy-only experiment rows that do not map back to a workbook sheet.
- Resolve real disagreements where workbook measurements and legacy experiment data both exist.

## Files

- `ontology_import_preview.json`: full preview payload
- `ontology_import_issues.csv`: flattened review + mismatch issues
- `ontology_import_parent_batches.json`: parent batch preview
- `ontology_import_variant_batches.json`: variant batch preview
- `ontology_import_cell_builds.json`: proposed cell-build lineage preview
