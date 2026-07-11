from __future__ import annotations

from datetime import datetime

from app.planning.planner import get_recommendations
from app.producer_ai.calendar import build_weekly_calendar
from app.producer_ai.health import calculate_channel_health
from app.producer_ai.models import ProducerRecommendation
from app.producer_ai.reviewer import assess_topic


def build_daily_brief(root) -> dict:
    health = calculate_channel_health(root)
    ideas = get_recommendations(limit=10)

    ranked: list[ProducerRecommendation] = []
    for idea in ideas:
        assessment = assess_topic(root, idea.prompt)
        score = round(
            idea.overall_score * 0.55
            + assessment.overall_score * 0.45
        )
        confidence = min(99, max(55, score + 3))
        ranked.append(
            ProducerRecommendation(
                title=idea.title,
                prompt=idea.prompt,
                score=score,
                confidence=confidence,
                category=idea.category,
                reasons=assessment.reasons[:3],
                assessment=assessment,
            )
        )

    ranked.sort(key=lambda item: item.score, reverse=True)
    recommendation = ranked[0] if ranked else None

    hour = datetime.now().hour
    greeting = (
        "Good morning"
        if hour < 12
        else "Good afternoon"
        if hour < 18
        else "Good evening"
    )

    return {
        "greeting": greeting,
        "recommendation": recommendation.model_dump() if recommendation else None,
        "alternatives": [item.model_dump() for item in ranked[1:4]],
        "channel_health": health.model_dump(),
        "weekly_calendar": build_weekly_calendar(),
    }
