from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate
from app.youtube_sync.channel_sync import stored_channels, sync_channels
from app.youtube_sync.service import youtube_client
from app.youtube_sync.video_store import ensure_video_table, upsert_videos
from app.youtube_sync.video_sync import _thumbnail, parse_duration_seconds


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_sync_runs_table(root: Path) -> None:
    migrate(root)
    with connect(root) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                channel_count INTEGER NOT NULL DEFAULT 0,
                discovered_count INTEGER NOT NULL DEFAULT 0,
                refreshed_count INTEGER NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT ''
            )
            """
        )


def _known_video_ids(root: Path, channel_id: str) -> set[str]:
    ensure_video_table(root)
    with connect(root) as db:
        rows = db.execute(
            """
            SELECT video_id
            FROM youtube_videos
            WHERE channel_id = ?
            """,
            (channel_id,),
        ).fetchall()
    return {row["video_id"] for row in rows}


def _latest_known_ids(root: Path, channel_id: str, limit: int = 50) -> list[str]:
    ensure_video_table(root)
    with connect(root) as db:
        rows = db.execute(
            """
            SELECT video_id
            FROM youtube_videos
            WHERE channel_id = ?
            ORDER BY published_at DESC
            LIMIT ?
            """,
            (channel_id, limit),
        ).fetchall()
    return [row["video_id"] for row in rows]


def _discover_upload_ids(
    client,
    uploads_playlist_id: str,
    known_ids: set[str],
    mode: str,
) -> list[str]:
    discovered: list[str] = []
    page_token: str | None = None
    consecutive_known = 0
    pages_seen = 0

    while True:
        response = (
            client.playlistItems()
            .list(
                part="contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=page_token,
            )
            .execute()
        )

        pages_seen += 1
        for item in response.get("items", []):
            video_id = (
                item.get("contentDetails", {})
                .get("videoId")
            )
            if not video_id:
                continue

            discovered.append(video_id)

            if video_id in known_ids:
                consecutive_known += 1
            else:
                consecutive_known = 0

            if mode == "incremental" and consecutive_known >= 8:
                return discovered

        page_token = response.get("nextPageToken")
        if not page_token:
            break

        if mode == "incremental" and pages_seen >= 3:
            break

    return discovered


def _fetch_video_details(
    client,
    channel_id: str,
    video_ids: list[str],
    synced_at: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    unique_ids = list(dict.fromkeys(video_ids))
    for start in range(0, len(unique_ids), 50):
        batch = unique_ids[start:start + 50]
        if not batch:
            continue

        response = (
            client.videos()
            .list(
                part="snippet,contentDetails,status,statistics",
                id=",".join(batch),
                maxResults=50,
            )
            .execute()
        )

        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            details = item.get("contentDetails", {})
            status = item.get("status", {})
            statistics = item.get("statistics", {})
            duration_seconds = parse_duration_seconds(
                details.get("duration", "")
            )

            records.append(
                {
                    "video_id": item.get("id"),
                    "channel_id": channel_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "thumbnail_url": _thumbnail(snippet),
                    "published_at": snippet.get("publishedAt"),
                    "duration_seconds": duration_seconds,
                    "privacy_status": status.get("privacyStatus", ""),
                    "category_id": snippet.get("categoryId", ""),
                    "tags": snippet.get("tags", []),
                    "views": int(statistics.get("viewCount", 0) or 0),
                    "likes": int(statistics.get("likeCount", 0) or 0),
                    "comments": int(statistics.get("commentCount", 0) or 0),
                    "is_short": duration_seconds <= 60,
                    "last_synced_at": synced_at,
                }
            )

    return records


def run_video_sync(root: Path, mode: str = "incremental") -> dict[str, Any]:
    if mode not in {"incremental", "full"}:
        raise ValueError("mode must be incremental or full")

    ensure_sync_runs_table(root)
    started_at = _now()

    with connect(root) as db:
        cursor = db.execute(
            """
            INSERT INTO youtube_sync_runs (
                mode,
                started_at,
                status
            )
            VALUES (?, ?, 'running')
            """,
            (mode, started_at),
        )
        run_id = int(cursor.lastrowid)

    try:
        channels = stored_channels(root)
        if not channels:
            channels = sync_channels(root).get("channels", [])

        if not channels:
            raise RuntimeError("No connected YouTube channel was found.")

        client = youtube_client(root)
        synced_at = _now()
        discovered_total = 0
        refreshed_total = 0

        for channel in channels:
            channel_id = channel.get("channel_id")
            uploads_playlist_id = channel.get("uploads_playlist_id")
            if not channel_id or not uploads_playlist_id:
                continue

            known_ids = _known_video_ids(root, channel_id)
            discovered_ids = _discover_upload_ids(
                client,
                uploads_playlist_id,
                known_ids,
                mode,
            )

            new_ids = [video_id for video_id in discovered_ids if video_id not in known_ids]
            refresh_ids = (
                discovered_ids
                if mode == "full"
                else list(
                    dict.fromkeys(
                        discovered_ids + _latest_known_ids(root, channel_id, 50)
                    )
                )
            )

            records = _fetch_video_details(
                client,
                channel_id,
                refresh_ids,
                synced_at,
            )
            upsert_videos(root, records)

            discovered_total += len(new_ids)
            refreshed_total += len(records)

        finished_at = _now()
        with connect(root) as db:
            db.execute(
                """
                UPDATE youtube_sync_runs
                SET
                    finished_at = ?,
                    status = 'complete',
                    channel_count = ?,
                    discovered_count = ?,
                    refreshed_count = ?
                WHERE id = ?
                """,
                (
                    finished_at,
                    len(channels),
                    discovered_total,
                    refreshed_total,
                    run_id,
                ),
            )

        return {
            "run_id": run_id,
            "mode": mode,
            "status": "complete",
            "started_at": started_at,
            "finished_at": finished_at,
            "channel_count": len(channels),
            "new_videos": discovered_total,
            "refreshed_videos": refreshed_total,
        }
    except Exception as exc:
        with connect(root) as db:
            db.execute(
                """
                UPDATE youtube_sync_runs
                SET
                    finished_at = ?,
                    status = 'failed',
                    error = ?
                WHERE id = ?
                """,
                (_now(), str(exc), run_id),
            )
        raise
