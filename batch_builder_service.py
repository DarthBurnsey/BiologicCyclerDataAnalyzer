"""Transactional helpers for authoring ontology-backed batches from the legacy app."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


BASE_DIR = Path(__file__).resolve().parent
ONTOLOGY_DB_PATH = BASE_DIR / "Cellscope 2.0" / "backend" / "cellscope2.db"
LEGACY_DB_PATH = BASE_DIR / "cellscope.db"

MATERIAL_CATEGORY_OPTIONS = [
    "cathode_active",
    "anode_active",
    "electrolyte_salt",
    "electrolyte_solvent",
    "electrolyte_additive",
    "separator",
    "binder",
    "conductive_additive",
    "current_collector",
    "other",
]
ELECTRODE_ROLE_OPTIONS = ["cathode", "anode"]
PROCESS_TYPE_OPTIONS = [
    "slurry",
    "coating",
    "drying",
    "calendaring",
    "cutting",
    "assembly",
    "electrolyte_fill",
    "formation",
    "other",
]
PROTOCOL_TYPE_OPTIONS = [
    "formation",
    "cycling",
    "rpt",
    "pulse",
    "eis",
    "calendar_aging",
    "other",
]
EQUIPMENT_TYPE_OPTIONS = [
    "cycler",
    "chamber",
    "potentiostat",
    "impedance_analyzer",
    "dispenser",
    "coater",
    "calendar",
    "fixture",
    "other",
]
CELL_FORMAT_OPTIONS = ["Coin", "Pouch", "Cylindrical", "Prismatic"]
BRANCH_TYPE_OPTIONS = [
    "electrolyte",
    "calendaring",
    "post_processing",
    "protocol",
    "material_variant",
    "other",
]


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalized_key(value: Any) -> Optional[str]:
    text = _text(value)
    return text.casefold() if text else None


def _enum_db_value(value: Any) -> Optional[str]:
    text = _text(value)
    return text.upper() if text else None


def _load_json(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default
    return payload if isinstance(payload, type(default)) else default


def _dump_json(value: Any) -> Optional[str]:
    if value in (None, "", [], {}):
        return None
    return json.dumps(value)


def _merge_json(existing: Optional[Dict[str, Any]], incoming: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not existing and not incoming:
        return None
    merged = dict(existing or {})
    merged.update(incoming or {})
    return merged


def _dedupe_preserve(values: Iterable[Any]) -> list[Any]:
    output: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if value in (None, ""):
            continue
        key = json.dumps(value, sort_keys=True) if isinstance(value, dict) else str(value)
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def _as_datetime_string(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).isoformat(timespec="seconds")
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat(timespec="seconds")
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.isoformat(timespec="seconds")
        except Exception:
            continue
    return text


def _as_date_string(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        pass
    if len(text) >= 10:
        return text[:10]
    return text


def _coerce_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _fetchone(connection: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> Optional[sqlite3.Row]:
    return connection.execute(query, params).fetchone()


def _normalize_material_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["metadata_json"] = _load_json(payload.get("metadata_json"), {})
    payload["created_at"] = _text(payload.get("created_at"))
    payload["updated_at"] = _text(payload.get("updated_at"))
    return payload


def _normalize_process_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["settings_json"] = _load_json(payload.get("settings_json"), {})
    payload["created_at"] = _text(payload.get("created_at"))
    payload["updated_at"] = _text(payload.get("updated_at"))
    return payload


def _normalize_batch_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["formulation_json"] = _load_json(payload.get("formulation_json"), [])
    payload["metadata_json"] = _load_json(payload.get("metadata_json"), {})
    payload["created_at"] = _text(payload.get("created_at"))
    payload["updated_at"] = _text(payload.get("updated_at"))
    return payload


def list_legacy_projects() -> list[dict[str, Any]]:
    if not LEGACY_DB_PATH.exists():
        return []
    with _get_connection(LEGACY_DB_PATH) as connection:
        rows = connection.execute(
            """
            SELECT id, name, description, project_type, created_date, last_modified
            FROM projects
            ORDER BY name COLLATE NOCASE ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def list_materials() -> list[dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return []
    with _get_connection(ONTOLOGY_DB_PATH) as connection:
        rows = connection.execute(
            """
            SELECT id, name, category, manufacturer, description, metadata_json, created_at, updated_at
            FROM ontology_materials
            ORDER BY category ASC, name COLLATE NOCASE ASC
            """
        ).fetchall()
    return [_normalize_material_row(row) for row in rows]


def list_protocol_versions() -> list[dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return []
    with _get_connection(ONTOLOGY_DB_PATH) as connection:
        rows = connection.execute(
            """
            SELECT id, name, version, protocol_type, description, metadata_json, created_at, updated_at
            FROM ontology_protocol_versions
            ORDER BY name COLLATE NOCASE ASC, version COLLATE NOCASE ASC
            """
        ).fetchall()
    payload: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metadata_json"] = _load_json(item.get("metadata_json"), {})
        payload.append(item)
    return payload


def list_operators() -> list[dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return []
    with _get_connection(ONTOLOGY_DB_PATH) as connection:
        rows = connection.execute(
            """
            SELECT id, name, team, email, active, metadata_json, created_at, updated_at
            FROM ontology_operators
            ORDER BY name COLLATE NOCASE ASC
            """
        ).fetchall()
    payload: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metadata_json"] = _load_json(item.get("metadata_json"), {})
        payload.append(item)
    return payload


def list_equipment_assets() -> list[dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return []
    with _get_connection(ONTOLOGY_DB_PATH) as connection:
        rows = connection.execute(
            """
            SELECT id, name, asset_type, vendor, model, serial_number, location, metadata_json, created_at, updated_at
            FROM ontology_equipment_assets
            ORDER BY name COLLATE NOCASE ASC
            """
        ).fetchall()
    payload: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metadata_json"] = _load_json(item.get("metadata_json"), {})
        payload.append(item)
    return payload


def list_batches(*, roots_only: bool = False, electrode_role: Optional[str] = None) -> list[dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return []
    where_clauses: list[str] = []
    params: list[Any] = []
    if electrode_role:
        where_clauses.append("b.electrode_role = ?")
        params.append(_enum_db_value(electrode_role))
    if roots_only:
        where_clauses.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM ontology_lineage_edges incoming
                WHERE incoming.parent_type = 'ELECTRODE_BATCH'
                  AND incoming.child_type = 'ELECTRODE_BATCH'
                  AND incoming.relationship_type = 'branches_to'
                  AND incoming.child_id = b.id
            )
            """
        )
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    with _get_connection(ONTOLOGY_DB_PATH) as connection:
        rows = connection.execute(
            f"""
            SELECT
                b.*,
                parent.batch_name AS parent_batch_name
            FROM ontology_electrode_batches b
            LEFT JOIN ontology_lineage_edges branch
              ON branch.parent_type = 'ELECTRODE_BATCH'
             AND branch.child_type = 'ELECTRODE_BATCH'
             AND branch.relationship_type = 'branches_to'
             AND branch.child_id = b.id
            LEFT JOIN ontology_electrode_batches parent ON parent.id = branch.parent_id
            {where_sql}
            ORDER BY COALESCE(b.created_at, '') DESC, b.batch_name COLLATE NOCASE ASC
            """,
            tuple(params),
        ).fetchall()
    payload: list[dict[str, Any]] = []
    for row in rows:
        item = _normalize_batch_row(row)
        metadata = item.get("metadata_json") or {}
        item["parent_batch_name"] = _text(item.get("parent_batch_name")) or _text(metadata.get("parent_batch_name"))
        item["default_project_id"] = metadata.get("default_legacy_project_id")
        item["default_project_name"] = metadata.get("default_legacy_project_name")
        item["preferred_experiment_name"] = metadata.get("preferred_experiment_name")
        item["study_focus"] = metadata.get("study_focus")
        payload.append(item)
    return payload


def create_material_record(
    *,
    name: str,
    category: str,
    manufacturer: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> dict[str, Any]:
    if category not in MATERIAL_CATEGORY_OPTIONS:
        raise ValueError(f"Unsupported material category: {category}")
    material_name = _text(name)
    if not material_name:
        raise ValueError("Material name is required.")

    with _get_connection(ONTOLOGY_DB_PATH) as connection:
        material = _ensure_material(
            connection,
            name=material_name,
            category=_enum_db_value(category) or "OTHER",
            manufacturer=manufacturer,
            description=description,
            metadata=metadata,
        )
        connection.commit()
        return material


def update_material_record(
    *,
    name: str,
    manufacturer: Optional[str] = None,
    description: Optional[str] = None,
) -> dict[str, Any]:
    material_name = _text(name)
    if not material_name:
        raise ValueError("Material name is required.")

    with _get_connection(ONTOLOGY_DB_PATH) as connection:
        existing = _fetchone(
            connection,
            "SELECT * FROM ontology_materials WHERE lower(name) = lower(?)",
            (material_name,),
        )
        if existing is None:
            raise ValueError(f"Material '{material_name}' was not found.")

        connection.execute(
            """
            UPDATE ontology_materials
            SET manufacturer = ?,
                description = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                _text(manufacturer),
                _text(description),
                existing["id"],
            ),
        )
        connection.commit()
        row = _fetchone(connection, "SELECT * FROM ontology_materials WHERE id = ?", (existing["id"],))
        return _normalize_material_row(row)


def _ensure_material(
    connection: sqlite3.Connection,
    *,
    name: str,
    category: str,
    manufacturer: Optional[str],
    description: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> dict[str, Any]:
    existing = _fetchone(
        connection,
        "SELECT * FROM ontology_materials WHERE lower(name) = lower(?)",
        (name,),
    )
    if existing is None:
        cursor = connection.execute(
            """
            INSERT INTO ontology_materials (
                name, category, manufacturer, description, metadata_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                _enum_db_value(category) or "OTHER",
                _text(manufacturer),
                _text(description),
                _dump_json(metadata),
            ),
        )
        row = _fetchone(connection, "SELECT * FROM ontology_materials WHERE id = ?", (cursor.lastrowid,))
        return _normalize_material_row(row)

    existing_payload = _normalize_material_row(existing)
    merged_metadata = _merge_json(existing_payload.get("metadata_json"), metadata)
    stored_manufacturer = existing_payload.get("manufacturer")
    if _text(manufacturer) and stored_manufacturer and _normalized_key(manufacturer) != _normalized_key(stored_manufacturer):
        merged_metadata = _merge_json(
            merged_metadata,
            {
                "manufacturer_hints": _dedupe_preserve(
                    [stored_manufacturer, manufacturer] + list((merged_metadata or {}).get("manufacturer_hints", []))
                )
            },
        )
    connection.execute(
        """
        UPDATE ontology_materials
        SET category = ?,
            manufacturer = COALESCE(?, manufacturer),
            description = COALESCE(?, description),
            metadata_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            _enum_db_value(category) or "OTHER",
            None if stored_manufacturer else _text(manufacturer),
            _text(description),
            _dump_json(merged_metadata),
            existing_payload["id"],
        ),
    )
    row = _fetchone(connection, "SELECT * FROM ontology_materials WHERE id = ?", (existing_payload["id"],))
    return _normalize_material_row(row)


def _ensure_protocol_version(
    connection: sqlite3.Connection,
    *,
    name: Optional[str],
    version: Optional[str],
    protocol_type: str,
    description: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> Optional[int]:
    protocol_name = _text(name)
    protocol_version = _text(version)
    if not protocol_name or not protocol_version:
        return None
    row = connection.execute(
        """
        SELECT * FROM ontology_protocol_versions
        WHERE lower(name) = lower(?) AND lower(version) = lower(?)
        """,
        (protocol_name, protocol_version),
    ).fetchone()
    if row is None:
        cursor = connection.execute(
            """
            INSERT INTO ontology_protocol_versions (
                name, version, protocol_type, description, metadata_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                protocol_name,
                protocol_version,
                _enum_db_value(protocol_type) or "OTHER",
                _text(description),
                _dump_json(metadata),
            ),
        )
        return int(cursor.lastrowid)

    existing = dict(row)
    merged_metadata = _merge_json(_load_json(existing.get("metadata_json"), {}), metadata)
    connection.execute(
        """
        UPDATE ontology_protocol_versions
        SET protocol_type = ?,
            description = COALESCE(?, description),
            metadata_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            _enum_db_value(protocol_type) or "OTHER",
            _text(description),
            _dump_json(merged_metadata),
            existing["id"],
        ),
    )
    return int(existing["id"])


def _ensure_operator(
    connection: sqlite3.Connection,
    *,
    name: Optional[str],
    team: Optional[str],
    email: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> Optional[int]:
    operator_name = _text(name)
    if not operator_name:
        return None
    row = _fetchone(
        connection,
        "SELECT * FROM ontology_operators WHERE lower(name) = lower(?)",
        (operator_name,),
    )
    if row is None:
        cursor = connection.execute(
            """
            INSERT INTO ontology_operators (name, team, email, active, metadata_json)
            VALUES (?, ?, ?, 1, ?)
            """,
            (operator_name, _text(team), _text(email), _dump_json(metadata)),
        )
        return int(cursor.lastrowid)

    existing = dict(row)
    merged_metadata = _merge_json(_load_json(existing.get("metadata_json"), {}), metadata)
    connection.execute(
        """
        UPDATE ontology_operators
        SET team = COALESCE(?, team),
            email = COALESCE(?, email),
            metadata_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (_text(team), _text(email), _dump_json(merged_metadata), existing["id"]),
    )
    return int(existing["id"])


def _ensure_equipment_asset(
    connection: sqlite3.Connection,
    *,
    name: Optional[str],
    asset_type: str,
    vendor: Optional[str],
    model: Optional[str],
    serial_number: Optional[str],
    location: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> Optional[int]:
    asset_name = _text(name)
    if not asset_name:
        return None
    row = _fetchone(
        connection,
        "SELECT * FROM ontology_equipment_assets WHERE lower(name) = lower(?)",
        (asset_name,),
    )
    if row is None:
        cursor = connection.execute(
            """
            INSERT INTO ontology_equipment_assets (
                name, asset_type, vendor, model, serial_number, location, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_name,
                _enum_db_value(asset_type) or "OTHER",
                _text(vendor),
                _text(model),
                _text(serial_number),
                _text(location),
                _dump_json(metadata),
            ),
        )
        return int(cursor.lastrowid)

    existing = dict(row)
    merged_metadata = _merge_json(_load_json(existing.get("metadata_json"), {}), metadata)
    connection.execute(
        """
        UPDATE ontology_equipment_assets
        SET asset_type = ?,
            vendor = COALESCE(?, vendor),
            model = COALESCE(?, model),
            serial_number = COALESCE(?, serial_number),
            location = COALESCE(?, location),
            metadata_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            _enum_db_value(asset_type) or "OTHER",
            _text(vendor),
            _text(model),
            _text(serial_number),
            _text(location),
            _dump_json(merged_metadata),
            existing["id"],
        ),
    )
    return int(existing["id"])


def _upsert_process_run(
    connection: sqlite3.Connection,
    *,
    name: Optional[str],
    process_type: str,
    protocol_version_id: Optional[int],
    operator_id: Optional[int],
    equipment_asset_id: Optional[int],
    started_at: Optional[str],
    completed_at: Optional[str],
    settings_json: Optional[Dict[str, Any]],
    notes: Optional[str],
) -> Optional[int]:
    process_name = _text(name)
    if not process_name:
        return None
    row = _fetchone(
        connection,
        "SELECT * FROM ontology_process_runs WHERE lower(name) = lower(?)",
        (process_name,),
    )
    if row is None:
        cursor = connection.execute(
            """
            INSERT INTO ontology_process_runs (
                name,
                process_type,
                protocol_version_id,
                operator_id,
                equipment_asset_id,
                started_at,
                completed_at,
                settings_json,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                process_name,
                _enum_db_value(process_type) or "OTHER",
                protocol_version_id,
                operator_id,
                equipment_asset_id,
                started_at,
                completed_at,
                _dump_json(settings_json),
                _text(notes),
            ),
        )
        return int(cursor.lastrowid)

    existing = _normalize_process_row(row)
    merged_settings = _merge_json(existing.get("settings_json"), settings_json)
    connection.execute(
        """
        UPDATE ontology_process_runs
        SET process_type = ?,
            protocol_version_id = COALESCE(?, protocol_version_id),
            operator_id = COALESCE(?, operator_id),
            equipment_asset_id = COALESCE(?, equipment_asset_id),
            started_at = COALESCE(?, started_at),
            completed_at = COALESCE(?, completed_at),
            settings_json = ?,
            notes = COALESCE(?, notes),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            _enum_db_value(process_type) or "OTHER",
            protocol_version_id,
            operator_id,
            equipment_asset_id,
            started_at,
            completed_at,
            _dump_json(merged_settings),
            _text(notes),
            existing["id"],
        ),
    )
    return int(existing["id"])


def _ensure_lineage_edge(
    connection: sqlite3.Connection,
    *,
    parent_type: str,
    parent_id: int,
    child_type: str,
    child_id: int,
    relationship_type: str,
    source: Optional[str],
    confidence: Optional[float],
    notes: Optional[str],
) -> None:
    existing = connection.execute(
        """
        SELECT id
        FROM ontology_lineage_edges
        WHERE parent_type = ?
          AND parent_id = ?
          AND child_type = ?
          AND child_id = ?
          AND relationship_type = ?
        """,
        (parent_type, parent_id, child_type, child_id, relationship_type),
    ).fetchone()
    if existing is not None:
        connection.execute(
            """
            UPDATE ontology_lineage_edges
            SET source = COALESCE(?, source),
                confidence = COALESCE(?, confidence),
                notes = COALESCE(?, notes)
            WHERE id = ?
            """,
            (_text(source), confidence, _text(notes), existing["id"]),
        )
        return

    connection.execute(
        """
        INSERT INTO ontology_lineage_edges (
            parent_type, parent_id, child_type, child_id, relationship_type, source, confidence, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            parent_type,
            parent_id,
            child_type,
            child_id,
            relationship_type,
            _text(source),
            confidence,
            _text(notes),
        ),
    )


def _default_formulation_for_role(electrode_role: str) -> list[dict[str, Any]]:
    if electrode_role == "anode":
        return [
            {
                "Component": "Graphite",
                "Category": "anode_active",
                "Dry Mass Fraction (%)": 95.0,
                "Manufacturer": "",
                "Source Name": "Graphite",
                "Post Processing": "",
                "Notes": "",
            },
            {
                "Component": "Super P",
                "Category": "conductive_additive",
                "Dry Mass Fraction (%)": 2.0,
                "Manufacturer": "",
                "Source Name": "Super P",
                "Post Processing": "",
                "Notes": "",
            },
            {
                "Component": "PVDF HSV1810",
                "Category": "binder",
                "Dry Mass Fraction (%)": 3.0,
                "Manufacturer": "Arkema",
                "Source Name": "PVDF HSV1810",
                "Post Processing": "",
                "Notes": "",
            },
        ]
    return [
        {
            "Component": "NMC811",
            "Category": "cathode_active",
            "Dry Mass Fraction (%)": 92.0,
            "Manufacturer": "",
            "Source Name": "NMC811",
            "Post Processing": "",
            "Notes": "",
        },
        {
            "Component": "Hx-e",
            "Category": "conductive_additive",
            "Dry Mass Fraction (%)": 4.0,
            "Manufacturer": "Hexegen",
            "Source Name": "Hx-e",
            "Post Processing": "",
            "Notes": "",
        },
        {
            "Component": "PVDF HSV1810",
            "Category": "binder",
            "Dry Mass Fraction (%)": 4.0,
            "Manufacturer": "Arkema",
            "Source Name": "PVDF HSV1810",
            "Post Processing": "",
            "Notes": "",
        },
    ]


def default_formulation_rows(electrode_role: str) -> list[dict[str, Any]]:
    return [dict(row) for row in _default_formulation_for_role(electrode_role)]


def _sanitize_formulation_components(
    formulation_components: Optional[list[dict[str, Any]]],
    *,
    electrode_role: str,
) -> list[dict[str, Any]]:
    rows = formulation_components or _default_formulation_for_role(electrode_role)
    sanitized: list[dict[str, Any]] = []
    for row in rows:
        component_name = _text(row.get("Component") or row.get("name"))
        if not component_name:
            continue
        category = _text(row.get("Category") or row.get("category") or "other")
        category = category.lower()
        if category not in MATERIAL_CATEGORY_OPTIONS:
            category = "other"
        dry_mass_fraction = _coerce_float(row.get("Dry Mass Fraction (%)") or row.get("dry_mass_fraction_pct"))
        manufacturer = _text(row.get("Manufacturer") or row.get("manufacturer"))
        source_name = _text(row.get("Source Name") or row.get("source_name")) or component_name
        post_processing = _text(row.get("Post Processing") or row.get("post_processing"))
        notes = _text(row.get("Notes") or row.get("notes"))
        metadata: dict[str, Any] = {}
        if source_name:
            metadata["source_name"] = source_name
        if manufacturer:
            metadata["manufacturer_hint"] = manufacturer
        if post_processing:
            metadata["post_processing"] = post_processing
        if notes:
            metadata["component_notes"] = notes
        sanitized.append(
            {
                "Component": component_name,
                "Category": category,
                "Dry Mass Fraction (%)": dry_mass_fraction,
                "metadata": metadata,
            }
        )
    return sanitized


def _default_substrate_for_role(electrode_role: str) -> str:
    return "Copper" if _normalized_key(electrode_role) == "anode" else "Aluminum"


def _resolve_root_batch(connection: sqlite3.Connection, batch_id: int) -> Optional[dict[str, Any]]:
    current = _fetchone(connection, "SELECT * FROM ontology_electrode_batches WHERE id = ?", (batch_id,))
    if current is None:
        return None
    visited: set[int] = set()
    while current is not None and current["id"] not in visited:
        visited.add(int(current["id"]))
        parent_edge = connection.execute(
            """
            SELECT parent_id
            FROM ontology_lineage_edges
            WHERE parent_type = 'ELECTRODE_BATCH'
              AND child_type = 'ELECTRODE_BATCH'
              AND relationship_type = 'branches_to'
              AND child_id = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (current["id"],),
        ).fetchone()
        if parent_edge is None:
            return _normalize_batch_row(current)
        current = _fetchone(connection, "SELECT * FROM ontology_electrode_batches WHERE id = ?", (parent_edge["parent_id"],))
    return _normalize_batch_row(current) if current is not None else None


def _load_batch_with_related(connection: sqlite3.Connection, batch_id: int) -> Optional[dict[str, Any]]:
    batch_row = _fetchone(connection, "SELECT * FROM ontology_electrode_batches WHERE id = ?", (batch_id,))
    if batch_row is None:
        return None
    batch = _normalize_batch_row(batch_row)
    parent_edge = connection.execute(
        """
        SELECT parent_id
        FROM ontology_lineage_edges
        WHERE parent_type = 'ELECTRODE_BATCH'
          AND child_type = 'ELECTRODE_BATCH'
          AND relationship_type = 'branches_to'
          AND child_id = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (batch_id,),
    ).fetchone()
    parent_batch = None
    if parent_edge is not None:
        parent_row = _fetchone(connection, "SELECT * FROM ontology_electrode_batches WHERE id = ?", (parent_edge["parent_id"],))
        if parent_row is not None:
            parent_batch = _normalize_batch_row(parent_row)

    root_batch = _resolve_root_batch(connection, batch_id) or batch
    material_edges = connection.execute(
        """
        SELECT parent_id
        FROM ontology_lineage_edges
        WHERE parent_type = 'MATERIAL'
          AND child_type = 'ELECTRODE_BATCH'
          AND relationship_type = 'formulates_into'
          AND child_id = ?
        ORDER BY id ASC
        """,
        (batch_id,),
    ).fetchall()
    material_ids = [int(row["parent_id"]) for row in material_edges]
    materials_by_id: dict[int, dict[str, Any]] = {}
    if material_ids:
        placeholders = ",".join("?" for _ in material_ids)
        material_rows = connection.execute(
            f"SELECT * FROM ontology_materials WHERE id IN ({placeholders})",
            tuple(material_ids),
        ).fetchall()
        materials_by_id = {int(row["id"]): _normalize_material_row(row) for row in material_rows}

    process_run = None
    if batch.get("process_run_id"):
        process_row = _fetchone(connection, "SELECT * FROM ontology_process_runs WHERE id = ?", (batch["process_run_id"],))
        if process_row is not None:
            process_run = _normalize_process_row(process_row)

    batch["parent_batch"] = parent_batch
    batch["root_batch"] = root_batch
    batch["materials"] = list(materials_by_id.values())
    batch["process_run"] = process_run
    return batch


def load_batch_detail(*, batch_id: Optional[int] = None, batch_name: Optional[str] = None) -> Optional[dict[str, Any]]:
    if not ONTOLOGY_DB_PATH.exists():
        return None
    with _get_connection(ONTOLOGY_DB_PATH) as connection:
        resolved_batch_id = batch_id
        if resolved_batch_id is None:
            normalized_name = _text(batch_name)
            if not normalized_name:
                return None
            row = _fetchone(
                connection,
                "SELECT id FROM ontology_electrode_batches WHERE lower(batch_name) = lower(?)",
                (normalized_name,),
            )
            if row is None:
                return None
            resolved_batch_id = int(row["id"])
        return _load_batch_with_related(connection, int(resolved_batch_id))


def create_batch_record(
    *,
    batch_name: str,
    electrode_role: str,
    created_at: Optional[Any] = None,
    formulation_components: Optional[list[dict[str, Any]]] = None,
    active_material_name: Optional[str] = None,
    notes: Optional[str] = None,
    preferred_experiment_name: Optional[str] = None,
    experiment_prefix: Optional[str] = None,
    study_focus: Optional[str] = None,
    ingestion_aliases: Optional[list[str]] = None,
    branch_type: Optional[str] = None,
    target_project_id: Optional[int] = None,
    target_project_name: Optional[str] = None,
    cell_format: Optional[str] = None,
    default_disc_diameter_mm: Optional[float] = None,
    default_loading_mg: Optional[float] = None,
    solids_content_pct: Optional[float] = None,
    pressed_thickness_um: Optional[float] = None,
    electrolyte_hint: Optional[str] = None,
    substrate_hint: Optional[str] = None,
    separator_hint: Optional[str] = None,
    cutoff_voltage_lower: Optional[float] = None,
    cutoff_voltage_upper: Optional[float] = None,
    formation_cycles: Optional[int] = None,
    expected_cell_count: Optional[int] = None,
    cell_build_naming: Optional[str] = None,
    connector_aliases: Optional[list[str]] = None,
    parent_batch_name: Optional[str] = None,
    protocol_name: Optional[str] = None,
    protocol_version: Optional[str] = None,
    protocol_type: str = "other",
    protocol_description: Optional[str] = None,
    operator_name: Optional[str] = None,
    operator_team: Optional[str] = None,
    operator_email: Optional[str] = None,
    equipment_name: Optional[str] = None,
    equipment_type: str = "other",
    equipment_vendor: Optional[str] = None,
    equipment_model: Optional[str] = None,
    equipment_serial_number: Optional[str] = None,
    equipment_location: Optional[str] = None,
    process_name: Optional[str] = None,
    process_type: str = "other",
    process_started_at: Optional[Any] = None,
    process_completed_at: Optional[Any] = None,
    process_settings: Optional[Dict[str, Any]] = None,
    process_notes: Optional[str] = None,
    inherit_parent_process: bool = True,
    batch_metadata: Optional[Dict[str, Any]] = None,
) -> dict[str, Any]:
    role = _text(electrode_role)
    if role not in ELECTRODE_ROLE_OPTIONS:
        raise ValueError(f"Unsupported electrode role: {electrode_role}")
    batch_name_text = _text(batch_name)
    if not batch_name_text:
        raise ValueError("Batch name is required.")

    with _get_connection(ONTOLOGY_DB_PATH) as connection:
        parent_batch = None
        inherited_formulation: list[dict[str, Any]] = []
        inherited_process_run_id: Optional[int] = None
        if _text(parent_batch_name):
            parent_row = _fetchone(
                connection,
                "SELECT * FROM ontology_electrode_batches WHERE lower(batch_name) = lower(?)",
                (_text(parent_batch_name),),
            )
            if parent_row is None:
                raise ValueError(f"Parent batch '{parent_batch_name}' was not found.")
            parent_batch = _normalize_batch_row(parent_row)
            inherited_formulation = list(parent_batch.get("formulation_json") or [])
            inherited_process_run_id = parent_batch.get("process_run_id")

        formulation = _sanitize_formulation_components(
            formulation_components if formulation_components else inherited_formulation,
            electrode_role=role,
        )
        if not formulation:
            raise ValueError("At least one formulation component is required.")

        material_records: dict[str, dict[str, Any]] = {}
        for component in formulation:
            metadata = component.get("metadata") if isinstance(component.get("metadata"), dict) else {}
            material = _ensure_material(
                connection,
                name=component["Component"],
                category=component["Category"],
                manufacturer=metadata.get("manufacturer_hint"),
                description=None,
                metadata={"source_name": metadata.get("source_name")} if metadata.get("source_name") else None,
            )
            material_records[component["Component"]] = material

        active_category = "anode_active" if role == "anode" else "cathode_active"
        active_component = None
        explicit_active_name = _text(active_material_name)
        for component in formulation:
            if explicit_active_name and _normalized_key(component["Component"]) == _normalized_key(explicit_active_name):
                active_component = component
                break
            if _normalized_key(component["Category"]) == active_category and active_component is None:
                active_component = component
        if active_component is None:
            raise ValueError("One active material component is required.")

        active_material_row = material_records.get(active_component["Component"])
        active_material_id = active_material_row["id"] if active_material_row else None
        active_material_source = None
        if isinstance(active_component.get("metadata"), dict):
            active_material_source = _text(active_component["metadata"].get("manufacturer_hint"))

        protocol_id = _ensure_protocol_version(
            connection,
            name=protocol_name,
            version=protocol_version,
            protocol_type=protocol_type,
            description=protocol_description,
            metadata={"source": "batch_builder"} if _text(protocol_name) and _text(protocol_version) else None,
        )
        operator_id = _ensure_operator(
            connection,
            name=operator_name,
            team=operator_team,
            email=operator_email,
            metadata={"source": "batch_builder"} if _text(operator_name) else None,
        )
        equipment_id = _ensure_equipment_asset(
            connection,
            name=equipment_name,
            asset_type=equipment_type,
            vendor=equipment_vendor,
            model=equipment_model,
            serial_number=equipment_serial_number,
            location=equipment_location,
            metadata={"source": "batch_builder"} if _text(equipment_name) else None,
        )

        process_run_id = None
        if _text(process_name):
            process_run_id = _upsert_process_run(
                connection,
                name=process_name,
                process_type=process_type,
                protocol_version_id=protocol_id,
                operator_id=operator_id,
                equipment_asset_id=equipment_id,
                started_at=_as_datetime_string(process_started_at),
                completed_at=_as_datetime_string(process_completed_at),
                settings_json=process_settings,
                notes=process_notes,
            )
        elif parent_batch is not None and inherit_parent_process:
            process_run_id = inherited_process_run_id

        ingestion_alias_values = _dedupe_preserve(
            [batch_name_text] + list(ingestion_aliases or []) + list(connector_aliases or [])
        )
        metadata = _merge_json(
            batch_metadata,
            {
                "source": "batch_builder",
                "parent_batch_name": _text(parent_batch_name),
                "study_focus": _text(study_focus),
                "branch_type": _text(branch_type),
                "default_legacy_project_id": target_project_id,
                "default_legacy_project_name": _text(target_project_name),
                "preferred_experiment_name": _text(preferred_experiment_name) or batch_name_text,
                "experiment_prefix": _text(experiment_prefix) or batch_name_text,
                "ingestion_aliases": ingestion_alias_values,
                "connector_hints": {
                    "batch_aliases": ingestion_alias_values,
                    "preferred_experiment_name": _text(preferred_experiment_name) or batch_name_text,
                    "cell_build_naming": _text(cell_build_naming) or "{experiment_name} {roman_index}",
                    "expected_cell_count": expected_cell_count,
                },
                "cell_format": _text(cell_format) or "Coin",
                "default_disc_diameter_mm": default_disc_diameter_mm,
                "default_loading_mg": default_loading_mg,
                "solids_content_pct": solids_content_pct,
                "pressed_thickness_um": pressed_thickness_um,
                "electrolyte_hint": _text(electrolyte_hint),
                "substrate_hint": _text(substrate_hint) or _default_substrate_for_role(role),
                "separator_hint": _text(separator_hint) or "25um PP",
                "cutoff_voltage_lower": cutoff_voltage_lower,
                "cutoff_voltage_upper": cutoff_voltage_upper,
                "formation_cycles": formation_cycles,
                "expected_cell_count": expected_cell_count,
                "active_material_source": active_material_source,
                "authoring_mode": "root" if parent_batch is None else "branch",
            },
        )

        created_at_value = _as_datetime_string(created_at)
        existing_batch = _fetchone(
            connection,
            "SELECT * FROM ontology_electrode_batches WHERE lower(batch_name) = lower(?)",
            (batch_name_text,),
        )
        if existing_batch is None:
            cursor = connection.execute(
                """
                INSERT INTO ontology_electrode_batches (
                    batch_name,
                    electrode_role,
                    active_material_id,
                    process_run_id,
                    formulation_json,
                    notes,
                    metadata_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                """,
                (
                    batch_name_text,
                    _enum_db_value(role) or "CATHODE",
                    active_material_id,
                    process_run_id,
                    _dump_json(formulation),
                    _text(notes),
                    _dump_json(metadata),
                    created_at_value,
                ),
            )
            batch_id = int(cursor.lastrowid)
        else:
            batch_id = int(existing_batch["id"])
            connection.execute(
                """
                UPDATE ontology_electrode_batches
                SET electrode_role = ?,
                    active_material_id = ?,
                    process_run_id = ?,
                    formulation_json = ?,
                    notes = COALESCE(?, notes),
                    metadata_json = ?,
                    created_at = COALESCE(?, created_at),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    _enum_db_value(role) or "CATHODE",
                    active_material_id,
                    process_run_id,
                    _dump_json(formulation),
                    _text(notes),
                    _dump_json(metadata),
                    created_at_value,
                    batch_id,
                ),
            )

        connection.execute(
            """
            DELETE FROM ontology_lineage_edges
            WHERE parent_type = 'MATERIAL'
              AND child_type = 'ELECTRODE_BATCH'
              AND relationship_type = 'formulates_into'
              AND child_id = ?
            """,
            (batch_id,),
        )
        connection.execute(
            """
            DELETE FROM ontology_lineage_edges
            WHERE parent_type = 'ELECTRODE_BATCH'
              AND child_type = 'ELECTRODE_BATCH'
              AND relationship_type = 'branches_to'
              AND child_id = ?
            """,
            (batch_id,),
        )

        if parent_batch is not None:
            _ensure_lineage_edge(
                connection,
                parent_type="ELECTRODE_BATCH",
                parent_id=int(parent_batch["id"]),
                child_type="ELECTRODE_BATCH",
                child_id=batch_id,
                relationship_type="branches_to",
                source="batch_builder",
                confidence=1.0,
                notes="Created from Batch Builder",
            )

        for component in formulation:
            material = material_records[component["Component"]]
            _ensure_lineage_edge(
                connection,
                parent_type="MATERIAL",
                parent_id=int(material["id"]),
                child_type="ELECTRODE_BATCH",
                child_id=batch_id,
                relationship_type="formulates_into",
                source="batch_builder",
                confidence=1.0,
                notes=None,
            )

        connection.commit()
        detail = _load_batch_with_related(connection, batch_id)
        if detail is None:
            raise RuntimeError("Failed to load the saved batch.")
        return detail


def build_batch_cell_inputs_template(
    *,
    batch_id: Optional[int] = None,
    batch_name: Optional[str] = None,
    target_project_id: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    batch = load_batch_detail(batch_id=batch_id, batch_name=batch_name)
    if batch is None:
        return None

    root_batch = batch.get("root_batch") or batch
    metadata = batch.get("metadata_json") or {}
    root_metadata = root_batch.get("metadata_json") or {}
    project_lookup = {project["id"]: project for project in list_legacy_projects()}
    resolved_project_id = (
        target_project_id
        or metadata.get("default_legacy_project_id")
        or root_metadata.get("default_legacy_project_id")
    )
    resolved_project = project_lookup.get(resolved_project_id) if resolved_project_id else None
    project_name = None
    if resolved_project is not None:
        project_name = resolved_project.get("name")
    else:
        project_name = _text(metadata.get("default_legacy_project_name")) or _text(root_metadata.get("default_legacy_project_name"))

    formulation = list(batch.get("formulation_json") or [])
    active_component = None
    active_category = "anode_active" if _normalized_key(batch.get("electrode_role")) == "anode" else "cathode_active"
    for component in formulation:
        if _normalized_key(component.get("Category")) == active_category:
            active_component = component
            break
    active_fraction = _coerce_float(active_component.get("Dry Mass Fraction (%)")) if active_component else None

    experiment_name = (
        _text(metadata.get("preferred_experiment_name"))
        or _text(root_metadata.get("preferred_experiment_name"))
        or batch.get("batch_name")
    )
    connector_hints = _merge_json(root_metadata.get("connector_hints"), metadata.get("connector_hints")) or {}
    ingestion_aliases = _dedupe_preserve(
        list(root_metadata.get("ingestion_aliases", []))
        + list(metadata.get("ingestion_aliases", []))
        + [batch.get("batch_name"), root_batch.get("batch_name")]
    )
    cell_inputs_defaults = {
        "experiment_name": experiment_name,
        "experiment_date": _as_date_string(batch.get("created_at")) or date.today().isoformat(),
        "disc_diameter_mm": metadata.get("default_disc_diameter_mm") or root_metadata.get("default_disc_diameter_mm") or 15.0,
        "loading_mg": metadata.get("default_loading_mg"),
        "active_material_pct": active_fraction,
        "formation_cycles": metadata.get("formation_cycles") or root_metadata.get("formation_cycles") or 4,
        "electrolyte": _text(metadata.get("electrolyte_hint")) or _text(root_metadata.get("electrolyte_hint")) or "1M LiPF6 1:1:1",
        "substrate": _text(metadata.get("substrate_hint")) or _text(root_metadata.get("substrate_hint")) or _default_substrate_for_role(batch.get("electrode_role") or "cathode"),
        "separator": _text(metadata.get("separator_hint")) or _text(root_metadata.get("separator_hint")) or "25um PP",
        "cutoff_voltage_lower": metadata.get("cutoff_voltage_lower") if metadata.get("cutoff_voltage_lower") is not None else root_metadata.get("cutoff_voltage_lower"),
        "cutoff_voltage_upper": metadata.get("cutoff_voltage_upper") if metadata.get("cutoff_voltage_upper") is not None else root_metadata.get("cutoff_voltage_upper"),
        "formulation": formulation,
        "solids_content": metadata.get("solids_content_pct") if metadata.get("solids_content_pct") is not None else root_metadata.get("solids_content_pct"),
        "pressed_thickness": metadata.get("pressed_thickness_um") if metadata.get("pressed_thickness_um") is not None else root_metadata.get("pressed_thickness_um"),
        "cell_format": _text(metadata.get("cell_format")) or _text(root_metadata.get("cell_format")) or "Coin",
    }
    notes_bits = [
        f"Canonical batch: {batch.get('batch_name')}",
        f"Parent batch: {root_batch.get('batch_name')}" if root_batch.get("batch_name") and root_batch.get("batch_name") != batch.get("batch_name") else None,
        f"Study focus: {metadata.get('study_focus') or root_metadata.get('study_focus')}" if metadata.get("study_focus") or root_metadata.get("study_focus") else None,
        _text(batch.get("notes")),
    ]
    experiment_notes = "\n".join(bit for bit in notes_bits if bit)

    ontology_context = {
        "source": "cellscope2_ontology",
        "mapping_basis": "batch_builder_selection",
        "relationship_type": "batch_builder_selected",
        "batch_id": batch.get("id"),
        "batch_name": batch.get("batch_name"),
        "display_batch_name": batch.get("batch_name"),
        "parent_batch_name": root_batch.get("batch_name") if root_batch.get("batch_name") != batch.get("batch_name") else None,
        "display_parent_batch_name": root_batch.get("batch_name") if root_batch.get("batch_name") != batch.get("batch_name") else None,
        "root_batch_id": root_batch.get("id"),
        "root_batch_name": root_batch.get("batch_name"),
        "display_root_batch_name": root_batch.get("batch_name"),
        "electrode_role": _normalized_key(batch.get("electrode_role")) or batch.get("electrode_role"),
        "candidate_batch_names": ingestion_aliases,
        "linked_cell_build_ids": [],
        "linked_cell_build_names": [],
        "linked_cell_build_count": 0,
    }

    return {
        "batch_id": batch.get("id"),
        "batch_name": batch.get("batch_name"),
        "root_batch_id": root_batch.get("id"),
        "root_batch_name": root_batch.get("batch_name"),
        "electrode_role": _normalized_key(batch.get("electrode_role")) or batch.get("electrode_role"),
        "project_id": resolved_project_id,
        "project_name": project_name,
        "preferred_experiment_name": experiment_name,
        "experiment_notes": experiment_notes,
        "formulation": formulation,
        "cell_inputs_defaults": cell_inputs_defaults,
        "ontology_context": ontology_context,
        "ingestion_hints": _merge_json(
            connector_hints,
            {
                "batch_aliases": ingestion_aliases,
                "root_batch_name": root_batch.get("batch_name"),
                "batch_name": batch.get("batch_name"),
            },
        )
        or {},
    }


def build_experiment_additional_data_from_template(template: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not template:
        return {}
    defaults = template.get("cell_inputs_defaults") or {}
    ontology_context = template.get("ontology_context") or {}
    return {
        "ontology": ontology_context,
        "batch_builder": {
            "batch_id": template.get("batch_id"),
            "batch_name": template.get("batch_name"),
            "root_batch_id": template.get("root_batch_id"),
            "root_batch_name": template.get("root_batch_name"),
            "project_id": template.get("project_id"),
            "project_name": template.get("project_name"),
            "ingestion_hints": template.get("ingestion_hints") or {},
        },
        "ingestion_hints": template.get("ingestion_hints") or {},
        "default_cell_values": {
            "loading": defaults.get("loading_mg"),
            "active_material": defaults.get("active_material_pct"),
            "formation_cycles": defaults.get("formation_cycles"),
            "electrolyte": defaults.get("electrolyte"),
            "substrate": defaults.get("substrate"),
            "separator": defaults.get("separator"),
            "cutoff_voltage_lower": defaults.get("cutoff_voltage_lower"),
            "cutoff_voltage_upper": defaults.get("cutoff_voltage_upper"),
            "formulation": defaults.get("formulation") or [],
        },
    }
