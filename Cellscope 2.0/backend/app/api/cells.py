"""Cell API routes."""

import io
import re
from pathlib import Path
from typing import List

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.cell import Cell
from app.schemas.cell import CellCreate, CellUpdate, CellRead

router = APIRouter(prefix="/api", tags=["cells"])


# ---------------------------------------------------------------------------
# Cycling data file parsers (ported from legacy data_processing.py)
# ---------------------------------------------------------------------------

def _detect_file_type(data: bytes) -> str:
    """Detect cycler file format from raw bytes."""
    if data[:4] == b"PK\x03\x04":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
        names = wb.sheetnames
        wb.close()
        if "Cycle List1" in names:
            return "mti_xlsx"
        return "neware_xlsx"
    return "biologic_csv"


def _parse_biologic_csv(buf: io.BytesIO, loading: float, active_pct: float) -> pd.DataFrame:
    """Parse Biologic CSV (semicolon or comma delimited)."""
    buf.seek(0)
    first_line = buf.readline().decode("utf-8", errors="ignore")
    buf.seek(0)
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    df = pd.read_csv(buf, delimiter=delimiter)

    for col in ["Q charge (mA.h)", "Q discharge (mA.h)"]:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}. Available: {list(df.columns)}")

    df["Q charge (mA.h)"] = df["Q charge (mA.h)"].fillna(0)
    df["Q discharge (mA.h)"] = df["Q discharge (mA.h)"].fillna(0)
    df = df[(df["Q charge (mA.h)"] > 0) | (df["Q discharge (mA.h)"] > 0)].reset_index(drop=True)
    if df.empty:
        raise ValueError("No valid cycling data found after filtering")

    active_mass = (loading / 1000) * (active_pct / 100)
    if active_mass <= 0:
        raise ValueError("Active mass must be > 0 — check loading and active material %.")

    out = pd.DataFrame()
    out["cycle"] = range(1, len(df) + 1)
    out["charge_capacity_mah"] = df["Q charge (mA.h)"].values
    out["discharge_capacity_mah"] = df["Q discharge (mA.h)"].values
    out["charge_capacity_mah_g"] = out["charge_capacity_mah"] / active_mass
    out["discharge_capacity_mah_g"] = out["discharge_capacity_mah"] / active_mass
    mask = (out["charge_capacity_mah"] > 0) & (out["discharge_capacity_mah"] > 0)
    out["coulombic_efficiency"] = 0.0
    out.loc[mask, "coulombic_efficiency"] = (
        out.loc[mask, "discharge_capacity_mah"] / out.loc[mask, "charge_capacity_mah"]
    )
    return out


def _extract_cutoff_voltages_neware(buf: io.BytesIO):
    """Try to extract cutoff voltages from Neware 'test' sheet."""
    try:
        test_df = pd.read_excel(buf, sheet_name="test")
        buf.seek(0)
        if len(test_df.columns) < 7:
            return None, None
        col_g = test_df.iloc[:, 6].astype(str)
        lower, upper = None, None
        for val in col_g:
            if val == "nan":
                continue
            m = re.search(r"(\d+\.?\d*)\s*-\s*(\d+\.?\d*)", val)
            if m:
                v1, v2 = float(m.group(1)), float(m.group(2))
                lower, upper = min(v1, v2), max(v1, v2)
                break
        return lower, upper
    except Exception:
        buf.seek(0)
        return None, None


def _parse_neware_xlsx(buf: io.BytesIO, loading: float, active_pct: float):
    """Parse Neware XLSX 'cycle' sheet. Returns (df, lower_v, upper_v)."""
    lower_v, upper_v = _extract_cutoff_voltages_neware(buf)
    buf.seek(0)
    df = pd.read_excel(buf, sheet_name="cycle")
    df.columns = df.columns.str.strip().str.replace("\n", "")

    for col in ["Chg. Cap.(mAh)", "DChg. Cap.(mAh)"]:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}. Available: {list(df.columns)}")

    active_mass = (loading / 1000) * (active_pct / 100)
    if active_mass <= 0:
        raise ValueError("Active mass must be > 0 — check loading and active material %.")

    out = pd.DataFrame()
    out["cycle"] = df["Cycle Index"].values if "Cycle Index" in df.columns else range(1, len(df) + 1)
    out["charge_capacity_mah"] = df["Chg. Cap.(mAh)"].fillna(0).values
    out["discharge_capacity_mah"] = df["DChg. Cap.(mAh)"].fillna(0).values
    out = out[(out["charge_capacity_mah"] > 0) | (out["discharge_capacity_mah"] > 0)].reset_index(drop=True)
    if out.empty:
        raise ValueError("No valid cycling data found after filtering")

    out["charge_capacity_mah_g"] = out["charge_capacity_mah"] / active_mass
    out["discharge_capacity_mah_g"] = out["discharge_capacity_mah"] / active_mass
    mask = (out["charge_capacity_mah"] > 0) & (out["discharge_capacity_mah"] > 0)
    out["coulombic_efficiency"] = 0.0
    out.loc[mask, "coulombic_efficiency"] = (
        out.loc[mask, "discharge_capacity_mah"] / out.loc[mask, "charge_capacity_mah"]
    )
    return out, lower_v, upper_v


def _extract_cutoff_voltages_mti(buf: io.BytesIO):
    """Try to extract cutoff voltages from MTI 'Ch info' sheet."""
    try:
        ch_df = pd.read_excel(buf, sheet_name="Ch info")
        buf.seek(0)
        if len(ch_df.columns) < 3:
            return None, None
        col_c = ch_df.iloc[:, 2].astype(str)
        lower, upper = None, None
        for val in col_c:
            if val == "nan":
                continue
            m = re.search(r"(\d+\.?\d*)\s*-\s*(\d+\.?\d*)", val)
            if m:
                v1, v2 = float(m.group(1)), float(m.group(2))
                lower, upper = min(v1, v2), max(v1, v2)
                break
        return lower, upper
    except Exception:
        buf.seek(0)
        return None, None


def _parse_mti_xlsx(buf: io.BytesIO, loading: float, active_pct: float):
    """Parse MTI XLSX 'Cycle List1' sheet. Returns (df, lower_v, upper_v)."""
    lower_v, upper_v = _extract_cutoff_voltages_mti(buf)
    buf.seek(0)
    df = pd.read_excel(buf, sheet_name="Cycle List1")
    df.columns = df.columns.str.strip()

    for col in ["Cycle", "Charge C(mAh)", "Discharge C(mAh)"]:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}. Available: {list(df.columns)}")

    active_mass = (loading / 1000) * (active_pct / 100)
    if active_mass <= 0:
        raise ValueError("Active mass must be > 0 — check loading and active material %.")

    out = pd.DataFrame()
    out["cycle"] = df["Cycle"].values
    out["charge_capacity_mah"] = df["Charge C(mAh)"].fillna(0).values
    out["discharge_capacity_mah"] = df["Discharge C(mAh)"].fillna(0).values
    out = out[(out["charge_capacity_mah"] > 0) | (out["discharge_capacity_mah"] > 0)].reset_index(drop=True)
    if out.empty:
        raise ValueError("No valid cycling data found after filtering")

    out["charge_capacity_mah_g"] = out["charge_capacity_mah"] / active_mass
    out["discharge_capacity_mah_g"] = out["discharge_capacity_mah"] / active_mass
    mask = (out["charge_capacity_mah"] > 0) & (out["discharge_capacity_mah"] > 0)
    out["coulombic_efficiency"] = 0.0
    out.loc[mask, "coulombic_efficiency"] = (
        out.loc[mask, "discharge_capacity_mah"] / out.loc[mask, "charge_capacity_mah"]
    )
    return out, lower_v, upper_v


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


@router.post("/cells/{cell_id}/upload-cycling-data", response_model=CellRead)
async def upload_cycling_data(
    cell_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a cycling data file (CSV/XLSX) to a cell.

    Supports Biologic CSV, Neware XLSX, and MTI XLSX formats.
    The cell must have loading and active_material_pct set for
    gravimetric capacity calculations.
    """
    result = await db.execute(select(Cell).where(Cell.id == cell_id))
    cell = result.scalar_one_or_none()
    if not cell:
        raise HTTPException(status_code=404, detail="Cell not found")

    loading = cell.loading
    active_pct = cell.active_material_pct
    if not loading or not active_pct:
        raise HTTPException(
            status_code=400,
            detail="Cell must have loading and active_material_pct set before uploading cycling data.",
        )

    raw = await file.read()
    buf = io.BytesIO(raw)

    try:
        file_type = _detect_file_type(raw)
        lower_v, upper_v = None, None

        if file_type == "biologic_csv":
            df = _parse_biologic_csv(buf, loading, active_pct)
        elif file_type == "neware_xlsx":
            df, lower_v, upper_v = _parse_neware_xlsx(buf, loading, active_pct)
        elif file_type == "mti_xlsx":
            df, lower_v, upper_v = _parse_mti_xlsx(buf, loading, active_pct)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Store as parquet
    parquet_dir = settings.data_path / str(cell.experiment_id)
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_file = parquet_dir / f"cell_{cell_id}.parquet"
    df.to_parquet(str(parquet_file), index=False)

    # Store compact JSON for charting
    data_json = {
        "cycle": df["cycle"].tolist(),
        "charge_capacity_mah_g": [round(v, 3) for v in df["charge_capacity_mah_g"]],
        "discharge_capacity_mah_g": [round(v, 3) for v in df["discharge_capacity_mah_g"]],
        "coulombic_efficiency": [round(v, 5) for v in df["coulombic_efficiency"]],
    }

    cell.file_name = file.filename
    cell.parquet_path = str(parquet_file)
    cell.data_json = data_json
    if lower_v is not None:
        cell.cutoff_voltage_lower = lower_v
    if upper_v is not None:
        cell.cutoff_voltage_upper = upper_v

    await db.flush()
    await db.refresh(cell)
    return CellRead.model_validate(cell)
