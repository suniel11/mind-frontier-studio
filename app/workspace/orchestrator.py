from __future__ import annotations

from pathlib import Path
from typing import Any

from app.atlas_agents.producer_agent import run_producer_agent
from app.atlas_agents.publishing_agent import run_publishing_agent
from app.atlas_agents.research_agent import run_research_agent
from app.atlas_agents.thumbnail_agent import run_thumbnail_agent
from app.atlas_memory.search import search_memory
from app.prediction.engine import predict_performance


def build_workspace_brief(
    root: Path,
    topic: str,
    target_seconds: int,
    hook_type: str,
) -> dict[str, Any]:
    research = run_research_agent(root, topic)
    producer = run_producer_agent(root, topic, target_seconds)
    thumbnail = run_thumbnail_agent(root, topic)
    publishing = run_publishing_agent(root)
    memory = search_memory(root, topic, limit=8)

    publish_day = publishing.get("recommended_day")
    publish_hour = publishing.get("recommended_hour_utc")

    prediction = predict_performance(
        root,
        topic,
        target_seconds,
        hook_type,
        publish_day if publish_day != "Insufficient data" else None,
        publish_hour,
    )

    readiness_score = 0
    readiness_score += min(25, len(research.get("related_videos", [])) * 4)
    readiness_score += 20 if producer.get("outline") else 0
    readiness_score += 15 if thumbnail.get("thumbnail_prompt") else 0
    readiness_score += 15 if publishing.get("recommended_day") else 0
    readiness_score += round(float(prediction.get("confidence", 0)) * 25)
    readiness_score = min(100, readiness_score)

    warnings = []
    if prediction.get("risk_level") == "high":
        warnings.append("Prediction confidence is low because channel evidence is limited.")
    if len(memory) < 2:
        warnings.append("Atlas Memory has limited evidence for this topic.")
    if research.get("channel_sample_size", 0) < 5:
        warnings.append("Channel sample size is still small.")

    return {
        "topic": topic,
        "target_seconds": target_seconds,
        "hook_type": hook_type,
        "readiness_score": readiness_score,
        "warnings": warnings,
        "research": research,
        "producer": producer,
        "thumbnail": thumbnail,
        "publishing": publishing,
        "prediction": prediction,
        "memory": memory,
    }
