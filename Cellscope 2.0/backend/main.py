"""CellScope 2.0 — FastAPI Backend

Single-file API wrapping v1.0's proven database functions.
Shares the same cellscope.db database for coexistence with the Streamlit app.
"""

import json
import os
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware

import database as db
from schemas import (
    ProjectCreate, ProjectUpdate, ProjectOut,
    ExperimentSummary, ExperimentDetail, ExperimentCreate, ExperimentUpdate,
    PreferencesUpdate, FormulationQuery, HealthResponse,
)

# ─── App Setup ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="CellScope 2.0",
    description="Battery cell testing data management and analysis API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USER_ID = db.TEST_USER_ID  # Single-user for now


# ─── Health ─────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="ok",
        app="CellScope 2.0",
        version="2.0.0",
        database=db.DATABASE_PATH,
    )


# ─── Projects ──────────────────────────────────────────────────────────────

@app.get("/api/projects", response_model=list)
def list_projects():
    """List all projects with experiment counts."""
    projects = db.get_user_projects(USER_ID)
    result = []
    for p in projects:
        pid, name, desc, ptype, created, modified = p
        # Count experiments
        exps = db.get_project_experiments(pid)
        result.append(ProjectOut(
            id=pid, name=name, description=desc, project_type=ptype or "Full Cell",
            created_date=str(created) if created else None,
            last_modified=str(modified) if modified else None,
            experiment_count=len(exps),
        ))
    return result


@app.post("/api/projects", response_model=ProjectOut, status_code=201)
def create_project(project: ProjectCreate):
    """Create a new project."""
    pid = db.create_project(USER_ID, project.name, project.description, project.project_type)
    proj = db.get_project_by_id(pid)
    if not proj:
        raise HTTPException(500, "Failed to create project")
    pid, name, desc, ptype, created, modified = proj
    return ProjectOut(
        id=pid, name=name, description=desc, project_type=ptype or "Full Cell",
        created_date=str(created) if created else None,
        last_modified=str(modified) if modified else None,
    )


@app.get("/api/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int):
    """Get a project by ID."""
    proj = db.get_project_by_id(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    pid, name, desc, ptype, created, modified = proj
    exps = db.get_project_experiments(pid)
    return ProjectOut(
        id=pid, name=name, description=desc, project_type=ptype or "Full Cell",
        created_date=str(created) if created else None,
        last_modified=str(modified) if modified else None,
        experiment_count=len(exps),
    )


@app.put("/api/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, update: ProjectUpdate):
    """Update a project's name, description, or type."""
    proj = db.get_project_by_id(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    
    if update.name is not None:
        db.rename_project(project_id, update.name)
    if update.project_type is not None:
        db.update_project_type(project_id, update.project_type)
    
    # Fetch updated
    return get_project(project_id)


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int):
    """Delete a project and all its experiments."""
    proj = db.get_project_by_id(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    db.delete_project(project_id)


# ─── Experiments ────────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/experiments", response_model=list)
def list_experiments(project_id: int):
    """List all experiments in a project."""
    proj = db.get_project_by_id(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    
    experiments = db.get_project_experiments(project_id)
    result = []
    for exp in experiments:
        exp_id, cname, fname, d_json, cdate = exp
        result.append(ExperimentSummary(
            id=exp_id, cell_name=cname, file_name=fname,
            created_date=str(cdate) if cdate else None,
            has_data=bool(d_json),
        ))
    return result


@app.post("/api/projects/{project_id}/experiments", status_code=201)
def create_experiment(project_id: int, exp: ExperimentCreate):
    """Create a new experiment."""
    proj = db.get_project_by_id(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    
    # Parse date if provided
    exp_date = None
    if exp.experiment_date:
        try:
            exp_date = date.fromisoformat(exp.experiment_date)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
    
    experiment_id = db.save_experiment(
        project_id=project_id,
        experiment_name=exp.experiment_name,
        experiment_date=exp_date,
        disc_diameter_mm=exp.disc_diameter_mm,
        group_assignments=exp.group_assignments or {},
        group_names=exp.group_names or [],
        cells_data=exp.cells_data,
        solids_content=exp.solids_content,
        pressed_thickness=exp.pressed_thickness,
        experiment_notes=exp.experiment_notes,
        cell_format_data=exp.cell_format_data,
    )
    return {"id": experiment_id, "name": exp.experiment_name}


@app.get("/api/experiments/{experiment_id}")
def get_experiment(experiment_id: int):
    """Get full experiment data by ID."""
    exp = db.get_experiment_by_id(experiment_id)
    if not exp:
        raise HTTPException(404, "Experiment not found")
    
    (eid, pid, cname, fname, loading, active, form_cycles, testnum,
     elec, sub, sep, form_json, d_json, solids, pressed, notes, cdate, porosity) = exp
    
    return ExperimentDetail(
        id=eid, project_id=pid, cell_name=cname, file_name=fname,
        loading=loading, active_material=active, formation_cycles=form_cycles,
        test_number=testnum, electrolyte=elec, substrate=sub, separator=sep,
        formulation_json=form_json, data_json=d_json,
        solids_content=solids, pressed_thickness=pressed,
        experiment_notes=notes,
        created_date=str(cdate) if cdate else None,
        porosity=porosity,
    )


@app.put("/api/experiments/{experiment_id}")
def update_experiment(experiment_id: int, exp: ExperimentUpdate):
    """Update an existing experiment."""
    existing = db.get_experiment_by_id(experiment_id)
    if not existing:
        raise HTTPException(404, "Experiment not found")
    
    project_id = existing[1]
    
    exp_date = None
    if exp.experiment_date:
        try:
            exp_date = date.fromisoformat(exp.experiment_date)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
    
    db.update_experiment(
        experiment_id=experiment_id,
        project_id=project_id,
        experiment_name=exp.experiment_name,
        experiment_date=exp_date,
        disc_diameter_mm=exp.disc_diameter_mm,
        group_assignments=exp.group_assignments or {},
        group_names=exp.group_names or [],
        cells_data=exp.cells_data,
        solids_content=exp.solids_content,
        pressed_thickness=exp.pressed_thickness,
        experiment_notes=exp.experiment_notes,
        cell_format_data=exp.cell_format_data,
    )
    return {"status": "updated", "id": experiment_id}


@app.delete("/api/experiments/{experiment_id}", status_code=204)
def delete_experiment(experiment_id: int):
    """Delete an experiment and its data."""
    existing = db.get_experiment_by_id(experiment_id)
    if not existing:
        raise HTTPException(404, "Experiment not found")
    db.delete_cell_experiment(experiment_id)


@app.post("/api/experiments/{experiment_id}/duplicate")
def duplicate_experiment(experiment_id: int):
    """Duplicate an experiment as a new template."""
    try:
        new_id, new_name = db.duplicate_experiment(experiment_id)
        return {"id": new_id, "name": new_name}
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/experiments/{experiment_id}/rename")
def rename_experiment(experiment_id: int, new_name: str = Query(...)):
    """Rename an experiment."""
    existing = db.get_experiment_by_id(experiment_id)
    if not existing:
        raise HTTPException(404, "Experiment not found")
    db.rename_experiment(experiment_id, new_name)
    return {"status": "renamed", "id": experiment_id, "name": new_name}


# ─── Components & Formulations ─────────────────────────────────────────────

@app.get("/api/projects/{project_id}/components")
def get_components(project_id: int):
    """Get all unique formulation components used in a project."""
    return db.get_project_components(project_id)


@app.get("/api/projects/{project_id}/formulation-summary")
def get_formulation_summary(project_id: int):
    """Get statistics on formulation components across a project."""
    return db.get_formulation_summary(project_id)


@app.post("/api/projects/{project_id}/formulation-search")
def search_by_formulation(project_id: int, query: FormulationQuery):
    """Search experiments by formulation component and percentage range."""
    experiments = db.get_experiments_by_formulation_component(
        project_id, query.component_name,
        query.min_percentage, query.max_percentage,
    )
    # Return lightweight summaries
    result = []
    for exp in experiments:
        result.append({
            "id": exp[0], "cell_name": exp[2], "file_name": exp[3],
            "electrolyte": exp[8], "formulation_json": exp[11],
        })
    return result


@app.get("/api/projects/{project_id}/formulation-groups/{component_name}")
def get_formulation_groups(project_id: int, component_name: str):
    """Group experiments by percentage of a specific component."""
    return db.get_experiments_grouped_by_formulation(project_id, component_name)


# ─── Preferences ────────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/preferences")
def get_preferences(project_id: int):
    """Get all preferences for a project."""
    return db.get_project_preferences(project_id)


@app.put("/api/projects/{project_id}/preferences")
def update_preferences(project_id: int, body: PreferencesUpdate):
    """Save preferences for a project."""
    db.save_project_preferences(project_id, body.preferences)
    return {"status": "saved"}


# ─── Master Table ───────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/all-experiments")
def get_all_experiments_data(project_id: int):
    """Get all experiments with full data for master table / analysis."""
    results = db.get_all_project_experiments_data(project_id)
    experiments = []
    for row in results:
        experiments.append({
            "id": row[0], "cell_name": row[1], "file_name": row[2],
            "loading": row[3], "active_material": row[4],
            "formation_cycles": row[5], "test_number": row[6],
            "electrolyte": row[7], "substrate": row[8], "separator": row[9],
            "formulation_json": row[10], "data_json": row[11],
            "created_date": str(row[12]) if row[12] else None,
            "porosity": row[13], "experiment_notes": row[14],
            "cutoff_voltage_lower": row[15], "cutoff_voltage_upper": row[16],
        })
    return experiments
