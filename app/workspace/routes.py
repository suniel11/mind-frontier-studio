from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.workspace.models import WorkspaceRequest, WorkspaceSaveRequest
from app.workspace.orchestrator import build_workspace_brief
from app.workspace.store import (
    get_workspace,
    list_workspaces,
    save_workspace,
)

router = APIRouter(prefix="/workspace", tags=["Producer Workspace"])


@router.post("/build")
def workspace_build(payload: WorkspaceRequest):
    return build_workspace_brief(
        settings.root,
        payload.topic,
        payload.target_seconds,
        payload.hook_type,
    )


@router.post("/save")
def workspace_save(payload: WorkspaceSaveRequest):
    brief = build_workspace_brief(
        settings.root,
        payload.topic,
        payload.target_seconds,
        payload.hook_type,
    )
    return save_workspace(
        settings.root,
        payload.topic,
        payload.target_seconds,
        payload.hook_type,
        payload.notes,
        brief,
    )


@router.get("/list")
def workspace_list(limit: int = 50):
    return {"workspaces": list_workspaces(settings.root, limit)}


@router.get("/{workspace_id}")
def workspace_detail(workspace_id: str):
    workspace = get_workspace(settings.root, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return workspace
