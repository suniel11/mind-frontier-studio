from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _project_created_at(folder: Path) -> str:
    project_json = _read_json(folder / "project.json")
    for key in ("created_at", "created", "timestamp"):
        value = project_json.get(key)
        if value:
            return str(value)

    return datetime.fromtimestamp(folder.stat().st_mtime).isoformat()


def _title_from_project(folder: Path) -> str:
    project = _read_json(folder / "project.json")
    release = _read_json(folder / "release-package.json")

    script = project.get("script", {}) if isinstance(project.get("script"), dict) else {}
    seo = project.get("seo", {}) if isinstance(project.get("seo"), dict) else {}

    return (
        release.get("title")
        or seo.get("title")
        or script.get("title")
        or project.get("title")
        or folder.name.replace("-", " ").replace("_", " ").title()
    )


def _topic_from_project(folder: Path) -> str:
    project = _read_json(folder / "project.json")
    return str(project.get("topic") or project.get("request", {}).get("topic") or "")


def _quality(folder: Path) -> dict[str, Any]:
    return _read_json(folder / "quality-report.json")


def _status(folder: Path) -> str:
    upload = _read_json(folder / "youtube-upload.json")
    manifest = _read_json(folder / "release-manifest.json")

    if upload.get("video_id"):
        return "published"
    if manifest.get("status"):
        return str(manifest["status"]).replace("_for_review", "")
    if (folder / "mind-frontier-short.mp4").exists():
        return "ready"
    return "draft"


def summarize_project(folder: Path) -> dict[str, Any]:
    quality = _quality(folder)
    video = folder / "mind-frontier-short.mp4"
    thumbnail = folder / "thumbnail.jpg"

    return {
        "id": folder.name,
        "title": _title_from_project(folder),
        "topic": _topic_from_project(folder),
        "status": _status(folder),
        "created_at": _project_created_at(folder),
        "quality_score": int(quality.get("overall_score", 0) or 0),
        "publish_ready": bool(quality.get("publish_ready", False)),
        "video_url": f"/projects/{folder.name}/mind-frontier-short.mp4" if video.exists() else None,
        "thumbnail_url": f"/projects/{folder.name}/thumbnail.jpg" if thumbnail.exists() else None,
        "has_metadata": (folder / "release-package.json").exists(),
        "has_beat_map": (folder / "narrative-beat-map.json").exists(),
        "has_quality_report": (folder / "quality-report.json").exists(),
    }


def list_projects(projects_root: Path) -> list[dict[str, Any]]:
    projects_root.mkdir(parents=True, exist_ok=True)
    projects = [
        summarize_project(folder)
        for folder in projects_root.iterdir()
        if folder.is_dir()
    ]
    return sorted(projects, key=lambda item: item["created_at"], reverse=True)


def get_project(projects_root: Path, project_id: str) -> dict[str, Any]:
    folder = (projects_root / project_id).resolve()
    root = projects_root.resolve()

    if root not in folder.parents:
        raise ValueError("Invalid project ID.")
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(project_id)

    summary = summarize_project(folder)
    summary["project"] = _read_json(folder / "project.json")
    summary["quality_report"] = _read_json(folder / "quality-report.json")
    summary["release_package"] = _read_json(folder / "release-package.json")
    summary["beat_map"] = _read_json(folder / "narrative-beat-map.json")
    summary["render_graph"] = _read_json(folder / "render-graph.json")
    return summary


def dashboard_stats(projects: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [item["quality_score"] for item in projects if item["quality_score"] > 0]

    return {
        "total_projects": len(projects),
        "ready_projects": sum(item["status"] == "ready" for item in projects),
        "published_projects": sum(item["status"] == "published" for item in projects),
        "average_quality": round(sum(scores) / len(scores), 1) if scores else 0,
    }
