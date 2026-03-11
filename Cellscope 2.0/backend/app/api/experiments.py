"""Experiment API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.experiment import Experiment
from app.models.cell import Cell
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentRead,
    ExperimentListRead,
)

router = APIRouter(tags=["experiments"])


@router.get("/api/projects/{project_id}/experiments", response_model=list)
async def list_experiments(
    project_id: int, db: AsyncSession = Depends(get_db)
):
    """List all experiments in a project with cell counts."""
    result = await db.execute(
        select(
            Experiment,
            func.count(Cell.id).label("cell_count"),
        )
        .outerjoin(Cell)
        .where(Experiment.project_id == project_id)
        .group_by(Experiment.id)
        .order_by(Experiment.created_at.desc())
    )
    experiments = []
    for experiment, cell_count in result.all():
        exp_data = ExperimentListRead.model_validate(experiment)
        exp_data.cell_count = cell_count
        experiments.append(exp_data)
    return experiments


@router.post(
    "/api/projects/{project_id}/experiments",
    response_model=ExperimentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_experiment(
    project_id: int,
    experiment_in: ExperimentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new experiment in a project."""
    experiment = Experiment(project_id=project_id, **experiment_in.model_dump())
    db.add(experiment)
    await db.flush()
    await db.refresh(experiment)
    return ExperimentRead.model_validate(experiment)


@router.get("/api/experiments/{experiment_id}", response_model=ExperimentRead)
async def get_experiment(
    experiment_id: int, db: AsyncSession = Depends(get_db)
):
    """Get an experiment by ID with all its cells."""
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentRead.model_validate(experiment)


@router.put("/api/experiments/{experiment_id}", response_model=ExperimentRead)
async def update_experiment(
    experiment_id: int,
    experiment_in: ExperimentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an experiment."""
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    update_data = experiment_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(experiment, field, value)

    await db.flush()
    await db.refresh(experiment)
    return ExperimentRead.model_validate(experiment)


@router.delete(
    "/api/experiments/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_experiment(
    experiment_id: int, db: AsyncSession = Depends(get_db)
):
    """Delete an experiment and all its cells (cascade)."""
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    await db.delete(experiment)
