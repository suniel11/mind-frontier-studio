from pathlib import Path

from app.atlas.database import connect, migrate
from app.youtube_sync.matcher import (
    apply_match,
    matching_summary,
    suggest_matches,
)
from app.youtube_sync.video_store import ensure_video_table


def seed(tmp_path: Path):
    migrate(tmp_path)
    ensure_video_table(tmp_path)

    with connect(tmp_path) as db:
        db.execute(
            """
            INSERT INTO projects (
                project_id,
                title,
                topic,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "comparison-project",
                "The Quiet Damage of Comparison",
                "comparison and self worth",
                "ready",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
            ),
        )

        db.execute(
            """
            INSERT INTO youtube_videos (
                video_id,
                channel_id,
                title,
                description,
                last_synced_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "yt123",
                "channel-1",
                "The Quiet Damage of Comparison",
                "Why comparison harms your self worth",
                "2026-01-01T00:00:00Z",
            ),
        )


def test_match_suggestion_and_apply(tmp_path: Path):
    seed(tmp_path)

    suggestions = suggest_matches(tmp_path, minimum_score=50)
    assert suggestions[0]["score"] >= 80

    result = apply_match(
        tmp_path,
        "yt123",
        "comparison-project",
    )
    assert result["ok"] is True

    summary = matching_summary(tmp_path)
    assert summary["matched_videos"] == 1
