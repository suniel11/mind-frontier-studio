from __future__ import annotations

import re

from app.producer_ai.memory import load_recent_topics, overlap_score
from app.producer_ai.models import TopicAssessment


PSYCHOLOGY_TERMS = {
    "comparison", "overthinking", "identity", "validation", "anxiety",
    "fear", "confidence", "loneliness", "perfectionism", "procrastination",
    "attention", "comfort", "ambition", "people pleasing", "self worth",
}

PHILOSOPHY_TERMS = {
    "stoicism", "meaning", "purpose", "control", "freedom", "mediocrity",
    "suffering", "happiness", "success", "discipline", "mortality",
}

WEAK_TERMS = {
    "motivation", "success tips", "be positive", "never give up",
    "work hard", "inspiration",
}


def _contains_any(text: str, values: set[str]) -> bool:
    return any(value in text for value in values)


def assess_topic(root, topic: str) -> TopicAssessment:
    cleaned = re.sub(r"\s+", " ", topic.strip())
    lower = cleaned.lower()

    hook_score = 58
    curiosity_score = 60
    audience_fit = 62
    originality_score = 68
    production_fit = 72
    reasons: list[str] = []

    if any(word in lower for word in ("why", "hidden", "quiet", "real reason", "cost", "trap")):
        hook_score += 18
        curiosity_score += 16
        reasons.append("The framing creates a clear curiosity gap.")

    if _contains_any(lower, PSYCHOLOGY_TERMS):
        audience_fit += 24
        production_fit += 16
        reasons.append("The topic strongly matches Mind Frontier's psychology audience.")

    if _contains_any(lower, PHILOSOPHY_TERMS):
        audience_fit += 18
        production_fit += 12
        reasons.append("The topic fits the channel's philosophy positioning.")

    if _contains_any(lower, WEAK_TERMS):
        hook_score -= 18
        originality_score -= 20
        reasons.append("The topic uses saturated motivational language.")

    if len(cleaned) > 260:
        hook_score -= 8
        production_fit -= 8
        reasons.append("The prompt is dense and may reduce creative focus.")

    recent_topics = load_recent_topics(root)
    overlap = overlap_score(cleaned, recent_topics)

    if overlap >= 65:
        originality_score -= 24
        reasons.append("A very similar topic already exists in the recent project library.")
    elif overlap >= 40:
        originality_score -= 12
        reasons.append("The topic partially overlaps with recent work.")
    else:
        reasons.append("The topic adds useful variety to the recent content mix.")

    hook_score = max(0, min(100, hook_score))
    curiosity_score = max(0, min(100, curiosity_score))
    audience_fit = max(0, min(100, audience_fit))
    originality_score = max(0, min(100, originality_score))
    production_fit = max(0, min(100, production_fit))

    overall = round(
        hook_score * 0.23
        + curiosity_score * 0.20
        + audience_fit * 0.24
        + originality_score * 0.15
        + production_fit * 0.18
    )

    if overall >= 82:
        verdict = "MAKE IT"
    elif overall >= 68:
        verdict = "GOOD WITH REFINEMENT"
    elif overall >= 50:
        verdict = "REWRITE BEFORE PRODUCTION"
    else:
        verdict = "SKIP"

    suggested_angle = cleaned
    if overall < 82:
        core = cleaned[:150].rstrip(".")
        suggested_angle = (
            f"Why {core.lower()} quietly shapes the way people see themselves"
        )

    return TopicAssessment(
        topic=cleaned,
        overall_score=overall,
        hook_score=hook_score,
        curiosity_score=curiosity_score,
        audience_fit=audience_fit,
        originality_score=originality_score,
        production_fit=production_fit,
        overlap_penalty=overlap,
        verdict=verdict,
        reasons=reasons,
        suggested_angle=suggested_angle,
    )
