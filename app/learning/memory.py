from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def record_project(
    root: Path,
    project_id: str,
    topic: str,
    producer_review,
    quality_report,
    storyboard,
) -> Path:
    memory_dir = root / "studio_memory"
    memory_dir.mkdir(exist_ok=True)
    path = memory_dir / "production-history.jsonl"

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_id": project_id,
        "topic": topic,
        "producer_review": producer_review.model_dump(),
        "quality_report": quality_report.model_dump(),
        "story_arc_summary": getattr(storyboard, "story_arc_summary", ""),
        "scene_roles": [
            getattr(scene, "story_role", "")
            for scene in getattr(storyboard, "scenes", [])
        ],
        "motion_types": [
            getattr(scene, "motion_type", "")
            for scene in getattr(storyboard, "scenes", [])
        ],
        "visual_types": [
            getattr(scene, "visual_type", "")
            for scene in getattr(storyboard, "scenes", [])
        ],
        "shot_types": [
            getattr(scene, "shot_type", "")
            for scene in getattr(storyboard, "scenes", [])
        ],
    }

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
