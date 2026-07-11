from __future__ import annotations

from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate
from app.atlas_memory.search import search_memory
from app.youtube_sync.analytics_store import ensure_analytics_tables
from app.youtube_sync.video_store import ensure_video_table


def top_videos(root: Path, limit: int = 8) -> list[dict[str, Any]]:
    migrate(root)
    ensure_video_table(root)
    ensure_analytics_tables(root)

    with connect(root) as db:
        rows = db.execute(
            """
            SELECT
                yv.video_id,
                yv.title,
                yv.published_at,
                COALESCE(ya.views, yv.views, 0) AS views,
                COALESCE(ya.average_view_percentage, 0) AS retention,
                COALESCE(ya.subscribers_gained, 0) AS subscribers_gained,
                COALESCE(ya.likes, yv.likes, 0) AS likes,
                COALESCE(ya.comments, yv.comments, 0) AS comments,
                yv.atlas_project_id,
                COALESCE(p.topic, '') AS topic,
                COALESCE(p.category, 'general') AS category
            FROM youtube_videos yv
            LEFT JOIN youtube_video_analytics ya
                ON ya.video_id = yv.video_id
            LEFT JOIN projects p
                ON p.project_id = yv.atlas_project_id
            ORDER BY views DESC
            LIMIT ?
            """,
            (max(1, min(limit, 50)),),
        ).fetchall()

    return [dict(row) for row in rows]


def recent_videos(root: Path, limit: int = 8) -> list[dict[str, Any]]:
    migrate(root)
    ensure_video_table(root)
    ensure_analytics_tables(root)

    with connect(root) as db:
        rows = db.execute(
            """
            SELECT
                yv.video_id,
                yv.title,
                yv.published_at,
                COALESCE(ya.views, yv.views, 0) AS views,
                COALESCE(ya.average_view_percentage, 0) AS retention,
                COALESCE(ya.subscribers_gained, 0) AS subscribers_gained,
                yv.atlas_project_id
            FROM youtube_videos yv
            LEFT JOIN youtube_video_analytics ya
                ON ya.video_id = yv.video_id
            ORDER BY yv.published_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 50)),),
        ).fetchall()

    return [dict(row) for row in rows]


def topic_evidence(root: Path, query: str, limit: int = 10) -> dict[str, Any]:
    memories = search_memory(root, query, limit=limit)

    migrate(root)
    ensure_video_table(root)
    ensure_analytics_tables(root)

    pattern = f"%{query.lower().strip()}%"
    with connect(root) as db:
        rows = db.execute(
            """
            SELECT
                yv.video_id,
                yv.title,
                COALESCE(ya.views, yv.views, 0) AS views,
                COALESCE(ya.average_view_percentage, 0) AS retention,
                COALESCE(ya.subscribers_gained, 0) AS subscribers_gained,
                COALESCE(p.topic, '') AS topic,
                COALESCE(p.category, 'general') AS category
            FROM youtube_videos yv
            LEFT JOIN youtube_video_analytics ya
                ON ya.video_id = yv.video_id
            LEFT JOIN projects p
                ON p.project_id = yv.atlas_project_id
            WHERE LOWER(yv.title) LIKE ?
               OR LOWER(COALESCE(p.topic, '')) LIKE ?
               OR LOWER(COALESCE(p.category, '')) LIKE ?
            ORDER BY views DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, max(1, min(limit, 50))),
        ).fetchall()

    return {
        "memory": memories,
        "videos": [dict(row) for row in rows],
    }
