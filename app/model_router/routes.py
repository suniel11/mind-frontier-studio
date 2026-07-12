from __future__ import annotations

from fastapi import APIRouter

from app.model_router.status import get_model_routing_status

router = APIRouter(prefix="/model-routing", tags=["model-routing"])


@router.get("/status")
def model_routing_status(project_id: str | None = None) -> dict:
    return get_model_routing_status(project_id=project_id)
