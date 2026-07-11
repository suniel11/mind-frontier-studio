from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate
from app.youtube_sync.analytics_store import ensure_analytics_tables
from app.youtube_sync.video_store import ensure_video_table


def load_channel_evidence(root: Path) -> dict[str, Any]:
    migrate(root)
    ensure_video_table(root)
    ensure_analytics_tables(root)

    with connect(root) as db:
        rows = [
            dict(row)
            for row in db.execute(
                """
                SELECT
                    yv.video_id,
                    yv.title,
                    yv.description,
                    yv.published_at,
                    yv.is_short,
                    yv.atlas_project_id,
                    COALESCE(p.topic, '') AS project_topic,
                    COALESCE(p.category, 'general') AS category,
                    COALESCE(ya.views, yv.views, 0) AS views,
                    COALESCE(ya.average_view_percentage, 0) AS retention,
                    COALESCE(ya.average_view_duration, 0) AS avg_view_duration,
                    COALESCE(ya.subscribers_gained, 0) AS subscribers_gained,
                    COALESCE(ya.likes, yv.likes, 0) AS likes,
                    COALESCE(ya.comments, yv.comments, 0) AS comments,
                    COALESCE(ya.shares, 0) AS shares
                FROM youtube_videos yv
                LEFT JOIN youtube_video_analytics ya
                    ON ya.video_id = yv.video_id
                LEFT JOIN projects p
                    ON p.project_id = yv.atlas_project_id
                ORDER BY views DESC
                """
            ).fetchall()
        ]

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_category[str(row.get("category") or "general")].append(row)

    category_stats = []
    for category, items in by_category.items():
        category_stats.append(
            {
                "category": category,
                "sample_size": len(items),
                "average_views": round(
                    sum(float(item.get("views", 0)) for item in items)
                    / max(1, len(items)),
                    1,
                ),
                "average_retention": round(
                    sum(float(item.get("retention", 0)) for item in items)
                    / max(1, len(items)),
                    1,
                ),
                "average_subscribers_gained": round(
                    sum(float(item.get("subscribers_gained", 0)) for item in items)
                    / max(1, len(items)),
                    1,
                ),
            }
        )

    category_stats.sort(
        key=lambda item: (
            item["sample_size"] >= 2,
            item["average_retention"],
            item["average_views"],
        ),
        reverse=True,
    )

    return {
        "videos": rows,
        "category_stats": category_stats,
        "sample_size": len(rows),
    }
