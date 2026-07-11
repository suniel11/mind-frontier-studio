from __future__ import annotations

from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate
from app.youtube_sync.incremental_sync import ensure_sync_runs_table
from app.youtube_sync.video_store import ensure_video_table


def youtube_dashboard(root: Path) -> dict[str, Any]:
    migrate(root)
    ensure_video_table(root)
    ensure_sync_runs_table(root)

    with connect(root) as db:
        channel = db.execute(
            """
            SELECT
                channel_id,
                title,
                thumbnail_url,
                subscriber_count,
                view_count,
                video_count,
                last_synced_at
            FROM youtube_channels
            ORDER BY last_synced_at DESC
            LIMIT 1
            """
        ).fetchone()

        summary = db.execute(
            """
            SELECT
                COUNT(*) AS imported_videos,
                SUM(CASE WHEN is_short = 1 THEN 1 ELSE 0 END) AS shorts,
                SUM(CASE WHEN is_short = 0 THEN 1 ELSE 0 END) AS long_form,
                COALESCE(SUM(views), 0) AS total_views,
                ROUND(AVG(views), 1) AS average_views,
                SUM(CASE WHEN atlas_project_id IS NULL THEN 1 ELSE 0 END)
                    AS unmatched_videos,
                SUM(CASE WHEN atlas_project_id IS NOT NULL THEN 1 ELSE 0 END)
                    AS matched_videos
            FROM youtube_videos
            """
        ).fetchone()

        recent = db.execute(
            """
            SELECT
                video_id,
                title,
                thumbnail_url,
                published_at,
                views,
                likes,
                comments,
                is_short,
                atlas_project_id
            FROM youtube_videos
            ORDER BY published_at DESC
            LIMIT 12
            """
        ).fetchall()

        top = db.execute(
            """
            SELECT
                video_id,
                title,
                thumbnail_url,
                views,
                likes,
                comments,
                is_short
            FROM youtube_videos
            ORDER BY views DESC
            LIMIT 5
            """
        ).fetchall()

        last_run = db.execute(
            """
            SELECT
                id,
                mode,
                started_at,
                finished_at,
                status,
                channel_count,
                discovered_count,
                refreshed_count,
                error
            FROM youtube_sync_runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    return {
        "channel": dict(channel) if channel else None,
        "summary": dict(summary),
        "recent_videos": [dict(row) for row in recent],
        "top_videos": [dict(row) for row in top],
        "last_sync": dict(last_run) if last_run else None,
    }
