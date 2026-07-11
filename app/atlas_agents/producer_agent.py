from __future__ import annotations

from pathlib import Path
from typing import Any

from app.atlas_agents.research_agent import run_research_agent


def _recommended_hook(related: list[dict[str, Any]]) -> str:
    retained = [item for item in related if float(item.get("retention", 0)) > 0]
    if not retained:
        return "direct contradiction"

    average = sum(float(item["retention"]) for item in retained) / len(retained)
    return "question" if average >= 70 else "direct contradiction"


def run_producer_agent(
    root: Path,
    topic: str,
    target_seconds: int,
) -> dict[str, Any]:
    research = run_research_agent(root, topic)
    related = research["related_videos"]
    hook_type = _recommended_hook(related)

    scene_count = 7 if target_seconds >= 45 else 6
    beat_seconds = round(target_seconds / scene_count, 1)

    outline = [
        {"beat": "hook", "seconds": beat_seconds, "purpose": "Create immediate tension."},
        {"beat": "setup", "seconds": beat_seconds, "purpose": "Define the problem clearly."},
        {"beat": "recognition", "seconds": beat_seconds, "purpose": "Make the viewer feel seen."},
        {"beat": "escalation", "seconds": beat_seconds, "purpose": "Show the hidden consequence."},
        {"beat": "insight", "seconds": beat_seconds, "purpose": "Introduce the core idea."},
        {"beat": "reframe", "seconds": beat_seconds, "purpose": "Offer a new standard or perspective."},
        {"beat": "ending", "seconds": beat_seconds, "purpose": "Close with a memorable line."},
    ][:scene_count]

    return {
        "topic": topic,
        "recommended_hook_type": hook_type,
        "recommended_runtime_seconds": target_seconds,
        "recommended_scene_count": scene_count,
        "outline": outline,
        "cta": "Use a reflective final line rather than a direct subscribe request.",
        "producer_prompt": (
            f"Create a {target_seconds}-second cinematic documentary Short about {topic}. "
            f"Open with a {hook_type} hook. Use emotional escalation, one core insight, "
            f"and end with a concise reflective reframe. Avoid generic motivational language."
        ),
        "research": research,
    }
