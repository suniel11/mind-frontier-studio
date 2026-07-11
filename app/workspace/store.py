from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_workspace_table(root: Path) -> None:
    migrate(root)

    with connect(root) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS producer_workspaces (
                workspace_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                topic TEXT NOT NULL,
                target_seconds INTEGER NOT NULL,
                hook_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                notes TEXT NOT NULL DEFAULT '',
                brief_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workspaces_updated
            ON producer_workspaces(updated_at DESC)
            """
        )


def save_workspace(
    root: Path,
    topic: str,
    target_seconds: int,
    hook_type: str,
    notes: str,
    brief: dict[str, Any],
) -> dict[str, Any]:
    ensure_workspace_table(root)

    workspace_id = f"ws-{uuid.uuid4().hex[:12]}"
    now = _now()

    with connect(root) as db:
        db.execute(
            """
            INSERT INTO producer_workspaces (
                workspace_id,
                created_at,
                updated_at,
                topic,
                target_seconds,
                hook_type,
                status,
                notes,
                brief_json
            )
            VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?)
            """,
            (
                workspace_id,
                now,
                now,
                topic,
                target_seconds,
                hook_type,
                notes,
                json.dumps(brief, ensure_ascii=False),
            ),
        )

    return {
        "workspace_id": workspace_id,
        "created_at": now,
        "topic": topic,
        "target_seconds": target_seconds,
        "hook_type": hook_type,
        "status": "draft",
        "notes": notes,
        "brief": brief,
    }


def list_workspaces(root: Path, limit: int = 50) -> list[dict[str, Any]]:
    ensure_workspace_table(root)

    with connect(root) as db:
        rows = db.execute(
            """
            SELECT *
            FROM producer_workspaces
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        ).fetchall()

    output = []
    for row in rows:
        item = dict(row)
        item["brief"] = json.loads(item.pop("brief_json") or "{}")
        output.append(item)
    return output


def get_workspace(root: Path, workspace_id: str) -> dict[str, Any] | None:
    ensure_workspace_table(root)

    with connect(root) as db:
        row = db.execute(
            """
            SELECT *
            FROM producer_workspaces
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

    if row is None:
        return None

    item = dict(row)
    item["brief"] = json.loads(item.pop("brief_json") or "{}")
    return item
