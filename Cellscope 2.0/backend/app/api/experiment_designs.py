"""Experiment Design API routes — CRUD plus realize-to-experiment."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.experiment_design import ExperimentDesign, DesignStatus
from app.models.experiment import Experiment
from app.models.cell import Cell
from app.schemas.experiment_design import (
    ExperimentDesignCreate,
    ExperimentDesignUpdate,
    ExperimentDesignRead,
    ExperimentDesignListRead,
    RealizeDesignRequest,
)

router = APIRouter(prefix="/api/experiment-designs", tags=["experiment-designs"])


def _enrich_read(design: ExperimentDesign) -> ExperimentDesignRead:
    """Build a read schema with resolved relationship names."""
    data = ExperimentDesignRead.model_validate(design)
    if design.target_project:
        data.target_project_name = design.target_project.name
    if design.formation_protocol:
        data.formation_protocol_name = (
            f"{design.formation_protocol.name} v{design.formation_protocol.version}"
        )
    if design.cycling_protocol:
        data.cycling_protocol_name = (
            f"{design.cycling_protocol.name} v{design.cycling_protocol.version}"
        )
    if design.target_equipment:
        data.target_equipment_name = design.target_equipment.name
    if design.designed_by:
        data.designed_by_name = design.designed_by.name
    return data


def _enrich_list(design: ExperimentDesign) -> ExperimentDesignListRead:
    data = ExperimentDesignListRead.model_validate(design)
    if design.target_project:
        data.target_project_name = design.target_project.name
    return data


@router.get("", response_model=list[ExperimentDesignListRead])
async def list_designs(db: AsyncSession = Depends(get_db)):
    """List all experiment designs."""
    result = await db.execute(
        select(ExperimentDesign).order_by(ExperimentDesign.updated_at.desc())
    )
    return [_enrich_list(d) for d in result.scalars().all()]


@router.post("", response_model=ExperimentDesignRead, status_code=status.HTTP_201_CREATED)
async def create_design(
    design_in: ExperimentDesignCreate, db: AsyncSession = Depends(get_db)
):
    """Create a new experiment design."""
    dump = design_in.model_dump()
    # Convert formulation entries to plain dicts for JSON storage
    if dump.get("formulation_json"):
        dump["formulation_json"] = [
            entry if isinstance(entry, dict) else entry
            for entry in dump["formulation_json"]
        ]
    design = ExperimentDesign(**dump)
    db.add(design)
    await db.flush()
    await db.refresh(design)
    return _enrich_read(design)


@router.get("/{design_id}", response_model=ExperimentDesignRead)
async def get_design(design_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single experiment design."""
    result = await db.execute(
        select(ExperimentDesign).where(ExperimentDesign.id == design_id)
    )
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Experiment design not found")
    return _enrich_read(design)


@router.patch("/{design_id}", response_model=ExperimentDesignRead)
async def update_design(
    design_id: int,
    design_in: ExperimentDesignUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an experiment design."""
    result = await db.execute(
        select(ExperimentDesign).where(ExperimentDesign.id == design_id)
    )
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Experiment design not found")

    update_data = design_in.model_dump(exclude_unset=True)
    if "formulation_json" in update_data and update_data["formulation_json"] is not None:
        update_data["formulation_json"] = [
            entry if isinstance(entry, dict) else entry
            for entry in update_data["formulation_json"]
        ]
    for field, value in update_data.items():
        setattr(design, field, value)

    await db.flush()
    await db.refresh(design)
    return _enrich_read(design)


@router.delete("/{design_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_design(design_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an experiment design."""
    result = await db.execute(
        select(ExperimentDesign).where(ExperimentDesign.id == design_id)
    )
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Experiment design not found")
    await db.delete(design)


@router.post("/{design_id}/realize", response_model=ExperimentDesignRead)
async def realize_design(
    design_id: int,
    body: RealizeDesignRequest,
    db: AsyncSession = Depends(get_db),
):
    """Realize a design: create a real Experiment + Cells from the design spec."""
    result = await db.execute(
        select(ExperimentDesign).where(ExperimentDesign.id == design_id)
    )
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Experiment design not found")
    if design.status == DesignStatus.REALIZED:
        raise HTTPException(
            status_code=400,
            detail="Design has already been realized",
        )

    # Create the experiment
    experiment = Experiment(
        project_id=body.project_id,
        name=body.experiment_name or design.name,
        experiment_date=None,
        disc_diameter_mm=design.disc_diameter_mm,
        solids_content=design.solids_content_pct,
        pressed_thickness=design.pressed_thickness_um,
        notes=f"Realized from experiment design #{design.id}: {design.name}",
    )
    db.add(experiment)
    await db.flush()
    await db.refresh(experiment)

    # Derive active material % from formulation
    active_material_pct = None
    formulation_for_cells = None
    if design.formulation_json:
        formulation_for_cells = [
            {
                "Component": entry.get("material_name", "Unknown"),
                "Dry Mass Fraction (%)": entry.get("dry_mass_fraction_pct", 0),
            }
            for entry in design.formulation_json
        ]
        for entry in design.formulation_json:
            cat = (entry.get("category") or "").lower()
            if "active" in cat:
                active_material_pct = entry.get("dry_mass_fraction_pct")
                break

    # Create cells according to the design
    pattern = design.cell_naming_pattern or "{name}-Cell-{n}"
    for i in range(1, design.num_cells + 1):
        cell_name = pattern.replace("{name}", design.name).replace("{n}", str(i))
        cell = Cell(
            experiment_id=experiment.id,
            cell_name=cell_name,
            loading=design.target_loading_mg_cm2,
            active_material_pct=active_material_pct,
            formation_cycles=design.formation_cycles or 4,
            electrolyte=design.electrolyte,
            separator=design.separator,
            substrate=design.current_collector,
            formulation=formulation_for_cells,
            cutoff_voltage_lower=design.cutoff_voltage_lower,
            cutoff_voltage_upper=design.cutoff_voltage_upper,
        )
        db.add(cell)

    # Update design status and link
    design.status = DesignStatus.REALIZED
    design.realized_experiment_id = experiment.id
    design.target_project_id = body.project_id

    await db.flush()
    await db.refresh(design)
    return _enrich_read(design)


@router.post("/{design_id}/duplicate", response_model=ExperimentDesignRead, status_code=status.HTTP_201_CREATED)
async def duplicate_design(design_id: int, db: AsyncSession = Depends(get_db)):
    """Duplicate a design as a new draft."""
    result = await db.execute(
        select(ExperimentDesign).where(ExperimentDesign.id == design_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Experiment design not found")

    # Copy all fields except id, status, realized link, timestamps
    copy_fields = [
        "name", "target_project_id", "electrode_role", "formulation_json",
        "disc_diameter_mm", "target_loading_mg_cm2", "target_thickness_um",
        "target_porosity", "solids_content_pct", "pressed_thickness_um",
        "active_mass_density_g_cc", "slurry_density_g_ml", "form_factor",
        "electrolyte", "separator", "current_collector", "formation_protocol_id",
        "cycling_protocol_id", "formation_cycles", "cutoff_voltage_lower",
        "cutoff_voltage_upper", "c_rate_charge", "c_rate_discharge", "temperature_c",
        "num_cells", "cell_naming_pattern", "target_equipment_id",
        "channel_assignments_json", "designed_by_id", "notes",
    ]
    kwargs = {f: getattr(source, f) for f in copy_fields}
    kwargs["name"] = f"{source.name} (copy)"
    kwargs["status"] = DesignStatus.DRAFT

    new_design = ExperimentDesign(**kwargs)
    db.add(new_design)
    await db.flush()
    await db.refresh(new_design)
    return _enrich_read(new_design)
