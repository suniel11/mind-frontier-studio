from pathlib import Path

from app.youtube_sync.analytics_store import ensure_analytics_tables
from app.youtube_sync.intelligence import intelligence_report
from app.youtube_sync.video_store import ensure_video_table


def test_intelligence_empty_state(tmp_path: Path):
    ensure_video_table(tmp_path)
    ensure_analytics_tables(tmp_path)

    report = intelligence_report(tmp_path)

    assert report["video_count"] == 0
    assert "growth" in report
    assert "limitations" in report
