from __future__ import annotations

from pathlib import Path
from typing import Any

from googleapiclient.discovery import build

from app.youtube_sync.auth import load_credentials


def youtube_client(root: Path):
    credentials = load_credentials(root)
    if credentials is None:
        raise PermissionError("YouTube is not connected.")
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


def get_channels(root: Path) -> list[dict[str, Any]]:
    client = youtube_client(root)
    response = (
        client.channels()
        .list(
            part="snippet,statistics,contentDetails",
            mine=True,
            maxResults=50,
        )
        .execute()
    )

    channels = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        channels.append(
            {
                "channel_id": item.get("id"),
                "title": snippet.get("title"),
                "description": snippet.get("description", ""),
                "thumbnail": (
                    snippet.get("thumbnails", {})
                    .get("default", {})
                    .get("url")
                ),
                "subscriber_count": int(
                    statistics.get("subscriberCount", 0) or 0
                ),
                "view_count": int(statistics.get("viewCount", 0) or 0),
                "video_count": int(statistics.get("videoCount", 0) or 0),
                "uploads_playlist_id": (
                    item.get("contentDetails", {})
                    .get("relatedPlaylists", {})
                    .get("uploads")
                ),
            }
        )

    return channels
