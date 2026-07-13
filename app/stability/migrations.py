from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _database_path(root: Path) -> Path:
    path = root / "studio_memory"
    path.mkdir(parents=True, exist_ok=True)
    return path / "atlas.db"


def _ensure_metadata(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _migration_1(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS background_jobs (
            job_id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            progress REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            error TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            result_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_background_jobs_status
        ON background_jobs(status, created_at DESC)
        """
    )


def _migration_2(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS system_backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            archive_path TEXT NOT NULL,
            database_size_bytes INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT ''
        )
        """
    )


def _column_names(db: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in db.execute(f"PRAGMA table_info({table})")
    }


def _migration_3(db: sqlite3.Connection) -> None:
    """Extend the v21 job table with durable production progress state."""

    columns = _column_names(db, "background_jobs")
    additions = {
        "project_id": "TEXT NOT NULL DEFAULT ''",
        "current_stage": "TEXT NOT NULL DEFAULT 'queued'",
        "completed_stages_json": "TEXT NOT NULL DEFAULT '[]'",
        "total_stages": "INTEGER NOT NULL DEFAULT 0",
        "warnings_json": "TEXT NOT NULL DEFAULT '[]'",
        "cancel_requested": "INTEGER NOT NULL DEFAULT 0",
        "retry_count": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, declaration in additions.items():
        if name not in columns:
            db.execute(
                f"ALTER TABLE background_jobs ADD COLUMN {name} {declaration}"
            )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_background_jobs_project
        ON background_jobs(project_id, created_at DESC)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_background_jobs_type_status
        ON background_jobs(job_type, status, created_at)
        """
    )


MIGRATIONS = [
    Migration(1, "background_jobs", _migration_1),
    Migration(2, "system_backups", _migration_2),
    Migration(3, "persistent_production_jobs", _migration_3),
]


def migrate(root: Path) -> dict:
    path = _database_path(root)
    db = sqlite3.connect(path)
    try:
        _ensure_metadata(db)
        applied = {
            int(row[0])
            for row in db.execute("SELECT version FROM schema_migrations")
        }
        newly_applied = []

        for migration in MIGRATIONS:
            if migration.version in applied:
                continue
            with db:
                migration.apply(db)
                db.execute(
                    """
                    INSERT INTO schema_migrations(version, name)
                    VALUES (?, ?)
                    """,
                    (migration.version, migration.name),
                )
            newly_applied.append(migration.version)

        current = max([0, *applied, *newly_applied])
        return {
            "database": str(path),
            "current_version": current,
            "applied_now": newly_applied,
            "available_version": max(m.version for m in MIGRATIONS),
        }
    finally:
        db.close()


def migration_status(root: Path) -> dict:
    path = _database_path(root)
    if not path.exists():
        return {
            "database": str(path),
            "current_version": 0,
            "available_version": max(m.version for m in MIGRATIONS),
            "pending": [m.version for m in MIGRATIONS],
        }

    db = sqlite3.connect(path)
    try:
        _ensure_metadata(db)
        rows = list(
            db.execute(
                """
                SELECT version, name, applied_at
                FROM schema_migrations
                ORDER BY version
                """
            )
        )
        applied = {int(row[0]) for row in rows}
        return {
            "database": str(path),
            "current_version": max(applied) if applied else 0,
            "available_version": max(m.version for m in MIGRATIONS),
            "pending": [
                m.version for m in MIGRATIONS if m.version not in applied
            ],
            "applied": [
                {
                    "version": row[0],
                    "name": row[1],
                    "applied_at": row[2],
                }
                for row in rows
            ],
        }
    finally:
        db.close()
