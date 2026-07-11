from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _duration_from_project(project: dict[str, Any]) -> float:
    script = project.get("script", {})
    if isinstance(script, dict):
        return float(script.get("estimated_seconds", 0) or 0)

    storyboard = project.get("storyboard", {})
    if isinstance(storyboard, dict):
        scenes = storyboard.get("scenes", [])
        if scenes:
            return float(max(scene.get("end_second", 0) for scene in scenes))

    return 0.0


def _category_from_text(title: str, topic: str) -> str:
    value = f"{title} {topic}".lower()
    psychology = (
        "comparison", "overthinking", "identity", "validation", "fear",
        "loneliness", "confidence", "anxiety", "psychology", "attention",
        "people pleasing", "self worth",
    )
    philosophy = (
        "stoic", "meaning", "purpose", "control", "freedom", "suffering",
        "happiness", "mediocrity", "philosophy", "mortality",
    )
    history = ("history", "ancient", "india", "empire", "civilization")

    if any(term in value for term in psychology):
        return "psychology"
    if any(term in value for term in philosophy):
        return "philosophy"
    if any(term in value for term in history):
        return "history"
    return "general"


def project_snapshot(project_dir: Path, engine_version: str = "") -> dict[str, Any]:
    project = _read_json(project_dir / "project.json")
    quality = _read_json(project_dir / "quality-report.json")
    cinema = _read_json(project_dir / "cinema-report.json")
    release = _read_json(project_dir / "release-package.json")
    manifest = _read_json(project_dir / "release-manifest.json")

    script = project.get("script", {}) if isinstance(project.get("script"), dict) else {}
    seo = project.get("seo", {}) if isinstance(project.get("seo"), dict) else {}

    title = str(
        release.get("title")
        or seo.get("title")
        or script.get("title")
        or project_dir.name.replace("-", " ").title()
    )
    topic = str(project.get("topic", ""))
    status = str(manifest.get("status", "")).replace("_for_review", "")
    if not status:
        status = "ready" if (project_dir / "mind-frontier-short.mp4").exists() else "draft"

    created_at = str(
        project.get("created_at")
        or project.get("created")
        or datetime.fromtimestamp(
            project_dir.stat().st_ctime, timezone.utc
        ).isoformat()
    )

    return {
        "project_id": project_dir.name,
        "title": title,
        "topic": topic,
        "category": _category_from_text(title, topic),
        "status": status,
        "created_at": created_at,
        "updated_at": _now(),
        "duration_seconds": _duration_from_project(project),
        "quality_score": float(quality.get("overall_score", 0) or 0),
        "cinema_score": float(cinema.get("cinema_score", 0) or 0),
        "producer_score": float(
            release.get("producer_score")
            or project.get("producer_score")
            or 0
        ),
        "video_path": str(project_dir / "mind-frontier-short.mp4"),
        "thumbnail_path": str(project_dir / "thumbnail.jpg"),
        "publish_ready": 1 if quality.get("publish_ready", False) else 0,
        "engine_version": str(manifest.get("version") or engine_version),
        "source_modified_at": project_dir.stat().st_mtime,
    }


def upsert_project(root: Path, project_dir: Path, engine_version: str = "") -> dict[str, Any]:
    migrate(root)
    snapshot = project_snapshot(project_dir, engine_version)

    with connect(root) as db:
        db.execute(
            """
            INSERT INTO projects (
                project_id, title, topic, category, status, created_at,
                updated_at, duration_seconds, quality_score, cinema_score,
                producer_score, video_path, thumbnail_path, publish_ready,
                engine_version, source_modified_at
            )
            VALUES (
                :project_id, :title, :topic, :category, :status, :created_at,
                :updated_at, :duration_seconds, :quality_score, :cinema_score,
                :producer_score, :video_path, :thumbnail_path, :publish_ready,
                :engine_version, :source_modified_at
            )
            ON CONFLICT(project_id) DO UPDATE SET
                title = excluded.title,
                topic = excluded.topic,
                category = excluded.category,
                status = excluded.status,
                updated_at = excluded.updated_at,
                duration_seconds = excluded.duration_seconds,
                quality_score = excluded.quality_score,
                cinema_score = excluded.cinema_score,
                producer_score = excluded.producer_score,
                video_path = excluded.video_path,
                thumbnail_path = excluded.thumbnail_path,
                publish_ready = excluded.publish_ready,
                engine_version = excluded.engine_version,
                source_modified_at = excluded.source_modified_at
            """,
            snapshot,
        )

    return snapshot


def sync_project_library(root: Path, engine_version: str = "") -> int:
    projects_dir = root / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir() and (project_dir / "project.json").exists():
            upsert_project(root, project_dir, engine_version)
            count += 1
    return count
