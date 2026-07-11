from __future__ import annotations

from pathlib import Path
from typing import Any

from app.atlas_agents.evidence import load_channel_evidence
from app.atlas_agents.producer_agent import run_producer_agent
from app.atlas_agents.publishing_agent import run_publishing_agent
from app.atlas_agents.thumbnail_agent import run_thumbnail_agent


TOPIC_SEEDS = [
    "comparison",
    "identity",
    "loneliness",
    "fear of mediocrity",
    "validation",
    "overthinking",
    "discipline",
    "meaning",
    "self worth",
    "social pressure",
]


def recommend_next_topics(root: Path, count: int = 5) -> dict[str, Any]:
    evidence = load_channel_evidence(root)
    publishing = run_publishing_agent(root)

    seen = " ".join(
        f"{item.get('title', '')} {item.get('project_topic', '')}".lower()
        for item in evidence["videos"]
    )

    category_bonus = {
        item["category"]: (
            item["average_retention"] * 0.7
            + item["average_views"] * 0.003
        )
        for item in evidence["category_stats"]
    }

    ranked = []
    for topic in TOPIC_SEEDS:
        repetition_penalty = seen.count(topic.lower()) * 8
        novelty = 20 if topic.lower() not in seen else 0

        inferred_category = (
            "psychology"
            if topic in {
                "comparison", "identity", "loneliness", "validation",
                "overthinking", "self worth", "social pressure",
            }
            else "philosophy"
        )

        score = round(
            55
            + novelty
            + category_bonus.get(inferred_category, 0)
            - repetition_penalty
        )
        score = max(0, min(100, score))

        ranked.append(
            {
                "topic": topic,
                "category": inferred_category,
                "score": score,
                "reason": (
                    "Balances channel evidence with novelty and repetition control."
                ),
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    selected = ranked[:count]

    for item in selected:
        item["producer"] = run_producer_agent(root, item["topic"], 45)
        item["thumbnail"] = run_thumbnail_agent(root, item["topic"])

    return {
        "recommendations": selected,
        "publishing": publishing,
        "channel_sample_size": evidence["sample_size"],
    }
