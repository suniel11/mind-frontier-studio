from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate


def _rows(db, query: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(query, params).fetchall()]


def dashboard_data(root: Path) -> dict[str, Any]:
    migrate(root)

    with connect(root) as db:
        summary = dict(
            db.execute(
                """
                SELECT
                    COUNT(*) AS total_projects,
                    SUM(CASE WHEN status = 'ready' THEN 1 ELSE 0 END) AS ready_projects,
                    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) AS published_projects,
                    ROUND(AVG(NULLIF(quality_score, 0)), 1) AS average_quality,
                    ROUND(AVG(NULLIF(cinema_score, 0)), 1) AS average_cinema,
                    ROUND(AVG(NULLIF(producer_score, 0)), 1) AS average_producer
                FROM projects
                """
            ).fetchone()
        )

        projects = _rows(
            db,
            """
            SELECT p.*,
                   COALESCE(m.views, 0) AS views,
                   COALESCE(m.likes, 0) AS likes,
                   COALESCE(m.comments, 0) AS comments,
                   COALESCE(m.average_percentage_viewed, 0) AS average_percentage_viewed,
                   COALESCE(m.viewed_percentage, 0) AS viewed_percentage,
                   COALESCE(m.subscribers_gained, 0) AS subscribers_gained
            FROM projects p
            LEFT JOIN youtube_metrics m
              ON m.id = (
                  SELECT id FROM youtube_metrics
                  WHERE project_id = p.project_id
                  ORDER BY recorded_at DESC
                  LIMIT 1
              )
            ORDER BY p.created_at DESC
            """,
        )

        quality_trend = _rows(
            db,
            """
            SELECT substr(created_at, 1, 10) AS day,
                   ROUND(AVG(NULLIF(quality_score, 0)), 1) AS quality,
                   ROUND(AVG(NULLIF(cinema_score, 0)), 1) AS cinema,
                   COUNT(*) AS projects
            FROM projects
            GROUP BY substr(created_at, 1, 10)
            ORDER BY day
            """,
        )

        topic_distribution = _rows(
            db,
            """
            SELECT category, COUNT(*) AS count
            FROM projects
            GROUP BY category
            ORDER BY count DESC
            """,
        )

        youtube_summary = dict(
            db.execute(
                """
                SELECT
                    COALESCE(SUM(latest.views), 0) AS total_views,
                    COALESCE(SUM(latest.likes), 0) AS total_likes,
                    COALESCE(SUM(latest.comments), 0) AS total_comments,
                    COALESCE(SUM(latest.subscribers_gained), 0) AS subscribers_gained,
                    ROUND(AVG(NULLIF(latest.average_percentage_viewed, 0)), 1)
                        AS average_percentage_viewed,
                    ROUND(AVG(NULLIF(latest.viewed_percentage, 0)), 1)
                        AS average_viewed_percentage
                FROM youtube_metrics latest
                WHERE latest.id IN (
                    SELECT MAX(id)
                    FROM youtube_metrics
                    GROUP BY project_id
                )
                """
            ).fetchone()
        )

    return {
        "summary": summary,
        "youtube_summary": youtube_summary,
        "projects": projects,
        "quality_trend": quality_trend,
        "topic_distribution": topic_distribution,
    }


def evidence_report(root: Path) -> dict[str, Any]:
    data = dashboard_data(root)
    projects = data["projects"]

    category_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for project in projects:
        category_rows[str(project.get("category", "general"))].append(project)

    category_performance = []
    for category, rows in category_rows.items():
        published = [row for row in rows if int(row.get("views", 0) or 0) > 0]
        category_performance.append(
            {
                "category": category,
                "projects": len(rows),
                "published_samples": len(published),
                "average_quality": round(
                    sum(float(row.get("quality_score", 0) or 0) for row in rows)
                    / max(1, len(rows)),
                    1,
                ),
                "average_views": round(
                    sum(int(row.get("views", 0) or 0) for row in published)
                    / max(1, len(published)),
                    1,
                ),
                "average_retention": round(
                    sum(float(row.get("average_percentage_viewed", 0) or 0)
                        for row in published)
                    / max(1, len(published)),
                    1,
                ),
            }
        )

    category_performance.sort(
        key=lambda item: (
            item["published_samples"] > 0,
            item["average_views"],
            item["average_quality"],
        ),
        reverse=True,
    )

    recommendations: list[str] = []
    top = category_performance[0] if category_performance else None
    if top and top["published_samples"] >= 2:
        recommendations.append(
            f"Prioritize {top['category']} topics: this category currently has "
            f"the strongest evidence with {top['average_views']} average views."
        )
    else:
        recommendations.append(
            "Enter YouTube metrics for more published Shorts before treating "
            "topic recommendations as evidence-based."
        )

    unpublished_high_quality = [
        project for project in projects
        if project.get("status") != "published"
        and float(project.get("quality_score", 0) or 0) >= 85
    ]
    if unpublished_high_quality:
        recommendations.append(
            f"Publish or review {len(unpublished_high_quality)} high-quality "
            "projects that are not yet marked as published."
        )

    categories = {item["category"] for item in category_performance}
    for missing in ("psychology", "philosophy", "history"):
        if missing not in categories:
            recommendations.append(
                f"The library has no Atlas-classified {missing} project; "
                "consider adding one to improve channel variety."
            )

    return {
        "category_performance": category_performance,
        "recommendations": recommendations,
        "sample_size": int(data["summary"].get("published_projects", 0) or 0),
    }
