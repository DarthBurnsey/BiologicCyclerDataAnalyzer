"""Tests for ontology lineage query services and API routes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.ontology import router as ontology_router
from app.database import Base
from app.models.experiment import Experiment
from app.models.ontology import (
    CellBuild,
    CellBuildStatus,
    ElectrodeBatch,
    ElectrodeRole,
    LineageEdge,
    LineageEntityType,
    Material,
    MaterialCategory,
    ProcessRun,
    ProcessType,
)
from app.models.project import Project, ProjectType
from app.services.ontology_lineage import (
    get_cell_build_lineage,
    get_electrode_batch_by_name,
    get_electrode_batch_descendants,
    get_electrode_batch_lineage,
    get_legacy_experiment_sources,
)


pytestmark = pytest.mark.asyncio


async def create_session_factory(tmp_path: Path):
    db_path = tmp_path / "ontology-lineage-test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


async def seed_lineage_graph(session_factory) -> dict[str, int]:
    async with session_factory() as session:
        project = Project(name="NMC Half Cells", project_type=ProjectType.CATHODE)
        session.add(project)
        await session.flush()

        experiment_n9x = Experiment(project_id=project.id, name="N9x")
        experiment_n9x_remake = Experiment(project_id=project.id, name="N9x Remake")
        session.add_all([experiment_n9x, experiment_n9x_remake])
        await session.flush()

        nmc = Material(name="NMC811", category=MaterialCategory.CATHODE_ACTIVE)
        hx_e = Material(name="Hx-e", category=MaterialCategory.CONDUCTIVE_ADDITIVE)
        pvdf = Material(name="PVDF HSV1810", category=MaterialCategory.BINDER)
        session.add_all([nmc, hx_e, pvdf])
        await session.flush()

        process_run = ProcessRun(
            name="N9 parent process",
            process_type=ProcessType.COATING,
        )
        session.add(process_run)
        await session.flush()

        n9 = ElectrodeBatch(
            batch_name="N9",
            electrode_role=ElectrodeRole.CATHODE,
            active_material_id=nmc.id,
            process_run_id=process_run.id,
            formulation_json=[
                {"Component": "NMC811", "Dry Mass Fraction (%)": 92.0},
                {"Component": "Hx-e", "Dry Mass Fraction (%)": 4.0},
                {"Component": "PVDF HSV1810", "Dry Mass Fraction (%)": 4.0},
            ],
            metadata_json={"study_focus": "baseline"},
        )
        n9x = ElectrodeBatch(
            batch_name="N9x",
            electrode_role=ElectrodeRole.CATHODE,
            active_material_id=nmc.id,
            process_run_id=process_run.id,
            formulation_json=n9.formulation_json,
            metadata_json={"parent_batch_name": "N9", "study_focus": "porosity"},
        )
        n9y = ElectrodeBatch(
            batch_name="N9y",
            electrode_role=ElectrodeRole.CATHODE,
            active_material_id=nmc.id,
            process_run_id=process_run.id,
            formulation_json=n9.formulation_json,
            metadata_json={"parent_batch_name": "N9", "study_focus": "porosity"},
        )
        n9x_remake = ElectrodeBatch(
            batch_name="N9x-remake",
            electrode_role=ElectrodeRole.CATHODE,
            active_material_id=nmc.id,
            process_run_id=process_run.id,
            formulation_json=n9.formulation_json,
            metadata_json={"parent_batch_name": "N9x", "study_focus": "verification"},
        )
        session.add_all([n9, n9x, n9y, n9x_remake])
        await session.flush()

        fc5 = CellBuild(
            build_name="FC5",
            chemistry="NMC-Si full cell",
            status=CellBuildStatus.TESTING,
            legacy_experiment_id=experiment_n9x.id,
        )
        fc5_repeat = CellBuild(
            build_name="FC5-repeat",
            chemistry="NMC-Si full cell",
            status=CellBuildStatus.TESTING,
            legacy_experiment_id=experiment_n9x_remake.id,
        )
        session.add_all([fc5, fc5_repeat])
        await session.flush()

        session.add_all(
            [
                LineageEdge(
                    parent_type=LineageEntityType.MATERIAL,
                    parent_id=nmc.id,
                    child_type=LineageEntityType.ELECTRODE_BATCH,
                    child_id=n9.id,
                    relationship_type="formulates_into",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.MATERIAL,
                    parent_id=hx_e.id,
                    child_type=LineageEntityType.ELECTRODE_BATCH,
                    child_id=n9.id,
                    relationship_type="formulates_into",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.MATERIAL,
                    parent_id=pvdf.id,
                    child_type=LineageEntityType.ELECTRODE_BATCH,
                    child_id=n9.id,
                    relationship_type="formulates_into",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.MATERIAL,
                    parent_id=nmc.id,
                    child_type=LineageEntityType.ELECTRODE_BATCH,
                    child_id=n9x.id,
                    relationship_type="formulates_into",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.MATERIAL,
                    parent_id=hx_e.id,
                    child_type=LineageEntityType.ELECTRODE_BATCH,
                    child_id=n9x.id,
                    relationship_type="formulates_into",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.MATERIAL,
                    parent_id=nmc.id,
                    child_type=LineageEntityType.ELECTRODE_BATCH,
                    child_id=n9y.id,
                    relationship_type="formulates_into",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.MATERIAL,
                    parent_id=nmc.id,
                    child_type=LineageEntityType.ELECTRODE_BATCH,
                    child_id=n9x_remake.id,
                    relationship_type="formulates_into",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.ELECTRODE_BATCH,
                    parent_id=n9.id,
                    child_type=LineageEntityType.ELECTRODE_BATCH,
                    child_id=n9x.id,
                    relationship_type="branches_to",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.ELECTRODE_BATCH,
                    parent_id=n9.id,
                    child_type=LineageEntityType.ELECTRODE_BATCH,
                    child_id=n9y.id,
                    relationship_type="branches_to",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.ELECTRODE_BATCH,
                    parent_id=n9x.id,
                    child_type=LineageEntityType.ELECTRODE_BATCH,
                    child_id=n9x_remake.id,
                    relationship_type="branches_to",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.ELECTRODE_BATCH,
                    parent_id=n9x.id,
                    child_type=LineageEntityType.CELL_BUILD,
                    child_id=fc5.id,
                    relationship_type="cathode_source_for",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.ELECTRODE_BATCH,
                    parent_id=n9x_remake.id,
                    child_type=LineageEntityType.CELL_BUILD,
                    child_id=fc5_repeat.id,
                    relationship_type="cathode_source_for",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.ELECTRODE_BATCH,
                    parent_id=n9x.id,
                    child_type=LineageEntityType.EXPERIMENT,
                    child_id=experiment_n9x.id,
                    relationship_type="evaluated_in",
                    source="test_seed",
                ),
                LineageEdge(
                    parent_type=LineageEntityType.ELECTRODE_BATCH,
                    parent_id=n9x_remake.id,
                    child_type=LineageEntityType.EXPERIMENT,
                    child_id=experiment_n9x_remake.id,
                    relationship_type="evaluated_in",
                    source="test_seed",
                ),
            ]
        )
        await session.commit()

    return {
        "root_batch_id": n9.id,
        "child_batch_id": n9x.id,
        "cell_build_id": fc5.id,
        "legacy_experiment_id": experiment_n9x.id,
    }


async def test_ontology_lineage_routes_are_registered():
    route_paths = {route.path for route in ontology_router.routes}
    assert "/api/ontology/electrode-batches/by-name/{batch_name}" in route_paths
    assert "/api/ontology/electrode-batches/{entity_id}/lineage" in route_paths
    assert "/api/ontology/electrode-batches/{entity_id}/descendants" in route_paths
    assert "/api/ontology/cell-builds/{entity_id}/lineage" in route_paths
    assert "/api/ontology/legacy-experiments/{legacy_experiment_id}/sources" in route_paths


async def test_lineage_query_services_return_expected_graph(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)
    seeded_ids = await seed_lineage_graph(session_factory)

    async with session_factory() as session:
        batch = await get_electrode_batch_by_name(session, batch_name="N9")
        assert batch is not None
        assert batch.batch_name == "N9"

        lineage_payload = await get_electrode_batch_lineage(
            session,
            batch_id=seeded_ids["root_batch_id"],
        )
        assert lineage_payload is not None
        assert lineage_payload.batch.batch_name == "N9"
        assert {batch.batch_name for batch in lineage_payload.child_batches} == {"N9x", "N9y"}
        assert {material.name for material in lineage_payload.formulation_materials} == {
            "Hx-e",
            "NMC811",
            "PVDF HSV1810",
        }

        descendants_payload = await get_electrode_batch_descendants(
            session,
            batch_id=seeded_ids["root_batch_id"],
        )
        assert descendants_payload is not None
        assert {item.batch.batch_name for item in descendants_payload.descendants} == {
            "N9x",
            "N9x-remake",
            "N9y",
        }
        remake = next(
            item
            for item in descendants_payload.descendants
            if item.batch.batch_name == "N9x-remake"
        )
        assert remake.depth == 2
        assert remake.ancestor_path == ["N9", "N9x"]
        assert {build.build_name for build in descendants_payload.related_cell_builds} == {
            "FC5",
            "FC5-repeat",
        }

        cell_build_payload = await get_cell_build_lineage(
            session,
            cell_build_id=seeded_ids["cell_build_id"],
        )
        assert cell_build_payload is not None
        assert cell_build_payload.cell_build.build_name == "FC5"
        assert [batch.batch_name for batch in cell_build_payload.source_batches] == ["N9x"]
        assert {material.name for material in cell_build_payload.source_materials} == {
            "Hx-e",
            "NMC811",
        }

        legacy_payload = await get_legacy_experiment_sources(
            session,
            legacy_experiment_id=seeded_ids["legacy_experiment_id"],
        )
        assert legacy_payload.experiment_name == "N9x"
        assert legacy_payload.project_name == "NMC Half Cells"
        assert [batch.batch_name for batch in legacy_payload.source_batches] == ["N9x"]
        assert [build.build_name for build in legacy_payload.related_cell_builds] == ["FC5"]

    await engine.dispose()
