from __future__ import annotations

from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate


def ensure_analytics_tables(root: Path) -> None:
    migrate(root)
    with connect(root) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_video_analytics (
                video_id TEXT PRIMARY KEY,
                views INTEGER NOT NULL DEFAULT 0,
                estimated_minutes_watched REAL NOT NULL DEFAULT 0,
                average_view_duration REAL NOT NULL DEFAULT 0,
                average_view_percentage REAL NOT NULL DEFAULT 0,
                subscribers_gained INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                shares INTEGER NOT NULL DEFAULT 0,
                synced_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_channel_daily (
                day TEXT PRIMARY KEY,
                views INTEGER NOT NULL DEFAULT 0,
                estimated_minutes_watched REAL NOT NULL DEFAULT 0,
                subscribers_gained INTEGER NOT NULL DEFAULT 0,
                average_view_duration REAL NOT NULL DEFAULT 0,
                average_view_percentage REAL NOT NULL DEFAULT 0,
                synced_at TEXT NOT NULL
            )
            """
        )


def upsert_video_analytics(
    root: Path,
    records: list[dict[str, Any]],
) -> int:
    ensure_analytics_tables(root)

    with connect(root) as db:
        for item in records:
            db.execute(
                """
                INSERT INTO youtube_video_analytics (
                    video_id,
                    views,
                    estimated_minutes_watched,
                    average_view_duration,
                    average_view_percentage,
                    subscribers_gained,
                    likes,
                    comments,
                    shares,
                    synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    views = excluded.views,
                    estimated_minutes_watched = excluded.estimated_minutes_watched,
                    average_view_duration = excluded.average_view_duration,
                    average_view_percentage = excluded.average_view_percentage,
                    subscribers_gained = excluded.subscribers_gained,
                    likes = excluded.likes,
                    comments = excluded.comments,
                    shares = excluded.shares,
                    synced_at = excluded.synced_at
                """,
                (
                    item["video_id"],
                    int(item.get("views", 0)),
                    float(item.get("estimated_minutes_watched", 0)),
                    float(item.get("average_view_duration", 0)),
                    float(item.get("average_view_percentage", 0)),
                    int(item.get("subscribers_gained", 0)),
                    int(item.get("likes", 0)),
                    int(item.get("comments", 0)),
                    int(item.get("shares", 0)),
                    item["synced_at"],
                ),
            )

    return len(records)


def replace_daily_analytics(
    root: Path,
    records: list[dict[str, Any]],
) -> int:
    ensure_analytics_tables(root)

    with connect(root) as db:
        for item in records:
            db.execute(
                """
                INSERT INTO youtube_channel_daily (
                    day,
                    views,
                    estimated_minutes_watched,
                    subscribers_gained,
                    average_view_duration,
                    average_view_percentage,
                    synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET
                    views = excluded.views,
                    estimated_minutes_watched = excluded.estimated_minutes_watched,
                    subscribers_gained = excluded.subscribers_gained,
                    average_view_duration = excluded.average_view_duration,
                    average_view_percentage = excluded.average_view_percentage,
                    synced_at = excluded.synced_at
                """,
                (
                    item["day"],
                    int(item.get("views", 0)),
                    float(item.get("estimated_minutes_watched", 0)),
                    int(item.get("subscribers_gained", 0)),
                    float(item.get("average_view_duration", 0)),
                    float(item.get("average_view_percentage", 0)),
                    item["synced_at"],
                ),
            )

    return len(records)
