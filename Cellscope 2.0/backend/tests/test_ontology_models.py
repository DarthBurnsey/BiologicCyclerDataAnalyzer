"""Integration tests for canonical ontology models and app wiring."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.ontology import router as ontology_router
from app.database import Base
from app.main import app
from app.models.ontology import (
    CellBuild,
    CellBuildStatus,
    ElectrodeBatch,
    ElectrodeRole,
    EquipmentAsset,
    EquipmentType,
    LineageEdge,
    LineageEntityType,
    Material,
    MaterialCategory,
    MaterialLot,
    Operator,
    ProcessRun,
    ProcessType,
    ProtocolType,
    ProtocolVersion,
)


async def create_session_factory(tmp_path: Path):
    db_path = tmp_path / "ontology-model-test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


async def test_ontology_models_persist_foundational_entities(tmp_path):
    engine, session_factory = await create_session_factory(tmp_path)

    async with session_factory() as session:
        material = Material(
            name="NMC811",
            category=MaterialCategory.CATHODE_ACTIVE,
            manufacturer="Example Materials",
        )
        session.add(material)
        await session.flush()

        lot = MaterialLot(
            material_id=material.id,
            lot_code="LOT-811-A",
            supplier_name="Cathode Supplier",
        )
        session.add(lot)

        protocol = ProtocolVersion(
            name="Formation Protocol",
            version="v3",
            protocol_type=ProtocolType.FORMATION,
            step_definition_json={"steps": [{"mode": "CCCV", "cycles": 4}]},
        )
        session.add(protocol)
        await session.flush()

        operator = Operator(name="Alex Kim", team="Cell Engineering")
        equipment = EquipmentAsset(
            name="Cycler Rack 12",
            asset_type=EquipmentType.CYCLER,
            vendor="BioLogic",
        )
        session.add_all([operator, equipment])
        await session.flush()

        process_run = ProcessRun(
            name="Cathode Calendaring Run 22",
            process_type=ProcessType.CALENDARING,
            protocol_version_id=protocol.id,
            operator_id=operator.id,
            equipment_asset_id=equipment.id,
            settings_json={"gap_um": 42, "line_speed_m_min": 1.5},
        )
        session.add(process_run)
        await session.flush()

        electrode_batch = ElectrodeBatch(
            batch_name="CAT-EB-022",
            electrode_role=ElectrodeRole.CATHODE,
            active_material_id=material.id,
            process_run_id=process_run.id,
            formulation_json=[
                {"Component": "NMC811", "Dry Mass Fraction (%)": 94.0},
                {"Component": "PVDF", "Dry Mass Fraction (%)": 3.0},
            ],
        )
        session.add(electrode_batch)
        await session.flush()

        cell_build = CellBuild(
            build_name="FC-2026-001",
            chemistry="NMC811-Graphite",
            form_factor="coin",
            status=CellBuildStatus.BUILT,
            legacy_project_id=1,
            legacy_experiment_id=2,
            legacy_cell_id=3,
            legacy_test_number="FC001",
        )
        session.add(cell_build)
        await session.flush()

        session.add_all(
            [
                LineageEdge(
                    parent_type=LineageEntityType.MATERIAL_LOT,
                    parent_id=lot.id,
                    child_type=LineageEntityType.ELECTRODE_BATCH,
                    child_id=electrode_batch.id,
                    relationship_type="feeds_batch",
                    source="test_seed",
                    confidence=1.0,
                ),
                LineageEdge(
                    parent_type=LineageEntityType.ELECTRODE_BATCH,
                    parent_id=electrode_batch.id,
                    child_type=LineageEntityType.CELL_BUILD,
                    child_id=cell_build.id,
                    relationship_type="built_into",
                    source="test_seed",
                    confidence=1.0,
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        material_rows = (
            await session.execute(select(Material).where(Material.name == "NMC811"))
        ).scalars().all()
        assert len(material_rows) == 1

        build = (
            await session.execute(
                select(CellBuild).where(CellBuild.build_name == "FC-2026-001")
            )
        ).scalar_one()
        assert build.legacy_test_number == "FC001"
        assert build.status == CellBuildStatus.BUILT

        lineage_rows = (
            await session.execute(
                select(LineageEdge)
                .where(LineageEdge.child_type == LineageEntityType.CELL_BUILD)
                .where(LineageEdge.child_id == build.id)
            )
        ).scalars().all()
        assert len(lineage_rows) == 1
        assert lineage_rows[0].parent_type == LineageEntityType.ELECTRODE_BATCH

    await engine.dispose()


async def test_ontology_router_registers_routes():
    route_paths = {route.path for route in ontology_router.routes}
    assert "/api/ontology/materials" in route_paths
    assert "/api/ontology/cell-builds" in route_paths
    assert "/api/ontology/lineage-edges" in route_paths

    app_route_paths = {route.path for route in app.routes}
    assert "/api/ontology/materials" in app_route_paths
pytestmark = pytest.mark.asyncio
