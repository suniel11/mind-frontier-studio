from __future__ import annotations

from pathlib import Path
from typing import Any

from app.atlas_agents.evidence import load_channel_evidence


def run_thumbnail_agent(root: Path, topic: str) -> dict[str, Any]:
    evidence = load_channel_evidence(root)
    top = sorted(
        evidence["videos"],
        key=lambda item: (
            float(item.get("views", 0)),
            float(item.get("retention", 0)),
        ),
        reverse=True,
    )[:5]

    avg_views = (
        sum(float(item.get("views", 0)) for item in top) / len(top)
        if top else 0
    )

    concept = {
        "composition": "single subject with strong negative space",
        "subject": "close-up human expression or symbolic object",
        "text": "0–3 words maximum",
        "contrast": "high subject-background separation",
        "palette": "dark neutral base with one warm accent",
        "avoid": [
            "crowded layouts",
            "small unreadable text",
            "multiple competing symbols",
        ],
    }

    return {
        "topic": topic,
        "concept": concept,
        "reference_top_videos": [
            {
                "title": item["title"],
                "views": item["views"],
                "retention": item["retention"],
            }
            for item in top
        ],
        "evidence_strength": "medium" if len(top) >= 3 else "low",
        "average_views_top_sample": round(avg_views, 1),
        "thumbnail_prompt": (
            f"Create a cinematic YouTube thumbnail for a video about {topic}. "
            f"Use one emotionally clear subject, strong negative space, dramatic lighting, "
            f"high contrast, no clutter, and no more than three words of text."
        ),
    }
