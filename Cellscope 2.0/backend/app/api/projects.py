"""Project API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.experiment import Experiment
from app.models.cell import Cell
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectRead, ProjectListRead

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list)
async def list_projects(db: AsyncSession = Depends(get_db)):
    """List all projects with experiment counts."""
    result = await db.execute(
        select(
            Project,
            func.count(Experiment.id).label("experiment_count")
        )
        .outerjoin(Experiment)
        .group_by(Project.id)
        .order_by(Project.updated_at.desc())
    )
    projects = []
    for project, exp_count in result.all():
        proj_data = ProjectListRead.model_validate(project)
        proj_data.experiment_count = exp_count
        projects.append(proj_data)
    return projects


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    project = Project(**project_in.model_dump())
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Get a project by ID with experiment and cell counts."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Count experiments and cells
    exp_count_result = await db.execute(
        select(func.count(Experiment.id)).where(Experiment.project_id == project_id)
    )
    cell_count_result = await db.execute(
        select(func.count(Cell.id))
        .join(Experiment)
        .where(Experiment.project_id == project_id)
    )

    proj_data = ProjectRead.model_validate(project)
    proj_data.experiment_count = exp_count_result.scalar() or 0
    proj_data.cell_count = cell_count_result.scalar() or 0
    return proj_data


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = project_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.flush()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a project and all its experiments/cells (cascade)."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)
