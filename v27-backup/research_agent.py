from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.atlas_agents.evidence import load_channel_evidence


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", value.lower()).split())


def run_research_agent(root: Path, topic: str) -> dict[str, Any]:
    evidence = load_channel_evidence(root)
    normalized = _normalize(topic)

    related = []
    for video in evidence["videos"]:
        haystack = _normalize(
            f"{video.get('title', '')} "
            f"{video.get('description', '')} "
            f"{video.get('project_topic', '')}"
        )
        ratio = SequenceMatcher(None, normalized, haystack[: max(len(normalized), 1) * 4]).ratio()
        keyword_overlap = len(set(normalized.split()) & set(haystack.split()))
        score = round(ratio * 60 + keyword_overlap * 10)

        if score >= 20:
            related.append(
                {
                    "video_id": video["video_id"],
                    "title": video["title"],
                    "views": video["views"],
                    "retention": video["retention"],
                    "subscribers_gained": video["subscribers_gained"],
                    "similarity_score": score,
                }
            )

    related.sort(
        key=lambda item: (
            item["similarity_score"],
            item["retention"],
            item["views"],
        ),
        reverse=True,
    )

    gaps = []
    words = [word for word in normalized.split() if len(word) >= 4]
    covered_titles = " ".join(v["title"].lower() for v in related[:10])

    for angle in (
        "hidden cost",
        "social pressure",
        "identity",
        "daily behavior",
        "historical perspective",
        "practical solution",
    ):
        if angle not in covered_titles:
            gaps.append(f"{topic}: {angle}")

    return {
        "topic": topic,
        "related_videos": related[:8],
        "content_gaps": gaps[:5],
        "channel_sample_size": evidence["sample_size"],
        "best_category": (
            evidence["category_stats"][0]
            if evidence["category_stats"]
            else None
        ),
        "research_brief": (
            f"Build the video around a fresh angle on {topic}. "
            f"Use evidence from the related-video list, avoid repeating titles, "
            f"and emphasize one clear emotional or philosophical tension."
        ),
    }
