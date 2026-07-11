from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.operations.health import system_health

router = APIRouter(prefix="/operations", tags=["Operations"])


@router.get("/health")
def operations_health():
    return system_health(settings.root)


@router.get("/recent-failures")
def recent_failures(limit: int = 10):
    logs_dir = settings.root / "studio_memory" / "logs"
    if not logs_dir.exists():
        return {"failures": []}

    failures = []
    paths = sorted(
        logs_dir.glob("*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("status") == "failed":
                failures.append(event)
                if len(failures) >= limit:
                    return {"failures": failures}

    return {"failures": failures}


@router.get("/pipeline-report/{project_id}")
def pipeline_report(project_id: str):
    safe_id = "".join(
        character for character in project_id
        if character.isalnum() or character in "-_"
    )

    project_report = (
        settings.projects_dir / safe_id / "pipeline-report.json"
    )
    fallback_report = (
        settings.root / "studio_memory" / "logs" / f"{safe_id}-report.json"
    )

    path = project_report if project_report.exists() else fallback_report
    if not path.exists():
        raise HTTPException(status_code=404, detail="Pipeline report not found.")

    return json.loads(path.read_text(encoding="utf-8"))
