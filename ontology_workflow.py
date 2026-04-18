"""Helpers for surfacing ontology context inside the legacy CellScope workflow."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


BASE_DIR = Path(__file__).resolve().parent
LEGACY_DB_PATH = BASE_DIR / "cellscope.db"
ONTOLOGY_DB_PATH = BASE_DIR / "Cellscope 2.0" / "backend" / "cellscope2.db"


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalized_key(value: Any) -> Optional[str]:
    text = _text(value)
    return text.casefold() if text else None


def _load_json(value: Any) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _dedupe_preserve(values: list[Any]) -> list[Any]:
    output: list[Any] = []
    seen = set()
    for value in values:
        key = json.dumps(value, sort_keys=True) if isinstance(value, dict) else value
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def normalize_ontology_context(raw_context: Any) -> Dict[str, Any]:
    if not isinstance(raw_context, dict):
        return {}

    context = dict(raw_context)
    for field_name in ("batch_name", "parent_batch_name", "root_batch_name"):
        display_name = f"display_{field_name}"
        if not _text(context.get(display_name)) and _text(context.get(field_name)):
            context[display_name] = _text(context.get(field_name))

    if not _text(context.get("root_batch_name")):
        fallback_root = _text(context.get("parent_batch_name")) or _text(context.get("batch_name"))
        if fallback_root:
            context["root_batch_name"] = fallback_root
            context["display_root_batch_name"] = fallback_root

    linked_names = context.get("linked_cell_build_names")
    if isinstance(linked_names, list) and "display_linked_cell_build_names" not in context:
        context["display_linked_cell_build_names"] = [_text(name) or str(name) for name in linked_names]

    return context


@lru_cache(maxsize=1)
def _load_batch_graph() -> Dict[str, Any]:
    if not ONTOLOGY_DB_PATH.exists():
        return {"batches_by_id": {}, "batch_id_by_name": {}}

    connection = sqlite3.connect(ONTOLOGY_DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT id, batch_name, electrode_role, metadata_json
            FROM ontology_electrode_batches
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        connection.close()

    batches_by_id: Dict[int, Dict[str, Any]] = {}
    batch_id_by_name: Dict[str, int] = {}
    for row in rows:
        metadata = _load_json(row["metadata_json"])
        display_batch_name = _text(row["batch_name"]) or str(row["batch_name"])
        normalized_name = _normalized_key(display_batch_name)
        if normalized_name:
            batch_id_by_name[normalized_name] = int(row["id"])

        batches_by_id[int(row["id"])] = {
            "id": int(row["id"]),
            "batch_name": row["batch_name"],
            "display_batch_name": display_batch_name,
            "electrode_role": row["electrode_role"],
            "metadata_json": metadata,
            "parent_batch_name": _text(metadata.get("parent_batch_name")),
            "parent_batch_id": None,
        }

    for batch in batches_by_id.values():
        parent_name_key = _normalized_key(batch.get("parent_batch_name"))
        if parent_name_key:
            batch["parent_batch_id"] = batch_id_by_name.get(parent_name_key)

    return {
        "batches_by_id": batches_by_id,
        "batch_id_by_name": batch_id_by_name,
    }


def _resolve_root_batch(
    batch_id: int,
    batches_by_id: Dict[int, Dict[str, Any]],
    root_cache: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    if batch_id in root_cache:
        return root_cache[batch_id]

    current = batches_by_id.get(batch_id)
    visited: set[int] = set()
    while current and current.get("parent_batch_id") and current["id"] not in visited:
        visited.add(current["id"])
        parent = batches_by_id.get(current["parent_batch_id"])
        if not parent:
            break
        current = parent

    resolved = current or batches_by_id.get(batch_id) or {}
    root_cache[batch_id] = resolved
    return resolved


def _build_context_for_batch(
    *,
    batch: Dict[str, Any],
    root_batch: Dict[str, Any],
    mapping_basis: str,
    relationship_type: Optional[str],
    linked_cell_build_ids: Optional[list[int]] = None,
    linked_cell_build_names: Optional[list[str]] = None,
    candidate_batch_names: Optional[list[str]] = None,
) -> Dict[str, Any]:
    parent_batch_name = _text(batch.get("parent_batch_name"))
    return normalize_ontology_context(
        {
            "source": "cellscope2_ontology",
            "mapping_basis": mapping_basis,
            "relationship_type": relationship_type,
            "batch_id": batch.get("id"),
            "batch_name": batch.get("batch_name"),
            "display_batch_name": batch.get("display_batch_name"),
            "parent_batch_id": batch.get("parent_batch_id"),
            "parent_batch_name": parent_batch_name,
            "display_parent_batch_name": parent_batch_name,
            "root_batch_id": root_batch.get("id"),
            "root_batch_name": root_batch.get("batch_name"),
            "display_root_batch_name": root_batch.get("display_batch_name"),
            "electrode_role": batch.get("electrode_role"),
            "linked_cell_build_ids": linked_cell_build_ids or [],
            "linked_cell_build_names": linked_cell_build_names or [],
            "linked_cell_build_count": len(linked_cell_build_ids or []),
            "candidate_batch_names": candidate_batch_names or [],
        }
    )


@lru_cache(maxsize=1)
def load_legacy_experiment_ontology_contexts() -> Dict[int, Dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return {}

    graph = _load_batch_graph()
    batches_by_id = graph["batches_by_id"]
    root_cache: Dict[int, Dict[str, Any]] = {}
    connection = sqlite3.connect(ONTOLOGY_DB_PATH)
    connection.row_factory = sqlite3.Row

    direct_links: Dict[int, list[Dict[str, Any]]] = defaultdict(list)
    build_links: Dict[int, list[Dict[str, Any]]] = defaultdict(list)

    try:
        direct_rows = connection.execute(
            """
            SELECT
                e.child_id AS legacy_experiment_id,
                e.relationship_type AS relationship_type,
                b.id AS batch_id
            FROM ontology_lineage_edges e
            JOIN ontology_electrode_batches b ON b.id = e.parent_id
            WHERE e.parent_type = 'ELECTRODE_BATCH'
              AND e.child_type = 'EXPERIMENT'
            ORDER BY e.child_id ASC, e.id ASC
            """
        ).fetchall()

        build_rows = connection.execute(
            """
            SELECT
                cb.legacy_experiment_id AS legacy_experiment_id,
                cb.id AS cell_build_id,
                cb.build_name AS build_name,
                b.id AS batch_id
            FROM ontology_cell_builds cb
            JOIN ontology_lineage_edges e
              ON e.parent_type = 'ELECTRODE_BATCH'
             AND e.child_type = 'CELL_BUILD'
             AND e.child_id = cb.id
            JOIN ontology_electrode_batches b ON b.id = e.parent_id
            WHERE cb.legacy_experiment_id IS NOT NULL
            ORDER BY cb.legacy_experiment_id ASC, cb.id ASC
            """
        ).fetchall()
    finally:
        connection.close()

    for row in direct_rows:
        batch = batches_by_id.get(int(row["batch_id"]))
        if not batch or batch.get("electrode_role") != "CATHODE":
            continue
        direct_links[int(row["legacy_experiment_id"])].append(
            {
                "batch_id": batch["id"],
                "relationship_type": row["relationship_type"],
            }
        )

    for row in build_rows:
        batch = batches_by_id.get(int(row["batch_id"]))
        if not batch or batch.get("electrode_role") != "CATHODE":
            continue
        build_links[int(row["legacy_experiment_id"])].append(
            {
                "cell_build_id": int(row["cell_build_id"]),
                "build_name": row["build_name"],
                "batch_id": batch["id"],
            }
        )

    contexts: Dict[int, Dict[str, Any]] = {}
    experiment_ids = sorted(set(direct_links) | set(build_links))
    for legacy_experiment_id in experiment_ids:
        direct_candidates = _dedupe_preserve(
            [item["batch_id"] for item in direct_links.get(legacy_experiment_id, [])]
        )
        build_candidates = _dedupe_preserve(
            [item["batch_id"] for item in build_links.get(legacy_experiment_id, [])]
        )

        mapping_basis = None
        relationship_type = None
        chosen_batch_id: Optional[int] = None

        if len(direct_candidates) == 1:
            chosen_batch_id = int(direct_candidates[0])
            mapping_basis = "direct_experiment_edge"
            relationship_type = direct_links[legacy_experiment_id][0]["relationship_type"]
        elif len(build_candidates) == 1:
            chosen_batch_id = int(build_candidates[0])
            mapping_basis = "cell_build_edge"
            relationship_type = "source_batch_for_cell_build"

        candidate_batch_names = [
            batches_by_id[batch_id]["display_batch_name"]
            for batch_id in direct_candidates + build_candidates
            if batch_id in batches_by_id
        ]

        if not chosen_batch_id or chosen_batch_id not in batches_by_id:
            if candidate_batch_names:
                contexts[legacy_experiment_id] = normalize_ontology_context(
                    {
                        "source": "cellscope2_ontology",
                        "mapping_basis": "ambiguous",
                        "candidate_batch_names": _dedupe_preserve(candidate_batch_names),
                    }
                )
            continue

        batch = batches_by_id[chosen_batch_id]
        root_batch = _resolve_root_batch(chosen_batch_id, batches_by_id, root_cache)
        linked_cell_build_ids = _dedupe_preserve(
            [item["cell_build_id"] for item in build_links.get(legacy_experiment_id, [])]
        )
        linked_cell_build_names = _dedupe_preserve(
            [_text(item["build_name"]) or str(item["build_name"]) for item in build_links.get(legacy_experiment_id, [])]
        )
        contexts[legacy_experiment_id] = _build_context_for_batch(
            batch=batch,
            root_batch=root_batch,
            mapping_basis=mapping_basis or "direct_experiment_edge",
            relationship_type=relationship_type,
            linked_cell_build_ids=linked_cell_build_ids,
            linked_cell_build_names=linked_cell_build_names,
            candidate_batch_names=_dedupe_preserve(candidate_batch_names),
        )

    return contexts


@lru_cache(maxsize=128)
def get_name_based_ontology_context(experiment_name: str) -> Dict[str, Any]:
    graph = _load_batch_graph()
    batches_by_id = graph["batches_by_id"]
    batch_id_by_name = graph["batch_id_by_name"]
    name_key = _normalized_key(experiment_name)
    if not name_key:
        return {}

    batch_id = batch_id_by_name.get(name_key)
    if not batch_id:
        return {}

    root_cache: Dict[int, Dict[str, Any]] = {}
    batch = batches_by_id.get(batch_id)
    if not batch:
        return {}
    root_batch = _resolve_root_batch(batch_id, batches_by_id, root_cache)
    return _build_context_for_batch(
        batch=batch,
        root_batch=root_batch,
        mapping_basis="exact_batch_name_lookup",
        relationship_type=None,
    )


def backfill_legacy_experiment_ontology_contexts(
    legacy_db_path: Path = LEGACY_DB_PATH,
    *,
    persist: bool = False,
) -> Dict[str, Any]:
    mappings = load_legacy_experiment_ontology_contexts()
    if not legacy_db_path.exists():
        return {
            "available": False,
            "updated_count": 0,
            "mapped_experiment_count": len(mappings),
            "updated_experiment_ids": [],
        }

    connection = sqlite3.connect(legacy_db_path)
    try:
        rows = connection.execute(
            "SELECT id, data_json FROM cell_experiments ORDER BY id ASC"
        ).fetchall()

        updated_experiment_ids: list[int] = []
        preview_rows: list[Dict[str, Any]] = []
        for legacy_experiment_id, raw_data_json in rows:
            ontology_context = mappings.get(int(legacy_experiment_id))
            if not ontology_context:
                continue

            experiment_data = _load_json(raw_data_json)
            previous_ontology = normalize_ontology_context(experiment_data.get("ontology"))
            if previous_ontology == ontology_context:
                continue

            updated_data = dict(experiment_data)
            updated_data["ontology"] = ontology_context
            preview_rows.append(
                {
                    "legacy_experiment_id": int(legacy_experiment_id),
                    "batch_name": ontology_context.get("display_batch_name") or ontology_context.get("batch_name"),
                    "root_batch_name": ontology_context.get("display_root_batch_name") or ontology_context.get("root_batch_name"),
                }
            )
            updated_experiment_ids.append(int(legacy_experiment_id))

            if persist:
                connection.execute(
                    "UPDATE cell_experiments SET data_json = ? WHERE id = ?",
                    (json.dumps(updated_data), int(legacy_experiment_id)),
                )

        if persist and updated_experiment_ids:
            connection.commit()

        return {
            "available": True,
            "mapped_experiment_count": len(mappings),
            "updated_count": len(updated_experiment_ids),
            "updated_experiment_ids": updated_experiment_ids,
            "preview_rows": preview_rows,
        }
    finally:
        connection.close()


def clear_ontology_workflow_caches() -> None:
    _load_batch_graph.cache_clear()
    load_legacy_experiment_ontology_contexts.cache_clear()
    get_name_based_ontology_context.cache_clear()
