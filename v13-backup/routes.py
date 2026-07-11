from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.models import ProjectOutput, ProjectRequest
from app.orchestration.project_pipeline import create_project_pipeline
from app.planning.planner import get_recommendations
from app.planning.roadmap import write_content_roadmap
from app.projects.manager import dashboard_stats, get_project, list_projects
from app.publishing.assistant import build_publish_package
from app.publishing.presets import get_channel_preset, load_channel_presets

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {
        "ok": True,
        "version": settings.version,
    }


@router.get("/content-plan")
def content_plan(limit: int = 5, category: str | None = None):
    ideas = get_recommendations(
        limit=limit,
        category=category,
    )
    write_content_roadmap(settings.root, limit=10)
    return {
        "ideas": [idea.model_dump() for idea in ideas],
        "count": len(ideas),
    }


@router.get("/dashboard")
def dashboard():
    projects = list_projects(settings.projects_dir)
    return {
        "projects": projects,
        "stats": dashboard_stats(projects),
    }


@router.get("/dashboard/projects/{project_id}")
def dashboard_project(project_id: str):
    try:
        return get_project(settings.projects_dir, project_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc



@router.get("/publishing/channels")
def publishing_channels():
    return {
        "channels": [
            preset.model_dump()
            for preset in load_channel_presets(settings.root)
        ]
    }


@router.post("/publishing/projects/{project_id}/package")
def create_publish_package(project_id: str, channel_id: str = "mind-frontier"):
    project_dir = (settings.projects_dir / project_id).resolve()

    if settings.projects_dir.resolve() not in project_dir.parents:
        raise HTTPException(status_code=400, detail="Invalid project ID.")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        channel = get_channel_preset(settings.root, channel_id)
        package = build_publish_package(project_dir, channel)
        return package.model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects", response_model=ProjectOutput)
def create_project(request: ProjectRequest):
    try:
        return create_project_pipeline(request)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc
