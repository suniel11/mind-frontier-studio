from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate


def ensure_video_table(root: Path) -> None:
    migrate(root)
    with connect(root) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_videos (
                video_id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                thumbnail_url TEXT,
                published_at TEXT,
                duration_seconds INTEGER NOT NULL DEFAULT 0,
                privacy_status TEXT NOT NULL DEFAULT '',
                category_id TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                views INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                is_short INTEGER NOT NULL DEFAULT 0,
                last_synced_at TEXT NOT NULL,
                atlas_project_id TEXT
            )
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_youtube_videos_channel
            ON youtube_videos(channel_id, published_at DESC)
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_youtube_videos_views
            ON youtube_videos(views DESC)
            """
        )


def upsert_videos(root: Path, videos: list[dict[str, Any]]) -> int:
    ensure_video_table(root)

    with connect(root) as db:
        for video in videos:
            db.execute(
                """
                INSERT INTO youtube_videos (
                    video_id,
                    channel_id,
                    title,
                    description,
                    thumbnail_url,
                    published_at,
                    duration_seconds,
                    privacy_status,
                    category_id,
                    tags_json,
                    views,
                    likes,
                    comments,
                    is_short,
                    last_synced_at,
                    atlas_project_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    channel_id = excluded.channel_id,
                    title = excluded.title,
                    description = excluded.description,
                    thumbnail_url = excluded.thumbnail_url,
                    published_at = excluded.published_at,
                    duration_seconds = excluded.duration_seconds,
                    privacy_status = excluded.privacy_status,
                    category_id = excluded.category_id,
                    tags_json = excluded.tags_json,
                    views = excluded.views,
                    likes = excluded.likes,
                    comments = excluded.comments,
                    is_short = excluded.is_short,
                    last_synced_at = excluded.last_synced_at
                """,
                (
                    video["video_id"],
                    video["channel_id"],
                    video["title"],
                    video.get("description", ""),
                    video.get("thumbnail_url"),
                    video.get("published_at"),
                    int(video.get("duration_seconds", 0)),
                    video.get("privacy_status", ""),
                    video.get("category_id", ""),
                    json.dumps(video.get("tags", []), ensure_ascii=False),
                    int(video.get("views", 0)),
                    int(video.get("likes", 0)),
                    int(video.get("comments", 0)),
                    1 if video.get("is_short") else 0,
                    video["last_synced_at"],
                    video.get("atlas_project_id"),
                ),
            )

    return len(videos)


def list_videos(
    root: Path,
    limit: int = 100,
    offset: int = 0,
    search: str = "",
    short_only: bool | None = None,
) -> list[dict[str, Any]]:
    ensure_video_table(root)

    clauses = []
    params: list[Any] = []

    if search.strip():
        clauses.append("LOWER(title) LIKE ?")
        params.append(f"%{search.strip().lower()}%")

    if short_only is not None:
        clauses.append("is_short = ?")
        params.append(1 if short_only else 0)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([max(1, min(limit, 500)), max(0, offset)])

    with connect(root) as db:
        rows = db.execute(
            f"""
            SELECT
                video_id,
                channel_id,
                title,
                description,
                thumbnail_url,
                published_at,
                duration_seconds,
                privacy_status,
                category_id,
                tags_json,
                views,
                likes,
                comments,
                is_short,
                last_synced_at,
                atlas_project_id
            FROM youtube_videos
            {where}
            ORDER BY published_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        ).fetchall()

    videos = []
    for row in rows:
        item = dict(row)
        item["tags"] = json.loads(item.pop("tags_json") or "[]")
        item["is_short"] = bool(item["is_short"])
        item["url"] = f"https://www.youtube.com/watch?v={item['video_id']}"
        videos.append(item)

    return videos


def video_summary(root: Path) -> dict[str, Any]:
    ensure_video_table(root)

    with connect(root) as db:
        row = db.execute(
            """
            SELECT
                COUNT(*) AS total_videos,
                SUM(CASE WHEN is_short = 1 THEN 1 ELSE 0 END) AS shorts,
                SUM(CASE WHEN is_short = 0 THEN 1 ELSE 0 END) AS long_form,
                COALESCE(SUM(views), 0) AS total_views,
                ROUND(AVG(views), 1) AS average_views,
                MAX(last_synced_at) AS last_synced_at
            FROM youtube_videos
            """
        ).fetchone()

        top = db.execute(
            """
            SELECT video_id, title, views
            FROM youtube_videos
            ORDER BY views DESC
            LIMIT 1
            """
        ).fetchone()

    result = dict(row)
    result["most_viewed"] = dict(top) if top else None
    return result
