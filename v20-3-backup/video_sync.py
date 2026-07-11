from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.youtube_sync.channel_sync import stored_channels, sync_channels
from app.youtube_sync.service import youtube_client
from app.youtube_sync.video_store import upsert_videos


_DURATION_PATTERN = re.compile(
    r"^P"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_duration_seconds(value: str) -> int:
    match = _DURATION_PATTERN.match(value or "")
    if not match:
        return 0

    parts = {
        name: int(number or 0)
        for name, number in match.groupdict().items()
    }
    return (
        parts["days"] * 86400
        + parts["hours"] * 3600
        + parts["minutes"] * 60
        + parts["seconds"]
    )


def _thumbnail(snippet: dict[str, Any]) -> str | None:
    thumbnails = snippet.get("thumbnails", {})
    for key in ("maxres", "standard", "high", "medium", "default"):
        url = thumbnails.get(key, {}).get("url")
        if url:
            return url
    return None


def _uploads_video_ids(client, uploads_playlist_id: str) -> list[str]:
    video_ids: list[str] = []
    page_token: str | None = None

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

        for item in response.get("items", []):
            video_id = (
                item.get("contentDetails", {})
                .get("videoId")
            )
            if video_id:
                video_ids.append(video_id)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return video_ids


def sync_video_library(root: Path) -> dict[str, Any]:
    channels = stored_channels(root)
    if not channels:
        channel_result = sync_channels(root)
        channels = channel_result.get("channels", [])

    if not channels:
        raise RuntimeError("No connected YouTube channel was found.")

    client = youtube_client(root)
    synced_at = _now()
    imported: list[dict[str, Any]] = []

    for channel in channels:
        uploads_playlist_id = channel.get("uploads_playlist_id")
        channel_id = channel.get("channel_id")

        if not uploads_playlist_id or not channel_id:
            continue

        ids = _uploads_video_ids(client, uploads_playlist_id)

        for start in range(0, len(ids), 50):
            batch = ids[start:start + 50]
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

                imported.append(
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
                        "comments": int(
                            statistics.get("commentCount", 0) or 0
                        ),
                        "is_short": duration_seconds <= 60,
                        "last_synced_at": synced_at,
                    }
                )

    imported_count = upsert_videos(root, imported)
    return {
        "synced_at": synced_at,
        "imported_count": imported_count,
        "channel_count": len(channels),
    }
