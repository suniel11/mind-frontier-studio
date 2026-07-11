from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate
from app.atlas.registry import sync_project_library
from app.youtube_sync.video_store import ensure_video_table


def _normalize(value: str) -> str:
    value = re.sub(r"[^a-z0-9 ]", " ", value.lower())
    return " ".join(value.split())


def _token_set(value: str) -> set[str]:
    stopwords = {
        "the", "and", "that", "this", "with", "from", "your", "about",
        "into", "why", "how", "what", "when", "where", "short", "video",
    }
    return {
        token for token in _normalize(value).split()
        if len(token) >= 3 and token not in stopwords
    }


def _similarity(project: dict[str, Any], video: dict[str, Any]) -> tuple[int, list[str]]:
    project_title = str(project.get("title", ""))
    project_topic = str(project.get("topic", ""))
    video_title = str(video.get("title", ""))
    video_description = str(video.get("description", ""))

    reasons: list[str] = []
    title_ratio = SequenceMatcher(
        None,
        _normalize(project_title),
        _normalize(video_title),
    ).ratio()

    project_tokens = _token_set(f"{project_title} {project_topic}")
    video_tokens = _token_set(f"{video_title} {video_description}")
    union = project_tokens | video_tokens
    overlap = len(project_tokens & video_tokens) / len(union) if union else 0.0

    score = round(title_ratio * 65 + overlap * 35)

    if title_ratio >= 0.88:
        reasons.append("Titles are nearly identical.")
    elif title_ratio >= 0.72:
        reasons.append("Titles are strongly similar.")

    if overlap >= 0.45:
        reasons.append("Topic keywords overlap strongly.")
    elif overlap >= 0.25:
        reasons.append("Topic keywords partially overlap.")

    return score, reasons


def _project_rows(root: Path) -> list[dict[str, Any]]:
    sync_project_library(root)
    migrate(root)

    with connect(root) as db:
        rows = db.execute(
            """
            SELECT
                project_id,
                title,
                topic,
                status,
                created_at,
                quality_score,
                cinema_score,
                producer_score
            FROM projects
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def _video_rows(root: Path) -> list[dict[str, Any]]:
    ensure_video_table(root)

    with connect(root) as db:
        rows = db.execute(
            """
            SELECT
                video_id,
                channel_id,
                title,
                description,
                published_at,
                views,
                likes,
                comments,
                is_short,
                atlas_project_id
            FROM youtube_videos
            ORDER BY published_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def suggest_matches(
    root: Path,
    minimum_score: int = 55,
) -> list[dict[str, Any]]:
    projects = _project_rows(root)
    videos = _video_rows(root)
    suggestions: list[dict[str, Any]] = []

    for video in videos:
        if video.get("atlas_project_id"):
            continue

        best: dict[str, Any] | None = None

        for project in projects:
            score, reasons = _similarity(project, video)

            if best is None or score > best["score"]:
                best = {
                    "video_id": video["video_id"],
                    "video_title": video["title"],
                    "published_at": video.get("published_at"),
                    "views": video.get("views", 0),
                    "project_id": project["project_id"],
                    "project_title": project["title"],
                    "project_topic": project.get("topic", ""),
                    "score": score,
                    "reasons": reasons,
                }

        if best and best["score"] >= minimum_score:
            best["confidence"] = (
                "high"
                if best["score"] >= 85
                else "medium"
                if best["score"] >= 70
                else "low"
            )
            suggestions.append(best)

    suggestions.sort(key=lambda item: item["score"], reverse=True)
    return suggestions


def apply_match(
    root: Path,
    video_id: str,
    project_id: str,
    source: str = "manual",
) -> dict[str, Any]:
    ensure_video_table(root)
    migrate(root)

    with connect(root) as db:
        project = db.execute(
            "SELECT project_id, title FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if project is None:
            raise FileNotFoundError(f"Project not found: {project_id}")

        video = db.execute(
            "SELECT video_id, title FROM youtube_videos WHERE video_id = ?",
            (video_id,),
        ).fetchone()
        if video is None:
            raise FileNotFoundError(f"YouTube video not found: {video_id}")

        db.execute(
            """
            UPDATE youtube_videos
            SET atlas_project_id = ?
            WHERE video_id = ?
            """,
            (project_id, video_id),
        )
        db.execute(
            """
            UPDATE projects
            SET status = 'published',
                updated_at = datetime('now')
            WHERE project_id = ?
            """,
            (project_id,),
        )
        db.execute(
            """
            INSERT INTO production_events (
                project_id,
                event_type,
                occurred_at,
                payload_json
            )
            VALUES (?, 'youtube_match', datetime('now'), ?)
            """,
            (
                project_id,
                json.dumps(
                    {
                        "video_id": video_id,
                        "source": source,
                    }
                ),
            ),
        )

    return {
        "ok": True,
        "video_id": video_id,
        "project_id": project_id,
        "source": source,
    }


def remove_match(root: Path, video_id: str) -> dict[str, Any]:
    ensure_video_table(root)

    with connect(root) as db:
        row = db.execute(
            """
            SELECT atlas_project_id
            FROM youtube_videos
            WHERE video_id = ?
            """,
            (video_id,),
        ).fetchone()

        if row is None:
            raise FileNotFoundError(f"YouTube video not found: {video_id}")

        project_id = row["atlas_project_id"]
        db.execute(
            """
            UPDATE youtube_videos
            SET atlas_project_id = NULL
            WHERE video_id = ?
            """,
            (video_id,),
        )

    return {
        "ok": True,
        "video_id": video_id,
        "project_id": project_id,
    }


def auto_match(
    root: Path,
    threshold: int = 85,
) -> dict[str, Any]:
    suggestions = suggest_matches(root, minimum_score=threshold)
    matched = []

    used_projects: set[str] = set()
    for suggestion in suggestions:
        project_id = suggestion["project_id"]
        if project_id in used_projects:
            continue

        apply_match(
            root,
            suggestion["video_id"],
            project_id,
            source="automatic",
        )
        matched.append(suggestion)
        used_projects.add(project_id)

    return {
        "matched_count": len(matched),
        "threshold": threshold,
        "matches": matched,
    }


def matching_summary(root: Path) -> dict[str, Any]:
    ensure_video_table(root)
    migrate(root)

    with connect(root) as db:
        videos = dict(
            db.execute(
                """
                SELECT
                    COUNT(*) AS total_videos,
                    SUM(CASE WHEN atlas_project_id IS NOT NULL THEN 1 ELSE 0 END)
                        AS matched_videos,
                    SUM(CASE WHEN atlas_project_id IS NULL THEN 1 ELSE 0 END)
                        AS unmatched_videos
                FROM youtube_videos
                """
            ).fetchone()
        )
        projects = dict(
            db.execute(
                """
                SELECT
                    COUNT(*) AS total_projects,
                    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END)
                        AS published_projects
                FROM projects
                """
            ).fetchone()
        )

    return {**videos, **projects}
