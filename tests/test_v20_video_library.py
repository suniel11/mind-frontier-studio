from pathlib import Path

from app.youtube_sync.video_store import (
    ensure_video_table,
    list_videos,
    upsert_videos,
)
from app.youtube_sync.video_sync import parse_duration_seconds


def test_duration_parser():
    assert parse_duration_seconds("PT45S") == 45
    assert parse_duration_seconds("PT1M2S") == 62
    assert parse_duration_seconds("PT1H2M3S") == 3723


def test_video_store_upsert(tmp_path: Path):
    ensure_video_table(tmp_path)
    count = upsert_videos(
        tmp_path,
        [
            {
                "video_id": "abc123",
                "channel_id": "channel-1",
                "title": "Test Short",
                "duration_seconds": 45,
                "is_short": True,
                "views": 100,
                "last_synced_at": "2026-01-01T00:00:00Z",
            }
        ],
    )

    assert count == 1
    rows = list_videos(tmp_path)
    assert rows[0]["video_id"] == "abc123"
    assert rows[0]["is_short"] is True
