from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models import ProjectRequest
from app.orchestration.project_pipeline import create_project_pipeline
from app.orion.planner import load_mission, save_mission


def execute_mission_item(
    root: Path,
    mission_id: str,
    item_index: int,
) -> dict[str, Any]:
    mission = load_mission(root, mission_id)
    items = mission.get("items", [])

    if item_index >= len(items):
        raise IndexError(item_index)

    item = items[item_index]
    if item.get("status") == "complete":
        return mission

    item["status"] = "running"
    item["error"] = None
    mission["status"] = "running"
    save_mission(root, mission)

    try:
        output = create_project_pipeline(
            ProjectRequest(
                topic=item["prompt"],
                target_seconds=int(item.get("target_seconds", 45)),
            )
        )
        item["status"] = "complete"
        item["project_id"] = output.project_id
        item["video_url"] = output.video_url
    except Exception as exc:
        item["status"] = "failed"
        item["error"] = str(exc)
        mission["status"] = "failed"
        save_mission(root, mission)
        raise

    statuses = {entry.get("status") for entry in items}
    if statuses == {"complete"}:
        mission["status"] = "complete"
    elif "failed" in statuses:
        mission["status"] = "partial"
    else:
        mission["status"] = "running"

    save_mission(root, mission)
    return mission
