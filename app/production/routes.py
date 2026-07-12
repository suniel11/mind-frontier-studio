from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.core.settings import settings
from app.production.jobs import (
    ProductionJobConflict,
    ProductionJobNotFound,
    get_production_job_runner,
)
from app.production.models import (
    ProductionJobCreated,
    ProductionJobRequest,
    ProductionJobStatus,
)

router = APIRouter(prefix="/production", tags=["Production"])


def _runner():
    return get_production_job_runner(settings.root)


@router.post(
    "/jobs",
    response_model=ProductionJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_production_job(request: ProductionJobRequest, response: Response):
    try:
        created = _runner().create(request.resolved_specification())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response.headers["Location"] = f"/api/production/jobs/{created.job_id}"
    return created


@router.get("/jobs/{job_id}", response_model=ProductionJobStatus)
def get_production_job(job_id: str):
    try:
        return _runner().get(job_id)
    except ProductionJobNotFound as exc:
        raise HTTPException(status_code=404, detail="Production job not found.") from exc


@router.post("/jobs/{job_id}/cancel", response_model=ProductionJobStatus)
def cancel_production_job(job_id: str):
    try:
        return _runner().cancel(job_id)
    except ProductionJobNotFound as exc:
        raise HTTPException(status_code=404, detail="Production job not found.") from exc
    except ProductionJobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/retry", response_model=ProductionJobStatus)
def retry_production_job(job_id: str):
    try:
        return _runner().retry(job_id)
    except ProductionJobNotFound as exc:
        raise HTTPException(status_code=404, detail="Production job not found.") from exc
    except ProductionJobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/projects/{project_id}/job", response_model=ProductionJobStatus)
def get_project_production_job(project_id: str):
    job = _runner().store.job_for_project(project_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Production job not found.")
    return job
