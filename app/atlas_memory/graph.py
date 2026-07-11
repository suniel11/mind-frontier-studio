from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate
from app.atlas_memory.store import (
    ensure_memory_tables,
    upsert_entity,
    upsert_relation,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", value.lower()).split())


def _entity_id(entity_type: str, name: str) -> str:
    return f"{entity_type}:{_normalize(name).replace(' ', '-')}"


def rebuild_memory_graph(root: Path) -> dict[str, Any]:
    migrate(root)
    ensure_memory_tables(root)
    started_at = _now()

    with connect(root) as db:
        cursor = db.execute(
            """
            INSERT INTO memory_rebuilds(started_at, status)
            VALUES (?, 'running')
            """,
            (started_at,),
        )
        rebuild_id = int(cursor.lastrowid)

    try:
        with connect(root) as db:
            rows = [
                dict(row)
                for row in db.execute(
                    """
                    SELECT
                        p.project_id,
                        p.title AS project_title,
                        p.topic,
                        p.category,
                        p.quality_score,
                        p.cinema_score,
                        p.producer_score,
                        yv.video_id,
                        yv.title AS video_title,
                        yv.published_at,
                        yv.views,
                        yv.likes,
                        yv.comments,
                        COALESCE(ya.average_view_percentage, 0) AS retention,
                        COALESCE(ya.subscribers_gained, 0) AS subscribers_gained
                    FROM projects p
                    LEFT JOIN youtube_videos yv
                        ON yv.atlas_project_id = p.project_id
                    LEFT JOIN youtube_video_analytics ya
                        ON ya.video_id = yv.video_id
                    ORDER BY p.created_at DESC
                    """
                ).fetchall()
            ]

        topic_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        category_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for row in rows:
            topic = str(row.get("topic") or row.get("project_title") or "untitled")
            category = str(row.get("category") or "general")
            topic_rows[topic].append(row)
            category_rows[category].append(row)

        updated_at = _now()
        entity_count = 0
        relation_count = 0

        for topic, items in topic_rows.items():
            views = [float(i.get("views", 0) or 0) for i in items if i.get("video_id")]
            retention = [
                float(i.get("retention", 0) or 0)
                for i in items
                if float(i.get("retention", 0) or 0) > 0
            ]
            subscribers = [
                float(i.get("subscribers_gained", 0) or 0)
                for i in items
                if i.get("video_id")
            ]

            attrs = {
                "project_count": len(items),
                "published_count": sum(bool(i.get("video_id")) for i in items),
                "average_views": round(sum(views) / len(views), 2) if views else 0,
                "average_retention": (
                    round(sum(retention) / len(retention), 2) if retention else 0
                ),
                "average_subscribers_gained": (
                    round(sum(subscribers) / len(subscribers), 2)
                    if subscribers else 0
                ),
                "best_project": max(
                    items,
                    key=lambda i: float(i.get("views", 0) or 0),
                ).get("project_id"),
            }

            confidence = min(1.0, len(items) / 6)
            topic_id = _entity_id("topic", topic)
            upsert_entity(
                root,
                topic_id,
                "topic",
                topic,
                _normalize(topic),
                attrs,
                len(items),
                confidence,
                updated_at,
            )
            entity_count += 1

            category = str(items[0].get("category") or "general")
            category_id = _entity_id("category", category)
            upsert_relation(
                root,
                topic_id,
                "belongs_to",
                category_id,
                weight=1.0,
                evidence=[
                    {"project_id": item.get("project_id")}
                    for item in items[:10]
                ],
                updated_at=updated_at,
            )
            relation_count += 1

        for category, items in category_rows.items():
            views = [float(i.get("views", 0) or 0) for i in items if i.get("video_id")]
            retention = [
                float(i.get("retention", 0) or 0)
                for i in items
                if float(i.get("retention", 0) or 0) > 0
            ]

            attrs = {
                "project_count": len(items),
                "average_views": round(sum(views) / len(views), 2) if views else 0,
                "average_retention": (
                    round(sum(retention) / len(retention), 2) if retention else 0
                ),
            }

            category_id = _entity_id("category", category)
            upsert_entity(
                root,
                category_id,
                "category",
                category,
                _normalize(category),
                attrs,
                len(items),
                min(1.0, len(items) / 10),
                updated_at,
            )
            entity_count += 1

        with connect(root) as db:
            db.execute(
                """
                UPDATE memory_rebuilds
                SET
                    finished_at = ?,
                    status = 'complete',
                    entity_count = ?,
                    relation_count = ?
                WHERE id = ?
                """,
                (_now(), entity_count, relation_count, rebuild_id),
            )

        return {
            "status": "complete",
            "entity_count": entity_count,
            "relation_count": relation_count,
            "rebuild_id": rebuild_id,
        }
    except Exception as exc:
        with connect(root) as db:
            db.execute(
                """
                UPDATE memory_rebuilds
                SET
                    finished_at = ?,
                    status = 'failed',
                    error = ?
                WHERE id = ?
                """,
                (_now(), str(exc), rebuild_id),
            )
        raise
