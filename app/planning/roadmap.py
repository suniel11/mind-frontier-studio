from __future__ import annotations

import json
from pathlib import Path

from app.planning.planner import get_recommendations


def write_content_roadmap(root: Path, limit: int = 10) -> Path:
    roadmap_dir = root / "studio_memory"
    roadmap_dir.mkdir(exist_ok=True)
    path = roadmap_dir / "content-roadmap.json"

    ideas = get_recommendations(limit=limit)
    payload = {
        "strategy": "Psychology and philosophy first; expand into history and science after channel identity is established.",
        "recommended_order": [
            {"position": index, **idea.model_dump()}
            for index, idea in enumerate(ideas, start=1)
        ],
    }

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
