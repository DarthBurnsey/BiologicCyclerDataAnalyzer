"""Read/query helpers for ontology lineage traversal."""

from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment import Experiment
from app.models.ontology import (
    CellBuild,
    ElectrodeBatch,
    LineageEdge,
    LineageEntityType,
    Material,
    ProcessRun,
)
from app.models.project import Project
from app.schemas.ontology import (
    BatchDescendantRead,
    CellBuildLineageRead,
    CellBuildRead,
    ElectrodeBatchDescendantsRead,
    ElectrodeBatchLineageRead,
    ElectrodeBatchRead,
    LegacyExperimentSourcesRead,
    LegacyExperimentSummary,
    LineageEdgeRead,
    MaterialRead,
    ProcessRunRead,
)


async def get_electrode_batch_by_name(
    db: AsyncSession,
    *,
    batch_name: str,
) -> Optional[ElectrodeBatch]:
    result = await db.execute(
        select(ElectrodeBatch).where(ElectrodeBatch.batch_name == batch_name)
    )
    return result.scalars().first()


async def _fetch_batches_by_ids(
    db: AsyncSession,
    batch_ids: Iterable[int],
) -> Dict[int, ElectrodeBatch]:
    ids = sorted({batch_id for batch_id in batch_ids if batch_id is not None})
    if not ids:
        return {}
    result = await db.execute(select(ElectrodeBatch).where(ElectrodeBatch.id.in_(ids)))
    return {batch.id: batch for batch in result.scalars().all()}


async def _fetch_materials_by_ids(
    db: AsyncSession,
    material_ids: Iterable[int],
) -> Dict[int, Material]:
    ids = sorted({material_id for material_id in material_ids if material_id is not None})
    if not ids:
        return {}
    result = await db.execute(select(Material).where(Material.id.in_(ids)))
    return {material.id: material for material in result.scalars().all()}


async def _fetch_cell_builds_by_ids(
    db: AsyncSession,
    build_ids: Iterable[int],
) -> Dict[int, CellBuild]:
    ids = sorted({build_id for build_id in build_ids if build_id is not None})
    if not ids:
        return {}
    result = await db.execute(select(CellBuild).where(CellBuild.id.in_(ids)))
    return {build.id: build for build in result.scalars().all()}


async def _fetch_process_runs_by_ids(
    db: AsyncSession,
    process_run_ids: Iterable[int],
) -> Dict[int, ProcessRun]:
    ids = sorted({process_run_id for process_run_id in process_run_ids if process_run_id is not None})
    if not ids:
        return {}
    result = await db.execute(select(ProcessRun).where(ProcessRun.id.in_(ids)))
    return {run.id: run for run in result.scalars().all()}


async def _fetch_experiment_summaries(
    db: AsyncSession,
    legacy_experiment_ids: Iterable[int],
) -> Dict[int, LegacyExperimentSummary]:
    ids = sorted({legacy_experiment_id for legacy_experiment_id in legacy_experiment_ids if legacy_experiment_id is not None})
    if not ids:
        return {}

    summaries = {
        legacy_experiment_id: LegacyExperimentSummary(legacy_experiment_id=legacy_experiment_id)
        for legacy_experiment_id in ids
    }

    result = await db.execute(
        select(Experiment, Project)
        .outerjoin(Project, Experiment.project_id == Project.id)
        .where(Experiment.id.in_(ids))
    )
    for experiment, project in result.all():
        summaries[experiment.id] = LegacyExperimentSummary(
            legacy_experiment_id=experiment.id,
            experiment_name=experiment.name,
            project_id=project.id if project else None,
            project_name=project.name if project else None,
        )
    return summaries


async def _fetch_edges(
    db: AsyncSession,
    *,
    parent_type: Optional[LineageEntityType] = None,
    parent_ids: Optional[Iterable[int]] = None,
    child_type: Optional[LineageEntityType] = None,
    child_ids: Optional[Iterable[int]] = None,
) -> List[LineageEdge]:
    stmt = select(LineageEdge)
    if parent_type is not None:
        stmt = stmt.where(LineageEdge.parent_type == parent_type)
    if parent_ids is not None:
        normalized_parent_ids = sorted({parent_id for parent_id in parent_ids if parent_id is not None})
        if not normalized_parent_ids:
            return []
        stmt = stmt.where(LineageEdge.parent_id.in_(normalized_parent_ids))
    if child_type is not None:
        stmt = stmt.where(LineageEdge.child_type == child_type)
    if child_ids is not None:
        normalized_child_ids = sorted({child_id for child_id in child_ids if child_id is not None})
        if not normalized_child_ids:
            return []
        stmt = stmt.where(LineageEdge.child_id.in_(normalized_child_ids))

    result = await db.execute(stmt.order_by(LineageEdge.id.asc()))
    return list(result.scalars().all())


def _batch_to_read(batch: ElectrodeBatch) -> ElectrodeBatchRead:
    return ElectrodeBatchRead.model_validate(batch)


def _material_to_read(material: Material) -> MaterialRead:
    return MaterialRead.model_validate(material)


def _cell_build_to_read(build: CellBuild) -> CellBuildRead:
    return CellBuildRead.model_validate(build)


def _process_run_to_read(process_run: ProcessRun) -> ProcessRunRead:
    return ProcessRunRead.model_validate(process_run)


def _edge_to_read(edge: LineageEdge) -> LineageEdgeRead:
    return LineageEdgeRead.model_validate(edge)


def _sorted_batches(batches: Iterable[ElectrodeBatch]) -> List[ElectrodeBatchRead]:
    return [_batch_to_read(batch) for batch in sorted(batches, key=lambda item: item.batch_name.lower())]


def _sorted_materials(materials: Iterable[Material]) -> List[MaterialRead]:
    return [_material_to_read(material) for material in sorted(materials, key=lambda item: item.name.lower())]


def _sorted_builds(builds: Iterable[CellBuild]) -> List[CellBuildRead]:
    return [_cell_build_to_read(build) for build in sorted(builds, key=lambda item: item.build_name.lower())]


def _sorted_experiment_summaries(
    summaries: Iterable[LegacyExperimentSummary],
) -> List[LegacyExperimentSummary]:
    return sorted(
        summaries,
        key=lambda item: (
            (item.project_name or "").lower(),
            (item.experiment_name or "").lower(),
            item.legacy_experiment_id,
        ),
    )


async def get_electrode_batch_lineage(
    db: AsyncSession,
    *,
    batch_id: int,
) -> Optional[ElectrodeBatchLineageRead]:
    batch = await db.get(ElectrodeBatch, batch_id)
    if batch is None:
        return None

    incoming_edges = await _fetch_edges(
        db,
        child_type=LineageEntityType.ELECTRODE_BATCH,
        child_ids=[batch.id],
    )
    outgoing_edges = await _fetch_edges(
        db,
        parent_type=LineageEntityType.ELECTRODE_BATCH,
        parent_ids=[batch.id],
    )
    all_edges = [*incoming_edges, *outgoing_edges]

    parent_batch_ids = [
        edge.parent_id
        for edge in incoming_edges
        if edge.parent_type == LineageEntityType.ELECTRODE_BATCH
    ]
    material_ids = [
        edge.parent_id
        for edge in incoming_edges
        if edge.parent_type == LineageEntityType.MATERIAL
    ]
    child_batch_ids = [
        edge.child_id
        for edge in outgoing_edges
        if edge.child_type == LineageEntityType.ELECTRODE_BATCH
    ]
    cell_build_ids = [
        edge.child_id
        for edge in outgoing_edges
        if edge.child_type == LineageEntityType.CELL_BUILD
    ]
    legacy_experiment_ids = [
        edge.child_id
        for edge in outgoing_edges
        if edge.child_type == LineageEntityType.EXPERIMENT
    ]

    parent_batches = await _fetch_batches_by_ids(db, parent_batch_ids)
    child_batches = await _fetch_batches_by_ids(db, child_batch_ids)
    formulation_materials = await _fetch_materials_by_ids(db, material_ids)
    active_materials = await _fetch_materials_by_ids(db, [batch.active_material_id])
    process_runs = await _fetch_process_runs_by_ids(db, [batch.process_run_id])
    cell_builds = await _fetch_cell_builds_by_ids(db, cell_build_ids)
    legacy_experiments = await _fetch_experiment_summaries(db, legacy_experiment_ids)

    return ElectrodeBatchLineageRead(
        batch=_batch_to_read(batch),
        active_material=_material_to_read(active_materials[batch.active_material_id])
        if batch.active_material_id in active_materials
        else None,
        process_run=_process_run_to_read(process_runs[batch.process_run_id])
        if batch.process_run_id in process_runs
        else None,
        parent_batches=_sorted_batches(parent_batches.values()),
        child_batches=_sorted_batches(child_batches.values()),
        formulation_materials=_sorted_materials(formulation_materials.values()),
        cell_builds=_sorted_builds(cell_builds.values()),
        legacy_experiments=_sorted_experiment_summaries(legacy_experiments.values()),
        lineage_edges=[_edge_to_read(edge) for edge in all_edges],
    )


async def get_electrode_batch_descendants(
    db: AsyncSession,
    *,
    batch_id: int,
) -> Optional[ElectrodeBatchDescendantsRead]:
    root_batch = await db.get(ElectrodeBatch, batch_id)
    if root_batch is None:
        return None

    discovered_edges: List[LineageEdge] = []
    parent_by_child: Dict[int, int] = {}
    depth_by_batch_id: Dict[int, int] = {}
    descendant_ids: set[int] = set()
    queue: deque[int] = deque([root_batch.id])

    while queue:
        parent_batch_id = queue.popleft()
        child_edges = await _fetch_edges(
            db,
            parent_type=LineageEntityType.ELECTRODE_BATCH,
            parent_ids=[parent_batch_id],
            child_type=LineageEntityType.ELECTRODE_BATCH,
        )
        for edge in child_edges:
            if edge.child_id in descendant_ids:
                continue
            descendant_ids.add(edge.child_id)
            parent_by_child[edge.child_id] = parent_batch_id
            depth_by_batch_id[edge.child_id] = depth_by_batch_id.get(parent_batch_id, 0) + 1
            discovered_edges.append(edge)
            queue.append(edge.child_id)

    descendant_batches = await _fetch_batches_by_ids(db, descendant_ids)
    build_edges = await _fetch_edges(
        db,
        parent_type=LineageEntityType.ELECTRODE_BATCH,
        parent_ids=descendant_ids,
        child_type=LineageEntityType.CELL_BUILD,
    )
    experiment_edges = await _fetch_edges(
        db,
        parent_type=LineageEntityType.ELECTRODE_BATCH,
        parent_ids=descendant_ids,
        child_type=LineageEntityType.EXPERIMENT,
    )

    related_builds = await _fetch_cell_builds_by_ids(db, [edge.child_id for edge in build_edges])
    related_experiments = await _fetch_experiment_summaries(
        db,
        [edge.child_id for edge in experiment_edges],
    )

    builds_by_batch_id: Dict[int, int] = {}
    for edge in build_edges:
        builds_by_batch_id[edge.parent_id] = builds_by_batch_id.get(edge.parent_id, 0) + 1

    experiments_by_batch_id: Dict[int, int] = {}
    for edge in experiment_edges:
        experiments_by_batch_id[edge.parent_id] = experiments_by_batch_id.get(edge.parent_id, 0) + 1

    descendants: List[BatchDescendantRead] = []
    for descendant_id, batch in sorted(descendant_batches.items(), key=lambda item: item[1].batch_name.lower()):
        path_names: List[str] = []
        current_id = descendant_id
        while current_id in parent_by_child:
            parent_id = parent_by_child[current_id]
            if parent_id == root_batch.id:
                path_names.append(root_batch.batch_name)
                break
            parent_batch = descendant_batches.get(parent_id)
            if parent_batch is None:
                break
            path_names.append(parent_batch.batch_name)
            current_id = parent_id
        descendants.append(
            BatchDescendantRead(
                depth=depth_by_batch_id[descendant_id],
                ancestor_path=list(reversed(path_names)),
                batch=_batch_to_read(batch),
                cell_build_count=builds_by_batch_id.get(descendant_id, 0),
                legacy_experiment_count=experiments_by_batch_id.get(descendant_id, 0),
            )
        )

    return ElectrodeBatchDescendantsRead(
        root_batch=_batch_to_read(root_batch),
        descendants=descendants,
        related_cell_builds=_sorted_builds(related_builds.values()),
        related_legacy_experiments=_sorted_experiment_summaries(related_experiments.values()),
        lineage_edges=[_edge_to_read(edge) for edge in [*discovered_edges, *build_edges, *experiment_edges]],
    )


async def get_cell_build_lineage(
    db: AsyncSession,
    *,
    cell_build_id: int,
) -> Optional[CellBuildLineageRead]:
    cell_build = await db.get(CellBuild, cell_build_id)
    if cell_build is None:
        return None

    incoming_edges = await _fetch_edges(
        db,
        child_type=LineageEntityType.CELL_BUILD,
        child_ids=[cell_build.id],
    )
    source_batch_ids = [
        edge.parent_id
        for edge in incoming_edges
        if edge.parent_type == LineageEntityType.ELECTRODE_BATCH
    ]
    source_batches = await _fetch_batches_by_ids(db, source_batch_ids)

    material_edges = await _fetch_edges(
        db,
        child_type=LineageEntityType.ELECTRODE_BATCH,
        child_ids=source_batch_ids,
        parent_type=LineageEntityType.MATERIAL,
    )
    material_ids = [edge.parent_id for edge in material_edges]
    source_materials = await _fetch_materials_by_ids(db, material_ids)

    experiment_edges = await _fetch_edges(
        db,
        parent_type=LineageEntityType.ELECTRODE_BATCH,
        parent_ids=source_batch_ids,
        child_type=LineageEntityType.EXPERIMENT,
    )
    related_experiment_ids = {cell_build.legacy_experiment_id} if cell_build.legacy_experiment_id else set()
    related_experiment_ids.update(edge.child_id for edge in experiment_edges)

    related_experiments = await _fetch_experiment_summaries(db, related_experiment_ids)

    return CellBuildLineageRead(
        cell_build=_cell_build_to_read(cell_build),
        source_batches=_sorted_batches(source_batches.values()),
        source_materials=_sorted_materials(source_materials.values()),
        related_legacy_experiments=_sorted_experiment_summaries(related_experiments.values()),
        lineage_edges=[_edge_to_read(edge) for edge in [*incoming_edges, *material_edges, *experiment_edges]],
    )


async def get_legacy_experiment_sources(
    db: AsyncSession,
    *,
    legacy_experiment_id: int,
) -> LegacyExperimentSourcesRead:
    incoming_edges = await _fetch_edges(
        db,
        child_type=LineageEntityType.EXPERIMENT,
        child_ids=[legacy_experiment_id],
        parent_type=LineageEntityType.ELECTRODE_BATCH,
    )
    source_batch_ids = [edge.parent_id for edge in incoming_edges]
    source_batches = await _fetch_batches_by_ids(db, source_batch_ids)

    material_edges = await _fetch_edges(
        db,
        child_type=LineageEntityType.ELECTRODE_BATCH,
        child_ids=source_batch_ids,
        parent_type=LineageEntityType.MATERIAL,
    )
    source_materials = await _fetch_materials_by_ids(db, [edge.parent_id for edge in material_edges])

    build_edges = await _fetch_edges(
        db,
        parent_type=LineageEntityType.ELECTRODE_BATCH,
        parent_ids=source_batch_ids,
        child_type=LineageEntityType.CELL_BUILD,
    )
    related_cell_builds = await _fetch_cell_builds_by_ids(db, [edge.child_id for edge in build_edges])
    experiment_summaries = await _fetch_experiment_summaries(db, [legacy_experiment_id])
    experiment_summary = experiment_summaries.get(
        legacy_experiment_id,
        LegacyExperimentSummary(legacy_experiment_id=legacy_experiment_id),
    )

    return LegacyExperimentSourcesRead(
        legacy_experiment_id=legacy_experiment_id,
        experiment_name=experiment_summary.experiment_name,
        project_id=experiment_summary.project_id,
        project_name=experiment_summary.project_name,
        source_batches=_sorted_batches(source_batches.values()),
        source_materials=_sorted_materials(source_materials.values()),
        related_cell_builds=_sorted_builds(related_cell_builds.values()),
        lineage_edges=[_edge_to_read(edge) for edge in [*incoming_edges, *material_edges, *build_edges]],
    )
