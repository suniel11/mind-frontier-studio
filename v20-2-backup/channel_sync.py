from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate
from app.youtube_sync.service import get_channels


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sync_channels(root: Path) -> dict[str, Any]:
    migrate(root)
    channels = get_channels(root)
    synced_at = _now()

    with connect(root) as db:
        for channel in channels:
            db.execute(
                """
                INSERT INTO youtube_channels (
                    channel_id,
                    title,
                    description,
                    thumbnail_url,
                    subscriber_count,
                    view_count,
                    video_count,
                    uploads_playlist_id,
                    last_synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    thumbnail_url = excluded.thumbnail_url,
                    subscriber_count = excluded.subscriber_count,
                    view_count = excluded.view_count,
                    video_count = excluded.video_count,
                    uploads_playlist_id = excluded.uploads_playlist_id,
                    last_synced_at = excluded.last_synced_at
                """,
                (
                    channel["channel_id"],
                    channel["title"],
                    channel.get("description", ""),
                    channel.get("thumbnail"),
                    channel.get("subscriber_count", 0),
                    channel.get("view_count", 0),
                    channel.get("video_count", 0),
                    channel.get("uploads_playlist_id"),
                    synced_at,
                ),
            )

    return {
        "synced_at": synced_at,
        "channel_count": len(channels),
        "channels": channels,
    }


def stored_channels(root: Path) -> list[dict[str, Any]]:
    migrate(root)
    with connect(root) as db:
        rows = db.execute(
            """
            SELECT
                channel_id,
                title,
                description,
                thumbnail_url AS thumbnail,
                subscriber_count,
                view_count,
                video_count,
                uploads_playlist_id,
                last_synced_at
            FROM youtube_channels
            ORDER BY last_synced_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]
