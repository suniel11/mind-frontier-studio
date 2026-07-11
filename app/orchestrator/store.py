from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_orchestrator_tables(root: Path) -> None:
    migrate(root)

    with connect(root) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS orchestrated_projects (
                project_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                topic TEXT NOT NULL,
                target_seconds INTEGER NOT NULL,
                hook_type TEXT NOT NULL,
                status TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0,
                readiness_score INTEGER NOT NULL DEFAULT 0,
                workspace_id TEXT,
                plan_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS orchestrator_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT '',
                output_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY(project_id)
                    REFERENCES orchestrated_projects(project_id)
                    ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orchestrated_projects_created
            ON orchestrated_projects(created_at DESC)
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orchestrator_steps_project
            ON orchestrator_steps(project_id, id)
            """
        )


def create_project_record(
    root: Path,
    topic: str,
    target_seconds: int,
    hook_type: str,
) -> str:
    ensure_orchestrator_tables(root)
    project_id = f"orch-{uuid.uuid4().hex[:12]}"
    now = _now()

    with connect(root) as db:
        db.execute(
            """
            INSERT INTO orchestrated_projects (
                project_id,
                created_at,
                updated_at,
                topic,
                target_seconds,
                hook_type,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'running')
            """,
            (
                project_id,
                now,
                now,
                topic,
                target_seconds,
                hook_type,
            ),
        )

    return project_id


def record_step_start(
    root: Path,
    project_id: str,
    step_name: str,
) -> int:
    ensure_orchestrator_tables(root)

    with connect(root) as db:
        cursor = db.execute(
            """
            INSERT INTO orchestrator_steps (
                project_id,
                step_name,
                status,
                started_at
            )
            VALUES (?, ?, 'running', ?)
            """,
            (project_id, step_name, _now()),
        )
        return int(cursor.lastrowid)


def record_step_finish(
    root: Path,
    step_id: int,
    *,
    status: str,
    duration_seconds: float,
    output: dict[str, Any] | None = None,
    error: str = "",
) -> None:
    ensure_orchestrator_tables(root)

    with connect(root) as db:
        db.execute(
            """
            UPDATE orchestrator_steps
            SET
                status = ?,
                finished_at = ?,
                duration_seconds = ?,
                error = ?,
                output_json = ?
            WHERE id = ?
            """,
            (
                status,
                _now(),
                round(duration_seconds, 3),
                error,
                json.dumps(output or {}, ensure_ascii=False),
                step_id,
            ),
        )


def complete_project(
    root: Path,
    project_id: str,
    *,
    status: str,
    confidence: float,
    readiness_score: int,
    workspace_id: str | None,
    plan: dict[str, Any],
    notes: str = "",
) -> None:
    ensure_orchestrator_tables(root)

    with connect(root) as db:
        db.execute(
            """
            UPDATE orchestrated_projects
            SET
                updated_at = ?,
                status = ?,
                confidence = ?,
                readiness_score = ?,
                workspace_id = ?,
                plan_json = ?,
                notes = ?
            WHERE project_id = ?
            """,
            (
                _now(),
                status,
                float(confidence),
                int(readiness_score),
                workspace_id,
                json.dumps(plan, ensure_ascii=False),
                notes,
                project_id,
            ),
        )


def get_project(root: Path, project_id: str) -> dict[str, Any] | None:
    ensure_orchestrator_tables(root)

    with connect(root) as db:
        project = db.execute(
            """
            SELECT *
            FROM orchestrated_projects
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()

        if project is None:
            return None

        steps = db.execute(
            """
            SELECT *
            FROM orchestrator_steps
            WHERE project_id = ?
            ORDER BY id
            """,
            (project_id,),
        ).fetchall()

    item = dict(project)
    item["plan"] = json.loads(item.pop("plan_json") or "{}")

    item["steps"] = []
    for row in steps:
        step = dict(row)
        step["output"] = json.loads(step.pop("output_json") or "{}")
        item["steps"].append(step)

    return item


def list_projects(root: Path, limit: int = 50) -> list[dict[str, Any]]:
    ensure_orchestrator_tables(root)

    with connect(root) as db:
        rows = db.execute(
            """
            SELECT
                project_id,
                created_at,
                updated_at,
                topic,
                target_seconds,
                hook_type,
                status,
                confidence,
                readiness_score,
                workspace_id
            FROM orchestrated_projects
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        ).fetchall()

    return [dict(row) for row in rows]
