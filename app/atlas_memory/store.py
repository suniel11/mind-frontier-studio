from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate


def ensure_memory_tables(root: Path) -> None:
    migrate(root)

    with connect(root) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_entities (
                entity_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                attributes_json TEXT NOT NULL DEFAULT '{}',
                evidence_count INTEGER NOT NULL DEFAULT 0,
                confidence REAL NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 0,
                evidence_json TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL,
                UNIQUE(source_id, relation_type, target_id)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_rebuilds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                entity_count INTEGER NOT NULL DEFAULT 0,
                relation_count INTEGER NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT ''
            )
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_entities_type
            ON memory_entities(entity_type, confidence DESC)
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_relations_source
            ON memory_relations(source_id, relation_type)
            """
        )


def upsert_entity(
    root: Path,
    entity_id: str,
    entity_type: str,
    name: str,
    normalized_name: str,
    attributes: dict[str, Any],
    evidence_count: int,
    confidence: float,
    updated_at: str,
) -> None:
    ensure_memory_tables(root)

    with connect(root) as db:
        db.execute(
            """
            INSERT INTO memory_entities (
                entity_id,
                entity_type,
                name,
                normalized_name,
                attributes_json,
                evidence_count,
                confidence,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_id) DO UPDATE SET
                entity_type = excluded.entity_type,
                name = excluded.name,
                normalized_name = excluded.normalized_name,
                attributes_json = excluded.attributes_json,
                evidence_count = excluded.evidence_count,
                confidence = excluded.confidence,
                updated_at = excluded.updated_at
            """,
            (
                entity_id,
                entity_type,
                name,
                normalized_name,
                json.dumps(attributes, ensure_ascii=False),
                evidence_count,
                confidence,
                updated_at,
            ),
        )


def upsert_relation(
    root: Path,
    source_id: str,
    relation_type: str,
    target_id: str,
    weight: float,
    evidence: list[dict[str, Any]],
    updated_at: str,
) -> None:
    ensure_memory_tables(root)

    with connect(root) as db:
        db.execute(
            """
            INSERT INTO memory_relations (
                source_id,
                relation_type,
                target_id,
                weight,
                evidence_json,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, relation_type, target_id) DO UPDATE SET
                weight = excluded.weight,
                evidence_json = excluded.evidence_json,
                updated_at = excluded.updated_at
            """,
            (
                source_id,
                relation_type,
                target_id,
                float(weight),
                json.dumps(evidence, ensure_ascii=False),
                updated_at,
            ),
        )


def list_entities(
    root: Path,
    entity_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    ensure_memory_tables(root)

    params: list[Any] = []
    where = ""
    if entity_type:
        where = "WHERE entity_type = ?"
        params.append(entity_type)
    params.append(max(1, min(limit, 500)))

    with connect(root) as db:
        rows = db.execute(
            f"""
            SELECT *
            FROM memory_entities
            {where}
            ORDER BY confidence DESC, evidence_count DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

    output = []
    for row in rows:
        item = dict(row)
        item["attributes"] = json.loads(item.pop("attributes_json") or "{}")
        output.append(item)
    return output


def list_relations(root: Path, limit: int = 200) -> list[dict[str, Any]]:
    ensure_memory_tables(root)

    with connect(root) as db:
        rows = db.execute(
            """
            SELECT *
            FROM memory_relations
            ORDER BY weight DESC
            LIMIT ?
            """,
            (max(1, min(limit, 1000)),),
        ).fetchall()

    output = []
    for row in rows:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json") or "[]")
        output.append(item)
    return output
