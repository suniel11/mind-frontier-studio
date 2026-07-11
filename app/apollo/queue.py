from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.orion.planner import build_mission


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _queue_dir(root: Path) -> Path:
    path = root / "studio_memory" / "apollo-queues"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_queue(root: Path, queue: dict[str, Any]) -> Path:
    queue["updated_at"] = _now()
    path = _queue_dir(root) / f"{queue['queue_id']}.json"
    path.write_text(json.dumps(queue, indent=2), encoding="utf-8")
    return path


def load_queue(root: Path, queue_id: str) -> dict[str, Any]:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", queue_id)
    path = _queue_dir(root) / f"{safe}.json"
    if not path.exists():
        raise FileNotFoundError(queue_id)
    return json.loads(path.read_text(encoding="utf-8"))


def list_queues(root: Path, limit: int = 20) -> list[dict[str, Any]]:
    paths = sorted(
        _queue_dir(root).glob("apollo-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    queues = []
    for path in paths[:limit]:
        try:
            queues.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return queues


def create_queue(
    root: Path,
    objective: str,
    count: int,
    target_seconds: int,
) -> dict[str, Any]:
    mission = build_mission(
        root=root,
        objective=objective,
        count=count,
        target_seconds=target_seconds,
    )

    queue_id = f"apollo-{uuid.uuid4().hex[:10]}"
    queue = {
        "queue_id": queue_id,
        "objective": objective,
        "created_at": _now(),
        "updated_at": _now(),
        "status": "planned",
        "target_seconds": target_seconds,
        "items": [
            {
                "title": item["title"],
                "prompt": item["prompt"],
                "category": item["category"],
                "score": item["score"],
                "status": "queued",
                "project_id": None,
                "video_url": None,
                "error": None,
            }
            for item in mission.get("items", [])
        ],
        "completed_count": 0,
        "failed_count": 0,
        "remaining_count": len(mission.get("items", [])),
    }
    save_queue(root, queue)
    return queue


def refresh_counts(queue: dict[str, Any]) -> None:
    items = queue.get("items", [])
    queue["completed_count"] = sum(i.get("status") == "complete" for i in items)
    queue["failed_count"] = sum(i.get("status") == "failed" for i in items)
    queue["remaining_count"] = sum(i.get("status") in {"queued", "running"} for i in items)

    if queue["remaining_count"] == 0:
        queue["status"] = "complete" if queue["failed_count"] == 0 else "partial"
    elif any(i.get("status") == "running" for i in items):
        queue["status"] = "running"
    elif queue.get("status") == "paused":
        queue["status"] = "paused"
    else:
        queue["status"] = "ready"
