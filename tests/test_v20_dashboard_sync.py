from pathlib import Path

from app.youtube_sync.incremental_sync import ensure_sync_runs_table
from app.youtube_sync.video_store import ensure_video_table
from app.youtube_sync.dashboard import youtube_dashboard


def test_dashboard_empty_state(tmp_path: Path):
    ensure_video_table(tmp_path)
    ensure_sync_runs_table(tmp_path)

    data = youtube_dashboard(tmp_path)

    assert data["summary"]["imported_videos"] == 0
    assert data["recent_videos"] == []
    assert data["top_videos"] == []
