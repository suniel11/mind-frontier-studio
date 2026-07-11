from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.atlas.analytics import dashboard_data, evidence_report
from app.atlas.database import migrate
from app.atlas.metrics import record_youtube_metrics
from app.atlas.models import ProjectStatusUpdate, YouTubeMetricInput
from app.atlas.registry import sync_project_library
from app.core.settings import settings

router = APIRouter(prefix="/atlas", tags=["Atlas"])


@router.get("/dashboard")
def atlas_dashboard():
    sync_project_library(settings.root, settings.version)
    return dashboard_data(settings.root)


@router.get("/recommendations")
def atlas_recommendations():
    sync_project_library(settings.root, settings.version)
    return evidence_report(settings.root)


@router.post("/sync")
def atlas_sync():
    count = sync_project_library(settings.root, settings.version)
    return {"synced_projects": count}


@router.post("/youtube-metrics")
def atlas_youtube_metrics(payload: YouTubeMetricInput):
    sync_project_library(settings.root, settings.version)
    try:
        record_id = record_youtube_metrics(settings.root, payload)
        return {"ok": True, "record_id": record_id}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found.")


@router.patch("/projects/{project_id}/status")
def atlas_project_status(project_id: str, payload: ProjectStatusUpdate):
    migrate(settings.root)
    from app.atlas.database import connect
    from datetime import datetime, timezone

    with connect(settings.root) as db:
        cursor = db.execute(
            """
            UPDATE projects
            SET status = ?, updated_at = ?
            WHERE project_id = ?
            """,
            (
                payload.status,
                datetime.now(timezone.utc).isoformat(),
                project_id,
            ),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Project not found.")

    return {"ok": True, "project_id": project_id, "status": payload.status}
