from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.atlas_agents.evidence import load_channel_evidence


def run_publishing_agent(root: Path) -> dict[str, Any]:
    evidence = load_channel_evidence(root)

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_hour: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for video in evidence["videos"]:
        published = video.get("published_at")
        if not published:
            continue
        try:
            dt = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
        except ValueError:
            continue

        by_day[dt.strftime("%A")].append(video)
        by_hour[dt.hour].append(video)

    def score(items: list[dict[str, Any]]) -> float:
        if not items:
            return 0.0
        avg_views = sum(float(item.get("views", 0)) for item in items) / len(items)
        avg_retention = sum(float(item.get("retention", 0)) for item in items) / len(items)
        return avg_views * 0.4 + avg_retention * 100

    day_scores = sorted(
        (
            {
                "day": day,
                "sample_size": len(items),
                "score": round(score(items), 1),
            }
            for day, items in by_day.items()
        ),
        key=lambda item: (item["sample_size"] >= 2, item["score"]),
        reverse=True,
    )

    hour_scores = sorted(
        (
            {
                "hour": hour,
                "sample_size": len(items),
                "score": round(score(items), 1),
            }
            for hour, items in by_hour.items()
        ),
        key=lambda item: (item["sample_size"] >= 2, item["score"]),
        reverse=True,
    )

    best_day = day_scores[0]["day"] if day_scores else "Insufficient data"
    best_hour = hour_scores[0]["hour"] if hour_scores else None

    return {
        "recommended_day": best_day,
        "recommended_hour_utc": best_hour,
        "day_rankings": day_scores,
        "hour_rankings": hour_scores,
        "confidence": (
            "high"
            if day_scores and day_scores[0]["sample_size"] >= 4
            else "medium"
            if day_scores and day_scores[0]["sample_size"] >= 2
            else "low"
        ),
        "note": "This is descriptive channel evidence, not a causal forecast.",
    }
