from pathlib import Path

from app.atlas.database import connect, migrate
from app.atlas_memory.graph import rebuild_memory_graph
from app.atlas_memory.search import search_memory


def test_memory_graph(tmp_path: Path):
    migrate(tmp_path)

    with connect(tmp_path) as db:
        db.execute(
            """
            INSERT INTO projects (
                project_id,
                title,
                topic,
                category,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "project-1",
                "Comparison and Self Worth",
                "comparison",
                "psychology",
                "ready",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
            ),
        )

    result = rebuild_memory_graph(tmp_path)
    assert result["entity_count"] >= 2

    matches = search_memory(tmp_path, "comparison")
    assert matches
    assert matches[0]["entity_type"] == "topic"
