"""API routes for the canonical battery ontology."""

from typing import Any, Optional, Type

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ontology import (
    CellBuild,
    ElectrodeBatch,
    EquipmentAsset,
    Fixture,
    LineageEdge,
    LineageEntityType,
    Material,
    MaterialLot,
    Operator,
    ProcessRun,
    ProtocolVersion,
)
from app.services.lib_anode_workbook import import_lib_anode_workbook
from app.services.nmc_cathode_workbook import import_nmc_cathode_workbook
from app.services.ontology_lineage import (
    get_cell_build_lineage,
    get_electrode_batch_by_name,
    get_electrode_batch_descendants,
    get_electrode_batch_lineage,
    get_legacy_experiment_sources,
)
from app.schemas.ontology import (
    CellBuildLineageRead,
    CellBuildCreate,
    CellBuildRead,
    CellBuildUpdate,
    ElectrodeBatchDescendantsRead,
    ElectrodeBatchLineageRead,
    ElectrodeBatchCreate,
    ElectrodeBatchRead,
    ElectrodeBatchUpdate,
    EquipmentAssetCreate,
    EquipmentAssetRead,
    EquipmentAssetUpdate,
    FixtureCreate,
    FixtureRead,
    FixtureUpdate,
    LineageEdgeCreate,
    LineageEdgeRead,
    LineageEdgeUpdate,
    LegacyExperimentSourcesRead,
    OntologySearchResult,
    OntologySummary,
    MaterialCreate,
    MaterialLotCreate,
    MaterialLotRead,
    MaterialLotUpdate,
    MaterialRead,
    MaterialUpdate,
    OperatorCreate,
    OperatorRead,
    OperatorUpdate,
    ProcessRunCreate,
    ProcessRunRead,
    ProcessRunUpdate,
    ProtocolVersionCreate,
    ProtocolVersionRead,
    ProtocolVersionUpdate,
)

router = APIRouter(prefix="/api/ontology", tags=["ontology"])


class NMCCathodeWorkbookImportRequest(BaseModel):
    workbook_path: str
    legacy_db_path: Optional[str] = None
    comparison_workbook_path: Optional[str] = None
    export_dir: Optional[str] = None
    persist: bool = False


class LIBAnodeWorkbookImportRequest(BaseModel):
    workbook_path: str
    legacy_db_path: Optional[str] = None
    export_dir: Optional[str] = None
    persist: bool = False


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=409, detail=detail)


def _not_found(resource_label: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{resource_label} not found")


def _resource_label(resource_path: str) -> str:
    return resource_path.strip("/").replace("-", " ").rstrip("s")


def _register_crud_routes(
    *,
    router: APIRouter,
    resource_path: str,
    model: Type[Any],
    create_schema: Type[BaseModel],
    update_schema: Type[BaseModel],
    read_schema: Type[BaseModel],
    sort_field: str = "created_at",
) -> None:
    resource_label = _resource_label(resource_path)
    order_column = getattr(model, sort_field)

    async def list_entities(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(model).order_by(order_column.desc()))
        return [read_schema.model_validate(row) for row in result.scalars().all()]

    list_entities.__name__ = f"list_{resource_path.strip('/').replace('-', '_')}"
    router.add_api_route(
        resource_path,
        list_entities,
        methods=["GET"],
        response_model=list[read_schema],
    )

    async def create_entity(payload: create_schema, db: AsyncSession = Depends(get_db)):  # type: ignore[valid-type]
        entity = model(**payload.model_dump())
        db.add(entity)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise _conflict(f"Unable to create {resource_label}: integrity error") from exc
        await db.refresh(entity)
        return read_schema.model_validate(entity)

    create_entity.__name__ = f"create_{resource_path.strip('/').replace('-', '_')[:-1]}"
    router.add_api_route(
        resource_path,
        create_entity,
        methods=["POST"],
        response_model=read_schema,
        status_code=status.HTTP_201_CREATED,
    )

    async def get_entity(entity_id: int, db: AsyncSession = Depends(get_db)):
        entity = await db.get(model, entity_id)
        if not entity:
            raise _not_found(resource_label)
        return read_schema.model_validate(entity)

    get_entity.__name__ = f"get_{resource_path.strip('/').replace('-', '_')[:-1]}"
    router.add_api_route(
        f"{resource_path}/{{entity_id}}",
        get_entity,
        methods=["GET"],
        response_model=read_schema,
    )

    async def update_entity(
        entity_id: int,
        payload: update_schema,  # type: ignore[valid-type]
        db: AsyncSession = Depends(get_db),
    ):
        entity = await db.get(model, entity_id)
        if not entity:
            raise _not_found(resource_label)

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(entity, field, value)

        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise _conflict(f"Unable to update {resource_label}: integrity error") from exc
        await db.refresh(entity)
        return read_schema.model_validate(entity)

    update_entity.__name__ = f"update_{resource_path.strip('/').replace('-', '_')[:-1]}"
    router.add_api_route(
        f"{resource_path}/{{entity_id}}",
        update_entity,
        methods=["PATCH"],
        response_model=read_schema,
    )

    async def delete_entity(entity_id: int, db: AsyncSession = Depends(get_db)):
        entity = await db.get(model, entity_id)
        if not entity:
            raise _not_found(resource_label)
        await db.delete(entity)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    delete_entity.__name__ = f"delete_{resource_path.strip('/').replace('-', '_')[:-1]}"
    router.add_api_route(
        f"{resource_path}/{{entity_id}}",
        delete_entity,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
    )


_register_crud_routes(
    router=router,
    resource_path="/materials",
    model=Material,
    create_schema=MaterialCreate,
    update_schema=MaterialUpdate,
    read_schema=MaterialRead,
    sort_field="name",
)
_register_crud_routes(
    router=router,
    resource_path="/material-lots",
    model=MaterialLot,
    create_schema=MaterialLotCreate,
    update_schema=MaterialLotUpdate,
    read_schema=MaterialLotRead,
)
_register_crud_routes(
    router=router,
    resource_path="/protocol-versions",
    model=ProtocolVersion,
    create_schema=ProtocolVersionCreate,
    update_schema=ProtocolVersionUpdate,
    read_schema=ProtocolVersionRead,
    sort_field="name",
)
_register_crud_routes(
    router=router,
    resource_path="/operators",
    model=Operator,
    create_schema=OperatorCreate,
    update_schema=OperatorUpdate,
    read_schema=OperatorRead,
    sort_field="name",
)
_register_crud_routes(
    router=router,
    resource_path="/fixtures",
    model=Fixture,
    create_schema=FixtureCreate,
    update_schema=FixtureUpdate,
    read_schema=FixtureRead,
    sort_field="name",
)
_register_crud_routes(
    router=router,
    resource_path="/equipment-assets",
    model=EquipmentAsset,
    create_schema=EquipmentAssetCreate,
    update_schema=EquipmentAssetUpdate,
    read_schema=EquipmentAssetRead,
    sort_field="name",
)
_register_crud_routes(
    router=router,
    resource_path="/process-runs",
    model=ProcessRun,
    create_schema=ProcessRunCreate,
    update_schema=ProcessRunUpdate,
    read_schema=ProcessRunRead,
)
_register_crud_routes(
    router=router,
    resource_path="/electrode-batches",
    model=ElectrodeBatch,
    create_schema=ElectrodeBatchCreate,
    update_schema=ElectrodeBatchUpdate,
    read_schema=ElectrodeBatchRead,
    sort_field="batch_name",
)
_register_crud_routes(
    router=router,
    resource_path="/cell-builds",
    model=CellBuild,
    create_schema=CellBuildCreate,
    update_schema=CellBuildUpdate,
    read_schema=CellBuildRead,
    sort_field="build_name",
)


@router.get("/summary", response_model=OntologySummary)
async def get_ontology_summary(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func as sqlfunc

    counts = {}
    for key, model in [
        ("materials", Material),
        ("material_lots", MaterialLot),
        ("protocol_versions", ProtocolVersion),
        ("operators", Operator),
        ("fixtures", Fixture),
        ("equipment_assets", EquipmentAsset),
        ("process_runs", ProcessRun),
        ("electrode_batches", ElectrodeBatch),
        ("cell_builds", CellBuild),
        ("lineage_edges", LineageEdge),
    ]:
        result = await db.execute(select(sqlfunc.count()).select_from(model))
        counts[key] = result.scalar() or 0
    return OntologySummary(**counts)


@router.get("/search", response_model=list[OntologySearchResult])
async def search_ontology(
    q: str = Query(..., min_length=1, max_length=500),
    entity_types: Optional[str] = Query(
        default=None, description="Comma-separated entity types to search"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    results: list[OntologySearchResult] = []
    pattern = f"%{q}%"

    searchable = [
        ("material", Material, Material.name, lambda e: f"{e.category} · {e.manufacturer or ''}"),
        ("cell_build", CellBuild, CellBuild.build_name, lambda e: f"{e.chemistry or ''} · {e.status}"),
        ("electrode_batch", ElectrodeBatch, ElectrodeBatch.batch_name, lambda e: f"{e.electrode_role}"),
        ("equipment_asset", EquipmentAsset, EquipmentAsset.name, lambda e: f"{e.asset_type} · {e.vendor or ''}"),
        ("protocol_version", ProtocolVersion, ProtocolVersion.name, lambda e: f"{e.protocol_type} · v{e.version}"),
        ("operator", Operator, Operator.name, lambda e: f"{e.team or ''} · {e.email or ''}"),
        ("process_run", ProcessRun, ProcessRun.name, lambda e: f"{e.process_type}"),
        ("fixture", Fixture, Fixture.name, lambda e: f"{e.fixture_type or ''}"),
    ]

    # Filter entity types if specified
    if entity_types:
        allowed = set(entity_types.split(","))
        searchable = [s for s in searchable if s[0] in allowed]

    for entity_type, model, name_col, detail_fn in searchable:
        stmt = select(model).where(name_col.ilike(pattern)).limit(limit)
        result = await db.execute(stmt)
        for entity in result.scalars().all():
            results.append(
                OntologySearchResult(
                    entity_type=entity_type,
                    entity_id=entity.id,
                    name=getattr(entity, name_col.key),
                    detail=detail_fn(entity),
                )
            )
        if len(results) >= limit:
            break

    return results[:limit]


@router.get("/electrode-batches/by-name/{batch_name}", response_model=ElectrodeBatchRead)
async def get_electrode_batch_by_batch_name(
    batch_name: str,
    db: AsyncSession = Depends(get_db),
):
    batch = await get_electrode_batch_by_name(db, batch_name=batch_name)
    if not batch:
        raise _not_found("electrode batch")
    return ElectrodeBatchRead.model_validate(batch)


@router.get(
    "/electrode-batches/{entity_id}/lineage",
    response_model=ElectrodeBatchLineageRead,
)
async def get_electrode_batch_lineage_view(
    entity_id: int,
    db: AsyncSession = Depends(get_db),
):
    lineage = await get_electrode_batch_lineage(db, batch_id=entity_id)
    if lineage is None:
        raise _not_found("electrode batch")
    return lineage


@router.get(
    "/electrode-batches/{entity_id}/descendants",
    response_model=ElectrodeBatchDescendantsRead,
)
async def get_electrode_batch_descendants_view(
    entity_id: int,
    db: AsyncSession = Depends(get_db),
):
    descendants = await get_electrode_batch_descendants(db, batch_id=entity_id)
    if descendants is None:
        raise _not_found("electrode batch")
    return descendants


@router.get("/lineage-edges", response_model=list[LineageEdgeRead])
async def list_lineage_edges(
    parent_type: Optional[LineageEntityType] = Query(default=None),
    parent_id: Optional[int] = Query(default=None, ge=1),
    child_type: Optional[LineageEntityType] = Query(default=None),
    child_id: Optional[int] = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(LineageEdge).order_by(LineageEdge.created_at.desc())
    if parent_type is not None:
        stmt = stmt.where(LineageEdge.parent_type == parent_type)
    if parent_id is not None:
        stmt = stmt.where(LineageEdge.parent_id == parent_id)
    if child_type is not None:
        stmt = stmt.where(LineageEdge.child_type == child_type)
    if child_id is not None:
        stmt = stmt.where(LineageEdge.child_id == child_id)
    result = await db.execute(stmt)
    return [LineageEdgeRead.model_validate(row) for row in result.scalars().all()]


@router.get("/cell-builds/{entity_id}/lineage", response_model=CellBuildLineageRead)
async def get_cell_build_lineage_view(
    entity_id: int,
    db: AsyncSession = Depends(get_db),
):
    lineage = await get_cell_build_lineage(db, cell_build_id=entity_id)
    if lineage is None:
        raise _not_found("cell build")
    return lineage


@router.get(
    "/legacy-experiments/{legacy_experiment_id}/sources",
    response_model=LegacyExperimentSourcesRead,
)
async def get_legacy_experiment_sources_view(
    legacy_experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await get_legacy_experiment_sources(
        db,
        legacy_experiment_id=legacy_experiment_id,
    )


@router.post(
    "/lineage-edges",
    response_model=LineageEdgeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_lineage_edge(
    payload: LineageEdgeCreate,
    db: AsyncSession = Depends(get_db),
):
    edge = LineageEdge(**payload.model_dump())
    db.add(edge)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict("Unable to create lineage edge: duplicate or invalid payload") from exc
    await db.refresh(edge)
    return LineageEdgeRead.model_validate(edge)


@router.get("/lineage-edges/{edge_id}", response_model=LineageEdgeRead)
async def get_lineage_edge(edge_id: int, db: AsyncSession = Depends(get_db)):
    edge = await db.get(LineageEdge, edge_id)
    if not edge:
        raise _not_found("lineage edge")
    return LineageEdgeRead.model_validate(edge)


@router.patch("/lineage-edges/{edge_id}", response_model=LineageEdgeRead)
async def update_lineage_edge(
    edge_id: int,
    payload: LineageEdgeUpdate,
    db: AsyncSession = Depends(get_db),
):
    edge = await db.get(LineageEdge, edge_id)
    if not edge:
        raise _not_found("lineage edge")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(edge, field, value)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict("Unable to update lineage edge: integrity error") from exc
    await db.refresh(edge)
    return LineageEdgeRead.model_validate(edge)


@router.delete(
    "/lineage-edges/{edge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_lineage_edge(edge_id: int, db: AsyncSession = Depends(get_db)):
    edge = await db.get(LineageEdge, edge_id)
    if not edge:
        raise _not_found("lineage edge")
    await db.delete(edge)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/imports/nmc-cathode-workbook", response_model=dict[str, Any])
async def run_nmc_cathode_workbook_import(
    payload: NMCCathodeWorkbookImportRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await import_nmc_cathode_workbook(
            db,
            workbook_path=payload.workbook_path,
            legacy_db_path=payload.legacy_db_path,
            comparison_workbook_path=payload.comparison_workbook_path,
            export_dir=payload.export_dir,
            persist=payload.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/imports/lib-anode-workbook", response_model=dict[str, Any])
async def run_lib_anode_workbook_import(
    payload: LIBAnodeWorkbookImportRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await import_lib_anode_workbook(
            db,
            workbook_path=payload.workbook_path,
            legacy_db_path=payload.legacy_db_path,
            export_dir=payload.export_dir,
            persist=payload.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
