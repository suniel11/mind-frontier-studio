from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.orion.executor import execute_mission_item
from app.orion.models import OrionExecuteRequest, OrionPlanRequest
from app.orion.planner import build_mission, list_missions, load_mission

router = APIRouter(prefix="/orion", tags=["Orion"])


@router.post("/plan")
def plan_orion_mission(payload: OrionPlanRequest):
    return build_mission(
        root=settings.root,
        objective=payload.objective,
        count=payload.count,
        target_seconds=payload.target_seconds,
    )


@router.get("/missions")
def orion_missions():
    return {"missions": list_missions(settings.root)}


@router.get("/missions/{mission_id}")
def orion_mission(mission_id: str):
    try:
        return load_mission(settings.root, mission_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Mission not found.")


@router.post("/missions/{mission_id}/execute")
def execute_orion_mission_item(
    mission_id: str,
    payload: OrionExecuteRequest,
):
    try:
        return execute_mission_item(
            settings.root,
            mission_id,
            payload.item_index,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Mission not found.")
    except IndexError:
        raise HTTPException(status_code=400, detail="Invalid mission item.")
