from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from statistics import median
from typing import Any

from app.atlas.database import connect, migrate
from app.atlas_memory.search import search_memory
from app.prediction.store import save_prediction
from app.youtube_sync.analytics_store import ensure_analytics_tables
from app.youtube_sync.video_store import ensure_video_table


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", value.lower()).split())


def _load_history(root: Path) -> list[dict[str, Any]]:
    migrate(root)
    ensure_video_table(root)
    ensure_analytics_tables(root)

    with connect(root) as db:
        rows = db.execute(
            """
            SELECT
                yv.video_id,
                yv.title,
                yv.published_at,
                yv.duration_seconds,
                yv.views,
                yv.likes,
                yv.comments,
                yv.atlas_project_id,
                COALESCE(p.topic, '') AS topic,
                COALESCE(p.category, 'general') AS category,
                COALESCE(ya.views, yv.views, 0) AS analytics_views,
                COALESCE(ya.average_view_percentage, 0) AS retention,
                COALESCE(ya.subscribers_gained, 0) AS subscribers_gained
            FROM youtube_videos yv
            LEFT JOIN youtube_video_analytics ya
                ON ya.video_id = yv.video_id
            LEFT JOIN projects p
                ON p.project_id = yv.atlas_project_id
            WHERE yv.is_short = 1
            ORDER BY analytics_views DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def _similarity(topic: str, row: dict[str, Any]) -> float:
    target = _normalize(topic)
    source = _normalize(
        f"{row.get('title', '')} {row.get('topic', '')} {row.get('category', '')}"
    )
    ratio = SequenceMatcher(None, target, source).ratio()
    target_tokens = set(target.split())
    source_tokens = set(source.split())
    overlap = (
        len(target_tokens & source_tokens) / max(1, len(target_tokens | source_tokens))
    )
    return ratio * 0.65 + overlap * 0.35


def _weighted_average(
    rows: list[dict[str, Any]],
    value_key: str,
) -> float:
    weighted_sum = 0.0
    total_weight = 0.0

    for row in rows:
        weight = float(row["similarity"])
        value = float(row.get(value_key, 0) or 0)
        if value <= 0:
            continue
        weighted_sum += value * weight
        total_weight += weight

    return weighted_sum / total_weight if total_weight > 0 else 0.0


def predict_performance(
    root: Path,
    topic: str,
    target_seconds: int,
    hook_type: str,
    publish_day: str | None = None,
    publish_hour_utc: int | None = None,
) -> dict[str, Any]:
    history = _load_history(root)

    scored = []
    for row in history:
        score = _similarity(topic, row)
        if score >= 0.08:
            scored.append({**row, "similarity": score})

    scored.sort(
        key=lambda item: (
            item["similarity"],
            float(item.get("retention", 0) or 0),
            int(item.get("analytics_views", 0) or 0),
        ),
        reverse=True,
    )
    comparable = scored[:12]

    views_history = [
        int(row.get("analytics_views", 0) or 0)
        for row in history
        if int(row.get("analytics_views", 0) or 0) > 0
    ]

    baseline_views = median(views_history) if views_history else 500
    weighted_views = _weighted_average(comparable, "analytics_views") or baseline_views
    weighted_retention = _weighted_average(comparable, "retention") or 55.0
    weighted_subscribers = _weighted_average(comparable, "subscribers_gained")

    runtime_factor = 1.0
    if 35 <= target_seconds <= 50:
        runtime_factor = 1.08
    elif target_seconds > 60:
        runtime_factor = 0.88

    hook_factor = {
        "question": 1.05,
        "story": 1.08,
        "direct contradiction": 1.07,
        "contradiction": 1.07,
        "direct_address": 1.03,
        "statement": 0.98,
    }.get(hook_type.lower(), 1.0)

    publish_factor = 1.0
    if publish_day:
        day_matches = [
            row for row in history
            if str(row.get("published_at") or "").startswith("")
            and publish_day.lower() in str(row.get("published_at") or "").lower()
        ]
        if len(day_matches) >= 2:
            publish_factor = 1.03

    predicted_center = max(
        1,
        weighted_views * runtime_factor * hook_factor * publish_factor,
    )

    sample_size = len(comparable)
    similarity_mean = (
        sum(float(row["similarity"]) for row in comparable) / sample_size
        if sample_size
        else 0
    )

    confidence = min(
        0.92,
        0.25
        + min(sample_size, 10) * 0.05
        + similarity_mean * 0.25,
    )

    spread = max(0.22, 0.62 - confidence * 0.45)
    low = int(max(0, predicted_center * (1 - spread)))
    high = int(predicted_center * (1 + spread))

    retention = min(
        100.0,
        max(
            0.0,
            weighted_retention
            * (1.04 if hook_factor > 1.05 else 1.0)
            * (1.03 if 35 <= target_seconds <= 50 else 0.98),
        ),
    )

    if weighted_subscribers <= 0 and weighted_views > 0:
        weighted_subscribers = weighted_views * 0.002

    subscribers_center = max(0.0, weighted_subscribers * hook_factor)
    subscribers_low = int(max(0, subscribers_center * 0.65))
    subscribers_high = int(max(subscribers_low, subscribers_center * 1.45))

    risk_level = (
        "low"
        if confidence >= 0.72 and sample_size >= 5
        else "medium"
        if confidence >= 0.48
        else "high"
    )

    prediction_id = f"pred-{uuid.uuid4().hex[:12]}"
    memory = search_memory(root, topic, limit=5)

    evidence = {
        "sample_size": sample_size,
        "similarity_mean": round(similarity_mean, 3),
        "baseline_views": int(baseline_views),
        "comparable_videos": [
            {
                "video_id": row["video_id"],
                "title": row["title"],
                "views": int(row.get("analytics_views", 0) or 0),
                "retention": float(row.get("retention", 0) or 0),
                "subscribers_gained": int(row.get("subscribers_gained", 0) or 0),
                "similarity": round(float(row["similarity"]), 3),
            }
            for row in comparable
        ],
        "memory_matches": memory,
        "factors": {
            "runtime_factor": runtime_factor,
            "hook_factor": hook_factor,
            "publish_factor": publish_factor,
        },
        "method": (
            "Evidence-weighted heuristic using similar historical Shorts. "
            "This is not a guaranteed forecast."
        ),
    }

    result = {
        "prediction_id": prediction_id,
        "created_at": _now(),
        "topic": topic,
        "target_seconds": target_seconds,
        "hook_type": hook_type,
        "publish_day": publish_day,
        "publish_hour_utc": publish_hour_utc,
        "predicted_views_low": low,
        "predicted_views_high": high,
        "predicted_retention": round(retention, 1),
        "predicted_subscribers_low": subscribers_low,
        "predicted_subscribers_high": subscribers_high,
        "confidence": round(confidence, 3),
        "risk_level": risk_level,
        "evidence": evidence,
    }

    save_prediction(root, result)
    return result
