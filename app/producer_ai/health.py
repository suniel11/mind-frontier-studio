from __future__ import annotations

from app.producer_ai.models import ChannelHealth
from app.projects.manager import dashboard_stats, list_projects


def calculate_channel_health(root) -> ChannelHealth:
    projects = list_projects(root / "projects")
    stats = dashboard_stats(projects)

    text = " ".join(
        f"{project.get('title', '')} {project.get('topic', '')}".lower()
        for project in projects
    )

    total = max(1, len(projects))
    psychology_count = sum(
        text.count(term)
        for term in (
            "psychology", "comparison", "overthinking", "validation",
            "confidence", "fear", "identity", "loneliness",
        )
    )
    philosophy_count = sum(
        text.count(term)
        for term in (
            "philosophy", "stoic", "meaning", "purpose",
            "control", "mediocrity", "happiness",
        )
    )

    psychology_share = min(100, round(psychology_count / total * 14))
    philosophy_share = min(100, round(philosophy_count / total * 14))

    ready = int(stats.get("ready_projects", 0))
    published = int(stats.get("published_projects", 0))
    average_quality = float(stats.get("average_quality", 0) or 0)

    consistency = min(100, published * 12 + ready * 4)
    health_score = round(
        min(100, average_quality) * 0.45
        + consistency * 0.30
        + min(100, len(projects) * 8) * 0.25
    )

    warnings: list[str] = []
    if published < 10:
        warnings.append("More published Shorts are needed before performance conclusions are reliable.")
    if average_quality and average_quality < 80:
        warnings.append("Average production quality is below the current target of 80.")
    if psychology_share > 75:
        warnings.append("The recent content mix is heavily concentrated in psychology.")
    if not warnings:
        warnings.append("The current production mix is balanced and ready for continued publishing.")

    return ChannelHealth(
        total_projects=len(projects),
        ready_projects=ready,
        published_projects=published,
        average_quality=average_quality,
        psychology_share=psychology_share,
        philosophy_share=philosophy_share,
        posting_consistency=consistency,
        health_score=health_score,
        warnings=warnings,
    )
