from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.stability.backup import create_backup, prune_backups
from app.stability.config import configuration_report
from app.stability.jobs import get_job, list_jobs
from app.stability.migrations import migrate, migration_status

router = APIRouter(prefix="/stability", tags=["Stability"])


@router.get("/status")
def stability_status():
    return {
        "version": getattr(settings, "version", "21.5.0"),
        "migrations": migration_status(settings.root),
        "configuration": configuration_report(settings.root),
        "jobs": list_jobs(settings.root, 10),
    }


@router.post("/migrate")
def stability_migrate():
    return migrate(settings.root)


@router.get("/jobs")
def stability_jobs(limit: int = 25):
    return {"jobs": list_jobs(settings.root, limit)}


@router.get("/jobs/{job_id}")
def stability_job(job_id: str):
    job = get_job(settings.root, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.post("/backup")
def stability_backup():
    return create_backup(settings.root, notes="Manual v21.5 backup")


@router.post("/backup/prune")
def stability_backup_prune(keep: int = 10):
    return prune_backups(settings.root, keep)
