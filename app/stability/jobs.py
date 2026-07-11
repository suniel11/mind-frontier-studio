from __future__ import annotations

import json
import sqlite3
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.stability.migrations import migrate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path(root: Path) -> Path:
    return root / "studio_memory" / "atlas.db"


def _connect(root: Path) -> sqlite3.Connection:
    migrate(root)
    db = sqlite3.connect(_db_path(root), check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def create_job(
    root: Path,
    job_type: str,
    payload: dict[str, Any] | None = None,
) -> str:
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    now = _now()
    with _connect(root) as db:
        db.execute(
            """
            INSERT INTO background_jobs (
                job_id, job_type, status, progress,
                created_at, updated_at, payload_json
            )
            VALUES (?, ?, 'queued', 0, ?, ?, ?)
            """,
            (
                job_id,
                job_type,
                now,
                now,
                json.dumps(payload or {}),
            ),
        )
    return job_id


def update_job(
    root: Path,
    job_id: str,
    *,
    status: str | None = None,
    progress: float | None = None,
    error: str | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    assignments = ["updated_at = ?"]
    values: list[Any] = [_now()]

    if status is not None:
        assignments.append("status = ?")
        values.append(status)
        if status == "running":
            assignments.append("started_at = COALESCE(started_at, ?)")
            values.append(_now())
        if status in {"complete", "failed", "cancelled"}:
            assignments.append("finished_at = ?")
            values.append(_now())

    if progress is not None:
        assignments.append("progress = ?")
        values.append(max(0.0, min(100.0, float(progress))))

    if error is not None:
        assignments.append("error = ?")
        values.append(error)

    if result is not None:
        assignments.append("result_json = ?")
        values.append(json.dumps(result))

    values.append(job_id)

    with _connect(root) as db:
        db.execute(
            f"""
            UPDATE background_jobs
            SET {", ".join(assignments)}
            WHERE job_id = ?
            """,
            tuple(values),
        )


def run_job(
    root: Path,
    job_id: str,
    function: Callable[..., dict[str, Any]],
    *args,
    **kwargs,
) -> None:
    def worker() -> None:
        update_job(root, job_id, status="running", progress=5)
        try:
            result = function(*args, **kwargs)
            update_job(
                root,
                job_id,
                status="complete",
                progress=100,
                result=result if isinstance(result, dict) else {"result": result},
            )
        except Exception as exc:
            update_job(
                root,
                job_id,
                status="failed",
                error=f"{exc}\n{traceback.format_exc()[-4000:]}",
            )

    thread = threading.Thread(
        target=worker,
        name=job_id,
        daemon=True,
    )
    thread.start()


def get_job(root: Path, job_id: str) -> dict[str, Any] | None:
    with _connect(root) as db:
        row = db.execute(
            "SELECT * FROM background_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()

    if row is None:
        return None

    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json") or "{}")
    item["result"] = json.loads(item.pop("result_json") or "{}")
    return item


def list_jobs(root: Path, limit: int = 25) -> list[dict[str, Any]]:
    with _connect(root) as db:
        rows = db.execute(
            """
            SELECT *
            FROM background_jobs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        ).fetchall()

    jobs = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json") or "{}")
        item["result"] = json.loads(item.pop("result_json") or "{}")
        jobs.append(item)
    return jobs
