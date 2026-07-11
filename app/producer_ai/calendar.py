from __future__ import annotations

from datetime import date, timedelta

from app.planning.planner import get_recommendations


def build_weekly_calendar(limit: int = 7) -> list[dict]:
    ideas = get_recommendations(limit=max(limit, 7))
    today = date.today()

    return [
        {
            "date": (today + timedelta(days=index)).isoformat(),
            "day": (today + timedelta(days=index)).strftime("%A"),
            "title": idea.title,
            "prompt": idea.prompt,
            "category": idea.category,
            "score": idea.overall_score,
        }
        for index, idea in enumerate(ideas[:limit])
    ]
