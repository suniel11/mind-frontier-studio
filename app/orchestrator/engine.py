from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from app.atlas_agents.producer_agent import run_producer_agent
from app.atlas_agents.publishing_agent import run_publishing_agent
from app.atlas_agents.research_agent import run_research_agent
from app.atlas_agents.thumbnail_agent import run_thumbnail_agent
from app.atlas_memory.graph import rebuild_memory_graph
from app.atlas_memory.search import search_memory
from app.orchestrator.store import (
    complete_project,
    create_project_record,
    record_step_finish,
    record_step_start,
)
from app.prediction.engine import predict_performance
from app.workspace.store import save_workspace


def _run_step(
    root: Path,
    project_id: str,
    step_name: str,
    function: Callable[[], dict[str, Any]],
    *,
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    step_id = record_step_start(root, project_id, step_name)
    started = time.perf_counter()

    try:
        output = function()
        record_step_finish(
            root,
            step_id,
            status="complete",
            duration_seconds=time.perf_counter() - started,
            output=output,
        )
        return output
    except Exception as exc:
        fallback_output = fallback or {}
        record_step_finish(
            root,
            step_id,
            status="fallback" if fallback is not None else "failed",
            duration_seconds=time.perf_counter() - started,
            output=fallback_output,
            error=str(exc),
        )
        if fallback is not None:
            return fallback_output
        raise


def build_autonomous_project(
    root: Path,
    topic: str,
    target_seconds: int,
    hook_type: str,
    save_workspace_enabled: bool = True,
) -> dict[str, Any]:
    project_id = create_project_record(
        root,
        topic,
        target_seconds,
        hook_type,
    )

    memory_rebuild = _run_step(
        root,
        project_id,
        "memory_rebuild",
        lambda: rebuild_memory_graph(root),
        fallback={
            "status": "fallback",
            "entity_count": 0,
            "relation_count": 0,
        },
    )

    memory = _run_step(
        root,
        project_id,
        "memory_lookup",
        lambda: {
            "results": search_memory(root, topic, limit=10),
        },
        fallback={"results": []},
    )

    research = _run_step(
        root,
        project_id,
        "research_agent",
        lambda: run_research_agent(root, topic),
        fallback={
            "topic": topic,
            "related_videos": [],
            "content_gaps": [],
            "channel_sample_size": 0,
            "research_brief": f"Create a fresh angle on {topic}.",
        },
    )

    producer = _run_step(
        root,
        project_id,
        "producer_agent",
        lambda: run_producer_agent(root, topic, target_seconds),
        fallback={
            "topic": topic,
            "recommended_hook_type": hook_type,
            "recommended_runtime_seconds": target_seconds,
            "recommended_scene_count": 7,
            "outline": [],
            "cta": "End with a reflective reframe.",
            "producer_prompt": (
                f"Create a {target_seconds}-second Short about {topic}."
            ),
        },
    )

    thumbnail = _run_step(
        root,
        project_id,
        "thumbnail_agent",
        lambda: run_thumbnail_agent(root, topic),
        fallback={
            "topic": topic,
            "concept": {
                "composition": "single subject with negative space",
                "palette": "dark neutral with one accent",
            },
            "thumbnail_prompt": (
                f"Create a cinematic thumbnail for {topic}."
            ),
            "evidence_strength": "low",
        },
    )

    publishing = _run_step(
        root,
        project_id,
        "publishing_agent",
        lambda: run_publishing_agent(root),
        fallback={
            "recommended_day": "Insufficient data",
            "recommended_hour_utc": None,
            "confidence": "low",
            "note": "No publishing evidence available.",
        },
    )

    prediction = _run_step(
        root,
        project_id,
        "prediction_engine",
        lambda: predict_performance(
            root,
            topic,
            target_seconds,
            hook_type,
            (
                publishing.get("recommended_day")
                if publishing.get("recommended_day") != "Insufficient data"
                else None
            ),
            publishing.get("recommended_hour_utc"),
        ),
        fallback={
            "predicted_views_low": 0,
            "predicted_views_high": 0,
            "predicted_retention": 0,
            "predicted_subscribers_low": 0,
            "predicted_subscribers_high": 0,
            "confidence": 0,
            "risk_level": "high",
            "evidence": {
                "method": "Prediction unavailable.",
                "comparable_videos": [],
            },
        },
    )

    warnings = []

    if float(prediction.get("confidence", 0)) < 0.5:
        warnings.append(
            "Prediction confidence is low because historical evidence is limited."
        )

    if not memory.get("results"):
        warnings.append(
            "Atlas Memory has little evidence for this topic."
        )

    if int(research.get("channel_sample_size", 0)) < 5:
        warnings.append(
            "YouTube sample size is still small."
        )

    readiness_score = 0
    readiness_score += min(20, len(memory.get("results", [])) * 3)
    readiness_score += min(20, len(research.get("related_videos", [])) * 3)
    readiness_score += 20 if producer.get("outline") else 8
    readiness_score += 15 if thumbnail.get("thumbnail_prompt") else 0
    readiness_score += 10 if publishing.get("recommended_day") else 0
    readiness_score += round(float(prediction.get("confidence", 0)) * 15)
    readiness_score = min(100, readiness_score)

    confidence = round(
        min(
            1.0,
            float(prediction.get("confidence", 0)) * 0.55
            + min(1.0, len(memory.get("results", [])) / 5) * 0.2
            + min(
                1.0,
                len(research.get("related_videos", [])) / 5,
            ) * 0.25,
        ),
        3,
    )

    plan = {
        "topic": topic,
        "target_seconds": target_seconds,
        "hook_type": hook_type,
        "readiness_score": readiness_score,
        "confidence": confidence,
        "warnings": warnings,
        "memory_rebuild": memory_rebuild,
        "memory": memory,
        "research": research,
        "producer": producer,
        "thumbnail": thumbnail,
        "publishing": publishing,
        "prediction": prediction,
        "execution_summary": {
            "agents_run": [
                "Atlas Memory",
                "Research Agent",
                "Producer Agent",
                "Thumbnail Agent",
                "Publishing Agent",
                "Prediction Engine",
            ],
            "fallbacks_allowed": True,
        },
    }

    workspace_id = None
    if save_workspace_enabled:
        workspace_result = _run_step(
            root,
            project_id,
            "workspace_save",
            lambda: save_workspace(
                root,
                topic,
                target_seconds,
                hook_type,
                "",
                plan,
            ),
            fallback={},
        )
        workspace_id = workspace_result.get("workspace_id")

    status = "ready" if readiness_score >= 55 else "needs_review"

    complete_project(
        root,
        project_id,
        status=status,
        confidence=confidence,
        readiness_score=readiness_score,
        workspace_id=workspace_id,
        plan=plan,
    )

    return {
        "project_id": project_id,
        "status": status,
        "confidence": confidence,
        "readiness_score": readiness_score,
        "workspace_id": workspace_id,
        "plan": plan,
    }
