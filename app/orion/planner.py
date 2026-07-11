from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.atlas.analytics import evidence_report
from app.planning.planner import get_recommendations
from app.producer_ai.reviewer import assess_topic


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mission_dir(root: Path) -> Path:
    path = root / "studio_memory" / "orion-missions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _keywords(value: str) -> set[str]:
    return {
        word for word in re.sub(r"[^a-z0-9 ]", " ", value.lower()).split()
        if len(word) >= 4
    }


def _objective_bonus(objective: str, title: str, prompt: str) -> int:
    target = _keywords(objective)
    candidate = _keywords(f"{title} {prompt}")
    if not target or not candidate:
        return 0
    overlap = len(target & candidate) / max(1, len(target))
    return min(18, round(overlap * 22))


def build_mission(
    root: Path,
    objective: str,
    count: int,
    target_seconds: int,
) -> dict[str, Any]:
    evidence = evidence_report(root)
    ideas = get_recommendations(limit=10)

    candidates: list[dict[str, Any]] = []
    for idea in ideas:
        assessment = assess_topic(root, idea.prompt)
        score = round(
            idea.overall_score * 0.45
            + assessment.overall_score * 0.45
            + _objective_bonus(objective, idea.title, idea.prompt)
        )
        score = min(100, score)

        candidates.append(
            {
                "title": idea.title,
                "prompt": idea.prompt,
                "category": idea.category,
                "score": score,
                "verdict": assessment.verdict,
                "reasons": assessment.reasons[:3],
                "suggested_angle": assessment.suggested_angle,
                "target_seconds": target_seconds,
                "status": "planned",
                "project_id": None,
                "error": None,
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    selected = [
        item for item in candidates
        if item["score"] >= 65
    ][:count]

    mission_id = f"orion-{uuid.uuid4().hex[:10]}"
    mission = {
        "mission_id": mission_id,
        "objective": objective,
        "created_at": _now(),
        "updated_at": _now(),
        "status": "planned",
        "target_seconds": target_seconds,
        "items": selected,
        "atlas_recommendations": evidence.get("recommendations", []),
        "published_sample_size": evidence.get("sample_size", 0),
    }

    save_mission(root, mission)
    return mission


def save_mission(root: Path, mission: dict[str, Any]) -> Path:
    mission["updated_at"] = _now()
    path = _mission_dir(root) / f"{mission['mission_id']}.json"
    path.write_text(json.dumps(mission, indent=2), encoding="utf-8")
    return path


def load_mission(root: Path, mission_id: str) -> dict[str, Any]:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", mission_id)
    path = _mission_dir(root) / f"{safe_id}.json"
    if not path.exists():
        raise FileNotFoundError(mission_id)
    return json.loads(path.read_text(encoding="utf-8"))


def list_missions(root: Path, limit: int = 20) -> list[dict[str, Any]]:
    paths = sorted(
        _mission_dir(root).glob("orion-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    missions = []
    for path in paths[:limit]:
        try:
            missions.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return missions
