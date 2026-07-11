from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.orchestrator.engine import build_autonomous_project
from app.orchestrator.models import (
    OrchestratorFinalizeRequest,
    OrchestratorRequest,
)
from app.orchestrator.store import (
    complete_project,
    get_project,
    list_projects,
)

router = APIRouter(prefix="/orchestrator", tags=["Autonomous Orchestrator"])


@router.post("/create-project")
def orchestrator_create_project(payload: OrchestratorRequest):
    return build_autonomous_project(
        settings.root,
        payload.topic,
        payload.target_seconds,
        payload.hook_type,
        payload.save_workspace,
    )


@router.get("/projects")
def orchestrator_projects(limit: int = 50):
    return {"projects": list_projects(settings.root, limit)}


@router.get("/project/{project_id}")
def orchestrator_project(project_id: str):
    project = get_project(settings.root, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.post("/regenerate/{project_id}")
def orchestrator_regenerate(project_id: str):
    project = get_project(settings.root, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    return build_autonomous_project(
        settings.root,
        project["topic"],
        int(project["target_seconds"]),
        project["hook_type"],
        True,
    )


@router.post("/finalize")
def orchestrator_finalize(payload: OrchestratorFinalizeRequest):
    project = get_project(settings.root, payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    complete_project(
        settings.root,
        payload.project_id,
        status="finalized",
        confidence=float(project["confidence"]),
        readiness_score=int(project["readiness_score"]),
        workspace_id=project.get("workspace_id"),
        plan=project["plan"],
        notes=payload.notes,
    )

    return {
        "ok": True,
        "project_id": payload.project_id,
        "status": "finalized",
    }
