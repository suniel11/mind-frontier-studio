from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build

from app.youtube_sync.analytics_store import (
    replace_daily_analytics,
    upsert_video_analytics,
)
from app.youtube_sync.auth import load_credentials


VIDEO_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,"
    "averageViewPercentage,subscribersGained,likes,comments,shares"
)

DAILY_METRICS = (
    "views,estimatedMinutesWatched,subscribersGained,"
    "averageViewDuration,averageViewPercentage"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def analytics_client(root: Path):
    credentials = load_credentials(root)
    if credentials is None:
        raise PermissionError("YouTube is not connected.")
    return build(
        "youtubeAnalytics",
        "v2",
        credentials=credentials,
        cache_discovery=False,
    )


def _rows_to_dicts(response: dict[str, Any]) -> list[dict[str, Any]]:
    headers = [
        header["name"]
        for header in response.get("columnHeaders", [])
    ]
    return [
        dict(zip(headers, row))
        for row in response.get("rows", [])
    ]


def sync_video_analytics(
    root: Path,
    start_date: str = "2005-01-01",
    end_date: str | None = None,
) -> dict[str, Any]:
    client = analytics_client(root)
    end_date = end_date or date.today().isoformat()
    synced_at = _now()

    records: list[dict[str, Any]] = []
    start_index = 1

    while True:
        response = (
            client.reports()
            .query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics=VIDEO_METRICS,
                dimensions="video",
                sort="-views",
                maxResults=200,
                startIndex=start_index,
            )
            .execute()
        )

        rows = _rows_to_dicts(response)
        if not rows:
            break

        for row in rows:
            records.append(
                {
                    "video_id": row.get("video", ""),
                    "views": row.get("views", 0),
                    "estimated_minutes_watched": row.get(
                        "estimatedMinutesWatched", 0
                    ),
                    "average_view_duration": row.get(
                        "averageViewDuration", 0
                    ),
                    "average_view_percentage": row.get(
                        "averageViewPercentage", 0
                    ),
                    "subscribers_gained": row.get(
                        "subscribersGained", 0
                    ),
                    "likes": row.get("likes", 0),
                    "comments": row.get("comments", 0),
                    "shares": row.get("shares", 0),
                    "synced_at": synced_at,
                }
            )

        if len(rows) < 200:
            break
        start_index += len(rows)

    count = upsert_video_analytics(root, records)
    return {
        "synced_at": synced_at,
        "video_analytics_count": count,
        "start_date": start_date,
        "end_date": end_date,
    }


def sync_daily_analytics(
    root: Path,
    start_date: str,
    end_date: str | None = None,
) -> dict[str, Any]:
    client = analytics_client(root)
    end_date = end_date or date.today().isoformat()
    synced_at = _now()

    response = (
        client.reports()
        .query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics=DAILY_METRICS,
            dimensions="day",
            sort="day",
            maxResults=1000,
        )
        .execute()
    )

    records = []
    for row in _rows_to_dicts(response):
        records.append(
            {
                "day": row.get("day"),
                "views": row.get("views", 0),
                "estimated_minutes_watched": row.get(
                    "estimatedMinutesWatched", 0
                ),
                "subscribers_gained": row.get(
                    "subscribersGained", 0
                ),
                "average_view_duration": row.get(
                    "averageViewDuration", 0
                ),
                "average_view_percentage": row.get(
                    "averageViewPercentage", 0
                ),
                "synced_at": synced_at,
            }
        )

    count = replace_daily_analytics(root, records)
    return {
        "synced_at": synced_at,
        "daily_rows": count,
        "start_date": start_date,
        "end_date": end_date,
    }


def sync_all_analytics(
    root: Path,
    start_date: str,
    end_date: str | None = None,
) -> dict[str, Any]:
    video_result = sync_video_analytics(root, start_date, end_date)
    daily_result = sync_daily_analytics(root, start_date, end_date)

    return {
        "video": video_result,
        "daily": daily_result,
    }
