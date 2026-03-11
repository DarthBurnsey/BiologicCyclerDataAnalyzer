"""Cell API routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.cell import Cell
from app.schemas.cell import CellCreate, CellUpdate, CellRead

router = APIRouter(prefix="/api", tags=["cells"])


@router.post(
    "/experiments/{experiment_id}/cells",
    response_model=CellRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_cell(
    experiment_id: int,
    cell_in: CellCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a cell to an experiment."""
    cell_data = cell_in.model_dump()
    # Convert formulation components to plain dicts for JSON storage
    if cell_data.get("formulation"):
        cell_data["formulation"] = [
            comp.model_dump(by_alias=True) if hasattr(comp, "model_dump") else comp
            for comp in cell_in.formulation
        ]
    cell = Cell(experiment_id=experiment_id, **cell_data)
    db.add(cell)
    await db.flush()
    await db.refresh(cell)
    return CellRead.model_validate(cell)


@router.get("/cells/{cell_id}", response_model=CellRead)
async def get_cell(cell_id: int, db: AsyncSession = Depends(get_db)):
    """Get a cell by ID."""
    result = await db.execute(select(Cell).where(Cell.id == cell_id))
    cell = result.scalar_one_or_none()
    if not cell:
        raise HTTPException(status_code=404, detail="Cell not found")
    return CellRead.model_validate(cell)


@router.put("/cells/{cell_id}", response_model=CellRead)
async def update_cell(
    cell_id: int,
    cell_in: CellUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a cell."""
    result = await db.execute(select(Cell).where(Cell.id == cell_id))
    cell = result.scalar_one_or_none()
    if not cell:
        raise HTTPException(status_code=404, detail="Cell not found")

    update_data = cell_in.model_dump(exclude_unset=True)
    # Convert formulation components to plain dicts for JSON storage
    if "formulation" in update_data and update_data["formulation"] is not None:
        update_data["formulation"] = [
            comp.model_dump(by_alias=True) if hasattr(comp, "model_dump") else comp
            for comp in cell_in.formulation
        ]
    for field, value in update_data.items():
        setattr(cell, field, value)

    await db.flush()
    await db.refresh(cell)
    return CellRead.model_validate(cell)


@router.delete("/cells/{cell_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cell(cell_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a cell."""
    result = await db.execute(select(Cell).where(Cell.id == cell_id))
    cell = result.scalar_one_or_none()
    if not cell:
        raise HTTPException(status_code=404, detail="Cell not found")

    await db.delete(cell)
