from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate
from app.youtube_sync.analytics_store import ensure_analytics_tables
from app.youtube_sync.video_store import ensure_video_table


def _safe_average(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _extract_hook_type(root: Path, project_id: str | None) -> str:
    if not project_id:
        return "unknown"

    path = root / "projects" / project_id / "project.json"
    if not path.exists():
        return "unknown"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown"

    script = data.get("script", {})
    if isinstance(script, dict):
        text = (
            script.get("content")
            or script.get("body")
            or script.get("narration")
            or script.get("hook")
            or ""
        )
    else:
        text = str(script)

    text = re.sub(r"\s+", " ", str(text)).strip()
    opening = text[:180].lower()

    if "?" in opening:
        return "question"
    if opening.startswith(("imagine", "once", "years ago", "one day")):
        return "story"
    if any(term in opening for term in ("but", "yet", "however", "the truth")):
        return "contradiction"
    if any(term in opening for term in ("you", "your")):
        return "direct_address"
    return "statement"


def intelligence_report(root: Path) -> dict[str, Any]:
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
                    yv.published_at,
                    yv.is_short,
                    yv.atlas_project_id,
                    COALESCE(p.category, 'general') AS category,
                    COALESCE(ya.views, yv.views, 0) AS views,
                    COALESCE(ya.average_view_duration, 0)
                        AS average_view_duration,
                    COALESCE(ya.average_view_percentage, 0)
                        AS average_view_percentage,
                    COALESCE(ya.subscribers_gained, 0)
                        AS subscribers_gained,
                    COALESCE(ya.estimated_minutes_watched, 0)
                        AS estimated_minutes_watched,
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

        daily = [
            dict(row)
            for row in db.execute(
                """
                SELECT *
                FROM youtube_channel_daily
                ORDER BY day
                """
            ).fetchall()
        ]

    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_hook: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_weekday: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_hour: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        by_topic[str(row.get("category") or "general")].append(row)

        hook = _extract_hook_type(root, row.get("atlas_project_id"))
        by_hook[hook].append(row)

        published_at = row.get("published_at")
        if published_at:
            try:
                dt = datetime.fromisoformat(
                    str(published_at).replace("Z", "+00:00")
                )
                by_weekday[dt.strftime("%A")].append(row)
                by_hour[f"{dt.hour:02d}:00"].append(row)
            except ValueError:
                pass

    def summarize(groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        output = []
        for key, values in groups.items():
            output.append(
                {
                    "name": key,
                    "sample_size": len(values),
                    "average_views": _safe_average(
                        [float(v.get("views", 0)) for v in values]
                    ),
                    "average_retention": _safe_average(
                        [
                            float(v.get("average_view_percentage", 0))
                            for v in values
                            if float(v.get("average_view_percentage", 0)) > 0
                        ]
                    ),
                    "average_subscribers_gained": _safe_average(
                        [
                            float(v.get("subscribers_gained", 0))
                            for v in values
                        ]
                    ),
                }
            )
        output.sort(
            key=lambda item: (
                item["sample_size"] >= 2,
                item["average_retention"],
                item["average_views"],
            ),
            reverse=True,
        )
        return output

    topic_intelligence = summarize(by_topic)
    hook_intelligence = summarize(by_hook)
    weekday_intelligence = summarize(by_weekday)
    hour_intelligence = summarize(by_hour)

    recommendations: list[str] = []

    if topic_intelligence:
        top = topic_intelligence[0]
        recommendations.append(
            f"Best current topic cluster: {top['name']} "
            f"({top['average_views']} average views, "
            f"{top['average_retention']}% average viewed)."
        )

    reliable_hooks = [
        item for item in hook_intelligence
        if item["sample_size"] >= 2 and item["name"] != "unknown"
    ]
    if reliable_hooks:
        top = reliable_hooks[0]
        recommendations.append(
            f"Best observed hook type: {top['name']} "
            f"across {top['sample_size']} matched videos."
        )
    else:
        recommendations.append(
            "More matched projects are needed before hook conclusions are reliable."
        )

    reliable_days = [
        item for item in weekday_intelligence
        if item["sample_size"] >= 2
    ]
    if reliable_days:
        top = reliable_days[0]
        recommendations.append(
            f"Best observed publishing day: {top['name']}."
        )

    return {
        "video_count": len(rows),
        "topic_intelligence": topic_intelligence,
        "hook_intelligence": hook_intelligence,
        "publishing_days": weekday_intelligence,
        "publishing_hours": hour_intelligence,
        "recommendations": recommendations,
        "growth": {
            "daily": daily,
            "total_views": sum(int(row.get("views", 0)) for row in daily),
            "total_watch_hours": round(
                sum(
                    float(row.get("estimated_minutes_watched", 0))
                    for row in daily
                ) / 60,
                2,
            ),
            "subscribers_gained": sum(
                int(row.get("subscribers_gained", 0))
                for row in daily
            ),
        },
        "limitations": [
            "Impressions and thumbnail CTR are not included in this release.",
            "Hook conclusions require matched projects with readable script data.",
            "Publishing-time results are descriptive, not causal predictions.",
        ],
    }
