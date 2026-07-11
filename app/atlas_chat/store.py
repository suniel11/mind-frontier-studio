from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_chat_tables(root: Path) -> None:
    migrate(root)

    with connect(root) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS atlas_conversations (
                conversation_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT 'Atlas Conversation'
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS atlas_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id)
                    REFERENCES atlas_conversations(conversation_id)
                    ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_atlas_messages_conversation
            ON atlas_messages(conversation_id, id)
            """
        )


def create_conversation(root: Path, title: str = "Atlas Conversation") -> str:
    ensure_chat_tables(root)
    conversation_id = f"chat-{uuid.uuid4().hex[:12]}"
    now = _now()

    with connect(root) as db:
        db.execute(
            """
            INSERT INTO atlas_conversations (
                conversation_id,
                created_at,
                updated_at,
                title
            )
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, now, now, title[:120]),
        )

    return conversation_id


def add_message(
    root: Path,
    conversation_id: str,
    role: str,
    content: str,
    evidence: list[dict[str, Any]] | None = None,
) -> None:
    ensure_chat_tables(root)
    now = _now()

    with connect(root) as db:
        db.execute(
            """
            INSERT INTO atlas_messages (
                conversation_id,
                role,
                content,
                evidence_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                role,
                content,
                json.dumps(evidence or [], ensure_ascii=False),
                now,
            ),
        )
        db.execute(
            """
            UPDATE atlas_conversations
            SET updated_at = ?
            WHERE conversation_id = ?
            """,
            (now, conversation_id),
        )


def get_messages(
    root: Path,
    conversation_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    ensure_chat_tables(root)

    with connect(root) as db:
        rows = db.execute(
            """
            SELECT role, content, evidence_json, created_at
            FROM atlas_messages
            WHERE conversation_id = ?
            ORDER BY id
            LIMIT ?
            """,
            (conversation_id, max(1, min(limit, 500))),
        ).fetchall()

    output = []
    for row in rows:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json") or "[]")
        output.append(item)
    return output


def list_conversations(root: Path, limit: int = 30) -> list[dict[str, Any]]:
    ensure_chat_tables(root)

    with connect(root) as db:
        rows = db.execute(
            """
            SELECT
                c.conversation_id,
                c.title,
                c.created_at,
                c.updated_at,
                COUNT(m.id) AS message_count
            FROM atlas_conversations c
            LEFT JOIN atlas_messages m
                ON m.conversation_id = c.conversation_id
            GROUP BY c.conversation_id
            ORDER BY c.updated_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        ).fetchall()

    return [dict(row) for row in rows]


def clear_conversation(root: Path, conversation_id: str) -> bool:
    ensure_chat_tables(root)

    with connect(root) as db:
        cursor = db.execute(
            """
            DELETE FROM atlas_conversations
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        )
    return cursor.rowcount > 0
