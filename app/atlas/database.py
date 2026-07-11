from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = 1


def database_path(root: Path) -> Path:
    data_dir = root / "studio_memory"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "atlas.db"


@contextmanager
def connect(root: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path(root))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def migrate(root: Path) -> None:
    with connect(root) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS atlas_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                topic TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                duration_seconds REAL NOT NULL DEFAULT 0,
                quality_score REAL NOT NULL DEFAULT 0,
                cinema_score REAL NOT NULL DEFAULT 0,
                producer_score REAL NOT NULL DEFAULT 0,
                video_path TEXT,
                thumbnail_path TEXT,
                publish_ready INTEGER NOT NULL DEFAULT 0,
                engine_version TEXT NOT NULL DEFAULT '',
                source_modified_at REAL NOT NULL DEFAULT 0
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS renders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                render_time_seconds REAL NOT NULL DEFAULT 0,
                duration_seconds REAL NOT NULL DEFAULT 0,
                engine_version TEXT NOT NULL DEFAULT '',
                success INTEGER NOT NULL DEFAULT 1,
                estimated_cost REAL NOT NULL DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(project_id)
                    ON DELETE CASCADE
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                published_at TEXT,
                channel TEXT NOT NULL DEFAULT 'Mind Frontier',
                youtube_video_id TEXT,
                views INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                shares INTEGER NOT NULL DEFAULT 0,
                subscribers_gained INTEGER NOT NULL DEFAULT 0,
                watch_time_hours REAL NOT NULL DEFAULT 0,
                average_view_duration_seconds REAL NOT NULL DEFAULT 0,
                average_percentage_viewed REAL NOT NULL DEFAULT 0,
                viewed_percentage REAL NOT NULL DEFAULT 0,
                swiped_away_percentage REAL NOT NULL DEFAULT 0,
                impressions INTEGER NOT NULL DEFAULT 0,
                click_through_rate REAL NOT NULL DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(project_id)
                    ON DELETE CASCADE
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS production_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT,
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )

        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_projects_created
            ON projects(created_at DESC)
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_metrics_project
            ON youtube_metrics(project_id, recorded_at DESC)
            """
        )

        db.execute(
            """
            INSERT INTO atlas_meta(key, value)
            VALUES('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(SCHEMA_VERSION),),
        )


# v20.1 YouTube channel extension
from app.atlas.database_patch import ensure_youtube_channel_table

_original_migrate = migrate

def migrate(root: Path) -> None:
    _original_migrate(root)
    ensure_youtube_channel_table(root)
