from __future__ import annotations

from pathlib import Path

from app.atlas.database import connect


def ensure_youtube_channel_table(root: Path) -> None:
    with connect(root) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_channels (
                channel_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                thumbnail_url TEXT,
                subscriber_count INTEGER NOT NULL DEFAULT 0,
                view_count INTEGER NOT NULL DEFAULT 0,
                video_count INTEGER NOT NULL DEFAULT 0,
                uploads_playlist_id TEXT,
                last_synced_at TEXT NOT NULL
            )
            """
        )
