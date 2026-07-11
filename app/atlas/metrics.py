from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.atlas.database import connect, migrate
from app.atlas.models import YouTubeMetricInput


def record_youtube_metrics(root: Path, payload: YouTubeMetricInput) -> int:
    migrate(root)
    now = datetime.now(timezone.utc).isoformat()

    with connect(root) as db:
        exists = db.execute(
            "SELECT 1 FROM projects WHERE project_id = ?",
            (payload.project_id,),
        ).fetchone()
        if not exists:
            raise FileNotFoundError(payload.project_id)

        cursor = db.execute(
            """
            INSERT INTO youtube_metrics (
                project_id, recorded_at, published_at, channel,
                youtube_video_id, views, likes, comments, shares,
                subscribers_gained, watch_time_hours,
                average_view_duration_seconds, average_percentage_viewed,
                viewed_percentage, swiped_away_percentage, impressions,
                click_through_rate
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.project_id,
                now,
                payload.published_at,
                payload.channel,
                payload.youtube_video_id,
                payload.views,
                payload.likes,
                payload.comments,
                payload.shares,
                payload.subscribers_gained,
                payload.watch_time_hours,
                payload.average_view_duration_seconds,
                payload.average_percentage_viewed,
                payload.viewed_percentage,
                payload.swiped_away_percentage,
                payload.impressions,
                payload.click_through_rate,
            ),
        )
        db.execute(
            """
            UPDATE projects
            SET status = 'published', updated_at = ?
            WHERE project_id = ?
            """,
            (now, payload.project_id),
        )
        return int(cursor.lastrowid)
