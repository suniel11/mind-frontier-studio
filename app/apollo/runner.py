from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models import ProjectRequest
from app.orchestration.project_pipeline import create_project_pipeline
from app.apollo.queue import load_queue, refresh_counts, save_queue


def run_next(root: Path, queue_id: str) -> dict[str, Any]:
    queue = load_queue(root, queue_id)

    if queue.get("status") == "paused":
        return queue

    item = next(
        (entry for entry in queue.get("items", []) if entry.get("status") == "queued"),
        None,
    )
    if item is None:
        refresh_counts(queue)
        save_queue(root, queue)
        return queue

    item["status"] = "running"
    item["error"] = None
    queue["status"] = "running"
    save_queue(root, queue)

    try:
        output = create_project_pipeline(
            ProjectRequest(
                topic=item["prompt"],
                target_seconds=int(queue.get("target_seconds", 45)),
            )
        )
        item["status"] = "complete"
        item["project_id"] = output.project_id
        item["video_url"] = output.video_url
    except Exception as exc:
        item["status"] = "failed"
        item["error"] = str(exc)

    refresh_counts(queue)
    save_queue(root, queue)
    return queue


def run_batch(root: Path, queue_id: str, max_items: int = 1) -> dict[str, Any]:
    queue = load_queue(root, queue_id)

    for _ in range(max_items):
        if queue.get("status") == "paused":
            break
        pending = any(
            item.get("status") == "queued"
            for item in queue.get("items", [])
        )
        if not pending:
            break
        queue = run_next(root, queue_id)

    return queue


def set_paused(root: Path, queue_id: str, paused: bool) -> dict[str, Any]:
    queue = load_queue(root, queue_id)
    queue["status"] = "paused" if paused else "ready"
    refresh_counts(queue)
    save_queue(root, queue)
    return queue
