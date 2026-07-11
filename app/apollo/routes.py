from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.apollo.models import ApolloQueueRequest, ApolloRunRequest
from app.apollo.queue import create_queue, list_queues, load_queue
from app.apollo.runner import run_batch, set_paused
from app.core.settings import settings

router = APIRouter(prefix="/apollo", tags=["Apollo"])


@router.post("/queues")
def create_apollo_queue(payload: ApolloQueueRequest):
    return create_queue(
        settings.root,
        payload.objective,
        payload.count,
        payload.target_seconds,
    )


@router.get("/queues")
def apollo_queues():
    return {"queues": list_queues(settings.root)}


@router.get("/queues/{queue_id}")
def apollo_queue(queue_id: str):
    try:
        return load_queue(settings.root, queue_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Queue not found.")


@router.post("/queues/{queue_id}/run")
def run_apollo_queue(queue_id: str, payload: ApolloRunRequest):
    try:
        return run_batch(settings.root, queue_id, payload.max_items)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Queue not found.")


@router.post("/queues/{queue_id}/pause")
def pause_apollo_queue(queue_id: str):
    try:
        return set_paused(settings.root, queue_id, True)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Queue not found.")


@router.post("/queues/{queue_id}/resume")
def resume_apollo_queue(queue_id: str):
    try:
        return set_paused(settings.root, queue_id, False)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Queue not found.")
