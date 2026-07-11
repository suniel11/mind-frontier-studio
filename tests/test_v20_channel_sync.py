from pathlib import Path

from app.atlas.database import connect
from app.atlas.database_patch import ensure_youtube_channel_table


def test_youtube_channel_table(tmp_path: Path):
    ensure_youtube_channel_table(tmp_path)

    with connect(tmp_path) as db:
        db.execute(
            """
            INSERT INTO youtube_channels (
                channel_id,
                title,
                last_synced_at
            )
            VALUES (?, ?, ?)
            """,
            ("channel-1", "Mind Frontier", "2026-01-01T00:00:00Z"),
        )

        row = db.execute(
            "SELECT title FROM youtube_channels WHERE channel_id = ?",
            ("channel-1",),
        ).fetchone()

    assert row["title"] == "Mind Frontier"
